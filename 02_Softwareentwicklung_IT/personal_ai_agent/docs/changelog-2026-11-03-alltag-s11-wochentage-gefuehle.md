# Changelog 03.11.2026 — Alltagsprotokoll S11: Wochentage und Gefühle nach Schlaf

Baut auf S10 auf. Zwei weitere Verknüpfungen der Daten, die schon da sind. Beide rechnen nur mit Zahlen und den sechs Grundgefühlen. Freitext geht dabei nicht hinaus.

## Neu im Zeitraum-Text von `alltag_abfragen`

- **Wochentage** (`wochentag_text`): Stimmung je Wochentag.
  - Gerechnet wird der Schnitt der Tagesschnitte, damit ein Tag mit vielen Einträgen nicht mehr zählt als einer mit wenigen.
  - Ein Wochentag erscheint erst ab 2 Tagen, die Auswertung insgesamt erst ab 2 solchen Wochentagen.
  - Beispiel: „Wochentage, Stimmung im Schnitt (Tage): Montag 2,5 (2) · Dienstag 4,5 (2)."
- **Gefühle nach Schlaf** (`gefuehle_nach_schlaf_text`): an wie vielen Tagen nach den kürzeren bzw. längeren Nächten welches Grundgefühl vorkam.
  - Die Nächte werden wie beim Schlafvergleich am Median geteilt, ab 4 Tagen.
  - Es zählen nur Gefühle aus der festen Liste. Eigene Gefühlsworte bleiben außen vor.
  - Beispiel: „Gefühle nach kürzeren / längeren Nächten (Tage mit dem Gefühl, je 2 Tage): Freude 0 / 2 · Ärger 2 / 1. Nur ein Zusammenhang, kein Beweis."
- `tag_kennzahlen` liefert zusätzlich `gefuehle_alle` (alle Grundgefühle des Tages). Bisher kamen nur die drei häufigsten heraus.
- Die Werkzeugbeschreibung nennt beides, mit Beispielfragen wie „An welchem Wochentag geht es mir besser?" und „Bin ich nach wenig Schlaf öfter gereizt?".

## Datenschutz

Unverändert. Die neuen Sätze enthalten nur Zahlen, Wochentag-Namen und Wörter aus `GRUNDGEFUEHLE`. Tätigkeiten, eigene Worte und Namen kommen darin nicht vor.

## Prüfung

- 6 neue Tests, vorher rot:
  - 5 in `test_alltag_auswertung.py`: Wochentagsprofil, Schweigen bei zu wenig Daten, Gefühle nach Schlaf (mit einem erfundenen eigenen Gefühlswort, das nicht erscheinen darf), Schweigen ohne Gefühle oder Tage, Zeitraum-Text.
  - 1 in `test_werkzeug_alltag.py`: Die Beschreibung nennt Wochentag und Gefühle nach Schlaf.
- Alle Alltag- und Werkzeug-Tests grün (359).
