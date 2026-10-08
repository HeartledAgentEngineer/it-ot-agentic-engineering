# 08.10.2026 – Gesichtsrahmen: Fotos wurden doppelt gedreht

## Befund (Sebastian, am Handy)

„Der Rahmen kommt irgendwo hin und nicht da, wo das erkannte Gesicht ist."

## Ursache (gemessen, nicht vermutet)

Die Gesichtserkennung dekodiert mit `cv2.imdecode(..., IMREAD_COLOR)` und dreht danach
mit `face_infer.orientiere_bild` nach der EXIF-Orientierung. Der Fix vom 15.09.2026
nahm an, dass `imdecode` die EXIF-Drehung ignoriert. Mit **OpenCV 5.0** stimmt das
nicht mehr. Diese Fassung steckt in der Gesichter-Umgebung am PC
(`~/foto_sortierung/venv_gesicht`).

Gemessen an einem künstlichen 200×100-JPEG mit Orientierung 6:

| Schritt | Form (Höhe, Breite) |
|---|---|
| `imdecode` allein (OpenCV 5.0) | (200, 100), also schon richtig gedreht |
| danach `orientiere_bild` | (100, 200), also ein zweites Mal gedreht und quer |
| Anzeige im Browser | (200, 100) |

Folge: Bei Fotos mit EXIF-Orientierung 3, 6 oder 8 lief die Erkennung auf einem
gedrehten Bild. Hochkant-Handyfotos haben fast immer 6 oder 8. `bbox`, `breite` und
`hoehe` liegen deshalb in einem anderen Koordinatenraum als das angezeigte Bild,
und der Rahmen landet neben dem Gesicht.

## Änderung

- `backend/face_infer.py`:
  - Neu: `dekodier_flags(cv2)`. Sie liefert `IMREAD_COLOR | IMREAD_IGNORE_ORIENTATION`, mit der Zahl 128 als Rückfall, falls eine Fassung die Konstante nicht ausweist.
  - `dekodiere_bild` dekodiert damit. OpenCV liefert die Rohpixel, gedreht wird genau einmal in `orientiere_bild`, gleich auf jeder OpenCV-Fassung.
- `tools/foto_sortierung/gesicht_erkennen.py` (`_bild_bereitstellen`, Weg ohne eigenen Dekodierer, also der echte YuNet-Lauf): dieselben Flags.

## Prüfung

- Neue Tests mit einer Attrappe, die sich wie `imdecode` von OpenCV 5.0 verhält:
  - `test_gesicht_erkennen.py`: `test_bild_bereitstellen_dreht_genau_einmal` für die Orientierungen 1/3/6/8 (Form **und** Lage eines Markierungsblocks gleich der Anzeige) sowie `test_bild_bereitstellen_schaltet_opencv_drehung_ab`.
  - `test_face_infer_ausrichtung.py`: `test_dekodiere_bild_dreht_genau_einmal`, `test_dekodier_flags_ohne_konstante_nutzt_rueckfall` und `test_dekodiere_bild_mit_echtem_opencv` (wird übersprungen, wenn OpenCV fehlt).
- Gegenprobe: Mit dem alten Code (vor diesem Commit) sind 6 dieser Tests rot, und zwar genau bei den Orientierungen 3, 6 und 8. Mit dem Fix sind beide Dateien grün: 162 bestanden, 1 übersprungen.
- Mit echtem OpenCV 5.0 (Gesichter-Umgebung, nur künstliches Bild) liegen bei den Orientierungen 1/3/6/8 Erkennungsbild und Anzeigebild gleich, in Form und Lage des Blocks.

## Was der Fix NICHT tut

Er repariert **keine schon gespeicherten Ergebnisse**: Vektordateien,
`gesicht_zuordnung.jsonl`, `personen_beispiele.json` und die Kopien am Handy behalten
bei gedrehten Fotos die falschen Koordinaten. Dafür braucht es zwei Schritte, die
nur Sebastian oder Hermes auf echten Daten startet:

