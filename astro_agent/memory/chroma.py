import os
import uuid
from pathlib import Path

MEMORY_DIR = Path.home() / ".astro" / "memory"

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    
    class LongTermMemory:
        def __init__(self):
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(MEMORY_DIR))
            self.collection = self.client.get_or_create_collection(
                name="astro_conversations",
                metadata={"hnsw:space": "cosine"}
            )
            self.model = None

        def _get_model(self):
            if self.model is None:
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            return self.model

        def memorize(self, session_id: str, human_text: str, ai_text: str):
            def _async_memorize():
                try:
                    doc = f"User: {human_text}\nAstro: {ai_text}"
                    embedding = self._get_model().encode([doc]).tolist()
                    doc_id = f"{session_id}_{uuid.uuid4().hex[:6]}"

                    self.collection.add(
                        ids=[doc_id],
                        embeddings=embedding,
                        documents=[doc],
                        metadatas=[{"session": session_id}]
                    )
                except Exception as e:
                    pass
            # Run in background to prevent slow embeddings from blocking agent
            import threading
            threading.Thread(target=_async_memorize, daemon=True).start()

        def recall(self, query: str, k=3) -> str:
            try:
                count = self.collection.count()
                if count == 0:
                    return ""

                query_emb = self._get_model().encode([query]).tolist()
                results = self.collection.query(
                    query_embeddings=query_emb,
                    n_results=min(k, count)
                )
                if not results.get('documents') or not results['documents'][0]:
                    return ""

                context = "Xotiradan parchalar:\n"
                for doc in results['documents'][0]:
                    context += f"---\n{doc}\n"
                return context
            except Exception as e:
                return ""

    memory_client = LongTermMemory()

except ImportError:
    class DummyMemory:
        def memorize(self, *args, **kwargs): pass
        def recall(self, *args, **kwargs): return ""
    memory_client = DummyMemory()
