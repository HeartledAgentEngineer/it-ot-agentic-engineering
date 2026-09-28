// Hermes-Live-Status: welcher Auftrag gehört in den grünen Balken? (28.09.2026)
//
// Befund (Sebastian): Der Balken „Hermes wurde benachrichtigt, warte auf
// Bearbeitung" stand dauerhaft oben, obwohl nichts lief. Ursachen: (1) jeder
// je "offen" gebliebene Auftrag wurde gezeigt, egal wie alt; (2) es wurde der
// ÄLTESTE gezeigt, weil die Liste neueste-zuerst kommt und der Code das letzte
// Element nahm.
//
// Dieser Test schneidet die REINE Funktion hermesLiveJobWaehlen() aus dem
// echten app.js aus und prüft Alter, Reihenfolge, Status und Wegklicken.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_hermes_live_status.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(pfadApp, 'utf8');

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

const hermesLiveJobWaehlen = new Function(
    funktionAusschneiden(src, 'hermesLiveJobWaehlen') + '; return hermesLiveJobWaehlen;')();

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

// Echtes Format aus auftrag_service._jetzt(): ISO mit Zeitzone, z. B.
// "2026-09-28T22:20:42+02:00" (in Meldungen als "[<zeit>] text").
const jetzt = Date.parse('2026-09-28T22:30:00+02:00');
const vor = (min) => new Date(jetzt - min * 60000).toISOString().slice(0, 19) + 'Z';

console.log('Hermes-Live-Status: Auswahl');
pruefe(hermesLiveJobWaehlen([], jetzt, []) === null, 'leere Liste -> kein Balken');
pruefe(hermesLiveJobWaehlen(null, jetzt, []) === null, 'kaputte Antwort -> kein Balken');

const alt = { id: 'alt', status: 'offen', erstellt: vor(600), status_meldungen: [] };
pruefe(hermesLiveJobWaehlen([alt], jetzt, []) === null, '10 h alter offener Auftrag -> kein Balken (war der Fehler)');

const frisch = { id: 'frisch', status: 'laeuft', erstellt: vor(5), status_meldungen: [] };
pruefe(hermesLiveJobWaehlen([frisch], jetzt, []).id === 'frisch', 'frischer laufender Auftrag -> Balken');

const fertig = { id: 'fertig', status: 'fertig', erstellt: vor(1), status_meldungen: [] };
pruefe(hermesLiveJobWaehlen([fertig], jetzt, []) === null, 'fertiger Auftrag -> kein Balken');

const neu = { id: 'neu', status: 'offen', erstellt: vor(2), status_meldungen: [] };
const aelter = { id: 'aelter', status: 'offen', erstellt: vor(20), status_meldungen: [] };
pruefe(hermesLiveJobWaehlen([neu, aelter], jetzt, []).id === 'neu', 'neueste-zuerst-Liste -> NEUESTER wird gezeigt');
pruefe(hermesLiveJobWaehlen([aelter, neu], jetzt, []).id === 'neu', 'Reihenfolge egal -> NEUESTER wird gezeigt');

const lebendig = { id: 'lebendig', status: 'laeuft', erstellt: vor(300),
    status_meldungen: ['[2026-09-28T22:27:00+02:00] arbeite noch'] };
pruefe(hermesLiveJobWaehlen([lebendig], jetzt, []).id === 'lebendig', 'alt erstellt, aber frische Meldung -> Balken');

pruefe(hermesLiveJobWaehlen([frisch], jetzt, ['frisch']) === null, 'weggeklickter Auftrag -> kein Balken');
pruefe(hermesLiveJobWaehlen([frisch, neu], jetzt, ['frisch']).id === 'neu', 'weggeklickt + anderer offen -> der andere');

const ohneZeit = { id: 'ohneZeit', status: 'offen', status_meldungen: [] };
pruefe(hermesLiveJobWaehlen([ohneZeit], jetzt, []) === null, 'Auftrag ohne Zeit -> gilt als alt, kein Balken');

pruefe(/hermesLiveJobWaehlen\(jobs, Date\.now\(\), ausgeblendetLesen\(\)\)/.test(src), 'Poller nutzt die Auswahlfunktion');
pruefe(src.indexOf("relevant[relevant.length - 1]") === -1, 'alte Ältester-statt-Neuester-Stelle ist weg');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
