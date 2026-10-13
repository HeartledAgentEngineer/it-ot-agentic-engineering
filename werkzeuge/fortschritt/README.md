# fortschritt — progress board for a night run

Reads `status.json` (single source of truth) and renders the state of a night-run
plan for three consumers:

- `python fortschritt.py --terminal` — plain text for the console / chat report.
- `python fortschritt.py --html` — writes the self-refreshing dashboard
  `.hermes/widgets/fortschritt.html`.
- `python fortschritt.py --zaehle` — counts Papa's unpacked Amazon archives via
  the pCloud API (read-only) and writes the real numbers back into
  `status.json`. The API count is the measurement; a success message from the
  unpack run is not.

Step state comes from `status.json` (`lage`: `fertig`, `laeuft`, `offen`,
`blockiert`); the counter bar is derived from the pCloud count, never asserted.

Each work in `laufende` also carries a **measured** state (`lage`): `fertig`
(target reached), `angehalten` (result file unchanged for more than
`RUHE_MINUTEN`, default 120 min) or `laeuft`. Only the truly running ones are
listed under "Laufende Arbeiten"; the rest appear under "Abgeschlossen oder
angehalten" with the reason. Without that split the board kept claiming work
that had ended hours ago.

`kennzahlen` lists small facts of the photo chain (data rows in
`bild_orte.csv`, rows and vectors in `bild_index.db`), counted directly from
the files (read-only, numbers only, header line subtracted so the value matches
the audit tool). They used to sit in the free-text hint and went stale there
silently (the text said 18.840 rows while the file had 25.177). A source that
cannot be measured is reported as "nicht messbar" — no value is invented.

Keep it cheap: `--zaehle` only reads the cloud, no model call, no images.
