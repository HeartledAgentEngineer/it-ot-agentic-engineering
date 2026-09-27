# Changelog 2026-09-27 — Gesichtserkennung am PC (N9b: Brücke Bild → Vektor)

**Schritt:** N9b des Nachtlaufs · **Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`)

Dieser Schritt baut die Brücke von echten Bild-`bytes` zu genau dem
Vektorformat, das `tools/foto_sortierung/personen_cluster.py` (N9a) liest:
je Bild eine Zeile `{"bild_id", "breite", "hoehe", "gesichter": […]}` mit
`bbox` (x, y, w, h), `score` und 128-Wert-`embedding`. Zusätzlich bekommt
`personen_cluster.referenzseiten_bauen(kachel_holen=…)` eine **echte**
pCloud-Kachelquelle (bisher nur Attrappen im Test).

## Neue Dateien (Zeilenzahlen)

| Datei | Zeilen | Inhalt |
|---|---|---|
| `tools/foto_sortierung/gesicht_erkennen.py` | **835** | Modul: Modellpfade, Gesichtsmodell, reine Erkennungsfunktion, Stapel-Lauf, Kachelquelle, Mengen-Übersicht, CLI |
| `backend/tests/test_gesicht_erkennen.py` | **850** | Prüfungen, vollständig offline (kein `cv2`, kein Netz) |
| `docs/changelog-2026-09-27-gesicht-erkennen.md` | diese Datei | Doku |

Bearbeitet wurde **keine** bestehende Datei — `personen_cluster.py` blieb
unverändert.

## Öffentliche Schnittstelle (wie im Auftrag benannt)

* `GesichtFehler(Exception)` — deutsche Klartextmeldungen.
* `modell_pfade(modelle_dir=None) -> dict` — löst die zwei ONNX-Dateien auf
  (Argument → Umgebungsvariable `GESICHT_MODELLE_DIR` → Standard
  `~/foto_sortierung/ml_models`); fehlt eine Datei, kommt `GesichtFehler`
  **mit dem Pfad im Text**.
* `verfuegbar() -> bool` — prüft `cv2` über `importlib.util.find_spec`, **ohne**
  `cv2` zu importieren; das Modul bleibt auch ohne OpenCV importierbar.
* `GesichtsModell` — `gesichter(roh, bild_id="")`, `version()`; `cv2`/ONNX
  werden **erst in `_laden()`** geladen (lazy).
* `gesichter_mit_detektor(roh, detektor, rekognizer, bild_id="", breite=None,
  hoehe=None)` — reine Funktion mit **eingestecktem** Detektor/Rekognizer; die
  EXIF-Orientierung wird über `backend/face_infer.orientiere_bild` /
  `exif_orientierung` **wiederverwendet**, nicht nachgebaut.
* `vektoren_fuer_stapel(bilder, modell, max_bilder=None, abbruch=None)` —
  Iterator mit Zählern unter `.zaehler` (`bilder_gesamt`, `bilder_geholt`,
  `bilder_ohne_gesicht`, `fehler`, `sekunden`, `loecher`); eine
  `hole_funktion()` wird erst beim Verarbeiten des jeweiligen Bildes gerufen.
* `kachel_quelle(service, max_bytes=…, groesse=None)` — gibt
  `kachel_holen(eintrag) -> bytes | None` zurück; `service` ist nur über
  `datei_bytes(fileid, max_bytes)` angekoppelt (Duck-Typing). Fehler/leere
  Antwort → `None` (Platzhalter greift), **nie** ein Abbruch.
* `massen_uebersicht(zeilen, katalog=None) -> dict` — belegt die Mengen-Regel
  über die erzeugten Vektorzeilen anhand von `personen_cluster.bild_entscheidung`.
* `main(argv=None) -> int` — CLI; **Standard ist der Trockenlauf**.

## Prüfbefehl (selbst ausgeführt)

```
cd "C:/Users/sebas/Desktop/workspace agentic engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend"
.venv/Scripts/python.exe -m pytest tests/ -q
```

**Ergebnis:** `1175 passed, 3 warnings in 81.79s` — **Exit 0**.

* Baseline vor diesem Schritt: **1095 passed**.
* Neu: **80 Tests** in `tests/test_gesicht_erkennen.py` (alle grün).
* Die 3 Warnungen stammen aus Fremdbibliotheken (`starlette`, `pydantic`) und
  sind unverändert gegenüber der Baseline.

Die neuen Tests laufen im **Projekt-venv ohne `cv2`** — mit Attrappen-Detektor
und Attrappen-Rekognizer, ohne Netz, Dateien nur unter `tmp_path`.

## Gemessene Umgebungen

* **Projekt-venv** (`backend/.venv`): kein `cv2` → `verfuegbar()` ist `False`;
  `GesichtsModell.gesichter()` liefert das Feld `fehler` **ohne** Absturz.
  Ein AST-Test belegt, dass das Modul `cv2` **nicht** beim Import lädt.
* **OpenCV-venv** (`~/foto_sortierung/venv_gesicht`), echter Lauf:
  * `cv2` beim Modul-Import geladen: **False** (lazy bestätigt),
  * `verfuegbar(): True`,
  * `modell_pfade()` löst beide Dateien auf,
  * `GesichtsModell().version(): 5.0.0`,
  * `gesichter(b'kein bild')` → Feld `fehler` gesetzt, Gesichtsliste leer,
    **kein** Absturz. Es wurde **kein** echtes Foto und **keine** pCloud
    berührt.

## Trockenlauf der CLI (Ergebnis)

Aufruf mit einem erfundenen Plan (3 Züge) im Scratch-Ordner:

```
backend/.venv/Scripts/python.exe tools/foto_sortierung/gesicht_erkennen.py \
    --plan <scratch>/n9b_plan.json --jahr 2020 --max-bilder 24 \
    --vektoren <scratch>/n9b_vektoren.jsonl
