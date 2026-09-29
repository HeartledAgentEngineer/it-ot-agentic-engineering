# Changelog 2026-09-29 — N23: Nachpflege-Job im Android-Ökosystem

**Auftrag:** `docs/auftrag-n23-handy-scheduler.md` (bindend).
**Ausführer:** Hermes-Subagent. **Keine** git-Befehle ausgeführt (der Planer
committet). Es wurden drei Dateien angelegt, eine geändert.

## Was gebaut wurde

| Datei | Zeilen | Art |
|---|---|---|
| `termux/nachpflege-job.sh` | 167 | neu — der Nachtjob |
| `termux/nachpflege-einrichten.sh` | 127 | neu — richtet den Job ein |
| `start-termux.sh` | 388 (vorher 375) | geändert — neuer Block, 13 Zeilen |
| `backend/tests/test_nachpflege_job.py` | 343 | neu — 28 Wächter-Tests |
| `docs/changelog-2026-09-29-n23-nachpflege-job.md` | diese Datei | neu — Doku |

Der geänderte `start-termux.sh` fügt **einen** Block hinzu (sonst nichts
angefasst); vorher 375 Zeilen, jetzt 388.

## Warum dieser Schritt

Schritt **N22** (`backend/scripts/archiv_nachpflege.py`) pflegt den Archiv-Index
inkrementell und idempotent nach, läuft aber nur auf Anstoß. N23 verankert den
Lauf im Android-Ökosystem: das Handy pflegt sich nachts **selbst**, ohne
eingeschalteten PC und über einen Neustart hinweg.

**Gemessene Ausgangslage (PC, `adb`):** `am startservice … com.termux.RUN_COMMAND`
→ „Error: Not found; no service started."; `run-as com.termux` → „package not
debuggable". **Folge:** vom PC aus lässt sich auf dem Handy **kein** Befehl
starten. Der einzige Weg aufs Handy ist der bewährte **Widget-Tipp** über
`start-termux.sh` (Symlink `~/.shortcuts/agent`). Deshalb sitzt die Einrichtung
in genau diesem Startskript.

## 1. `termux/nachpflege-job.sh` (der Nachtjob)

* **Sperre gegen Doppelläufe:** `~/.nachpflege.lock` per `mkdir` (atomar, wie
  `termux/agent-start` Zeile 52). Läuft schon ein Lauf → **eine Zeile ins Log**
  und `exit 0`. Eine **eigene, veraltete** Sperre (älter als 6 Stunden = 21600 s)
  wird entfernt — nur die eigene Sperrdatei, sonst nichts. Entfernt wird **ohne
  rekursives Löschen**: Zeitdatei weg (`rm -f`), dann `rmdir` des leeren Ordners.
* **Log:** `~/nachpflege.log`, bei **> 200 KB** auf die letzten **500 Zeilen**
  gekürzt (gleiches Muster wie `agent-ensure.sh`). Jede Zeile mit Zeitstempel.
* `termux-wake-lock`, falls vorhanden (wie die Nachbarskripte).
* **Quelle und Index:** `QUELLE=${ARCHIV_QUELLE:-…}` mit Kandidaten
  `$HOME/archiv/db/memory.db`, `$HOME/db/memory.db`,
  `$HOME/Chats von GPT, GEMINI, Claude/db/memory.db`;
  `INDEX=${ARCHIV_INDEX:-$HOME/archiv_index.db}`. Fehlt eine der beiden →
  **ehrliche Zeile ins Log** („Quelle fehlt: …" / „Index fehlt: …") und
  **`exit 3`**, nichts wird angelegt.
* **Lauf:** `python "$PROJEKT/backend/scripts/archiv_nachpflege.py" --quelle-db …
  --index … --schreiben --mit-vektoren`. Liefert das Werkzeug **Exit 3** (kein
  OpenRouter-Schlüssel), wird **einmal ohne** `--mit-vektoren` wiederholt (der
  Text kommt trotzdem in den Index, neue Chunks bleiben `hat_vektor = 0`), und
  das steht so im Log. Anderer Exit ≠ 0 → Log + Exit-Code weitergeben.
* **Bericht für den PC:** Kopfzeile
  `nachpflege_bericht <ISO-Zeit> quelle=<maske> index_mb=<n> exit=<n>` + die
  letzten **50** Log-Zeilen nach
  `$HOME/storage/downloads/hermes_diag/nachpflege_letzte.txt` (Rückfall
  `/sdcard/Download/hermes_diag/`) — dasselbe Muster wie die anderen Skripte,
  weil der Termux-Heimordner über ADB nicht lesbar ist. In den Bericht kommen
  **nur** Zahlen und der Dateiname der Quelle (Maske), **kein** Pfad, **kein**
  Inhalt, **kein** Geheimnis.
