# Feinauftrag N24c — Belegstand beim Rundenstart (PC-Werkzeug, nur lesend)

> Planer: Hauptkontext · Ausführer: Hermes-Subagent (`deepseek-v4.1-flash`) ·
> Prüfer: andere Modellfamilie · Stand 29.09.2026

## Warum (Kandidat aus der N24b-Messung)

N24b hat den **Belegweg** gebaut: `start-termux.sh` schreibt beim Widget-Tipp
`$DIAG/job_liste.txt` (`JOB_ID_ERWARTET=1901`, `JOB_ID_GEFUNDEN=ja|nein|unbekannt`
plus rohe `termux-job-scheduler --list`-Ausgabe) in den freigegebenen
Download-Ordner; `tools/handy/diag_holen.py` holt ihn per Kabel und meldet
`job_1901_belegt=ja|nein|unbekannt`.

**Die Lücke:** ob dieser Beleg vorliegt, muss der Planer derzeit **per Hand**
herausfinden — Kabel prüfen, `diag_holen.py` starten, Ordner ansehen. Damit
bleibt die Zeile „ist die Job-Kennung 1901 am Handy wirklich registriert?"
zwischen den Runden liegen. Gesucht ist **ein Befehl**, der am Rundenstart in
**einer Zeile** den Belegstand meldet — ohne den Plan anzufassen (der Plan ist
geteilte Datei, ein zweiter Agent arbeitet im selben Arbeitsbaum).

## Auftrag: neues Werkzeug `tools/handy/belegstand.py`

**Nur Standardbibliothek.** Nur **lesend** über `adb` (kein `adb push`, kein
`adb shell` mit Schreibbefehl, kein `rm`, kein `--force`, kein `curl`/`wget`,
kein HTTP, kein pCloud, kein LLM). Kein Schreiben ins Repo.

### Kernstück: reine Funktionen (ohne Gerät, ohne Netz testbar)

1. `spiegel_lesen(ordner: str) -> dict`
   Liest den **lokalen Spiegel** (`~/foto_sortierung/handy_diag`, also den
   Ablageort von `diag_holen.py`) **nur lesend** und gibt zurück:
   `{"vorhanden": bool, "dateien": [{"name", "groesse"}, ...],
     "job_liste_vorhanden": bool}`.
   Fehlender Ordner ist **kein Fehler** (`vorhanden=False`), kein Werfen.

2. `letzter_tipp(job_liste_inhalt: str) -> str`
   Liest die **erste** Kopfzeile des Beleg-Berichts der Form
   `beleg job-liste <ISO-Zeit>` und gibt den Zeitstempel zurück, sonst `""`.
   **Nicht raten:** passt das Muster nicht, kommt der leere Text.

3. `belegstand(...) -> dict`
   Führt Geräte-Lage, Spiegel und Job-Beleg zusammen und gibt **immer dieselben
   Felder** zurück:
   `{"geraet": "verbunden"|"geraet_ordner_fehlt"|"kein_geraet"|"unbekannt",
     "device_ordner": "<Pfad>", "device_dateien": <int>,
     "spiegel": "vorhanden"|"nicht_vorhanden",
     "job_liste": "vorhanden"|"fehlt",
     "job_1901_belegt": "ja"|"nein"|"unbekannt",
     "letzter_tipp": "<ISO>"|"",
     "fehler": <None|str>}`

   **Nachtrag des Planers (29.09., während der Umsetzung):** die drei Zustände
   `verbunden`/`kein_geraet`/`unbekannt` reichen **nicht** aus — „Gerät hängt am
   Kabel, aber `hermes_diag/` gibt es noch nicht" (genau der Zustand direkt nach
   dem Bau von N24b) und „kein Gerät am Kabel" sehen sonst gleich aus, und die
   Journal-Zeile würde in einem der beiden Fälle **falsch** lauten. Deshalb
   vierter Wert **`geraet_ordner_fehlt`**, unterschieden an der **rohen**
   `adb`-Ausgabe (die `dateiliste` aus `diag_holen.py` liefert sie als `roh`):
   nennt sie einen fehlenden Gerätebestand („no devices"/„device not found"),
   ist es `kein_geraet`; ist es „No such file" o. Ä. (Ordner fehlt), ist es
   `geraet_ordner_fehlt`; sonst `unbekannt`. Die Regel wird getestet.

   Die Job-Lage wird **nicht neu erfunden**, sondern über die bestehende
   Funktion `job_beleg_deuten` aus `tools/handy/diag_holen.py` bestimmt
   (**eine Quelle**, kein Duplikat). `spiegel_lesen`/`letzter_tipp` dürfen
   werfen — `belegstand` fängt es und schreibt den Grund nach `fehler`.

4. `journal_zeile(stand: dict) -> str` — **reine Funktion**, genau **eine**
   Zeile, deutsch, ohne Personennamen und ohne Geräte-IP, Form:
   `Belegstand <TT.MM.JJJJ>: Geraet=verbunden | Spiegel=vorhanden | job_1901_belegt=ja`
   (bei fehlender Angabe entsprechend `kein_geraet` / `nicht_vorhanden` /
   `unbekannt`). Diese Zeile ist zum **Kopieren in den Plan** gedacht — das
   Werkzeug schreibt sie **nicht** selbst in den Plan.

