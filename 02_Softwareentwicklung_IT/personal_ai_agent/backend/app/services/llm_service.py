"""LLM service for OpenRouter API communication."""

import json
import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Handles communication with OpenRouter API for LLM calls."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = settings.openrouter_base_url

        if not self.api_key:
            logger.warning("No OpenRouter API key configured!")
            self.client = None
        else:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/HeartledAgentEngineer/personal-ai-agent",
                    "X-Title": "Personal AI Agent",
                },
            )

    @property
    def is_configured(self) -> bool:
        """Check if the LLM service is properly configured."""
        return self.client is not None and bool(self.api_key)

    def load_system_prompt(self) -> str:
        """Load the system prompt from file."""
        try:
            with open(settings.system_prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(
                "System prompt file not found: %s. Using default.",
                settings.system_prompt_file,
            )
            return "Du bist ein hilfreicher KI-Assistent."

    def _build_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """Build a memory context string from retrieved memories."""
        if not memories:
            return ""

        context_parts = ["\n## GEMERKTE INFORMATIONEN AUS FRÜHEREN GESPRÄCHEN:"]
        for mem in memories:
            context_parts.append(f"- {mem['content']} (Kategorie: {mem['category']})")

        return "\n".join(context_parts)

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Send a chat message to the LLM and get a response.

        Args:
            user_message: The user's current message
            conversation_history: Previous messages in this conversation
            memories: Relevant memories retrieved from vector DB

        Returns:
            The LLM's response text
        """
        if not self.is_configured:
            return (
                "⚠️ **OpenRouter nicht konfiguriert.**\n\n"
                "Bitte setze den `OPENROUTER_API_KEY` in der `.env`-Datei.\n"
                "Du bekommst einen Key unter: https://openrouter.ai/keys"
            )

        system_prompt = self.load_system_prompt()

        # Add memory context to system prompt if memories exist
        memory_context = self._build_memory_context(memories or [])
        if memory_context:
            system_prompt += memory_context

        # Build message list
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history (last 10 messages for context)
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append(msg)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=0.7,
                max_tokens=2048,
                extra_body={"provider": {"allow_fallbacks": True}},
            )

            reply = response.choices[0].message.content or ""
            logger.debug(
                "LLM response received (%d tokens, model=%s)",
                response.usage.total_tokens if response.usage else 0,
                response.model,
            )
            return reply

        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            return f"⚠️ Fehler bei der Anfrage an OpenRouter:\n```\n{str(e)}\n```"

    def extract_memories(self, user_message: str, llm_reply: str) -> List[str]:
        """Ask the LLM to extract facts that should be memorized.

        Args:
            user_message: The user's message
            llm_reply: The LLM's response

        Returns:
            List of factual statements to store
        """
        if not self.is_configured:
            return []

        extraction_prompt = (
            "Extrahiere aus folgendem Dialog maximal 3 wichtige Fakten, "
            "die über den Nutzer gemerkt werden sollten (z.B. Name, Vorlieben, "
            "Projekte, persönliche Details). "
            "Antworte NUR mit einer JSON-Liste von Strings, z.B.: "
            '["Fakt 1", "Fakt 2"]. Wenn nichts zu merken ist, antworte mit [].\n\n'
            f"Nutzer: {user_message}\n"
            f"Assistent: {llm_reply}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": extraction_prompt}],  # type: ignore
                temperature=0.1,
                max_tokens=500,
                extra_body={"provider": {"allow_fallbacks": True}},
            )

            raw = response.choices[0].message.content or "[]"
            # Try to parse JSON, clean up if needed
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

            facts = json.loads(raw)
            if isinstance(facts, list):
                return [str(f) for f in facts if f]
            return []

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to extract memories: %s", e)
            return []


# Singleton instance
llm_service = LLMService()