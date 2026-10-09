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

## Gesichter fest einer Person zuordnen

Befund am Handy: Mehrere große Vorschläge mischen Personen, vor allem Kinderfotos aus dem
Fotobuch (Sebastian, sein Zwilling Julian, Bruder David). Bisher gab es nur „🚫 ausschließen“.
Danach gehörte das Gesicht niemandem mehr und musste beim nächsten PC-Lauf neu einsortiert
werden.

**Neu im Backend** (`backend/app/services/gruppen_quiz.py`, `backend/app/router/gruppen.py`):
- `POST /api/gruppen/zuordnen` nimmt `{name, gesichter: [{kennung, gid}]}` an. Die Form ist
  dieselbe wie bei `/person/ausschliessen`.
- Die Person muss schon benannt sein. Jedes Gesicht muss zu der Kennung gehören, die mitkommt.
- Das Gesicht verlässt seinen alten Vorschlag. Dafür entsteht ein Eintrag unter
  `ausgeschlossen`, im Format, das `personen_gruppieren.py` schon liest.
- Zusätzlich hängt das Gesicht fest an der Person. Dafür entsteht ein Eintrag unter
  `zugeordnet` in `personen_vorgaben.json`: `{bild_id, index, name, kennung, aktion}`.
- Gibt es für dasselbe Gesicht mehrere Einträge, gilt der letzte. Umhängen und Zurückhängen
  funktionieren also.
- Die Zuordnung wirkt am Handy sofort an diesen Stellen:
  - Gesamtansicht der Person
  - Personenliste (Zahl der Gesichter)
  - „Bilder mit …“ (`bilder_mit`)
  - Erzählen (`personen_auf_bildern`, `gesichter_auf_bild`)
- Nach einem neuen PC-Lauf liegt ein Gesicht oft unter einer anderen Kennung. Die
  Personenansicht findet es dann über `bild_id:index` trotzdem.
- Ein Protokolleintrag deckt alle markierten Gesichter ab. Rückgängig nimmt die Zuordnung und
  die dazu angelegten Ausschlüsse in einem Schritt zurück.

**Zeitblöcke und Video-Hinweis:**
- `GET /api/gruppen/gesichter` kennt jetzt `ordnung=guete|zeit`. Mit `zeit` wird nach
  Aufnahmedatum sortiert, Gesichter ohne Datum kommen zuletzt.
- Die Antwort für einen Vorschlag enthält `videos`, die Zahl seiner Gesichter aus Videos.
- Befund zu Vorschlag 064: 89 Vorschläge bestehen nur aus Video-Standbildern. Die
  Gesamtansicht zeigt bisher nur Fotos, deshalb blieb sie bei diesen Vorschlägen
  kommentarlos leer.

**Oberfläche** (`frontend/gruppen_quiz.js`, `index.html`, `style.css`):
- In „Alle Gesichter“ gibt es neben 🚫 jetzt **👤 Zuordnen**. Ein Tipp darauf zeigt die
  benannten Personen als Knöpfe; die gerade offene Person fehlt in der Liste.
- Ein Tipp auf einen Namen ordnet alle markierten Gesichter dieser Person zu.
- **📅 Nach Jahren** schaltet auf Zeitblöcke mit Jahresköpfen. Die Wahl bleibt für die
  Sitzung erhalten.
- Von Hand zugeordnete Gesichter tragen unten links ein 👤.
- Ein Vorschlag nur aus Videos zeigt jetzt eine klare Meldung: Bitte mit „⏭ Weiter (später)“
  überspringen. Bei gemischten Vorschlägen nennt die Infozeile die Zahl der nicht
  gezeigten Video-Gesichter.
- Cache-Kennungen: `gruppen_quiz.js?v=20261010A`, `style.css?v=20261010A`.

**Prüfung:**
- `backend/tests/test_gruppen_quiz.py`: 11 neue Testfälle (7 Funktionen, eine davon mit
  5 Varianten). Sie decken ab:
  - Zuordnen aus einem fremden Vorschlag mit Wirkung auf Personen, Register und Erzählen
  - Lesbarkeit der Datei für den Gruppierer
  - Rückgängig
  - Umhängen und Zurückhängen
  - mehrere Gesichter in einem Rückgängig-Schritt
  - ungültige Eingaben, bei denen nichts geschrieben wird
  - Sortierung nach Zeit und Video-Zählung
  - die Routen
  - Kennungswechsel nach einem neuen PC-Lauf
- Die Testdatei läuft mit 87 passed.
- `frontend/tests/test_gruppen_quiz.js`: 15 neue Prüfungen. Die Infozeile ist auf den neuen
  Text angepasst. In `test_foto_galerie.js` ist nur die festgeschriebene `style.css`-Kennung
  nachgezogen.

**Noch offen:**
- **PC-Seite:** `personen_gruppieren.py` liest `zugeordnet` noch nicht. Beim nächsten
  vollen Lauf am PC bleibt das Gesicht nur aus dem alten Vorschlag ausgeschlossen, landet
  aber noch nicht sicher bei der Person.
- Die Zuordnungen am Handy bleiben in `personen_vorgaben.json` erhalten und wirken dort weiter.
- Video-Gesichter anzeigen (Standbild aus dem Video) ist ein eigener Schritt.
- Die Oberfläche ist noch nicht im Browser und noch nicht am Handy angesehen.
