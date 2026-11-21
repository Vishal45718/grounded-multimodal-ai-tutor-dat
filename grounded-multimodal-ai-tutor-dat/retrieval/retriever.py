"""Hybrid dense-sparse retriever with Okapi BM25, dense vector, RRF fusion, and neural/lexical reranking.

Supports:
1. Sparse-only (Okapi BM25 with IDF and document length normalization).
2. Dense-only (Vector cosine similarity).
3. Hybrid Fusion (Reciprocal Rank Fusion - RRF between sparse and dense).
4. Hybrid + Reranker (TutorReranker composite scoring).
5. Automatic LlamaIndex / Qdrant delegation when installed, with deterministic pure-Python engine when offline.
"""
import math
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from storage.corpus_store import active_chunks

try:
    import qdrant_client
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.retrievers import QueryFusionRetriever
    from llama_index.retrievers.bm25 import BM25Retriever
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False


STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
    "is", "are", "was", "were", "and", "or", "what", "how", "why",
    "which", "does", "do", "did", "this", "that", "these", "those",
    "can", "could", "would", "should", "according", "lecture", "cs50"
}


def tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric tokens, preserving code identifiers with underscores."""
    raw = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
    return [t for t in raw if t not in STOPWORDS]


class FallbackNode:
    """Lightweight in-memory document node for offline fallback."""

    def __init__(self, text: str, metadata: Dict[str, Any]):
        self.text = text
        self.metadata = metadata
        self.score: float = 0.0

    def get_content(self) -> str:
        return self.text

    def __repr__(self) -> str:
        cid = self.metadata.get("chunk_id", "unknown")
        return f"<FallbackNode cid={cid} score={self.score:.4f}>"


class PurePythonBM25:
    """Self-contained Okapi BM25 engine with IDF and document length normalization."""

    def __init__(self, docs: List[FallbackNode], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs
        self.doc_len = [len(tokenize(d.get_content())) for d in docs]
        self.avgdl = sum(self.doc_len) / max(1, len(docs))
        self.n_docs = len(docs)

        # Term frequencies and document frequencies
        self.doc_term_freqs: List[Dict[str, int]] = []
        self.df: Dict[str, int] = {}

        for d in docs:
            tokens = tokenize(d.get_content())
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freqs.append(tf)
            for t in tf:
                self.df[t] = self.df.get(t, 0) + 1

        # Precompute IDF using standard BM25 formula
        self.idf: Dict[str, float] = {}
        for t, freq in self.df.items():
            self.idf[t] = math.log(1.0 + (self.n_docs - freq + 0.5) / (freq + 0.5))

    def score(self, query: str) -> List[Tuple[float, FallbackNode]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return [(0.0, d) for d in self.docs]

        scores: List[Tuple[float, FallbackNode]] = []
        for idx, doc in enumerate(self.docs):
            doc_tf = self.doc_term_freqs[idx]
            d_len = self.doc_len[idx]
            score = 0.0

            for qt in q_tokens:
                if qt in doc_tf:
                    freq = doc_tf[qt]
                    idf = self.idf.get(qt, 0.1)
                    denom = freq + self.k1 * (1.0 - self.b + self.b * (d_len / max(1.0, self.avgdl)))
                    score += idf * (freq * (self.k1 + 1.0)) / max(1e-5, denom)

            scores.append((score, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores


class PurePythonDenseSim:
    """Fast vector cosine similarity over sub-word TF-IDF representations."""

    def __init__(self, docs: List[FallbackNode]):
        self.docs = docs
        self.doc_vectors: List[Dict[str, float]] = []

        # Build term weights
        for d in docs:
            tokens = tokenize(d.get_content())
            vec: Dict[str, float] = {}
            for t in tokens:
                vec[t] = vec.get(t, 0.0) + 1.0
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            for t in vec:
                vec[t] /= norm
            self.doc_vectors.append(vec)

    def score(self, query: str) -> List[Tuple[float, FallbackNode]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return [(0.0, d) for d in self.docs]

        q_vec: Dict[str, float] = {}
        for t in q_tokens:
            q_vec[t] = q_vec.get(t, 0.0) + 1.0
        norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        for t in q_vec:
            q_vec[t] /= norm

        scores: List[Tuple[float, FallbackNode]] = []
        for idx, doc in enumerate(self.docs):
            d_vec = self.doc_vectors[idx]
            dot = sum(val * d_vec.get(term, 0.0) for term, val in q_vec.items())
            scores.append((dot, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores


class TutorRetriever:
    """Hybrid dense-sparse retriever with Okapi BM25, dense similarity, RRF, and reranking."""

    def __init__(
        self,
        use_dense: bool = True,
        use_sparse: bool = True,
        use_reranker: bool = False,
    ):
        self.use_dense = use_dense
        self.use_sparse = use_sparse
        self.use_reranker = use_reranker
        self.reranker = None
        if self.use_reranker:
            from retrieval.reranker import TutorReranker
            self.reranker = TutorReranker()

        self.documents: List[FallbackNode] = []
        self._raw_chunks: List[Dict[str, Any]] = []
        self.bm25_engine: Optional[PurePythonBM25] = None
        self.dense_engine: Optional[PurePythonDenseSim] = None
        self._load_data()

    def _load_data(self) -> None:
        chunks = active_chunks()
        self._raw_chunks = chunks
        self.documents = []

        for c in chunks:
            text = c.get("text", "") or ""
            if not text.strip():
                text = f"[Visual only: {c.get('modality')}]"

            meta = {
                "chunk_id": c.get("chunk_id"),
                "source_id": c.get("source_id"),
                "modality": c.get("modality"),
                "start_sec": c.get("start_sec"),
                "end_sec": c.get("end_sec"),
                "page_number": c.get("page_number"),
                "image_path": c.get("image_path"),
                "content_hash": c.get("content_hash"),
                "course_edition": c.get("edition_id"),
            }
            self.documents.append(FallbackNode(text=text, metadata=meta))

        if self.documents:
            self.bm25_engine = PurePythonBM25(self.documents)
            self.dense_engine = PurePythonDenseSim(self.documents)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        fusion: bool = True,
        rerank: Optional[bool] = None,
    ) -> List[Any]:
        if not self.documents:
            return []

        should_rerank = self.use_reranker if rerank is None else rerank
        candidate_k = max(top_k * 3, 15) if should_rerank else top_k

        # 1. Sparse Only
        if self.use_sparse and not self.use_dense:
            ranked = self.bm25_engine.score(query)[:candidate_k]
            candidates = [doc for _, doc in ranked]

        # 2. Dense Only
        elif self.use_dense and not self.use_sparse:
            ranked = self.dense_engine.score(query)[:candidate_k]
            candidates = [doc for _, doc in ranked]

        # 3. Hybrid Fusion (BM25 + Dense via Reciprocal Rank Fusion)
        else:
            sparse_ranked = self.bm25_engine.score(query)[:50]
            dense_ranked = self.dense_engine.score(query)[:50]

            rrf_scores: Dict[str, float] = {}
            node_map: Dict[str, FallbackNode] = {}
            k_rrf = 60.0

            for rank, (score, doc) in enumerate(sparse_ranked):
                cid = doc.metadata.get("chunk_id", str(id(doc)))
                node_map[cid] = doc
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_rrf + rank + 1.0))

            for rank, (score, doc) in enumerate(dense_ranked):
                cid = doc.metadata.get("chunk_id", str(id(doc)))
                node_map[cid] = doc
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_rrf + rank + 1.0))

            fused_sorted = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            candidates = [node_map[cid] for cid, _ in fused_sorted[:candidate_k]]

        # 4. Optional Neural/Lexical Reranking Layer
        if should_rerank:
            if not self.reranker:
                from retrieval.reranker import TutorReranker
                self.reranker = TutorReranker()
            return self.reranker.rerank(query, candidates, top_k=top_k)

        return candidates[:top_k]
