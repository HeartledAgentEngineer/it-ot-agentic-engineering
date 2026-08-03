"""Simple JSON-based memory store (drop-in replacement for ChromaDB on ARM)."""

import json
import logging
import uuid
import os
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class SimpleMemoryStore:
    """File-based vector memory store using numpy + JSON.
    
    Drop-in replacement for ChromaDB that works on ARM/Android.
    Persists to a JSON file. Can be migrated to ChromaDB later.
    """

    def __init__(self):
        self.persist_dir = settings.chroma_persist_dir
        self.store_path = os.path.join(self.persist_dir, "memory_store.json")
        self._memories: List[Dict[str, Any]] = []
        self._loaded = False

    def connect(self) -> None:
        """Load or create the memory file."""
        os.makedirs(self.persist_dir, exist_ok=True)
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    self._memories = json.load(f)
                logger.info("Memory store loaded: %d items", len(self._memories))
            except Exception as e:
                logger.warning("Could not load memory store, starting fresh: %s", e)
                self._memories = []
        else:
            self._memories = []
            logger.info("Memory store created (empty)")
        self._loaded = True

    def count(self) -> int:
        """Number of stored items."""
        if not self._loaded:
            self.connect()
        return len(self._memories)

    def add_memory(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        category: str = "fact",
        importance: int = 3,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Add a memory entry."""
        if not self._loaded:
            self.connect()
        memory_id = str(uuid.uuid4())
        entry: Dict[str, Any] = {
            "id": memory_id,
            "content": content,
            "category": category,
            "importance": importance,
            "timestamp": datetime.utcnow().isoformat(),
            "embedding": embedding,
        }
        if conversation_id:
            entry["conversation_id"] = conversation_id
        self._memories.append(entry)
        self._persist()
        logger.debug("Added memory: %s... (id=%s)", content[:50], memory_id)
        return memory_id

    def search_memories(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Cosine-similarity search over stored embeddings."""
        if not self._loaded:
            self.connect()
        if not self._memories:
            return []

        indexed = [m for m in self._memories if m.get("embedding") is not None]
        if not indexed:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        matrix = np.array([m["embedding"] for m in indexed], dtype=np.float32)

        norms = np.linalg.norm(matrix, axis=1)
        q_norm = np.linalg.norm(q)
        if q_norm == 0 or (norms == 0).any():
            return []
        similarities = (matrix @ q) / (norms * q_norm)

        top_indices = np.argsort(similarities)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            m = indexed[idx]
            results.append({
                "id": m["id"],
                "content": m["content"],
                "category": m.get("category", "fact"),
                "importance": m.get("importance", 3),
                "timestamp": m.get("timestamp", ""),
                "distance": float(1.0 - similarities[idx]),
            })
        return results

    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return stored memories (without embeddings)."""
        if not self._loaded:
            self.connect()
        return [
            {k: v for k, v in m.items() if k != "embedding"}
            for m in self._memories[-limit:]
        ]

    def delete_memory(self, memory_id: str) -> bool:
        """Remove a memory by ID."""
        if not self._loaded:
            self.connect()
        before = len(self._memories)
        self._memories = [m for m in self._memories if m["id"] != memory_id]
        if len(self._memories) < before:
            self._persist()
            return True
        return False

    def clear_all(self) -> None:
        """Delete all memories."""
        self._memories = []
        self._persist()
        logger.info("Memory store cleared")

    def _persist(self) -> None:
        """Write memory store to disk."""
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, indent=2, ensure_ascii=False)


# Singleton – same name as before, so imports stay compatible
chroma_client = SimpleMemoryStore()