* **Grenzen:** kein rekursives Löschen, kein `deletefile`/`deletefolder`, kein
  Verschieben/Löschen von Index, Archiv oder Fotos, kein Datentransfer nach
  außen, kein Abruf von einer Gegenstelle. Erlaubt ist ausschließlich: eigene
  Sperrdatei entfernen, eigenes Log kürzen, eigene Berichtsdatei schreiben,
  Index **anhängen** (macht das Werkzeug). Kein Schlüsselwert, kein
  Gesprächsinhalt in Ausgabe/Log.

## 2. `termux/nachpflege-einrichten.sh` (Einrichtung, idempotent)

* **Erst fragen, dann einrichten:** `termux-job-scheduler --list | grep -q
  "<JOB_ID>"` → schon da: Zeile „schon eingerichtet" + `exit 0`.
* **Feste Job-Kennung:** `JOB_ID=1901` (eine Zahl, Konstante im Skript).
* **Weg 1 (bevorzugt):** `termux-job-scheduler` mit `--period-ms 86400000`
  (täglich) und `--persisted`. Die **tatsächlich unterstützten Schalter** werden
  zur Laufzeit über `termux-job-scheduler --help` geprüft, nicht geraten; fehlt
  `--persisted`, wird es weggelassen und das im Log genannt.
* **Weg 2 (Rückfall):** `crond` vorhanden → eine Zeile in den Crontab des
  Nutzers (`$PREFIX/var/spool/cron/crontabs/$(whoami)`, termux-services-Layout)
  mit derselben Uhrzeit (03:00). Eine vorhandene eigene Zeile wird **ersetzt**,
  nicht doppelt angehängt.
* **Weg 3:** beides nicht vorhanden → **ehrliche Zeile + `exit 4`**, kein stiller
  Durchlauf.
* Ergebnis (Weg, Uhrzeit, Exit) geht in dieselbe Berichtsdatei
  `hermes_diag/nachpflege_letzte.txt`. Auch hier: keine Löschbefehle, nichts
  löschen außer der eigenen alten Crontab-Zeile (ersetzen, nicht wegwerfen).

## 3. `start-termux.sh` (neuer Block)

Neuer Block **nach** dem Git-Abgleich und **nach** der Index-Übernahme, damit
der Job auf den frischen Index geht:

```sh
bash "$PROJEKT/termux/nachpflege-einrichten.sh" || true
```

Mit Klartext-Kommentar auf Deutsch, warum (Widget-Tipp ist der einzige Weg aufs
Handy; PC kann per ADB nichts starten). Das `|| true` stellt sicher, dass die
Einrichtung den **Serverstart niemals** verhindert. Der Block registriert nichts
bei jedem Start neu — die Idempotenz sitzt im Einricht-Skript.

## 4. `backend/tests/test_nachpflege_job.py` (28 Wächter-Tests, offline)

Alles ist Text-/Syntax-Wächter, nichts wird ausgeführt, was das Handy
beschreiben könnte. Abgedeckt sind die **12 Punkte** des Auftrags:

1. beide Skripte existieren, nicht leer, Termux-Bash-Shebang;
2. verbotene Muster fehlen (kein rekursives Löschen, kein
   `deletefile`/`deletefolder`, kein `shutil.rmtree`/`os.remove`, kein
   Daten-`curl -X POST/PUT/DELETE`, kein `wget`; dazu kein `scp`/`rsync`);
3. genau zwei Werkzeugaufrufe von `backend/scripts/archiv_nachpflege.py`, beide
   mit `--schreiben`, genau einer mit `--mit-vektoren`, der Rückfall danach ohne
   (an `Exit 3`);
4. `mkdir`-Sperre, `termux-wake-lock`, `tail -n 500`;
5. Bericht in `hermes_diag`, Name enthält `nachpflege_letzte.txt`, Kopfzeile mit
   `quelle=`/`index_mb=`/`exit=`, letzte 50 Log-Zeilen;
6. Einricht-Aufruf **mit** `|| true`, **nach** `git fetch` und **nach** dem
   Index-Block, **vor** dem Serverstart;
7. `start-termux.sh` erwähnt **kein** `--force` und **kein** `rm -rf`;
8. Wächter gegen Auseinanderlaufen: derselbe Indexname (`archiv_index.db`) in
   Job und Startskript; die Einrichtung nennt `nachpflege-job.sh`, und diese
   Datei existiert;
9. feste `JOB_ID` (Zahl), `--list`-Prüfung vor der Registrierung,
   `--period-ms 86400000`, `--help`-Prüfung, crond-Rückfall + `exit 4`;
10. kein Geheimnis-Muster (`Bearer `, `sk-<lange Zeichenkette>`, Ziffernfolgen ab
    30 Stellen) in allen drei Skripten; `PCLOUD_TOKEN=`/`API_KEY` zusätzlich in
    den beiden neuen Skripten;
