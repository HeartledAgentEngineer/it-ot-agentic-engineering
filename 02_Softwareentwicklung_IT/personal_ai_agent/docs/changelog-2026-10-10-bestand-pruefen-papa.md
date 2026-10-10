# Änderungsprotokoll 10.10.2026 — Bestandsprüfung: Papas 6.336 Fotos wurden nicht geprüft

## Anlass

Die Ketten-Notiz für Papas Fotos behauptete, `tools/foto_sortierung/bestand_pruefen.py`
erkenne Papa „über die Kennungen automatisch". Das traf **nicht** zu. Der Lauf am
echten Bestand (11:2x) nannte nur die zwei Sammlungs-Pläne und zählte Papas
Vektorzeilen als „außerhalb aller Pläne" — Papa war in der Prüfung schlicht
**nicht enthalten**. Grund: `STANDARD_PLAENE` führte nur `sortierplan.json` und
`sortierplan_bildervideos.json`; `sortierplan_papa.json` fehlte, ebenso
`personen_vektoren_papa.jsonl`.

**Zweiter Fehler, beim Lesen aufgefallen:** Die Beschreibungszeile hängte
`.replace(".", ",")` an die **ganze** Zeile — und traf damit auch den Dateinamen.
In der Ausgabe stand `bild_beschreibungen,jsonl: …` mit Komma statt Punkt.

## Änderung

- `STANDARD_PLAENE` und `STANDARD_FOTO_VEKTOREN` führen jetzt auch
  `sortierplan_papa.json` und `personen_vektoren_papa.jsonl`.
- `STANDARD_BESCHREIBUNGEN` ist eine **Liste** von Dateien statt einer: der
  Altspeicher `bild_beschreibungen.jsonl` und `bild_beschreibungen_papa_reich.jsonl`
  (Papas reiche Fassung — eigener Lauf, weil sein Plan andere Feldnamen trägt und
  im Altspeicher nicht vorkommt). Der Bericht druckt **eine Zeile je Datei**, die
  Zuordnung zu den Plänen läuft unverändert über die Kennungen (Vereinigung).
- Komma-Fehler behoben: der neue Helfer `_usd()` formatiert **nur die Zahl** mit
  Komma; Dateinamen bleiben unangetastet.

Unverändert: nur lesend, nur Zahlen und Dateinamen (keine Namen, keine
Beschreibungen, keine Koordinaten), nichts wird geschrieben, Kennungen werden
als Text verglichen, Gruppenteil und Lücken-Erkennung wie bisher.

## Prüfung (offline, nur lesend)

- **Lauf am echten Bestand** (`tools/foto_sortierung/bestand_pruefen.py`, 11:2x):
  Papas Plan erscheint jetzt als eigene Gruppe —
  „Plan sortierplan_papa.json: 6.336 Einträge = 6.336 Fotos + 0 Videos",
  „Gesichter Fotos: 3.801 von 6.336 (60,0 %)", „Beschreibungen: 1.908 von 6.336
  (30,1 %)" (Stand der laufenden Prozesse), und die Dateinamen-Zeile ist wieder
  `bild_beschreibungen.jsonl: …` mit Punkt.
- `backend/tests/test_bestand_und_handy_uebergabe.py`: neuer Test
  `test_bestand_prueft_papas_plan_und_mehrere_beschreibungsdateien`
  (Papas Plan mit `name`/`ordner` wird geprüft, zweite Beschreibungsdatei wird
  mitgezählt, Dateiname behält den Punkt) — **15 passed**.
- **Voller Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → siehe Commit (grün, Exit 0).

## Offen (ehrlich)

- Der Bericht zeigt für Papa die **laufenden** Zahlen (Gesichter- und
  Beschreibungslauf arbeiten noch) — der Nachweis ist damit live, nicht
  eingefroren. Schritt 10 der Kette ist erst „fertig", wenn beide Läufe bei
  6.336 stehen.
- Die Zeile „Vektorzeilen außerhalb aller Pläne: 1.260" bleibt; das sind
  Vektorzeilen ohne Plan-Zugehörigkeit (u. a. Video-Standbilder), nicht Papa.
