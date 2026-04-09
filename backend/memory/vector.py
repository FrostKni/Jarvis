import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
from backend.config import get_settings

settings = get_settings()


class VectorMemory:
    def __init__(self):
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

        if settings.openai_api_key:
            ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.openai_api_key,
                model_name="text-embedding-3-small",
            )
        else:
            ef = embedding_functions.DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name="jarvis_memory",
            embedding_function=ef,
        )

    def store(self, text: str, metadata: dict | None = None):
        doc_id = f"mem_{datetime.utcnow().timestamp()}"
        self._collection.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[
                {**(metadata or {}), "timestamp": datetime.utcnow().isoformat()}
            ],
        )

    def search(self, query: str, n: int = 5) -> list[str]:
        results = self._collection.query(query_texts=[query], n_results=n)
        return results["documents"][0] if results["documents"] else []

    def consolidate_session(self, session_summary: str):
        self.store(session_summary, {"type": "session_summary"})
