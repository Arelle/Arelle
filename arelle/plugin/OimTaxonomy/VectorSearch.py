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

What’s in this module
---------------------
- Single-query search: `searchXbrl(...)`
- Multi-query search: `searchFactsBatchTopk(...)` + `encodeQueriesMean(...)`
* Computes top-k matches for EACH query in parallel on GPU/CPU.
* Keeps the existing single-query API intact.

Notes on multi-query design
---------------------------
- Queries are initially variable-length lists of aspect tokens.
- To batch them efficiently, we convert each query to a fixed-size vector (D,)
  by combining the embeddings of its aspect tokens (masked mean).
- Once we have Q = (B, D) query vectors, we compute all similarities at once:
    scores = facts (N, D) @ Q^T (D, B) = (N, B)
  and then take top-k per query (per column / per query row after transpose).

"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Literal
from ordered_set import OrderedSet
import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .XbrlCube import XbrlCube
from .XbrlTaxonomyModule import referencableObjectTypes

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

DEVICE_DESCRIPTION = {
    "cuda": "NVIDIA GPUs",
    "mps":  "Apple Silicon GPUs",
    "cpu":  "CPU vectorized math"
    }

# --------------------------------------------------------------------
# Tokenization / vocabulary
# --------------------------------------------------------------------

def buildXbrlVocab(txmyMdl: XbrlTaxonomyModel, valueTokensOffset: int) -> Tuple[Dict[str, int], Dict[int, str]]:
    """
    Collect unique tokens from an OIM Taxonomy Model including factsets and return mappings.

    Tokens are normalized as:
      - every object in xbrlModel.xbrlObjects is a token whose value is object.xbrlMdlObjIndex (integer from 0)
      - every value which is not an xbrl object is tokenized herein (starting at txmyMdl.initialValueToken

    Rationale:
      - We want a single embedding space shared by all XBRL "aspects":
        concepts, dimensions, units, periods.
      - By putting prefixes in the token string, we keep namespaces
        clear and avoid collisions.

    """
    cubeTokens = set()
    factTokens = set()
    valueTokens = OrderedSet()

    # from cubes
    for cubeObj in txmyMdl.filterNamedObjects(XbrlCube):
        c = cubeObj.xbrlMdlObjIndex
        tokens = []
        for cubeDimObj in cubeObj.cubeDimensions:
            dimQn = cubeDimObj.dimensionName
            dimObj = txmyMdl.namedObjects.get(dimQn)
            if dimObj:
                d = dimObj.xbrlMdlObjIndex
                tokens.append( d )          # hasDimension for queries wildcarding dimension
                for memQn in cubeDimObj.allowedMembers(txmyMdl):
                    memObj = txmyMdl.namedObjects.get(memQn)
                    if memObj:
                        v = ( d, memObj.xbrlMdlObjIndex )
                        t = valueTokens.add( v ) + valueTokensOffset
                        tokens.append( t ) # dimension value for dimension value queries
        cubeTokens.add( (c, tuple(tokens) ) )

    # from factspace
    for reportQn, reportObj in txmyMdl.reports.items():
        for factspace in reportObj.factspaces.values():
            f = factspace.xbrlMdlObjIndex
            tokens = []
            for qn, value in factspace.dimensions.items():
                dimObj = txmyMdl.namedObjects.get(qn)
                if dimObj:
                    d = dimObj.xbrlMdlObjIndex
                    if isinstance(value, QName) and value in txmyMdl.namedObjects:
                        m = txmyMdl.namedObjects[value].xbrlMdlObjIndex
                    else:
                        m = value
                    v = ( d, m )
                    t = valueTokens.add( v ) + valueTokensOffset
                    tokens.append( t ) # dimension value for dimension value queries
                    tokens.append( d )      # hasDimension for queries wildcarding dimension
            factTokens.add( (f, tuple(tokens) ) )
            # do we encode the fact's value?  or its hash?  or valueSource like html id or pdf form field id

    return OrderedSet(sorted(cubeTokens)), OrderedSet(sorted(factTokens)), valueTokens


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
    def __init__(self, vocab_size: int, embedDim: int, device: torch.device):
        super().__init__()
        # GPU/CPU: embedding table lives where we send the module
        self.embedding = nn.Embedding(vocab_size, embedDim)
        self.to(device)  # <-- GPU/MPS/CPU placement (hot path decision)

    @property
    def device(self) -> torch.device:
        return self.embedding.weight.device

    def tokenVec(self, token_id: int) -> torch.Tensor:
        """
        Single token ID → (embedDim,) tensor on current device.

        GPU hot path:
          - This is an embedding lookup; on CUDA/MPS it becomes a GPU kernel
            fetching a row from the embedding matrix in GPU memory.
        """
        idx = torch.tensor([token_id], device=self.device)
        return self.embedding(idx)[0]

    def combine(self, ids: Tuple[int] | List[int], weights: List[float] | None = None) -> torch.Tensor:
        """
        Combine multiple token IDs into one vector by weighted average.
        Returns (embedDim,) tensor.

        GPU hot path:
          - Converts ids to a tensor on self.device.
          - Embedding lookup produces a (n, D) tensor on GPU/CPU.
          - Weighted average is a few vector ops (mul, sum) on that device.
        """
        if not ids:
            raise ValueError("No token IDs provided to combine().")

        ids_tensor = torch.tensor(ids, device=self.device)
        vecs = self.embedding(ids_tensor)  # (n, embedDim) on CUDA/MPS/CPU

        if weights is None:
            return vecs.mean(dim=0)

        w = torch.tensor(weights, dtype=vecs.dtype, device=self.device)
        w = w / w.sum()
        return (vecs * w.unsqueeze(1)).sum(dim=0)


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

    All tensors here (taxonomy_vecs, factVecs) are:
      - row-normalized (L2=1) to support cosine similarity as dot product
      - allocated on the same device as the embedder (CUDA/MPS/CPU)
    """
    device: torch.device
    embedDim: int
    cubeVecs: torch.Tensor | None      # (N_tax, D) normalized
    factVecs: torch.Tensor | None          # (N_fact, D) normalized
    cubeObjsList: List[IndexEntry]
    factObjsList: List[IndexEntry]
    valueTokensOffset: int
    valueTokens: OrderedSet[Any]


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


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
    embedDim: int = 64,
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
    # print("Using device:", device)

    # offset tokens to be past largest xbrlMdlObjIndex in txmyMdl
    lenObjs = len(txmyMdl.xbrlObjects)
    valueTokensOffset = 10 ** math.ceil(math.log10( lenObjs ))

    cubeTokens, factTokens, valueTokens = buildXbrlVocab(txmyMdl, valueTokensOffset)
    vocabSize = len(cubeTokens) + len(factTokens) + len(valueTokens)
    # print(f"Vocab size: {vocabSize}")
    txmyMdl.info("arelle:oimModelVectorSearch",
                 _("Using %(device)s.  Vectorized vocabulary size %(vocabSize)s."),
                 device=DEVICE_DESCRIPTION.get(device.type, "unrecognized device"), vocabSize=vocabSize)

    embedder = XBRLEmbedder(vocabSize, embedDim, device=device)

    # --------- cube dimension vectors ----------
    cubeVecsList: List[torch.Tensor] = []
    cubeObjsList: List[int] = []

    # cube dimensions:
    for c, tokens in cubeTokens:
        v = embedder.combine(tokens)
        cubeObjsList.append(c)
        cubeVecsList.append(v)

    cubeVecs = None
    if cubeVecsList:
        cubeVecs = torch.stack(cubeVecsList, dim=0)  # (N_tax, D)
        cubeVecs = l2NormalizeRows(cubeVecs)   # normalization on device

    # --------- fact dimension vectors ----------
    factVecsList: List[torch.Tensor] = []
    factObjsList: List[int] = []

    # from facts
    for f, tokens in range(len(factTokens)):
        v = embedder.combine(tokens)
        factObjsList.append(c)
        factVecsList.append(v)

    factVecs = None
    if factVecsList:
        factVecs = torch.stack(factVecsList, dim=0)     # (N_fact, D)
        factVecs = l2NormalizeRows(factVecs)           # normalization on device

    store = XBRLVectorStore(
        device=device,
        embedDim=embedDim,
        cubeVecs=cubeVecs,
        factVecs=factVecs,
        cubeObjsList=cubeObjsList,
        factObjsList=factObjsList,
        valueTokensOffset=valueTokensOffset,
        valueTokens=valueTokens
    )

    return embedder, store

# --------------------------------------------------------------------
# Query aspect encoder
# --------------------------------------------------------------------

def mapQueryAspects(
    txmyMdl: XbrlTaxonomyModel,
    queryAspects: List[Tuple[int, ...]],
    store: XBRLVectorStore,
) -> List[int]:    # Map tokens to IDs, ignore unknown
    """
    queryAspects: list of model object indices and values, e.g.:
        for concept: (xbrl:concept qname, exp:assets qname)
        for dimension presence: (exp:dim qname, )
        for dimension value: (exp:dim qname, exp:mem qname or
                             (exp:dim qname, typed mem value)
        for period: (xbrl:period qname, period datetime value)
        for unit: (xbrl:unit qname, unit string value) ???
    """

    aspectIds = []
    for queryAspect in queryAspects:
        dimObj = txmyMdl.namedObjects.get( queryAspect[0] )
        if dimObj:
            d = dimObj.xbrlMdlObjIndex
            if len(queryAspect) > 1:
                value = queryAspect[1]
                if isinstance(value, QName) and value in txmyMdl.namedObjects:
                    v = ( d, txmyMdl.namedObjects[value].xbrlMdlObjIndex )
                elif v in store.valueTokens:
                    v = ( d, value )
                if v in store.valueTokens:
                    v = store.valueTokens.index( value ) + store.valueTokenOffset
                else:
                    continue
            else:
                v = d
                aspectIds.append( v )
    return aspectIds

# --------------------------------------------------------------------
# Exact search using cosine similarity
# --------------------------------------------------------------------

def searchXbrl(
    txmyMdl: XbrlTaxonomyModel,
    queryAspects: List[Tuple[int, ...]],
    embedder: XBRLEmbedder,
    store: XBRLVectorStore,
    domain: Literal["cubes", "factspaces", "both"] = "both",
    topK: int = 5,
) -> List[Tuple[float, IndexEntry]]:
    """
    queryAspects: see mapQueryAspects above

    domain: "cubes" | "factspaces" | "both"

    Returns a list of (score, IndexEntry) sorted by descending cosine similarity.

    VERY IMPORTANT:
      - This is an EXACT search.
      - We compute cosine similarity between the query vector and every stored
        vector in the chosen domain using a dense matrix-vector product.
      - Complexity is O(N * D), but on CUDA/MPS that's extremely fast for the
        XBRL scales we care about (thousands to low hundreds of thousands).
      - No approximate index, no risk of "missing" nearest neighbors.
    """

    aspectIds = mapQueryAspects(txmyMdl, queryAspects, store)
    if not aspectIds:
        raise ValueError("None of the queryAspects exist in tok2id. Check token strings.")

    # Encode query aspects into a vector on same device, normalize
    qVec = embedder.combine(aspectIds).to(store.device)
    qVec = F.normalize(qVec.unsqueeze(0), dim=1)  # (1, D), on CUDA/MPS/CPU

    results: List[Tuple[float, IndexEntry]] = []

    # ---- taxonomy search (GPU hot path: matrix-vector dot) ----
    if domain in ("cubes", "both") and store.cubeVecs is not None:
        tv = store.cubeVecs  # (N_tax, D), already normalized, on device
        # EXACT cosine similarity via dot product on device
        sims = (tv @ qVec.T).squeeze(1)  # (N_tax,)
        k = min(topK, sims.shape[0])
        scores, idxs = torch.topk(sims, k)
        for s, idx in zip(scores.tolist(), idxs.tolist()):
            cubeObjIndex = store.cubeObjsList[idx]
            results.append((float(s), txmyMdl.xbrlObjects[cubeObjIndex]))

    # ---- fact search (same GPU hot path) ----
    if domain in ("facts", "both") and store.factVecs is not None:
        fv = store.factVecs  # (N_fact, D), already normalized, on device
        sims = (fv @ qVec.T).squeeze(1)  # (N_fact,)
        k = min(topK, sims.shape[0])
        scores, idxs = torch.topk(sims, k)
        for s, idx in zip(scores.tolist(), idxs.tolist()):
            factObjIndex = store.cubeObjsList[idx]
            results.append((float(s), txmyMdl.xbrlObjects[factObjIndex]))

    # Merge+sort if both
    results.sort(key=lambda x: x[0], reverse=True)
    if domain == "both":
        results = results[:topK]

    return results

# --------------------------------------------------------------------
# Multi-query facility
# --------------------------------------------------------------------

def encodeQueriesMean(
    embedder: XBRLEmbedder,
    queries_token_ids: List[List[int]],
    padId: int,
) -> torch.Tensor:
    """Batch-encode many queries into a (B, D) tensor using masked mean.

    Why this exists:
      - Each query is a variable-length list of aspect token IDs.
      - GPUs like rectangular tensors.
      - We pad to (B, Lmax), do ONE embedding lookup, then masked-average.

    Returns:
      Q: (B, D) L2-normalized query vectors on embedder.device.

    CUDA/MPS usage:
      - The embedding lookup for the entire (B, Lmax) ID matrix is a single
        high-throughput device operation.
    """

    if not queries_token_ids:
        raise ValueError("No queries provided.")

    device = embedder.device
    B = len(queries_token_ids)
    Lmax = max(len(q) for q in queries_token_ids)
    if Lmax == 0:
        raise ValueError("All queries are empty.")

    ids = torch.full((B, Lmax), pad_id, device=device, dtype=torch.long)
    mask = torch.zeros((B, Lmax), device=device, dtype=torch.float32)

    for i, q in enumerate(queries_token_ids):
        if not q:
            continue
        ids[i, : len(q)] = torch.tensor(q, device=device, dtype=torch.long)
        mask[i, : len(q)] = 1.0

    # (B, Lmax, D) embedding lookup in one call (device op)
    E = embedder.embedding(ids)

    # masked mean
    denom = mask.sum(dim=1, keepdim=True).clamp_min(1.0)  # (B,1)
    Q = (E * mask.unsqueeze(-1)).sum(dim=1) / denom       # (B,D)

    return F.normalize(Q, dim=1)


def searchFactsBatchTopk(
    txmyMdl: XbrlTaxonomyModel,
    queriesAspects: List[List[str]],
    embedder: XBRLEmbedder,
    store: XBRLVectorStore,
    domain: Literal["cubes", "factspaces"] = "factspace",
    top_k: int = 20,
    query_batch: int = 128,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Exact batched search over facts: returns top-k per query.

    Inputs:
      queries_aspects: List of queries; each query is a List[str] of aspect tokens.
      top_k: number of matches per query
      query_batch: process queries in chunks to limit score matrix size

    Returns:
      top_idx:    (B, K) indices into store.fact_entries
      top_scores: (B, K) cosine similarity scores

    Exactness:
      - For each query, we compute cosine similarity against ALL facts.
      - This is a dense matmul and torch.topk; no approximation.

    GPU/MPS usage:
      - For each query chunk of size b:
          scores = fact_vecs (N,D) @ Qb^T (D,b) -> (N,b)
        This is a highly optimized device matmul.
      - Then we take topk per query (on device).

    Notes:
      - We chunk queries because the intermediate score matrix is size (N x b).
        For large N, keep query_batch modest (e.g., 64-256).
    """

    if store.factVecs is None or not store.factEntries:
        raise ValueError("No fact vectors available in store.")

    # Convert each query’s aspect tokens -> token IDs; keep per-query lists
    queriesIds: List[List[int]] = []
    for q in queriesAspects:
        ids = mapQueryAspects(txmyMdl, q, store)
        queriesIds.append(ids)

    B = len(queries_ids)
    if B == 0:
        raise ValueError("No queries provided.")

    padId = (store.valueTokensOffset + len(store.valueTokens)) / 1000 + 1000 # round up to make it easy to debug

    # Pre-allocate CPU tensors for final outputs; we’ll fill per chunk.
    # We return torch tensors; caller can map indices back to entries.
    allTopIdx = []
    allTopScores = []

    if domain == "cubes":
        vecs = store.cubeVecs  # (N, D), already normalized, on device
    else:
        vecs = store.factVecs  # (N, D), already normalized, on device
    N = vecs.shape[0]

    for start in range(0, B, query_batch):
        end = min(B, start + query_batch)
        chunkIds = queriesIds[start:end]

        # Encode query chunk to Qb (b, D) on device
        Qb = encodeQueriesMean(embedder, chunkIds, padId=padId)
        # scores: (N, b) exact cosine similarities
        scores = fact_vecs @ Qb.T
        # topk per query: transpose to (b, N) so dim=1 is facts
        scoresBt = scores.T
        k = min(top_k, N)
        topScores, topIdx = torch.topk(scoresBt, k=k, dim=1)

        allTopIdx.append(top_idx.detach().cpu())
        allTopScores.append(top_scores.detach().cpu())

    return torch.cat(allTopIdx, dim=0), torch.cat(allTopScores, dim=0)

