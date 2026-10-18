// Live-Status im Chat, klare Beschriftung (S7b, 18.10.2026).
//
//   Befund Sebastian: Der Balken oben im Chat stand ewig auf „wartet" — sah
//   aus, als würde gleich jemand die Aufgabe übernehmen. Es arbeitete aber
//   niemand daran (auf dem Handy läuft kein lokaler Hermes, der PC ist nicht
//   erreichbar). Der Backend-Teil (S7) sagt das seit 18.10. ehrlich in Text
//   und Statuszeile; die Beschriftung des Balkens log noch.
//
// Dieser Test schneidet die REINE Funktion aus dem echten app.js und prüft
// jeden Zustand des Auftrags einzeln, dazu zwei Quelltext-Wächter:
//   (1) die alte Wendung „⏳ wartet" darf im Code nicht mehr vorkommen,
//   (2) BEIDE Stellen, die die Beschriftung setzen, müssen über die eine
//       Funktion laufen (sonst kann eine davon wieder „wartet" behaupten).
// Die Gegenprobe (alte Fassung) wird rot, siehe Kopf der Datei unten.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_live_status_indikator.js app.js
// Gegenprobe ALT:
//   git show HEAD:frontend/app.js > "$TMPDIR/alt_app.js"
//   node tests/test_live_status_indikator.js "$TMPDIR/alt_app.js"   # -> rot
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(pfadApp, 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
    if (bedingung) { console.log('  OK   ' + name); }
    else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

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

// Alte Fassungen haben die Funktion nicht: dann NICHT abbrechen, sondern
// jeden Zustand einzeln als rot melden (lesbarer Gegenbeweis).
let echteIndikator = null;
try {
    echteIndikator = new Function(
        funktionAusschneiden(src, 'hermesLiveIndikator') + '\nreturn hermesLiveIndikator;')();
} catch (e) {
    echteIndikator = null;
}
function indikator(status) {
    return echteIndikator ? echteIndikator(status) : '(Funktion fehlt)';
}

console.log('Funktion im Quelltext');
pruefe('hermesLiveIndikator ist vorhanden', echteIndikator !== null);

console.log('Beschriftung je Auftragszustand');
pruefe('laeuft -> "⚡ arbeitet"', indikator('laeuft') === '⚡ arbeitet', indikator('laeuft'));
pruefe('offen -> "⏳ liegt bereit"', indikator('offen') === '⏳ liegt bereit', indikator('offen'));
pruefe('fertig -> "✅ fertig"', indikator('fertig') === '✅ fertig', indikator('fertig'));
pruefe('fehler -> "❌ fehler"', indikator('fehler') === '❌ fehler', indikator('fehler'));

console.log('Unbekannter Zustand behauptet keine Arbeit');
for (const wert of [undefined, null, '', 'unbekannt', 'WARTET']) {
    const text = indikator(wert);
    pruefe('Wert ' + JSON.stringify(wert) + ' -> "' + text + '"',
        text === '⏳ liegt bereit',
        'behauptet Arbeit oder Sondertext: ' + text);
}
pruefe('"offen" und unbekannt sind gleich beschriftet (keine Sonderbehauptung)',
    indikator('offen') === indikator('quatsch'));

console.log('Quelltext-Waechter');
pruefe('alte Wendung "⏳ wartet" kommt nicht mehr vor',
    src.indexOf('⏳ wartet') === -1,
    'gefunden an ' + src.split('\n').findIndex((z) => z.includes('⏳ wartet')));
const aufrufe = src.split('indicator.textContent = hermesLiveIndikator(').length - 1;
pruefe('BEIDE Beschriftungs-Stellen laufen über die eine Funktion (2 Aufrufe)',
    aufrufe === 2, 'gefundene Aufrufe: ' + aufrufe);
pruefe('kein direkter Text am Indikator (kein indicator.textContent = \'...)',
    !/indicator\.textContent\s*=\s*['"]/.test(src),
    'direkter Text gefunden');
pruefe('Auftragszustaende des Servers sind die geprueften (offen/laeuft/fertig/fehler)',
    ['offen', 'laeuft', 'fertig', 'fehler'].every((s) => typeof indikator(s) === 'string'));

if (fehler) {
    console.log('\nFEHLGESCHLAGEN: ' + fehler + ' Pruefung(en) rot.');
    process.exit(1);
}
console.log('\nAlle Pruefungen bestanden.');
