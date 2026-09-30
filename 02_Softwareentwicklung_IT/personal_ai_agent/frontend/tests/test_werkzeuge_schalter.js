// Werkzeug-Schalter + Datenschutz-Riegel im Stream-Weg (30.09.2026)
//
// Tool Use (docs/spec-tool-use-v1.md): Knopf „Werkzeuge" an der Eingabe, Standard
// aus, Wunsch in localStorage; die Stream-Anfrage schickt `werkzeuge` mit.
// Befund beim Einbau: Der Stream-Weg schickte `no_retention` NIE mit (nur der
// Rückfallweg /api/chat) - die Oberfläche sagte „Riegel fest an", das Backend
// bekam den Standard „aus". Beides wird hier festgehalten.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_werkzeuge_schalter.js
const fs = require('fs');
const path = require('path');

const js = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

// Den Körper der Stream-Anfrage herausschneiden (fetch auf /api/chat/stream).
const start = js.indexOf('`${API_BASE}/api/chat/stream`');
const streamKoerper = start === -1 ? '' : js.slice(start, js.indexOf('signal: controller.signal', start));

console.log('Werkzeug-Schalter');
pruefe(/<button id="werkzeug-btn" class="tool-toggle" aria-pressed="false"/.test(html),
    'Knopf werkzeug-btn in der Werkzeugleiste, anfangs nicht gedrückt');
pruefe(/werkzeuge: localStorage\.getItem\('werkzeuge'\) === '1'/.test(js),
    'Standard aus: nur ein gespeichertes "1" schaltet ein');
pruefe(/function setWerkzeuge\(an\)/.test(js) && /localStorage\.setItem\('werkzeuge'/.test(js),
    'setWerkzeuge() merkt sich den Wunsch');
pruefe(/setWerkzeuge\(state\.werkzeuge\);/.test(js),
    'Zustand wird beim Start wiederhergestellt');
pruefe(/werkzeuge: state\.werkzeuge,/.test(streamKoerper),
    'Stream-Anfrage schickt werkzeuge mit');

console.log('Datenschutz-Riegel im Stream-Weg');
pruefe(streamKoerper.length > 0, 'Stream-Anfrage gefunden');
pruefe(/no_retention: state\.noRetention,/.test(streamKoerper),
    'Stream-Anfrage schickt no_retention mit (vorher fehlte er)');
pruefe(/noRetention: true,/.test(js), 'Riegel steht weiter fest auf an');

console.log('Cache-Bump');
const m = html.match(/app\.js\?v=(\d{8})([A-Z])/);
pruefe(m && m[1] >= '20260930', 'app.js-Version ist vom 30.09.2026 oder neuer');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
