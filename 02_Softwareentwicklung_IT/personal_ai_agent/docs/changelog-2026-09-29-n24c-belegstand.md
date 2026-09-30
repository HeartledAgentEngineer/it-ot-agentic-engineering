# Changelog 2026-09-29 — N24c: Belegstand beim Rundenstart in einer Zeile

Auftrag: `docs/auftrag-n24c-belegstand.md`. Gebaut von einem Hermes-Subagenten.
Nur drei Dateien angefasst, kein Frontend, **kein Cache-Bump**, kein git-Befehl.

## 1. Warum (die Lücke aus N24b)

N24b hat den **Belegweg** gebaut: `start-termux.sh` schreibt beim Widget-Tipp
`hermes_diag/job_liste.txt` (`JOB_ID_ERWARTET=1901`, `JOB_ID_GEFUNDEN=ja|nein|unbekannt`
plus rohe `termux-job-scheduler --list`-Ausgabe); `tools/handy/diag_holen.py`
holt ihn per Kabel und meldet `job_1901_belegt=ja|nein|unbekannt`.

Offen blieb: **ob** dieser Beleg vorliegt, musste der Planer per Hand
herausfinden — Kabel prüfen, `diag_holen.py` starten, Ordner ansehen. Die Zeile
„ist die Job-Kennung 1901 am Handy wirklich registriert?“ blieb damit zwischen
den Runden liegen. N24c liefert **einen Befehl**, der am Rundenstart in **einer
Zeile** den Belegstand meldet — ohne den Plan anzufassen (der Plan ist geteilte
Datei, ein zweiter Agent arbeitet im selben Baum).

## 2. Was gebaut wurde

| Datei | Zeilen | Art |
|---|---|---|
| `tools/handy/belegstand.py` | **459** | neu (PC-Werkzeug, nur lesend) |
| `backend/tests/test_belegstand_handy.py` | **440** | neu (**19** Testfunktionen, alles offline) |
| `docs/changelog-2026-09-29-n24c-belegstand.md` | diese Datei | neu (Doku) |

### A) `tools/handy/belegstand.py` (PC-Seite, nur lesend)

Deutscher Modul-Docstring im Stil von `tools/handy/diag_holen.py` (Zweck,
Verhalten, harte Grenzen, Exit-Codes, Aufruf). Kernstück sind **reine,
offline testbare Funktionen**:

- `spiegel_lesen(ordner)` — liest den lokalen Spiegel
  (`~/foto_sortierung/handy_diag`, der Ablageort von `diag_holen.py`) **nur
  lesend** und gibt `{"vorhanden", "dateien": [{"name", "groesse"}, ...],
  "job_liste_vorhanden"}` zurück. Ein fehlender Ordner ist **kein Fehler**
  (`vorhanden=False`), es wird nicht geworfen.
- `letzter_tipp(job_liste_inhalt)` — liest den Zeitstempel der **ersten**
  Kopfzeile der Form `beleg job-liste <ISO-Zeit>`; passt das Muster nicht, kommt
  `""` (es wird **nicht geraten**).
- `geraete_lage(roh)` — **reine Funktion** (Nachtrag des Planers): deutet die
  **rohe** `adb`-Ausgabe (Feld `roh` aus `diag_holen.dateiliste`). „no
  devices“/„device not found“ → `kein_geraet`; „No such file“/„does not exist“
  → `geraet_ordner_fehlt` (Gerät am Kabel, aber `hermes_diag/` gibt es noch
  nicht); sonst ehrlich `unbekannt`. Es wird **nicht geraten**.
- `belegstand(adb, ordner, spiegel, ohne_kabel)` — führt Geräte-Lage, Spiegel
  und Job-Beleg zusammen und gibt **immer dieselben Felder** zurück: `geraet`
  (`verbunden`/`geraet_ordner_fehlt`/`kein_geraet`/`unbekannt`), `device_ordner`, `device_dateien`,
  `spiegel` (`vorhanden`/`nicht_vorhanden`), `job_liste`
  (`vorhanden`/`fehlt`), `job_1901_belegt` (`ja`/`nein`/`unbekannt`),
  `letzter_tipp`, `fehler`. Die Job-Lage wird **nicht neu erfunden**, sondern
  über die **bestehende** Funktion `job_beleg_deuten` aus
  `tools/handy/diag_holen.py` bestimmt (eine Quelle, kein Duplikat — das Modul
  wird als Nachbarmodul geladen). `spiegel_lesen`/`letzter_tipp` dürfen werfen;
  `belegstand` fängt es und schreibt den Grund nach `fehler`. Mit
  `ohne_kabel=True` wird `adb` gar nicht aufgerufen.
