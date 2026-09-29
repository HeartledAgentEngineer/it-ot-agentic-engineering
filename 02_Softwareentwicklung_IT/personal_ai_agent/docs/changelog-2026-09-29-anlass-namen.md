# Änderungsprotokoll 29.09.2026: regelbasierte Anlass-Namen (N-0929 Schritt 4)

## Was
Neues Werkzeug `tools/foto_sortierung/anlass_namen.py`. Es macht Vorschläge für Anzeigenamen der Anlässe aus `ereignisse.jsonl` und nutzt dafür kein Sprachmodell und kein Netz.

- **Regeln nach Priorität:**
  1. Handordner-Name, wenn mehr als die Hälfte der Bilder im selben Ordner liegt.
  2. Häufigster Ort. Bei mindestens 3 Orten derselben Region wird daraus die Region, bei mindestens 3 Orten desselben Landes das Land.
  3. Nur der Zeitraum.

  Das Thema steht nur als Zusatz dahinter, „Sonstiges" entfällt.
- **Format:** „Ort, Zeitraum – Thema"; über eine Monats- oder Jahresgrenze zum Beispiel „Juli–August 2014".
- **Merker je Anlass:** `heimat_verdacht` bedeutet, der Ort ist der häufigste über alle Anlässe. `reise` bedeutet, der Anlass liegt außerhalb davon und hat einen Ort.
- **Ausgabe:** `~/foto_sortierung/anlass_namen.jsonl`. Das ist eine Ableitung und wird atomar neu geschrieben. `ereignisse.jsonl` wird nie geschrieben. Trockenlauf ist der Standard, ein Repo-Pfad ergibt Exit 2. Die Konsole zeigt nur Zähler.
- **Handordner-Format festgelegt:** `~/foto_sortierung/handordner.jsonl` mit einer Zeile `{"bild_id", "handordner"}` je Bild. Die Datei erzeugt später Hermes.

## Warum
Anlass-Namen wie „Bühne" oder „Sonstiges" erkennt niemand wieder. Ort und Zeit sind so, wie Menschen sich erinnern (Befund Sebastian, 29.09.).

## Prüfung
- `pytest tests/test_anlass_namen.py`: 26 passed.
- Voller Prüfbefehl: 2920 passed, Exit 0 (Baseline 2894), Lauf durch den Ausführer.

## Grenzen
- Regionen kommen unübersetzt aus GeoNames, zum Beispiel „Tuscany".
- Ein einzelnes falsches EXIF-Datum kann den Zeitraum aufblähen.
