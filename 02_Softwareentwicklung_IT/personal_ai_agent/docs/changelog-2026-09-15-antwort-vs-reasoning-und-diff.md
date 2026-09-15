# Changelog 2026-09-15 — Antwort von internem Denken getrennt, Patches mit +/−

## Auslöser (Sebastian, Sprachdiktat)

„Alles wieder in einer Blase … ich kann immer noch nicht alles sehen, teilweise
hängt das, und ich kann nur nach dem Aktualisieren alle Nachrichten sehen. Was
hast du gemacht und was nicht? Warum sehe ich das jetzt wieder so kryptisch?
Und das Einzige, was noch gefehlt hat: bestimmte Code-Schnipsel anzeigen, plus
minus."

## Ursache (belegt, nicht vermutet)

Das Status-Log des Daemons (`~/hermes_inbox/status.jsonl`) zeigte als
„Antwort"-Blasen:

    💬 Let me look at the image first.
    💬 Also, should I check whether the same flat-list flaw exists in the conv_code
    💬 es live rendering path? …
    🧠 ┌─ Reasoning ──────────────┐

Das ist das **rohe englische Modell-Reasoning**, mitten im Wort umgebrochen,
teils doppelt (die CLI zeichnet Zeilen neu). Grund: `hermes_inbox_daemon.py`
behandelte **jede** Ausgabezeile von `hermes chat -q` als Antwort —
`🟠 was der Agent denkt` und `💬 was der Agent antwortet` waren derselbe Topf.

Die CLI rahmt die Abschnitte aber sauber (`cli.py`)
: Gedanken `┌─ Reasoning ─…┐` … `└─…┘`, Antwort `╭─⚕ Hermes …╮` … `╰─…╯`.
Deshalb landete am Ende **alles zusammen in EINER Antwort-Blase** — und die
Hauptblase wurde mit „✅ **Ergebnis:**" + Reasoning-Suppe gefüllt.

## Fix 1 — Daemon trennt Antwort und Denken (`_CliAusgabe`)

`backend/hermes_inbox_daemon.py`:

- Neue Klasse `_CliAusgabe` mit Zustand (`gedanken` / `antwort` / außerhalb).
  Sie ordnet jede Zeile ein: `antwort`, `gedanke` oder `keine`.
- Nur Zeilen aus dem **Antwort-Kasten** werden Antwort und landen im `ergebnis`.
- Der **Gedanken-Kasten** wird zu EINEM kurzen Status verdichtet
  („🧠 Hermes denkt nach (internes Reasoning) …") — kein englischer Rohtext
  mehr im Chat.
- Rahmen-, Werkzeug- (`┊`) und Abschlusszeilen (`Resume this session …`,
  `session_id: …`) fallen weg.
- **Rückfall:** Erscheint gar kein Kasten (andere CLI-Fassung), gilt wie bisher
  jede Zeile als Antwort — es geht nichts verloren.
- **Rückfragen bleiben zusammen** (`_formular_haelt_puffer`): endet der Puffer
  mitten in einem Frage-Formular („1. …", „❯ 2. …"), wartet der Flush (max.
  2 s / 40 Zeilen), damit Frage + Optionen als EINE Meldung ankommen und das
  Frontend daraus die klickbare Abfrage bauen kann. Die Umbruch-Regel greift nur
  noch direkt nach einer Optionszeile — normale lange Absätze flushen weiter
  sofort.

## Fix 2 — Patches sichtbar mit +/− (`codeBlockZuHtml`)

`frontend/app.js` + `frontend/style.css`:

- ```-Blöcke laufen jetzt durch `codeBlockZuHtml(lang, code)`.
- Sprache `diff`/`patch`: jede Zeile bekommt `<span class="d-plus|d-minus|
  d-hunk|d-kopf|d-kontext">` in `<pre class="diff">` — Hinzufügungen grün,
  Löschungen rot, Hunk-Kopf blau, Dateizeilen abgesetzt.
- Alle anderen Sprachen bleiben unverändert `<pre><code>`.
- Alles escaped (`escapeHtml`) — Code bleibt kein HTML-Injektionsweg.
- Cache-Bust: `index.html` app.js `?v=20260915dA` → `eA`, style.css
  `?v=20260907bE` → `20260915bF`.

## Verifikation (frisch in diesem Lauf)

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Daemon-Filter (NEU) | `python -m pytest backend/tests/test_cli_ausgabe_boxen.py -q` | 6 passed, exit 0 |
| Daemon-Filter (ALT-Kontrolllauf) | Testdatei gegen `git show HEAD:…daemon.py` | 6 failed, exit **1** (rot = Test beweist den Fix) |
| Diff-Darstellung (NEU) | `node frontend/tests/test_diff_darstellung.js frontend/app.js` | alle grün, exit 0 |
| Diff-Darstellung (ALT) | dito gegen `git show HEAD:…app.js` | 7 rot, exit **1** |
| Syntax | `node --check frontend/app.js` | OK |
| Options-Assistent | `node frontend/tests/test_options_assistent.js frontend/app.js` | alle grün, exit 0 |
| Quiz-Ende (Regression) | `node frontend/tests/test_quiz_ende.js frontend/app.js` | exit 0 |

## Wirkung erst nach Neustart

Server (`uvicorn`) und Inbox-Daemon laden Code **ohne `--reload`**. Damit Fix 1
greift, nach dem Ende des laufenden Auftrags:

    bash /data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/termux/neu-start-nach-lauf.sh

(das Skript wartet, bis kein `hermes chat -q` mehr läuft, und startet dann Server
+ Daemon neu). Fix 2 wird mit dem Neuladen der Seite aktiv (Cache-Bust).
