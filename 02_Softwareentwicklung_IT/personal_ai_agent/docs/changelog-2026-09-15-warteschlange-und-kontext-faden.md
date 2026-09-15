# Changelog 2026-09-15 — Sichtbare Warteschlange + weitergeführter Faden im Coding-Chat

Nachtrag zum vorherigen Block (Live-Stream + ehrlicher Neustart). Auslöser war
Sebastians Wunsch, den Coding-Chat **als Alternative zur Termux-CLI** zu nutzen:
„verlässlich, genug Feedback, Fragen und Interaktion, Gespräche
weitergeführt".

## Fix 3 — Warteschlange ist sichtbar (kein „reagiert nicht" mehr)

`backend/app/services/hermes_local.py`:

**Ursache.** Der Inbox-Daemon arbeitet die Aufträge **streng nacheinander** ab
(`for auftrag in neue: _beantworte(auftrag)` in `hermes_inbox_daemon.py`). Ein
zweiter Auftrag wartet also, bis der erste fertig ist. Im Chat war das
unsichtbar: es kam nur „🔁 Hermes übernimmt die Nachricht … bearbeitet", ohne
jede Angabe, worauf gewartet wird — für den Nutzer nicht von einem Hänger zu
unterscheiden.

**Fix.** Neu: `_warteschlange_davor(auftraege.jsonl, antworten.jsonl, auftrag_id)`
zählt die noch **unbeantworteten** Aufträge, die VOR dem eigenen in der
Inbox stehen (0 = wir sind dran) und `_warteschlange_text(n)` macht daraus eine
ehrliche Meldung:

```
🕒 Warteschlange: noch 2 Auftraege davor. Hermes arbeitet sie nacheinander ab
   — deine Nachricht kommt danach (kein Haenger).
```

`stream_auftrag_aktiv()` meldet die Position **sofort** beim Übernehmen und
danach **nur bei Änderung** (Prüfung höchstens alle 3 s, damit der Verlauf nicht
zugemüllt wird). Rutscht die Position auf 0, kommt „🔧 Jetzt dran — Hermes
bearbeitet deine Nachricht…". Eine neue Warteschlangen-Meldung gilt zugleich als
Lebenszeichen (die Ruhe-Uhr für den 420-s-Hinweis wird zurückgesetzt).

**Belege.** `backend/tests/test_warteschlange_position.py` (8 Prüfungen):
erster Auftrag = 0, zweiter = 1, beantwortete zählen nicht, Aufträge NACH uns
zählen nicht, unbekannte ID/fehlende Dateien = 0, kaputte JSON-Zeilen brechen
die Zählung nicht. Gegen die ECHTE Inbox geprüft (24 Aufträge, alle beantwortet
→ Position 0, wie erwartet).

## Fix 4 — Der Faden reißt nicht mehr (Kontext für conv_code)

`backend/app/router/chat.py`, `_baue_kontext()`:

**Ursache.** Jeder Auftrag im Coding-Chat ist ein **frischer**
`hermes chat -q`-Prozess (Inbox-Daemon) — Hermes hat über Aufträge hinweg
**kein eigenes Sitzungsgedächtnis**. Die Kontinuität eines Arbeitsfadens
entsteht ausschließlich im mitgegebenen Kontextpaket. Das war auf **3 Runden ×
400 Zeichen** begrenzt: bei Coding-Aufgaben („welche Datei? welche Entscheidung?
welcher nächste Schritt?") riss der Faden dadurch regelmäßig.

**Fix.** Zwei Größen, je Kanal:

| Kanal | Runden | je Nachricht | Gesamtdeckel |
|---|---|---|---|
| `conv_code` (Coding) | bis 12 | bis 1200 Zeichen | 7000 Zeichen |
| `conv_main` (Haupt) | 3 (unverändert) | 400 (unverändert) | 1600 |

Der Deckel kürzt **vorne**, behält also das Neueste (und die Erinnerungen am
Ende). Statuszeilen mit Zeitstempel (`[10:48:20] …`) bleiben wie bisher außen
vor.

**Belege.** `backend/tests/test_kontext_delegation.py` (jetzt 6 Prüfungen):
Coding-Chat greift weiter zurück als der Haupt-Chat (Frage 2 dabei vs. nicht),
lange Nachrichten bleiben mit 900 Zeichen vollständig (Haupt-Chat kürzt auf
400), Deckel wird eingehalten (≤ 7002 Zeichen, „…"-Präfix, Neuestes enthalten),
Statuszeilen fallen raus.

## Verifikation (frisch ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| `pytest test_warteschlange_position.py test_kontext_delegation.py test_cli_ausgabe_boxen.py test_verwaiste_auftraege.py` | 24/24 grün |
| `pytest test_hermes_local_boxen.py test_sse_service.py test_sse_live_strom.py test_chat_routing.py test_hermes_spiegel_persistenz.py` | 34/34 grün (keine Regression) |
| Server-Neustart 17:08 (`termux/neu-start-nach-lauf.sh`) | Health `ok`, `Memory store loaded: 175 items`, Daemon per Selbstheilung neu |

## Fallstrick, der dabei aufgefallen ist

`termux/neu-start-nach-lauf.sh` beendet Prozesse per
`pkill -9 -f "hermes_inbox_daemon.py"`. Steht dieses Muster in der **eigenen**
Kommandozeile (z. B. in einem `pgrep -f hermes_inbox_daemon.py` aus derselben
Shell), trifft `pkill` auch die eigene Shell — sie stirbt mit SIGKILL. Prüfen
deshalb mit dem Klammer-Trick: `pgrep -f "hermes_inbox_[d]aemon"`.