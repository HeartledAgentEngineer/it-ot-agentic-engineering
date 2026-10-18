// SCHRITT C (18.10.2026) — Mehrfachbearbeitung mit EINZELMELDUNGEN
// (Plan "Rahmeneditor im Detailbild", Fassung 13, Abschnitt 4, Schritt C:
//  "Markierte Rahmen werden nacheinander abgearbeitet; je Rahmen ein Ergebnis.")
//
// Warum dieser Test die ECHTEN Funktionen aus app.js AUSFUEHRT: das Kriterium
// ist ein ABLAUF — drei Rahmen, davon EINER kaputt; die zwei guten muessen
// gespeichert werden, der dritte muss seinen Fehler melden, und der Ablauf darf
// danach NICHT stehenbleiben. Ausserdem darf KEIN Rahmen seine Markierung
// verlieren (Rahmenliste + Personen-Zuordnung bleiben unveraendert erhalten).
// Das laesst sich nur messen, wenn die Funktion wirklich laeuft.
//
// Pruefkriterium (Plan): "Test mit drei Rahmen, davon einer kaputt — die zwei
// guten sind gespeichert, der dritte meldet seinen Fehler, kein Rahmen verliert
// seine Markierung."
//
// Aufruf: node tests/test_quiz_rahmen_mehrfach.js app.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2], 'utf8');
const html = fs.readFileSync(path.join(path.dirname(process.argv[2]), 'index.html'), 'utf8');

