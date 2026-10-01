# Änderungsprotokoll 01.10.2026 — Personen benennen im Gruppenmodus (Plan Foto-Gedächtnis Schritt 2)

Plan: `C:\Users\sebas\.claude\plans\dapper-roaming-rose.md`, Schritt 2. Vorgänger: Schritt 1
`personen_gruppieren.py` (Commit 7e5f49b) fasst am PC alle Gesichter zu Gruppen zusammen.
Bisher fragte das Gesichter-Quiz Bild für Bild — bei ~30.000 Gesichtern undurchführbar.

## 2a — Backend + Übergabe im echten App-Startweg

- **`backend/app/services/gruppen_quiz.py`** (neu): größte offene Gruppe zuerst; Antworten
  `name` · `gleich`/`verschieden` (Zwillings-Kandidat) · `spaeter` (kommt zum Schluss wieder) ·
  `unbekannt` (nie mehr gefragt) · `rueckgaengig()` (letzte Antwort zurück, auch mehrfach).
  Ablage **genau im Format, das `personen_gruppieren.py` liest** (`bestaetigt_lesen`,
  `vorgaben_lesen`): `personen_bestaetigt.json` `{"bestaetigt": {Kennung: Name}}`,
  `personen_vorgaben.json` `{"gleich": [[a,b]], "verschieden": [[a,b]]}`; dazu
  `gruppen_quiz_stand.json` (später/unbekannt) und das Protokoll `gruppen_antworten.jsonl` (nur
  anhängend, Grundlage für Rückgängig). Gleicher Name für eine zweite Gruppe (Groß/Klein egal) →
  zusätzlich ein `gleich`-Paar (beim nächsten PC-Lauf zusammengelegt). Vor jedem Schreiben
  `*.vorher`-Sicherung, atomar (temp + `os.replace`), Schreibsperre gegen gleichzeitige Antworten,
  Schreiben in den Projektordner abgelehnt, andere Felder der Namensdatei bleiben erhalten.
  Register `bilder_mit(namen, modus)` über `gesicht_zuordnung.jsonl`: `alle` (und), `eine`
  (oder), `genau` (keine weitere **benannte** Person; unbenannte Gesichter im Hintergrund zählen
  nicht); Videos je `video_id` zusammengefasst, neueste zuerst.
  Ort `~/foto_sortierung` (`GRUPPEN_QUIZ_BASIS`); gelesen wird zuerst `personen_gruppen/<datei>`
  (so schreibt der PC), sonst `<datei>` (so legt die Übergabe am Handy ab). Keine Vektoren, kein
  Netz, kein Modell.
- **`backend/app/router/gruppen.py`** (neu, `/api/gruppen`, mit Schlüssel-Schutz in `main.py`):
  `GET /stand`, `GET /naechste`, `POST /antwort`, `POST /rueckgaengig`,
  `GET /bilder?namen=…&modus=alle|eine|genau&limit=…`; immer HTTP 200 mit `ok`/`fehler`.
- **Übergabe im echten Startweg** (`termux/agent-ensure.sh`): Befund 30.09. — die Übernahme der
  vom PC per Kabel gelegten Dateien stand nur in `start-termux.sh` (Widget); die App startet über
  `agent-ensure.sh` und kam nie dort vorbei. Jetzt dort nach dem Pull und vor dem Serverstart,
  gleiches Werkzeug (`tools/handy/uebergabe_uebernehmen.py`, unverändert), `|| true`. Die
  Dateiliste beider Skripte um `personen_beispiele.json` und `gesicht_zuordnung.jsonl` erweitert
  (Kopfkommentar von `agent-ensure.sh` berichtigt: „keine Datei-Übernahmen" stimmt nicht mehr).

## Prüfung (2a)

- Neu `backend/tests/test_gruppen_quiz.py` — **26 Tests**, offline mit erfundenen Gruppen; die
  Format-Tests lesen die geschriebenen Dateien mit den Lesefunktionen von
  `personen_gruppieren.py` selbst.
- `backend/tests/test_uebergabe_uebernehmen.py`: Wächter-Namen aus den Dienst-Konstanten jetzt
  **7** (+ `gruppen_quiz.BEISPIELE_DATEINAME`/`ZUORDNUNG_DATEINAME`); neu zwei Wächter für
  `agent-ensure.sh` (beide Aufrufe mit voller Liste; Übernahme nach dem Pull, vor `uvicorn`,
  jeder Aufruf endet auf `|| true`). `bash -n` auf beiden Skripten OK.
- Voller Prüfbefehl: siehe Commit.

## Offen

- **2b Oberfläche** (eigene Datei `frontend/gruppen_quiz.js`) — folgt.
- Die Dateien müssen einmal per Kabel in den Download-Ordner des Handys gelegt werden
  (`adb push … /sdcard/Download/`) — das startet Sebastian oder Hermes (persönliche Daten, nicht
  Claude). Danach übernimmt die App sie beim nächsten Start.
- Rückweg Handy → PC für `personen_bestaetigt.json`/`personen_vorgaben.json` (damit der nächste
  Gruppier-Lauf am PC die Namen kennt) — noch kein Werkzeug; vorerst per `adb pull` aus einem
  freigegebenen Ordner oder pCloud.
- Brücke in den `gesichter_katalog.json` (neue Handy-Fotos erkennen die benannte Person) braucht
  ein Merkmal je Gesicht — eigener Schritt.