5. `merken(pfad: str, zeile: str) -> bool` — **einzige Schreibstelle** des
   Werkzeugs, nur außerhalb des Repos, nur mit `--merken`: hängt die Zeile an
   `~/foto_sortierung/belegstand.jsonl` an. **Idempotent:** ist die **letzte**
   Zeile der Datei schon gleich, wird **nichts** geschrieben (Rückgabe `False`).

### Kommandozeile

```
python tools/handy/belegstand.py              # Gerät fragen + Spiegel lesen, nichts schreiben
python tools/handy/belegstand.py --ohne-kabel # nur den lokalen Spiegel lesen (kein adb)
python tools/handy/belegstand.py --merken     # Zeile zusätzlich in belegstand.jsonl (idempotent)
python tools/handy/belegstand.py --adb /pfad/zur/attrappe-adb   # für Tests
```

* `--ordner` (Standard `/sdcard/Download/hermes_diag`),
  `--spiegel` (Standard `~/foto_sortierung/handy_diag`),
  `--adb` (Standard `adb`), `--ohne-kabel`, `--merken`.
* **Exit 0 = Aussage erzeugt** — auch bei `kein_geraet`, `nicht_vorhanden`,
  `job_1901_belegt=unbekannt` (das ist das **Ergebnis**, kein Programmfehler).
* **Exit 2** = Aufruf-/Schutzfehler (z. B. `--spiegel` liegt **im Repo**).
  Schutzprüfung wie in `diag_holen.py` (`_im_repo`).
* Ausgabe am Ende **genau die Journal-Zeile** als letzte Zeile (eine Zeile,
  damit sie direkt übernommen werden kann).

### Tests — `backend/tests/test_belegstand_handy.py` (neu, offline)

Alles ohne Netz, ohne Kabel, mit **Attrappen-`adb`** (kleines Bash-Skript in
`tmp_path`, Muster aus `test_belegweg_handy.py`). Mindestens:

1. `spiegel_lesen` ohne Ordner → `vorhanden False`, kein Werfen.
2. `spiegel_lesen` mit zwei erfundenen Dateien → Namen und Größen stimmen.
3. `letzter_tipp`: gültige Kopfzeile → ISO-Text; fehlende/falsche Kopfzeile → `""`.
4. `belegstand` ohne Gerät (Attrappe meldet `no devices`) → `geraet="kein_geraet"`,
   `job_1901_belegt="unbekannt"`, `fehler is None`, **kein Werfen**.
5. `belegstand` mit Attrappen-Gerät + Spiegel mit `JOB_ID_GEFUNDEN=ja` → `"ja"`,
   mit `=nein` → `"nein"`, ohne die Zeile → `"unbekannt"`.
6. `journal_zeile` ist **eine** Zeile, enthält alle drei Felder, ändert sich bei
   fehlender Angabe wie beschrieben.
7. `merken`: erster Aufruf schreibt, **zweiter gleicher Aufruf schreibt nicht**
   (Idempotenz, Datei-Inhalt byte-gleich), andere Zeile schreibt.
8. CLI: `--spiegel` **im Repo** → Exit 2, nichts geschrieben; `--ohne-kabel`
   ruft `adb` **nie** auf (Attrappe, die bei Aufruf eine Markierungsdatei legt:
   Datei bleibt aus); letzte Ausgabezeile ist die Journal-Zeile.
9. **Datenschutz/Wächter:** Quelltext enthält keine Löschfunktion
   (`os.remove`, `os.rmdir`, `shutil.rmtree`, `unlink`), kein `rm `, kein
   `--force`, kein HTTP (`urllib`, `requests`, `socket`), kein pCloud; das
   Werkzeug schreibt **nur** nach `--merken` und **nie** ins Repo.
10. Keine echten Namen/Nummern in den neuen Dateien (Liste wie in
    `test_belegweg_handy.py:65` **wortgleich übernehmen** — sie *ist* der
    Wächter).

### Doku (gleicher Commit, „code + docs")

* `docs/changelog-2026-09-29-n24c-belegstand.md` — deutsch, mit Zahlen
  (Zeilen des Werkzeugs, Zahl der Testfunktionen, Prüfbefehl-Ergebnis,
  Live-Lauf-Ausgabe) — **keine** Zahlen behaupten, die nicht gemessen wurden.
* **Kein Frontend → kein Cache-Bump.**

## Prüfkriterien (der Prüfer fährt sie selbst)

1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0**;
   die neue Datei allein grün; Zahl der neuen Testfunktionen stimmt mit der
   Doku überein.
2. `python tools/handy/belegstand.py` läuft **ohne Gerät** durch, Exit 0, letzte
   Zeile ist die Journal-Zeile (kein Fehler, kein Werfen).
3. Zweiter `--merken`-Lauf schreibt **nichts** (Idempotenz belegt).
4. Keine Lösch-/Netz-/Schreibfunktion im Werkzeug außer `--merken` außerhalb
   des Repos; 0 Treffer im Datenschutz-Scan.
5. Doku ↔ Code ohne Widerspruch.
