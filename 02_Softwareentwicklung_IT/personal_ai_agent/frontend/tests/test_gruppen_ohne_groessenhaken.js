// Haken „Nur Gesichter ≥ 50 px" entfernt (F2, 03.11.2026): das Backend filtert immer.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_gruppen_ohne_groessenhaken.js gruppen_quiz.js
const fs = require('fs');
const path = require('path');

const pfad = path.resolve(process.argv[2] || path.join(__dirname, '..', 'gruppen_quiz.js'));
const src = fs.readFileSync(pfad, 'utf8');
const html = fs.readFileSync(path.join(path.dirname(pfad), 'index.html'), 'utf8');

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt); fehler++; }
}

pruefe(!/gruppen-filter-groesse/.test(html), 'index.html hat keinen Größen-Haken mehr');
pruefe(!/gruppen-filter-groesse/.test(src), 'gruppen_quiz.js fragt keinen Haken mehr ab');
pruefe(!/min_px=/.test(src), 'Quiz schickt keinen eigenen Mindestwert (Backend-Vorgabe gilt)');
const w = html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/);
pruefe(w && w[1] >= '20261103A', 'gruppen_quiz.js mindestens 20261103A');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
