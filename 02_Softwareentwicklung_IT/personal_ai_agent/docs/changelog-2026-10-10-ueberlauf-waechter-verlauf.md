# Änderungsprotokoll 10.10.2026 — Überlauf-Wächter misst jetzt auch den VERLAUF

Befund Sebastian (10.10.2026): Eine Antwort ragt am Handy rechts über den Rand, und der
Vorlese-Knopf ist aus dem Bild gedrückt. Der Wächter vom 01.10.2026
(`changelog-2026-10-01-ueberlauf-waechter.md`) sollte genau das messen — die Datei
`/sdcard/Download/hermes_diag/ueberlauf.jsonl` war am Handy aber **nicht vorhanden**.

## Ursache

Der Wächter feuerte nur bei **frisch gestreamten** Antworten (`frontend/app.js`, Aufrufe in der
Stream-Schleife und in `finishReply`). Die kaputte Blase kam jedoch aus dem **Verlauf** (nach dem
App-Start geladen) — dieser Weg maß nie. Deshalb blieb der Fehler für den Wächter unsichtbar.

## Was neu ist

- **`frontend/app.js`:**
  - `ueberlaufAllePruefen(phase, max)` — geht alle vorhandenen Blasen (`.message-content`) durch und
    misst **jede sichtbare** mit dem bestehenden `ueberlaufPruefen` (derselbe dataset-Merker sorgt
    für höchstens eine Meldung je Blase und Phase). Nur Sichtbares (im Fenster liegende Blasen)
    wird gemessen; `max` (Standard 80) deckelt die Zahl je Aufruf.
  - **Verlauf:** In `zeigeGespraech()` wird nach dem Aufbau gemessen — nach 0,3 s (`verlauf`) und
    nach 2 s (`verlauf_spaeter`, weil Bilder/Quellen die Breite erst danach verändern). Beim
    Nachladen älterer Blasen („Ältere Nachrichten laden…") zusätzlich `verlauf_aelter`.
  - **Größenwechsel:** `ueberlaufBeiGroessenwechsel()` misst entprellt (0,4 s) bei `resize` und
    `orientationchange`. Der Phasenname trägt die Fensterbreite (`resize412`), damit Drehen und
    Zurückdrehen je Breite genau einmal meldet (kein Dauerfeuer).
  - `index.html`: `app.js?v=20261010B`.
- Kein Text, keine Bilder, keine Gesichter: der Wächter meldet weiterhin nur Zahlen und
  Element-Kennzeichen. Der Backend-Endpunkt (`POST /api/diagnose/ueberlauf`) blieb unverändert.

## Prüfung (echte Ausgabe)

- **`frontend/tests/test_ueberlauf_waechter.js`** erweitert (Verlauf durchgeht die Blasen, misst je
  Blase mit der Phase, nimmt nie Text mit, Verlaufs-/Älter-Aufrufe, Größenwechsel-Listener,
  Breite im Phasennamen). `test_foto_galerie.js` auf `20261010B` nachgezogen.
- **Alle 26 JS-Tests grün** (Frontend, `node tests/<datei>.js [app.js]`).
- **Prüfbefehl grün:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
  **3613 passed, 2 skipped** (Exit 0).
- **Messung am echten Code** (Edge headless, echte `style.css`, Handybreite): zwei Blasen, eine
  normal, eine absichtlich zu breit (`width:2000px` in einem 300-px-Inhalt) →
  `ueberlaufAllePruefen('verlauf')` meldet **genau 1** (die breite), der zweite Aufruf derselben
  Phase **0** (Dedup), eine neue Phase **1** (erneute Messung), **2** POST-Aufrufe gesamt.
  Die Seite selbst lief dabei **nicht** über (`seite_scroll == breite`) — erkannt wurde die Blase
  allein über `scrollWidth > clientWidth`, also genau den Inhalt, um den es geht.

## Nächster Schritt (Sebastian am Handy)

Den kaputten Chat einmal öffnen. Der Verlauf wird jetzt vermessen; die Zeile landet in
`/sdcard/Download/hermes_diag/ueberlauf.jsonl` (oder Logcat `[UEBERLAUF]`) und benennt das
sprengende Element. Erst dann ist die eigentliche Layout-Ursache belegbar statt geraten.
