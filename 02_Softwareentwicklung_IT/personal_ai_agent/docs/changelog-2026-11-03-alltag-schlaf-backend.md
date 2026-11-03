# 03.11.2026 — Alltagsprotokoll: Schlafnächte der Uhr im Backend (Issue #12)

## Neu
- `backend/app/services/alltag_speicher.py` (S1): append-only JSONL unter `~/alltagsprotokoll/eintraege.jsonl`
  (`ALLTAGSPROTOKOLL_PFAD`). Arten `stunde`, `schlaf`, `schlafnacht`. Korrektur = neue Zeile mit `ersetzt`,
  Löschen = Marker über die ganze Kette, kaputte Zeilen werden übersprungen.
  `schlafnaechte_uebernehmen()` ist idempotent je Health-Connect-Kennung; ändert die Uhr eine Nacht, wird
  sie als Korrektur gespeichert. Ungültige Nächte (Ende vor Beginn, > 24 h, ohne Kennung) werden gezählt
  und verworfen, fremde Felder fallen weg, unbekannte Phasen heißen `unbekannt`.
- `backend/app/services/alltag_rechnen.py` (S2): je Nacht Dauer, Schlaf, Wach/leicht/tief/REM, Wachphasen
  (ohne Einschlafen/Aufstehen), Einschlaf-/Aufwachzeit in Ortszeit der Uhr; Nacht zählt zum Tag des
  Aufwachens; Nickerchen = Beginn 9–19 Uhr und < 3 h. Zusammenfassung (Schnitt, kürzeste/längste Nacht)
  und Klartext.
- `backend/app/router/alltag.py`: `POST /api/alltag/schlaf`, `GET /api/alltag/schlaf?von&bis` (Standard
  14 Tage), `GET /api/alltag/schlaf/stand`. In `main.py` hinter dem API-Key.
- Chat-Werkzeug `schlaf_abfragen` (`datum` oder `tage`): „Wie habe ich letzte Nacht geschlafen?".
  Werkzeugzahl in zwei Tests 15 → 16.

## Tests
`test_alltag_speicher.py` (18), `test_alltag_rechnen.py` (9), `test_alltag_router.py` (6),
`test_werkzeug_schlaf.py` (7) — alle mit erfundenen Nächten, rot → grün.

## Noch offen
Hey Agent liest Health Connect und übergibt an die WebView (nächster Schritt).
