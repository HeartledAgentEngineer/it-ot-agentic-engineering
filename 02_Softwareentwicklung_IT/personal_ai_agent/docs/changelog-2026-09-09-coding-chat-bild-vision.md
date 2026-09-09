# Coding-Chat-Bilder → Hermes mit Gemini-Vision (2026-09-09)

## Warum
Sebastian will im Coding-Chat (`conv_code`) hochgeladene Bilder (Screenshots,
Fehlermeldungen) von **Hermes** verarbeiten lassen — Hermes soll dabei ein
Vision-fähiges Modell (Gemini) über einen Skill einsetzen. Das kehrt die frühere
Entscheidung um (2026-09-07: „Bilder im Coding-Chat **lokal** per OpenRouter-Vision
verarbeiten, KEIN Hermes-Handoff“).

## Bild-Pfad (analysiert)
1. Frontend `frontend/app.js`: Upload → `POST /api/upload` → `data_url` (base64) +
   `id`/`url` → `state.pendingFiles`.
2. Senden im Coding-Chat → `POST /api/chat/stream` (Standard) → `backend/app/router/chat.py`.
3. **Lost point (vorher):** Der conv_code-Zweig hatte den Guard `and not request.files`
   → ein Bild-Upload ging NICHT an Hermes, sondern in den OpenRouter-LLM-Pfad.
   DORT wechselte der Vision-Model-Switch nur bei Dateisuche-Bildern
   (`datei_tool_bilder`), NICHT bei Uploads → der Screenshot landete am
   bild-untauglichen `deepseek`-Modell. Zusätzlich wurde im tmux-Kanal der
   `kontext` (mit Bildpfad) verworfen — nur `query`/`aktiv` reichen den Kontext durch.

## Änderungen (`backend/app/router/chat.py`)
- **conv_code → Hermes, auch mit Bild** (`/chat` + `/chat/stream`): Guard
  `not request.files` entfernt. Ein Coding-Bild-Upload wird jetzt an Hermes
  delegiert statt an den OpenRouter-Vision-LLM.
- **`_hermes_bild_hinweis(request)` (neu):** bettet Bild-Pfad + explizite
  Vision-Anweisung („lies das Bild mit `vision_analyze`/gemini-Vision-Modell“) in
  die Hermes-Aufgabe ein. Wird im Stream-Pfad DIREKT an `herm_aufgabe` gehängt
  (erreicht auch den tmux-Kanal) und via `_hermes_kontext_mit_bild` an den Kontext.
- **Vision-Switch für ALLE Bilder:** `/chat` nutzt `bild_aktiv` statt nur
  `datei_tool_bilder`; `/chat/stream` nutzt `s_bild_aktiv`. Damit gehen auch
  hochgeladene Bilder im **normalen** Chat an `gemini-2.5-flash` statt an deepseek.

## Neuer Hermes-Skill `coding-chat-bild-vision`
- Repo: `hermes_skills/coding-chat-bild-vision/SKILL.md` (versioniert)
- Aktiv: installiert nach `~/.hermes/skills/personal-ai-agent/coding-chat-bild-vision/`
- Inhalt: Erkennt den Marker `[Angehaengte Bild-Datei zur Analyse: <pfad>]`, liest
  das Bild über das Hermes-Tool `vision_analyze` ein (routet automatisch über ein
  gemini/OpenRouter-Vision-Backend) und antwortet anhand des echten Bildinhalts
  auf Deutsch.

## Wie es jetzt läuft
Upload im Coding-Chat → conv_code → Hermes (Track C/A/B). Hermes erhält den
Bildpfad + die Anweisung im Auftrag, ruft `vision_analyze` (gemini-Vision-Backend)
auf und antwortet anhand des Bildes. Danach kann Sebastian im selben Chat mit
Spracheingabe/Tastatur-Autofill weiterarbeiten.

## Offene Punkte
- CLAUDE.md-Änderungsprotokoll konnte nicht automatisch ergänzt werden (geschützte
  Datei) — Eintrag manuell nachziehen.
- End-to-End (echte Hermes-Session + Gemini-Call) hier nicht verifiziert: kein
  Live-Server (Neustart nur über `termux/agent-start`) und kein isolierter
  Gemini-Call ausgeführt. Lokale Verifikation: `py_compile` OK, 11 Chat-Tests grün.
- Hermes' Vision-Backend wird auto-erkannt (OpenRouter/gemini-Klasse), nicht
  hart auf `google/gemini-2.5-flash` fixiert — je nach Backend-Lösung kann das
  abweichen.