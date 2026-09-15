# Änderung 15.09.2026 — Der Coding-Chat bekommt jetzt IMMER inhaltliche Ausgabe

## Problem (Live, Sebastian)

Im Coding-Chat kamen nur Statusmeldungen — „Hermes nimmt die Nachricht",
„Hermes bearbeitet die Nachricht (Modell DeepSeek V4.1 Flash)", „Hermes denkt
nach", **„✅ Hermes hat geantwortet"** — aber **keine inhaltliche Antwort**.
Sichtbar war am Ende nur ein Haken und ein **Strich**: „Ergebnis —".

Für Sebastian nicht unterscheidbar von „es wurde gar nichts gearbeitet".

## Ursache

`hermes_inbox_daemon.py` ordnet jede CLI-Zeile ein: nur Zeilen **innerhalb des
Antwort-Kastens** (`╭─⚕ Hermes …╮` … `╰…╯`) wurden als Antwort gesammelt. Kam
dieser Kasten nicht an (andere CLI-Fassung, abweichende Rahmenzeichen, andere
Umgebung), blieb die Antwortliste leer — und der Code schrieb wörtlich:

```python
ergebnis = "\n".join(ergebnis_zeilen).strip() or "—"
```

Genau der Strich. Der Status „✅ Hermes hat geantwortet" wurde trotzdem gesetzt.

## Fix

1. **Alle echten Ausgabezeilen werden mitgeschrieben** (`roh_zeilen`).
2. **Ist die Antwortliste leer, wird die Rohausgabe geliefert** — klar
   gekennzeichnet:
   ```
   📄 Ausgabe des lokalen Hermes (Roh — Antwort-Kasten wurde nicht erkannt):
   …
   ```
   Rahmenzeilen, `Query:`, `Resume this session`, `session_id:` usw. fliegen
   dabei raus (bis zu 40 Zeilen).
3. **Ist auch die Rohausgabe leer**, kommt ein **Klartext-Grund** statt eines
   Strichs:
   ```
   ⚠️ Hermes hat den Auftrag bearbeitet, aber KEINE Ausgabe geliefert
   (kein Antwort-Text in der CLI-Ausgabe erkannt).
   Prüfen: tail -40 ~/hermes_inbox/daemon.log
   ```
4. **Rahmen-Erkennung geschärft:** Eine Zeile, die mit einem Eckzeichen beginnt
   (`╭╮╰╯┌┐└┘`), gilt immer als Kastenrand — auch mit Beschriftung wie
   `╭─⚕ Hermes ─────╮`. Kasten-Inhalt (`│` / `┊`) bleibt erhalten.

## Verifikation

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q     # 221 passed, Exit 0
```

Neue Tests `backend/tests/test_daemon_ausgabe.py` (5):
Rahmenzeile erkannt · leerer Fall nennt klaren Grund + Log-Hinweis ·
Rohausgabe wird geliefert und ist gekennzeichnet · **Regression:** der normale
Antwort-Kasten funktioniert unverändert · internes Reasoning wird nicht zur
Antwort.

## Was Sebastian jetzt sieht

- **Normale Läufe:** wie bisher die echte Antwort.
- **Läufe ohne erkannten Antwort-Kasten:** die tatsächliche CLI-Ausgabe, als
  Rohausgabe markiert — also **immer** inhaltliches Feedback, nie mehr nur „—".
- **Läufe komplett ohne Ausgabe:** die Meldung mit dem Log-Pfad — man weiß
  sofort, dass es ein CLI-/Umgebungsproblem ist und wo man nachsieht.

## Nachtrag (gleicher Tag) — Reihenfolge + mitlesbare Häppchen

**Beobachtung Sebastian:** Das Ergebnis erschien **vor** den Gedanken, und unten
wurden die Statuszeilen noch nachgeschoben; außerdem kam „alles auf einmal" als
großer Block (Hochscrollen nötig).

**Ursachen und Fixes (alles in `hermes_inbox_daemon.py`):**

1. **Reihenfolge:** Der Status-Puffer wurde erst **nach** dem Ergebnis geleert.
   Jetzt steht `_flush()` **direkt vor** dem Schreiben des Ergebnisses — erst
   alle Zwischenmeldungen, dann das Ergebnis. Kein Nachschieben mehr.
2. **Häppchen statt Block:** `FLUSH_MAX_ZEILEN` 6 → **2**, `FLUSH_S` 1,2 s →
   **0,8 s**. Es kommen also höchstens zwei Zeilen pro Blase, im ~0,8-s-Takt —
   mitlesbar statt „BAM".
3. **Rohausgabe: NICHT kürzen, sondern blockweise streamen** (Sebastian wollte
   ausdrücklich die **ganze** Ausgabe, nur eben langsam mitlesbar). Die
   Rohausgabe wird jetzt in Blöcken von **4 Zeilen** über
   `_schreibe_status` gestreamt — jede Blockmeldung trägt den **Zeitstempel**
   des Daemons — mit **0,4 s Pause** zwischen den Blöcken. Am Ende steht eine
   Schlusszeile („Rohausgabe vollständig: N Zeilen, oben in M Blöcken
   gestreamt"). Ohne `block_writer` (Tests, andere Aufrufer) kommt weiterhin
   alles als **ein** Text zurück — nichts geht verloren.

**Tests (3 neu/angepasst, insgesamt 8 in `tests/test_daemon_ausgabe.py`):**
komplette Rohausgabe ungekürzt (erste **und** letzte Zeile dabei) ·
Block-Streaming (8 Blöcke à 4 Zeilen, Reihenfolge korrekt, Schlusszeile) ·
Häppchen-Größe klein (`FLUSH_MAX_ZEILEN <= 3`, `FLUSH_S <= 1.0`,
`ROH_BLOCK_ZEILEN <= 6`).

**Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
**224 passed**, Exit 0.

## Noch offen

- Live prüfen (Handy): Läuft der Daemon mit diesem Stand, kommt im Coding-Chat
  echtes Feedback. Der Daemon wird beim Widget-Start und beim Server-Start
  sichergestellt — nach dem Pull also automatisch aktuell.
- Ursache des fehlenden Antwort-Kastens auf dem Handy (CLI-Fassung/Termux)
  bleibt zu beobachten; mit der Rohausgabe ist sie jetzt diagnostizierbar.
