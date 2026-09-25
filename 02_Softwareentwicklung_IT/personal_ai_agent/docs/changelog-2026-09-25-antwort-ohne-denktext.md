# Changelog 25.09.2026 — Antwort ohne Denk-Text, erst denken dann antworten

## Befund (Live-Test Sebastian, 25.09.2026, ~22:19)

Im Chat stand als „Antwort" die **Rohausgabe samt internem Denken** des Modells:

> 📄 Rohausgabe des lokalen Hermes (Antwort-Kasten nicht erkannt): 20 Zeilen in 5 Bloecken:
> „The user just sent \"Test\" again via the frontend. This is a test harness. I should
> respond briefly in German. …"

Sebastians Vorgabe: **„Erst denken dann antwort ausgeben, nicht anders herum."**

## Ursache

Der Inbox-Daemon rief die CLI ohne Ausgabeformat auf (`hermes chat -q … -Q`). Erkannte er den
Antwort-Kasten (`╭─⚕ Hermes ╮`) nicht — was auf dem Handy der Fall war —, nahm er die Rohausgabe
(Notpfad, siehe der vorige Changelog). In dieser Rohausgabe stehen **Antwort und Denken
vermischt**; das Denken landete also in der Antwort.

## Was gemessen wurde (zwei echte CLI-Läufe, `--format stream-json`)

| Lauf | Ereignisse |
|---|---|
| `Antworte nur mit dem Wort HALLO` | `system` (init) → `text` „HALLO" → `result` (Text, Tokens, Dauer) |
| `Zaehle laut mit …`, `--reasoning high` | `system` → `text` „1" → „," → „ 2, 3," → „ 4, 5\n\n5" → `result` (vollständiger Text) |

**Ergebnis:** `type=text` sind **Antwort-Bruchstücke** (Live-Mitschnitt), `type=result` ist die
**vollständige Antwort**. Das interne Denken wird in der strukturierten Ausgabe **gar nicht**
mitgeschickt — es kann also nicht mehr in die Antwort geraten.

## Änderung (`backend/hermes_inbox_daemon.py`)

1. CLI-Aufruf mit **`--format stream-json`**.
2. Neu `_stream_json_zeile(zeile)` — ordnet eine Ausgabezeile ein: `text` → `antwort`,
   `result` → `fertig`, andere Ereignisse → `gedanke`, Nicht-JSON → `None` (dann greift die
   bisherige Kasten-Erkennung weiter, nichts wird weggenommen).
3. Neu `_art_und_text(zeile, ausgabe)` — strukturierte Ausgabe hat Vorrang, sonst alter Weg.
4. Im Lesekreislauf: `antwort` wird live als 💬-Blase gezeigt; **`ende` (die Abschlusszeile)
   ersetzt die gesammelten Bruchstücke** — damit steht im Antwortfeld genau die fertige
   Antwort, ohne Denk-Text und ohne doppelte Fassung. Ist bis dahin keine Blase entstanden,
   wird sie aus der Abschlusszeile erzeugt.
5. Leere Zwischenmeldungen werden verworfen (keine leeren Blasen).

**Reihenfolge** ist damit: Zwischenmeldungen/Gedanken → dann die verbindliche Antwort.

## Prüfung

```
cd backend && .venv/Scripts/python -m pytest tests/test_daemon_ausgabe.py -q
→ 12 passed, Exit 0
```

Neu: `test_stream_json_erkennt_antwort_und_abschluss`, `test_stream_json_trennt_denktext_von_der_antwort`
(Reasoning darf nicht in der Antwort stehen), `test_art_und_text_faellt_auf_die_alte_erkennung_zurueck`.
Zwei Erwartungen des ersten Entwurfs waren falsch und wurden an die Messung angepasst (ich hatte
`type=text` als Gedanke angenommen — gemessen ist es die Antwort in Bruchstücken).

## Nachtrag — Live-Befund vom Handy (25.09.2026, ~01:20)

Auf dem Handy kam als **Antwort die Gebrauchsanweisung der CLI**:

> hermes: error: unrecognized arguments: --format stream-json

Ursache: Die Hermes-Fassung **auf dem Handy ist älter** und kennt `--format` noch nicht; sie
brach den Lauf sofort ab. Der Daemon hatte das Flag ungefragt geschickt — das war mein Fehler.

**Behoben (dieselbe Datei):**

1. `_cli_kann_stream_json()` — fragt **einmalig** `hermes chat --help` ab und merkt das
   Ergebnis im Merker `_STREAM_JSON_OK`. Das Flag wird **nur** geschickt, wenn die CLI es kennt.
2. `_cli_kennt_flag_nicht(roh_zeilen)` — Notbremse: Steht „unrecognized arguments" in der
   Ausgabe, wird **nichts** ausgewertet und **nichts erfunden**, sondern ein Klartext-Hinweis
   geschrieben („Bitte Hermes auf diesem Gerät aktualisieren"); der Merker fällt, damit der
   nächste Auftrag es gar nicht erst versucht.

**Ergebnis:** Die Antwort auf dem Handy ist wieder korrekt (über den Notpfad). Die Trennung
von Denken und Antwort greift dort erst, wenn Hermes auf dem Handy aktualisiert ist.

Prüfung: `.venv/Scripts/python -m pytest tests/test_daemon_ausgabe.py -q` → **15 passed, Exit 0**
(neu: Erkennung der alten CLI, Erkennung der neuen CLI, Notbremse bei „unrecognized arguments").

## Noch offen

- Der Kasten-Weg bleibt als Rückfall erhalten; erst ein Lauf auf dem Handy zeigt, ob die
  strukturierte Ausgabe dort ebenfalls greift (auf dem PC gemessen, nicht am Gerät).
- Die Tokenzahl aus `type=result` wird noch nicht ausgewertet (Kostenanzeige je Auftrag wäre
  damit möglich).
