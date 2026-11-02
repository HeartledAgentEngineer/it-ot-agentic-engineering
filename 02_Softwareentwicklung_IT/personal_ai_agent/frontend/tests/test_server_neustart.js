// Neustart/Wiederverbinden statt Tab-Tod (02.11.2026, Wunsch Sebastian).
//
// Befund (Sebastian, Handy, mit Screenshot): Nach einem bewussten Neustart
// (Server-Protokoll -> Neustart, POST /api/system/update) wird der Server
// gekillt, es laeuft git pull + Uebernahmen (8-30 s), dann erst uvicorn.
// In dieser Luecke zeigte das Frontend den "Server nicht erreichbar / Tab
// schließen"-Schirm: er LEERTE den ganzen Chat (document.body.innerHTML = '')
// und zaehlte 30 s runter. Am Ende rief er window.close() — das wirkt in einem
// normalen Tab NICHT -> der Countdown blieb bei 0 stehen, "passiert nix", und
// es gab keinen Rueckweg in den Chat.
//
// Zielverhalten: ein NICHT-zerstoerender Wiederverbinden-Overlay mit sichtbarem
// Feedback (Spinner), der /api/health pollt und bei Rueckkehr EINMAL neu laedt
// -> automatisch zurueck in den Chat. "Tab schließen" nur noch als manueller
// Knopf nach langer Totzeit, nie als haengender Countdown.
//
// Dieser Test schneidet die reine Textfunktion aus app.js und prueft zusaetzlich
// die Verdrahtung (Aufrufstellen, Poll, Reload, entfernte Sackgasse, Cache).
//
// Aufruf (aus dem Ordner frontend):  node tests/test_server_neustart.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const pfadHtml = path.join(__dirname, '..', 'index.html');
const pfadCss = path.join(__dirname, '..', 'style.css');
const src = fs.readFileSync(pfadApp, 'utf8');
const html = fs.readFileSync(pfadHtml, 'utf8');
const css = fs.readFileSync(pfadCss, 'utf8');

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

const f = (function () {
    const teile = funktionAusschneiden(src, 'wiederverbindenMeldung');
    return new Function(teile + '\nreturn { wiederverbindenMeldung };')();
})();
const meldung = f.wiederverbindenMeldung;

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt); fehler++; }
}

const verboteneSymbole = /[✓✔✅❌⚠\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

console.log('Wiederverbinden: Meldungstexte je Grund');
const mNeu = meldung('neustart');
pruefe(/neu gestartet/i.test(mNeu.titel), 'neustart -> Titel sagt, dass neu gestartet wird');
pruefe(/zur[uü]ck in den Chat/i.test(mNeu.text), 'neustart -> Text verspricht automatisch zurueck in den Chat');

const mVerl = meldung('verloren');
pruefe(/verbindung verloren/i.test(mVerl.titel), 'verloren -> Titel "Verbindung verloren"');
pruefe(/automatisch/i.test(mVerl.text) && /zur[uü]ck in den Chat/i.test(mVerl.text),
    'verloren -> Text: automatisch neu verbinden, zurueck in den Chat');

const mLang = meldung('lange');
pruefe(/nicht erreichbar/i.test(mLang.titel), 'lange -> Titel "Server nicht erreichbar"');
pruefe(/erneut versuchen/i.test(mLang.text) && /tab schlie/i.test(mLang.text),
    'lange -> Text bietet erneut versuchen und Tab schließen');

const mUnbekannt = meldung('irgendwas');
pruefe(mUnbekannt && typeof mUnbekannt.titel === 'string' && typeof mUnbekannt.text === 'string'
    && mUnbekannt.titel === mVerl.titel,
    'unbekannter Grund faellt auf "verloren" zurueck (kein Absturz)');

pruefe(!verboteneSymbole.test(mNeu.titel + mNeu.text)
    && !verboteneSymbole.test(mVerl.titel + mVerl.text)
    && !verboteneSymbole.test(mLang.titel + mLang.text),
    'Meldungstexte ohne Haekchen-/Statussymbole/Emojis');

console.log('Wiederverbinden: Verdrahtung in app.js');
pruefe(src.indexOf('function starteWiederverbinden(') !== -1, 'starteWiederverbinden existiert');
pruefe(src.indexOf('function wiederverbindenMeldung(') !== -1, 'wiederverbindenMeldung existiert');
pruefe(/id="reconnect-overlay"|'reconnect-overlay'|"reconnect-overlay"/.test(src),
    'ein eigener Wiederverbinden-Overlay (#reconnect-overlay)');
pruefe(src.indexOf("starteWiederverbinden('neustart')") !== -1,
    'der Neustart-Knopf startet den Wiederverbinden-Overlay');
pruefe(src.indexOf("starteWiederverbinden('verloren')") !== -1,
    'unerwarteter Verbindungsverlust startet den Wiederverbinden-Overlay');
pruefe(/fetch\(`\$\{API_BASE\}\/api\/health`/.test(src) && src.indexOf('window.location.reload()') !== -1,
    'es wird /api/health gepollt und bei Rueckkehr neu geladen (zurueck in den Chat)');
pruefe(/setTimeout\(\s*pollen\s*,\s*2000\s*\)/.test(src) || /2000/.test(funktionAusschneiden(src, 'starteWiederverbinden')),
    'der Poll wiederholt sich zuegig (ca. 2 s)');

console.log('Wiederverbinden: Sackgasse entfernt');
pruefe(src.indexOf('_showCloseOverlay') === -1, 'alter zerstoerender Schirm _showCloseOverlay entfernt');
pruefe(src.indexOf('_tryCloseTab') === -1, 'alter _tryCloseTab entfernt');
pruefe(src.indexOf("document.body.innerHTML = ''") === -1,
    'der Chat wird nicht mehr geleert (kein document.body.innerHTML = \'\')');

console.log('Wiederverbinden: Darstellung & Cache');
pruefe(css.indexOf('#reconnect-overlay') !== -1, 'style.css gestaltet den Overlay');
pruefe(/@keyframes\s+reconnect-spin/.test(css) && css.indexOf('.reconnect-spinner') !== -1,
    'ein sichtbarer Spinner (Keyframe + Klasse) als Feedback');
pruefe((html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] >= '20261102F',
    'Cache-Schluessel app.js mindestens 20261102F');
pruefe((html.match(/style\.css\?v=([0-9A-Z]+)/) || [])[1] >= '20261102A',
    'Cache-Schluessel style.css mindestens 20261102A');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
