# Änderungsprotokoll 01.10.2026 — Überlauf-Wächter (Darstellungsfehler am Handy messen)

Befund Sebastian (30.09. und 01.10. ~09:20, wiederholt): Eine frisch gestreamte Antwort — zuletzt
mit Recherche — ragt am Handy rechts über den Rand; erst nach einem App-Neustart ist dieselbe
Nachricht richtig eingerückt.

## Ursachensuche (ohne Ergebnis im Browser)

Browser-Prüfstand mit dem **echten** `index.html` + `app.js` (Handybreite 375 × 812, nachgebautes
Backend, gestreamte Recherche-Antwort mit Überschrift, Tabelle, langem Link, langem Code-Wort und
zwei Quellen mit überlangem Titel): Blase rechts bei 359 px, Inhalt 309 px breit, Seite 375 px —
**kein Überlauf**, weder während des Streams noch nach dem Abschluss. Der Fehler hängt also an
etwas, das nur am Handy auftritt (Android-WebView, Zoom/Schriftvergrößerung, ein bestimmter Inhalt).
Ohne Messung am Gerät wäre jede Reparatur geraten.

## Was neu ist

- **`frontend/app.js`:** `ueberlaufTaeter()` (rein, testbar) und `ueberlaufPruefen(contentDiv,
  phase)`: misst Fensterbreite, WebView-Zoom (`visualViewport.scale`), Seitenbreite, rechten
  Blasenrand, Inhalts-Scrollbreite; ragt etwas heraus, werden die drei am weitesten
  herausragenden Elemente mit Tag, Klasse, Breite, `white-space`, `display` festgehalten — **nie
  Text**. Meldung an `console.warn('[UEBERLAUF] …')` (Logcat, `chromium`) und
  `POST /api/diagnose/ueberlauf`; je Blase und Phase höchstens eine Meldung. Aufrufe: während des
  Streams (bei jedem sichtbaren Neuzeichnen) und nach `finishReply` nach 0,3 s und 2 s.
  `app.js?v=20261001B`.
- **`backend/app/router/diagnose.py`** (neu, mit Schlüssel-Schutz): legt die Messung als
  JSONL-Zeile in den kabel-lesbaren Diagnose-Ordner (`~/storage/downloads/hermes_diag/
  ueberlauf.jsonl`, sonst `~/agent_diag`, `DIAG_ORDNER`); nur Zahlen und harmlose Zeichen,
  höchstens 8 Täter, Datei > 512 KB → letzte 200 Zeilen bleiben. Immer HTTP 200.

## Prüfung

- Neu `frontend/tests/test_ueberlauf_waechter.js` (Täter-Auswahl, misst Zoom/Seitenbreite, nie
  Text, eine Meldung je Phase, Aufrufstellen, Cache-Stand); `test_foto_galerie.js` auf
  `20261001B` nachgezogen. Neu `backend/tests/test_diagnose_ueberlauf.py` (4 Tests: Zeile mit
  entschärften Zeichen, Ablehnung zu vieler/zu langer Felder, Kürzen, Schlüssel-Schutz).
- Browser-Prüfstand (echtes `app.js`): normale Antwort → **0** Meldungen; künstlich gesprengte
  Blase (600 px `nowrap`) → **genau 1** Meldung mit `span.test-breit`, `nowrap`, rechts 633 px;
  zweite Prüfung → keine Doppelmeldung.

## Nächster Schritt

Tritt der Fehler wieder auf: per Kabel `/sdcard/Download/hermes_diag/ueberlauf.jsonl` lesen
(oder Logcat `[UEBERLAUF]`) — dann steht dort, welches Element die Blase sprengt.
