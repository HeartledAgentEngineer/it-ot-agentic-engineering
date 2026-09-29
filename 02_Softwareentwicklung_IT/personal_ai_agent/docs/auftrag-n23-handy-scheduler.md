# Auftrag N23 — Nachpflege-Job im Android-Ökosystem (Teil A: Repo-Seite)

> **Planer:** Hauptagent. **Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`).
> **Prüfer:** frischer Subagent, andere Modellfamilie. **Datum:** 29.09.2026.

## Warum dieser Schritt

Schritt **N22** (nächtliche Nachpflege des Archiv-Index, `backend/scripts/archiv_nachpflege.py`)
ist gebaut und abgenommen, läuft aber **nur, wenn jemand ihn startet**. Schritt
**N25** (verschlüsseltes Backup in die pCloud) wartet auf Sebastians
Passphrase-Entscheidung und ist deshalb **gesperrt** (Planjournal). Deshalb ist
N23 dran: der Nachpflege-Lauf muss **im Android-Ökosystem von selbst** laufen —
ohne eingeschalteten PC, überlebt einen Handy-Neustart.

**Gemessene Ausgangslage dieser Runde** (PC, `adb`):
`adb shell am startservice … com.termux.RUN_COMMAND` → `Error: Not found; no
service started.`; `adb shell run-as com.termux` → `package not debuggable`.
**Folge:** vom PC aus lässt sich auf dem Handy **kein** Befehl starten. Der
Handy-Teil muss deshalb über den **bewährten Widget-Tipp-Pfad** laufen
(`start-termux.sh` = Symlink `~/.shortcuts/agent`), der schon Index-, Token- und
Datendatei-Übernahme selbstheilend macht.

## Was gebaut wird (genau diese Dateien, nichts weiter)

1. **`termux/nachpflege-job.sh`** (neu) — der eigentliche Nachtjob auf dem Handy.
2. **`termux/nachpflege-einrichten.sh`** (neu) — richtet den wiederkehrenden Job
   ein (idempotent).
3. **`start-termux.sh`** (ändern) — neuer Block nahe den bestehenden
   Übernahme-Blöcken: ruft `nachpflege-einrichten.sh` auf, falls noch nicht
   eingerichtet. **Darf den Serverstart NIE verhindern** (`|| true`).
4. **`backend/tests/test_nachpflege_job.py`** (neu) — Wächter-Tests, alles offline.
5. **`docs/changelog-2026-09-29-n23-nachpflege-job.md`** (neu) — Doku „code + docs".

## Anforderungen im Einzelnen

### `termux/nachpflege-job.sh`
* Shebang wie die Nachbarskripte: `#!/data/data/com.termux/files/usr/bin/bash`,
  `set -u`. Projektordner wie in `agent-ensure.sh` bestimmen (`~/.shortcuts/agent`
  auflösen, `PROJEKT` überschreibbar).
* **Sperre gegen Doppelläufe:** `~/.nachpflege.lock` per `mkdir` (Atomarität wie
  `termux/agent-start` Zeile 52). Läuft schon ein Lauf → eine Zeile ins Log und
  `exit 0`. Eine **eigene, veraltete** Sperre (älter als 6 Stunden) wird
  entfernt — nur die eigene Sperrdatei, sonst nichts.
* **Log:** `~/nachpflege.log`, bei > 200 KB auf die letzten 500 Zeilen kürzen
  (gleiches Muster wie `agent-ensure.sh`). Jede Zeile mit Zeitstempel.
