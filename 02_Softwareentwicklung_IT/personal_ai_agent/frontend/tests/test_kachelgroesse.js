// Kachelgroesse in breiten Ansichten (16.10.2026, Dauerlauf-Schritt S3):
// Befund Sebastian — auf Tablet/PC sind die Gesichts-Kacheln im Gruppenblatt
// „viel, viel zu gross". Das Gruppenblatt liegt NICHT in #app
// (max-width: 800px), es fuellt das Fenster; mit vier festen Spalten war eine
// Kachel bei 1400 px Fensterbreite rund 337 px breit.
//
// Soll: ab 1000 px Fensterbreite ein Raster mit fester Mindestbreite
// (auto-fill/minmax(150px, 1fr)); Handy (380 px) und Tablet (768 px) bleiben
// unveraendert. Sollzahlen aus der echten Browsermessung (Edge/Chromium,
// 16.10.2026) — siehe docs/changelog-2026-10-16-kachelgroesse-breite-ansichten.md.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_kachelgroesse.js
// Der Pruefbefehl reicht jedem Test ein Argument durch (Vorgabe app.js) — dieses
// Stylesheet wird deshalb am Testordner aufgeloest, nicht aus dem Argument.
const fs = require('fs');
const path = require('path');

const arg = process.argv[2] || '';
const quelle = arg.endsWith('.css') ? arg : 'style.css';
const style = fs.readFileSync(path.resolve(__dirname, '..', quelle), 'utf8');

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

// --- Sollwerte (gemessen im echten Browser) ---------------------------------
const KACHEL_MIN = 150;      // minmax(..., 1fr) der neuen Regel
const RASTER_ABSTAND = 6;    // gap: 6px des Rasters
const RAND_JE_SEITE = 16;    // .gruppen-body padding: 12px 16px
const SOLL_SPALTEN = { 1400: 8, 1000: 6 };   // Mindestforderung: 4 bei 1400
const MINDEST_SPALTEN_1400 = 4;

// --- Prueffunktion (auch als Gegenprobe auf andere Fassungen anwendbar) -----
function breitesRasterBlock(css) {
    const m = css.match(/@media\s*\(min-width:\s*1000px\)\s*\{([\s\S]*?)\n\}/);
    return m ? m[1] : null;
}

function rasterMaengel(css) {
    const maengel = [];
    const block = breitesRasterBlock(css);
    if (!block) {
        maengel.push('kein @media (min-width: 1000px)-Block gefunden');
        return maengel;
    }
    if (!/\.gruppen-kacheln/.test(block)) {
        maengel.push('.gruppen-kacheln fehlt im breiten Raster');
    }
    if (!/\.gruppen-alle-raster/.test(block)) {
        maengel.push('.gruppen-alle-raster fehlt im breiten Raster');
    }
    if (!/grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(\s*\d+px,\s*1fr\s*\)\)/.test(block)) {
        maengel.push('die Spaltenregel auto-fill/minmax(px, 1fr) fehlt');
    }
    // Der Block muss HINTER der Vier-Spalten-Regel von .gruppen-alle-raster
    // stehen — sonst gewinnt die aeltere Regel und nichts aendert sich.
    const alt = css.indexOf('.gruppen-alle-raster {');
    const neu = css.search(/@media\s*\(min-width:\s*1000px\)/);
    if (alt === -1 || neu === -1 || neu < alt) {
        maengel.push('der breite Rasterblock steht nicht hinter .gruppen-alle-raster (wird ueberschrieben)');
    }
    return maengel;
}

// Spaltenzahl so, wie der Browser sie rechnet: verfuegbare Rasterbreite,
// Abstand zwischen den Spalten, Mindestbreite je Spalte.
function spaltenZahl(fensterbreite, rasterbreite) {
    return Math.max(1, Math.floor((rasterbreite + RASTER_ABSTAND) / (KACHEL_MIN + RASTER_ABSTAND)));
}

console.log('CSS — breites Raster (S3)');
pruefe(rasterMaengel(style).length === 0, 'Regeln vollstaendig und an der richtigen Stelle');
pruefe((style.match(/auto-fill,\s*minmax\(150px/g) || []).length === 1,
    'genau eine Stelle im Stylesheet stellt auf auto-fill/minmax(150px) um');
pruefe(breitesRasterBlock(style) !== null, 'der Block haengt an einer Mindestbreite (min-width), nicht an einer Hoechstbreite');

console.log('Sollzahlen gegen die Messung');
const raster1400 = 1400 - 2 * RAND_JE_SEITE;
pruefe(spaltenZahl(1400, raster1400) === SOLL_SPALTEN[1400],
    'bei 1400 px Fenster rechnerisch ' + SOLL_SPALTEN[1400] + ' Spalten (gemessen: 8)');
const raster1000 = 1000 - 2 * RAND_JE_SEITE;
pruefe(spaltenZahl(1000, raster1000) === SOLL_SPALTEN[1000],
    'bei 1000 px Fenster rechnerisch ' + SOLL_SPALTEN[1000] + ' Spalten (gemessen: 6)');
pruefe(spaltenZahl(1400, raster1400) >= MINDEST_SPALTEN_1400,
    'Kriterium des Auftrags erfuellt: mindestens ' + MINDEST_SPALTEN_1400 + ' Kacheln je Zeile bei 1400 px');

console.log('Handy/Tablet bleiben unveraendert');
pruefe(/\.gruppen-kacheln\s*\{[^}]*repeat\(4,\s*minmax\(0,\s*1fr\)\)/.test(style),
    '.gruppen-kacheln traegt weiter die Vier-Spalten-Regel als Grundlage');
pruefe(/\.gruppen-alle-raster\s*\{\s*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/.test(style),
    '.gruppen-alle-raster traegt weiter vier Spalten als Grundlage');
pruefe(/\.foto-kacheln\s*\{[^}]*minmax\(84px,\s*1fr\)/.test(style),
    'die Chat-Galerie .foto-kacheln (84 px) bleibt unangetastet');

console.log('Gegenprobe — eine unvollstaendige Fassung muss beanstandet werden');
const ohneBlock = style.replace(/@media\s*\(min-width:\s*1000px\)\s*\{[\s\S]*?\n\}\n?/, '');
pruefe(rasterMaengel(ohneBlock).length > 0, 'ohne den breiten Block wird die Fassung abgewiesen');
const ohneAlleRaster = style.replace(/(\.gruppen-kacheln,\s*\n\s*)\.gruppen-alle-raster/, '$1.gruppen-nur-kacheln');
pruefe(rasterMaengel(ohneAlleRaster).some((m) => /gruppen-alle-raster/.test(m)),
    'ohne .gruppen-alle-raster im Block wird die Fassung abgewiesen');
const blockVorDerAltenRegel = (() => {
    const block = breitesRasterBlock(style);
    const ohne = style.replace(/@media\s*\(min-width:\s*1000px\)\s*\{[\s\S]*?\n\}\n?/, '');
    const stelle = ohne.indexOf('.gruppen-alle-raster {');
    return ohne.slice(0, stelle)
        + '@media (min-width: 1000px) {\n    .gruppen-kacheln,\n    .gruppen-alle-raster {\n        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));\n    }\n}\n'
        + ohne.slice(stelle);
})();
pruefe(rasterMaengel(blockVorDerAltenRegel).some((m) => /ueberschrieben/.test(m)),
    'ein Block VOR der alten Vier-Spalten-Regel wird als wirkungslos abgewiesen');

if (fehler) { console.log('\n' + fehler + ' Fehler'); process.exit(1); }
console.log('\nalles grün');
