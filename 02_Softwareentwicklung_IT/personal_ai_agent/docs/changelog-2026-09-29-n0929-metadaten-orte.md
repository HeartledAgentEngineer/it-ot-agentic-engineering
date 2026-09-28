# Änderungsprotokoll 29.09.2026 — Nachtlauf N-0929: Metadaten und Orte

## Was
- `tools/foto_sortierung/gesicht_erkennen.py`: neue reine Funktion `exif_metadaten(rohdaten)` (nur PIL). Liest Aufnahmedatum (DateTimeOriginal, sonst Digitized, sonst DateTime), Kamera-Hersteller/-Modell und GPS (Dezimalgrad, 6 Stellen; 0/0 und unplausible Werte → `None`). Wirft nie. `StapelLauf` hängt das Ergebnis je Vektorzeile als `metadaten` an. Neue Zähler `mit_aufnahme` und `mit_gps`; die Konsole zeigt nur diese Summen, nie Koordinaten.
- Neu: `tools/foto_sortierung/orte_zuordnen.py`. Es ordnet GPS offline Land, Region und Ort zu (`reverse_geocoder`, GeoNames, kein Netz).
  - Eingabe: `~/foto_sortierung/personen_vektoren.jsonl`
  - Ausgabe: `~/foto_sortierung/orte.jsonl`, nur anhängend und idempotent, ohne Koordinaten.
  - Trockenlauf ist Standard. Ein Repo-Pfad als Ziel führt zu Exit 2.
  - Abhängigkeit `reverse_geocoder` 1.5.1 (mit scipy) nur im PC-venv, dokumentiert im Modul-Docstring.

## Warum
- Jedes Foto wird nur einmal über pCloud geladen. Dabei entstehen Gesichter, echtes Datum, Handy-Modell und GPS zugleich (Plan E13a/E4).
- Die Orte sind die Grundlage für Fragen wie „Wann war ich in Dänemark?" und für Anlassnamen aus Ort und Zeitraum (E13c).
- Der Code entsteht im Claude-Abo, Hermes führt die Läufe nur aus.

## Prüfung
- `cd backend && .venv/Scripts/python -m pytest tests/ -q`: 2808 passed, Exit 0 (Baseline 2789), Lauf durch den Ausführer.
- `pytest tests/test_orte_zuordnen.py -q`: 10 passed. Der Pfad-Fix wurde vom Planer frisch geprüft.
- Neu sind 19 EXIF-Testfunktionen, alle mit synthetischen JPEGs. Dazu kommen 10 Orte-Tests (Attrappe plus ein echter Offline-Test mit Split → HR).

## Grenzen
- Die `main`-Ausgabe mit `--schreiben` ist nur über die Zähler getestet, nicht mit echtem Netz.
- `abstand_km` misst zur nächsten GeoNames-Stadt. Bei kleinen Orten ist der Wert deshalb ungenau.