* `termux-wake-lock`, falls vorhanden (wie die Nachbarskripte).
* **Quelle und Index bestimmen:**
  `QUELLE=${ARCHIV_QUELLE:-…}` mit Kandidaten
  `$HOME/archiv/db/memory.db`, `$HOME/db/memory.db`,
  `$HOME/Chats von GPT, GEMINI, Claude/db/memory.db`;
  `INDEX=${ARCHIV_INDEX:-$HOME/archiv_index.db}`.
  Fehlt eine der beiden → **ehrliche Zeile ins Log** („Quelle fehlt: …") und
  `exit 3`, **nichts anlegen**.
* **Lauf:** `python "$PROJEKT/backend/scripts/archiv_nachpflege.py" --quelle-db …
  --index … --schreiben --mit-vektoren`. Liefert das Werkzeug **Exit 3**
  (kein OpenRouter-Schlüssel), wird **einmal ohne** `--mit-vektoren` wiederholt
  (Text soll trotzdem in den Index), und das steht so im Log. Anderer Exit ≠ 0 →
  Log + Exit-Code weitergeben.
* **Bericht für den PC:** letzte 50 Log-Zeilen **und** eine Kopfzeile
  `nachpflege_bericht <ISO-Zeit> quelle=<maske> index_mb=<n> exit=<n>` nach
  `$HOME/storage/downloads/hermes_diag/nachpflege_letzte.txt` (Rückfall
  `/sdcard/Download/hermes_diag/`) — dasselbe Muster wie die anderen Skripte, weil
  der Termux-Heimordner über ADB nicht lesbar ist. Aus dem Pfad darf **kein**
  Geheimnis und kein Nachrichteninhalt werden (nur Zahlen/Dateigrößen).
* **Verboten im Skript** (wird getestet): `rm -rf`, `deletefile`, `deletefolder`,
  Löschen/Verschieben von Index, Archiv oder Fotos, jeder Upload, jeder
  `curl`/`wget`-Aufruf mit Daten. Erlaubt ist **ausschließlich**: eigene
  Sperrdatei entfernen, eigenes Log kürzen, eigene Berichtsdatei schreiben,
  Index **anhängen** (macht das Werkzeug).
* Kein Schlüsselwert, kein Klartext-Gesprächsinhalt in Ausgabe/Log/Doku.

### `termux/nachpflege-einrichten.sh`
* **Erst fragen, dann einrichten:** `termux-job-scheduler --list | grep -q
  "<JOB_ID>"` → schon da: Zeile „schon eingerichtet" + `exit 0` (**idempotent**).
* **Weg 1 (bevorzugt):** `termux-job-scheduler` — feste `JOB_ID` (eine Zahl, im
  Skript als Konstante), täglich (`--period-ms 86400000`), `--persisted true`
  damit der Job einen Neustart übersteht. Die **tatsächlich unterstützten
  Schalter** zur Laufzeit prüfen (`termux-job-scheduler --help`), nicht raten;
  nicht unterstützte Schalter weglassen und das im Log nennen.
* **Weg 2 (Rückfall):** `crond` vorhanden → eine Zeile in den Crontab des Nutzers
  (`$PREFIX/var/spool/cron/crontabs/$(whoami)`, `termux-services`-Layout) mit
  derselben Uhrzeit; vorhandene Zeile ersetzen statt doppelt anhängen.
* **Weg 3:** beides nicht vorhanden → eine ehrliche Zeile + `exit 4`. **Kein**
  stiller Durchlauf.
* Ergebnis (Weg, Uhrzeit, Exit) in dieselbe Berichtsdatei wie oben schreiben.
* Auch hier: kein `rm -rf`, nichts löschen außer evtl. einer eigenen alten
  Crontab-Zeile (ersetzen, nicht die Datei wegwerfen).

### `start-termux.sh`
* Neuer Block **nach** dem Git-Abgleich und **nach** der Index-Übernahme, damit
  der Job auf den aktuellen Index geht.
* Aufruf: `bash "$PROJEKT/termux/nachpflege-einrichten.sh" || true` — mit
  Klartext-Kommentar auf Deutsch, warum (Widget-Tipp ist der einzige Weg aufs
  Handy, PC kann per ADB nichts starten).
* Block darf **niemals** den Serverstart verhindern und nichts bei jedem Start
  neu registrieren (der Wächter im Einricht-Skript erledigt die Idempotenz).

### `backend/tests/test_nachpflege_job.py` (offline, alles Text-/AST-Wächter)
1. Beide Skripte existieren, sind nicht leer, haben den Termux-Bash-Shebang.
2. Verbotene Muster fehlen in beiden Skripten (`rm -rf`, `deletefile`,
   `deletefolder`, `shutil.rmtree`, `os.remove`, `curl -X POST|PUT|DELETE`,
   `wget`).
3. Der Job ruft **genau** `backend/scripts/archiv_nachpflege.py` mit
   `--schreiben` und hat den **Rückfall ohne `--mit-vektoren`** (Exit 3).
4. Sperre + Wake-Lock + Log-Kürzung sind vorhanden (`mkdir`, `termux-wake-lock`,
   `tail -n 500`).
5. Der Job schreibt die Berichtsdatei in den Diagnose-Ordner und der Name
   enthält `nachpflege_letzte.txt`.
6. `start-termux.sh` enthält den Einricht-Aufruf, **mit** `|| true`, und der
   Aufruf steht **nach** dem `git fetch` und **nach** dem Index-Block.
7. `start-termux.sh` erwähnt **kein** `--force` und **kein** `rm -rf`.
8. **Wächter gegen Auseinanderlaufen:** der vom Job benutzte Indexname
   (`archiv_index.db`) und der in `start-termux.sh` übernommene Name sind
   **derselbe**; ebenso darf die Einrichtung `nachpflege-job.sh` nennen und der
   Jobname muss existieren.
9. `nachpflege-einrichten.sh` hat eine **feste** JOB_ID (Zahl) und prüft vorher
   `--list` (Idempotenz) — und nutzt `--period-ms 86400000`.
10. Kein Geheimnis-Muster in allen drei Skripten (`sk-`, `Bearer `, `PCLOUD_TOKEN=`,
    Ziffernfolgen ≥ 30).
11. Kein echter Personen-, Orts- oder Ereignisname in den neuen Dateien.
12. `bash -n` auf alle drei Skripte (nur wenn `bash` vorhanden ist, sonst
    `pytest.skip`) → Syntaxprüfung.

### Doku
* `docs/changelog-2026-09-29-n23-nachpflege-job.md`: **Zahlen und Wege**, keine
  Namen Dritter, keine Orte; was gebaut ist, was noch offen ist (siehe unten),
  Prüfbefehl mit Ergebnis.
* **Gegebenenfalls** `HANDOVER-CLAUDE-CODE.md` anfassen: **nicht** in diesem
  Schritt (fremder Agent arbeitet parallel) — nur wenn nötig, sonst weglassen.

## Prüfbefehl (Pflicht, selbst ausführen)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```
**Exit 0** nötig. Baseline vor der Änderung selbst messen und die Zahl nennen.
Zusätzlich: `bash -n termux/nachpflege-job.sh termux/nachpflege-einrichten.sh start-termux.sh`.

## Grenzen (bindend)

* **Nicht** committen, **nicht** pushen, **keine** git-Befehle — das macht der Planer.
* Fremde Dateien **nicht anfassen**: `tools/agentbus/wache.py`,
  `docs/experimente/live_zahlen.*`, `.claude/`, `docs/recherche/*`.
* Datenschutz: kein Foto, kein Chat-Inhalt, kein Kontaktname, kein Ort, keine
  Nummer, kein Schlüsselwert in Code, Test oder Doku.
* Nichts löschen, nichts verschieben, keine Schreiboperation außerhalb des Repos
  (das Handy wird in diesem Schritt **nicht** beschrieben).
* Kein `git add -A`, kein `git commit -a` (Regel „Mehrere Agenten im selben
  Arbeitsbaum").

## Offen nach diesem Schritt (ehrlich in der Doku nennen)

* Der **erste echte Handy-Lauf** (Registrierung + Nachtlauf + Überleben eines
  Neustarts) ist **nicht** verifiziert — er passiert beim nächsten Widget-Tipp
  bzw. in der ersten Nacht danach; danach steht in
  `hermes_diag/nachpflege_letzte.txt` das Ergebnis, das der PC per Kabel liest.
* Damit der Nachtlauf auf dem Handy **etwas zu tun hat**, braucht das Handy eine
  Quelle (`memory.db`); heute liegt die Archiv-Pflege auf dem PC. Der Job meldet
  eine fehlende Quelle ehrlich (Exit 3) statt still zu laufen.
