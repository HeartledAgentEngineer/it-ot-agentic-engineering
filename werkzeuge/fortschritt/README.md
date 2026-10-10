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

Keep it cheap: `--zaehle` only reads the cloud, no model call, no images.
