# Changelog 06.10.2026 — Gesichts-Markierung in der Personen- und Gruppenansicht

## Anlass

Beim Benennen und Prüfen von Personengruppen war auf den Kacheln nicht
erkennbar, **welches Gesicht** im Foto zur Gruppe gehört. Bei Gruppenfotos
ließ sich damit nicht beurteilen, ob die richtige Person zugeordnet wurde —
falsche Gesichter im Bestand verfälschen später jede Zuordnung
(„wer war wo dabei").

## Was neu ist

**`frontend/gruppen_quiz.js`**

* Die Kachelansicht (Gruppenansicht „Alle N Gesichter" und die Vorschläge in
  der Personenansicht) öffnet das große Foto jetzt **mit gelbem Rahmen genau
  um das Gesicht, das zu dieser Gruppe gehört**. Die Markierung kommt aus den
  gespeicherten Werten `bbox` (= `[x, y, Breite, Höhe]` in Originalpixeln),
  `breite`/`hoehe`; die Anzeige rechnet mit `bbox_norm` (0…1), damit Zoom und
  Drehung den Rahmen am Gesicht lassen.
* Fehlen Maße oder ist die `bbox` unbrauchbar, wird **nichts** markiert — lieber
  kein Rahmen als ein Rahmen auf dem falschen Fleck.
* Neue reine Funktionen: `gesichtKennung(beispiel)` (die Gesichterliste liefert
  `fileid`, die Personenvorschläge `bild_id` — beides wird jetzt bedient) und
  `gesichtRahmen(beispiel)` (normiert die bbox für die Gesamtansicht).

**`frontend/index.html`** — Versions-Kennung für `gruppen_quiz.js` hochgezogen
auf `20261006E` (harte Zwischenspeicherung im Browser, Hausregel).

**`frontend/tests/test_gruppen_quiz.js`** — 11 neue Prüfungen für
`gesichtKennung` und `gesichtRahmen` (Normierung, Vorrang von `fileid`,
Rückfall auf `bild_id`, Null-Fälle). Aufruf wie gehabt:
`node tests/test_gruppen_quiz.js gruppen_quiz.js`.

## Prüfstand

* `node --check frontend/gruppen_quiz.js` → ok
* `node frontend/tests/test_gruppen_quiz.js` → **alle Prüfungen grün**
* Alle 25 Frontend-Tests grün (Aufruf mit Quelldatei:
  `node tests/<test>.js app.js` bzw. `… gruppen_quiz.js`).
* Backend-Prüfbefehl: siehe Commit (unverändert, die Änderung ist rein
  Frontend).

## Was das Werkzeug bewusst nicht tut

* Keine Änderung an gespeicherten Gesichtsdaten — es wird nur **angezeigt**.
* Kein neuer Backend-Aufruf: `bbox`, `breite`, `hoehe` liefern die vorhandenen
  Endpunkte `/api/gruppen/gesichter` und `/api/gruppen/person` bereits.
