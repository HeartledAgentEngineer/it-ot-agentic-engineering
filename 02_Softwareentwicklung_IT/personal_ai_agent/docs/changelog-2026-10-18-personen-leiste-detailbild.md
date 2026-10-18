# 18.10.2026 — Schritt F: Personen-Leiste im Detailbild (Rahmen der angeklickten Person)

Plan „Rahmeneditor im Detailbild" (Fassung 13), Abschnitt 4, **Schritt F**
(„Bedienfeld überall erreichbar", Auftragspunkt 5) und Sebastians Wunsch aus To-do-Punkt 6 (S9):
*„unten die Personen durchklicken → der zugehörige Rahmen wird im Bild gezeigt"*.

## Was neu ist

| Ort | Neu |
|---|---|
| `frontend/app.js`, `rahmenPersonenLeiste(e, gesichter, pfad)` | **Rein:** je **Rahmen** mit bekannter Person ein Eintrag `{ idx, person }` in Rahmen-Reihenfolge. Quelle: der eigene Eintrag `personen[idx]` (Schritt G), sonst die für diese Region **bestätigten** Namen (`gesichter[idx].bestaetigt` bzw. der lokale Merker — dieselbe Quelle wie die Quiz-Suche). Ein ausdrücklich „unbekannter" Rahmen (`''`, Schritt E) bekommt **keinen** Eintrag; die **globale** Zielperson zählt nicht (sie gilt fürs ganze Bild). Jede Person genau einmal — der erste Rahmen gewinnt |
| `frontend/app.js`, `rahmenWahlAusLeiste(e, gesichter, pfad, person)` | **Rein:** Rahmen-Index zu einer angeklickten Person; `-1`, wenn die Person nicht in der Leiste steht (dann wird **nichts** ausgewählt statt des falschen Rahmens) |
| `frontend/app.js`, `zeigeBildVollbild` (Werkzeugleiste) | Neue Leiste `vollbild-personen-leiste` mit Knöpfen je Person: ein Klick setzt `sel` auf **ihren** Rahmen (`resync()` + `zeigeAuswahlGriffe()`) — der Rahmen wird **grün** hervorgehoben und bekommt seine Griffe. Der angewählte Knopf ist markiert (`aria-pressed`, grüne Farbe). **Nicht** in der Referenz-Nachbearbeitung; ohne bekannte Person bleibt die Leiste ganz weg |
| `frontend/app.js`, `zeigeAuswahlGriffe()` | malt die Personen-Leiste mit (der aktive Knopf folgt der Auswahl) |
| `frontend/app.js`, `zeigeBildVollbild` | merkt die Gesichtsliste des offenen Bildes (`_quizEditor.gesichter`) — Grundlage der Namenszuordnung |
| `frontend/index.html` | Cache-Schlüssel `app.js?v=20261018K` → **`20261018L`** |

## Ausdrücklich NICHT geändert

- **Kein Speichern** aus der Leiste, kein Server-Schreibvorgang: der Klick wählt nur aus. Die Riegel
  aus A2 (kein Speichern ohne passendes Ziel) und E (unbekannter Rahmen) sind unverändert.
- Die **Werkzeugleiste** selbst (Reihenfolge/Knöpfe) ist unverändert; die Leiste hängt als absolut
  gesetztes Kind **über** ihr und ist aus dem Fluss heraus (sie verschiebt keinen Knopf).
- Video-Kacheln, Gruppen-/Personenansicht und `frontend/gruppen_quiz.js` sind **nicht** angefasst.

## Belege (in diesem Lauf selbst ausgeführt)

- **Neuer Test** `frontend/tests/test_quiz_rahmen_personen_leiste.js` — **30 Prüfungen, Exit 0**:
  eigene Personen (G) je Rahmen, bestätigte Namen aus der Gesichtsliste, lokaler Merker,
  „unbekannt" bekommt **keinen** Namen, globale Zielperson erzeugt **keine** Einträge, doppelte
  Person nur einmal (erster Rahmen), Klick wählt genau den Rahmen (auch bei anderer Schreibweise,
  mit Leerraum), unbekannte/leere Person → `-1`, leere Plätze sind keine Rahmen (Index bleibt echt),
  plus Quelltext-Wächter (Verdrahtung, Ausblenden ohne Inhalt, Cache-Schlüssel).
- **Gegenprobe** gegen `git show HEAD:.../frontend/app.js`: derselbe Test bricht mit
  **Exit 1** ab — `Funktion nicht gefunden: rahmenPersonenLeiste`; die Fähigkeit gab es vorher
  nachweislich nicht.
- **Rendermessung im echten Browser** (Edge, Belegskript außerhalb des Repos
  (`…/hermes/cache/scratch/f_personen_leiste_messen3.js`), echte `index.html` + `app.js`,
  echter Aufruf `zeigeBildVollbild(...)` mit zwei Gesichtsregionen und den Namen „Anna"/„Tim"):
  - **1400 px:** Leiste 163 × 41 px, **über** der Werkzeugleiste, **keine** Überlappung
    (`ueberlapptWerkzeug: false`), Dokument-Überlauf **0**; Klick auf „Tim" → `aria-pressed` „true",
    Knopf grün (rgb(153,255,153) auf rgb(42,83,56)) und **Rahmen `data-frei="1"` wechselt von
    rgb(255,255,102) auf rgb(68,255,68)** (Hervorhebung); Rahmen 0 unverändert.
  - **380 px:** dasselbe (Leiste 108–272 px, Überlauf 0, Hervorhebung des zweiten Rahmens).
  - **keine JS-Fehler** (`page.on('pageerror')` = leer).
- **Roter Fund im eigenen Bau (ehrlich):** die erste Fassung lag mit `bottom:124px` **19 px IN der
  Werkzeugleiste** (gemessen: Leiste 735–776 px, Werkzeugleiste 757–826 px) — die Werkzeugleiste ist
  69 px hoch, nicht ~40. Behoben, indem die Leiste als absolut gesetztes Kind mit `bottom:100%`
  **an** der Werkzeugleiste hängt (kein fester Pixelwert mehr); Nachmessung siehe oben.
  Beide Messskripte liegen als Beleg im Scratch (`…_messen2.js` = roter Befund, `…_messen3.js` = grün).
- **Gegenmessung der Werkzeugleiste ohne diese Änderung** (Kopie der HEAD-Fassungen im Scratch,
  dasselbe Skript): bei 380 px ist die Werkzeugleiste **schon vorher** 511 px breit (links −66 px) —
  dieselben Zahlen wie nachher. Die waagerechte Ausdehnung der Werkzeugleiste auf schmalen Geräten
  ist also **älter als dieser Schritt** und nicht von der Leiste verursacht (absolut gesetztes Kind
  ändert die Breite des Elternkastens nicht).
- `pytest tests/test_frontend_node.py -q` → **45 passed** (44 vorher + dieser Test).

## Ehrliche Grenzen

- **Die erste Hälfte des F-Kriteriums ist nicht erfüllt und wurde deshalb gemessen statt behauptet:**
  „Test, dass die Ansicht aus dem Personenweg **mit** Kontext geöffnet wird" ist heute nicht baubar —
  die Ansicht „Benannt"/Gruppen liefert **keine Bildzeile**, sondern nur eine pCloud-**Kennung**
  (`gruppen_quiz.py::_beispiel_fuer_anzeige` gibt genau `fileid`, `index`, `bbox`, `breite`, `hoehe`;
  `frontend/gruppen_quiz.js:473` ruft `zeigeBildVollbild(gross, gesicht ? [gesicht] : [])` **ohne**
  `bildPfad`), und `editorSpeicherZiel` verlangt Übereinstimmung mit einer **offenen Quizrunde**
  (`_aktuellerQuizPfad`). Ein „Kontext" für kennungsbasierte Bilder braucht erst eine eigene Identität
  (und die Entscheidung, ob Rahmen dort überhaupt schreibbar sein sollen) — das ist ein **eigener
  Schritt F2** und gehört dem Plan-Eigentümer/Sebastian, nicht in diesen Durchlauf.
- Geprüft sind Mechanismus und Darstellung; die **Abnahme am Gerät** (Person antippen → der richtige
  Rahmen leuchtet) bleibt Sebastians Schritt am Handy.
- Die Leiste zeigt nur Personen, die der Client **weiß** (eigener Eintrag oder bestätigter Name). Ein
  Bild ohne bekannte Namen hat damit **keine** Leiste — gewollt (nichts erfinden), aber es heißt auch:
  im Quiz erscheint sie erst, wenn die Regionen bestätigte Namen tragen.
