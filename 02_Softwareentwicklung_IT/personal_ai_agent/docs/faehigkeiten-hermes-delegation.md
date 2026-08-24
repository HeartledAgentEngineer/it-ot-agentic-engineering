# Fähigkeiten-Selbstbild + Hermes-Delegation + Smart-Output

Zusammenfassung der jüngsten Agent-Fähigkeiten (2026-08-24).

## 1. Fähigkeiten-Selbstbild (`app/services/faehigkeiten.py`)

Der Agent weiß begründet, was er kann und was nicht:

- **`FAEHIGKEITEN`** — was der Agent kann (chat_verständnis, gedächtnis, websuche,
  archiv, dokument_text, tts_stt) und was NICHT (terminal, dateien_schreiben,
  tool_install, git, system_zugriff).
- **`stoesst_an_grenze(text)`** — erkennt Grenzthemen (Terminal/Datei/System/
  Tool-Install) **mit Wortgrenzen (Regex)**, damit kurze Marker wie "git" oder
  "run" nicht in "digital"/"darunter" fälschlich treffen.
- **`faehigkeits_block()`** — wird in den System-Prompt eingebettet (siehe
  `llm_service.load_system_prompt()`), sodass der Agent auf Anfragen an seiner
  Grenze antwortet: **"Das übernimmt Hermes."** + kurze Begründung.

## 2. Hermes-Delegation (`soll_hermes_delegieren`)

Die Chat-Weiche (`chat.py`, beide Endpoints) delegiert an Hermes, wenn:

- `ist_auftrag()` ein Coding-Kommando erkennt (bestehend), ODER
- `stoesst_an_grenze()` ein Fähigkeits-Grenzthema erkennt (NEU) — selbst wenn
  die Wort-Heuristik es nicht als Coding einstuft (z. B. "Installiere mir ein
  Paket").

Bei hochgeladenen Dateien wird NICHT delegiert (Upload = Verständnis/Analyse).

## 3. Smart-Output (`frontend/app.js`)

Rohe Auswahl-Menüs aus Hermes (z. B. `| frage | | 1. … | 2. … |`) werden als
**klickbare Option-Buttons** gerendert statt als Rohtext:

- `parseOptionsMenue(text)` — erkennt nummerierte Optionen und extrahiert
  Frage + Optionen (Wortgrenzen, Pipes → Zeilen).
- `bauOptionsUi(menu)` — baut die klickbaren Buttons; Klick sendet die gewählte
  Option an den Agenten.

## Tests

- `tests/test_faehigkeiten.py` — Manifest + Grenz-Erkennung (inkl. False-Positiv-
  Regression: "digital"/"darunter" sind KEINE Grenze).
- `tests/test_faehigkeiten_prompt.py` — Fähigkeiten-Block im System-Prompt.
- `tests/test_hermes_delegieren.py` — Delegations-Entscheidung (Coding/Grenze/
  normal/Upload).
