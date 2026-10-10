// Hintergrund-Leiste (10.10.2026): dauerhafte Statuszeile am oberen Rand.
//
// Befund (Sebastian): Gestern lief 20-30 Minuten eine Bildanalyse, im Chat
// war nichts davon zu sehen — "muss jederzeit ersichtlich sein, welche
// Hintergrundprozesse laufen". Die Leiste zeigt dauerhaft "Es läuft: <Name>
// seit <Dauer>" (Quelle GET /api/laeuft), antippbar fuer Einzelheiten; ohne
// Arbeit "Keine Hintergrundarbeit". Deutsch, ohne Haekchen-/Statussymbole.
//
// Dieser Test schneidet die REINEN Text-Funktionen aus dem echten app.js
// und prueft Texte, Robustheit und die Verdrahtung (index.html, Abruf-Takt,
// Status-Ereignisse des Backends).
//
// Aufruf (aus dem Ordner frontend):  node tests/test_hintergrund_leiste.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const pfadHtml = path.join(__dirname, '..', 'index.html');
const src = fs.readFileSync(pfadApp, 'utf8');
const html = fs.readFileSync(pfadHtml, 'utf8');

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

function ausschneiden(namen) {
    // Alle Funktionen in EINEN Scope schneiden — sie rufen sich gegenseitig
    // auf (hintergrundKurzText -> hintergrundDauerText usw.).
    const teile = namen.map((n) => funktionAusschneiden(src, n)).join('\n');
    return new Function(teile + '\nreturn {' + namen.join(', ') + '};')();
}

const f = ausschneiden([
    'hintergrundDauerText', 'hintergrundZeitText', 'hintergrundKurzText',
    'hintergrundZustandText', 'hintergrundEinzelheitenText',
]);
const dauerText = f.hintergrundDauerText;
const zeitText = f.hintergrundZeitText;
const kurzText = f.hintergrundKurzText;
const zustandText = f.hintergrundZustandText;
const einzelheitenText = f.hintergrundEinzelheitenText;

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

