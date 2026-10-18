# Gruppen nach dem Zuordnen auflösen (To-do Punkt 14, 18.10.2026)

Sebastians Wunsch (16.10.2026): „Die Gruppen können nach dem Zuordnen auch aufgelöst werden."
Seine Klärung dazu: **„Die Gruppen sind nicht wichtig nach der Zuordnung."** — also
**automatisch**: sobald eine Gruppe einer benannten Person zugeordnet ist, wird der
**Gruppeneintrag** aufgelöst und die Gruppe steht nicht mehr als Gruppeneintrag in der Liste.
Zusätzlich ein Knopf für den Rest (die schon vorher zugeordneten Gruppen).

Harte Vorgabe aus dem Plan: „Auflösen darf **niemals** Bilder löschen oder Zuordnungen
verlieren — es entfernt nur den **Gruppeneintrag**. Die Gesichter bleiben der Person
zugeordnet. Vor dem Schreiben Trockenlauf und Zählung, und die Auflösung muss rückholbar
dokumentiert werden."

## Was der Code jetzt tut

- **Neue Stand-Liste `aufgeloest`** in `gruppen_quiz_stand.json` — genau die Ablage, in der
  schon `spaeter` und `unbekannt` stehen (`STAND_LISTEN`). Es wird **nur die Mitgliedschaft**
  vermerkt: Bilder, Gesichter, Vorschläge und Zuordnungen bleiben unangetastet, und die
  Adressdateien des Gruppierers (`personen_bestaetigt.json`, `personen_vorgaben.json`,
  `personen_beispiele.json`, `gesicht_zuordnung.jsonl`) werden nicht einmal angefasst
  (im Test byteweise gegengeprüft).
- **Automatisch beim Benennen**: die Antwort „Name" (und der übernommene Name bei
  „= dieselbe Person") löst genau die Gruppen auf, **die diese Antwort benannt hat**
  (`eintrag["namen_vorher"]`). Ein einzelnes Gesicht, das in der Gesamtansicht einer Person
  **zugeordnet** wird, löst **keine** Gruppe auf — eine Gruppe kann weitere, noch unbekannte
  Gesichter enthalten; das wäre keine Auflösung, sondern ein Verstecken.
- **Knopf „✂ Auflösen"** in der Gruppenübersicht an jeder Zeile mit Status „Benannt"
  (`#gruppen-liste-aufloesen-<Kennung>`). Er ruft erst `POST /api/gruppen/aufloesen` mit
  `trocken=true` (Server zählt: Gruppe, Person, Gesichter; schreibt nichts), zeigt die Zahl
  in der Meldung und schreibt dann. Idempotent: ein zweiter Lauf findet den Zustand und
  schreibt nicht noch einmal.