11. keine echten Personen-/Orts-/Ereignisnamen in den neuen Skripten;
12. `bash -n` auf alle drei Skripte (sonst `pytest.skip`).

## 5. Prüfbefehl (Gate, selbst ausgeführt)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* **Baseline vor der Änderung** (selbst gemessen): `3030 passed, 1 skipped` —
  Exit 0.
* **Endstand mit der neuen Testdatei:** `3058 passed, 1 skipped, 3 warnings in
  229.38s` — **Exit 0**. (3030 + 28 = 3058.)
* **Syntaxprüfung:**
  `bash -n termux/nachpflege-job.sh termux/nachpflege-einrichten.sh start-termux.sh`
  → **Exit 0**.

## 6. Ehrlich offen (nicht verifiziert in diesem Schritt)

* Der **erste echte Handy-Lauf** (Registrierung des Jobs + Nachtlauf +
  Überleben eines Handy-Neustarts) ist **nicht** verifiziert. Er passiert beim
  nächsten Widget-Tipp bzw. in der ersten Nacht danach; danach steht in
  `hermes_diag/nachpflege_letzte.txt` das Ergebnis, das der PC per Kabel liest.
  In diesem Schritt wurde das Handy **nicht** beschrieben.
* Die genauen Schalter von `termux-job-scheduler` werden am Handy zur Laufzeit
  geprüft (`--help`); die genaue Schreibweise kann je Termux-Version abweichen.
* Damit der Nachtlauf etwas zu tun hat, braucht das Handy eine **Quelle**
  (`memory.db`); heute liegt die Archiv-Pflege auf dem PC. Der Job meldet eine
  fehlende Quelle ehrlich (Exit 3) statt still zu laufen.

## 7. Grenzen (bindend, eingehalten)

* Kein Commit, kein Push, keine git-Befehle.
* Keine fremde Datei angefasst (`tools/agentbus/wache.py`,
  `docs/experimente/live_zahlen.*`, `.claude/`, `docs/recherche/*`).
* Kein Foto, kein Chat-Inhalt, kein Kontaktname, kein Ort, keine Nummer, kein
  Schlüsselwert in Code, Test oder Doku. Kein Backup, kein Upload gebaut.
* Nichts gelöscht, nichts verschoben, keine Schreiboperation außerhalb des Repos.

## 8. Prüfer-Abnahme (frische Sitzung, andere Modellfamilie: `z-ai/glm-5.2`)

**BESTANDEN, 0 blockierende Abweichungen.** Der Prüfer hat selbst gemessen und
nicht abgeschrieben:

* Prüfbefehl selbst gefahren: **3058 passed, 1 skipped, Exit 0** (222,00 s); die
  neue Testdatei allein **28 passed** (0,97 s), `grep -c "^def test_"` = **28**.
* `bash -n` auf allen drei Shell-Dateien: Exit **0 / 0 / 0**.
* Zeilenzahlen selbst nachgezählt: **167 / 127 / 388 / 343 / 166**; `start-termux.sh`
  im Vorgänger-Commit **375** → **388** (13 Zeilen zugefügt, 0 gelöscht).
* Commit `3020280` enthält **genau sechs** Dateien — keine fremde
  (`tools/agentbus/wache.py`, `docs/experimente/live_zahlen.*`, `frontend/*`
  bleiben draußen); `origin/main...HEAD` = **`0 0`**.
* Verbotene Muster im Produktivcode: **0 Treffer** (Treffer nur in den
  Test-Assertions und im Doku-Text, die diese Muster prüfen). Keine
  Geheimnis-Muster (`sk-`, `Bearer `, `PCLOUD_TOKEN=`, Ziffernfolgen ≥ 30).
* Datenschutz: kein echter Personen-/Orts-/Ereignisname in den neuen Dateien;
  die zwei Vorkommen des Nutzer-Vornamens in `start-termux.sh` sind **Bestand**
  (nicht im neuen Block) und in der Testdatei steht er ausschließlich in der
  Guard-Liste der Namen.
* **Eigene Gegenprobe zur Idempotenz:** `termux/nachpflege-einrichten.sh` mit
  einer Attrappe von `termux-job-scheduler` (Scratch-Bereich, nicht im Repo) —
  Lauf 1 registriert `JOB_ID 1901`, Lauf 2 findet ihn per `--list` und meldet
  „schon eingerichtet": **2 Läufe → 1 Registrierung**.
* Doku ↔ Code: kein Widerspruch; die Doku behauptet **nicht**, der Job sei am
  Handy eingerichtet oder verifiziert.
* Nicht blockierende Anmerkung: der Prüfer maß 222,00 s statt der im Changelog
  genannten 229,38 s — reine Laufzeit-Streuung.