- `journal_zeile(stand)` — **reine Funktion**, genau **eine** Zeile, deutsch,
  ohne Personennamen und ohne Geräte-IP:
  `Belegstand <TT.MM.JJJJ>: Geraet=<...> | Spiegel=<...> | job_1901_belegt=<...>`.
  Fehlende Angaben werden zu `kein_geraet` / `nicht_vorhanden` / `unbekannt`.
  Zum **Kopieren in den Plan** gedacht — das Werkzeug schreibt sie **nicht**
  selbst in den Plan.
- `merken(pfad, zeile)` — die **einzige Schreibstelle**, nur außerhalb des
  Repos, nur mit `--merken`: hängt die Zeile an
  `~/foto_sortierung/belegstand.jsonl` an. **Idempotent**: ist die **letzte**
  Zeile der Datei schon gleich, wird **nichts** geschrieben (`False`).

CLI: `--ordner` (Standard `/sdcard/Download/hermes_diag`), `--spiegel`
(Standard `~/foto_sortierung/handy_diag`), `--adb` (Standard `adb`, für Tests
durch eine Attrappe ersetzbar), `--ohne-kabel` (nur den lokalen Spiegel lesen),
`--merken`. **Exit 0 = Aussage erzeugt** — auch bei `kein_geraet`,
`nicht_vorhanden`, `unbekannt`; **Exit 2** = Aufruf-/Schutzfehler (`--spiegel`
liegt IM Repo, Schutzprüfung `_im_repo` wie in `diag_holen.py`). Die
**Journal-Zeile ist die letzte Ausgabezeile**.

Grenzen (im Docstring und getestet): nur Standardbibliothek; nur lesend über
`adb`; kein Netz außer dem **lokalen** `adb`-Aufruf; **keine Löschfunktion**
(kein `os.remove`/`os.rmdir`/`shutil.rmtree`/`unlink`); kein `rm`, kein
`--force`; kein HTTP, kein pCloud, kein LLM; Schreiben **nur** nach `--merken`
und **nie** ins Repo.

### B) `backend/tests/test_belegstand_handy.py` (19 Testfunktionen, alles offline)

Kein Netz, kein Kabel, kein echtes Handy: die Attrappen-`adb` ist ein
Bash-Skript unter `tmp_path` (Muster aus `test_belegweg_handy.py`); auf Windows
entsteht daneben ein kleiner `.cmd`-Umweg, der denselben Bash-Aufruf macht (auf
POSIX wird das Skript direkt gestartet). Die Attrappe legt bei **jedem** Aufruf
eine Markierungsdatei `adb-wurde-gerufen` an — damit ist beweisbar, dass
`--ohne-kabel` `adb` **nie** aufruft.

Abgedeckt (Regelgruppen des Auftrags): `spiegel_lesen` ohne Ordner (kein
Werfen) · `spiegel_lesen` mit zwei erfundenen Dateien (Namen/Größen stimmen) ·
`letzter_tipp` gültig/falsch/leer/`None` · `belegstand` ohne Gerät
(`kein_geraet`, `unbekannt`, `fehler is None`, kein Werfen) · `belegstand` mit
Gerät + Spiegel für `ja`/`nein`/fehlende Zeile · Feldmenge immer gleich ·
**Nachtrag:** `geraete_lage`-Regel aus der rohen Ausgabe (drei Zweige: „no
devices“/„no such file“/sonst) · Gerät am Kabel ohne Ordner →
`geraet_ordner_fehlt` (**nicht** `kein_geraet`) · unbrauchbare adb-Meldung →
`unbekannt` ·
`journal_zeile` eine Zeile mit allen drei Feldern, auch bei fehlender Angabe ·
`merken` schreibt, zweiter gleicher Aufruf schreibt **nicht** (Datei-Inhalt
byte-gleich), andere Zeile schreibt, IM Repo → `ValueError` · CLI `--spiegel` im
Repo → Exit 2 (nichts angelegt) · CLI `--ohne-kabel` ruft `adb` nie auf, letzte
Zeile ist die Journal-Zeile · Datenschutz-Wächter im Werkzeug (keine
Lösch-/Netzfunktion, genau **eine** Schreibstelle) · keine echten Namen,
kein `sk-`/Bearer/30-Ziffern-Muster.

Die Wächter-Liste `VERBOTENE_NAMEN` ist **wortgleich** aus
`test_belegweg_handy.py:65` übernommen (sie *ist* der Wächter und prüft, dass
diese Namen in `belegstand.py` **nicht** vorkommen).

## 3. Prüfbefehle (selbst gefahren, Ausgabe wörtlich)

