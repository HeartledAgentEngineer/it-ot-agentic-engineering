# Changelog 02.11.2026 — Checks nur noch über das Roboter-Symbol

## Wunsch (Sebastian, Handy)
Das Checks-Fenster ließ sich zweimal öffnen: über den Klemmbrett-Knopf (`#selbsttest-btn`) und über
das Roboter-Symbol 🤖 (`#agent-face`, seit 20.10.2026). Der Knopf soll weg, damit die Kopfzeile Platz hat.

## Änderung
- `frontend/index.html`: Knopf `#selbsttest-btn` entfernt; `app.js?v=20261102A`.
- `frontend/app.js`: `dom.selbsttestBtn` und dessen Klick-Anbindung entfernt. Das Roboter-Symbol öffnet
  das Fenster weiter per Antippen, Enter oder Leertaste.
- Tests: `test_selbsttest.js` (kein Knopf, Roboter öffnet das Blatt), `test_server_zustand.js`.

## Beleg
Tests zuerst umgestellt → beide rot (Exit 1); nach der Änderung beide grün;
`pytest tests/test_frontend_node.py` 59 passed.

## Mitgezogen: Datums-Zeitbombe in `tests/test_gedaechtnis_erklaeren.py`
Das Commit-Tor war am 02.11.2026 rot (1 failed / 6110 passed): `test_teilwort_findet_den_eintrag` erwartete
für einen Termin „Am 2. November“ fest `lage == "kommend"`, gerechnet wird aber gegen das echte Heute
(`memory_service._lage`) — am Termintag ist die Lage „heute“, danach „vergangen“. Die Tage rechnete der Test
schon, die Lage jetzt nach derselben Regel. Beleg: `pytest tests/test_gedaechtnis_erklaeren.py` 7 passed.
