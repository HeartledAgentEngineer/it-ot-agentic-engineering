// Vorlese-/Stopp-Umschalter überall (02.11.2026, Wunsch Sebastian).
//
// Befund (Sebastian): "Wenn ich vorlesen lasse, muss der Vorlese-Button mit
// Stopp verbunden sein, damit ich wieder drücken kann, damit es aufhört. Ist
// ganz wichtig, überall." Bisher startete jeder Vorlese-Knopf nur; zum Anhalten
// gab es keinen Weg am selben Knopf.
//
// Ziel: Jeder Vorlese-Knopf ist ein Umschalter. Erster Druck startet (Knopf zeigt
// "⏹ Stopp"), zweiter Druck auf denselben Knopf hält an und setzt den Knopf
// zurück. Startet ein anderer Vorlese-Knopf, wird der vorherige zurückgesetzt.
// Am Ende des Vorlesens setzt sich der Knopf von selbst zurück.
//
// Dieser Test schneidet die reine Label-Funktion aus erzaehlen.js und prüft die
// Verdrahtung (Umschalt-Logik, Knopf-Durchreichung, Rücksetzen, Cache).
//
// Aufruf (aus dem Ordner frontend):  node tests/test_erzaehlen_vorlese_stopp.js
const fs = require('fs');
const path = require('path');

const pfad = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const pfadHtml = path.join(__dirname, '..', 'index.html');
const src = fs.readFileSync(pfad, 'utf8');
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

const f = (function () {
    const teile = funktionAusschneiden(src, 'erzaehlVorleseLabel');
    return new Function(teile + '\nreturn { erzaehlVorleseLabel };')();
})();
const label = f.erzaehlVorleseLabel;

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt); fehler++; }
}

console.log('Vorlese/Stopp: Label-Funktion');
pruefe(label(true, '🔊 Vorlesen') === '⏹ Stopp', 'spielt -> "⏹ Stopp"');
pruefe(label(false, '🔊 Vorlesen') === '🔊 Vorlesen', 'nicht spielt -> Standardbeschriftung zurück');
pruefe(typeof label(false, '') === 'string' && label(false, '') !== '⏹ Stopp',
    'ohne Standard kein "Stopp" (kein Hängenbleiben)');

console.log('Vorlese/Stopp: Verdrahtung in erzaehlen.js');
pruefe(/function vorlesenText\(sprech,\s*knopf\)/.test(src), 'vorlesenText nimmt den Knopf entgegen');
pruefe(/async function vorlesen\(quelleId,\s*knopf\)/.test(src), 'vorlesen nimmt den Knopf entgegen');
// Befund 03.11.2026 (Handy): vorlesen() nahm den Knopf an, gab ihn aber nicht weiter -> kein "Stopp".
pruefe(/vorlesenText\(erzaehlSprechtext\(rohtext\),\s*knopf\)/.test(funktionAusschneiden(src, 'vorlesen')),
    'vorlesen reicht den Knopf an vorlesenText weiter');
pruefe(/aktiverVorleseKnopf/.test(src), 'es gibt einen Merker für den aktiven Knopf');
pruefe(/aktiverVorleseKnopf === knopf/.test(src), 'zweiter Druck auf denselben Knopf hält an (Umschalter)');
pruefe(src.indexOf('function _vorleseFertig(') !== -1, 'ein zentrales Zurücksetzen (_vorleseFertig)');
pruefe(/_knopfVorlese\(aktiverVorleseKnopf,\s*false\)/.test(src),
    'Stoppen/Ende setzt den aktiven Knopf zurück');
pruefe(src.indexOf('window.vorleseTextMitKnopf') !== -1,
    'der Umschalter ist für andere Dateien (Beschreibungs-Box) verfügbar');

console.log('Vorlese/Stopp: alle Knöpfe reichen sich selbst durch');
[
    ["vorlesen('erzaehl-personen-text', vorlesenGruppe)", 'Personen (Gruppe)'],
    ["vorlesen('erzaehl-bild-personen-text', vorlesenBild)", 'Personen (Bild)'],
    ["vorlesen('erzaehl-gruppen-geschichten', vorlesenGeschichtenGruppe)", 'Geschichten (Gruppe)'],
    ["vorlesen('erzaehl-geschichten', vorlesenGeschichtenBild)", 'Geschichten (Bild)'],
    ["vorlesen('erzaehl-bildgeschichte-text', vorlesenBildgeschichte)", 'Bildgeschichte'],
    ["vorlesen('erzaehl-anlassgeschichte-text', vorlesenAnlassgeschichte)", 'Anlassgeschichte'],
    ["allesVorlesen(vorlesenAlles)", 'Alles vorlesen'],
].forEach(([muster, name]) => {
    pruefe(src.indexOf(muster) !== -1, name + ' reicht seinen Knopf durch');
});
pruefe(/vorlesenText\(t,\s*vorlesenBeschreibung\)/.test(src),
    'Beschreibung-Vorlesen reicht seinen Knopf durch');

console.log('Vorlese/Stopp: Cache');
const w = html.match(/erzaehlen\.js\?v=([0-9A-Z]+)/);
pruefe(w && w[1] >= '20261102E', 'Cache-Schlüssel erzaehlen.js mindestens 20261102E, gefunden: ' + (w && w[1]));

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
