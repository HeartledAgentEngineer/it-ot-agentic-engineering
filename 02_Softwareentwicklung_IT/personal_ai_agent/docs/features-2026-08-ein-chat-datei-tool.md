# Features 2026-08 (Ein-Chat, Datei-Tool, Chat-Suche, Modell-Kategorien)

Dokumentation der jüngsten Agent-Fähigkeiten — codegenau zum Stand.

## 1. Ein-Chat-Architektur (Rolling-Summary, Option C)

- Es gibt **GENAU EINE fortlaufende Conversation** (kein `+`-Button, kein
  Chat-Switcher; `neuesGespraech` ist ein No-op).
- **Rolling-Summary** (`app/services/kontext_service.py`): Ab >60 Nachrichten
  werden die älteren Teile zu einem kompakten Summary gerollt (Rate-Limit:
  frühestens alle 50 neuen Nachrichten neu).
- **Kontext pro Anfrage**: [Summary der Vergangenheit] + [letzte 15 Nachrichten]
  + [5 relevante Erinnerungen aus ChromaDB], grobes Token-Budget ~2000.
- Persistenz: Summaries liegen in `chat_verlauf.summarys`, gespeichert in
  `conversations.json` (Feld `summarys`).
- Test: `tests/test_kontext_service.py`, `tests/test_chat_verlauf_service.py`.

## 2. Handy-Dateisuche + Datei-Inhalt (über Sprache, ohne UI)

- **Stufe A** — Suche: `GET /api/dateien?suche=<wort>` durchsucht
  `~/storage/shared` (alle freigegebenen Android-Ordner) nach Dateinamen;
  nur erlaubte Erweiterungen, nur lesend, keine Systempfade/privaten Dateien.
- **Stufe B** — Inhalt lesen: `lese_datei_info(pfad)` extrahiert PDF-Text
  (pdfminer), TXT/MD direkt, Bilder als Vision-`data_url`.
- **Über Sprache**: `_datei_tool(frage)` erkennt Datei-Suchs-/Lese-Signale
  ("suche/finde/lies/was steht in/zeig mir den inhalt von …") und hängt die
  Treffer bzw. den Inhalt an die user_message — der LLM nennt/fasst zusammen.
  Keine Lupen-UI nötig; alles läuft über den Sprach-/Chat-Weg.
- Voraussetzung auf dem Handy: `termux-setup-storage` (einmalig), damit
  `~/storage/shared` existiert.
- Tests: `tests/test_datei_suche.py` (7 Tests).

## 3. Chat-Volltextsuche im Ein-Chat

- `GET /api/chat/suche?q=<begriff>` durchsucht alle Nachrichten der
  Conversations und liefert bis zu 20 Treffer (neueste zuerst) mit Rolle,
  Textausschnitt und Zeit — "was haben wir zu X gesagt?".
- Funktioniert ohne Handy-Archiv (nutzt `conversations`).
- Tests: `tests/test_chat_suche.py`.

## 4. Modell-Kategorien (Auswahl-UI)

- **Stärke-Kategorien** (klar): `bilder`, `coding`, `reasoning`, `tool_use`,
  `alltag`.
- **`tool_use` neu**: Modelle, die besonders gut Werkzeuge/Agenten nutzen
  (codex, claude-sonnet, grok).
- **`preis_leistung` ist KEIN Stärke-Profil** mehr (es ist ein Sortier-
  Kriterium); sehr günstige Modelle fallen unter `alltag`.
- Entfernt: "EU-fähig"-Chip (doppeldeutig) + "Denkt mit"-Chip.
- Quelle: `app/modelle_use.py` (`MODELL_STAERKEN_DE`) + Backend-Ableitung
  in `llm_service._staerke_ableiten`.

## Verifikation

Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest -q` → 57 Tests grün.