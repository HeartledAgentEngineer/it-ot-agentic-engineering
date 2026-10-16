# Gruppenfilter in der Ansicht „Benannt“ (16.10.2026)

Dauerlauf-Schritt **S5** (To-do Punkt 2b). Wunsch Sebastian, wörtlich:

> „Und du hast doch diese Gruppenansicht hinzugefügt. Ich wollte aber eigentlich
> das, was unter Gruppenansicht heißt, einfach unter Benannt noch mal als
> Filterauswahl haben, weil eigentlich finde ich diese ganze Ansicht, die man
> unter Benannt hat, sehr, sehr schön.“

Die Ansicht „Benannt“ bleibt also **wie sie ist** — es kommt nur die
Filterauswahl hinzu.

## Ausgangslage (im Code nachgelesen)

- Die Gruppenansicht (`#gruppen-liste-ansicht`) filtert nach **Status**:
  `Offen · Später · Benannt · Ausgeblendet` (`LISTEN_STATUS` in
  `frontend/gruppen_quiz.js`).
- „Benannt“ (`#gruppen-benannt-ansicht`) zeigt zusammengefasste Personen
  (eine Person = alle Vorschläge desselben Namens) und hatte bisher nur eine
  **Namenssuche** (`#gruppen-benannt-filter`).
- Statusfilter wären in einer Liste, in der **alle** schon benannt sind, nicht
  unterscheidend. Die kleinste sinnvolle Auslegung von „nach einer Gruppe
  filtern“ (so im Auftrag festgehalten) ist deshalb: **eine konkrete
  Gesichtsgruppe auswählen** und sehen, welche benannte Person dazu gehört.
- `gruppen_quiz.personen()` lieferte dafür die Kennungen der Gesichtsgruppen
  **nicht** mit.

## Änderung

### Server: nur Gruppenmetadaten, keine Bilddaten

`backend/app/services/gruppen_quiz.py`:

- neu `_personen_gruppen(kennungen, nach_kennung, aus)` — je Person eine Liste
  `{kennung, groesse, von, bis}`, größte zuerst; die Größe zählt
  **ausgeschlossene** Gesichter ab (wie die Gesamtzahl daneben);
- `personen()` gibt dieses Feld als **`gruppen`** mit aus. Es sind
  ausschließlich Metadaten: **keine** `fileid`, **keine** `bbox`, kein Beispiel —
  die Route `/api/gruppen/personen` bleibt damit frei von Bilddaten.

### Oberfläche

`frontend/index.html` (Ansicht „Benannt“): die Eingabezeile bekommt

```html
<select id="gruppen-benannt-gruppe" aria-label="Nach einer Gesichtsgruppe filtern">
    <option value="">Alle Gruppen</option>
</select>
<button id="gruppen-benannt-filter-zuruecksetzen" class="gruppen-knopf" type="button">Filter zurücksetzen</button>
```

`frontend/gruppen_quiz.js`:

- reine Helfer `gruppenPersonGruppen`, `gruppenPersonPasstGruppe`,
  `gruppenAuswahlText`, `gruppenAuswahlEintraege` (Auswahlliste: alle Gruppen der
  geladenen Personen, **ohne Doppelte**, größte zuerst);
- `gruppenAuswahlFuellen()` füllt das Auswahlfeld nach jedem Laden der
  Personenliste; eine gewählte Gruppe bleibt stehen, solange es sie noch gibt;
- `personenZeigen()` filtert mit **beiden** Filtern (Namenssuche **und**
  Gruppe = UND-Verknüpfung) und nennt die gewählte Gruppe in der Infozeile;
- „Filter zurücksetzen“ leert **beide** Filter und setzt den Fokus zurück in die
  Suche.

`frontend/style.css`: die Zeile darf umbrechen (`.gruppen-benannt-filter-zeile`),
Auswahlfeld im Stil der übrigen Eingabefelder.

## Beleg — echter Browser, gemessen (nicht gerechnet)

Belegskript **außerhalb** des Repos
(`…/cache/scratch/benannt_filter_messen.js`, Puppeteer + Edge) lädt die **echte**
`style.css` mit der echten Markup-Struktur der Zeile und misst die echten
Elementgrößen:

| Fensterbreite | Zeilen im Fluss | Überlauf der Zeile | Breite Suchfeld | Breite Auswahl | Breite Knopf |
|---|---|---|---|---|---|
| 1400 px | 1 | 0 | 604 px | 604 px | 144 px |
| 1000 px | 1 | 0 | 404 px | 404 px | 144 px |
| 800 px | 1 | 0 | 304 px | 304 px | 144 px |
| **380 px (Handy)** | **2** | 0 | 170 px | 170 px | 144 px (2. Zeile) |

Kein Überlauf der Zeile und kein Überlauf des Dokuments bei **keiner** der
Breiten; der lange Gruppenname „Vorschlag 1001 · 120 Gesichter · 2015–2025“ ist
im Auswahlfeld sichtbar. Sichtprüfung zusätzlich als Screenshot im gerenderten
Browser bei 1400 px und 380 px (Dunkelmodus erzwungen): 1400 px alles auf einer
Linie, 380 px bricht der Knopf in die zweite Zeile um, nichts abgeschnitten,
Text hell auf dunklem Grund.

## Tests

- `backend/tests/test_gruppen_quiz.py`: neu
  `test_personen_liste_nennt_ihre_gruppen_ohne_bilddaten` (Kennungen, Größen,
  Zeitraum, **genau** die vier Schlüssel — damit fällt auf, wenn jemand
  Bilddaten nachrüstet) und
  `test_personen_gruppen_metadaten_zaehlen_ausgeschlossene_ab`.
- `frontend/tests/test_gruppen_quiz.js`: reine Funktionen (Liste immer eine
  Liste, Treffer/kein Treffer/leer = alle, Auswahlliste ohne Doppelte und
  größte zuerst, Auswahlzeile) sowie die zwei neuen Element-Kennungen in HTML
  **und** Skript.
- `frontend/tests/test_gruppen_liste.js`: neue Laufzeitprüfung
  `personenGruppenFilterInBenannt` — zwei Personen, Filter setzen, UND mit der
  Namenssuche, „Filter zurücksetzen“ leert beide, gewählte Gruppe überlebt das
  Neuladen der Liste. Die dortige Personen-Attrappe trug noch ein erfundenes
  Feld `gruppen: 1` (Zahl) und ist auf die echte Form umgestellt.
- Alle **36** Frontend-Node-Tests grün (`pytest tests/test_frontend_node.py`
  → 36 passed); die reinen Node-Läufe einzeln: Exit 0.

## Cache

`frontend/index.html`:

- `style.css?v=20261016B` → **`?v=20261016C`**
- `gruppen_quiz.js?v=20261016A` → **`?v=20261016B`**

## Ehrliche Grenzen

- Die Auswahlliste wird aus den **geladenen Personen** gebaut. Eine
  Gesichtsgruppe, die zu **keiner** benannten Person gehört, steht dort nicht —
  das ist gewollt (die Ansicht zeigt benannte Personen), aber es heißt: der
  Filter ist kein Ersatz für die Gruppenübersicht.
- Die Auswahl wirkt **innerhalb** der Ansicht „Benannt“; die Gruppenübersicht
  behält ihre eigenen Statusfilter.
- Umgesetzt ist nur Punkt 2b. Die Bedienung der Kacheln (Punkt 2c / Schritt S4)
  ist **nicht** enthalten.
