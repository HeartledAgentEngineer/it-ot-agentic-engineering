# Changelog 03.11.2026 — Alltagsprotokoll S5 (Teil 1): API ohne Sprachmodell

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S5. Dieser Teil braucht kein Modell und baut
nur auf S1 (Speicher) und S2 (Rechnen) auf. `POST /api/alltag/eintrag` (Text → Struktur) folgt
mit S3.

## Neu in `backend/app/router/alltag.py` (hinter dem API-Key)

| Route | Antwort |
|---|---|
| `GET /api/alltag/offen` | `{offene_stunden, schlaeft, letzter_eintrag}` für das Pop-up (S7) |
| `GET /api/alltag/tag?datum=JJJJ-MM-TT` | Stunden- und Schlaf-Einträge des Tages, je mit `fehlt`, dazu `naechte_uhr` |
| `PATCH /api/alltag/eintrag/{id}` | neue Fassung mit `ersetzt`; unbekannte Felder fallen weg |
| `DELETE /api/alltag/eintrag/{id}` | Löschmarker (append-only) |

Ein unbekannter Eintrag ergibt 404, kein JSON oder ein falsches Datum 400.

## Prüfung

- Neu: `test_alltag_router_s5.py` (7): offen ohne Einträge, volle Stunden, still im Schlaf,
  Tag mit Lücken und Uhr-Nacht, Datum fehlt, korrigieren und löschen, 404/400. Vorher 7 rot.
- `test_alltag_router.py` unverändert grün.
