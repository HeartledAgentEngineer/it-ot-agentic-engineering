# Changelog 03.11.2026 — Schlaf im Checks-Fenster (Issue #12)

## Was

- Neue Datei `frontend/schlaf.js`: zeigt im Checks-Fenster den Stand des
  Schlafprotokolls (Anzahl Nächte, letzte Nacht) und die letzten 7 Tage als Text.
- Empfänger `window.heyAgentSchlafEmpfangen(jsonText)`: Hey Agent übergibt die
  Nächte aus Health Connect, die Seite schickt sie angemeldet an
  `POST /api/alltag/schlaf` und meldet das Ergebnis in Klartext.
- Knopf `#schlaf-abgleichen` stößt den Abgleich in der App an
  (`window.HeyAgentSchlaf.abgleichen()`); im normalen Browser kommt ein Hinweis.
- `schlaf.js` steht in `FRONTEND_DATEIEN`, Cache-Bump `app.js?v=20261103B`.

## Warum

Die Uhr schreibt den Schlaf nach Health Connect. Der Weg ins Protokoll führt über
die App, weil nur sie Health Connect lesen darf; die Seite hat die Anmeldung fürs
Backend.

## Prüfung

- `node tests/test_schlaf.js schlaf.js` grün (reine Funktionen, Fetch-Stub, Verdrahtung).
- `test_frontend_node.py` hat die Zuordnung `test_schlaf.js → schlaf.js`.
