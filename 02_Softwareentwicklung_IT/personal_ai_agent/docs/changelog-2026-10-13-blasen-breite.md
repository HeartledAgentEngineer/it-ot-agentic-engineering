# Changelog 13.10.2026 – Ansicht springt nicht mehr nach rechts

## Anlass

Sebastian, 12.10.2026, unterwegs am Handy: Er sprach etwas ein, und die Antwort lief ein. Sobald
die Ausgabe voll war, sprang die ganze Ansicht nach rechts, und der Vorlese-Knopf war verschwunden.
Erst ein Neustart der App half.

## Ursache (gemessen, nicht vermutet)

Nachgestellt in der statischen Vorschau bei 375 × 812 px mit einer Antwort, die eine Tabelle enthält:

- Eine Chat-Blase ist eine Flex-Zeile: innere Spalte (Blaseninhalt, Zeit, Antwort-Knopf) und daneben
  `.speak-controls`.
- Die innere Spalte entsteht in `addMessage` (`frontend/app.js`). Sie hatte kein `min-width`. Als
  Flex-Kind gilt dann `min-width: auto`, die Spalte kann also nicht schmaler werden als ihr breitester
  Inhalt.
- Eine Tabelle mit langen Spaltenköpfen hat eine große Mindestbreite. Die Spalte wurde dadurch
  **358 px** breit, obwohl die Zeile nur **338 px** Platz hat.
- `.speak-controls` wurden über den rechten Rand geschoben. `#chat-container` hatte `scrollWidth`
  **406** bei `clientWidth` **370**. Wegen `overflow-x: hidden` war der Knopf nicht mehr erreichbar.

## Änderung

- `frontend/app.js` `addMessage`: Die innere Spalte bekommt `min-width:0`. Die Tabelle scrollt jetzt
  nur in ihrer eigenen Hülle `.table-wrap` (`overflow-x: auto`, gab es schon).
- Live gemessen nach dem Fix:
  - `scrollWidth` des Chats liegt bei 370 und ist damit gleich `clientWidth`.
  - Der rechte Rand des Vorlese-Knopfs liegt bei 354 px, also innerhalb von 375.
- `index.html`: `app.js?v=20261013A` (Cache-Bump); `tests/test_foto_galerie.js` prüft die neue
  Kennung.

## Test

- Neu `frontend/tests/test_blasen_breite.js`. Er läuft über `backend/tests/test_frontend_node.py`
  automatisch im Prüfbefehl mit und prüft zwei Dinge:
  - Die innere Spalte bleibt eine Flex-Spalte mit `min-width:0`.
  - `.table-wrap` scrollt waagerecht.
- Rotprobe: Gegen den alten Stand von `app.js` schlägt der Test fehl, mit 1 Fehler (`min-width:0`).

## Grenzen

- Der Test prüft den Quelltext, nicht das gerenderte Layout. Die Messung im Browser ist oben
  dokumentiert.
- Der Handytest durch Sebastian steht aus: Nach dem Push eine lange Antwort mit Tabelle abwarten. Der
  Vorlese-Knopf muss sichtbar bleiben.
