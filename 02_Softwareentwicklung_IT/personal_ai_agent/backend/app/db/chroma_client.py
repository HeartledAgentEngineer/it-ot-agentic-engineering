"""ChromaDB client for vector storage and retrieval."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)


class ChromaClient:
    """Manages the ChromaDB vector database for memory storage."""

    def __init__(self):
        self.persist_dir = settings.chroma_persist_dir
        self.collection_name = settings.chroma_collection_name
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None

    def connect(self) -> None:
        """Initialize ChromaDB client and get/create collection."""
        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB connected. Collection '%s' has %d items.",
                self.collection_name,
                self._collection.count(),
            )
        except Exception as e:
            logger.error("Failed to connect to ChromaDB: %s", e)
            raise

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self.connect()
        return self._collection  # type: ignore

    def add_memory(
        self,
        content: str,
        embedding: List[float],
        category: str = "fact",
        importance: int = 3,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Add a new memory to the vector store."""
        memory_id = str(uuid.uuid4())
        metadata: Dict[str, Any] = {
            "content": content,
            "category": category,
            "importance": importance,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if conversation_id:
            metadata["conversation_id"] = conversation_id

        self.collection.add(
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[memory_id],
        )
        logger.debug("Added memory: %s... (id=%s)", content[:50], memory_id)
        return memory_id

    def search_memories(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for the most relevant memories."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
        )

        memories = []
        if results["metadatas"] and results["metadatas"][0]:
            for i, metadata in enumerate(results["metadatas"][0]):
                memories.append(
                    {
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "content": metadata.get("content", ""),
                        "category": metadata.get("category", "fact"),
                        "importance": metadata.get("importance", 3),
                        "timestamp": metadata.get("timestamp", ""),
                        "distance": results["distances"][0][i]
                        if results.get("distances")
                        else None,
                    }
                )
        return memories

    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all stored memories."""
        if self.collection.count() == 0:
            return []

        results = self.collection.get(limit=limit)

        memories = []
        if results["metadatas"]:
            for i, metadata in enumerate(results["metadatas"]):
                memories.append(
                    {
                        "id": results["ids"][i] if results["ids"] else None,
                        "content": metadata.get("content", ""),
                        "category": metadata.get("category", "fact"),
                        "importance": metadata.get("importance", 3),
                        "timestamp": metadata.get("timestamp", ""),
                    }
                )
        return memories

    def count(self) -> int:
        """Get the number of stored memories."""
        return self.collection.count()

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error("Failed to delete memory %s: %s", memory_id, e)
            return False

    def clear_all(self) -> None:
        """Delete all memories (for testing)."""
        if self.collection.count() > 0:
            self.collection.delete(ids=self.collection.get()["ids"])


# Singleton instance
chroma_client = ChromaClient()