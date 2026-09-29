# Auftrag N24b — Belegweg: Job-Registrierung am Handy ohne Widget-Tipp belegbar machen

> **Planer:** Hauptagent. **Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`).
> **Prüfer:** frischer Subagent, andere Modellfamilie. **Datum:** 29.09.2026.
> Codex ist gesperrt (live geprüft: „You've hit your usage limit … try again at
> Oct 15th, 2026 9:32 PM"), deshalb läuft der Bauweg über einen Subagenten.

## Warum dieser Schritt

**N23** hat den Android-Nachtjob gebaut (`termux/nachpflege-job.sh`,
`termux/nachpflege-einrichten.sh`, Block in `start-termux.sh`). **N23 Teil B**
(„erster Lauf am Gerät beobachten") ist aber **nicht belegbar**: vom PC aus lässt
sich auf dem Handy kein Befehl starten (gemessen: `RUN_COMMAND`-Service fehlt,
`TermuxService` braucht `TERMUX_INTERNAL`, `run-as` → „not debuggable"). Der
einzige Weg ist Sebastians Widget-Tipp — und ob der Job danach wirklich
registriert ist, lässt sich heute nur behaupten.

**Befund dieser Runde (Planer, nur lesend):** Das Gerät hängt am Kabel
(`adb devices` → `device`), aber `/sdcard/Download/hermes_diag/` **existiert noch
nicht**. Die Einrichtung schreibt ihre Berichtszeile zwar schon nach
`hermes_diag/nachpflege_letzte.txt`, doch die eigentliche Frage — **steht
`JOB_ID 1901` wirklich in der Job-Liste von Android?** — schreibt niemand
irgendwohin. Genau das fehlt.

## Was gebaut wird (genau diese Dateien, nichts weiter)

1. **`start-termux.sh`** (ändern) — ein neuer Block, der beim Widget-Tipp den
   Beleg in den Diagnose-Ordner legt.
2. **`tools/handy/diag_holen.py`** (neu) — PC-seitiges Nur-Lese-Werkzeug: holt
   den Diagnose-Ordner per Kabel und wertet **nur die technischen Berichte** aus.
3. **`backend/tests/test_belegweg_handy.py`** (neu) — Wächter-Tests, alles offline.
4. **`docs/changelog-2026-09-29-n24b-belegweg.md`** (neu) — Doku „code + docs".

**Kein Frontend, kein Cache-Bump.**

## Anforderungen im Einzelnen

### A) Block in `start-termux.sh`

* Platz: **direkt unter** dem vorhandenen Diagnose-Block (dort ist `$DIAG`
  bereits bestimmt, Zeilen ~327–330). Der neue Block darf **nicht** davon
  abhängen, dass `$INBOX_DIR` existiert — `hermes_diag` soll auch ohne Postfach
  entstehen.
* `mkdir -p "$DIAG" 2>/dev/null || true`; gelingt es nicht → ehrliche Zeile,
  **kein** Abbruch.
* Schreibt **`$DIAG/job_liste.txt`** mit genau diesen Bestandteilen:
  * Kopfzeile `beleg job-liste <ISO-Zeit>` (`date '+%Y-%m-%dT%H:%M:%S'`),
  * `JOB_ID_ERWARTET=<Zahl>` — dieselbe Zahl wie `JOB_ID` in
    `termux/nachpflege-einrichten.sh` (nur die Zahl, kein Halluzinieren:
    aus der Datei per `grep`/`sed` lesen **oder** als Konstante mit Kommentar,
    der die Quelle nennt),
  * `JOB_ID_GEFUNDEN=ja|nein|unbekannt` — `ja`, wenn die Ausgabe von
    `termux-job-scheduler --list` die Zahl enthält; `unbekannt`, wenn das
    Programm fehlt,
  * `--- termux-job-scheduler --list ---` und darunter die **rohe Ausgabe**
    (auf 40 Zeilen gekappt), oder bei fehlendem Programm die Zeile
    `termux-job-scheduler nicht vorhanden (Beleg nicht möglich)`.
* Schreibt **`$DIAG/nachpflege_einrichtung_letzte.txt`** mit den **letzten 20
  Zeilen** von `$HOME/nachpflege-einrichten.log`; fehlt das Log, steht dort eine
  ehrliche Zeile („Log nicht vorhanden — seit der Einrichtung kein Lauf").
* **Harte Grenzen** (werden getestet): kein `rm`, kein `rm -rf`, kein
  `deletefile`/`deletefolder`, kein `--force`, kein `curl`/`wget`, kein Netz,
  keine Ausgabe eines Geheimnisses, kein Abbruch des Serverstarts (`|| true`
  bzw. `2>/dev/null`).
* Kommentar auf Deutsch, der erklärt **warum** (Widget-Tipp ist der einzige Weg,
  Heimordner über Kabel nicht lesbar, PC braucht den Beleg).

### B) `tools/handy/diag_holen.py` (PC-Seite, nur lesend)

* Modul-Docstring auf Deutsch im Stil von `tools/handy/uebergabe_uebernehmen.py`
  (Zweck, Verhalten, harte Grenzen, Exit-Codes, Aufruf).
* CLI:
  * `--ordner` (Standard `/sdcard/Download/hermes_diag`)
  * `--ziel` (Standard `~/foto_sortierung/handy_diag`)
  * `--adb` (Standard `adb`, für Tests durch eine Attrappe ersetzbar)
  * **Trockenlauf ist der Standard** (`--holen` nötig, um wirklich zu holen).
* Verhalten Trockenlauf: `adb shell ls -la <ordner>` → Dateiliste (Name, Größe)
  ausgeben, **nichts schreiben**, Exit 0; fehlt der Ordner → ehrliche Zeile
  („Ordner auf dem Gerät nicht vorhanden"), Exit 0.
* Verhalten `--holen`: je Datei (nur **reguläre** Dateien, keine Unterordner)
  * Ziel existiert mit **gleicher Größe** → `uebersprungen`, nichts laden;
  * sonst: vorhandene Zieldatei zuerst als `<name>.vorher` sichern, dann per
    `adb pull` in eine temp-Datei im Zielordner und danach `os.replace`
    (nie eine halbe Datei); Größe der Kopie gegen die Anzeige des Geräts halten
    → Ungleichheit = `fehler`, Exit 1.
* **Bericht** (wird gedruckt): je Datei Name + Bytes + Zeit; **Inhalt nur** von
  `job_liste.txt` und `nachpflege_letzte.txt` (technische Berichte), gekappt auf
  40 Zeilen; dazu die Zeile `job_1901_belegt=ja|nein|unbekannt`. **Der Inhalt
  von `antworten_letzte.jsonl`, `auftraege_letzte.jsonl`, `status_letzte.jsonl`
  und `daemon_letzte.txt` wird NIE ausgegeben** (private Chat-/Auftragsinhalte)
  — nur Name und Größe. Diese Regel muss im Docstring stehen **und** getestet
  werden.
* Schutz: `--ziel` **im Repo** → deutsche Meldung + **Exit 2** (nichts
  geschrieben); unbekannter/fehlender Ordner + `--holen` → Exit 1.
* **Keine Löschfunktion** außer dem Ersetzen der eigenen temp-Datei. Kein Netz
  außer dem lokalen `adb`-Aufruf. Keine Bibliotheken außer der Standardbibliothek.

### C) `backend/tests/test_belegweg_handy.py` (alles offline)

Regelgruppen (Zahlen am Ende der Datei-Docstring-Liste):

1. **Startskript-Block:** `job_liste.txt` und
   `nachpflege_einrichtung_letzte.txt` kommen vor; `termux-job-scheduler --list`
   kommt vor; `command -v termux-job-scheduler` als Wächter; `mkdir -p "$DIAG"`
   im neuen Block; `JOB_ID_GEFUNDEN` und `JOB_ID_ERWARTET` vorhanden.
2. **Verbotene Muster** im Startskript: `rm -rf`, `deletefile`, `deletefolder`,
   `--force`, `curl`, `wget` — 0 Treffer (bestehende Tests dürfen sich dadurch
   nicht ändern; keine bestehende Zeile umformulieren).
3. **Kein Auseinanderlaufen (lebender Wächter):** die `JOB_ID` aus
   `termux/nachpflege-einrichten.sh` steht auch im Startskript (Zahl-Vergleich,
   aus beiden Dateien gelesen).
4. **Reihenfolge:** der Beleg-Block steht **nach** der Bestimmung von `$DIAG`
   und **nach** dem `nachpflege-einrichten.sh`-Aufruf (nur Code-Zeilen zählen,
   Kommentare ausblenden).
5. **`bash -n start-termux.sh`** Exit 0 (nur wenn `bash` da ist, sonst skip).
6. **Werkzeug offline:** eine Attrappen-`adb` (kleines Bash-Skript im
   `tmp_path`, das für `shell ls -la` eine feste Liste und für `pull` eine
   erfundene Datei liefert) → Trockenlauf schreibt nichts; `--holen` holt, zwei
   Dateien mit gleicher Größe werden beim zweiten Lauf `uebersprungen`; Inhalt
   `GEHEIM-TESTTEXT` in einer Attrappen-`antworten_letzte.jsonl` erscheint
   **nicht** im Bericht; Repo-`--ziel` → Exit 2.
7. **Datenschutz:** keine echten Personen-/Orts-/Ereignisnamen, kein
   Geheimnismuster (`sk-`, `Bearer `, Ziffernfolgen ≥ 30) in den drei Dateien.
8. **Kein echter Netz-/Gerätezugriff im Test:** Testdatei ruft `adb` nur über den
   Attrappen-Pfad auf; kein `pCloud`, kein HTTP.

### D) Doku

`docs/changelog-2026-09-29-n24b-belegweg.md`: Ausgangsbefund (mit Beleg,
dass `hermes_diag` fehlte), was gebaut wurde (Zeilenzahlen), Prüfbefehl mit
Zahlen, was **nicht** belegt ist (der erste echte Widget-Tipp). Keine Zahlen
erfinden — nur was wirklich gemessen wurde.

## Regeln für den Ausführer

* **Kein git** (kein add/commit/push), keine Shell-Ausführung außer den Tests.
* Nur die vier genannten Dateien anfassen. Keine bestehende Zeile in
  `start-termux.sh` umformulieren — **nur einfügen**.
* Kein `.env`, keine Geheimnisse, keine echten Namen/Orte/Kennungen, keine Fotos,
  kein Chat-Archiv.
* Alles offline testbar; Tests dürfen **kein** Netz und **kein** echtes Gerät
  brauchen.
* Prüfbefehl selbst fahren und die Ausgabe im Abschlussbericht nennen:
  `cd backend && .venv/Scripts/python -m pytest tests/ -q` (Exit 0 erwartet).