Neue Datei allein:

```
cd backend && .venv/Scripts/python -m pytest tests/test_belegstand_handy.py -q
...................                                                      [100%]
19 passed in 5.52s
```

Gesamtlauf (im Hintergrund, weil er länger als ein Vordergrund-Fenster dauert):

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
3166 passed, 1 skipped, 3 warnings in 184.50s (0:03:04)
```

Exit-Code **0** für beide. Die eine übersprungene Prüfung ist **vorbestehend**
(`test_video_gesichter.py` überspringt sich, weil `cv2` fehlt) und hat mit
diesem Auftrag nichts zu tun. Gegenprobe zur Zahl: die neue Datei allein hat
**19** Testfunktionen grün (siehe oben), der Gesamtlauf **3166**. Die Zunahme
gegenüber der letzten N24c-Messung (3158) ist **+8** — sie lässt sich aber
**nicht** allein diesem Werkzeug zuschreiben, weil der Arbeitsbaum **geteilt**
ist (ein zweiter Agent arbeitet parallel darin); belegt sind die **3** neuen
Testfunktionen durch den Lauf der Datei **allein** (`19 passed`, oben).

## 4. Live-Läufe (echte Geräte-Lage, Ausgabe wörtlich)

Ohne Kabel, nur der lokale Spiegel (kein `adb`):

```
$ python tools/handy/belegstand.py --ohne-kabel
Geraete-Ordner: /sdcard/Download/hermes_diag
Geraet: unbekannt (Dateien im Geraete-Ordner: 0)
Spiegel: nicht_vorhanden (C:\Users\<nutzer>\foto_sortierung\handy_diag)
Job-Liste: fehlt
letzter Tipp: -
Belegstand 29.09.2026: Geraet=unbekannt | Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt
```

Exit 0. Ein zweiter Lauf **ohne** `--ohne-kabel` fragt das Gerät ehrlich:

```
$ python tools/handy/belegstand.py
...
Geraet: kein_geraet (Dateien im Geraete-Ordner: 0)
Belegstand 29.09.2026: Geraet=kein_geraet | Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt
```

Exit 0, **kein** Fehler — `kein_geraet`/`nicht_vorhanden`/`unbekannt` sind das
Ergebnis, kein Programmfehler.

Der **vierte** Wert `geraet_ordner_fehlt` ist hier **nicht** live zu sehen (kein
Gerät am Kabel, kein Ordner): er ist ausschließlich **offline** über die
Attrappen-adb belegt — mit einem Gerät am Kabel, aber fehlendem `hermes_diag/`
(siehe Abschnitt 2B und die Prüfbefehle in Abschnitt 3).

**Idempotenz belegt** (zwei `--merken`-Läufe hintereinander):

```
$ python tools/handy/belegstand.py --ohne-kabel --merken      # erster Lauf
Gemerkt: C:\Users\<nutzer>\foto_sortierung\belegstand.jsonl
Belegstand 29.09.2026: Geraet=unbekannt | Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt

$ python tools/handy/belegstand.py --ohne-kabel --merken      # zweiter Lauf
Nicht gemerkt: die letzte Zeile ist schon gleich (idempotent).
Belegstand 29.09.2026: Geraet=unbekannt | Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt
```

Beide Exit 0; `wc -l` auf `belegstand.jsonl` ergibt nach dem zweiten Lauf
**1 Zeile** (nicht zwei) — der zweite Lauf hat nachweislich nichts geschrieben.

## 5. Was (noch) NICHT belegt ist

**Der echte Beleg selbst.** Der lokale Spiegel
(`~/foto_sortierung/handy_diag`) existierte in dieser Runde **nicht**
(`Spiegel=nicht_vorhanden`) und das Gerät war am Kabel **nicht** ansprechbar
(`kein_geraet`). Solange kein Widget-Tipp am Handy stattgefunden hat, entsteht
kein `job_liste.txt` — bis dahin meldet das Werkzeug ehrlich `unbekannt`, statt
einen Beleg zu erfinden. Diese Runde hat **kein Handy angefasst**.

## 6. Grenzen, die eingehalten wurden

Kein git-Befehl. Nur die **drei** genannten Dateien geschrieben. Kein `.env`,
keine Geheimnisse, keine echten Personen-/Orts-/Ereignisnamen, kein Foto-Archiv,
kein Chat-Archiv, kein pCloud, kein Netz. Alle Tests laufen offline; kein
echtes Gerät, kein `adb`-Schreibbefehl. Die einzige Schreibstelle des Werkzeugs
(`merken`) greift nur nach `--merken` und nur **außerhalb** des Repos.
