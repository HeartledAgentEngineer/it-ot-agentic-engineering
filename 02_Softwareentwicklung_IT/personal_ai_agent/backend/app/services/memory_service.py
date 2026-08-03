"""Memory service – stores conversation facts (embeddings optional)."""

import logging
import warnings
from typing import List, Dict, Any, Optional

from app.config import settings
from app.db.chroma_client import chroma_client
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Try to load sentence-transformers; if torch is missing, disable embeddings
_embeddings_available = False
_embedder = None

try:
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer(settings.embedding_model)
    _embeddings_available = True
    logger.info("Embedding model '%s' loaded successfully.", settings.embedding_model)
except Exception as e:
    logger.warning(
        "Embedding model NOT available (%s). "
        "Vector memory search will be disabled until sentence-transformers + torch are installed.",
        e,
    )


class MemoryService:
    """Orchestrates memory operations: storage, retrieval, extraction."""

    # ── store ──────────────────────────────────────────────────────

    def store_memory(
        self,
        content: str,
        category: str = "fact",
        importance: int = 3,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Store a memory (with embedding if available)."""
        embedding = None
        if _embeddings_available and _embedder is not None:
            try:
                vec = _embedder.encode(content, normalize_embeddings=True)
                embedding = vec.tolist()
            except Exception as e:
                logger.debug("Embedding failed, storing without vector: %s", e)

        memory_id = chroma_client.add_memory(
            content=content,
            embedding=embedding,
            category=category,
            importance=importance,
            conversation_id=conversation_id,
        )
        logger.info("Stored memory: %s (category=%s)", content[:80], category)
        return memory_id

    # ── retrieve ───────────────────────────────────────────────────

    def retrieve_relevant_memories(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to a query (vector search if possible)."""
        if chroma_client.count() == 0:
            return []

        if _embeddings_available and _embedder is not None:
            try:
                query_vec = _embedder.encode(query, normalize_embeddings=True)
                return chroma_client.search_memories(
                    query_embedding=query_vec.tolist(), top_k=top_k
                )
            except Exception as e:
                logger.debug("Vector search failed, returning empty: %s", e)
                return []
        else:
            # No embeddings – return last N memories as simple context
            return chroma_client.get_all_memories(limit=top_k)

    # ── extract & store (LLM-based) ───────────────────────────────

    def extract_and_store_memories(
        self, user_message: str, llm_reply: str, conversation_id: Optional[str] = None
    ) -> List[str]:
        """Use LLM to extract facts from conversation and store them."""
        facts = llm_service.extract_memories(user_message, llm_reply)
        stored_ids = []

        for fact in facts:
            if len(fact) > 10:
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

    # ── query ──────────────────────────────────────────────────────

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