1. Je Bild nur die EXIF-Orientierung lesen (nur der Dateikopf, kein ganzes Foto) und
   zählen, wie viele Bilder betroffen sind.
2. Die Koordinaten der betroffenen Bilder umrechnen. Die Merkmale bleiben gültig, weil
   `alignCrop` das Gesicht an den Landmarken ausrichtet. Damit bleiben Gruppen und
   bestätigte Namen erhalten. Gesichter, die auf dem quer liegenden Bild nicht gefunden
   wurden, holt erst eine neue Erkennung dieser Bilder nach.

Ebenfalls offen: Ein im Vollbild verschobener Rahmen lässt sich aus der Gruppen-
bzw. Personenansicht nicht speichern (`speichereEditorRahmen`, Fall c). Dafür fehlt
ein Speicherweg für Gruppenbeispiele.

## Nachtrag 08.10.2026, abends: Werkzeug `orientierung_pruefen.py`

**Gemessen:** pCloud-Vorschaubilder (`getthumb`) sind schon nach EXIF gedreht und
tragen selbst **keinen** Orientierungs-Tag mehr. Prüfung mit drei künstlichen
400×200-Bildern (Orientierung 1/3/6) in `/Agent/test_orientierung/`: Die Vorschau
entsprach jedes Mal der Anzeige, nicht dem Rohbild. Die Oberfläche zeigt also das
richtig gedrehte Bild. Bei gedrehten Fotos legt sie aber die gespeicherten
Koordinaten aus dem falsch gedrehten Erkennungsbild darüber. Deshalb zeigen
Gruppen-Ausschnitte bei diesen Fotos ins Leere oder auf ein halbes, fremdes Gesicht.

**Neu:** `tools/foto_sortierung/orientierung_pruefen.py` stellt fest, welche Fotos
betroffen sind.
- Es liest je Bild-ID aus den Vektordateien nur den Dateikopf, höchstens 128 KB per
  Range-Anfrage. Die EXIF-Orientierung liest es mit derselben Funktion wie die
  Erkennung (`face_infer.exif_orientierung`).
- Video-Standbilder (`#t=`) und doppelte IDs werden übersprungen.
- Ausgabe 1, `~/foto_sortierung/orientierung.jsonl`: Es wird nur angehängt.
  Geprüfte Bilder werden übersprungen, Fehlerzeilen beim nächsten Lauf erneut versucht.
- Ausgabe 2, `~/foto_sortierung/gedreht_plan.json`: Hier stehen alle Bilder mit
  Orientierung ≠ 1, im Planformat von `gesicht_erkennen.py --plan`. Die Datei wird
  atomar neu geschrieben.
- Standard ist der Trockenlauf: zählen, ohne Netz.
- Exit-Codes: Ziel im Repo → 2, fehlende Vektordatei → 1, einzelne Fehler → 3.
- Die Konsole zeigt nur Zahlen.
- Es reicht das Backend-venv.

**Tests:** `backend/tests/test_orientierung_pruefen.py`, 8 Tests mit erfundenen IDs,
künstlichen JPEG-Köpfen und eingestecktem Holer statt Netz.
- Geprüft werden: IDs ohne Video und ohne Doppelte, Trockenlauf ohne Netz,
  Schreiben samt Plan, zweiter Lauf ohne neuen Abruf, Wiederholung nach Fehler,
  Bericht ohne IDs, Repo-Ziel Exit 2, fehlende Datei Exit 1.
- Der echte Kopf-Holer wurde an den drei künstlichen pCloud-Dateien nachgeprüft:
  Orientierungen 1/3/6 richtig gelesen.

**Nächste Schritte (noch nicht gebaut):**
- Die betroffenen Bilder mit dem reparierten Code neu erkennen
  (`gesicht_erkennen.py --plan gedreht_plan.json`).
- Ihre alten Zeilen in den Gruppen ersetzen statt anhängen. Namen und
  Mittelpunkte bleiben dabei.
- Danach folgt der Speicherweg für von Hand verschobene Rahmen.
