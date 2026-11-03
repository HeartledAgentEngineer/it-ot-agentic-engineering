# Changelog 03.11.2026 — Alltagsprotokoll S12: Einschlafzeit und Stimmung

Baut auf S11 auf (`main`, `cf3d971`; volle Suite dort 6446 grün).

## Neu im Zeitraum-Text von `alltag_abfragen`

- **Einschlafzeit** (`einschlafzeit_text`): Stimmung und Anspannung nach früherem bzw. späterem Einschlafen.
  - Geteilt wird am Median, ab 4 Tagen, wie beim Schlafvergleich.
  - Die Uhrzeit zählt ab 12 Uhr mittags (`_abend_minuten`). So gilt 00:30 als später als 23:00.
  - Beispiel: „Einschlafzeit und Stimmung (4 Tage): Nach früherem Einschlafen (bis 23:00) lag die Stimmung im Schnitt bei 4,5, nach späterem bei 2,5. Anspannung im Schnitt 15 gegenüber 60. Nur ein Zusammenhang, kein Beweis."
- Die Werkzeugbeschreibung nennt die Einschlafzeit.

## Behoben

- **Unterbrochene Nacht:** `_nacht_zusammen` übernahm die Einschlafzeit des letzten Abschnitts. Aus 23:00 (zwischendurch wach, dann ab 04:00) wurde so 04:00. Jetzt gilt die Einschlafzeit des ersten Abschnitts.

## Datenschutz

Unverändert. Es gehen nur Uhrzeiten und Zahlen hinaus.

## Prüfung

- 5 neue Tests, vorher rot:
  - 4 in `test_alltag_auswertung.py`: Vergleich, Schweigen bei zu wenig Tagen, Einschlafzeit der unterbrochenen Nacht, Zeitraum-Text.
  - 1 in `test_werkzeug_alltag.py`.
- Alle Alltag- und Werkzeug-Tests grün (364).