// Keine Haekchen-/Statussymbole und keine Emojis in den Anzeigetexten.
const verboteneSymbole = /[\u2713\u2714\u2705\u274C\u26A0\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

console.log('Hintergrund-Leiste: Kopfzeile');
pruefe(kurzText(null, 0) === 'Keine Hintergrundarbeit', 'nichts laeuft -> "Keine Hintergrundarbeit"');
pruefe(kurzText({ arbeiten: [] }, 0) === 'Keine Hintergrundarbeit', 'leere Liste -> "Keine Hintergrundarbeit"');
pruefe(kurzText({}, 0) === 'Keine Hintergrundarbeit', 'kaputte Antwort -> "Keine Hintergrundarbeit"');

const eineArbeit = { arbeiten: [{
    name: 'Werkzeug fotos_mit_person', zustand: 'laeuft', dauer_sekunden: 300,
    seit: '', letzte_zeile: '', fortschritt: '',
}] };
pruefe(kurzText(eineArbeit, 0) === 'Es läuft: Werkzeug fotos_mit_person seit 5 Minuten',
    'eine Arbeit -> "Es läuft: <Name> seit <Dauer>"');

const zweiArbeiten = { arbeiten: [
    eineArbeit.arbeiten[0],
    { name: 'Protokoll bildanalyse.log', zustand: 'laeuft', dauer_sekunden: 90 },
] };
pruefe(kurzText(zweiArbeiten, 0) === 'Es laufen 2 Arbeiten: Werkzeug fotos_mit_person seit 5 Minuten',
    'zwei Arbeiten -> Anzahl plus erste');

const ohneDauer = { arbeiten: [{
    name: 'X', zustand: 'laeuft', seit: new Date(Date.now() - 120000).toISOString(),
}] };
pruefe(/^Es läuft: X seit 2 Minuten$/.test(kurzText(ohneDauer, Date.now())),
    'ohne dauer_sekunden: aus der Startzeit gerechnet');
const nurSteht = { arbeiten: [{
    name: 'Protokoll alt.log', zustand: 'steht', dauer_sekunden: 7200,
    seit: '', letzte_zeile: 'Ende',
}] };
pruefe(kurzText(nurSteht, 0) === 'Keine Hintergrundarbeit',
    'nur stehende Protokolle -> "Keine Hintergrundarbeit" (kein falsches "laeuft")');
pruefe(einzelheitenText(nurSteht).indexOf('Protokoll alt.log') !== -1,
    'das stehende Protokoll steht trotzdem in den Einzelheiten');
pruefe(!verboteneSymbole.test(kurzText(eineArbeit, 0)),
    'Kopfzeile ohne Symbole/Emojis');

console.log('Hintergrund-Leiste: Dauer in Worten');
pruefe(dauerText(0) === 'weniger als eine Minute', '0 s');
pruefe(dauerText(59) === 'weniger als eine Minute', '59 s');
pruefe(dauerText(60) === '1 Minute', '60 s -> 1 Minute');
pruefe(dauerText(150) === '2 Minuten', '150 s -> 2 Minuten');
pruefe(dauerText(3600) === '1 Stunde', '3600 s -> 1 Stunde');
pruefe(dauerText(4800) === '1 Stunde 20 Minuten', '4800 s -> 1 Stunde 20 Minuten');
pruefe(dauerText(-5) === 'weniger als eine Minute', 'negativ/kaputt bleibt harmlos');

console.log('Hintergrund-Leiste: Einzelheiten');
const eintraege = { arbeiten: [
    { name: 'Hermes: Beschreibe alle Bilder', art: 'hermes', zustand: 'laeuft',
      seit: new Date().toISOString(), dauer_sekunden: 1560,
      fortschritt: '1234 von 17580', letzte_zeile: 'Bild 1234 fertig' },
    { name: 'Protokoll alt.log', art: 'protokoll', zustand: 'steht',
      seit: '', dauer_sekunden: 7200, letzte_zeile: 'Ende' },
] };
const details = einzelheitenText(eintraege);
pruefe(details.indexOf('Hermes: Beschreibe alle Bilder (läuft)') === 0,
    'Name und Zustand stehen zuerst');
pruefe(details.indexOf('Start: ') !== -1, 'Startzeit steht dabei');
pruefe(details.indexOf('Dauer: 26 Minuten') !== -1, 'Dauer in Minuten');
pruefe(details.indexOf('Fortschritt: 1234 von 17580') !== -1, 'Fortschritt (soweit erkennbar)');
pruefe(details.indexOf('Letzte Zeile: Bild 1234 fertig') !== -1, 'letzte Zeile des Protokolls');
pruefe(details.indexOf('Protokoll alt.log (steht (keine neuen Zeilen))') !== -1,
    'stehende Datei wird als steht gekennzeichnet');
pruefe(!verboteneSymbole.test(details), 'Einzelheiten ohne Symbole/Emojis');
pruefe(einzelheitenText({ arbeiten: [] }) === '', 'ohne Arbeit keine Einzelheiten');
pruefe(einzelheitenText({ arbeiten: [null, { name: 'A' }] }).indexOf('A') !== -1,
    'kaputter Eintrag wird uebersprungen statt Absturz');
pruefe(zustandText('laeuft') === 'läuft' && zustandText('leer') === 'leer'
    && zustandText(undefined) === 'unbekannt', 'Zustaende als Klartext');

console.log('Hintergrund-Leiste: Zeit-Text');
pruefe(/^\d{2}:\d{2} Uhr$/.test(zeitText(new Date().toISOString())),
    'heute -> "HH:MM Uhr"');
pruefe(/^\d{2}\.\d{2}\. \d{2}:\d{2} Uhr$/.test(
    zeitText(new Date(Date.now() - 3 * 86400000).toISOString())),
    'aelter -> "TT.MM. HH:MM Uhr"');
pruefe(zeitText('keine-zeit') === '' && zeitText('') === '' && zeitText(null) === '',
    'kaputte Zeit -> leerer Text');

console.log('Hintergrund-Leiste: Verdrahtung');
pruefe(html.indexOf('id="hintergrund-leiste"') !== -1, 'index.html enthaelt die Leiste');
pruefe(html.indexOf('id="hintergrund-text"') !== -1
    && html.indexOf('Keine Hintergrundarbeit') !== -1, 'Starttext steht im HTML');
pruefe(html.indexOf('id="hintergrund-kopf"') !== -1
    && html.indexOf('id="hintergrund-einzelheiten"') !== -1,
    'Kopf und Einzelheiten (antippbar) stehen im HTML');
pruefe(/fetch\(`\$\{API_BASE\}\/api\/laeuft`\)/.test(src), 'Abruf von GET /api/laeuft');
pruefe(src.indexOf('HINTERGRUND_TAKT_MS = 15000') !== -1
    && src.indexOf('setInterval(laden, HINTERGRUND_TAKT_MS)') !== -1,
    'erneuert sich regelmaessig selbst (15 s)');
pruefe(src.indexOf('visibilitychange') !== -1,
    'laedt beim Zurueckkommen in die App sofort neu');
pruefe(/setzeTutZeile\(daten\.status\)/.test(src),
    'Status-Ereignisse des Backends landen in der Arbeits-Zeile');
pruefe(src.indexOf('Hintergrund-Status gerade nicht abrufbar') !== -1,
    'ehrliche Meldung, wenn der Server fehlt');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
