import os
import re
from typing import Any, Dict, List, Optional

from storage.corpus_store import active_chunks

try:
    import qdrant_client
    from llama_index.core import VectorStoreIndex, Document, Settings
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from llama_index.retrievers.bm25 import BM25Retriever
    from llama_index.core.retrievers import QueryFusionRetriever
    from llama_index.core.schema import NodeWithScore
    _HAS_LLAMA_INDEX = True
except ImportError:
    _HAS_LLAMA_INDEX = False

    class Document:
        """Lightweight document representation when LlamaIndex is not installed."""
        def __init__(self, text: str = "", metadata: Optional[Dict[str, Any]] = None):
            self.text = text
            self.metadata = metadata or {}

        def get_content(self) -> str:
            return self.text


class TutorRetriever:
    def __init__(self, use_dense: bool = True, use_sparse: bool = True):
        self.use_dense = use_dense
        self.use_sparse = use_sparse
        if _HAS_LLAMA_INDEX:
            self.client = qdrant_client.QdrantClient(location=":memory:")
            self.vector_store = QdrantVectorStore(client=self.client, collection_name="tutor_chunks")
        else:
            self.client = None
            self.vector_store = None
        self.index = None
        self.bm25_retriever = None
        self.documents: List[Document] = []
        self._load_data()

    def _load_data(self):
        chunks = active_chunks()
        self.documents = []
        for c in chunks:
            text = c.get("text", "")
            if not text:
                text = f"[Visual only: {c.get('modality')}]"
            doc = Document(
                text=text,
                metadata={
                    "chunk_id": c["chunk_id"],
                    "source_id": c["source_id"],
                    "asset_id": c.get("asset_id"),
                    "content_hash": c.get("content_hash"),
                    "course_edition": c.get("course_edition") or c.get("edition_id"),
                    "edition_id": c.get("edition_id"),
                    "modality": c["modality"],
                    "start_sec": c.get("start_sec"),
                    "end_sec": c.get("end_sec"),
                    "image_path": c.get("image_path"),
                    "page_number": c.get("page_number"),
                    "source_url": c.get("source_url"),
                    "status": c.get("status", "success"),
                }
            )
            self.documents.append(doc)
            
        if self.documents and _HAS_LLAMA_INDEX:
            if self.use_dense:
                self.index = VectorStoreIndex.from_documents(
                    self.documents,
                    vector_store=self.vector_store
                )
            if self.use_sparse:
                self.bm25_retriever = BM25Retriever.from_defaults(
                    nodes=self.documents,
                    similarity_top_k=5
                )

    def retrieve(self, query: str, top_k: int = 5, fusion: bool = False) -> List[Any]:
        if not self.documents:
            return []
            
        if _HAS_LLAMA_INDEX:
            if fusion and self.use_dense and self.use_sparse:
                dense_retriever = self.index.as_retriever(similarity_top_k=top_k)
                retriever = QueryFusionRetriever(
                    [dense_retriever, self.bm25_retriever],
                    similarity_top_k=top_k,
                    num_queries=1,
                    mode="reciprocal_rerank",
                    use_async=False
                )
                return retriever.retrieve(query)
            elif self.use_dense and self.index:
                return self.index.as_retriever(similarity_top_k=top_k).retrieve(query)
            elif self.use_sparse and self.bm25_retriever:
                return self.bm25_retriever.retrieve(query)

        # Fallback offline keyword-matching when LlamaIndex is not installed
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        scored_docs = []
        for doc in self.documents:
            doc_text = doc.get_content().lower()
            score = sum(doc_text.count(t) for t in terms)
            scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]
