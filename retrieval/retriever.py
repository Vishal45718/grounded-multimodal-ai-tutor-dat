import qdrant_client
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.schema import NodeWithScore

from storage.corpus_store import active_chunks

class TutorRetriever:
    def __init__(self, use_dense=True, use_sparse=True):
        self.use_dense = use_dense
        self.use_sparse = use_sparse
        self.client = qdrant_client.QdrantClient(location=":memory:")
        self.vector_store = QdrantVectorStore(client=self.client, collection_name="tutor_chunks")
        self.index = None
        self.bm25_retriever = None
        self.documents = []
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
                    "modality": c["modality"],
                    "start_sec": c.get("start_sec"),
                    "end_sec": c.get("end_sec"),
                    "image_path": c.get("image_path")
                }
            )
            self.documents.append(doc)
            
        if self.documents:
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

    def retrieve(self, query: str, top_k: int = 5, fusion: bool = False):
        if not self.documents:
            return []
            
        if fusion and self.use_dense and self.use_sparse:
            dense_retriever = self.index.as_retriever(similarity_top_k=top_k)
            retriever = QueryFusionRetriever(
                [dense_retriever, self.bm25_retriever],
                similarity_top_k=top_k,
                num_queries=1,  # simple fusion, no query expansion for now
                mode="reciprocal_rerank",
                use_async=False
            )
            return retriever.retrieve(query)
        elif self.use_dense and self.index:
            return self.index.as_retriever(similarity_top_k=top_k).retrieve(query)
        elif self.use_sparse and self.bm25_retriever:
            return self.bm25_retriever.retrieve(query)
        return []

