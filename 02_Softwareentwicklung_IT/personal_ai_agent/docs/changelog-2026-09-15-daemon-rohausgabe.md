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

## Noch offen

- Live prüfen (Handy): Läuft der Daemon mit diesem Stand, kommt im Coding-Chat
  echtes Feedback. Der Daemon wird beim Widget-Start und beim Server-Start
  sichergestellt — nach dem Pull also automatisch aktuell.
- Ursache des fehlenden Antwort-Kastens auf dem Handy (CLI-Fassung/Termux)
  bleibt zu beobachten; mit der Rohausgabe ist sie jetzt diagnostizierbar.