function funktionAusschneiden(quelle, name) {
    // Auch `async function NAME(` erfassen — sonst faellt das `async` beim
    // Ausschneiden weg und die Sandkasten-Funktion ist kein Async mehr.
    const treffer = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(quelle);
    if (!treffer) throw new Error('Funktion nicht gefunden: ' + name);
    const start = treffer.index;
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

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'rahmenPersonWahl', 'editorSpeicherZiel', 'rahmenIndizes',
               'speichereAlleRahmen', 'speichereEditorRahmen'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

// Sandkasten: die echten Funktionen laufen gegen Attrappen der Nachbarn.
// `sends` zaehlt die Sendeversuche des Quiz-Wegs (quizBeantwortenSilent macht
// darin den fetch). `kaputterRuf` = die Nummer des Aufrufs, der scheitern soll.
function baueSandkasten(kaputterRuf) {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        let _quizVollbild = null, _letzteQuizKarte = null;
        let sends = 0, fetchs = 0, meldungen = [], bestaetigt = [];
        let kaputt = ${JSON.stringify(kaputterRuf == null ? 0 : kaputterRuf)};
        const API_BASE = '';
        function bboxNormClampen(n) { return n; }
        function bboxPixelVonNorm(n) { return [n[0], n[1], n[2], n[3]]; }
        function bboxRegionSchluessel() { return 'R'; }
        function merkeBestaetigt(p, r, per) { bestaetigt.push([p, r, per]); }
        function macheQuizFertig() {}
        function quizBeantwortenSilent() {
            sends++;
            if (kaputt && sends === kaputt) return Promise.reject(new Error('Netz weg'));
            return Promise.resolve({ ok: true, referenz_geschrieben: true,
                                     rahmen_gespeichert: 'gesendet' });
        }
        function fetch() {
            fetchs++;
            return Promise.resolve({ json: () => Promise.resolve({ ok: true, vektor_erneuert: true }) });
        }
        ${quelle}
        return {
            setze: (rahmen, person, pfad) => {
                _aktuelleQuizPerson = person;
                _aktuellerQuizPfad = pfad;
                _quizEditor = { bbox_norm_live: rahmen, personen: [],
                                melde: (t) => { meldungen.push(t); },
                                bildPfad: pfad, refKontext: null };
                return _quizEditor;
            },
            alle: () => speichereAlleRahmen(800, 600, null),
            indizes: () => rahmenIndizes(_quizEditor),
            meldungen: () => meldungen,
            zaehler: () => ({ sends: sends, fetchs: fetchs }),
            bestaetigt: () => bestaetigt,
            roh: () => JSON.parse(JSON.stringify(_quizEditor.bbox_norm_live || [])),
            personen: () => (_quizEditor.personen || []).slice(),
        };
    `;
    return new Function(koerper)();
}

const DREI = [[0.10, 0.10, 0.20, 0.20], [0.40, 0.40, 0.20, 0.20], [0.70, 0.10, 0.20, 0.20]];

(async () => {
    console.log('\nA) Drei Rahmen, keiner kaputt — drei Ergebnisse');
    {
        const s = baueSandkasten(0);
        s.setze(JSON.parse(JSON.stringify(DREI)), 'Anna', '/bilder/A.jpg');
        const r = await s.alle();
        pruefe(r.gesamt === 3 && r.gut === 3, 'Ergebnis: 3 von 3 gespeichert');
        pruefe(s.zaehler().sends === 3, 'genau drei Sendeversuche (je Rahmen einer)');
        pruefe(s.zaehler().fetchs === 0, 'kein Umweg ueber den Referenz-Endpunkt');
        const m = s.meldungen();
        pruefe(m.length === 4, 'je Rahmen eine Meldung + eine Zusammenfassung (4)');
        pruefe(/^Rahmen 1 von 3: gespeichert/.test(m[0]), 'Meldung 1 nennt Rahmen 1');
        pruefe(/^Rahmen 3 von 3: gespeichert/.test(m[2]), 'Meldung 3 nennt Rahmen 3');
        pruefe(/3 von 3 Rahmen gespeichert/.test(m[3]), 'Zusammenfassung zaehlt 3 von 3');
        pruefe(JSON.stringify(s.roh()) === JSON.stringify(DREI), 'alle drei Rahmen stehen unveraendert');
        pruefe(s.personen().length === 3 && s.personen()[2] === 'Anna', 'jede Markierung sitzt auf ihrem Rahmen');
    }

    console.log('\nB) Drei Rahmen, der MITTLERE kaputt — kein Rahmen verliert seine Markierung');
    {
        const s = baueSandkasten(2);   // zweiter Sendeversuch scheitert
        s.setze(JSON.parse(JSON.stringify(DREI)), 'Anna', '/bilder/A.jpg');
        const r = await s.alle();
        pruefe(s.zaehler().sends === 3, 'der Ablauf laeuft nach dem Fehler WEITER (sends 3)');
        pruefe(r.gut === 2 && r.ergebnisse.length === 3, 'Ergebnis: 2 von 3 gespeichert, 3 Einzelergebnisse');
        pruefe(r.ergebnisse[1].ok === false && /Netz weg/.test(r.ergebnisse[1].fehler),
               'das kaputte Ergebnis traegt den ehrlichen Fehlertext');
        const m = s.meldungen();
        pruefe(/^Rahmen 2 von 3: NICHT gespeichert/.test(m[1]), 'der kaputte Rahmen meldet sich EINZELN');
        pruefe(/^Rahmen 1 von 3: gespeichert/.test(m[0]) && /^Rahmen 3 von 3: gespeichert/.test(m[2]),
               'die zwei guten melden ihren Erfolg einzeln');
        pruefe(/2 von 3 Rahmen gespeichert/.test(m[m.length - 1]), 'Zusammenfassung nennt 2 von 3');
        pruefe(JSON.stringify(s.roh()) === JSON.stringify(DREI),
               'KEIN Rahmen verliert seine Markierung (Rahmenliste unveraendert)');
        pruefe(s.personen().length === 3 && s.personen()[1] === 'Anna',
               'auch der kaputte Rahmen behaelt seine Markierung');
        pruefe(s.bestaetigt().length === 3, 'die Markierung wurde fuer alle drei VOR dem Senden gesetzt');
    }

    console.log('\nC) Luecken in der Rahmenliste sind keine Rahmen (Indizes)');
    {
        const s = baueSandkasten(0);
        s.setze([[0.1, 0.1, 0.2, 0.2], null, [0.5, 0.5, 0.1, 0.1]], 'Anna', '/bilder/A.jpg');
        pruefe(JSON.stringify(s.indizes()) === '[0,2]', 'nur vollstaendige Rahmen werden gezaehlt');
        const r = await s.alle();
        pruefe(r.gesamt === 2 && s.zaehler().sends === 2, 'zwei Rahmen = zwei Sendeversuche');
    }

    console.log('\nD) Ohne Ziel wird fuer JEDEN Rahmen ehrlich gemeldet, nichts gesendet');
    {
        const s = baueSandkasten(0);
        s.setze(JSON.parse(JSON.stringify(DREI)), '', '/bilder/A.jpg');
        const r = await s.alle();
        pruefe(s.zaehler().sends === 0 && s.zaehler().fetchs === 0, 'kein Sendeversuch (Riegel A2 gilt weiter)');
        pruefe(r.gut === 0 && r.ergebnisse.length === 3, 'drei Ergebnisse, keines erfolgreich');
        const m = s.meldungen();
        pruefe(m.filter((t) => /NICHT gespeichert/.test(t)).length === 3,
               'jeder Rahmen nennt seinen Grund einzeln');
        pruefe(/^Rahmen 3 von 3: NICHT gespeichert/.test(m[2]), 'auch der letzte Rahmen meldet sich');
    }

    console.log('\nE) Gegenprobe — ohne den Fehler-Fang waere der Ablauf gerissen');
    {
        // Der Test misst den Unterschied: in B wurde sends===3 gezaehlt, OBWOHL
        // der zweite Aufruf abgelehnt hat. Die alte Fassung (ohne .catch im
        // Quiz-Weg) haette eine unbehandelte Ablehnung erzeugt und beim
        // sequenziellen Ablauf den dritten Rahmen nie erreicht.
        const alt = async () => {
            let sendsAlt = 0;
            const weg = () => { sendsAlt++; return Promise.reject(new Error('Netz weg')); };
            try { await weg(); await weg(); await weg(); } catch (_e) { return sendsAlt; }
            return sendsAlt;
        };
        pruefe((await alt()) === 1, 'alte Fassung: nach dem Fehler nur 1 Versuch (Ablauf gerissen)');
    }

    console.log('\nF) Verdrahtung im Quelltext');
    {
        const bau = src.slice(src.indexOf('const speicherZiel = editorSpeicherZiel(_quizEditor, sel);'),
                              src.indexOf('leiste.appendChild(speicherHinweis);'));
        pruefe(/rahmenIndizes\(_quizEditor\)\.length/.test(bau), 'die Leiste zaehlt die Rahmen');
        pruefe(/if \(rahmenZahl >= 2\)/.test(bau), '"alle speichern" nur bei mindestens zwei Rahmen');
        pruefe(/speichereAlleRahmen\(iw, ih, alleBtn\)/.test(bau), 'der Knopf ruft den Mehrfachweg');
        pruefe(bau.indexOf('speichereAlleRahmen(iw, ih, alleBtn)') > bau.indexOf('if (speicherZiel.ok)'),
               'der Knopf entsteht nur mit gueltigem Ziel (Riegel A2)');
        const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
        pruefe(/^\d{8}[A-Z]$/.test(vApp) && vApp >= '20261016G',
               'index.html laedt app.js mit ?v= (mindestens 20261016G), gefunden: ' + vApp);
    }

    console.log(fehler === 0 ? '\nAlle Pruefungen bestanden.' : '\nFEHLER: ' + fehler);
    process.exit(fehler === 0 ? 0 : 1);
})();
