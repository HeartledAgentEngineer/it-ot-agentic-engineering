"""Deutsche Modellbeschreibungen für die Modellauswahl.

OpenRouter liefert im Katalog (`/models/user`) nur englische Beschreibungen.
Damit die Auswahl in der Benutzeroberfläche auf Deutsch ist, schlägt das
Backend hier nach: Wird ein Modell geführt, erscheint der deutsche Text;
sonst fällt ``list_models()`` auf die englische OpenRouter-Beschreibung
zurück. Pflegen lässt sich die Liste einfach, indem man einen
``modell_id: deutscher_text``-Eintrag ergänzt.

Bewusst als eigenes Modul und nicht in ``llm_service.py``: Die Tabelle ist
Daten, keine Logik, und soll sich nicht durch den Service-Code ziehen.
"""

# modell_id → deutsche Beschreibung
MODEL_BESCHREIBUNGEN_DE: dict[str, str] = {
    # ── OpenAI ──────────────────────────────────────────────────────────
    "openai/gpt-5": (
        "OpenAIs fortschrittlichstes Modell mit großen Verbesserungen bei "
        "Denkfähigkeit, Code-Qualität und Bedienbarkeit. Optimiert für "
        "komplexe Aufgaben, die schrittweises Denken und Genauigkeit erfordern."
    ),
    "openai/gpt-5.1": (
        "Das neueste Flaggschiff der GPT-5-Reihe: stärkeres allgemeines Denken, "
        "besseres Befolgen von Anweisungen und ein natürlicherer Gesprächsstil "
        "als GPT-5. Setzt auf adaptives Reasoning."
    ),
    "openai/gpt-5.1-codex": (
        "Spezialisierte Version von GPT-5.1 für Programmierung: entwickelt für "
        "agentische Coding-Aufgaben, Repository-Änderungen und Codex-Tools."
    ),
    "openai/gpt-5.1-codex-mini": (
        "Kleinere und schnellere Variante von GPT-5.1-Codex für Coding-Aufgaben "
        "mit geringerem Ressourcenbedarf."
    ),
    "openai/gpt-5.1-codex-max": (
        "OpenAIs modernstes agentisches Codier-Modell mit höchster Leistung für "
        "komplexe, langlaufende Programmieraufträge."
    ),
    "openai/gpt-5-nano": (
        "Kleinste und schnellste Variante im GPT-5-System. Für Entwickler-Tools, "
        "kurze Interaktionen und Anwendungen mit sehr geringer Latenz gedacht; "
        "in der Denktiefe begrenzter als die großen Geschwister."
    ),
    "openai/gpt-5-mini": (
        "Kompakte Version von GPT-5: günstig und schnell, geeignet für den "
        "Alltag mit soliden Fähigkeiten bei Denken und Code."
    ),
    "openai/gpt-5.4-nano": (
        "Sehr leichtgewichtige und kostengünstige Variante der GPT-5.4-Reihe "
        "für einfache Aufgaben mit hoher Geschwindigkeit."
    ),
    "openai/gpt-5.4-mini": (
        "Bringt die Kernfähigkeiten von GPT-5.4 in eine kompakte, schnelle und "
        "günstige Variante."
    ),
    "openai/gpt-5.6-luna": (
        "Schnelles und kosteneffizientes Modell in OpenAIs GPT-5.6-Reihe — "
        "guter Kompromiss aus Leistung und Preis."
    ),
    "openai/gpt-4.1": (
        "OpenAIs Flaggschiff-Großmodell, optimiert für anspruchsvolle Aufgaben, "
        "Programmierung und lange Kontexte."
    ),
    "openai/gpt-4.1-mini": (
        "Mittelgroßes Modell der GPT-4.1-Reihe mit guter Leistung zu niedrigeren "
        "Kosten als GPT-4.1."
    ),
    "openai/gpt-4.1-nano": (
        "Schnellste Variante der GPT-4.1-Reihe für einfache Aufgaben mit sehr "
        "geringer Latenz."
    ),
    "openai/gpt-4o": (
        "Multimodales Modell („Omni“): verarbeitet Text und Bilder. Sehr "
        "ausgewogen für allgemeine Assistenzaufgaben."
    ),
    "openai/gpt-4o-mini": (
        "OpenAIs modernstes kleines Modell: unterstützt Text- und Bild-Eingabe "
        "mit Text-Ausgabe und ist deutlich günstiger als GPT-4o."
    ),
    "openai/gpt-4o-2024-08-06": (
        "Aktualisierte Version von GPT-4o (August 2024) mit verbesserter "
        "Leistung gegenüber dem Original."
    ),
    "openai/gpt-3.5-turbo-0613": (
        "OpenAIs schnelles Klassiker-Modell GPT-3.5 Turbo; versteht Text und "
        "liefert Textantworten."
    ),
    "openai/gpt-3.5-turbo-16k": (
        "GPT-3.5 Turbo mit dem vierfachen Kontextumfang (16k Token) des "
        "Standardmodells."
    ),
    # ── Anthropic / Claude ─────────────────────────────────────────────
    "anthropic/claude-sonnet-5": (
        "Anthropics leistungsfähigstes Sonnet-Modell mit Spitzenleistung bei "
        "Programmierung, Agenten und professioneller Arbeit. Unterstützt "
        "adaptives Denken mit wählbarer Denk-Anstrengung (niedrig bis maximal)."
    ),
    "anthropic/claude-haiku-4.5": (
        "Anthropics schnellstes und effizientestes Modell: fast "
        "Frontline-Intelligenz zu einem Bruchteil der Kosten und Latenz "
        "größerer Claude-Modelle."
    ),
    "anthropic/claude-3-haiku": (
        "Anthropics schnellstes und kompaktestes Claude-3-Modell — geeignet "
        "für schnelle, kostengünstige Antworten."
    ),
    # ── Google / Gemini ────────────────────────────────────────────────
    "google/gemini-2.5-pro": (
        "Googles modernstes KI-Modell für anspruchsvolles Denken, "
        "Programmierung, Mathematik und wissenschaftliche Aufgaben. Nutzt "
        "eingebaute „Denk“-Fähigkeiten für genauere Antworten."
    ),
    "google/gemini-2.5-pro-preview": (
        "Vorschauversion von Gemini 2.5 Pro — wie das Endmodell sehr stark bei "
        "Denken, Programmierung und Mathematik."
    ),
    "google/gemini-2.5-flash": (
        "Googles bewährtes Arbeitstier: speziell entwickelt für anspruchsvolles "
        "Denken, Programmierung, Mathematik und Wissenschaft mit eingebauten "
        "„Denk“-Fähigkeiten."
    ),
    "google/gemini-2.5-flash-lite": (
        "Leichtgewichtiges Reasoning-Modell von Google: günstig und schnell "
        "für Alltagsaufgaben."
    ),
    "google/gemini-2.5-flash-image": (
        "Gemini 2.5 Flash mit Bildgenerierung („Nano Banana“) — multimodal für "
        "Bild- und Textaufgaben."
    ),
    "google/gemini-3.1-flash": (
        "Googles GA-modernes multimodales Hochleistungsmodell in der Flash-Klasse "
        "für schnelle und komplexe Aufgaben."
    ),
    "google/gemini-3.1-flash-lite": (
        "Hocheffizientes, kostengünstiges multimodales Modell von Google für "
        "schnelle Aufgaben."
    ),
    "google/gemini-3.1-flash-image": (
        "Gemini 3.1 Flash mit Bildgenerierung („Nano Banana 2“) — für Text und "
        "Bilderzeugung."
    ),
    "google/gemini-3.1-flash-lite-image": (
        "Gemini 3.1 Flash Lite mit Bildgenerierung („Nano Banana 2 Lite“) — "
        "kompakt für schnelle Bild- und Textaufgaben."
    ),
    "google/gemini-3-flash-preview": (
        "Vorschau von Gemini 3 Flash: schnelles, hochwertiges Denk-Modell von Google."
    ),
    "google/gemini-3.5-flash": (
        "Googles hocheffizientes multimodales Modell für schnelle, komplexe "
        "Aufgaben und agentische Arbeitsabläufe."
    ),
    "google/gemini-3.5-flash-lite": (
        "Leichtgewichtiges, hocheffizientes Modell von Google für schnelle "
        "Alltagsaufgaben."
    ),
    "google/gemini-3.6-flash": (
        "Googles hocheffizientes Flash-Modell der Gemini-3.6-Reihe für schnelle, "
        "vielseitige Aufgaben."
    ),
    "google/gemini-3.7-flash": (
        "Googles multimodales Flash-Modell für schnelle agentische Arbeitsabläufe, "
        "Programmierung und komplexes, mehrstufiges Denken."
    ),
    "google/gemini-3-pro-image": (
        "Googles fortgeschrittenstes Bildgenerierungs-Modell („Nano Banana Pro“)."
    ),
    # ── DeepSeek ────────────────────────────────────────────────────────
    "deepseek/deepseek-v4-flash": (
        "Effizienz-optimiertes Experten-Gemisch (MoE) von DeepSeek mit 284B "
        "Gesamt- und 13B aktiven Parametern sowie 1M-Token-Kontext. Entwickelt "
        "für schnelle Inferenz."
    ),
    "deepseek/deepseek-v4-flash-0731": (
        "DeepSeek V4 Flash (Stand 07/2025): verteiltes Experten-Gemisch (MoE) "
        "für schnelle, effiziente Antworten."
    ),
    "deepseek/deepseek-v4-pro": (
        "Großes Experten-Gemisch (MoE) von DeepSeek mit 1,6T Gesamt- und 49B "
        "aktiven Parametern sowie 1M-Token-Kontext. Für anspruchsvolles Denken "
        "und Programmierung."
    ),
    "deepseek/deepseek-v4-pro-0813": (
        "Großes Experten-Gemisch (MoE) von DeepSeek (Stand 08/2025) für "
        "anspruchsvolles Denken und Programmierung."
    ),
    "deepseek/deepseek-v3.2": (
        "Großes Sprachmodell von DeepSeek, entwickelt um Denken, "
        "Programmierung und vielfältige Aufgaben ausgewogen zu meistern."
    ),
    "deepseek/deepseek-v3.2-exp": (
        "Experimentelles großes Sprachmodell von DeepSeek — Erprobung neuer "
        "Fähigkeiten."
    ),
    "deepseek/deepseek-chat": (
        "DeepSeek-V3: das aktuelle Standardmodell von DeepSeek für allgemeine "
        "Chat- und Assistenzaufgaben."
    ),
    "deepseek/deepseek-chat-v3-0324": (
        "DeepSeek V3 (Stand 03/2024): großes Experten-Gemisch (MoE) mit 685B "
        "Parametern."
    ),
    "deepseek/deepseek-chat-v3.1": (
        "DeepSeek-V3.1: großes Hybrid-Denkmodell (671B Parameter), sehr stark "
        "bei Programmierung und Denken."
    ),
    "deepseek/deepseek-r1": (
        "DeepSeek R1: das bekannte Open-Source-Denkmodell, das mit dem Niveau "
        "von OpenAI o1 verglichen wird."
    ),
    "deepseek/deepseek-r1-0528": (
        "DeepSeek R1 (Update vom 28.05.) — verbesserte Version des "
        "Open-Source-Denkmodells."
    ),
    "deepseek/deepseek-r1-distill-llama-70b": (
        "Destillierte DeepSeek-R1-Fähigkeiten in Llama 70B — kompakt und "
        "denkstark."
    ),
    # ── Meta / Llama ───────────────────────────────────────────────────
    "meta-llama/llama-3.3-70b-instruct": (
        "Das mehrsprachige Llama 3.3 (LLM, 70B): vorab trainiertes, auf "
        "Anweisungen abgestimmtes generatives Modell für Text-in/Text-out."
    ),
    "meta-llama/llama-4-scout": (
        "Llama 4 Scout (17B, 16E): effizientes Experten-Gemisch (MoE) von Meta "
        "für vielseitige Aufgaben."
    ),
    "meta-llama/llama-4-maverick": (
        "Llama 4 Maverick (17B, 128E): hochleistungsfähiges multimodales "
        "Experten-Gemisch (MoE) von Meta."
    ),
    "meta-llama/llama-3.2-3b": (
        "Llama 3.2 3B: kompaktes mehrsprachiges Sprachmodell mit 3 Milliarden "
        "Parametern."
    ),
    "meta-llama/llama-3.1-8b-instruct": (
        "Llamas Modellklasse 3.1 (8B), gestartet mit vielen "
        "Einsatzmöglichkeiten — kompakt und vielseitig."
    ),
    "meta-llama/llama-3.1-70b-instruct": (
        "Llamas Modellklasse 3.1 (70B) — leistungsstärker für anspruchsvolle "
        "Aufgaben."
    ),
    "meta-llama/llama-guard-4-12b": (
        "Llama Guard 4 (12B): multimodales Sicherheits-Modell zur Inhaltsprüfung, "
        "abgeleitet von Llama 4 Scout."
    ),
    # ── Mistral ────────────────────────────────────────────────────────
    "mistralai/mistral-small-3.2-24b-instruct": (
        "Mistral Small 3.2 (24B, Stand 06/2025): optimiert fürs Befolgen von "
        "Anweisungen, weniger Wiederholungen und besseres Funktionsaufrufen."
    ),
    "mistralai/mistral-small-24b-instruct-2501": (
        "Mistral Small 3 (24B): effizientes Sprachmodell von Mistral, optimiert "
        "für schnelle Antworten."
    ),
    "mistralai/mistral-small-2603": (
        "Mistral Small 4: die nächste Hauptversion der Mistral-Small-Reihe."
    ),
    "mistralai/mistral-nemo": (
        "12B-Parameter-Modell mit 128k-Token-Kontext, entwickelt für vielseitige "
        "Aufgaben."
    ),
    "mistralai/ministral-8b": (
        "Ministral 8B: kompaktes 8B-Modell mit besonderer Effizienz."
    ),
    "mistralai/mistral-small-3.2-24b": (
        "Mistral Small 3.2 (24B): kompaktes, leistungsfähiges Sprachmodell."
    ),
    # ── Qwen (Alibaba) ─────────────────────────────────────────────────
    "qwen/qwen3-32b": (
        "Qwen3-32B: dichtes Sprachmodell mit 32,8B Parametern aus der Qwen3-Reihe, "
        "optimiert für komplexes Denken und effizienten Dialog. Mit nahtlos "
        "umschaltbarem „Denk“-Modus."
    ),
    "qwen/qwen3-30b-a3b": (
        "Qwen3 (30B-A3B): das neueste Modell der Qwen-Reihe mit effizientem "
        "Experten-Gemisch."
    ),
    "qwen/qwen3-14b": (
        "Qwen3-14B: dichtes Sprachmodell mit 14,8B Parametern für vielseitige "
        "Aufgaben."
    ),
    "qwen/qwen3-coder": (
        "Qwen3-Coder-480B-A35B: spezialisiertes Experten-Gemisch (MoE) für "
        "Programmierung."
    ),
    "qwen/qwen3-coder-30b-a3b-instruct": (
        "Qwen3-Coder-30B-A3B: auf Anweisungen abgestimmtes Expertengemisch für "
        "Coding-Aufgaben."
    ),
    "qwen/qwen-2.5-7b-instruct": (
        "Qwen2.5 7B: vielseitiges Sprachmodell von Alibaba für allgemeine Aufgaben."
    ),
    "qwen/qwen-2.5-72b-instruct": (
        "Qwen2.5 72B: leistungsstarke Variante der Qwen-Serie für anspruchsvolle "
        "Aufgaben."
    ),
    "qwen/qwen3-vl-8b-instruct": (
        "Qwen3-VL-8B: multimodales Bild-Verständnis-Modell mit Text-Antworten."
    ),
    # ── xAI / Grok ─────────────────────────────────────────────────────
    "x-ai/grok-4.6": (
        "xAI/Grok-Modell mit Frontline-Leistung bei Programmierung, "
        "Wissensarbeit und MINT-Aufgaben."
    ),
    "x-ai/grok-4.5": (
        "xAI-Grok-Modell mit Spitzenleistung auf vielen anspruchsvollen "
        "Benchmarks."
    ),
    "x-ai/grok-4.3": (
        "xAI-Grok 4.3: Reasoning-Modell für Text und anspruchsvolle "
        "Denkaufgaben."
    ),
    "x-ai/grok-4.20": (
        "xAI-Grok 4.20: Reasoning-Modell mit branchenführenden Kenntnissen."
    ),
    "x-ai/grok-4.20-multi-agent": (
        "xAI-Grok 4.20 als Multi-Agent-Variante für parallele, eigenständige "
        "Teilaufgaben."
    ),
    # ── Moonshot AI / Kimi ─────────────────────────────────────────────
    "moonshotai/kimi-k2.6": (
        "Kimi K2.6: multimodales Modell der nächsten Generation für "
        "langlaufende Coding-Aufgaben, UI/UX-Generierung und Orchestrierung "
        "mehrerer Agenten."
    ),
    "moonshotai/kimi-k2": (
        "Kimi K2 Instruct: großes Experten-Gemisch (MoE) mit starker "
        "allgemeiner Leistung."
    ),
    "moonshotai/kimi-k2-thinking": (
        "Kimi K2 Thinking: Moonshot AIs fortschrittlichstes offenes "
        "Denk-Modell."
    ),
    "moonshotai/kimi-k2.7-code": (
        "Kimi K2.7 Code: auf Programmierung fokussiertes Modell von Moonshot AI."
    ),
    "moonshotai/kimi-k2.5": (
        "Kimi K2.5: Moonshot AIs natives multimodales Modell für vielseitige "
        "Aufgaben."
    ),
    # ── MiniMax ────────────────────────────────────────────────────────
    "minimax/minimax-m3": (
        "MiniMax-M3: multimodales Grundmodell mit Text-, Bild- und Video-Eingabe, "
        "1M-Token-Kontext — geeignet für langlaufende agentische Arbeit und Coding."
    ),
    "minimax/minimax-m2": (
        "MiniMax-M2: kompaktes, hocheffizientes großes Sprachmodell."
    ),
    "minimax/minimax-m2.5": (
        "MiniMax-M2.5: modernes Sprachmodell, entwickelt für Reasoning und "
        "vielseitige Aufgaben."
    ),
    "minimax/minimax-m1": (
        "MiniMax-M1: großes Open-Source-Reasoning-Modell."
    ),
    # ── Z.ai / GLM ─────────────────────────────────────────────────────
    "z-ai/glm-5": (
        "GLM-5: Z.ais Flaggschiff-Grundmodell für komplexe Systementwicklung "
        "und langlaufende Agenten-Workflows; produktionsreif bei großer "
        "Programmierarbeit."
    ),
    "z-ai/glm-5.1": (
        "GLM-5.1: großer Sprung in der Programmierfähigkeit mit branchenführender "
        "Leistung."
    ),
    "z-ai/glm-5.2": (
        "GLM 5.2: großes Reasoning-Modell von Z.ai mit starken "
        "Schlussfolgerungs-Fähigkeiten."
    ),
    "z-ai/glm-5.3": (
        "GLM 5.3: großes Reasoning-Modell von Z.ai, gebaut für anspruchsvolles "
        "Denken."
    ),
    "z-ai/glm-5-turbo": (
        "GLM-5 Turbo: von Z.ai für schnelle Inferenz entwickeltes Modell."
    ),
    "z-ai/glm-5v-turbo": (
        "GLM-5V Turbo: Z.ais erstes natives multimodales Agenten-Grundmodell."
    ),
    "z-ai/glm-4.7": (
        "GLM-4.7: Z.ais aktuelles Flaggschiff-Modell mit vielen Verbesserungen "
        "gegenüber der Vorgängergeneration."
    ),
    "z-ai/glm-4.6": (
        "GLM-4.6: Aktualisierung von GLM 4.5 mit mehreren wichtigen "
        "Verbesserungen."
    ),
    "z-ai/glm-4.5": (
        "GLM-4.5: Z.ais Flaggschiff-Grundmodell, gezielt gebaut für klassische "
        "Aufgaben."
    ),
    # ── Amazon / Nova ──────────────────────────────────────────────────
    "amazon/nova-pro-v1": (
        "Amazon Nova Pro 1.0: leistungsfähiges multimodales Modell, das "
        "Genauigkeit, Geschwindigkeit und Kosten für viele Aufgaben ausbalanciert."
    ),
    "amazon/nova-lite-v1": (
        "Amazon Nova Lite 1.0: sehr kostengünstiges multimodales Modell für "
        "schnelle Antworten."
    ),
    "amazon/nova-micro-v1": (
        "Amazon Nova Micro 1.0: reines Textmodell mit schneller, günstiger "
        "Leistung."
    ),
    "amazon/nova-2-lite-v1": (
        "Nova 2 Lite: schnelles, kostengünstiges Reasoning-Modell von Amazon."
    ),
    # ── Nous Research / Hermes ─────────────────────────────────────────
    "nousresearch/hermes-4-70b": (
        "Hermes 4 70B: hybrides Reasoning-Modell von Nous Research auf dichter "
        "70B-Basis für Denken und allgemeine Aufgaben."
    ),
    "nousresearch/hermes-4-405b": (
        "Hermes 4 (405B): großes Reasoning-Modell von Nous Research — sehr stark "
        "bei anspruchsvollen Denkaufgaben."
    ),
    # ── Perplexity ─────────────────────────────────────────────────────
    "perplexity/sonar": (
        "Leichtgewichtiges, günstiges und schnelles Modell von Perplexity mit "
        "integrierter Websuche."
    ),
    "perplexity/sonar-deep-research": (
        "Recherche-fokussiertes Modell von Perplexity für gründliche "
        "Tiefenrecherche mit Quellenangaben."
    ),
    # ── OpenRouter-Eigenes ─────────────────────────────────────────────
    "openrouter/free": (
        "Der einfachste Weg zu kostenloser Inferenz: openrouter/free wählt "
        "zufällig ein kostenloses Modell aus denen, die auf OpenRouter verfügbar sind."
    ),
}
