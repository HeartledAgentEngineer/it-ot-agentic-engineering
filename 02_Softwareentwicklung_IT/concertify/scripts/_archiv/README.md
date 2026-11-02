# Archiv — historische Wegwerf- und Debug-Skripte

Diese Skripte gehören **nicht** zur laufenden App. Sie sind einmalige
Daten-Patches, Debug-Hilfen und Ad-hoc-Live-Tests aus der Entwicklung.
Keines davon wird von `app.py`, `fetch_data.py`, `main.py` oder
`preview_run.py` importiert oder als Subprozess gestartet (geprüft).

Sie liegen hier gebündelt statt im Projektroot, damit der Root nur die
echten Produktivmodule zeigt. Bei Bedarf sind sie weiter greifbar.

## Kategorien

| Präfix | Zweck | Beispiele |
|--------|-------|-----------|
| `patch_*` | Einmalige Korrekturen an `concert_data.json` | `patch_bb`, `patch_supports` |
| `debug_*` | API-Verhalten einzelner Clients prüfen | `debug_eventim`, `debug_songkick` |
| `clean_duplicate_*` | Doppelte Spotify-URIs aus den Daten räumen | `clean_duplicate_uris` |
| `resolve_uris*` | Vier Varianten eines URI-Auflösers (anon/app/user) | `resolve_uris_app` |
| `test_bb*`, `test_*` | **Keine pytest-Tests** — Live-Skripte, die echte APIs abfragen | `test_bb_eu`, `test_tavily` |
| sonstige | Diverse einmalige Hilfen | `inject_bb`, `write_setlists`, `search_log` |

## Toter Produktivcode

| Datei | Warum hier |
|-------|------------|
| `bandsintown_client.py` | Echter API-Client, aber vom Live-Pfad (`app.py`, `fetch_data.py`, `main.py`) nicht mehr importiert — nur vom ebenfalls archivierten `debug_bandsintown.py`. Hierher verschoben, damit der Root nur noch aktiv genutzte Clients zeigt. Bei Reaktivierung einfach zurück in den Root holen. |

> Die echten, automatisierten Tests liegen in `../../tests/` und laufen
> über den Prüfbefehl `.venv/Scripts/python.exe -m pytest tests -q`.
