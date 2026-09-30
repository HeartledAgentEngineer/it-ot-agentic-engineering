// Werkzeuge immer an + Datenschutz-Riegel im Stream-Weg (30.09. / 01.10.2026)
//
// Tool Use (docs/spec-tool-use-v1.md): Seit 01.10.2026 sind Werkzeuge am Server
// Standard an (Sebastian: „Werkzeuge brauch ich eigentlich immer"). Der Knopf
// „Werkzeuge" ist weg, die Stream-Anfrage schickt KEIN `werkzeuge` mehr (sonst
// würde ein altes gespeichertes „aus" den Server-Standard überstimmen), und der
// Stichwort-Abfang „zeig … Foto" vor dem Senden ist aus — das Modell entscheidet.
// Befund 30.09.: Der Stream-Weg schickte `no_retention` NIE mit (nur der
// Rückfallweg /api/chat) — das bleibt hier festgehalten.
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

console.log('Werkzeuge immer an (kein Knopf)');
pruefe(!/id="werkzeug-btn"/.test(html), 'Knopf werkzeug-btn ist aus der Werkzeugleiste entfernt');
pruefe(/id="web-btn"/.test(html), 'Web-Schalter bleibt (bewusst abschaltbar)');
pruefe(!/function setWerkzeuge\(/.test(js) && !/state\.werkzeuge/.test(js),
    'kein Schalter-Zustand mehr im Frontend');
pruefe(!/werkzeuge:/.test(streamKoerper),
    'Stream-Anfrage schickt kein werkzeuge-Feld (Server-Standard gilt)');

console.log('Stichwort-Abfang aus');
pruefe((js.match(/fotoFrageErkennen\(/g) || []).length === 1,  // nur noch die Definition
    '„zeig … Foto" geht ans Modell statt vorab an die feste Galerie');
pruefe(/function fotoFrageErkennen\(/.test(js) && /function zeigeFotoGalerie\(/.test(js),
    'Galerie und Erkennung bleiben für das spätere galerie-Ereignis');

console.log('Datenschutz-Riegel im Stream-Weg');
pruefe(streamKoerper.length > 0, 'Stream-Anfrage gefunden');
pruefe(/no_retention: state\.noRetention,/.test(streamKoerper),
    'Stream-Anfrage schickt no_retention mit (vorher fehlte er)');
pruefe(/noRetention: true,/.test(js), 'Riegel steht weiter fest auf an');

console.log('Cache-Bump');
const m = html.match(/app\.js\?v=(\d{8}[A-Z])/);
pruefe(m && m[1] >= '20261001A', 'app.js-Version 20261001A oder neuer (gefunden: ' + (m && m[1]) + ')');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
