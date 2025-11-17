"""
See COPYRIGHT.md for copyright information.

Unified vector search over XBRL taxonomy + facts using:
- PyTorch embeddings
- Exact cosine similarity (no ANN, no FAISS)
- Automatic device selection (CUDA / MPS / CPU)

Design rationale / hardware model
---------------------------------
- We NEVER call CUDA or Metal (MPS) directly.
- Instead, we:
    * Choose a torch.device: "cuda", "mps", or "cpu".
    * Move the embedding layer and all vectors to that device.
    * Run all encoding and search operations with PyTorch tensor ops.
- This means:
    * On Windows/Linux with NVIDIA → CUDA kernels do the work.
    * On macOS with Apple Silicon → MPS (Metal Performance Shaders) does the work.
    * On other systems → CPU with vectorized math (SIMD) does the work.
- Search is EXACT:
    * We compute cosine similarity against every stored vector.
    * No approximate index; no results are “missed” due to ANN heuristics.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Literal

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# --------------------------------------------------------------------
# Device selection
# --------------------------------------------------------------------

def bestDevice() -> torch.device:
    """
    Decide where all heavy tensor work will run.

    Priority:
      1. CUDA  (NVIDIA GPUs on Windows/Linux)
      2. MPS   (Apple Silicon GPUs via Metal on macOS)
      3. CPU   (fallback)

    All tensors that matter (embeddings, fact/taxonomy vectors,
    cosine similarity search) are created on this device so that:
      - matrix multiplications and embedding lookups are GPU-accelerated
        when hardware is available.
      - code remains portable with a single path.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

# --------------------------------------------------------------------
# Tokenization / vocabulary
# --------------------------------------------------------------------

def buildXbrlVocab(txmyMdl: XbrlTaxonomyModel) -> Tuple[Dict[str, int], Dict[int, str]]:
    """
    Collect unique tokens from an OIM Taxonomy Model including factsets and return mappings.

    Tokens are normalized as:
      - xbrl:concept::...
      - exp:CountryDimension::MemberQName or value
      - xbrl:unit::...
      - xbrl:period::...

    Rationale:
      - We want a single embedding space shared by all XBRL "aspects":
        concepts, dimensions, units, periods.
      - By putting prefixes in the token string, we keep namespaces
        clear and avoid collisions.

    """
    tokens = set()

    for coreDim, xbrlClass in (("xbrl:concept", XbrlConcept),
                               ("xbrl:concept", XbrlDimension),
                               ("xbrl:member", XbrlMember),
                               ("xbrl:unit", XbrlUnit),
                               ("xbrl:cube", XbrlCube),
                               ):
        for obj in txmyMdl.filterNamedObjects(xbrlClass):
            tokens.add(f"{coreDim}::{obj.name}")
            

    # axes and explicit members
    for cubeObj in txmy.cubes:
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects.get(dimQn)
            for memQn in cubeDimObj.allowedMembers(txmyMdl):
                tokens.add(f"{dimQn}::{memQn}")

    # from facts
    for reportQn, reportObj in txmyMdl.reports.items():
        for fact in reportObj.facts.values():
            for qn, value in fact.dimensions.items():
                tokens.add(f"{qn}::{value}")

    token_list = sorted(tokens)
    tok2id = {t: i for i, t in enumerate(token_list)}
    id2tok = {i: t for t, i in tok2id.items()}
    return tok2id, id2tok


# --------------------------------------------------------------------
# Embedding model
# --------------------------------------------------------------------

