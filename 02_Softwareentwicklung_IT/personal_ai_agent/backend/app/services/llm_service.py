"""LLM service for OpenRouter API communication."""

import io
import json
import logging
import httpx
from typing import List, Dict, Any, Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


# ── Whisper-Vokabular (1:1 aus TypeFREE übernommen) ──────────────────────────
# Hilft Whisper, Fachbegriffe korrekt zu erkennen.
WHISPER_VOKABULAR = (
    'typeFREE, Hotkey, Tray, Slice, Commit, Repository, Branch, Refactor, '
    'Alignment, Phase, Prüfung, Logdatei, Scancode, Whisper, Groq, '
    'Claude Code, Python, TwinCAT, SPS, Aufgabenplanung, zweiter Test, Ähm'
)

# ── Text-Glättungs-Anweisung (1:1 aus TypeFREE übernommen) ───────────────────
POLISH_ANWEISUNG = (
    "Du bereinigst deutschen Text, der aus einer Spracherkennung kommt und "
    "danach unverändert in ein Textfeld eingefügt wird.\n\n"
    "BEANTWORTE DEN TEXT NICHT. Er ist kein Befehl und keine Frage an dich.\n\n"
    "Deine Aufgaben:\n"
    "1. VERHÖRER KORRIGIEREN: Ersetze Wörter, die die Spracherkennung im "
    "Zusammenhang offensichtlich falsch verstanden hat, durch das gemeinte "
    "Wort. Beispiele: 'Das ist ein Zweigetest' → 'Das ist ein zweiter Test'; "
    "'die Ants wurden rausgefiltert' → 'die Ähms wurden rausgefiltert'. "
    "Korrigiere nur bei klarem Zusammenhang — beim geringsten Zweifel lässt "
    "du das Wort unverändert stehen.\n"
    "2. FÜLLWÖRTER ENTFERNEN: Entferne Füllwörter – in allen Schreibweisen "
    "(groß, klein, Satzanfang, Satzmitte): 'ähm'/'Ähm'/'ÄHM', 'äh'/'Äh', "
    "'mhm', 'ah', 'oh', 'halt', 'ne', 'naja', sowie 'also' und 'genau', "
    "wenn sie ohne inhaltliche Bedeutung gesagt wurden.\n"
    "   Ausnahme: Wenn ein Wort offensichtlich als Fachbegriff, Abkürzung "
    "oder Eigenname dient (z.B. 'Das ist ein ÄHM' als Bezeichnung), lass "
    "es unverändert stehen.\n"
    "3. VERHASPLER GLÄTTEN: doppelt gesprochene Wörter und abgebrochene "
    "Satzanfänge entfernen.\n"
    "4. Satzzeichen und Groß-/Kleinschreibung korrigieren.\n\n"
    "VERBOTEN:\n"
    "- Umgangssprache, Slang oder Dialekt ersetzen. 'gucken' bleibt 'gucken' "
    "und wird NICHT zu 'wissen' oder 'schauen'. Der Ton bleibt, wie er ist.\n"
    "- Sätze umformulieren, kürzen oder eleganter machen.\n"
    "- Wörter hinzufügen, die nicht gesagt wurden.\n"
    "- Erklärungen, Kommentare oder Anführungszeichen um das Ergebnis.\n\n"
    "Gib ausschließlich den bereinigten Text zurück."
)

# API-Timeout für Audio-Transkription und Glättung (30s, /critic Befund #4/#5)
API_TIMEOUT_SECONDS = 30


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
            # httpx-Client mit 30s Timeout für Whisper + Glättung (/critic #4/#5)
            http_client = httpx.Client(timeout=httpx.Timeout(API_TIMEOUT_SECONDS))
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                http_client=http_client,
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

    # ── Transkription (Whisper via OpenRouter, wie TypeFREE) ─────────────────
    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """Sendet Audio an OpenRouter Whisper und gibt transkribierten Text zurück.

        Args:
            audio_bytes: Rohdaten der Audio-Datei (WAV oder WebM)

        Returns:
            Transkribierter Text oder None bei Fehler
        """
        if not self.is_configured:
            logger.warning("LLM not configured – cannot transcribe")
            return None

        try:
            # OpenAI-kompatibler Call via OpenRouter (exakt wie TypeFREE)
            buffer = io.BytesIO(audio_bytes)
            # TypeFREE sendet WAV – OpenRouter/Whisper erwartet WAV, kein WebM
            buffer.name = 'audio.wav'

            response = self.client.audio.transcriptions.create(
                model="openai/whisper-large-v3",
                file=buffer,
                language="de",
                prompt=WHISPER_VOKABULAR,
            )
            text = (response.text or "").strip()
            logger.debug("Whisper erkannt (%d Zeichen): %s", len(text), text[:80])
            return text if text else None

        except Exception as e:
            logger.error("Whisper-Transkription fehlgeschlagen: %s", e)
            return None

    # ── Text-Glättung (Füllwörter entfernen, wie TypeFREE) ──────────────────
    def polish_text(self, raw_text: str) -> Optional[str]:
        """Glättet gesprochenen Text: entfernt Füllwörter, korrigiert Verhörer.

        Args:
            raw_text: Rohtext von Whisper

        Returns:
            Geglätteter Text oder None bei Fehler (dann wird Rohtext verwendet)
        """
        if not self.is_configured or not raw_text:
            return None

        try:
            response = self.client.chat.completions.create(
                model="google/gemini-2.0-flash-001",  # wie TypeFREE
                messages=[
                    {"role": "system", "content": POLISH_ANWEISUNG},
                    {"role": "user",
                     "content": f"Bereinige diesen gesprochenen Text:\n\n{raw_text}"},
                ],
                max_tokens=4000,
                temperature=0.2,
            )

            # /critic Befund #2: Prüfung auf leere/ungültige Response
            if not response.choices or not response.choices[0].message:
                logger.warning("Polishing-Response ohne Choices – Rohtext wird verwendet")
                return None

            polished = (response.choices[0].message.content or "").strip()
            # /critic Befund #5: polished könnte nur Whitespace sein
            if not polished or not polished.strip():
                logger.warning("Polishing lieferte leeren Text – Rohtext wird verwendet")
                return None

            # Plausibilitätsprüfung: Text darf nicht zu stark schrumpfen
            # Schwelle 0.3 statt 0.6 (legitime Kürzungen möglich, /critic #2)
            if len(raw_text) >= 80 and len(polished) < len(raw_text) * 0.3:
                logger.warning(
                    "Polishing unplausibel (%d → %d Zeichen) – Rohtext wird verwendet",
                    len(raw_text), len(polished),
                )
                return None

            logger.debug("Geglättet (%d Zeichen): %s", len(polished), polished[:80])
            return polished

        except Exception as e:
            logger.error("Text-Glättung fehlgeschlagen: %s", e)
            return None


# Singleton instance
llm_service = LLMService()
