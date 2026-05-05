"""
FormulaAlignment.py - GPU-accelerated fact alignment for the formula interpreter.

This module extends the VectorSearch infrastructure to support the key
operation needed by the XBRL Query and Rules Language: *alignment*.

Alignment definition
--------------------
Two facts f1 and f2 are *aligned* when they share the same values for every
dimension EXCEPT the concept dimension (xbrl:concept).  That is, they refer to
the same reporting period, same entity, same explicit dimension members, etc.

Naive approach: O(N₁ × N₂) comparisons for each pair of fact sets in a rule.
For large filings (N > 10,000 facts per concept) this is prohibitively slow.

GPU approach (this module)
--------------------------
1. Represent each fact's alignment context as a vector by embedding its
   non-concept dimension tokens and mean-pooling them — identical to how
   VectorSearch.py builds factVecs, but *excluding* the concept token.

2. For a rule that references K fact-query slots, build K × N_k embedding
   matrices (one row per fact).

3. Compute pairwise cosine similarities using a batched matrix multiply:
       S = A_i  @  A_j^T          shape (N_i, N_j)
   Exact alignment ↔  S[p, q] ≈ 1.0   (threshold configurable).

4. Enumerate all K-way aligned groups by intersecting per-pair match lists.

All heavy tensor work runs on the same device (CUDA/MPS/CPU) chosen by
VectorSearch.bestDevice().

See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Optional, Tuple, Any, TYPE_CHECKING

import torch

from arelle.ModelValue import QName
from arelle.XmlValidate import VALID

from ..VectorSearch import (
    XBRLEmbedder, XBRLVectorStore, XbrlCompiledModel,
    buildAlignmentVectors, pairwiseAlignmentScores,
)
from .FormulaValue import AlignmentKey, alignmentKeyOf

if TYPE_CHECKING:
    from arelle.plugin.XbrlModel.XbrlReport import XbrlFact


# ---------------------------------------------------------------------------
# Alignment index: per-fact non-concept embedding
# ---------------------------------------------------------------------------

CONCEPT_DIM_NS  = "https://xbrl.org/2021"
CONCEPT_DIM_LN  = "concept"


def _conceptDimQn(txmyMdl: XbrlCompiledModel) -> Optional[QName]:
    from arelle.ModelValue import qname
    return qname(CONCEPT_DIM_NS, CONCEPT_DIM_LN)


@dataclass
class AlignmentIndex:
    """
    Holds per-fact alignment vectors (non-concept dimensions only).

    factList:   ordered list of XbrlFact objects (index ↔ row in factMat)
    factMat:    (N, D) L2-normalised tensor on device  — one row per fact
    device:     torch.device where factMat lives
    """
    factList: List["XbrlFact"]
    factMat:  torch.Tensor          # (N, D)
    device:   torch.device
    embedDim: int
    embedder: XBRLEmbedder


def buildAlignmentIndex(
    txmyMdl: XbrlCompiledModel,
    facts: List["XbrlFact"],
    embedDim: int = 64,
) -> AlignmentIndex:
    """
    Build an alignment index for a list of facts.

    Each fact is encoded using its *non-concept* dimension tokens only, so
    that two facts with the same entity/period/dimension slice but different
    concepts receive the same (or very similar) vector.

    Parameters
    ----------
    txmyMdl:
        The compiled OIM taxonomy/report model.
    facts:
        Facts to index.
    embedDim:
        Embedding dimension.  Should match the global VectorSearch embedder
        if one already exists on the model, otherwise a new one is created.

    Returns
    -------
    AlignmentIndex ready for use with `alignedPairs` or `alignedGroups`.
    """
    # Delegate to VectorSearch.buildAlignmentVectors which handles
    # embedder creation, caching, and device placement in one place.
    factMat, validFacts = buildAlignmentVectors(txmyMdl, facts, embedDim=embedDim)

    embedder: XBRLEmbedder = txmyMdl._xbrlEmbedder
    store: XBRLVectorStore = txmyMdl._xbrlVectorStore

    return AlignmentIndex(
        factList=validFacts,
        factMat=factMat,
        device=store.device,
        embedDim=store.embedDim,
        embedder=embedder,
    )


# ---------------------------------------------------------------------------
# Pair-wise alignment
# ---------------------------------------------------------------------------

def alignedPairs(
    indexA: AlignmentIndex,
    indexB: AlignmentIndex,
    threshold: float = 0.999,
) -> Iterator[Tuple["XbrlFact", "XbrlFact"]]:
    """
    Yield all (factA, factB) pairs whose non-concept alignment vectors have
    cosine similarity ≥ threshold (i.e. are aligned).

    Uses a single GPU/CPU batch matrix multiply to compute all N_A × N_B
    similarities at once.
    """
    if indexA.factMat.shape[0] == 0 or indexB.factMat.shape[0] == 0:
        return

    # Use the centralised VectorSearch helper for the batch matmul
    S = pairwiseAlignmentScores(indexA.factMat, indexB.factMat)  # (N_A, N_B)

    # Find pairs above threshold
    matches = (S >= threshold).nonzero(as_tuple=False)  # (K, 2)
    for pair in matches:
        i, j = pair[0].item(), pair[1].item()
        yield indexA.factList[i], indexB.factList[j]


# ---------------------------------------------------------------------------
# K-way alignment (K ≥ 2 fact-query slots)
# ---------------------------------------------------------------------------

def alignedGroups(
    txmyMdl: XbrlCompiledModel,
    factSets: List[List["XbrlFact"]],
    threshold: float = 0.999,
    embedDim: int = 64,
) -> Iterator[List["XbrlFact"]]:
    """
    Yield aligned K-tuples: one fact per slot in `factSets`, all aligned.

    Algorithm
    ---------
    For K=1:  yield each fact individually (no alignment required).

    For K=2:  build two indices, call alignedPairs.

    For K>2:  build an index per slot, then iteratively filter:
        - start with the cross-product of (slot0, slot1) aligned pairs,
        - for each additional slot, keep only tuples where the new fact
          aligns (cosine ≥ threshold) with every existing tuple member.

    This is still worst-case O(N^K), but in practice XBRL filings have a
    small number of aligned groups per dimension slice, so K-way alignment
    terminates quickly.  The GPU batch-matmul dominates the runtime.

    Parameters
    ----------
    txmyMdl:
        Compiled OIM model (needed to build alignment indices).
    factSets:
        One list of XbrlFact per fact-query slot in the rule.
    threshold:
        Cosine similarity threshold for "same alignment".  Default 0.999
        allows for minor floating-point rounding.
    embedDim:
        Embedding dimension.

    Yields
    ------
    list[XbrlFact]
        One fact per slot, in the same order as factSets.
    """
    K = len(factSets)
    if K == 0:
        return
    if K == 1:
        for fact in factSets[0]:
            yield [fact]
        return

    # Build per-slot alignment indices
    indices = [buildAlignmentIndex(txmyMdl, fs, embedDim=embedDim) for fs in factSets]

    # Start with slot 0
    # current_groups: list of (alignment_vec, [fact_slot0, ...])
    current_groups: List[Tuple[torch.Tensor, List["XbrlFact"]]] = [
        (indices[0].factMat[i], [indices[0].factList[i]])
        for i in range(len(indices[0].factList))
    ]

    for slotIdx in range(1, K):
        idx = indices[slotIdx]
        if idx.factMat.shape[0] == 0:
            return  # no facts in this slot → no aligned groups possible

        next_groups: List[Tuple[torch.Tensor, List["XbrlFact"]]] = []

        if not current_groups:
            return

        # Stack current group alignment vectors: (G, D)
        groupVecs = torch.stack([g[0] for g in current_groups], dim=0).to(idx.device)
        # S[g, j] = similarity between group g and slot fact j
        S = groupVecs @ idx.factMat.T      # (G, N_slot)
        matches = (S >= threshold).nonzero(as_tuple=False)  # (M, 2)

        for pair in matches:
            g, j = pair[0].item(), pair[1].item()
            groupVec, groupFacts = current_groups[g]
            newFact = idx.factList[j]
            # Combined alignment vector: average (both are already L2-normalised,
            # so averaging and re-normalising gives a good approximation)
            combined = F.normalize((groupVec + idx.factMat[j]).unsqueeze(0), dim=1).squeeze(0)
            next_groups.append((combined, groupFacts + [newFact]))

        current_groups = next_groups
        if not current_groups:
            return

    for _vec, facts in current_groups:
        yield facts


# ---------------------------------------------------------------------------
# Exact alignment (dimension value comparison, no vectors)
# ---------------------------------------------------------------------------

def exactAlignedGroups(
    factSets: List[List["XbrlFact"]],
    conceptQn: Optional[QName] = None,
) -> Iterator[List["XbrlFact"]]:
    """
    Fallback exact-match alignment without vectors.

    Groups facts by their AlignmentKey (frozenset of non-concept dimension
    values).  Yields K-tuples where all slots share the same key.

    This is O(Σ N_k) for building the index plus O(|matching groups|) for
    iteration, and is exact (no threshold).  Use when the vector index is
    unavailable or when correctness is paramount over performance.
    """
    from collections import defaultdict

    if not factSets:
        return
    if len(factSets) == 1:
        for fact in factSets[0]:
            yield [fact]
        return

    # Build per-slot index: alignment_key → [fact, ...]
    slotIndices: List[Dict[AlignmentKey, List["XbrlFact"]]] = []
    for facts in factSets:
        idx: Dict[AlignmentKey, List["XbrlFact"]] = defaultdict(list)
        for fact in facts:
            key = alignmentKeyOf(fact, conceptQn)
            idx[key].append(fact)
        slotIndices.append(idx)

    # Find alignment keys present in ALL slots
    commonKeys = set(slotIndices[0].keys())
    for idx in slotIndices[1:]:
        commonKeys &= set(idx.keys())

    for key in commonKeys:
        # Cartesian product of all per-slot facts sharing the same key
        from itertools import product as _product
        for combo in _product(*[idx[key] for idx in slotIndices]):
            yield list(combo)