class XBRLEmbedder(nn.Module):
    """
    Wraps a single nn.Embedding used for all XBRL tokens.

    Key design points:
      - The embedding matrix is moved to the chosen device (CUDA/MPS/CPU)
        in __init__ via self.to(device).
      - All token → vector operations happen on that device.
      - The model is intentionally simple; training can be layered on later.
    """
    def __init__(self, vocab_size: int, embed_dim: int, device: torch.device):
        super().__init__()
        # GPU/CPU: embedding table lives where we send the module
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.to(device)  # <-- GPU/MPS/CPU placement (hot path decision)

    @property
    def device(self) -> torch.device:
        return self.embedding.weight.device

    def tokenVec(self, token_id: int) -> torch.Tensor:
        """
        Single token ID → (embed_dim,) tensor on current device.

        GPU hot path:
          - This is an embedding lookup; on CUDA/MPS it becomes a GPU kernel
            fetching a row from the embedding matrix in GPU memory.
        """
        idx = torch.tensor([token_id], device=self.device)
        return self.embedding(idx)[0]

    def combine(self, ids: List[int], weights: List[float] | None = None) -> torch.Tensor:
        """
        Combine multiple token IDs into one vector by weighted average.
        Returns (embed_dim,) tensor.

        GPU hot path:
          - Converts ids to a tensor on self.device.
          - Embedding lookup produces a (n, D) tensor on GPU/CPU.
          - Weighted average is a few vector ops (mul, sum) on that device.
        """
        if not ids:
            raise ValueError("No token IDs provided to combine().")

        ids_tensor = torch.tensor(ids, device=self.device)
        vecs = self.embedding(ids_tensor)  # (n, embed_dim) on CUDA/MPS/CPU

        if weights is None:
            return vecs.mean(dim=0)

        w = torch.tensor(weights, dtype=vecs.dtype, device=self.device)
        w = w / w.sum()
        return (vecs * w.unsqueeze(1)).sum(dim=0)

    def encodeFact(
        self,
        concept_id: int,
        dim_ids: List[int],
        unit_id: int,
        period_id: int,
        weights: Dict[str, float] | None = None,
    ) -> torch.Tensor:
        """
        Encode a fact: combine concept + dims + unit + period into one vector.
        weights: optional per-part weights: keys: "concept", "dims", "unit", "period".
        Returns (embed_dim,) tensor.

        Rationale:
          - A fact's semantic position in vector space is an aggregate of
            its aspects. We currently use a weighted average for simplicity.
          - All math happens on the same device as the embedding matrix.
        """
        ids: List[int] = []
        ws: List[float] = []

        if weights is None:
            weights = {"xbrl:concept": 1.0, "dims": 1.0, "xbrl:unit": 1.0, "period": 1.0}

        # concept
        ids.append(concept_id)
        ws.append(weights.get("concept", 1.0))

        # each dimension gets same weight share of the "dims" block
        if dim_ids:
            dim_weight_total = weights.get("dims", 1.0)
            each_dim_weight = dim_weight_total / len(dim_ids)
            for d in dim_ids:
                ids.append(d)
                ws.append(each_dim_weight)

        # unit
        ids.append(unit_id)
        ws.append(weights.get("unit", 1.0))

        # period
        ids.append(period_id)
        ws.append(weights.get("period", 1.0))

        return self.combine(ids, ws)

    def encodeAspects(
        self,
        aspect_token_ids: List[int],
        aspect_weights: List[float] | None = None,
    ) -> torch.Tensor:
        """
        Encode an arbitrary set of aspect tokens (for queries).
        Returns (embed_dim,) tensor.

        This is the same operation as encodeFact(...) but without
        imposing XBRL structure; useful for partial-aspect searches.
        """
        return self.combine(aspect_token_ids, aspect_weights)


# --------------------------------------------------------------------
# Data structures for stored vectors
# --------------------------------------------------------------------

@dataclass
class IndexEntry:
    kind: Literal["taxonomy", "fact"]
    key: str           # e.g. token string or "FACT::<idx>"
    payload: dict      # original JSON or metadata


@dataclass
class XBRLVectorStore:
    """
    Holds normalized vectors and their metadata for taxonomy and facts.

    All tensors here (taxonomy_vecs, fact_vecs) are:
      - row-normalized (L2=1) to support cosine similarity as dot product
      - allocated on the same device as the embedder (CUDA/MPS/CPU)
    """
    device: torch.device
    embed_dim: int
    taxonomy_vecs: torch.Tensor | None      # (N_tax, D) normalized
    fact_vecs: torch.Tensor | None          # (N_fact, D) normalized
    taxonomy_entries: List[IndexEntry]
    fact_entries: List[IndexEntry]


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def factToComponentIds(fact: XbrlFact, tok2id: Dict[str, int]) -> Tuple[int, List[int], int, int]:
    """
    Turn a fact JSON object into token IDs for:
      - concept
      - dimension members
      - unit
      - period
    """

    concept_id = unit_id = period_id = None
    dim_ids: List[int] = []
    for qn, value in fact.factDimensions.items():
        pQn = str(qn)
        tok = f"{pQn}::{value}"
        id = tok2id[tok]
        if pQn == "xbrl:concept":
            concept_id = id
        elif pQn == "xbrl:unit":
            unit_id = id
        elif pQn == "xbrl:period":
            period_id = id
        else:
            dim_ids.append(id)

    return concept_id, dim_ids, unit_id, period_id


