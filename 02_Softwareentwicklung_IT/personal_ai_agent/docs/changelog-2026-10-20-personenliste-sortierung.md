# Änderungsprotokoll 20.10.2026: Personenliste „Benannt“ — Sortierung statt Gruppenfilter

## Anlass
Sebastian zur Filterzeile im Reiter „Benannt“ (Fenster „Personen benennen“):
„Alle Gruppen brauchen wir nicht als Filter, alle Erinnerungen ohne und mit
brauchen wir auf jeden Fall. Personensuchen ist auch super. Und wir wollen auch
eine Sortierung haben … alphabetisch, aber auch mit den meisten Bildern.“

## Umfang
Nur Frontend (`frontend/index.html`, `frontend/gruppen_quiz.js`). Die Backend-API
`/api/gruppen/personen` bleibt unverändert; das Feld `gruppen` je Person wird
weiter geliefert, die Oberfläche liest es nicht mehr.

## Änderung
- **Gruppenfilter entfernt:** `<select id="gruppen-benannt-gruppe">`, `gruppenAuswahlFuellen()`
  samt beider Aufrufe in `personenLaden`, der `change`-Listener, `zustand.personenGruppe`,
  der Gruppen-Anteil in `personenGefiltert`/`personenZeigen` (Infozeile) und im
  „Filter zurücksetzen“. Die dadurch unbenutzten reinen Helfer `gruppenPersonGruppen`,
  `gruppenPersonPasstGruppe`, `gruppenAuswahlText`, `gruppenAuswahlEintraege` sind
  gelöscht (vorher per grep über `frontend/` und `docs/` geprüft: sonst nirgends benutzt).
  `gruppenVorschlagKopf`, `gruppenNummer`, `gruppenZeitraum` bleiben (Personenansicht).
- **Neue Auswahl** `#gruppen-benannt-sortierung` (`index.html:458`, `aria-label="Sortierung der Personenliste"`)
  an der Stelle des Gruppenfilters: „Alphabetisch“ (Wert leer) und „Meiste Fotos zuerst“
  (Wert `meiste`). Wert in `zustand.personenSortierung`; ein Wechsel zeichnet die Liste neu.
- **Eine Regel für Liste, Weiter-Weg und Wischen:**
  - `gruppenPersonenSortiert(personen, art)` (`gruppen_quiz.js:371`) bekommt die Sortierart.
    `meiste`: nach `gesichter` absteigend, bei Gleichstand nach `gruppenSortierName`
    (Umlaute aufgelöst, wie bisher). Fehlende, negative oder ungültige Zahl zählt als 0.
    Es wird eine Kopie sortiert; die Server-Liste im Zustand bleibt unberührt.
    Hilfen: `gruppenSortierArt` (nur `meiste` oder leer, alles andere = alphabetisch),
    `gruppenGesichterZahl`.
  - `gruppenPersonenGefiltert(personen, frage, erinnerung, sortierung)` (`:437`,
    Parameter `gruppe` entfällt) filtert (Suche UND Erinnerung) und sortiert dann mit
    der gewählten Art. `personenGefiltert()` reicht `zustand.personenSortierung` durch;
    dieselbe Funktion bedient die Liste, den „Nächste ohne Erinnerung“-Knopf und das
    Wischen/die Pfeiltasten — die angezeigte Reihenfolge ist die Wisch-Reihenfolge.
- **Sprungleiste A–Z** nur bei alphabetischer Sortierung; bei „Meiste Fotos zuerst“
  bleibt sie leer und versteckt, die Zeilen tragen kein `data-sprung`.
- **Infozeile:** „· alphabetisch ·“ bzw. „· meiste Fotos zuerst ·“ je nach Wahl.
- **„Filter zurücksetzen“** leert Suche und Erinnerungsfilter, die Sortierung bleibt
  stehen (sie ist kein Filter); sie bleibt auch nach Reiterwechsel/Neuladen der Liste.
- Kommentare in `gruppen_quiz.js` und `index.html` an den neuen Stand angepasst.

## Cache-Kennung
`frontend/index.html:724`: `gruppen_quiz.js?v=20261020A` → `?v=20261020B`.
`style.css` unverändert (keine CSS-Änderung; die Auswahl nutzt die Stile der
bisherigen Filterzeile).

## Prüfung
- `frontend/tests/test_gruppen_personenliste.js`: neue Prüfungen `sortierungImHtml`
  (kein `gruppen-benannt-gruppe` mehr in HTML und Skript, Sortier-Select mit beiden
  Optionen, Cache-Kennung ≥ `20261020B`), `sortierungMeisteFotosZuerst` (Reihenfolge,
  Gleichstand alphabetisch, Infozeile, Sprungleiste weg/zurück), `filterUndSortierungWirkenZusammen`
  (Suche + Erinnerung + Sortierung), `zuruecksetzenLaesstDieSortierungStehen`,
  `reineSortierung` (fehlende/ungültige Zahl = 0, Eingabeliste unverändert).
- `frontend/tests/test_gruppen_quiz.js`: reine Prüfungen zur Sortierung; Prüfungen
  der entfernten Gruppen-Helfer gelöscht; `#gruppen-benannt-sortierung` statt
  `#gruppen-benannt-gruppe` in der Verdrahtungsliste.
- `frontend/tests/test_gruppen_liste.js`: Test `personenGruppenFilterInBenannt` gelöscht.
- `frontend/tests/test_gruppen_wischen.js`: `wischenFolgtDerSortierung` und
  eine Prüfung der Reihe nach Fotos in `reineRegelNachbar`.
- Lauf: alle `frontend/tests/*.js` einzeln mit dem Argument aus
  `backend/tests/test_frontend_node.py`, dazu `pytest tests/test_frontend_node.py`
  (siehe Abschlussbericht des Arbeitslaufs).

## Grenzen
- „Meiste Fotos“ ist die Zahl der **erkannten Gesichter** der Person (`gesichter`
  vom Server: Summe der Gesichter ihrer Vorschläge, abzüglich ausgeschlossener,
  zuzüglich fest zugeordneter; `gruppen_quiz.py` um Zeile 1393-1411), nicht die
  Zahl verschiedener Bilddateien: zeigt ein Foto dieselbe Person zweimal, zählt es
  doppelt. Ob Video-Gesichter in der Gruppengröße stecken, hängt vom Server ab
  und wurde hier nicht geprüft.
- Es gibt keine weitere Sortierart (z. B. nach Erinnerungen oder Datum) und keine
  Umkehrung der Reihenfolge.
- Die Wahl der Sortierung gilt nur für die laufende Sitzung der Seite
  (kein Speichern über einen Neustart der App hinaus).
- Die bisherige Eingrenzung auf eine Gesichtsgruppe in „Benannt“ ist nicht mehr
  möglich; die Gruppenübersicht im Reiter „Offen“ ist davon unberührt.
- Alte Änderungsprotokolle (`changelog-2026-10-16-gruppenfilter-benannt.md` u. a.)
  beschreiben den Stand vor dieser Änderung und sind bewusst nicht umgeschrieben.
