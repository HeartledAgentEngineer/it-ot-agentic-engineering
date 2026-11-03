# 03.11.2026 — KI-Erzählung: Erinnerung als Kern, gereinigt statt zitiert

## Wunsch (Sebastian)
Der **Inhalt** der Notiz bleibt 1:1 — jede Aussage. Nur die eingesprochene Sprache wird gereinigt
(Füllwörter, Grammatik, abgebrochene Sätze, Hörfehler der Spracherkennung) und mit Bild und
Personen verwoben. Bisher: Notiz am Ende wörtlich angehängt, samt Hörfehlern.

## Ursachen (gemessen mit erfundenen Daten, Skripte nur im Scratchpad)
1. Altes Verhalten am Handy: das Denk-Modell lieferte oft keinen Text → Vorlage → Notiz wörtlich
   (behoben in da243ea).
2. Prompt: feste Satzzahl („4–8" / „6–10 Sätze") zwang zum Ausschmücken (Wind, Gerüche, Tiere);
   keine Regel zum Glätten der Diktat-Sprache; Hörfehler („Enden" statt „Enten") blieben in 2 von 3 Läufen.
3. Maskierung: Vorname und ganzer Name bekamen getrennte Kürzel ([PERSON_02] / [PERSON_01]) — das
   Modell machte daraus zwei Personen und verwechselte, wer was tat.

## Änderung (`geschichte_erzaehlen_ki.py`)
- Systemprompt: kein Erfinden, ausdrücklich auch keine Gefühle, Gerüche, Geräusche, Wetter.
- Regeln: Erinnerung = Kern (jede Aussage, nichts weg, nichts dazu); Diktat glätten
  (Füllwörter, Grammatik, abgebrochene Sätze, Hörfehler bei eindeutigem Zusammenhang); mit dem Bild
  verweben und Handlungen den Personen zuordnen; Länge „höchstens 8 / 10 Sätze" statt Mindestlänge.
- Neu `personen_hinweis()`: „[PERSON_02] ist dieselbe Person wie [PERSON_01]" — nur Kürzel; ein von
  mehreren Personen geteilter Namensteil wird nicht gleichgesetzt (bleibt maskiert).
- Tests: 8 neue (rot → grün), 20 grün.

## Messung nachher (3 Bild- + 2 Anlassgeschichten, erfunden)
- Personen in allen 5 Läufen richtig zugeordnet (vorher doppelte „Erika", „ich" statt Erika).
- Längen 43–104 Wörter statt 106–186; Erfundenes nur noch vereinzelt („lachend").
- Hörfehler „Enden" noch in 1 von 3 Läufen (vorher 2 von 3) — offen.
- Offen: Ort als Platzhalter → „zum [Ort]" (Artikel passt nicht).
