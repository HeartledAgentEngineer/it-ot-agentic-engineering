# Personenauswahl als alphabetische Liste (Schritt S8, 18.10.2026)

Sebastians Wunsch (16.10.2026, To-do Punkt 10): „Statt der jetzigen Ansicht eine **Liste mit
Suchzeile**, scrollbar und **alphabetisch sortiert** (mit **Buchstaben-Sprungmarken**)."
Dazu seine zwei Ergänzungen: **„Vorschläge" in dieser Ansicht entfernen** („Die Vorschläge sind
nur die zugeordneten Gruppen und sollen dort nicht stehen") und der Filter „mit/ohne Erinnerung"
(Erinnerung = aufgenommene Sprachnotiz im Profil).

## Welche Ansicht — die Entscheidung des Nachtlaufs

Der Plan lässt die Ansicht ausdrücklich offen („Personenauswahl oder Gruppenübersicht … sonst die
Personenauswahl nehmen") und verlangt, im Nachtlauf nicht zu fragen. **Gewählt: die
Personenauswahl** — der Reiter **„Benannt"** im 👥-Blatt, also die Liste, aus der eine Person zum
Ansehen und Bearbeiten aufgerufen wird. Gründe, am Code nachgemessen:

- Sie ist die einzige Stelle der App, die **Personen** auflistet und eine **Suchzeile** trägt
  (`#gruppen-benannt-filter`); die Gruppenübersicht listet Gruppen **ohne** Namen.
- Genau dort stand die **Zahl der Vorschläge** in jeder Zeile (`gruppenPersonInfo`) — Sebastians
  Befund trifft also diese Ansicht.
- Vorhandene oder umbenannte Funktionen werden nicht doppelt gebaut (kein zweiter Personen-Listen-Weg).

**Offen und ehrlich benannt:** hätte Sebastian die **Gruppenübersicht** gemeint, wäre die Sortierung
dort eine eigene, kleine Änderung (dieselben vier reinen Funktionen, andere Liste) — die
Sprungmarken sind bewusst so geschnitten, dass sie ohne Änderung übertragbar sind.

## Was der Code jetzt tut

- **Alphabetische Reihenfolge** (`gruppenPersonenSortiert`): sortiert wird nach dem Namen mit
  **aufgelösten Umlauten** („Öztürk" unter O, „Straße" als SS) — wie im Telefonbuch. Einträge, die
  nicht mit A–Z beginnen (Ziffern, Zeichen), stehen **hinten** unter „#". Die Reihenfolge der
  Server-Antwort bleibt unberührt (es wird kopiert, `zustand.personen` unverändert); gleiche
  Schlüssel behalten ihre Ordnung.
- **Buchstaben-Sprungmarken** (`gruppenSprungmarken`, `#gruppen-benannt-sprung`): je vorhandenem
  Buchstaben ein Knopf, A–Z, „#" zuletzt. Ein Klick **markiert** den ersten Eintrag dieses
  Buchstabens (`.gruppen-sprung-ziel`) und rollt ihn nach oben (`scrollIntoView`,
  `block: 'start'`) — markiert nur, **wählt nichts aus**. Bei nur einem Buchstaben bleibt die
  Leiste verborgen (sonst wäre sie Lärm).
- **Rollbereich**: `.gruppen-benannt-ansicht .gruppen-benannt-liste` bekommt `max-height: 60vh` und
  `overflow-y: auto`. Bewusst **nur** im Reiter „Benannt": die Gruppenübersicht trägt dieselbe
  Klassenkette (`gruppen-benannt-liste gruppen-liste`) und bleibt unverändert.
- **„Vorschläge" sind aus der Zeile entfernt.** Was bleibt: Gesichterzahl, Beziehung, Zahl der
  Erinnerungen, 📇 bei verknüpftem Kontakt. Die Infozeile nennt jetzt „alphabetisch".
- Die **Suchzeile** und der **Gruppenfilter** (15.10./16.10.) sind unverändert — sie wirken
  weiterhin zusammen (UND).
- Cache: `gruppen_quiz.js?v=20261018B`, `style.css?v=20261018B` (`index.html`).

## Belege (in diesem Lauf ausgeführt)

- **Neu** `frontend/tests/test_gruppen_personenliste.js` (Runtime-Vertrag, echte Handler in einer
  kleinen DOM-Umgebung, HTTP nur als Attrappe) **Exit 0**: Sortierung mit Umlauten und Ziffern am
  Ende, Sprungmarken nur für vorhandene Buchstaben, Sprung markiert genau einen Eintrag und rollt
  mit `block: 'start'`, bei einem Buchstaben bleibt die Leiste verborgen, die Vorschlagszahl steht
  nicht mehr in der Zeile, die Suchzeile filtert und sortiert neu.
- `frontend/tests/test_gruppen_quiz.js` **Exit 0** — dort sind die vier reinen Funktionen direkt
  geprüft (**10 neue Prüfungen** in zwei neuen Abschnitten); die Zeilen-Prüfung hält jetzt den
  neuen Text ohne Vorschlagszahl fest.
  `test_gruppen_liste.js`, `test_gruppen_auswahl.js` **Exit 0**; **alle 45 Frontend-Tests grün**
  (die 15 `app.js`-Prüfungen mit `app.js` als Argument).
- **Gegenprobe gegen den alten Stand** (HEAD-Fassungen von `gruppen_quiz.js`, `index.html`,
  `style.css` in einen Ordner **außerhalb des Repos** kopiert, dieselbe neue Prüfdatei):
  **alt 6 von 6 Prüfungen rot**, u. a. „erwartet ‚anna' zuerst: Tim", „kein eigener Rollbereich",
  Marken `[]`, „die Vorschlags-Zahl steht weiter in der Zeile: Anna130 Gesichter · **4 Vorschläge** ·
  2 Erinnerungen". Die vier Fähigkeiten gab es vorher nachweislich nicht.
- **Rendermessung im echten Browser** (Edge headless am echten `style.css`, Probeseite außerhalb des
  Repos, 60 Personenzeilen): **bei 1374 px** Liste `max-height 484,2 px`, `overflow-y auto`,
  `scrollHeight 3762 > clientHeight 484` → **rollbar**, Sprungleiste **eine** Zeile (18 px);
  **bei 496 px** Liste 424,2 px hoch und rollbar, Sprungleiste **zwei** Zeilen (40 px), Seite ohne
  Überlauf. Gegenprobe in derselben Messung: die **Gruppenübersicht** bleibt `max-height: none`,
  `overflow-y: visible`, nicht rollend.
- **Volles Tor** über den Commit-Haken: siehe Journal des Dauerlauf-Plans (Zahl dort).

## Ehrliche Grenzen

- Der **Filter „mit/ohne Erinnerung"** ist inzwischen gebaut (eigener kleiner Schritt, siehe
  `docs/changelog-2026-10-18-erinnerungsfilter.md`). **Noch nicht gebaut** sind das
  **Durcharbeiten der Personen ohne Erinnerung** (Sprachnotiz je Person) und das **Wischen** zur
  nächsten/vorherigen Person — sie gehören zum selben Punkt 10 und werden als eigene, kleine
  Schritte nachgeholt (jeder mit eigenem Prüfbefehl).
- **Nicht geprüft:** die Bedienung mit dem Finger am echten Gerät (Sprungmarken, Rollbereich) —
  das bleibt Sebastians Abnahme am Handy.
- Die Ansicht-Entscheidung ist die des Nachtlaufs (keine Rückfrage möglich) und oben begründet;
  bei Bedarf in einem Satz umkehrbar.
- Kein Bild, kein Vision-Aufruf, keine echten Personennamen (nur erfundene wie „Anna", „Öztürk"),
  keine Geräteeingriffe, nichts gelöscht. **Kosten 0 USD.**
