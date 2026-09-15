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
  `llm_service.load_system_prompt()`). Das Selbstbild ist **proaktiv**: Es nennt
  Hermes als benutzbares Werkzeug, listet die **Auslöser-Stichworte**, an denen
  die Weiche automatisch delegiert (Terminal/Datei schreiben/Git/Docker/
  Tool-Install/SPS-OT + Arbeitsverb mit System-Bezug), und weist den Agenten an,
  bei solchen Anfragen **NICHT zurückzufragen**, sondern direkt **"Das übernimmt
  Hermes."** zu sagen. Zusätzlich nennt es die **Handy-Dateisuche** als eigene
  Fähigkeit: Bilder/Screenshots/Fotos per Suchbegriff anzeigen und PDF-/Text-
  Dokumente vom Gerät lesen (ohne Upload), statt nach einem Upload zu fragen.

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

- `parseOptionsMenue(text)` — zerlegt die Ausgabe in **Frage-Blöcke**
  (`{fragen:[{frage, optionen}], optionen, frage}`); „1. …“, „1) …“ und
  „❯ 1. …“ werden erkannt, Pipes → Zeilen. Eine Textzeile NACH bereits
  gesehenen Optionen eröffnet die NÄCHSTE Frage — so bleibt jede Antwort bei
  ihrer Frage (früher wurde alles zu einer flachen Liste und die Fragen waren
  unsichtbar).
- `bauOptionsUi(menu)` — eine Frage: Frage + Buttons, Klick sendet die Option.
  Mehrere Fragen: **Durchklick-Assistent** `_bauOptionsAssistent(box, fragen)`
  — es wird immer NUR „Frage i von N“ mit ihren Optionen gezeigt; nach der Wahl
  kommt die nächste Frage. Erst am Ende geht EINE Nachricht mit allen Antworten
  („Frage → Wahl“) an den Agenten.
- Test: `frontend/tests/test_options_assistent.js` (echte Funktionen aus
  `app.js` in Node, mit DOM-Stub; Kontrolllauf gegen den ALT-Stand rot).

### Codeblöcke und Patches (`+`/`-`)

`parseMarkdown(text)` setzt ```-Blöcke über `codeBlockZuHtml(lang, code)` um:

- Sprache `diff`/`patch`: Jede Zeile wird eigenes `<span class="d-plus|d-minus|
  d-hunk|d-kopf|d-kontext">` in einem `<pre class="diff">` — Hinzufügungen grün,
  Löschungen rot, Hunk-Kopf blau, Dateizeilen abgesetzt (Farben in
  `style.css`). Vorher lief jeder Codeblock durch dieselbe `<pre><code>`-Ausgabe
  und ein Diff war ein grauer Block ohne erkennbares Plus/Minus.
- Alle anderen Sprachen bleiben unverändert `<pre><code>`.
- Jede Zeile wird escaped (`escapeHtml`) — Code ist kein HTML-Injektionsweg.
- Test: `frontend/tests/test_diff_darstellung.js` (inkl. Escaping-Prüfung;
  Kontrolllauf gegen den ALT-Stand rot).

## Tests

- `tests/test_faehigkeiten.py` — Manifest + Grenz-Erkennung (inkl. False-Positiv-
  Regression: "digital"/"darunter" sind KEINE Grenze).
- `tests/test_faehigkeiten_prompt.py` — Fähigkeiten-Block im System-Prompt.
- `tests/test_hermes_delegieren.py` — Delegations-Entscheidung (Coding/Grenze/
  normal/Upload).
