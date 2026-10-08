# Änderungsprotokoll 08.10.2026: Gruppen-Diagnose

## Anlass

Sebastian hat am Handy die 20 größten Personengruppen benannt. Danach kamen Gruppen,
in denen verschiedene Personen und Gegenstände gemischt sind.

## Verdachte (noch nicht belegt)

1. **Gedrehte Fotos.** Bis `ad4f09c` lief die Erkennung auf doppelt gedrehten Bildern.
   Auf quer liegenden Bildern findet sie Gesichter in Gegenständen. Deren Merkmale sind
   unbrauchbar und sammeln sich in Mischgruppen.
2. **Niedrige Erkennungssicherheit.** Als Gesicht zählt alles ab `score` 0,6
   (`personen_cluster.MIN_SCORE`). Echte Gesichter liegen meist über 0,9.

## Neu

`tools/foto_sortierung/gruppen_diagnose.py` misst beide Verdachte gegeneinander,
bevor etwas neu gerechnet wird.
- **Liest nur:** `~/foto_sortierung/personen_gruppen/gesicht_zuordnung.jsonl` und
  `~/foto_sortierung/orientierung.jsonl` (aus `orientierung_pruefen.py`).
- **Schreibt nichts.**
- **Bericht:** Die Gruppen 1–20 (die schon benannten), die Gruppen ab Platz 21 und
  die Gesichter ohne Gruppe stehen nebeneinander. Je Bereich gibt es:
  - den Anteil aus gedrehten Fotos
  - den Anteil unter `score` 0,9 und den Median-`score`
  - den Anteil kleiner Gesichter (unter 0,5 % der Bildfläche)
  - den Anteil aus Videos
- **Dazu einzeln:** die Gruppen ab Platz 16, mit Kennung (`Person_1003`).
- Die Ausgabe enthält keine Namen, keine Bild-IDs und keine Koordinaten.

Tests: `backend/tests/test_gruppen_diagnose.py` mit 5 Offline-Tests auf erfundenen Daten.

## Was daraus folgt (Entscheidung nach dem Lauf)

- Ist der Anteil gedrehter Fotos ab Platz 21 deutlich höher: die gedrehten Fotos gezielt
  neu erkennen.
- Ist der Anteil unsicherer Funde deutlich höher: die Schwelle für die Gruppierung
  anheben. Danach den Rest neu gruppieren, die benannten Gruppen bleiben erhalten.
- Ist beides unauffällig: weiter nach der Ursache suchen, nichts neu rechnen.
