// Blasen-Breite (13.10.2026): Die innere Spalte einer Chat-Blase muss
// min-width:0 tragen. Sonst hat sie als Flex-Kind min-width:auto, wird so
// breit wie ihr breitester Inhalt (Tabelle mit langen Spaltenköpfen) und
// schiebt den Vorlese-Knopf über den rechten Rand – am Handy half nur Neustart.
// Gemessen bei 375 px: Spalte 358 px in einer 338-px-Zeile, Chat scrollWidth 406.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_blasen_breite.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');

function funktionAusschneiden(quelle, name) {
    const start = quelle.indexOf('function ' + name + '(');
    if (start === -1) throw new Error('Funktion nicht gefunden: ' + name);
    let tiefe = 0;
    for (let i = quelle.indexOf('{', start); i < quelle.length; i++) {
        if (quelle[i] === '{') tiefe++;
        else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(start, i + 1);
    }
    throw new Error('Funktionsende nicht gefunden: ' + name);
}

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

console.log('addMessage – innere Spalte');
const add = funktionAusschneiden(src, 'addMessage');
const m = add.match(/inner\.style\.cssText\s*=\s*'([^']*)'/);
pruefe(!!m, 'innere Spalte wird mit cssText gebaut');
const css = m ? m[1].replace(/\s/g, '') : '';
pruefe(/display:flex/.test(css) && /flex-direction:column/.test(css), 'bleibt eine Flex-Spalte');
pruefe(/min-width:0(;|$)/.test(css), 'trägt min-width:0 (kann unter die Tabellenbreite schrumpfen)');

console.log('CSS – Tabellen scrollen in ihrer eigenen Hülle');
const style = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');
pruefe(/\.table-wrap\s*\{[^}]*overflow-x:\s*auto/.test(style), '.table-wrap hat overflow-x:auto');

if (fehler) { console.log('\n' + fehler + ' Fehler'); process.exit(1); }
console.log('\nalles grün');