- **Status „Aufgelöst"** als eigener Reiter im Statusfilter der Gruppenübersicht
  (Offen · Später · Benannt · **Aufgelöst** · Ausgeblendet) samt der Zeilen dort. An einer
  aufgelösten Zeile steht **„↩ Zurück in die Liste"** — der Umkehrweg. „benannt" bleibt die
  volle Zahl: die Person behält ihre Gesichter, die Fortschrittszeile („x von y Vorschlägen
  benannt") ändert sich deshalb nicht.
- **Rückgängig**: `rueckgaengig()` nimmt eine Auflösung Schritt für Schritt zurück (auch die
  Position in der Liste, wie bei `spaeter`/`unbekannt`); `art='offen'` holt eine aufgelöste
  Gruppe direkt zurück in die Liste. Für eine **nicht** aufgelöste, benannte Gruppe bleibt die
  bisherige Sperre („Benannte Gruppen können nicht zurück zu Offen gesetzt werden.").
- **Alte Stand-Datei bleibt lesbar**: die am Handy liegende Fassung mit nur zwei Listen läuft
  unverändert weiter (`_stand_lesen` füllt fehlende Listen mit leer).

Geändert: `backend/app/services/gruppen_quiz.py` (Stand-Listen, `_gruppen_status`, `liste`,
`stand`, `_antwort_anwenden`, neue Funktion `aufloesen`), `backend/app/router/gruppen.py`
(Route `POST /api/gruppen/aufloesen`, Statusfilter der Liste, Kopfkommentar),
`frontend/gruppen_quiz.js` (`LISTEN_STATUS`, Auflösen-Knopf, `gruppeAufloesen`,
Umkehrweg-Beschriftung), `frontend/index.html` (Reiter „Aufgelöst"),
`frontend/style.css` (`flex-wrap` + Mindestbreite für den Statusfilter).
Cache: `gruppen_quiz.js?v=20261018F`, `style.css?v=20261018C`.

## Belege (in diesem Lauf ausgeführt)

- **Neu** `backend/tests/test_gruppen_aufloesen.py` — **15 passed**: automatisches Auflösen beim
  Benennen (Liste, Zählung, Dateiinhalt), die Person behält Vorschlag und Gesichter (40 Gesichter,
  Gruppe weiter aufrufbar), Zuordnungsdateien byteweise unverändert, verbundene Gruppe („= dieselbe
  Person") wird mit aufgelöst, **Trockenlauf schreibt nichts** (Dateivergleich vor/nach),
  Schreiben fasst nur Stand-Datei/Protokoll/Namen-Datei an, zweiter Lauf idempotent, ausgeschlossene
  Gesichter zählen nicht mit (40 → 38), Auflösen nur für zugeordnete Gruppen (offen/unbekannt/leer →
  ehrliche deutsche Meldung, nichts geschrieben), Rückgängig in drei Schritten, Reihenfolge,
  Umkehrweg `art='offen'` samt bleibender Sperre, beide Routen, alte Stand-Datei ohne
  `aufgeloest` läuft weiter.
- **Angepasst** `backend/tests/test_gruppen_liste.py` (5 Stellen): die Stand-Datei trägt jetzt die
  dritte Liste — die Vergleiche nennen sie mit. Zusammen mit den bestehenden Gruppen-Tests
  (`test_gruppen_quiz.py`, `test_gruppen_quiz_video.py`, `test_gruppen_diagnose.py`,
  `test_erzaehlen_personen.py`, `test_import_status.py`): **189 passed**.
- **Frontend** `frontend/tests/test_gruppen_liste.js` um `aufloesenRuntime` erweitert (echte Handler,
  HTTP nur als Attrappe): an der benannten Zeile steht der Auflösen-Knopf, ein Klick schickt **erst
  `trocken=true`, dann `trocken=false`** (Reihenfolge im Anfrageprotokoll festgehalten), die Meldung
  nennt die gezählten Gesichter und die Person, der Rückgängig-Knopf erscheint, die Liste wird ab
  Seite 1 neu geladen; an der aufgelösten Zeile steht „↩ Zurück in die Liste", ein Klick schickt
  `art='offen'` und meldet „Wieder in der Gruppenliste". **Exit 0**; `pytest
  tests/test_frontend_node.py -q` → **48 passed** (alle Frontend-Prüfdateien).
- **Gegenprobe gegen den HEAD-Stand** von `gruppen_quiz.js` (Kopie außerhalb des Repos, dieselbe
  Prüfdatei): **rot** — es geht **keine** Anfrage an `/api/gruppen/aufloesen` (`[]` statt der zwei
  erwarteten Aufrufe); die Fähigkeit gab es vorher nachweislich nicht.
- **Rendermessung im echten Browser** (Edge headless, echtes `index.html` + echtes `style.css`,
  Skript außerhalb des Repos): **ein Befund und behoben** — mit fünf Knöpfen lag bei **380 px**
  „Ausgeblendet" außerhalb des Fensters (gemessen: `überbreit: ["gruppen-liste-status-ausgeblendet"]`).
  Nach `flex-wrap: wrap` + Mindestbreite 84 px: **380 px → zwei Zeilen, 93 px hoch, kein
  überbreites Element, Dokument 380 = Fenster 380**; 496 px und 1400 px → eine Zeile (50 px), alles
  im Fenster. Die Auflösen-/Zurück-Knöpfe einer Zeile messen bei 380 px 55 px Höhe (bedienbar), bei
  496/1400 px 40 px.
- **Volles Tor** über den Commit-Haken: siehe Commit-Zeile im Bericht (Baseline 4743 + 15 neue
  Backend-Tests).

## Ehrliche Grenzen

- Gemessen sind die Regel (Backend, echte Funktionen am echten Dateiformat) und der Oberflächenweg
  mit gestellten Antworten. Die **Abnahme mit dem Finger am Gerät** (Knopf drücken, Reiter
  wechseln) bleibt Sebastians Schritt.
- Die Automatik wirkt beim **Benennen** im Quiz und beim Knopf in der Gruppenübersicht; ein in der
  Gesamtansicht **zugeordnetes Einzelgesicht** löst absichtlich keine Gruppe auf (Begründung oben).
- Die Auflösung entfernt nur den Listeneintrag — bestehende Gruppen am Handy, die vor dem 18.10.
  benannt wurden, bleiben in der Liste stehen, bis sie einmal „aufgelöst" werden (Knopf).
- Kein Backend-Bilddienst, kein Vision-, kein pCloud-Schreibzugriff, keine Geräteeingriffe,
  keine echten Personennamen in Tests und Bericht. **Kosten 0 USD.**
