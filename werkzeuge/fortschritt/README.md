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

Keep it cheap: `--zaehle` only reads the cloud, no model call, no images.