def l2NormalizeRows(t: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """
    Row-wise L2 normalization.

    GPU hot path:
      - For (N, D) tensor on CUDA/MPS, this is a few fast vector ops.
      - Used so that cosine similarity becomes a simple dot product.
    """
    norms = torch.linalg.norm(t, dim=1, keepdim=True)
    return t / (norms + eps)


# --------------------------------------------------------------------
# Build embedder + vector store
# --------------------------------------------------------------------

def buildXbrlVectors(
    txmyMdl: XbrlTaxonomyModel,
    embed_dim: int = 64,
    device_hint: str | None = None,
) -> Tuple[XBRLEmbedder, Dict[str, int], Dict[int, str], XBRLVectorStore]:
    """
    Build:
      - token vocabulary
      - XBRLEmbedder on chosen device
      - taxonomy vectors (one per concept/axis-member/unit)
      - fact vectors (one per fact)
      - XBRLVectorStore with normalized vectors and metadata

    All heavy work (embeddings & normalization) is on device:
      - CUDA → GPU kernels
      - MPS  → Metal on Apple Silicon
      - CPU  → vectorized CPU ops
    """
    # Device decision is centralized here
    device = bestDevice() if device_hint is None else torch.device(device_hint)
    print("Using device:", device)

    tok2id, id2tok = buildXbrlVocab(txmyMdl)
    vocab_size = len(tok2id)
    print(f"Vocab size: {vocab_size}")

    embedder = XBRLEmbedder(vocab_size, embed_dim, device=device)

    taxonomy_entries: List[IndexEntry] = []
    fact_entries: List[IndexEntry] = []

    # --------- taxonomy vectors ----------
    txmy_vecs_list: List[torch.Tensor] = []

    # concepts etc
    for coreDim, xbrlClass in (("xbrl:concept", XbrlConcept),
                               ("xbrl:concept", XbrlDimension),
                               ("xbrl:member", XbrlMember),
                               ("xbrl:unit", XbrlUnit),
                               ("xbrl:cube", XbrlCube),
                               ):
        for obj in txmyMdl.filterNamedObjects(xbrlClass):
            tok = f"{coreDim}::{obj.name}"
            tid = tok2id[tok]
            v = embedder.tokenVec(tid)  # GPU/CPU embedding lookup
            taxonomy_entries.append(IndexEntry(kind="taxonomy", key=tok, payload={coreDim: c}))
            txmy_vecs_list.append(v)

    # axes and explicit members
    for cubeObj in txmy.cubes:
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects.get(dimQn)
            for memQn in cubeDimObj.allowedMembers(txmyMdl):
                tok = f"{dimQn}::{memQn}"
                tid = tok2id[tok]
                v = embedder.tokenVec(tid)
                taxonomy_entries.append(
                    IndexEntry(kind="taxonomy", key=tok, payload={"dimension": str(dimQn), "member": str(memQn)})
                )
                txmy_vecs_list.append(v)

    taxonomy_vecs = None
    if txmy_vecs_list:
        taxonomy_vecs = torch.stack(txmy_vecs_list, dim=0)  # (N_tax, D)
        taxonomy_vecs = l2NormalizeRows(taxonomy_vecs)   # normalization on device

    # --------- fact vectors ----------
    fact_vecs_list: List[torch.Tensor] = []

    # from facts
    for reportQn, reportObj in txmyMdl.reports.items():
        for fact in reportObj.facts.values():
            concept_id, dim_ids, unit_id, period_id = factToComponentIds(fact, tok2id)
            fv = embedder.encodeFact(concept_id, dim_ids, unit_id, period_id)  # GPU/CPU
            fact_entries.append(IndexEntry(kind="fact", key=f"{fact.name}", payload=fact))
            fact_vecs_list.append(fv)

    fact_vecs = None
    if fact_vecs_list:
        fact_vecs = torch.stack(fact_vecs_list, dim=0)     # (N_fact, D)
        fact_vecs = l2NormalizeRows(fact_vecs)           # normalization on device

    store = XBRLVectorStore(
        device=device,
        embed_dim=embed_dim,
        taxonomy_vecs=taxonomy_vecs,
        fact_vecs=fact_vecs,
        taxonomy_entries=taxonomy_entries,
        fact_entries=fact_entries,
    )

    return embedder, tok2id, id2tok, store


    # from facts
    for reportQn, reportObj in txmyMdl.reports.items():
        for fact in reportObj.facts.values():
            for qn, value in fact.dimensions.items():
                tokens.add(f"{qn}::{value}")



# --------------------------------------------------------------------
# Exact search using cosine similarity
# --------------------------------------------------------------------

def searchXbrl(
    query_aspects: List[str],
    embedder: XBRLEmbedder,
    tok2id: Dict[str, int],
    store: XBRLVectorStore,
    domain: Literal["taxonomy", "facts", "both"] = "both",
    top_k: int = 5,
) -> List[Tuple[float, IndexEntry]]:
    """
    query_aspects: list of token strings, e.g.:
        "CONCEPT::us-gaap:RevenueFromContractWithCustomer"
        "AXIS::StatementBusinessSegmentsAxis=EuropeMember"
        "UNIT::iso4217:USD"
        "PERIOD::2024-12-31"

    domain: "taxonomy" | "facts" | "both"

    Returns a list of (score, IndexEntry) sorted by descending cosine similarity.

    VERY IMPORTANT:
      - This is an EXACT search.
      - We compute cosine similarity between the query vector and every stored
        vector in the chosen domain using a dense matrix-vector product.
      - Complexity is O(N * D), but on CUDA/MPS that's extremely fast for the
        XBRL scales we care about (thousands to low hundreds of thousands).
      - No approximate index, no risk of "missing" nearest neighbors.
    """
    # Map tokens to IDs, ignore unknown
    aspect_ids = [tok2id[t] for t in query_aspects if t in tok2id]
    if not aspect_ids:
        raise ValueError("None of the query_aspects exist in tok2id. Check token strings.")

    # Encode query aspects into a vector on same device, normalize
    q_vec = embedder.encodeAspects(aspect_ids).to(store.device)
    q_vec = F.normalize(q_vec.unsqueeze(0), dim=1)  # (1, D), on CUDA/MPS/CPU

    results: List[Tuple[float, IndexEntry]] = []

    # ---- taxonomy search (GPU hot path: matrix-vector dot) ----
    if domain in ("taxonomy", "both") and store.taxonomy_vecs is not None:
        tv = store.taxonomy_vecs  # (N_tax, D), already normalized, on device
        # EXACT cosine similarity via dot product on device
        sims = (tv @ q_vec.T).squeeze(1)  # (N_tax,)
        k = min(top_k, sims.shape[0])
        scores, idxs = torch.topk(sims, k)
        for s, idx in zip(scores.tolist(), idxs.tolist()):
            entry = store.taxonomy_entries[idx]
            results.append((float(s), entry))

    # ---- fact search (same GPU hot path) ----
    if domain in ("facts", "both") and store.fact_vecs is not None:
        fv = store.fact_vecs  # (N_fact, D), already normalized, on device
        sims = (fv @ q_vec.T).squeeze(1)  # (N_fact,)
        k = min(top_k, sims.shape[0])
        scores, idxs = torch.topk(sims, k)
        for s, idx in zip(scores.tolist(), idxs.tolist()):
            entry = store.fact_entries[idx]
            results.append((float(s), entry))

    # Merge+sort if both
    results.sort(key=lambda x: x[0], reverse=True)
    if domain == "both":
        results = results[:top_k]

    return results


# --------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------


def demo():
    """
    Run a small demo on the toy EXAMPLE_OIM (OIM-JSON).

    This:
      - Builds the vocabulary and embeddings.
      - Encodes taxonomy and facts.
      - Issues the same query across facts, taxonomy, and both.
      - Prints top matches with cosine similarity scores.

    On CUDA/MPS, this will exercise:
      - embedding lookups
      - vector aggregation
      - normalization
      - dense matrix-vector dot products
    all on the GPU.
    """
    embedder, tok2id, id2tok, store = buildXbrlVectors(EXAMPLE_OIM, embed_dim=32)

    # Example query: concept + segment member
    query_aspects = [
        "CONCEPT::us-gaap:RevenueFromContractWithCustomer",
        "AXIS::StatementBusinessSegmentsAxis=EuropeMember",
    ]

    print("\n=== Search FACTS matching concept+segment (partial aspects) ===")
    fact_hits = searchXbrl(
        query_aspects,
        embedder,
        tok2id,
        store,
        domain="facts",
        top_k=5,
    )
    for score, entry in fact_hits:
        print(f"score={score:.3f}  kind={entry.kind}  payload={entry.payload}")

    print("\n=== Search TAXONOMY similar to concept+segment ===")
    tax_hits = searchXbrl(
        query_aspects,
        embedder,
        tok2id,
        store,
        domain="taxonomy",
        top_k=5,
    )
    for score, entry in tax_hits:
        print(f"score={score:.3f}  kind={entry.kind}  key={entry.key}  payload={entry.payload}")

    print("\n=== Search BOTH (facts+taxonomy) with the same query ===")
    both_hits = searchXbrl(
        query_aspects,
        embedder,
        tok2id,
        store,
        domain="both",
        top_k=5,
    )
    for score, entry in both_hits:
        print(f"score={score:.3f}  kind={entry.kind}  key={entry.key}  payload={entry.payload}")


if __name__ == "__main__":
    demo()
