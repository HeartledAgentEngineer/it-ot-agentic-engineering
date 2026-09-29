# Changelog 2026-09-29 — N24b: Belegweg für die Job-Registrierung am Handy

Auftrag: `docs/auftrag-n24b-belegweg.md`. Gebaut von einem Hermes-Subagenten
(Codex war gesperrt — Nutzungslimit). Nur vier Dateien angefasst, kein Frontend,
kein Cache-Bump, kein git.

## 1. Ausgangsbefund (mit Beleg-Quelle)

**Der Job wird registriert — aber niemand schreibt hin, ob wirklich.** Vom PC
aus lässt sich auf dem Handy kein Befehl starten (gemessen in N23: der
`RUN_COMMAND`-Service fehlt, `TermuxService` braucht `TERMUX_INTERNAL`, `run-as`
→ „not debuggable"). Der einzige Weg ist der Widget-Tipp; ob `JOB_ID 1901`
danach in der Job-Liste von Android steht, war bisher nur **behauptet**.

Die Einrichtung schrieb ihre Berichtszeile bereits nach
`hermes_diag/nachpflege_letzte.txt`, doch der Ordner `/sdcard/Download/hermes_diag/`
existierte laut Planer-Messung (Auftrag, nur lesend geprüft) **noch nicht**, und
die eigentliche Frage — steht die Kennung in der Job-Liste? — schrieb niemand
irgendwohin. **Diese Runde hat kein Gerät angefasst** (kein adb am echten Handy,
kein Kabel): der Befund stammt aus dem Auftrag, nicht aus einer neuen Messung.

## 2. Was gebaut wurde

| Datei | Zeilen | Art |
|---|---|---|
| `start-termux.sh` | 396 → **439** (+43) | geändert (nur eingefügt, keine Zeile umformuliert) |
| `tools/handy/diag_holen.py` | **438** | neu (PC-Werkzeug, nur lesend) |
| `backend/tests/test_belegweg_handy.py` | **363** | neu (18 Testfunktionen, alles offline) |
| `docs/changelog-2026-09-29-n24b-belegweg.md` | diese Datei | neu (Doku) |

### A) Block in `start-termux.sh` (Zeilen 341–383)

Direkt **unter** dem vorhandenen Diagnose-Block (dort ist `$DIAG` bestimmt) und
somit auch **nach** dem `nachpflege-einrichten.sh`-Aufruf (Zeile 101). Der Block:

- legt `hermes_diag` selbst an (`mkdir -p "$DIAG" 2>/dev/null`), **unabhängig**
  vom Postfach (`$INBOX_DIR`) — gelingt es nicht, gibt es eine ehrliche Zeile und
  **keinen** Abbruch (kein `exit`);
- schreibt `$DIAG/job_liste.txt`: Kopfzeile `beleg job-liste <ISO-Zeit>`,
  `JOB_ID_ERWARTET=1901`, `JOB_ID_GEFUNDEN=ja|nein|unbekannt`, dann
  `--- termux-job-scheduler --list ---` mit der **rohen Ausgabe** (auf 40 Zeilen
  gekappt) — bzw. `termux-job-scheduler nicht vorhanden (Beleg nicht moeglich)`;
- schreibt `$DIAG/nachpflege_einrichtung_letzte.txt` mit den **letzten 20 Zeilen**
  von `$HOME/nachpflege-einrichten.log`, oder die ehrliche Zeile
  „Log nicht vorhanden — seit der Einrichtung kein Lauf";
- rein lesend: kein `rm`, kein `--force`, kein `curl`/`wget`, kein Netz,
  kein Geheimnis.

Die erwartete Kennung steht als Konstante mit Quellen-Kommentar
(`JOB_ID_ERWARTET=1901`, Quelle `termux/nachpflege-einrichten.sh`, dort
`JOB_ID=1901` in Zeile 37). Der Wächter-Test 3 liest die Zahl aus **beiden**
Dateien und schlägt an, falls sie auseinanderlaufen.

### B) `tools/handy/diag_holen.py` (PC-Seite, nur lesend)

Deutscher Modul-Docstring im Stil von `tools/handy/uebergabe_uebernehmen.py`
(Zweck, Verhalten, harte Grenzen, Exit-Codes, Aufruf). CLI: `--ordner`
(Standard `/sdcard/Download/hermes_diag`), `--ziel` (Standard
`~/foto_sortierung/handy_diag`), `--adb` (Standard `adb`, für Tests durch eine
Attrappe ersetzbar), **Trockenlauf ist der Standard** (`--holen` nötig).

- Trockenlauf: `adb shell ls -la <ordner>` → Dateiliste (Name, Größe, Zeit),
  **nichts** geschrieben, Exit 0; fehlender Ordner → ehrliche Zeile, Exit 0.
- `--holen`: je **regulärer** Datei — gleiche Größe im Ziel → `uebersprungen`;
  sonst vorhandene Zieldatei zuerst als `<name>.vorher` sichern, `adb pull` in
  eine temp-Datei IM Zielordner, dann `os.replace` (nie eine halbe Datei),
  Größenprobe gegen die Geräte-Anzeige → Ungleichheit = `fehler`, Exit 1.
- Bericht: je Datei Name + Bytes + Zeit; Inhalt **nur** von `job_liste.txt` und
  `nachpflege_letzte.txt` (auf 40 Zeilen gekappt); dazu
  `job_1901_belegt=ja|nein|unbekannt`. **Nie** ausgegeben wird der Inhalt von
  `antworten_letzte.jsonl`, `auftraege_letzte.jsonl`, `status_letzte.jsonl` und
  `daemon_letzte.txt` (private Chat-/Auftragsinhalte) — nur Name und Größe.
  Diese Regel steht im Docstring **und** ist getestet.
- Schutz: `--ziel` IM Repo → deutsche Meldung + Exit 2 (nichts geschrieben);
  fehlender Geräte-Ordner + `--holen` → Exit 1. Keine Löschfunktion außer dem
  Ersetzen der eigenen temp-Datei; kein Netz außer dem lokalen `adb`-Aufruf;
  nur Standardbibliothek. Exit-Codes: 0 / 1 / 2.

### C) `backend/tests/test_belegweg_handy.py` (18 Testfunktionen, alles offline)

Regelgruppen 1–8 des Auftrags: Startskript-Block · verbotene Muster im
Startskript · JOB_ID-Wächter gegen Auseinanderlaufen · Reihenfolge (nach
`$DIAG`-Bestimmung und nach dem Einricht-Aufruf, nur Code-Zeilen) · `bash -n` ·
Werkzeug offline gegen eine **Attrappen-`adb`** unter `tmp_path` (Trockenlauf
schreibt nichts; `--holen` holt; zweiter Lauf → `uebersprungen`;
`GEHEIM-TESTTEXT` aus einer Attrappen-`antworten_letzte.jsonl` erscheint **nicht**
im Bericht; Repo-`--ziel` → Exit 2; fehlender Ordner + `--holen` → Exit 1) ·
Datenschutz (keine echten Namen in der neuen Datei, kein `sk-`/Bearer/30-Ziffern-
Muster) · kein Netz/kein echtes Gerät.

Kein Netz, kein Kabel, kein echtes Handy: die Attrappe ist ein Bash-Skript im
`tmp_path`. Auf Windows kann ein Bash-Skript nicht direkt gestartet werden
(kein Win32-Programm; gemessen: `WinError 193`) — deshalb legt der Test daneben
einen kleinen `.cmd`-Umweg an, der denselben Bash-Aufruf macht. Auf POSIX wird
das Skript direkt gestartet.

## 3. Prüfbefehl (selbst gefahren, Ausgabe wörtlich)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
3142 passed, 1 skipped, 3 warnings in 170.56s (0:02:50)
```

Exit-Code **0**. Die eine übersprungene Prüfung ist **vorbestehend** und hat mit
diesem Auftrag nichts zu tun: `test_video_gesichter.py` überspringt sich, weil
`cv2` fehlt (`SKIPPED […]: could not import 'cv2': No module named 'cv2'`). Die
neue Testdatei allein: `18 passed in 10.50s` (Exit 0, überspringt nichts).

```
bash -n start-termux.sh      → Exit 0
```

## 4. Was (noch) NICHT belegt ist

**Der erste echte Widget-Tipp am Gerät.** Dieser Lauf hat kein Handy angefasst —
`job_liste.txt` entsteht erst, wenn das Startskript am Handy einmal per
Widget-Tipp läuft. Erst danach kann `python tools/handy/diag_holen.py --holen`
sagen, ob `JOB_ID_GEFUNDEN=ja` und damit `job_1901_belegt=ja` herauskommt. Bis
dahin ist der Belegweg gebaut und getestet, aber **nicht** geschlossen.

## 5. Grenzen, die eingehalten wurden

Kein git-Befehl. Nur die vier genannten Dateien angefasst; in `start-termux.sh`
wurde ausschließlich eingefügt (43 Zeilen), keine bestehende Zeile umformuliert
oder gelöscht. Kein `.env`, keine Geheimnisse, keine echten Personen-/Orts-/
Ereignisnamen, keine Fotos, kein Chat-Archiv, kein pCloud. Alle Tests laufen
offline; kein echtes Gerät, kein `adb` am Gerät.

## 6. Messung des Planers (nur lesend, gleiche Runde)

Damit der Belegweg nicht nur gebaut, sondern einmal **wirklich** gelaufen ist,
hat der Planer das neue Werkzeug am hängenden Kabel selbst gestartet:

```
python tools/handy/diag_holen.py
  → Ordner auf dem Geraet nicht vorhanden: /sdcard/Download/hermes_diag
  → adb.exe: no devices/emulators found            Exit 0
```

Zwei ehrliche Befunde daraus: (1) `hermes_diag/` fehlt am Gerät weiterhin — seit
dem Bau von N23/N29b hat **kein** Widget-Tipp stattgefunden, der Beleg ist also
noch nicht entstanden; (2) das Gerät war zu Beginn dieser Runde am Kabel
(`adb devices` → `ZY22K9RGLQ  device`, vom Planer gemessen) und ist es später
**nicht mehr** (`List of devices attached` ohne Eintrag) — die zweite Messung
lief deshalb ohne Gerät. Das Werkzeug meldet diesen Fall **ehrlich** und endet
mit Exit 0, statt einen Fehler zu erfinden.

## 7. Prüfer-Befund (andere Modellfamilie, frische Sitzung)

`z-ai/glm-5.2` prüfte gegen `docs/auftrag-n24b-belegweg.md`: Prüfbefehl selbst
gefahren, Testfunktionen selbst gezählt, Block gegen die Auftragspunkte geprüft,
`bash -n`, Werkzeug-Trockenlauf und Attrappen-Lauf, Datenschutz (Inhalt privater
Dateien erscheint nicht im Bericht), Geheimnismuster (`sk-`, `Bearer `,
≥ 30 Ziffern) in allen vier Dateien **0 Treffer**. Offen blieb genau **eine**
Beobachtung, als Wortlaut-Abweichung zu Auftragspunkt C.7 geführt und vom
Prüfer selbst als „Schwere gering, kein Datenleck" eingeordnet:
`backend/tests/test_belegweg_handy.py:65` enthält in `VERBOTENE_NAMEN` den
Nutzer-Vornamen, den Systembenutzernamen und einen Gerätenamen — dieselbe Zeile
steht **wortgleich** schon in der abgenommenen Testdatei
`backend/tests/test_nachpflege_job.py:59`. Es ist damit **Bestandsmuster des
Projekts**, keine neu eingeführte Namensnennung: die Liste ist der **Wächter**
selbst und prüft, dass diese Namen in den neuen Dateien **nicht** vorkommen.
Die Liste bleibt deshalb unverändert (sie zu fingieren würde den Wächter
abschwächen); die Einordnung steht im Planjournal.
