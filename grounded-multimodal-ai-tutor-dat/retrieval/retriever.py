from typing import Any, Dict, List, Optional
from storage.corpus_store import active_chunks

try:
    import qdrant_client
    from llama_index.core import VectorStoreIndex, Document
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from llama_index.retrievers.bm25 import BM25Retriever
    from llama_index.core.retrievers import QueryFusionRetriever
    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False


class FallbackNode:
    """Lightweight in-memory document node for offline fallback."""
    def __init__(self, text: str, metadata: Dict[str, Any]):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class TutorRetriever:
    """Hybrid dense-sparse retriever with in-memory fallback when Qdrant is unavailable."""

    def __init__(self, use_dense: bool = True, use_sparse: bool = True):
        self.use_dense = use_dense
        self.use_sparse = use_sparse
        self.index = None
        self.bm25_retriever = None
        self.documents = []
        self._raw_chunks = []
        self._load_data()

    def _load_data(self):
        chunks = active_chunks()
        self._raw_chunks = chunks
        self.documents = []

        for c in chunks:
            text = c.get("text", "")
            if not text:
                text = f"[Visual only: {c.get('modality')}]"

            meta = {
                "chunk_id": c.get("chunk_id"),
                "source_id": c.get("source_id"),
                "modality": c.get("modality"),
                "start_sec": c.get("start_sec"),
                "end_sec": c.get("end_sec"),
                "page_number": c.get("page_number"),
                "image_path": c.get("image_path"),
            }

            if HAS_LLAMA_INDEX:
                doc = Document(text=text, metadata=meta)
            else:
                doc = FallbackNode(text=text, metadata=meta)
            self.documents.append(doc)

        if HAS_LLAMA_INDEX and self.documents:
            if self.use_dense:
                try:
                    self.client = qdrant_client.QdrantClient(location=":memory:")
                    self.vector_store = QdrantVectorStore(client=self.client, collection_name="tutor_chunks")
                    self.index = VectorStoreIndex.from_documents(
                        self.documents,
                        vector_store=self.vector_store,
                    )
                except Exception:
                    self.index = None
            if self.use_sparse:
                try:
                    self.bm25_retriever = BM25Retriever.from_defaults(
                        nodes=self.documents,
                        similarity_top_k=5,
                    )
                except Exception:
                    self.bm25_retriever = None

    def retrieve(self, query: str, top_k: int = 5, fusion: bool = False) -> List[Any]:
        if not self.documents:
            return []

        if HAS_LLAMA_INDEX and self.index:
            if fusion and self.use_dense and self.use_sparse and self.bm25_retriever:
                dense_retriever = self.index.as_retriever(similarity_top_k=top_k)
                retriever = QueryFusionRetriever(
                    [dense_retriever, self.bm25_retriever],
                    similarity_top_k=top_k,
                    num_queries=1,
                    mode="reciprocal_rerank",
                    use_async=False,
                )
                return retriever.retrieve(query)
            elif self.use_dense and self.index:
                return self.index.as_retriever(similarity_top_k=top_k).retrieve(query)
            elif self.use_sparse and self.bm25_retriever:
                return self.bm25_retriever.retrieve(query)

        # In-memory heuristic fallback (keyword overlap scoring)
        q_tokens = set(query.lower().split())
        scored = []
        for doc in self.documents:
            c_text = doc.get_content().lower()
            score = sum(1 for t in q_tokens if t in c_text)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


