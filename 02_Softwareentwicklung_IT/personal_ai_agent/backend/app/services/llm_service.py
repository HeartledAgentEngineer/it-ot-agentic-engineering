"""LLM service for OpenRouter API communication."""

import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Iterator, Optional, Tuple

import httpx

from openai import OpenAI, APIStatusError

from app.config import settings
from app.modelle_de import MODEL_BESCHREIBUNGEN_DE
from app.modelle_use import (
    MODELL_USECASES_DE,
    MODELL_STAERKEN_DE,
    MODELL_BENCHMARK_REF,
)

logger = logging.getLogger(__name__)


# ── Whisper-Vokabular (1:1 aus TypeFREE übernommen) ──────────────────────────
# Hilft Whisper, Fachbegriffe korrekt zu erkennen.
WHISPER_VOKABULAR = (
    'typeFREE, Hotkey, Tray, Slice, Commit, Repository, Branch, Refactor, '
    'Alignment, Phase, Prüfung, Logdatei, Scancode, Whisper, Groq, '
    'Claude Code, Python, TwinCAT, SPS, Aufgabenplanung, zweiter Test,'
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

# Websuche: Wie viele Treffer OpenRouter beisteuern soll.
WEB_MAX_RESULTS = 5

# Datenschutz-Profile der Anbieter. Kein Teil der dokumentierten API, sondern
# der Endpunkt, den OpenRouters eigene Oberfläche benutzt – er kann sich also
# ohne Ankündigung ändern. Fällt er aus, läuft die Modellliste ohne
# Datenschutz-Detail weiter; sie darf nicht daran hängen.
ALL_PROVIDERS_URL = "https://openrouter.ai/api/frontend/v1/all-providers"

# Wie viele Anbieterabfragen gleichzeitig laufen. Mit 16 sind rund 110 Modelle
# in etwa einer Sekunde durch; höher zu gehen bringt nichts und riskiert nur
# eine Drosselung.
INDEX_PARALLEL = 16

# Hinweistext bei fehlendem Schlüssel – von chat() und chat_stream() geteilt.
NICHT_KONFIGURIERT = (
    "⚠️ **OpenRouter nicht konfiguriert.**\n\n"
    "Bitte setze den `OPENROUTER_API_KEY` in der `.env`-Datei.\n"
    "Du bekommst einen Key unter: https://openrouter.ai/keys"
)


def _staerke_ableiten(
    gepflegt: Optional[str],
    hat_bilder: bool,
    hat_reasoning: bool,
    rohpreis_prompt: Any,
) -> str:
    """Leitet ein Stärke-Profil für ein Modell ab.

    Reihenfolge:
      1. Gepflegter Eintrag (MODELL_STAERKEN_DE) gewinnt immer.
      2. Bildfähig  → "bilder"
      3. Reasoning  → "reasoning"
      4. Sehr günstig (Eingabepreis <= 0,15 $/Mio) → "preis_leistung"
      5. sonst      → "alltag"

    So bekommt JEDES Modell eine einsortierte Stärke, auch wenn es nicht
    manuell gepflegt ist.
    """
    if gepflegt:
        return gepflegt
    if hat_bilder:
        return "bilder"
    if hat_reasoning:
        return "reasoning"
    preis = LLMService._preis_pro_mio(rohpreis_prompt)
    if preis is not None and preis <= 0.15:
        return "preis_leistung"
    return "alltag"


class LLMService:
    """Handles communication with OpenRouter API for LLM calls."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = settings.openrouter_base_url

        # Zwischenspeicher für den Modellkatalog. Ein Abruf sind drei
        # HTTP-Anfragen, und die Liste ändert sich höchstens täglich.
        self._modelle_cache: Dict[str, Any] = {"zeit": 0.0, "daten": None}
        self._anbieter_cache: Dict[str, Any] = {"zeit": 0.0, "daten": None}
        self._index_cache: Dict[str, Any] = {"zeit": 0.0, "daten": None}

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
        """Laedt den System-Prompt: oeffentlicher Teil plus persoenlicher.

        Der oeffentliche Teil steht im Repo und beschreibt nur, wie der
        Agent arbeitet. Der persoenliche Teil (Profil, Geraete, Haltung)
        liegt in einer gitignorierten Datei daneben und ist optional -
        fehlt sie, laeuft der Agent ohne Wissen ueber den Nutzer weiter.
        """
        try:
            with open(settings.system_prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except FileNotFoundError:
            logger.warning(
                "System prompt file not found: %s. Using default.",
                settings.system_prompt_file,
            )
            prompt = "Du bist ein hilfreicher KI-Assistent."

        try:
            with open(settings.system_prompt_local_file, "r", encoding="utf-8") as f:
                persoenlich = f.read().strip()
            if persoenlich:
                prompt = f"{prompt}\n\n{persoenlich}"
        except FileNotFoundError:
            # Normalfall auf einem frisch geklonten Rechner - kein Fehler.
            logger.debug(
                "Kein persoenlicher System-Prompt unter %s",
                settings.system_prompt_local_file,
            )

        # Fähigkeiten-Selbstbild anhängen: Der Agent weiß, was er kann und
        # was an Hermes delegiert wird (Terminal/Datei/System/Tool-Install).
        try:
            from app.services.faehigkeiten import faehigkeits_block
            prompt = prompt + faehigkeits_block()
        except Exception as e:  # pragma: no cover - darf den Prompt nie brechen
            logger.warning("Fähigkeiten-Block nicht angehängt: %s", e)

        return prompt

    def _build_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """Build a memory context string from retrieved memories."""
        if not memories:
            return ""

        context_parts = ["\n## GEMERKTE INFORMATIONEN AUS FRÜHEREN GESPRÄCHEN:"]
        for mem in memories:
            context_parts.append(f"- {mem['content']} (Kategorie: {mem['category']})")

        return "\n".join(context_parts)

    def _extra_body(
        self,
        web_search: str = "off",
        no_retention: bool = False,
    ) -> Dict[str, Any]:
        """Zusatzfelder für den LLM-Aufruf.

        ``no_retention`` setzt ``provider.data_collection = "deny"``. Ohne
        diesen Riegel entscheidet OpenRouters Routing, bei welchem Anbieter
        die Anfrage landet – und 75 der nutzbaren Modelle haben mindestens
        einen Anbieter, der Prompts speichert. Der Riegel macht daraus eine
        Zusicherung: Passt kein Anbieter, wird die Anfrage abgelehnt, statt
        still bei einem speichernden zu landen.

        Die Kontoeinstellungen bleiben davon unberührt und gelten weiterhin
        als Untergrenze – der Parameter kann nur zusätzlich einschränken.

        Die Anbieter-Einstellung muss dabei erhalten bleiben – wird sie vom
        Suchplugin überschrieben, fällt die Ausweichlogik weg.

        Zwei Wege zur Websuche, die sich grundlegend unterscheiden:

        - ``manual`` nutzt das Plugin. Es sucht **einmal pro Anfrage**, egal
          worum es geht – auch bei "danke". Der Nutzer entscheidet über den
          Schalter, wann das sinnvoll ist.
        - ``auto`` nutzt das Server-Werkzeug. Das Modell ruft es nur auf, wenn
          es aktuelle Angaben braucht; OpenRouter führt die Suche selbst aus.
          Es kostet also nur bei tatsächlicher Suche.
        """
        extra: Dict[str, Any] = {"provider": {"allow_fallbacks": True}}

        if no_retention:
            extra["provider"]["data_collection"] = "deny"

        if web_search == "manual":
            extra["plugins"] = [{"id": "web", "max_results": WEB_MAX_RESULTS}]
        elif web_search == "auto":
            # Bewusst über extra_body statt über den tools-Parameter des SDK:
            # Der Typ ist OpenRouter-eigen und passt nicht in dessen Schema.
            extra["tools"] = [{
                "type": "openrouter:web_search",
                "parameters": {"max_results": WEB_MAX_RESULTS},
            }]

        return extra

    @staticmethod
    def _quellen(annotations: Any) -> List[Dict[str, str]]:
        """Aus den Anmerkungen einer Antwort eine schlichte Quellenliste bauen.

        Die Form schwankt je nach Anbieter zwischen Wörterbuch und Objekt,
        deshalb wird beides abgeklopft und Unbrauchbares übersprungen.
        """
        gefunden: List[Dict[str, str]] = []
        for eintrag in annotations or []:
            try:
                if isinstance(eintrag, dict):
                    typ = eintrag.get("type")
                    daten = eintrag.get("url_citation") or {}
                else:
                    typ = getattr(eintrag, "type", None)
                    roh = getattr(eintrag, "url_citation", None)
                    daten = roh if isinstance(roh, dict) else {
                        "url": getattr(roh, "url", None),
                        "title": getattr(roh, "title", None),
                    }
                if typ != "url_citation":
                    continue
                url = daten.get("url")
                if url:
                    gefunden.append({"url": url, "title": daten.get("title") or url})
            except Exception:
                continue
        return gefunden

    @staticmethod
    def fehlertext(e: Exception) -> str:
        """Aus einem API-Fehler eine Meldung machen, mit der man etwas anfangen kann.

        OpenRouter lehnt ein Modell ab, wenn kein Anbieter zu den Privacy-
        Einstellungen des Kontos passt. Die rohe Antwort lautet dann etwa
        „No allowed providers are available" – das liest sich wie ein
        Serverfehler, ist aber eine Einstellungssache und in einem Klick
        behoben, wenn man weiß, woran es liegt.
        """
        if isinstance(e, APIStatusError):
            try:
                body = e.response.text[:500]
            except Exception:
                body = ""
            logger.error("OpenRouter lehnte ab (HTTP %s): %s", e.status_code, body)

            klein = body.lower()
            if any(h in klein for h in (
                "no allowed providers", "no endpoints found", "data policy",
            )):
                return (
                    "⚠️ **Dieses Modell ist mit deinen Datenschutz-Einstellungen "
                    "nicht nutzbar.**\n\nOpenRouter findet keinen Anbieter, der "
                    "zu deiner Provider-Whitelist passt. Wähle ein anderes Modell."
                )
            # Bild-Anhänge an ein reines Text-Modell: OpenRouter lehnt die
            # Anfrage ab, bevor das Modell sie sieht. Der Nutzer weiß dann
            # weder, dass es am Modell liegt, noch, was zu tun ist.
            if any(h in klein for h in (
                "does not support images", "image input", "vision",
                "unsupported content", "image_url", "input modality",
            )):
                return (
                    "⚠️ **Dieses Modell kann keine Bilder verarbeiten.**\n\n"
                    "Du hast ein Bild angehängt, aber das gewählte Modell "
                    "unterstützt keine Bild-Eingabe. Wechsle in der "
                    "Modellauswahl zu einem Vision-Modell (Filter "
                    "„Bilder/Dateien“), z. B. `openai/gpt-5-nano` oder "
                    "`anthropic/claude-sonnet-5`."
                )
            if "regional routing" in klein:
                return (
                    "⚠️ **EU-Routing ist für dieses Konto nicht freigeschaltet.**\n\n"
                    "Es erfordert einen Enterprise-Vertrag bei OpenRouter."
                )

        return f"⚠️ Fehler bei der Anfrage an OpenRouter:\n```\n{e}\n```"

    @staticmethod
    def _build_archiv_context(treffer: List[Dict[str, Any]]) -> str:
        """Archiv-Fundstellen für den System-Prompt aufbereiten.

        Mit Quelle und Datum, damit das Modell sagen kann, *woher* es etwas
        weiß. Ein Assistent, der über die eigene Vergangenheit spricht, ohne
        die Fundstelle nennen zu können, ist nicht überprüfbar – und damit
        wertlos, sobald er sich irrt.
        """
        if not treffer:
            return ""

        teile = [
            "\n## AUS DEINEN FRÜHEREN GESPRÄCHEN "
            "(Archiv – nenne Quelle und Datum, wenn du dich darauf beziehst):"
        ]
        for t in treffer:
            datum = (t.get("beginn") or "")[:10]
            quelle = t.get("source") or "unbekannt"
            titel = t.get("title") or ""
            kopf = f"[{quelle}, {datum}]" + (f" {titel}" if titel else "")
            # Gekürzt: Ein Chunk kann sehr lang sein, und fünf davon
            # ungekürzt verdrängen die eigentliche Unterhaltung.
            text = (t.get("text") or "").strip()
            if len(text) > 1200:
                text = text[:1200] + " […]"
            teile.append(f"{kopf}\n{text}")
        return "\n\n".join(teile)

    def _build_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
        archiv: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
    ) -> List[Dict[str, str]]:
        """Nachrichtenliste für einen LLM-Aufruf zusammenbauen.

        Wird von chat() und chat_stream() gemeinsam genutzt, damit beide
        Wege garantiert denselben Kontext sehen.

        Wenn Dateien (Bilder/PDFs) angehängt sind, wird der User-Content
        als Array gemischt (Text + image_urls / PDF-Text).
        """
        system_prompt = self.load_system_prompt()

        # Rolling-Summary der älteren Unterhaltung (Ein-Chat) — wird in den
        # System-Kontext eingebettet, damit die Vergangenheit nicht verloren
        # geht, auch wenn die Historie auf die letzten Nachrichten begrenzt ist.
        if summary and summary.strip():
            system_prompt += (
                "\n\n[Zusammenfassung deiner früheren Unterhaltung mit dem Nutzer — "
                "behalte die wichtigsten Fakten im Hinterkopf:]\n" + summary.strip()
            )

        # Add memory context to system prompt if memories exist
        memory_context = self._build_memory_context(memories or [])
        if memory_context:
            system_prompt += memory_context

        # Fundstellen aus dem Chat-Archiv – das, was den Agenten überhaupt
        # erst über die eigene Vergangenheit sprechen lässt.
        archiv_context = self._build_archiv_context(archiv or [])
        if archiv_context:
            system_prompt += archiv_context

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history (last 10 messages for context)
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append(msg)

        # User-Nachricht mit optionalen Dateianhängen
        if files and len(files) > 0:
            content_parts: List[Dict[str, Any]] = [
                {"type": "text", "text": user_message}
            ]
            pdf_context_parts: List[str] = []

            for f in files:
                if f.get("type") == "image" and f.get("data_url"):
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f["data_url"],
                            "detail": "auto",
                        },
                    })
                elif f.get("type") == "pdf" and f.get("text"):
                    pdf_context_parts.append(
                        f"[PDF: {f.get('filename', 'Unbenannt')}]\n{f['text']}"
                    )

            if pdf_context_parts:
                content_parts.append({
                    "type": "text",
                    "text": "\n\n---\nInhalt hochgeladener PDFs:\n" + "\n\n".join(pdf_context_parts),
                })

            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_message})

        return messages

    def chat_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
        web_search: str = "off",
        model: Optional[str] = None,
        no_retention: bool = False,
        archiv: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
    ) -> Iterator[Dict[str, Any]]:
        """Wie chat(), liefert die Antwort aber Stück für Stück.

        Args:
            model: Abweichendes Modell; ohne Angabe das aus der Konfiguration.

        Yields:
            `{"delta": "..."}` für Textstücke,
            `{"sources": [...]}` sobald neue Fundstellen auftauchen.
        """
        if not self.is_configured:
            yield {"delta": NICHT_KONFIGURIERT}
            return

        messages = self._build_messages(user_message, conversation_history, memories, archiv, files, summary)

        stream = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,  # type: ignore
            temperature=0.7,
            # 4096 statt 2048: Reasoning-Modelle (76 der 109 nutzbaren) zaehlen
            # ihre Denkschritte gegen dieses Budget. Mit 2048 verbraucht etwa
            # gpt-5-nano alles im Nachdenken und liefert eine LEERE Antwort –
            # ohne Fehlermeldung, was die Ursache gut versteckt.
            max_tokens=4096,
            stream=True,
            extra_body=self._extra_body(web_search, no_retention),
        )

        gesehen: set = set()
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue

            # Quellen können an jedem Häppchen hängen, nicht nur am ersten
            # oder letzten – deshalb bei jedem nachsehen und doppelte
            # Adressen herausfiltern.
            neue = [
                q for q in self._quellen(getattr(delta, "annotations", None))
                if q["url"] not in gesehen
            ]
            if neue:
                gesehen.update(q["url"] for q in neue)
                yield {"sources": neue}

            if delta.content:
                yield {"delta": delta.content}

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        memories: Optional[List[Dict[str, Any]]] = None,
        web_search: str = "off",
        model: Optional[str] = None,
        no_retention: bool = False,
        archiv: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        summary: str = "",
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Send a chat message to the LLM and get a response.

        Args:
            user_message: The user's current message
            conversation_history: Previous messages in this conversation
            memories: Relevant memories retrieved from vector DB
            web_search: "off", "manual" oder "auto" (siehe _extra_body)
            model: Abweichendes Modell; ohne Angabe das aus der Konfiguration

        Returns:
            Antworttext und Liste der Fundstellen (leer ohne Websuche)
        """
        if not self.is_configured:
            return NICHT_KONFIGURIERT, []

        messages = self._build_messages(user_message, conversation_history, memories, archiv, files, summary)

        try:
            response = self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,  # type: ignore
                temperature=0.7,
                max_tokens=4096,   # siehe chat_stream: Reasoning zaehlt mit
                extra_body=self._extra_body(web_search, no_retention),
            )

            nachricht = response.choices[0].message
            reply = nachricht.content or ""
            quellen = self._quellen(getattr(nachricht, "annotations", None))
            logger.debug(
                "LLM response received (%d tokens, model=%s, %d Quellen)",
                response.usage.total_tokens if response.usage else 0,
                response.model,
                len(quellen),
            )
            return reply, quellen

        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            return self.fehlertext(e), []

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

        # Die Anweisung ist bewusst abweisend formuliert. Die frühere Fassung
        # bat um "maximal 3 wichtige Fakten" – eine Aufforderung zu liefern,
        # der ein Modell auch dann nachkommt, wenn nichts dasteht. So
        # entstanden erfundene Einträge wie "Lieblings-Protokoll: WireGuard",
        # bloß weil das Wort im Gespräch vorkam.
        #
        # Die Antwort des Assistenten steht weiterhin im Text, weil ein Fakt
        # oft erst durch sie eindeutig wird ("Wie alt bin ich?" – "42").
        # Deshalb der ausdrückliche Riegel, aus ihr nichts abzuleiten: Sonst
        # wurde die Selbstbeschreibung des Agenten zum Beruf des Nutzers.
        extraction_prompt = (
            "Du pflegst ein Gedächtnis über den Nutzer. Ein falscher Eintrag "
            "richtet dort mehr Schaden an als ein fehlender, denn er wird "
            "später als Tatsache behandelt.\n\n"
            "Übernimm, was der Nutzer über sich selbst preisgibt und was "
            "auch in einem Monat noch gilt – Name, Beruf, Wohnort, "
            "Menschen um ihn herum, laufende Vorhaben, ausgesprochene "
            "Vorlieben und Abneigungen, gesundheitliche oder familiäre "
            "Umstände. Dafür braucht es keine Aufforderung: Erzählt er "
            "beiläufig 'ich arbeite seit zehn Jahren in der "
            "Automatisierung', ist das ein Fakt. Bittet er ausdrücklich "
            "('merk dir'), gilt es immer.\n\n"
            "Der Prüfstein ist die Haltbarkeit, nicht die Wichtigkeit: "
            "Was nächste Woche noch stimmt, gehört hinein.\n\n"
            "Nicht übernehmen:\n"
            "- alles aus der Antwort des Assistenten; sie beschreibt nicht "
            "den Nutzer, auch wenn sie in der Ich-Form spricht\n"
            "- Themen, die nur erwähnt oder gefragt wurden. Nach etwas zu "
            "fragen heißt nicht, es zu mögen oder zu benutzen\n"
            "- Erschlossenes, Vermutetes, Ausgeschmücktes\n"
            "- Vorübergehendes wie eingestellte Modelle oder Schalter\n\n"
            "Ging es nur um eine Sachfrage, gibt der Dialog nichts her – "
            "dann ist [] richtig. Höchstens 3 Einträge; einer, der trägt, "
            "ist mehr wert als drei, die nur füllen.\n\n"
            "Antworte NUR mit einer JSON-Liste von Strings, z.B.: "
            '["Fakt 1", "Fakt 2"] oder [].\n\n'
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
            # Audiodaten in BytesIO
            buffer = io.BytesIO(audio_bytes)

            # Format anhand der Magic Bytes erkennen (nicht nur Extension)
            # WebM/Matroska beginnt mit 0x1A 0x45 0xDF 0xA3
            # WAV beginnt mit "RIFF" (0x52 0x49 0x46 0x46)
            if len(audio_bytes) >= 4:
                if audio_bytes[:4] == b'\x1a\x45\xdf\xa3':
                    buffer.name = 'audio.webm'
                    logger.debug("Audio-Format erkannt: WebM")
                elif audio_bytes[:4] == b'RIFF':
                    buffer.name = 'audio.wav'
                    logger.debug("Audio-Format erkannt: WAV")
                else:
                    buffer.name = 'audio.webm'
                    logger.debug("Audio-Format unbekannt – sende als WebM")
            else:
                buffer.name = 'audio.webm'
                logger.warning("Audio zu kurz (%d Bytes) – sende als WebM", len(audio_bytes))

            # MAI-Transcribe 1.5 von Microsoft (via Azure, DSGVO-konform, EU-RZ)
            # Kein language-Parameter (wird nicht unterstützt, erkennt Sprache automatisch)
            # Kein prompt/Vokabular (wird nicht unterstützt)
            response = self.client.audio.transcriptions.create(
                model="microsoft/mai-transcribe-1.5",
                file=buffer,
            )
            text = (response.text or "").strip()
            logger.info("Whisper erkannt (%d Zeichen): %s", len(text), text[:80])
            return text if text else None

        except APIStatusError as e:
            # OpenRouter reicht Anbieter-Fehler nur als "Provider returned 400"
            # durch. Der eigentliche Grund steht im rohen Antwort-Body.
            try:
                body = e.response.text[:1000]
            except Exception:
                body = "<Body nicht lesbar>"
            logger.error(
                "Transkription abgelehnt (HTTP %s): %s | Anbieter-Antwort: %s",
                e.status_code, e, body,
            )
            return None

        except Exception as e:
            logger.error("Whisper-Transkription fehlgeschlagen: %s", e)
            return None

    # ── Sprachausgabe (natürliche Stimme statt Browser-Roboter) ─────────────
    def list_voices(self) -> List[Dict[str, Any]]:
        """Verfügbare Sprachmodelle samt Stimmen von OpenRouter holen.

        Braucht keinen Schlüssel – die Modell-Liste ist öffentlich.
        """
        try:
            antwort = httpx.get(
                f"{self.base_url}/models",
                params={"output_modalities": "speech"},
                timeout=10,
            )
            antwort.raise_for_status()
            modelle = antwort.json().get("data", [])
        except Exception as e:
            logger.error("Stimmliste konnte nicht geladen werden: %s", e)
            return []

        return [
            {
                "model": m["id"],
                "name": m.get("name", m["id"]),
                "dollar_pro_mio_token": round(
                    float(m.get("pricing", {}).get("prompt") or 0) * 1_000_000, 2
                ),
                "voices": m.get("supported_voices") or [],
            }
            for m in modelle
        ]

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Optional[bytes]:
        """Wandelt Text in gesprochenes Audio (MP3).

        Args:
            text: Vorzulesender Text
            voice: Stimme; ohne Angabe die aus der Konfiguration
            model: Modell; ohne Angabe das aus der Konfiguration

        Returns:
            MP3-Daten oder None bei Fehler.
        """
        if not self.is_configured or not text.strip():
            return None

        modell = model or settings.tts_model
        stimme = voice or settings.tts_voice

        try:
            # voice ist im SDK ein Pflichtparameter – ohne ihn scheitert der
            # Aufruf schon in Python, bevor eine Anfrage rausgeht.
            response = self.client.audio.speech.create(
                model=modell,
                voice=stimme,
                input=text,
                response_format="mp3",
            )
            audio = response.read()
            logger.info(
                "Sprachausgabe erzeugt (%d Zeichen → %d Bytes, %s / %s)",
                len(text), len(audio), modell, stimme,
            )
            return audio or None

        except APIStatusError as e:
            try:
                body = e.response.text[:1000]
            except Exception:
                body = "<Body nicht lesbar>"
            logger.error(
                "Sprachausgabe abgelehnt (HTTP %s): %s | Anbieter-Antwort: %s",
                e.status_code, e, body,
            )
            return None

        except Exception as e:
            logger.error("Sprachausgabe fehlgeschlagen: %s", e)
            return None

    # ── Modellkatalog ───────────────────────────────────────────────────────
    @staticmethod
    def _preis_pro_mio(roh: Any) -> Optional[float]:
        """Rohpreis je Token in Dollar je Million umrechnen.

        Modelle mit variablem Preis (``openrouter/auto``) tragen im Katalog
        den Platzhalter ``-1000000``. Als Zahl angezeigt stünde dort ein
        negativer Betrag – deshalb wird daraus ``None`` („variabel").
        """
        try:
            wert = float(roh or 0) * 1_000_000
        except (TypeError, ValueError):
            return None
        return round(wert, 3) if wert >= 0 else None

    @staticmethod
    def _preis_leistung_stufe(eingabe_pro_mio: Optional[float]) -> Optional[str]:
        """Grobe Preis-Leistungs-Einstufung anhand des Eingabepreises ($/Mio).

        Nur eine grobe, ehrliche Schablone, keine harte Bewertung der
        tatsaechlichen Qualitaet. Schwellen 2026/08 (Eingabepreis):
          - bis  0,15 $  → „sehr günstig"
          - bis  0,60 $  → „günstig"
          - bis  1,50 $  → „mittel"
          - darüber     → „teuer"
        Ohne bekannten Preis → None („unbekannt").
        """
        if eingabe_pro_mio is None:
            return None
        if eingabe_pro_mio <= 0.15:
            return "sehr günstig"
        if eingabe_pro_mio <= 0.60:
            return "günstig"
        if eingabe_pro_mio <= 1.50:
            return "mittel"
        return "teuer"

    @staticmethod
    def _whitelist() -> set:
        """Anbieter-Slugs des Kontos. Leere Menge heißt "unbekannt"."""
        return {
            s.strip().lower()
            for s in (settings.provider_whitelist or "").split(",")
            if s.strip()
        }

    @staticmethod
    def _ist_chat_modell(model_id: str) -> bool:
        """Aussortieren, was in einer Chat-Auswahl nichts verloren hat.

        - ``~``-Präfix: interne Alias-Einträge auf andere Modelle
        - ``:batch``: asynchrone Stapelverarbeitung, antwortet nicht sofort
        - ``:free``: genau die Tarife, in denen Anbieter die Daten
          verwerten dürfen – das Gegenteil dessen, was hier gesucht wird
        """
        return not (
            model_id.startswith("~")
            or ":batch" in model_id
            or ":free" in model_id
        )

    def _katalog(self, pfad: str, basis: Optional[str] = None) -> List[Dict[str, Any]]:
        """Eine Katalogseite holen.

        ``/models/user`` liefert nur mit Schlüssel etwas – OpenRouter wendet
        darauf die Provider-Whitelist und die Privacy-Einstellungen des Kontos
        an. Ohne Schlüssel kommt 401 zurück, dann bleibt die Liste leer und
        der Aufrufer entscheidet, was er anzeigt.
        """
        url = f"{basis or self.base_url}{pfad}"
        try:
            antwort = httpx.get(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            antwort.raise_for_status()
            return antwort.json().get("data", []) or []
        except Exception as e:
            logger.error("Modellkatalog nicht abrufbar (%s): %s", url, e)
            return []

    def _anbieter_richtlinien(self) -> Dict[str, Dict[str, Any]]:
        """Anbieter-Datensatz je Anbieter, abrufbar über Anzeigename UND Slug.

        Liefert den ganzen Eintrag (mit ``slug`` und ``dataPolicy``), nicht nur
        die Richtlinie: Der Slug wird gebraucht, um gegen die Whitelist des
        Kontos abzugleichen.

        Beide Schlüssel sind nötig: Die Endpunktliste eines Modells nennt den
        Anzeigenamen ("Mancer 2") und einen Tag ("mancer/fp4"), der Katalog
        dagegen den Slug ("mancer"). Über nur einen von beiden bleiben
        einzelne Anbieter ohne Treffer.

        Fällt der Endpunkt aus, kommt ein leeres Wörterbuch zurück – die
        Modellliste funktioniert dann weiterhin, nur ohne Datenschutzangaben.
        """
        jetzt = time.monotonic()
        cache = self._anbieter_cache
        if cache["daten"] is not None and jetzt - cache["zeit"] < settings.models_cache_ttl:
            return cache["daten"]

        profile: Dict[str, Dict[str, Any]] = {}
        try:
            antwort = httpx.get(ALL_PROVIDERS_URL, timeout=15)
            antwort.raise_for_status()
            roh = antwort.json()
            for anbieter in roh.get("data", roh) or []:
                for schluessel in (
                    anbieter.get("displayName"),
                    anbieter.get("slug"),
                    anbieter.get("name"),
                ):
                    if schluessel:
                        profile[schluessel] = anbieter
        except Exception as e:
            logger.warning("Anbieter-Richtlinien nicht abrufbar: %s", e)

        cache.update({"zeit": jetzt, "daten": profile})
        return profile

    def _datenschutz_index(self, model_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Je Modell zählen, wie viele seiner Anbieter Prompts speichern.

        Es gibt keinen Sammelabruf dafür. Der ``providers``-Parameter des
        Katalogs sieht danach aus, liefert bei langen Anbieterlisten aber
        unvollständige Ergebnisse (nachgeprüft: ``amazon/nova-micro-v1`` wird
        ausschließlich von Amazon Bedrock bedient und fehlt trotzdem), und auf
        ``/models/user`` wird er ganz ignoriert. Bleibt der Einzelabruf –
        parallel sind rund 110 Modelle in etwa einer Sekunde durch.
        """
        jetzt = time.monotonic()
        cache = self._index_cache
        if cache["daten"] is not None and jetzt - cache["zeit"] < settings.models_cache_ttl:
            return cache["daten"]

        profile = self._anbieter_richtlinien()
        if not profile:
            # Ohne Richtlinien wäre jede Aussage geraten. Lieber keine treffen
            # als eine falsche – der Filter bleibt dann einfach leer.
            logger.warning("Kein Anbieter-Profil verfügbar – Datenschutz-Index entfällt.")
            return {}

        kopf = {"Authorization": f"Bearer {self.api_key}"}
        whitelist = self._whitelist()

        def zaehle(mid: str) -> Tuple[str, Optional[Dict[str, int]]]:
            try:
                antwort = client.get(f"{self.base_url}/models/{mid}/endpoints", headers=kopf)
                antwort.raise_for_status()
                endpunkte = (antwort.json().get("data") or {}).get("endpoints") or []
            except Exception:
                return mid, None

            gesamt = speichernd = unbekannt = 0
            for e in endpunkte:
                anbieter = (
                    profile.get(e.get("provider_name"))
                    or profile.get((e.get("tag") or "").split("/")[0])
                )
                # Ist die Whitelist bekannt, zählen nur Anbieter, die dieses
                # Konto überhaupt erreichen kann. Sonst stünde an einem Modell
                # "8 von 21 speichern", obwohl für Sebastian nur zwei Anbieter
                # in Frage kommen und davon einer speichert.
                if anbieter is not None and whitelist:
                    if (anbieter.get("slug") or "").lower() not in whitelist:
                        continue

                gesamt += 1
                if anbieter is None:
                    unbekannt += 1
                elif (anbieter.get("dataPolicy") or {}).get("retainsPrompts"):
                    speichernd += 1
            return mid, {
                "anbieter_gesamt": gesamt,
                "anbieter_speichernd": speichernd,
                "anbieter_unbekannt": unbekannt,
            }

        client = httpx.Client(timeout=20)
        try:
            with ThreadPoolExecutor(max_workers=INDEX_PARALLEL) as pool:
                ergebnisse = list(pool.map(zaehle, model_ids))
        finally:
            client.close()

        index = {mid: daten for mid, daten in ergebnisse if daten is not None}
        logger.info(
            "Datenschutz-Index: %d von %d Modellen erfasst",
            len(index), len(model_ids),
        )
        cache.update({"zeit": jetzt, "daten": index})
        return index

    def _notliste(self) -> List[Dict[str, Any]]:
        """Minimalliste, wenn der Katalog nicht erreichbar ist.

        Besser eine kurze Liste als eine leere Auswahl – sonst steht der
        Nutzer vor einem Feld ohne jede Option und weiß nicht, warum.
        """
        ids = [
            m.strip()
            for m in settings.allowed_models_fallback.split(",")
            if m.strip()
        ]
        return [
            {
                "id": mid,
                "name": mid,
                "eingabe_pro_mio": None,
                "ausgabe_pro_mio": None,
                "cache_pro_mio": None,
                "context_length": None,
                "beschreibung": None,
                "wissensstand": None,
                "max_ausgabe": None,
                "tools": False,
                "eu": False,
                "notliste": True,
            }
            for mid in ids
        ]

    def list_models(self) -> List[Dict[str, Any]]:
        """Alle Modelle, die dieses Konto tatsächlich benutzen darf.

        ``/models/user`` filtert serverseitig nach Provider-Whitelist,
        Privacy-Einstellungen und Guardrails – anders als der öffentliche
        Katalog, der alles zeigt, auch das Gesperrte.

        Das Feld ``eu`` sagt: Dieses Modell *würde* über den EU-Endpunkt
        bedient. Nutzbar ist das nur mit einem Enterprise-Vertrag; der
        Chat darüber wird für dieses Konto mit HTTP 403 abgelehnt.
        """
        jetzt = time.monotonic()
        cache = self._modelle_cache
        if cache["daten"] is not None and jetzt - cache["zeit"] < settings.models_cache_ttl:
            return cache["daten"]

        roh = self._katalog("/models/user")
        if not roh:
            return self._notliste()

        eu_ids = {
            m.get("id")
            for m in self._katalog("/models/user", settings.openrouter_eu_base_url)
        }

        modelle: List[Dict[str, Any]] = []
        for m in roh:
            mid = m.get("id") or ""
            if not mid or not self._ist_chat_modell(mid):
                continue
            preise = m.get("pricing") or {}
            parameter = m.get("supported_parameters") or []
            eingaben = (m.get("architecture") or {}).get("input_modalities") or []
            modelle.append({
                "id": mid,
                "name": m.get("name") or mid,
                "eingabe_pro_mio": self._preis_pro_mio(preise.get("prompt")),
                "ausgabe_pro_mio": self._preis_pro_mio(preise.get("completion")),
                # Cache-Preis: Wiederaufrufe eines schon gesehenen Kontexts
                # (z. B. langer System-Prompt) sind spuerbar billiger. Fehlt
                # er, ist variabel/kein Cache vorgesehen.
                "cache_pro_mio": self._preis_pro_mio(preise.get("input_cache_read")),
                "context_length": m.get("context_length"),
                # Wofuer das Modell gedacht ist – der wichtigste Hinweis bei
                # der Auswahl. OpenRouter liefert nur englische Texte; für
                # gepflegte Modelle steht hier eine deutsche Fassung (siehe
                # modelle_de.py), sonst die englische OpenRouter-Beschreibung.
                "beschreibung": (
                    MODEL_BESCHREIBUNGEN_DE.get(mid)
                    or m.get("description")
                    or None
                ),
                # Eigene Einsatzempfehlung (deutsch), falls gepflegt.
                "verwendung": MODELL_USECASES_DE.get(mid),
                # Grobe Preis-Leistungs-Einstufung aus dem echten Eingabepreis
                # ($/Mio Token). Grobe, ehrliche Schwellen; "unbekannt" wenn kein Preis.
                "preis_leistung": self._preis_leistung_stufe(
                    self._preis_pro_mio(preise.get("prompt"))
                ),
                # Stärke-Profil für die AuswahlgGroupierung. Eigener Eintrag
                # (MODELL_STAERKEN_DE) gewinnt; sonst automatische Ableitung
                # aus Bild-/Reasoning-/Preis-Eigenschaften (deckt ALLE Modelle).
                "staerke": _staerke_ableiten(
                    MODELL_STAERKEN_DE.get(mid),
                    "image" in eingaben,
                    "reasoning" in parameter,
                    preise.get("prompt"),
                ),
                # Benchmark-Referenz für Top-Modelle (gepflegt), sonst leer.
                "benchmark_ref": MODELL_BENCHMARK_REF.get(mid),
                # Wissensstand / Datenstand des Modells (knowledge_cutoff).
                "wissensstand": m.get("knowledge_cutoff") or None,
                # Laengste Antwort, die ein Modell in einem Zug ausgeben kann.
                # Fehlt die Angabe, ist sie nicht begrenzt bzw. unbekannt.
                "max_ausgabe": (m.get("top_provider") or {}).get("max_completion_tokens"),
                # Wird in Slice D2 gebraucht: Gedächtnis-Werkzeuge laufen
                # nicht auf jedem Modell.
                "tools": "tools" in parameter,
                "reasoning": "reasoning" in parameter,
                "bilder": "image" in eingaben,
                "dateien": "file" in eingaben,
                "eu": mid in eu_ids,
            })

        # Anbieter-Datenschutz je Modell anreichern. Steht der Index nicht zur
        # Verfügung, bleibt das Feld None – "unbekannt", nicht "unbedenklich".
        index = self._datenschutz_index([m["id"] for m in modelle])
        for m in modelle:
            eintrag = index.get(m["id"])
            if eintrag is None:
                m["speicherfrei"] = None
                m["anbieter_gesamt"] = None
                m["anbieter_speichernd"] = None
            else:
                m["anbieter_gesamt"] = eintrag["anbieter_gesamt"]
                m["anbieter_speichernd"] = eintrag["anbieter_speichernd"]
                # Null Anbieter heißt nicht "sicher", sondern "keine Angabe".
                # Betrifft z. B. openrouter/free – ausgerechnet dort wäre ein
                # grünes Abzeichen die falscheste aller Auskünfte.
                if eintrag["anbieter_gesamt"] == 0:
                    m["speicherfrei"] = None
                else:
                    m["speicherfrei"] = (
                        eintrag["anbieter_speichernd"] == 0
                        and eintrag["anbieter_unbekannt"] == 0
                    )

        # Günstigste zuerst; Modelle ohne festen Preis ans Ende.
        modelle.sort(key=lambda x: (
            x["ausgabe_pro_mio"] is None,
            x["ausgabe_pro_mio"] or 0,
        ))

        logger.info(
            "Modellkatalog geladen: %d nutzbar, %d EU-fähig, %d ohne speichernden Anbieter",
            len(modelle),
            sum(1 for m in modelle if m["eu"]),
            sum(1 for m in modelle if m["speicherfrei"]),
        )
        cache.update({"zeit": jetzt, "daten": modelle})
        return modelle

    def model_details(self, model_id: str) -> Dict[str, Any]:
        """Wer bedient dieses Modell – und was macht er mit den Daten?

        Wird erst beim Antippen eines Modells abgerufen. Alle Modelle vorab
        abzufragen wäre eine Anfrage pro Modell und damit unvertretbar.
        """
        try:
            antwort = httpx.get(
                f"{self.base_url}/models/{model_id}/endpoints",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            antwort.raise_for_status()
            daten = antwort.json().get("data") or {}
        except Exception as e:
            logger.error("Anbieterliste für %s nicht abrufbar: %s", model_id, e)
            return {"id": model_id, "anbieter": [], "fehler": str(e)}

        profile = self._anbieter_richtlinien()
        whitelist = self._whitelist()
        anbieter = []
        for endpunkt in daten.get("endpoints") or []:
            name = endpunkt.get("provider_name") or "unbekannt"
            # Der Tag lautet "slug/quantisierung" – der Slug davor ist der
            # zweite Weg zum Profil, falls der Anzeigename nicht passt.
            tag = (endpunkt.get("tag") or "").split("/")[0]
            eintrag = profile.get(name) or profile.get(tag)
            richtlinie = (eintrag or {}).get("dataPolicy") if eintrag else None

            # Anbieter außerhalb der Whitelist werden gekennzeichnet, nicht
            # verschwiegen: Sie sind der Grund, eine Whitelist später zu ändern.
            slug = ((eintrag or {}).get("slug") or tag or "").lower()
            erreichbar = (not whitelist) or (slug in whitelist)

            if richtlinie is None:
                # Ohne Profil bleibt es ausdrücklich unbekannt. Hier "nein"
                # einzutragen wäre ein falsches Sicherheitsversprechen –
                # genau an der Stelle, an der es am meisten schadet.
                logger.info("Kein Datenschutz-Profil für Anbieter %r (tag %r)", name, tag)
                anbieter.append({
                    "name": name,
                    "trainiert": None,
                    "speichert": None,
                    "aufbewahrung_tage": None,
                    "agb_url": None,
                    "erreichbar": erreichbar,
                    "kontext": endpunkt.get("context_length"),
                })
                continue

            anbieter.append({
                "name": name,
                "trainiert": bool(richtlinie.get("training")),
                "speichert": bool(richtlinie.get("retainsPrompts")),
                "aufbewahrung_tage": richtlinie.get("retentionDays"),
                # Die AGB des Anbieters – zum Nachlesen, ausdrücklich KEIN
                # Nachweis eines Auftragsverarbeitungsvertrags.
                "agb_url": richtlinie.get("termsOfServiceURL"),
                "erreichbar": erreichbar,
                "kontext": endpunkt.get("context_length"),
            })

        # Erreichbare zuerst – was das Konto nicht ansteuern kann, ist
        # Hintergrundwissen und gehört nach unten.
        anbieter.sort(key=lambda a: not a["erreichbar"])

        return {
            "id": model_id,
            "name": daten.get("name") or model_id,
            "anbieter": anbieter,
            "whitelist_aktiv": bool(whitelist),
        }

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
