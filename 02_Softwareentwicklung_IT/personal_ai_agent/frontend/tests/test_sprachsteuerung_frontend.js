// test_sprachsteuerung_frontend.js — Tests fuer appSprachbefehlAusfuehren und LiveVoiceClient
// Node.js Testsuite

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const appPath = path.resolve(__dirname, '../app.js');
const appSrc = fs.readFileSync(appPath, 'utf8');

let fehler = 0;
function pruefe(bed, msg, detail) {
    if (bed) {
        console.log('  OK   ' + msg);
    } else {
        console.log('  FEHL ' + msg + (detail ? ' -> ' + detail : ''));
        fehler++;
    }
}

console.log('\n1) Pruefung Quelltext: Sprachsteuerung & LiveVoiceClient in app.js vorhanden');
{
    pruefe(appSrc.includes('function appSprachbefehlAusfuehren'), 'appSprachbefehlAusfuehren existiert');
    pruefe(appSrc.includes('function appAktionAusfuehren'), 'appAktionAusfuehren existiert');
    pruefe(appSrc.includes('class LiveVoiceClient'), 'class LiveVoiceClient existiert');
    pruefe(appSrc.includes('window.appSprachbefehlAusfuehren = appSprachbefehlAusfuehren'), 'appSprachbefehlAusfuehren am window exportiert');
    pruefe(appSrc.includes('window.liveVoiceClient = new LiveVoiceClient()'), 'liveVoiceClient am window initialisiert');
}

console.log('\n2) Simulation & Ausfuehrung von App-Aktionen');
{
    // Minimales Fake-DOM fuer Aktions-Tests
    const clicks = [];
    const elements = {
        'gruppen-btn': { click: () => clicks.push('gruppen-btn'), hidden: false },
        'erzaehlen-btn': { click: () => clicks.push('erzaehlen-btn'), hidden: false },
        'erzaehlen-sheet': { hidden: true },
        'gruppen-sheet': { hidden: true },
        'model-sheet': { hidden: true },
        'message-input': { value: '', focus: () => clicks.push('focus-input') },
        'erzaehl-zurueck': { click: () => clicks.push('erzaehl-zurueck'), hidden: false },
        'erzaehl-weiter': { click: () => clicks.push('erzaehl-weiter'), hidden: false },
        'erzaehl-text': { value: 'Bestehende Notiz', focus: () => clicks.push('focus-text') },
        'erzaehl-ki-geschichte-btn': { click: () => clicks.push('ki-geschichte'), hidden: false },
        'gruppen-neu-vorsortieren-btn': { click: () => clicks.push('neu-vorsortieren'), hidden: false },
        'erzaehl-speichern-btn': { click: () => clicks.push('speichern'), hidden: false },
    };

    global.document = {
        getElementById: (id) => elements[id] || null,
        querySelectorAll: (sel) => {
            if (sel === '.erzaehl-ereignis') {
                return [{ click: () => clicks.push('event-0') }, { click: () => clicks.push('event-1') }];
            }
            if (sel === '.erzaehl-kachel') {
                return [{ click: () => clicks.push('bild-0') }, { click: () => clicks.push('bild-1') }];
            }
            return [];
        }
    };
    global.window = {};

    // Extrahiere appAktionAusfuehren
    const fnMatch = appSrc.match(/async function appAktionAusfuehren\([\s\S]*?\n\}/);
    pruefe(!!fnMatch, 'appAktionAusfuehren extrahiert');
    
    const appAktionAusfuehren = new Function(`
        ${fnMatch[0]}
        return appAktionAusfuehren;
    `)();

    // A. Quiz oeffnen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'quiz_oeffnen' });
    pruefe(clicks.includes('gruppen-btn'), 'quiz_oeffnen klickt gruppen-btn');

    // B. Erzaehlen oeffnen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'erzaehlen_oeffnen' });
    pruefe(clicks.includes('erzaehlen-btn'), 'erzaehlen_oeffnen klickt erzaehlen-btn');

    // C. 3 Seiten vorwaerts blaettern
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'blaettern', parameter: { richtung: 'vor', anzahl: 3 } });
    pruefe(clicks.filter(c => c === 'erzaehl-weiter').length === 3, 'blaettern vor 3x ausgefuehrt');

    // D. 2 Seiten zurueck blaettern
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'blaettern', parameter: { richtung: 'zurueck', anzahl: 2 } });
    pruefe(clicks.filter(c => c === 'erzaehl-zurueck').length === 2, 'blaettern zurueck 2x ausgefuehrt');

    // E. Oberstes Event oeffnen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'event_oeffnen', parameter: { index: 0 } });
    pruefe(clicks.includes('event-0'), 'event_oeffnen oeffnet Index 0');

    // F. Erstes Bild oeffnen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'bild_oeffnen', parameter: { index: 0 } });
    pruefe(clicks.includes('bild-0'), 'bild_oeffnen oeffnet Index 0');

    // G. Notiz hinzufuegen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'notiz_hinzufuegen', parameter: { text: 'Toller Sommertag' } });
    pruefe(elements['erzaehl-text'].value.includes('Toller Sommertag'), 'notiz_hinzufuegen traegt Text ein');

    // H. Geschichte erzaehlen
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'geschichte_erzaehlen' });
    pruefe(clicks.includes('ki-geschichte'), 'geschichte_erzaehlen klickt erzaehl-ki-geschichte-btn');

    // I. Neu vorsortieren
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'neu_vorsortieren' });
    pruefe(clicks.includes('neu-vorsortieren'), 'neu_vorsortieren klickt gruppen-neu-vorsortieren-btn');

    // J. Speichern
    clicks.length = 0;
    appAktionAusfuehren({ aktion: 'speichern' });
    pruefe(clicks.includes('speichern'), 'speichern klickt erzaehl-speichern-btn');
}

console.log('\n3) LiveVoiceClient Test');
{
    // Extrahiere LiveVoiceClient
    const classMatch = appSrc.match(/class LiveVoiceClient[\s\S]*?\n\}/);
    pruefe(!!classMatch, 'class LiveVoiceClient extrahiert');

    const LiveVoiceClient = new Function(`
        ${classMatch[0]}
        return LiveVoiceClient;
    `)();

    const client = new LiveVoiceClient();
    pruefe(client.isConnected === false, 'Client initialisiert unverbunden');
    pruefe(typeof client.connect === 'function', 'connect() Methode vorhanden');
    pruefe(typeof client.sendAudioChunk === 'function', 'sendAudioChunk() Methode vorhanden');
    pruefe(typeof client.sendInterrupt === 'function', 'sendInterrupt() Methode vorhanden');
    pruefe(typeof client.disconnect === 'function', 'disconnect() Methode vorhanden');
}

if (fehler > 0) {
    console.error(`\nFEHLER: ${fehler}`);
    process.exit(1);
} else {
    console.log('\nalle Prüfungen grün');
    process.exit(0);
}
