// Vollbild: der rote ✕-Knopf eines Gesichtsrahmens verdeckt das Gesicht nicht (10.10.2026).
//
// Befund (Sebastian, Handy): Im Vollbild sass der Loesch-Knopf INNEN in der Ecke des
// gelben Rahmens. Bei kleinen Gesichtern verdeckte er das Gesicht - auch beim
// Vergroessern, weil er im gezoomten Bereich mitwaechst. Jetzt sitzt er ausserhalb,
// ueber der rechten oberen Ecke.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_vollbild_marke.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
let fehler = 0;
function pruefe(bedingung, text) {
    if (bedingung) { console.log('  ✔ ' + text); } else { console.log('  ✘ ' + text); fehler++; }
}

const start = src.indexOf("marke.className = 'vollbild-rahmen-marke'");
pruefe(start !== -1, 'Rahmen-Marke ist auffindbar');
const zeile = src.slice(start, src.indexOf('\n', src.indexOf('marke.style.cssText', start)));
pruefe(zeile.includes('bottom:100%'), 'Marke sitzt ueber dem Rahmen (bottom:100%)');
pruefe(!/top:\s*2px/.test(zeile), 'Marke sitzt nicht mehr innen oben');
pruefe(zeile.includes("textContent = '✕'") || src.slice(start, start + 600).includes("textContent = '✕'"),
       'Loeschen bleibt erreichbar');
pruefe(/app\.js\?v=20261010[A-Z]/.test(html), 'Cache-Kennung von app.js erhoeht');

if (fehler) { console.log(fehler + ' Pruefung(en) rot'); process.exit(1); }
console.log('alle Pruefungen gruen');
