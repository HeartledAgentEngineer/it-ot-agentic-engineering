# Feinauftrag N9b — echte Gesichtserkennung am PC (Brücke Bild → Vektor)

**Planer:** Hauptagent (`deepseek-v4.1-flash`) · **Ausführer:** Hermes-Subagent
(`deepseek-v4.1-flash`) · **Prüfer:** frischer Kontext, **andere Familie**
(`openai/gpt-5.6-luna`).

**Vorgeschichte:** N9a (`tools/foto_sortierung/personen_cluster.py`) rechnet nur
auf **Vektoren**. N9b liefert die Vektoren — aus echten Bildern.

## Umgebung (bereits eingerichtet, gemessen — nicht neu bauen)

* **Eigenes venv** (Projekt-venv bleibt unberührt!):
  `C:/Users/sebas/foto_sortierung/venv_gesicht/Scripts/python.exe`
  → `opencv-contrib-python 5.0.0.93`, `onnxruntime 1.30.0`, `numpy 2.5.3`.
* **Modelle** (öffentlich, OpenCV Zoo, heruntergeladen):
  `C:/Users/sebas/foto_sortierung/ml_models/face_detection_yunet_2023mar.onnx` (232.589 B),
  `C:/Users/sebas/foto_sortierung/ml_models/face_recognition_sface_2021dec.onnx` (38.696.353 B).
* **Funktionsnachweis** (gefahren): 512×512-Testbild → 1 Gesicht, bbox
  `[207.8, 182.5, 145.9, 206.9]`, score 0.909, Embedding `(1, 128)`, Norm 2.3436.
* **Das Projekt-venv hat bewusst KEIN `cv2`/`onnxruntime`** — Modul und Tests
  müssen ohne sie importierbar bleiben (lazy import, genau wie `backend/face_infer.py`).

## Auftrag

Neu: **`tools/foto_sortierung/gesicht_erkennen.py`** — die Brücke von Bild-Bytes
zu genau dem Vektorformat, das `personen_cluster.py` liest. Dazu Tests
`backend/tests/test_gesicht_erkennen.py` und eine Changelog-Doku.

Zusätzlich **neu anstecken:** `personen_cluster.referenzseiten_bauen(kachel_holen=…)`
bekommt eine **echte** pCloud-Kachelquelle (bisher nur Attrappen im Test).

### Verlangte öffentliche Schnittstelle (Namen bitte genau so)

1. `GesichtFehler(Exception)` — deutsche Klartextmeldungen.
2. `modell_pfade(modelle_dir=None) -> dict` — löst die zwei Modelldateien auf
   (Standard `~/foto_sortierung/ml_models`); fehlt eine Datei → `GesichtFehler`
   mit Pfad im Text. `modelle_dir` auch über Argument/Umgebungsvariable setzbar.
3. `verfuegbar() -> bool` — sagt, ob `cv2` importierbar und die Modelle da sind.
   **Darf `cv2` NICHT beim Import des Moduls laden.**
4. `klasse GesichtsModell`:
   * `__init__(self, modelle_dir=None, score_schwelle=0.6, nms_schwelle=0.3, topk=5000)`
   * `gesichter(self, roh: bytes, bild_id: str = "") -> dict`
     → `{"bild_id":…, "breite": w, "hoehe": h, "gesichter": [ {"bbox":[x,y,w,h],
        "score": float, "landm": [[x,y]×5], "embedding": [128 floats]} ]}`
     * leere Liste, wenn kein Gesicht/Gesicht nicht dekodierbar — **kein Absturz**,
       stattdessen Feld `"fehler"` mit deutschem Text.
     * **EXIF-Orientierung** identisch zur Anzeige: `backend.face_infer.orientiere_bild`
       bzw. `exif_orientierung` **wiederverwenden** (die sind numpy-only und ohne cv2
       importierbar) — nicht nachbauen.
   * `version(self) -> str` (cv2-Version, ohne Modellwerte).
5. `gesichter_mit_detektor(roh, detektor, rekognizer, bild_id="", breite=None, hoehe=None) -> dict`
   — **reine Funktion**: bekommt Detektor/Rekognizer **eingesteckt** (jedes Objekt
   mit `setInputSize`/`detect` bzw. `alignCrop`/`feature`). So sind die Tests
   vollständig offline ohne cv2. `GesichtsModell.gesichter` ruft sie auf.
