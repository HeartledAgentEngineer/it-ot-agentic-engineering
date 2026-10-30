// SCHRITT I (18.10.2026) — "Erkennung fuer dieses EINE Bild neu starten"
// (Auftragspunkt 3 des Rahmeneditor-Plans, .hermes/plans/2026-10-16_rahmeneditor-detailbild.md).
//
// Kriterium des Plans (Fassung 9/10, verschaerft nach Befund 3): eine reine
// ZAEHLUNG vorher/nachher genuegt NICHT. Je bereits bestaetigtem Rahmen muessen
// Koordinaten UND Personenzuordnung WERTGLEICH bleiben — auch wenn der neue
// Lauf die Gesichter in VERTAUSCHTER Reihenfolge liefert; Neufunde kommen
// zusaetzlich dazu, und die Meldung nennt die Zahl der Neufunde.
//
// Aufruf:               node tests/test_quiz_rahmen_neu_erkennen.js app.js
// Gegenprobe (alt):     git show HEAD:frontend/app.js > alt_app.js
//                       node tests/test_quiz_rahmen_neu_erkennen.js alt_app.js  -> rot
const fs = require('fs');
const path = require('path');

const quellePfad = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(quellePfad, 'utf8');
const html = fs.readFileSync(path.join(path.dirname(path.resolve(quellePfad)), 'index.html'), 'utf8');

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
function pruefe(bed, text, detail) {
    if (bed) { console.log('  OK   ' + text); }
    else { fehler++; console.log('  FEHL ' + text + (detail ? '  -> ' + detail : '')); }
}
function gleich(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

const NAMEN = ['bboxRegionSchluessel', 'bboxNormClampen', 'bboxUeberdeckung',
               'rahmenNeuErkennen', 'rahmenIndizes'];
// Gegenprobe-tauglich: fehlt eine Funktion im geprueften Stand, wird sie durch
// eine leere Attrappe ersetzt — dann faellt JEDE Pruefung einzeln durch, statt
// dass das Skript beim Ausschneiden abbricht (so ist "vorher" zaehlbar rot).
const fehlend = [];
const quelle = NAMEN.map((n) => {
    try { return funktionAusschneiden(src, n); } catch (_e) {
        fehlend.push(n);
        return 'function ' + n + '() { return { bbox_norm_live: [], personen: [], behalten: 0, neu: 0 }; }';
    }
}).join('\n');
if (fehlend.length) console.log('  HINWEIS: im geprueften Stand fehlen: ' + fehlend.join(', '));

// Sandkasten: die ECHTEN Funktionen laufen gegen Attrappen der Nachbarn.
function baueSandkasten() {
    return new Function(`
        let _quizEditor = null;
        ${quelle}
        return {
            setzen: (rahmen, personen) => {
                _quizEditor = { bbox_norm_live: rahmen, personen: personen || [] };
                return _quizEditor;
            },
            zusammen: (gesichter, altNorm, altPersonen, schwelle) =>
                rahmenNeuErkennen(gesichter, altNorm, altPersonen, schwelle),
            indizes: () => rahmenIndizes(_quizEditor),
            ueberdeckung: (a, b) => bboxUeberdeckung(a, b),
        };
    `)();
}

// Zwei Gesichter + ein drittes (fuer Neufunde).
const A = [0.10, 0.10, 0.20, 0.20];
const B = [0.55, 0.12, 0.18, 0.18];
const C = [0.30, 0.60, 0.15, 0.15];

console.log('\n1) VERTAUSCHTE Erkennungsreihenfolge: Koordinaten UND Person bleiben wertgleich');
{
    const s = baueSandkasten();
    s.setzen([A, B], ['Anna', 'Tim']);
    // Die Engine liefert dieselben zwei Gesichter in UMGEKEHRTER Reihenfolge.
    const r = s.zusammen([{ bbox_norm: B }, { bbox_norm: A }], [A, B], ['Anna', 'Tim']);
    pruefe(gleich(r.bbox_norm_live[0], A), 'Rahmen 0 bleibt Rahmen A (wertgleich)', JSON.stringify(r.bbox_norm_live[0]));
    pruefe(gleich(r.bbox_norm_live[1], B), 'Rahmen 1 bleibt Rahmen B (wertgleich)', JSON.stringify(r.bbox_norm_live[1]));
    pruefe(r.personen[0] === 'Anna', 'Person von Rahmen 0 bleibt Anna (wandert NICHT mit der Reihenfolge)', r.personen[0]);
    pruefe(r.personen[1] === 'Tim', 'Person von Rahmen 1 bleibt Tim', r.personen[1]);
    pruefe(r.neu === 0, 'kein Neufund gemeldet', String(r.neu));
    pruefe(r.behalten === 2, 'beide vorhandenen Rahmen bestaetigt', String(r.behalten));
    pruefe(r.bbox_norm_live.length === 2, 'die Zahl der Rahmen bleibt gleich', String(r.bbox_norm_live.length));
}

console.log('\n2) Vertauschte Reihenfolge mit DREI Rahmen (zyklisch) — jede Person bleibt bei ihrem Rahmen');
{
    const s = baueSandkasten();
    s.setzen([A, B, C], ['Anna', 'Tim', 'Bea']);
    const r = s.zusammen([{ bbox_norm: C }, { bbox_norm: A }, { bbox_norm: B }], [A, B, C], ['Anna', 'Tim', 'Bea']);
    pruefe(gleich(r.personen, ['Anna', 'Tim', 'Bea']), 'Personen bleiben an ihren Rahmen', JSON.stringify(r.personen));
    pruefe(gleich(r.bbox_norm_live, [A, B, C]), 'keine Koordinate wandert', JSON.stringify(r.bbox_norm_live));
    pruefe(r.neu === 0, 'kein Neufund', String(r.neu));
}

console.log('\n3) Leicht VERSCHOBEN erkannt (andere 1-%-Region, ueberlappt aber): alter Rahmen gewinnt');
{
    const s = baueSandkasten();
    const verschoben = [0.11, 0.11, 0.20, 0.20];
    pruefe(s.ueberdeckung(A, verschoben) > 0.5, 'die Rahmen ueberlappen sich deutlich',
        String(s.ueberdeckung(A, verschoben)));
    pruefe(s.ueberdeckung(A, verschoben) < 1, 'die Koordinaten sind NICHT identisch (echter Test)',
        String(s.ueberdeckung(A, verschoben)));
    const r = s.zusammen([{ bbox_norm: verschoben }], [A], ['Anna']);
    pruefe(gleich(r.bbox_norm_live[0], A), 'die Korrektur bleibt wertgleich (kein Zittern)', JSON.stringify(r.bbox_norm_live[0]));
    pruefe(r.personen[0] === 'Anna', 'die Person bleibt', r.personen[0]);
    pruefe(r.neu === 0 && r.bbox_norm_live.length === 1, 'kein zweiter Rahmen fuer dasselbe Gesicht',
        JSON.stringify([r.neu, r.bbox_norm_live.length]));
}

console.log('\n4) NEUFUND kommt ZUSAMMEN mit dem Ergebnis dazu (ohne Person)');
{
    const s = baueSandkasten();
    s.setzen([A], ['Anna']);
    const r = s.zusammen([{ bbox_norm: A }, { bbox_norm: C }], [A], ['Anna']);
    pruefe(r.bbox_norm_live.length === 2, 'ein Rahmen mehr', String(r.bbox_norm_live.length));
    pruefe(gleich(r.bbox_norm_live[0], A) && r.personen[0] === 'Anna', 'der vorhandene Rahmen bleibt unveraendert',
        JSON.stringify([r.bbox_norm_live[0], r.personen[0]]));
    pruefe(gleich(r.bbox_norm_live[1], C), 'der Neufund sitzt an seinem Platz', JSON.stringify(r.bbox_norm_live[1]));
    pruefe(r.personen[1] === '', 'der Neufund ist ausdruecklich „unbekannt" (nichts erfunden)', JSON.stringify(r.personen[1]));
    pruefe(r.neu === 1, 'genau EIN Neufund gemeldet', String(r.neu));
}

console.log('\n5) Leere oder unbrauchbare Erkennung aendert NICHTS (kein Rahmen faellt weg)');
{
    const s = baueSandkasten();
    s.setzen([A, B], ['Anna', 'Tim']);
    const leer = s.zusammen([], [A, B], ['Anna', 'Tim']);
    pruefe(gleich(leer.bbox_norm_live, [A, B]) && gleich(leer.personen, ['Anna', 'Tim']),
        'leere Antwort: alles bleibt', JSON.stringify([leer.bbox_norm_live, leer.personen]));
    pruefe(leer.neu === 0 && leer.behalten === 0, 'nichts gemeldet, nichts behalten', JSON.stringify([leer.neu, leer.behalten]));

    const s2 = baueSandkasten();
    s2.setzen([A], ['Anna']);
    const ohne = s2.zusammen([{ bbox: [1, 2, 3, 4] }, { bbox_norm: null }, {}], [A], ['Anna']);
    pruefe(gleich(ohne.bbox_norm_live, [A]) && ohne.neu === 0,
        'Gesichter OHNE bbox_norm werden uebersprungen (kein Erfinden)', JSON.stringify(ohne.bbox_norm_live));
}

console.log('\n6) Ein weit entferntes Gesicht ist KEIN Treffer — der alte Rahmen bleibt trotzdem stehen');
{
    const s = baueSandkasten();
    const weit = [0.70, 0.70, 0.10, 0.10];
    pruefe(s.ueberdeckung(A, weit) === 0, 'keine Ueberdeckung', String(s.ueberdeckung(A, weit)));
    const r = s.zusammen([{ bbox_norm: weit }], [A], ['Anna']);
    pruefe(r.bbox_norm_live.length === 2 && gleich(r.bbox_norm_live[0], A), 'nichts wird ersetzt oder geloescht',
        JSON.stringify(r.bbox_norm_live));
    pruefe(r.neu === 1, 'das entfernte Gesicht gilt als Neufund', String(r.neu));
}

console.log('\n7) Schon geloeschte Plaetze (null) bleiben geloescht und werden nicht neu belegt');
{
    const s = baueSandkasten();
    s.setzen([null, B], [undefined, 'Tim']);
    const r = s.zusammen([{ bbox_norm: A }, { bbox_norm: B }], [null, B], [undefined, 'Tim']);
    pruefe(r.bbox_norm_live[0] === null, 'der geloeschte Platz bleibt null (nicht wieder gefuellt)',
        JSON.stringify(r.bbox_norm_live[0]));
    pruefe(r.personen[1] === 'Tim', 'der zweite Rahmen behaelt seine Person', r.personen[1]);
    pruefe(r.neu === 1, 'A kommt als eigener Neufund dazu', String(r.neu));
    pruefe(r.bbox_norm_live.length === 3 && r.bbox_norm_live.filter((n) => n && n.length >= 4).length === 2,
        'gezaehlt werden nur vollstaendige Rahmen (der leere Platz zaehlt nicht)',
        JSON.stringify(r.bbox_norm_live.map((n) => (n && n.length >= 4 ? 'rahmen' : n))));
}

console.log('\n8) Quelltext-Waechter (Knopf, Route, ehrliche Engine-Luecke, Cache)');
{
    const knopf = src.indexOf("// Schritt I (18.10.2026): \"🔍 Neu erkennen\"");
    const menue = src.indexOf('// Schritt G (18.10.2026): Ziel-Personen-Menue JE RAHMEN');
    const bau = (knopf >= 0 && menue > knopf) ? src.slice(knopf, menue) : '';
    pruefe(bau.length > 0, 'der Neu-erkennen-Block steht in der Werkzeugleiste');
    pruefe(/if \(!_quizEditor\.refKontext\) \{\r?\n {20}const erkennBtn/.test(bau),
        'der Knopf entsteht nur ausserhalb der Referenz-Nachbearbeitung');
    pruefe(/vollbild-neu-erkennen/.test(bau), 'der Knopf hat eine eigene Kennung');
    pruefe(/erkenneDiesesBildNeu\(\)/.test(bau), 'der Klick ruft die Neu-Erkennung');
    pruefe(/🔍 Neu erkennen/.test(bau), 'der Knopf ist sichtbar beschriftet');
    pruefe(/leiste\.style\.cssText = 'position:fixed;bottom:74px;left:0;right:0;margin:0 auto;width:fit-content;[^']*flex-wrap:wrap[^']*max-width:96vw/.test(src),
        'die Werkzeugleiste bricht um und bleibt im Fenster (Knoepfe erreichbar)');

    const fnStart = src.indexOf('async function erkenneDiesesBildNeu()');
    pruefe(fnStart > 0, 'die Neu-Erkennung existiert');
    const fn = fnStart > 0 ? src.slice(fnStart, fnStart + 4200) : '';
    pruefe(/\/api\/gesichter\/quiz\/analysiere/.test(fn), 'sie nutzt die vorhandene Analyse-Route');
    pruefe(/rahmenNeuErkennen\(antwort\.gesichter/.test(fn), 'sie verschmilzt ueber die reine Funktion');
    pruefe(fn.indexOf('rahmenListeVerschmelzen') === -1,
        'sie nutzt NICHT die positionsbasierte Verschmelzung (Befund 3)');
    pruefe(fn.indexOf('engine_verfuegbar === false') < fn.indexOf('rahmenNeuErkennen('),
        'die Engine-Luecke wird VOR jeder Aenderung ehrlich gemeldet');
    pruefe(/bleiben unveraendert/.test(fn), 'die Meldung nennt, was unveraendert bleibt');
    pruefe(/neue\(s\) Gesicht\(er\) dazu/.test(fn), 'die Meldung nennt die Zahl der Neufunde');
    pruefe(/snapshotVorAenderung\(\)/.test(fn), 'ein Zurueck-Schnappschuss vor der Aenderung');

    const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    pruefe(/^\d{8}[A-Z]$/.test(vApp), 'index.html laedt app.js mit ?v= (Muster)', vApp);
    pruefe(vApp >= '20261018M', '?v= app.js ist mindestens 20261018M (Schritt I gebumpt)', vApp);
}

console.log('\n' + (fehler ? 'FEHLER: ' + fehler : 'alle Pruefungen bestanden'));
process.exit(fehler ? 1 : 0);
