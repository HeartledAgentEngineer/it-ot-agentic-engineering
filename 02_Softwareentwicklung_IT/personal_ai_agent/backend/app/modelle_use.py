"""Deutsche Einsatzbereich-Empfehlungen (Usecase) für die Modellauswahl.

Ergänzt die deutsche Beschreibung (`MODEL_BESCHREIBUNGEN_DE`) um die ehrliche
Antwort auf die Frage „wofür nehme ich das?“. Das Backend hängt diesen Text als
Feld `verwendung` an jedes Modell (siehe llm_service.py). Fehlt ein Modell,
liefert die Oberfläche keinen eigenen Usecase — lieber keine erfundene
Empfehlung als eine falsche.

Pflegen: `modell_id: usecase_text` ergänzen.
"""

# modell_id → deutscher Usecase / Einsatzempfehlung
MODELL_USECASES_DE: dict[str, str] = {
    # ── OpenAI ──────────────────────────────────────────────────────────
    "openai/gpt-5-nano": (
        "Alltags-Chat & einfache Aufgaben: sehr günstig und schnell, ideal "
        "für kurze Antworten, Übersetzen und kleine Anfragen."
    ),
    "openai/gpt-5-mini": (
        "Alltag mit etwas mehr Substanz: für längere Antworten und "
        "anspruchsvollere Texte, ohne schon teuer zu werden."
    ),
    "openai/gpt-5.1-codex-mini": (
        "Coding-Aufgaben: kleinere, schnelle Variante, gut für Code-Snippets "
        "und Skripte."
    ),
    "openai/gpt-5": (
        "Anspruchsvolle, mehrstufige Aufgaben, die schrittweises Denken und "
        "Genauigkeit brauchen (Analysen, Planung, komplexe Logik)."
    ),
    "openai/gpt-5.1": (
        "Sehr anspruchsvolle Aufgaben & präzise Antworten: das Flaggschiff, "
        "wenn Qualität über Kosten geht."
    ),
    "openai/gpt-4o": (
        "Multimodale Aufgaben: Bilder verstehen und Text- plus Bildeingabe "
        "in einem."
    ),
    "openai/gpt-4.1-mini": (
        "Gute Balance aus Können und Kosten für mittlere Aufgaben."
    ),
    # ── Anthropic ───────────────────────────────────────────────────────
    "anthropic/claude-sonnet-5": (
        "Professionelle Arbeit & Agenten: stark bei Programmierung, "
        "Wissensarbeit und zuverlässigem, sorgfältigem Stil."
    ),
    "anthropic/claude-haiku-4.5": (
        "Schnelle, kostengünstige Alltagsantworten mit guter Sorgfalt."
    ),
    # ── Google Gemini ───────────────────────────────────────────────────
    "google/gemini-2.5-flash-lite": (
        "Günstiger Alltag mit Denken: schnelle Antworten für einfache Fragen "
        "und Übersichten."
    ),
    "google/gemini-2.5-flash": (
        "Starke Allzweck-Wahl: Denken, Programmieren, Mathematik, "
        "Wissenschaft — zu moderaten Kosten."
    ),
    "google/gemini-2.5-pro": (
        "Komplexe Reasoning-Aufgaben und lange Analysen, wenn Qualität im "
        "Mittelpunkt steht."
    ),
    # ── DeepSeek ────────────────────────────────────────────────────────
    "deepseek/deepseek-v4-flash": (
        "Bestes Preis-Leistungs-Verhältnis im Alltag: 1M-Token-Kontext, "
        "solides Denken — die Standardwahl für den Assistenten."
    ),
    "deepseek/deepseek-v4-flash-0731": (
        "Wie V4 Flash, momentaner Stand: bewährter Alltags-Allrounder."
    ),
    "deepseek/deepseek-v4-pro": (
        "Mehr Substanz als Flash: für lange, anspruchsvollere Antworten und "
        "tiefere Analysen, wenn man das Budget gut ist."
    ),
    "deepseek/deepseek-r1": (
        "Ausführliches, schrittweises Denken (Chain-of-Thought) für "
        "knifflige Logik- und MINT-Fragen."
    ),
    # ── Qwen ────────────────────────────────────────────────────────────
    "qwen/qwen3-30b-a3b": (
        "Effizientes Experten-Gemisch (MoE): solide Alltags-Qualität zu "
        "geringen Kosten."
    ),
    "qwen/qwen3-32b": (
        "Stäkeres Qwen-Modell für anspruchsvollere Aufgaben bei moderaten "
        "Kosten."
    ),
    "qwen/qwen3-coder": (
        "Programmieren: speziell für Code-Aufgaben optimierte Qwen-Variante."
    ),
    # ── xAI / Grok ──────────────────────────────────────────────────────
    "x-ai/grok-4.6": (
        "Frontlinie bei Programmierung, Wissensarbeit und MINT: starkes "
        "Generalisten-Modell für anspruchsvolles Arbeiten."
    ),
    # ── Mistral ─────────────────────────────────────────────────────────
    "mistralai/mistral-small-3.2-24b-instruct": (
        "Schnelle, günstige Antworten für Alltagsfragen und einfache "
        "Textaufgaben."
    ),
}