6. `vektoren_fuer_stapel(bilder, modell, max_bilder=None, abbruch=None) -> iterator/dict`
   — `bilder` ist eine Folge `(bild_id, hole_funktion)` oder `(bild_id, bytes)`;
   `hole_funktion()` wird **erst beim Verarbeiten** gerufen (billigster Weg zuerst).
   Rückgabe/Iterator mit **genau einer Zeile je Bild** in der Form, die
   `personen_cluster` liest (siehe dessen Modulkopf):
   `{"bild_id","breite","hoehe","gesichter":[…]}`.
   Zähler: `bilder_gesamt`, `bilder_geholt`, `bilder_ohne_gesicht`, `fehler`,
   `sekunden`, `loecher` (fehlende bytes → gezählt, nicht geraten).
7. `kachel_quelle(service, max_bytes=…, groesse=None)` — gibt eine Funktion
   `kachel_holen(eintrag) -> bytes | None` zurück, die für einen Eintrag mit
   `fileid` **in-memory** die Bytes über `service.datei_bytes(fileid, max_bytes)`
   holt. `service` ist **eingesteckt** (nur Attribut `datei_bytes` nötig) —
   kein Token, keine Konfiguration im Modul. Fehler/leere Antwort → `None`
   (der Platzhalter von `referenzseiten_bauen` greift), **nie** ein Abbruch.
8. `massen_uebersicht(zeilen, katalog=None) -> dict` — zählt über die erzeugten
   Vektorzeilen, wie viele Bilder `personen_cluster.bild_entscheidung` als
   `clustern: False` (Menge) einstuft. Damit ist die Mengen-Regel am **echten**
   Bild belegbar.
9. `main(argv=None) -> int` — CLI:
   * `--plan ~/foto_sortierung/sortierplan.json` (Quelle: Feld `zuege[].fileid`
     und `zuege[].jahr`; **lesend**), `--jahr 2020`, `--max-bilder 24`,
     `--je-jahr N`, `--vektoren ~/foto_sortierung/personen_vektoren.jsonl`.
   * **Standard ist Trockenlauf:** nur zählen/auflisten, was geholt würde —
     **kein** Download. Erst `--schreiben` holt wirklich (in-memory) und schreibt
     die Vektorzeilen.
   * Ausgabe: deutsche Klartextzeilen mit den Zahlen; **keine** Tokens, keine
     echten Ordnernamen, kein Bildinhalt.

### Harte Regeln (Tests prüfen die Abwesenheit)

* **Bilder werden NIE gespeichert.** Kein `open(…, "wb")`, kein `tofile`, kein
  Temp-Bild, kein Schreiben von Bytes außer den **Vektorzeilen** (JSONL, Text).
  Ein Test prüft: Lauf mit erfundenen Bytes legt außer der Vektor-Datei
  **keine** neue Datei an (Vergleich der Dateiliste vor/nach).
* **Kein Löschen.** Keine `deletefile`/`deletefolder`/`os.remove`/`unlink`-Aufrufe
  im Modul (Test über den Quelltext).
* **Kein Repo-Schreibzugriff:** Zielpfad im Repo → deutsche Meldung + `SystemExit(2)`,
  geschrieben wird nichts (wie `personen_cluster.py`).
* **Keine Namen, keine Pfade in der Ausgabe:** `bild_id` ist die `fileid` als
  Zeichenkette. Ordnernamen, Personen-, Orts- und Ereignisnamen kommen **nicht**
  vor — weder in Code, Tests noch Doku.
* **Keine Geheimnisse:** kein Token lesen, ausgeben oder speichern.

### Prüfbefehl (selbst ausführen, Ausgabe + Exit-Code melden)

```
cd "C:/Users/sebas/Desktop/workspace agentic engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend"
.venv/Scripts/python.exe -m pytest tests/ -q
```

Baseline vor diesem Schritt: **1095 passed**. Erwartet: **> 1095, Exit 0**.
Wichtig: die neuen Tests laufen **im Projekt-venv ohne cv2** — also mit
eingestecktem Attrappen-Detektor, kein Netz, `tmp_path`.

Optionaler eigener Nachweis (darf, muss nicht): mit
`C:/Users/sebas/foto_sortierung/venv_gesicht/Scripts/python.exe` das Modul auf
einem **öffentlichen** Testbild aufrufen (lena.jpg o. ä. ist erlaubt) — **kein**
Foto aus dem Bestand, kein pCloud-Aufruf.

### Rückmeldung an den Planer (kurz, mit Zahlen)

Dateien + Zeilenzahlen, Anzahl neuer Tests, Prüfbefehl-Ausgabe + Exit-Code,
was im Trockenlauf der CLI herauskam, alles was du **nicht** geprüft hast.
