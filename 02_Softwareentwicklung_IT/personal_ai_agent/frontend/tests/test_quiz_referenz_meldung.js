// SCHRITT A3 (16.10.2026) — der Quiz-Weg behauptet eine Referenz nur noch dann,
// wenn der Server sie wirklich geschrieben hat UND die gespeicherten Koordinaten
// der GESENDETE (Nutzer-)Rahmen sind.
//
// Warum ausgefuehrt und nicht nur gesucht: die Meldung haengt an drei
// Antwortformen des Servers (`referenz_geschrieben` true/false,
// `rahmen_gespeichert` 'gesendet'/'erkannt'). Der Test laesst die echte Funktion
// `speichereEditorRahmen` gegen jede Form laufen und liest den Text, der
// wirklich beim Nutzer ankommt.
//
// Aufruf: node tests/test_quiz_referenz_meldung.js app.js
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

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'editorSpeicherZiel',
               'speichereEditorRahmen', 'schliesseBildVollbild'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

function baueSandkasten() {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        let _quizVollbild = null, _letzteQuizKarte = null;
        let sends = 0, fetchs = 0, meldungen = [], antwort = { ok: true };
        const API_BASE = '';
        function bboxNormClampen(n) { return n; }
        function bboxPixelVonNorm(n) { return [n[0], n[1], n[2], n[3]]; }
        function bboxRegionSchluessel() { return 'R'; }
        function merkeBestaetigt() {}
        function macheQuizFertig() {}
        function quizBeantwortenSilent() { sends++; return Promise.resolve(antwort); }
        function fetch() { fetchs++; return Promise.resolve({ json: () => Promise.resolve({ ok: true }) }); }
        ${quelle}
        return {
            setzeAntwort: (a) => { antwort = a; },
            mitZiel: () => {
                _aktuelleQuizPerson = 'Anna'; _aktuellerQuizPfad = '/bilder/A.jpg';
                _quizEditor = { bbox_norm_live: [[0.1, 0.1, 0.2, 0.2]], personen: [],
                                melde: (t) => { meldungen.push(t); },
                                bildPfad: '/bilder/A.jpg', refKontext: null };
            },
            speichern: () => speichereEditorRahmen(0, 800, 600, null),
            meldungen: () => meldungen,
            zaehler: () => ({ sends: sends, fetchs: fetchs }),
        };
    `;
    return new Function(koerper)();
}

const tick = () => new Promise((r) => setTimeout(r, 0));

(async () => {
    console.log('\nA) gesendeter Rahmen + geschriebene Referenz -> Referenz wird benannt');
    {
        const s = baueSandkasten();
        s.setzeAntwort({ ok: true, referenz_geschrieben: true, rahmen_gespeichert: 'gesendet', grund: '' });
        s.mitZiel();
        s.speichern();
        await tick();
        const t = s.meldungen().join(' | ');
        pruefe(s.zaehler().sends === 1, 'genau ein Sendeversuch');
        pruefe(/liegt als Referenz im Datenbestand/.test(t), 'Meldung: Rahmen liegt als Referenz vor');
    }

    console.log('\nB) Referenz mit ERKANNTEM Rahmen -> wird als Rueckfall benannt, nicht als Nutzerrahmen');
    {
        const s = baueSandkasten();
        s.setzeAntwort({ ok: true, referenz_geschrieben: true, rahmen_gespeichert: 'erkannt',
                         grund: 'Ausschnitt-Einbettung nicht moeglich - Detektor-Rahmen als Rueckfall' });
        s.mitZiel();
        s.speichern();
        await tick();
        const t = s.meldungen().join(' | ');
        pruefe(/ERKANNTEN Rahmen/.test(t), 'Meldung nennt den erkannten Rahmen ausdruecklich');
        pruefe(!/Datenbestand/.test(t), 'behauptet NICHT, der verschobene Rahmen sei gespeichert');
    }

    console.log('\nC) KEINE Referenz -> kein Referenz-Versprechen, Grund wird genannt');
    {
        const s = baueSandkasten();
        s.setzeAntwort({ ok: true, referenz_geschrieben: false, rahmen_gespeichert: null,
                         grund: 'Cosinus-Distanz unter 0,05 - keine neue Referenz' });
        s.mitZiel();
        s.speichern();
        await tick();
        const t = s.meldungen().join(' | ');
        pruefe(/KEINE neue Referenz/.test(t), 'Meldung sagt ausdruecklich: keine neue Referenz');
        pruefe(/0,05/.test(t), 'der ehrliche Grund des Servers steht in der Meldung');
        pruefe(!/Datenbestand/.test(t), 'kein Referenz-Versprechen');
    }

    console.log('\nD) Fehlende Felder (aeltere Antwortform) -> keine Referenz-Behauptung');
    {
        const s = baueSandkasten();
        s.setzeAntwort({ ok: true });          // Antwortform VOR A3
        s.mitZiel();
        s.speichern();
        await tick();
        const t = s.meldungen().join(' | ');
        pruefe(!/Datenbestand/.test(t), 'ohne Felder wird nichts behauptet');
        pruefe(/KEINE neue Referenz|kein neuer Vektor/.test(t), 'Grund wird trotzdem genannt');
    }

    console.log('\nE) Verdrahtung: die drei Zweige stehen wirklich im Quelltext');
    {
        const stelle = funktionAusschneiden(src, 'speichereEditorRahmen');
        pruefe(/d\.referenz_geschrieben && d\.rahmen_gespeichert === 'gesendet'/.test(stelle),
               'Bedingung prueft referenz_geschrieben UND gesendeten Rahmen');
        pruefe(/else if \(d\.referenz_geschrieben\)/.test(stelle),
               'zweiter Zweig fuer den Detektor-Rueckfall');
        pruefe(/d\.grund/.test(stelle), 'der Servergrund wird angezeigt');
        const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
        pruefe(/^\d{8}[A-Z]$/.test(vApp) && vApp >= '20261016E',
               'index.html laedt app.js mit ?v= (mindestens 20261016E), gefunden: ' + vApp);
    }

    console.log(fehler === 0 ? '\nAlle Pruefungen bestanden.' : '\nFEHLER: ' + fehler);
    process.exit(fehler === 0 ? 0 : 1);
})();
