import chromadb
from chromadb.utils import embedding_functions
from app.core.config import settings

class VectorRetriever:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="askly_knowledge",
            embedding_function=self.embedding_fn
        )

    def search(self, query: str, top_k: int = 2) -> list[dict]:
        results = self.collection.query(query_texts=[query], n_results=top_k)
        retrieved_docs = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            for doc, meta in zip(docs, metas):
                retrieved_docs.append({"content": doc, "source": meta.get("source", "unknown")})
        return retrieved_docs

retriever = VectorRetriever()