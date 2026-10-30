// SCHRITT G (18.10.2026) — Zielperson JE RAHMEN ("Auswahlliste statt nur
// 'ist nicht <Name>'", Auftragspunkt 2 des Detailbild-Auftrags).
//
// Kriterium des Plans (.hermes/plans/2026-10-16_rahmeneditor-detailbild.md,
// Schritt G): JS-Test mit ZWEI Rahmen und ZWEI Personen — nach dem Setzen
// traegt jeder Rahmen seine eigene Person (Zustand `_quizEditor.personen`), und
// der SENDEAUFRUF nennt je Rahmen die richtige Person (Zaehler + Namen).
// Gegenprobe: ohne Menuewahl bleibt die globale Zielperson unveraendert.
//
// Aufruf: node tests/test_quiz_rahmen_person_je_rahmen.js app.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2], 'utf8');
const html = fs.readFileSync(path.join(path.dirname(process.argv[2]), 'index.html'), 'utf8');

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

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'rahmenPersonWahl', 'rahmenPersonSetzen',
               'rahmenPersonMenueListe', 'editorSpeicherZiel', 'speichereEditorRahmen'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

// Sandkasten: die ECHTEN Funktionen laufen gegen Attrappen der Nachbarn.
// `sendungen` protokolliert JEDEN Sendeaufruf mit Bildpfad UND Person — damit
// ist "je Rahmen die richtige Person" messbar und nicht nur behauptet.
function baueSandkasten() {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        let _quizVollbild = null, _letzteQuizKarte = null;
        let sendungen = [], fetchs = 0, meldungen = [];
        const API_BASE = '';
        function bboxNormClampen(n) { return n; }
        function bboxPixelVonNorm(n) { return [n[0], n[1], n[2], n[3]]; }
        function bboxRegionSchluessel() { return 'R'; }
        function merkeBestaetigt() {}
        function macheQuizFertig() {}
        function quizBeantwortenSilent(pfad, person) {
            sendungen.push({ pfad: pfad, person: person });
            return Promise.resolve({ ok: true, referenz_geschrieben: true, rahmen_gespeichert: 'gesendet' });
        }
        function fetch() { fetchs++; return Promise.resolve({ json: () => Promise.resolve({ ok: true }) }); }
        ${quelle}
        return {
            // Editor mit n Rahmen aufbauen; globale Zielperson/Quizpfad setzen.
            aufbauen: (person, pfad, rahmen, personen) => {
                _aktuelleQuizPerson = person; _aktuellerQuizPfad = pfad;
                _quizEditor = { bbox_norm_live: rahmen, personen: personen || [],
                                melde: (t) => { meldungen.push(t); }, bildPfad: pfad };
                return _quizEditor;
            },
            wahl: (idx) => rahmenPersonWahl(_quizEditor, idx),
            setzen: (idx, person) => rahmenPersonSetzen(_quizEditor, idx, person),
            liste: (katalog, aktuell) => rahmenPersonMenueListe(katalog, aktuell),
            ziel: (idx) => editorSpeicherZiel(_quizEditor, idx),
            speichern: (idx) => speichereEditorRahmen(idx, 800, 600, null),
            personen: () => (_quizEditor.personen || []).slice(),
            globalPerson: () => _aktuelleQuizPerson,
            zaehler: () => ({ sendungen: sendungen.slice(), fetchs: fetchs }),
            meldungen: () => meldungen.slice(),
        };
    `;
    return new Function(koerper)();
}

const ZWEI = [[0.10, 0.10, 0.20, 0.20], [0.55, 0.12, 0.18, 0.18]];

console.log('\nA) Zwei Rahmen, zwei Personen — jeder Rahmen traegt seine eigene');
{
    const s = baueSandkasten();
    // WICHTIG: die globale Zielperson ist LEER — die Zuordnung kommt allein aus
    // dem Menue je Rahmen. Genau das war vor Schritt G nicht moeglich.
    s.aufbauen('', '/bilder/A.jpg', ZWEI, []);
    const w0 = s.setzen(0, 'Anna');
    const w1 = s.setzen(1, 'Tim');
    pruefe(w0 === 'Anna' && w1 === 'Tim', 'beide Rahmen uebernehmen ihre Person');
    pruefe(s.personen().length === 2 && s.personen()[0] === 'Anna' && s.personen()[1] === 'Tim',
           'Zustand _quizEditor.personen traegt beide (je Rahmen eine)');
    pruefe(s.wahl(0) === 'Anna' && s.wahl(1) === 'Tim',
           'rahmenPersonWahl nennt je Rahmen die eigene Person');
    pruefe(s.ziel(0).person === 'Anna' && s.ziel(1).person === 'Tim',
           'editorSpeicherZiel gilt je Rahmen als erfuellt (keine globale Person noetig)');
}

console.log('\nB) Der SENDEAUFRUF nennt je Rahmen die richtige Person (Zaehler + Namen)');
{
    const s = baueSandkasten();
    s.aufbauen('', '/bilder/A.jpg', ZWEI, []);
    s.setzen(0, 'Anna');
    s.setzen(1, 'Tim');
    Promise.all([s.speichern(0), s.speichern(1)]).then(() => {
        const z = s.zaehler();
        pruefe(z.sendungen.length === 2, 'genau zwei Sendeversuche (einer je Rahmen)');
        pruefe(z.sendungen[0] && z.sendungen[0].person === 'Anna' &&
               z.sendungen[0].pfad === '/bilder/A.jpg',
               'Rahmen 1 sendet Bildpfad + "Anna"');
        pruefe(z.sendungen[1] && z.sendungen[1].person === 'Tim' &&
               z.sendungen[1].pfad === '/bilder/A.jpg',
               'Rahmen 2 sendet denselben Bildpfad + "Tim"');
        pruefe(z.fetchs === 0, 'der Referenz-Weg wird dabei nicht angefasst (fetch 0)');
        console.log(fehler === 0 ? '\nAlle Pruefungen bestanden.' : '\nFEHLER: ' + fehler);
        process.exit(fehler === 0 ? 0 : 1);
    });
}

console.log('\nC) Gegenprobe: ohne Menuewahl bleibt die globale Zielperson unveraendert');
{
    const s = baueSandkasten();
    s.aufbauen('Anna', '/bilder/A.jpg', ZWEI, [null, null]);
    pruefe(s.wahl(0) === 'Anna' && s.wahl(1) === 'Anna',
           'ohne eigenen Eintrag gilt weiter die globale Zielperson (rueckwaertsvertraeglich)');
    pruefe(s.ziel(1).ok === true && s.ziel(1).person === 'Anna',
           'der zweite Rahmen speichert wie bisher auf die globale Person');
    s.setzen(1, 'Tim');
    pruefe(s.globalPerson() === 'Anna',
           'das Setzen fuer EINEN Rahmen aendert die globale Zielperson NICHT');
    pruefe(s.wahl(0) === 'Anna',
           'der andere Rahmen behaelt die globale Person');
}

console.log('\nD) Von Hand gezogene Rahmen ("unbekannt") werden zuordenbar (Schritt E -> G)');
{
    const s = baueSandkasten();
    s.aufbauen('Anna', '/bilder/A.jpg', ZWEI, ['', null]);
    s.speichern(0);
    pruefe(s.zaehler().sendungen.length === 0,
           'ein unbekannter Rahmen sendet nichts (Riegel aus Schritt E gilt weiter)');
    pruefe((s.meldungen().join(' ') || '').indexOf('unbekannt') !== -1,
           'die Meldung nennt den Grund ehrlich ("unbekannt")');
    s.setzen(0, 'Tim');
    pruefe(s.ziel(0).ok === true && s.ziel(0).person === 'Tim',
           'nach der Menuewahl ist genau DIESER Rahmen speicherbar');
    // Leerwahl (zurueck auf "unbekannt"): getrimmt, kein Geistername.
    pruefe(s.setzen(0, '   ') === '' && s.ziel(0).person === 'Anna',
           'eine Leerwahl setzt den Rahmen zurueck auf "unbekannt" (globale Person gilt wieder)');
}

console.log('\nE) Ungueltige Eingaben veraendern nichts');
{
    const s = baueSandkasten();
    s.aufbauen('', '/bilder/A.jpg', ZWEI, []);
    pruefe(s.setzen(5, 'Anna') === '', 'Rahmen 5 gibt es nicht — nichts gesetzt');
    pruefe(s.setzen(-1, 'Anna') === '', 'negativer Index — nichts gesetzt');
    pruefe(s.personen().length === 0, 'kein Eintrag entstanden');
    pruefe(s.wahl(0) === '' && s.wahl(1) === '', 'ohne eigene und globale Person ist die Wahl leer');
}

console.log('\nF) Menue-Liste: eigener Wert vorn, keine Doppelten, keine Leerzeilen');
{
    const s = baueSandkasten();
    const l1 = s.liste(['Anna', 'Tim'], 'Tim');
    pruefe(l1.length === 2 && l1[0] === 'Tim' && l1[1] === 'Anna',
           'der gesetzte Wert steht vorn, jeder Name genau einmal');
    const l2 = s.liste([' Anna ', '', null, 'Anna', 'Bea'], 'Anna');
    pruefe(l2.length === 2 && l2[0] === 'Anna' && l2[1] === 'Bea',
           'Leerraum wird beschnitten, Leeres/Doppeltes faellt weg');
    const l3 = s.liste(null, '  Tim  ');
    pruefe(l3.length === 1 && l3[0] === 'Tim', 'ohne Katalog bleibt der gesetzte Wert');
}

console.log('\nG) Verdrahtung im Quelltext');
{
    pruefe(/vollbild-person-wahl/.test(src), 'das Menue hat eine eigene Kennung');
    pruefe(/rahmenPersonSetzen\(_quizEditor, sel/.test(src),
           'das Menue setzt die Person fuer den AUSGEWAEHLTEN Rahmen');
    pruefe(/const speicherZiel = editorSpeicherZiel\(_quizEditor, sel\);/.test(src),
           'die Werkzeugleiste fragt das Ziel fuer den ausgewaehlten Rahmen');
    pruefe(/if \(!_quizEditor\.refKontext\) \{\r?\n {20}const personWahl/.test(src),
           'in der Referenz-Nachbearbeitung gibt es kein Personen-Menue');
    pruefe(/nm\.style\.display = \(unb \|\| eigenName\)/.test(src),
           'ein Rahmen mit eigener Person zeigt deren Namen an');
    const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    pruefe(/^\d{8}[A-Z]$/.test(vApp) && vApp >= '20261018J',
           'index.html laedt app.js mit ?v= (mindestens 20261018J), gefunden: ' + vApp);
}

// (B laeuft asynchron und beendet den Prozess.)
