"""Memory service combining embeddings, vector storage, and LLM extraction."""

import logging
from typing import List, Dict, Any, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db.chroma_client import chroma_client
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class MemoryService:
    """Orchestrates memory operations: embedding, storage, retrieval, extraction."""

    def __init__(self):
        self._embedder: Optional[SentenceTransformer] = None
        self._embedder_loaded = False

    def _load_embedder(self) -> None:
        """Lazy-load the embedding model."""
        if not self._embedder_loaded:
            try:
                logger.info(
                    "Loading embedding model: %s...", settings.embedding_model
                )
                self._embedder = SentenceTransformer(settings.embedding_model)
                self._embedder_loaded = True
                logger.info("Embedding model loaded successfully.")
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                raise

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._load_embedder()
        return self._embedder  # type: ignore

    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        embedding = self.embedder.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def store_memory(
        self,
        content: str,
        category: str = "fact",
        importance: int = 3,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Generate embedding and store a memory."""
        embedding = self._get_embedding(content)
        memory_id = chroma_client.add_memory(
            content=content,
            embedding=embedding,
            category=category,
            importance=importance,
            conversation_id=conversation_id,
        )
        logger.info("Stored memory: %s (category=%s)", content[:80], category)
        return memory_id

    def retrieve_relevant_memories(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to a query."""
        if chroma_client.count() == 0:
            return []

        query_embedding = self._get_embedding(query)
        memories = chroma_client.search_memories(
            query_embedding=query_embedding, top_k=top_k
        )
        logger.debug("Retrieved %d relevant memories", len(memories))
        return memories

    def extract_and_store_memories(
        self, user_message: str, llm_reply: str, conversation_id: Optional[str] = None
    ) -> List[str]:
        """Use LLM to extract facts from conversation and store them."""
        facts = llm_service.extract_memories(user_message, llm_reply)
        stored_ids = []

        for fact in facts:
            if len(fact) > 10:  # Ignore very short/empty facts
                memory_id = self.store_memory(
                    content=fact,
                    category="fact",
                    importance=3,
                    conversation_id=conversation_id,
                )
                stored_ids.append(memory_id)

        if stored_ids:
            logger.info("Extracted and stored %d new memories", len(stored_ids))
        return stored_ids

    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all stored memories."""
        return chroma_client.get_all_memories(limit=limit)

    def get_memory_count(self) -> int:
        """Get the number of stored memories."""
        return chroma_client.count()

    def clear_memories(self) -> None:
        """Clear all memories (for testing)."""
        chroma_client.clear_all()
        logger.info("All memories cleared.")


# Singleton instance
memory_service = MemoryService()