# Feinauftrag N9a — Personen-Verfahren (Mengen-Filter, Clustering, Referenzseiten)

> **Rolle:** Planer = Hauptagent. Ausführer = Hermes-Subagent. Prüfer = anderes
> Modell (`openai/gpt-5.6-luna`). Codex ist gesperrt (live geprüft, Kontingent
> bis 15.10.2026) — deshalb Hermes-Subagent.
>
> **Regeln:** `AGENTS.md` („Dauerlauf / Nachtarbeit"), `CLAUDE_EXTENDS.md` §6.6.
> Keine Rückfragen. Nur **reiner Code** an den Ausführer — keine Fotos, keine
> Archive, keine `.env`, keine Vektoren aus dem echten Bestand.

## Warum dieser Zuschnitt

Der Plan verlangt für N9: „Modelle/OpenCV am PC prüfen, Vektoren +
Cluster-Verfahren, unbenannte Gruppen + Referenzseiten — **mit Mengen-Filter**".

**Aufklärung am PC (gemessen, 27.09.):**

| Prüfung | Ergebnis |
|---|---|
| `backend/.venv`: `cv2`, `onnxruntime`, `sklearn`, `insightface` | **fehlen alle** (`ModuleNotFoundError`); vorhanden: `numpy 2.4.6`, `PIL 12.3.0` |
| Modelle `ml_models/face_detection_yunet_2023mar.onnx`, `..._sface_2021dec.onnx` | **nicht im Repo** — Pfad in `backend/face_infer.py` zeigt auf **Termux** (`/data/data/com.termux/...`) |
| Wären `onnxruntime` + `opencv-contrib-python` am PC installierbar? | **ja**: Auflösung in Wegwerf-Umgebung ergab `onnxruntime 1.30.0`, `opencv-contrib-python 5.0.0.93`, `numpy 2.4.6` (kein Herabsetzen nötig) — aber **Modell-Dateien fehlen** |

Daraus folgt die Zweiteilung:

* **N9a (dieser Auftrag): das Verfahren.** Alles, was **kein** Bild braucht:
  Mengen-/Gruppen-Entscheidung, Clustering, stabile Kennungen, Referenzseiten.
  Eingabe sind **Vektoren** im Format, das `backend/face_infer.py` schon liefert
  (YuNet-bbox + 128-dim SFace-Embedding). Damit hängt das Werkzeug **nicht** an
  OpenCV und ist vollständig offline prüfbar.
* **N9b (nächster Schritt): die echte Erkennung.** Modelle auf den PC holen bzw.
  auf dem Handy rechnen lassen, cv2/onnxruntime in **eigenem** venv (das
  Projekt-venv mit 879 grünen Tests wird nicht angefasst), Stichprobe eines
  Jahres messen.

## Eingabe-Format (genau so, wie `face_infer.py op_embed` antwortet)

JSONL, eine Zeile je Bild. Das Werkzeug darf **nur** genau diese Felder erwarten
und muss fehlende/ungültige Zeilen zählen statt abzubrechen:

```json
{"bild_id": "1234567", "breite": 4032, "hoehe": 3024,
 "gesichter": [
   {"bbox": [1200.0, 800.0, 420.0, 420.0], "score": 0.93,
    "embedding": [0.01, -0.2, ... 128 Werte ...]}
 ]}
```

* `bild_id`: pCloud-`fileid` als Zeichenkette (oder ein Hash). **Keine Pfade,
  keine Ordnernamen, keine echten Namen** im Repo.
* `bbox`: `[x, y, w, h]` in **absoluten Pixeln** relativ zum vollen Bild
  (Reihenfolge wie bei YuNet/`face_infer.py`).
* `embedding`: 128 Werte (SFace). Andere Längen → Zeile als ungültig zählen.
* Katalog (optional, für die Vordergrund-Prüfung): JSON
  `{"personen": [{"kennung": "Person_001", "name": null, "vektoren": [[...128...]]}]}`
  — `name: null` ist der Normalfall (unbenannt), ein Name darf vorkommen, wird
  aber **nie** geschrieben.

## Dateien

1. `tools/foto_sortierung/personen_cluster.py` — das Werkzeug (Schätzung: 700–1.100 Zeilen).
2. `backend/tests/test_personen_cluster.py` — Tests, **alles offline** (`tmp_path`,
   kein Netz, keine pCloud, keine echten Namen/Orte), Zielgröße **≥ 60 Testfunktionen**.
3. `docs/changelog-2026-09-27-personen-verfahren.md` — Changelog mit Zahlen.

## Verbindliche Regeln aus dem Projekt (nicht verhandelbar)

* **Menschenmengen** (viele Gesichter, weit weg, nicht erkennbar): **kein**
  Clustering, **keine** Referenzseite, **kein** Anlernen. Nur thematisch
  sortieren (das macht `foto_sortieren.py` schon).
* **Vordergrund-Prüfung bei Mengen:** ist im Vordergrund eine **bekannte**
  Person (Katalog) → dem Menschen zuordnen (normales Foto), sonst weglassen.
* **Schwelle statt Gefühl:** „Menge oder Gruppe" entscheidet **der Code** über
  Gesichtsgröße (Anteil der Bildfläche) und Anzahl der Gesichter — alle
  Schwellen als benannte Konstanten **im Modul**, nicht im Aufrufer.
* **Unbenannt zuerst:** Kennungen `Person_001`… — kein Name ohne Sebastians
  Bestätigung. Kennung bleibt stabil, wenn später ein Name dazukommt.
* **Biometrie bleibt lokal:** Vektoren/Katalog/Referenzseiten **nie** ins Repo,
  **nie** an ein Fremd-LLM. Schreiben des Werkzeugs nur **außerhalb** des Repos
  (Repo-Schreibversuch → Fehler, wie in `foto_sortieren.py`).
* **Keine Löschfunktion** — im Quelltext nicht vorhanden (Test prüft die
  Abwesenheit). Kein pCloud-Aufruf im Modul (Test prüft die Abwesenheit).

## Verlangte reine Funktionen (Namen sind Vorgabe, Signatur frei wählbar)

1. `gesichts_anteil(bbox, breite, hoehe) -> float` — Gesichtsfläche /
   Bildfläche; ungültige Werte (0, negativ, nicht numerisch) → `0.0`.
2. `bild_art(gesichter, breite, hoehe, params) -> "leer" | "gruppe" | "menge" | "unklar"`
   mit `MENGEN_PARAMS` als benannte Konstanten, Vorschlag:
   * nutzbar = `score >= MIN_SCORE (0.6, wie face_infer.py)` **und**
     `gesichts_anteil >= ANTEIL_MIN (0.0005)` — Staub ist kein Gesicht;
   * `erkennbar` = `gesichts_anteil >= ANTEIL_ERKENNBAR (0.005)` = 0,5 % der Bildfläche;
   * `leer` = keine nutzbaren Gesichter;
   * `gruppe` = mindestens `1` **erkennbares** Gesicht;
   * `menge` = `anzahl >= MENGE_ANZAHL (6)` nutzbare Gesichter **und kein**
     erkennbares;
   * `unklar` = alles andere (z. B. 3 kleine Gesichter) → **wird nicht geclustert**
     (Regel: im Zweifel weglassen, nichts anlernen).
   Die Konstanten und ihre Herkunft (Bildfläche-Anteil statt Pixelzahl, damit es
   für 12-MP-Handyfotos und Scans gilt) im Docstring begründen.
3. `vordergrund_gesichter(gesichter, breite, hoehe, params) -> list` — die
   **erkennbaren** Gesichter, absteigend nach Flächenanteil (das ist die
   „Vordergrund"-Definition der Regel: erkennbar groß).
4. `katalog_treffer(gesichter, katalog, schwelle) -> list[{"kennung","name","score"}]`
   — Cosinus-Ähnlichkeit gegen die Katalog-Vektoren; Standard-Schwelle als
   benannte Konstante `KATALOG_SCHWELLE` (SFace-Cosinus, Vorschlag **0.363**, im
   Docstring als OpenCV-Standardwert benennen). Mehrere Vektoren je Person →
   bester Treffer zählt. Am ähnlichsten zuerst, Duplikate je `kennung` entfernt.
5. `bild_entscheidung(bild, katalog, params) -> dict` — die Kernentscheidung,
   Felder: `bild_id`, `art`, `anzahl_nutzbar`, `anzahl_erkennbar`, `clustern`
   (bool), `personen` (Liste bekannter Kennungen), `grund` (kurzer Text).
   Regelwerk:
   * `menge` **ohne** bekannten Vordergrund → `clustern: False`,
     `grund: "menge_ohne_bekannte_person"` ← **die Pflichtprüfung des Plans**
   * `menge` **mit** bekannter Vordergrund-Person → `clustern: True`,
     `personen: [<bekannt>]`, `grund: "menge_mit_bekannter_person"`
   * `gruppe` → `clustern: True`, `grund: "gruppe"`
   * `unklar` / `leer` → `clustern: False`
6. `vektoren_clustern(eintraege, schwelle, min_groesse) -> list[list[int]]` —
   DBSCAN-artig **ohne sklearn** (numpy genügt): Cosinus-Distanz
   (`1 - cosinus`), Kernpunkte mit `>= min_nachbarn`, Expansion über
   Nachbarschaft, Rauschpunkte werden **verworfen** (nicht in eine Gruppe
   gedrängt). Determinismus: Eingabereihenfolge bestimmt die Gruppen-Reihenfolge;
   eine Gruppe enthält die Indizes der Eingabe. `schwelle` und `min_nachbarn`
   als Parameter mit dokumentiertem Standard.
7. `gruppen_kennungen(gruppen, eintraege, altbestand, schwelle) -> list[dict]` —
   stabile Kennungen: passt eine Gruppe (Cosinus ihrer Vektoren) auf einen
   **Altbestand** (Liste `{"kennung": "...", "mittelpunkt": [...]}`), bleibt die
   Kennung; sonst wird die nächste freie `Person_<NNN>` vergeben (Nummern nie
   wiederverwenden, Lücken sind erlaubt). **Idempotenz:** derselbe Bestand
   zweimal → dieselben Kennungen.
8. `referenzseiten_bauen(gruppen_eintraege, kachel_holen, ausgabe_ordner, ...)` —
   je Gruppe **eine** Kontaktseite (PIL) aus den besten Kacheln (Reihenfolge:
   größter Flächenanteil, dann Score), Kachel mit **Nummer** und **Kennung**
   beschriftet, Kacheln je Seite als Parameter (Standard 8), `kachel_holen(eintrag)
   -> bytes | None` ist eine **eingesteckte Funktion** (Bytes → PIL-Bild), damit
   die Funktion ohne Netz/ohne pCloud testbar ist und später der echte Weg
   (pCloud-Download bzw. Handy-Crop) angesteckt werden kann. Fehlende Kachel
   (None) → Platzhalter, **kein** Abbruch. Rückgabe: Liste der geschriebenen
   Dateien. **Idempotent:** vorhandene Datei wird übersprungen, außer `--erneut`.
9. `bericht_bauen(...) -> dict` — Zahlen für den Changelog: Bilder gelesen,
   ungültige Zeilen, je Art gezählt, geclusterte Bilder, Gruppen, Größen der
   Gruppen, Kennungen neu/wiederverwendet, Kacheln geschrieben.
10. CLI `main()`: `--vektoren <pfad.jsonl>` (Pflicht), `--ausgabe <dir>` (Pflicht,
    **außerhalb des Repos**), `--katalog <pfad.json>` (optional), `--erneut`,
    `--trocken`. **Standard ist trocken**: nur zeigen, was entstünde
    (Zahlen + geplante Dateien), nichts schreiben. Ohne `--trocken` schreiben.
    Ausgabeordner innerhalb des Repos → **Fehler** mit klarer Meldung.
    Konsole nennt am Ende die Berichtszahlen in **Klartext-Deutsch**.

## Testpflichten (Auswahl — die Pflichtfälle sind nicht optional)

* **Massenfoto erzeugt keine Gruppe** (der Plan nennt das ausdrücklich als
  Prüfkriterium): synthetisches Bild 4032×3024 mit 40 kleinen Gesichtern
  → `bild_art == "menge"` → `bild_entscheidung(...)["clustern"] is False`;
  derselbe Fall **mit** einer bekannten Person im Vordergrund (ein großes
  Gesicht, Katalog-Treffer) → `clustern is True` und `personen == ["Person_007"]`.
* Grenzfälle der Art: 0 Gesichter, 1 Großgesicht, 3 kleine (→ `unklar`),
  5 kleine + 1 großes (→ `gruppe`, weil ein erkennbares da ist), Score unter
  `MIN_SCORE`, `bbox` mit Breite 0, `breite`/`hoehe` 0 (kein `ZeroDivisionError`).
* `vektoren_clustern`: 3 klar getrennte Gruppen + Rauschen → genau 3 Gruppen und
  das Rauschen **nicht** enthalten; identische Vektoren → eine Gruppe;
  leerer Eingang → leere Liste; Determinismus (zweimal derselbe Aufruf → gleich).
* `gruppen_kennungen`: zweiter Lauf mit gleichem Altbestand → gleiche Kennungen;
  eine **neue** Gruppe bekommt die nächste freie Nummer; eine **verschwundene**
  Kennung wird nicht neu vergeben.
* `referenzseiten_bauen`: mit synthetischen PIL-Bildern → Datei entsteht, Größe
  > 0, Beschriftung vorhanden (über die Bildgröße/Anzahl belegt); zweiter Lauf
  überspringt (0 neu) außer mit `erneut=True`; `kachel_holen` liefert `None`
  → Platzhalter, kein Absturz.
* Schutz: Quelltext enthält **keine** Löschfunktion
  (`deletefile|deletefolder|shutil.rmtree|os.remove`), **keinen** pCloud-Aufruf
  (`requests|httpx|e.pcloud`), **kein** Schreiben ins Repo, **keine**
  Ausgabe von Vektorwerten/Geheimnissen über `print` (Test: `print`-Zeilen im
  Modul enthalten keine Vektor-Dumps).
* `bild_entscheidung` und `bericht_bauen` sind **frei von Nebenwirkungen**
  (kein Dateizugriff).

## Was der Ausführer NICHT tut

* Keine Bilddateien anfassen, nichts herunterladen, keinen pCloud-Aufruf.
* Keine echten Ordnernamen, Ortsnamen, Personennamen (auch nicht erfunden
  wirkende wie „Anna") in Code, Tests oder Doku — nur `Person_001`… und
  erfundene `fileid`-Ziffern.
* Keine Änderung an bestehenden Dateien außer den drei genannten
  (und keinesfalls an `foto_sortieren.py`, `foto_kategorien.py`,
  `event_abgleich.py`, `themen_katalog.py`).
* Keine `git`-Befehle (das macht der Planer).

## Prüfkriterium (der Planer fährt es selbst)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q      # Exit 0, Baseline 879
```

Dazu eine **Stichprobe am Werkzeug selbst**: eine synthetische Vektordatei mit
**bekannter Wahrheit** (z. B. 12 eingebaute Personen-Cluster à 4–9 Vektoren,
plus 5 % Rauschen, plus 3 Massen-Bilder ohne erkennbare Gesichter) wird live
durch das Werkzeug gefahren; der Changelog nennt **gefundene Gruppen vs.
eingebaute Wahrheit** (Trefferquote, falsch zusammengelegte, übersehene) und
sagt ausdrücklich, dass die Stichprobe **synthetisch** ist (die echte Messung
kommt in N9b).
