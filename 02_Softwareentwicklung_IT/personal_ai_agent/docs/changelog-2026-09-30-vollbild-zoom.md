# Änderungsprotokoll 30.09.2026 — Vollbild: mit zwei Fingern zoomen

Befund Sebastian (Handy, ~23:00): Ein Foto seines Arbeitsblatts (Tabelle „Emotionen und
Bedürfnisse") ließ sich im Vollbild nicht vergrößern — Text zu klein zum Lesen.

## Ursache

Das Vollbild-Overlay (`zeigeBildVollbild`, `frontend/app.js`) fängt seit dem 15.09.2026 **alle**
Gesten selbst ab: `touch-action:none` plus `preventDefault()` in `touchmove`/`pointermove`
(Sperre gegen Pull-to-Refresh, siehe `changelog-2026-09-15-quiz-stabil.md` Punkt 8 — dort
angekündigt: „wird als eigene JS-Zoomstufe nachgezogen"). Die Seite selbst ist
`user-scalable=no`. Der Kommentar über der Funktion behauptete trotzdem „NATIV per
Zwei-Finger-Pinch zoombar" — das stimmte seitdem nicht mehr; berichtigt.

## Was neu ist

- **Reine Funktionen** (testbar): `zoomBegrenzen` (Stufe 1…6), `zoomUmPunkt` (der Bildpunkt unter
  der Fingermitte bleibt unter der Fingermitte — Zoomen und Verschieben in einer Rechnung),
  `zoomVerschiebungBegrenzen` (Bild rutscht nicht aus dem Schirm, bei Stufe 1 immer mittig),
  `istDoppeltipp` (< 320 ms, < 30 px).
- **Gesten im Vollbild** (auf dem Bildbereich `wrap`): zwei Finger = zoomen + verschieben, ein
  Finger bei Zoom = verschieben, Doppeltipp = 2,5× an der Stelle bzw. zurück auf ganz, Mausrad
  am PC. Die Pull-to-Refresh-Sperre bleibt unverändert.
- **Zoom wirkt auf die `bildBox`** (`translate(...) scale(...)`), in der Bild, Gesichtsrahmen und
  Griffe liegen — alles zoomt gemeinsam. Der Rahmen-Editor rechnet ungezoomt: `resync` teilt das
  Bildschirmmaß durch `zoom.s`, Rahmen verschieben und Größe ziehen teilen den Fingerweg durch
  `zoom.s`; bei zwei Fingern wird kein Rahmen verschoben.
- Bildbereich `overflow:hidden` statt `auto` (verschoben wird per transform, nicht gescrollt);
  Bild `max-width:100vw; max-height:100vh` statt `100%` — die `bildBox` hat keine feste Höhe,
  `max-height:100%` griff deshalb nie, hohe Dokument-Fotos ragten oben/unten heraus.
- `app.js?v=20260930C`.

## Prüfung

- Neu `frontend/tests/test_vollbild_zoom.js` (27 Prüfungen: Rechenfunktionen, Verdrahtung,
  Sperre bleibt, Rahmen-Geometrie ungezoomt, Cache-Bump); `test_foto_galerie.js` auf den neuen
  Cache-Stand nachgezogen (reiner Versionsabgleich). `node --check app.js` OK, **alle 22
  Frontend-Tests Exit 0**.
- Browser-Prüfstand (Handybreite 375 × 812, echte Funktionen aus `app.js`, Testbild 1200 × 1600
  mit Gesichtsrahmen 500/300/200/240): Pinch ×3 um (190, 400) → Brennpunkt pixelgenau ortsfest,
  Rahmen weiter exakt 500/300/200/240; Ein-Finger-Verschieben um (−60, −80) genau übernommen;
  Rahmen im Zoom 3× um 30 Bildschirm-px gezogen → 32 Originalpixel (Soll 30 / 3 × 1200 / 375 = 32),
  Bild bleibt dabei stehen; weit über den Rand geschoben → Bildkante bleibt am Schirmrand;
  Doppeltipp → zurück auf ganz, erneut → 2,5×; Bild ohne Gesichter: Pinch 80 → 200 px = 2,5×.
- **Nicht belegt:** echte Mehrfinger-Berührung am Handy (der Prüfstand sendet
  Zeiger-Ereignisse) — Live-Test durch Sebastian.
