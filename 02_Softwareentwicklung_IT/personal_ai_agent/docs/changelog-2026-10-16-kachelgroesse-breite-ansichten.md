# Kacheln auf Tablet und PC deutlich kleiner (16.10.2026)

Dauerlauf-Schritt **S3** (To-do Punkt 2a: „Kacheln auf breiten Bildschirmen
deutlich kleiner, Handy unverändert"). Befund Sebastian im Feld: „Fürs Tablet
oder für den PC sind die Kacheln natürlich viel, viel zu groß."

## Ursache (gemessen, nicht vermutet)

Gesucht war die **Gesichts-Kachelansicht im Gruppenblatt**
(`#gruppen-sheet`, Ordner `frontend/`, `gruppen_quiz.js`). Der Grund liegt im
Aufbau:

- Das Gruppenblatt liegt **nicht** in `#app` (das ist auf `max-width: 800px`
  begrenzt), sondern in einem eigenen, über das Fenster gespannten Blatt
  (`#gruppen-sheet`, `.sheet-panel`, kein `max-width`).
- Die beiden Raster `.gruppen-kacheln` und `.gruppen-alle-raster` hatten
  **vier feste Spalten** (`grid-template-columns: repeat(4, minmax(0, 1fr))`).
  Damit wächst die Kachel mit dem Fenster: bei 1400 px Fensterbreite war eine
  Kachel **337,50 px** breit.

Die Chat-Galerie `.foto-kacheln` (84 px) ist **nicht** betroffen und bleibt
unangetastet; die Benannt-Liste (`.gruppen-kachel.klein`, 52 px) ebenso.

## Änderung

In `frontend/style.css`, am **Dateiende** (dort, wo die älteren Regeln
überschrieben werden dürfen):

```css
@media (min-width: 1000px) {
    .gruppen-kacheln,
    .gruppen-alle-raster {
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    }
}
```

Ab 1000 px Fensterbreite also ein Raster mit fester Mindestbreite statt fester
Spaltenzahl. **Unter** 1000 px (Handy 380 px, Tablet 768 px) gilt weiter die
bisherige Vier-Spalten-Regel — dort ändert sich nichts.

## Beleg — echter Browser, gemessen (nicht gerechnet)

Gerendert mit Puppeteer + Edge in einem Belegskript **außerhalb** des Repos
(`…/cache/scratch/kachel_messen.js`), das die **echte** `style.css` und die
echte Markup-Struktur des Gruppenblatts lädt; gezählt wurde die reale
Spaltenzahl des Rasters. Fensterbreite 1400 px:

| Raster | Spalten vorher | Kachel vorher | Spalten nachher | Kachel nachher |
|---|---|---|---|---|
| `#gruppen-kacheln` | 4 | 337,50 px | **8** | **165,75 px** |
| `#gruppen-alle-raster` | 4 | 337,50 px | **8** | **165,75 px** |
| Beispiel-Kacheln eines Vorschlags | 4 | 333,00 px | **8** | **163,50 px** |

Weitere Breiten (nachher): 1600 px → 10 Spalten (151,39 px); 1200 px →
7 Spalten (161,70 px); 1000 px → 6 Spalten (156,33 px);

Unverändert (nachher wie vorher, Baseline-Vergleich): 999 px → 4 Spalten zu
237,25 px; 768 px → 4 Spalten zu 179,50 px; **380 px → 4 Spalten zu 82,50 px**.

Prüfkriterium des Auftrags damit erfüllt: bei 1400 px **acht** Kacheln je Zeile
(geforderte Mindestzahl: vier), bei 380 px **keine** Änderung.
Sichtprüfung zusätzlich als Screenshot im gerenderten Browser (1400 px, vorher
und nachher) — 8 Kacheln je Zeile, gleich groß, ohne Überlappung.

## Ehrliche Grenze

- Die Umstellung greift **ab 1000 px**; zwischen 999 px (vier Spalten zu
  237,25 px) und 1000 px (sechs Spalten zu 156,33 px) springt die Kachelgröße
  einmal. Das ist die im Arbeitsplan festgelegte Grenze („ab 1000 px"), gewählt,
  damit Handy und Tablet garantiert unverändert bleiben. Wer den Sprung später
  weicher will, verschiebt die Grenze nach unten — die Belegmessung ist dafür
  wiederholbar.
- Nur die **Darstellung** ist geändert. Bedienung, Auswahl-Logik und der
  Gruppenfilter sind eigene Schritte (S4 und S5) und hier **nicht** enthalten.

## Tests

Neu: `frontend/tests/test_kachelgroesse.js` (läuft über
`backend/tests/test_frontend_node.py` automatisch im Prüfbefehl mit). Er prüft
am **echten** Stylesheet:

- der Block `@media (min-width: 1000px)` nennt **beide** Raster und die Regel
  `repeat(auto-fill, minmax(…, 1fr))`;
- er steht **hinter** der alten Vier-Spalten-Regel von `.gruppen-alle-raster`
  (sonst würde die ältere Regel gewinnen und nichts ändern);
- die Spaltenzahl ist mit den Maßen des Rasters nachgerechnet und muss die
  **Sollwerte der Messung** treffen (1400 px → 8, 1000 px → 6) und die
  Mindestforderung von vier Kacheln bei 1400 px erfüllen;
- Handy/Tablet-Bestand ist festgehalten: `.gruppen-kacheln` und
  `.gruppen-alle-raster` tragen weiter ihre Vier-Spalten-Regel als Grundlage,
  `.foto-kacheln` bleibt bei 84 px;
- **Gegenproben** (sonst wäre der Test grün, egal was im Stylesheet steht): eine
  Fassung **ohne** den breiten Block, eine Fassung **ohne**
  `.gruppen-alle-raster` im Block und eine Fassung mit dem Block **vor** der
  alten Regel werden alle abgewiesen.

`frontend/tests/test_foto_galerie.js` nagelte den `style.css`-Token als Literal
fest (`vCss === '20261016A'`) und wurde durch genau diesen Bump **rot** — damit
war bewiesen, dass die Prüfung greift. Sie verlangt jetzt wie beim
`app.js`-Token nur noch das Muster `JJJJMMTT` + Buchstabe und einen Stand
**nicht älter** als `20261016B`; der Zweck (der Bump passiert wirklich) bleibt,
die Prüfung verrottet aber nicht mehr bei jedem berechtigten Bump.
Alle **36** Frontend-Node-Tests sind grün (`pytest tests/test_frontend_node.py`
→ 36 passed) — sie laufen im Prüfbefehl automatisch mit.

## Cache

`frontend/index.html`: `style.css?v=20261016A` → **`?v=20261016B`** (ohne den
Bump behält der Browser die alte Gestaltung — am PC wie am Handy).
