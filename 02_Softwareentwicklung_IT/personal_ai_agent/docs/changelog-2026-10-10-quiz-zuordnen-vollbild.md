# Änderungsprotokoll 10.10.2026: Vollbild-Rahmen und Gesichter zuordnen

## Vollbild: Der ✕-Knopf verdeckt das Gesicht nicht mehr

Befund am Handy: Im Vollbild trägt jeder gelbe Gesichtsrahmen einen roten ✕-Knopf, mit dem
man den Rahmen im alten Quiz löschen kann. Er war 22 px groß und saß **innen** in der rechten
oberen Ecke. Bei kleinen Gesichtern lag er genau auf dem Gesicht. Beim Vergrößern half das
nicht, weil der Knopf im gezoomten Bereich mitwächst.

**Behoben** (`frontend/app.js`, Rahmen im Vollbild):
- Der Knopf sitzt jetzt **außerhalb** des Rahmens, über der rechten oberen Ecke
  (`bottom:100%`).
- Er hat die Klasse `vollbild-rahmen-marke`.
- Das Löschen bleibt gleich.
- Cache-Kennung: `app.js?v=20261010A`.

**Prüfung:**
- Neu `frontend/tests/test_vollbild_marke.js` (5 Prüfungen).
- In `test_foto_galerie.js` ist nur die festgeschriebene Cache-Kennung nachgezogen.
- Alle Frontend-Tests haben Exit 0. Die meisten erwarten `app.js` als Argument
  (`node tests/<test>.js app.js`); `test_erzaehlen.js`, `test_wecken.js` und
  `test_vollbild_marke.js` laufen ohne Argument.
- Am Handy ist die Änderung noch nicht angesehen worden.