```

Ausgabe (Exit 0):

```
Gesichtserkennung N9b — Trockenlauf (es wird NICHTS geholt und NICHTS geschrieben)
Plan: 3 Bild(er)   Auswahl: 2 Bild(er)
gefiltert auf das Jahr 2020
Vektorzeilen-Ziel: <scratch>/n9b_vektoren.jsonl
  2020: 2 Bild(er)
Ohne --schreiben wurde NICHTS geholt und NICHTS geschrieben.
```

Der Trockenlauf hat **kein** Download und **kein** Schreiben ausgelöst — die
Vektorzeilen-Datei entstand nicht (Vergleich der Dateiliste im Scratch-Ordner).

## Harte Regeln — belegt

* **Bilder nie gespeichert:** nur die Vektorzeilen-Datei wird geschrieben (Text,
  UTF-8). Ein Test vergleicht die Dateiliste vor/nach einem Lauf.
* **Kein Löschen:** Quelltext-Prüfung auf `os.remove`/`unlink`/`deletefile`/
  `deletefolder`/`rmtree` findet nichts.
* **Kein Repo-Schreibzugriff:** ein Ziel im Repo ergibt eine deutsche Meldung
  und `SystemExit(2)` — geprüft **vor** jedem Download; geschrieben wird nichts.
* **Keine Geheimnisse:** kein Zugangsdaten-Wort im Modul, in Tests oder Doku;
  die pCloud-Quelle ist eingesteckt.
* **Keine echten Namen/Pfade in der Ausgabe:** `bild_id` ist die `fileid` als
  Zeichenkette; die CLI druckt nur Zahlen.

## Echte Messung am Bestand (Planer, nach dem Bau — `~/foto_sortierung/n9b_messung.py`)

Gefahren mit `venv_gesicht`, **nur lesend** gegen pCloud; Originale ausschließlich
im Arbeitsspeicher, nichts davon auf Platte:

* **Stichprobe A:** 16 Bilder aus dem Jahr 2020 (über das Jahr verteilt),
  **Stichprobe B:** 8 Bilder aus dem bilderstärksten Anlass mit Mengen-Thema
  (`Konzert und Buehne`, 54 Bilder) — zusammen **24 Bilder, 0 Fehler, 88,4 s**
  (inklusive Download).
* **Erkennung:** **72 Gesichter** auf **19 von 24** Bildern (5 ohne Gesicht);
  kleinstes Gesicht **16×22 px**, größtes **521×603 px**; **30** Gesichter
  ≥ 0,5 % Flächenanteil (erkennbar), **21** unter 0,05 %, **21** dazwischen.
* **Verfahren N9a auf den echten Vektoren** (`lauf_rechnen`, ohne Katalog):
  `leer 8 · gruppe 12 · menge 0 · unklar 4`; **12 Bilder geclustert**,
  **2 Gruppen** (Größen **6** und **40**), 2 neue Kennungen, 0 bekannte Personen.
* **Referenzseiten mit echten Bilddaten:** **6 Seiten** (`Person_001_seite_01`,
  `Person_002_seite_01…05`, 59–102 KB) nach `~/foto_sortierung/personen_echt/`;
  die Kacheln sind echte Gesichtsausschnitte (der Messlauf schneidet den
  Ausschnitt vor dem Übergeben zu — in-memory, `cv2.imencode`).
  **Zweiter Lauf: 0 neue Dateien** (Idempotenz am echten Bestand belegt).
* **Vektorzeilen:** `~/foto_sortierung/personen_vektoren.jsonl`, **221.698 Bytes,
  24 Zeilen** — genau das Eingabeformat von N9a.
* **Kennungs-Altbestand** geschrieben: `~/foto_sortierung/personen_kennungen.json`.

### Befund, der notiert bleiben muss (ehrlich, ohne Beschönigung)

Die **Mengen-Regel greift**, aber auf einem anderen Zweig als im N9a-Test:
die Gesichter der beiden Konzert-Fotos liegen **unter** `ANTEIL_MIN` (0,05 % der
Bildfläche, winzige Gesichter weit weg) und werden deshalb als `leer` gezählt,
**nicht** als `menge`. Das Ergebnis ist dasselbe und das gewollte — diese Bilder
werden **nicht** geclustert und **nicht** angelernt — aber der Zweig `menge` ist
am echten Foto **nicht** erreicht worden. `ANTEIL_MIN` (und damit die N9a-Tests)
werden in diesem Schritt **nicht** angetastet; das ist ein eigener Schritt mit
eigener Messung (Kandidat **N9c**).

**Zweiter offener Punkt:** die ausgelieferte `kachel_quelle` gibt die **ganzen**
Fotobytes zurück; `referenzseiten_bauen` verkleinert sie dann als Ganzes. Der
Messlauf hat deshalb zusätzlich zugeschnitten. Für die Personenstufe wäre der
Zuschnitt (Ausschnitt um die `bbox`, in-memory) die bessere Kachel — ebenfalls
N9c-Kandidat, nicht in diesem Schritt geändert.

## Was der Ausführer NICHT geprüft hat

* Kein echter pCloud-Download, kein echtes Foto, keine echte Detektion — das hat
  der Planer mit der Messung oben nachgeholt (`kachel_quelle` selbst ist nur
  gegen einen Attrappen-Dienst geprüft).
* Kein `--schreiben`-Lauf der CLI (bräuchte einen echten pCloud-Dienst); die
  Schreiblogik ist über `vektoren_schreiben`/`vektoren_fuer_stapel` mit
  Attrappen geprüft.
* **Keine Cluster-Qualität gegen Wahrheit** mit echten Vektoren (es gibt keine
  bekannte Wahrheit über die 72 echten Gesichter; N9a hat das synthetisch belegt).

## Umgebung (gemessen, für die Wiederholung)

| Was | Wert |
|---|---|
| venv | `~/foto_sortierung/venv_gesicht` (Python 3.12.10) — **Projekt-venv unberührt** |
| Pakete | `opencv-contrib-python 5.0.0.93`, `onnxruntime 1.30.0`, `numpy 2.5.3`, `Pillow 12.3.0`, `httpx`, `pydantic-settings` |
| Modelle | `~/foto_sortierung/ml_models/face_detection_yunet_2023mar.onnx` (232.589 B), `face_recognition_sface_2021dec.onnx` (38.696.353 B) — öffentlich aus dem OpenCV-Zoo, **nicht** ins Repo |
| Funktionsnachweis | öffentliches Testbild 512×512 → 1 Gesicht, bbox `[207.8, 182.5, 145.9, 206.9]`, score 0.909, Embedding `(1,128)` |

