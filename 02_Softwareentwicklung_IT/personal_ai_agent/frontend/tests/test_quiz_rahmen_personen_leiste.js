// SCHRITT F (18.10.2026) — Personen-Leiste im Detailbild-Editor
// (Auftragspunkt 5: "Dasselbe Bedienfeld von der Personenauswahl aus … unten
//  die Personen durchklicken → der zugehoerige Rahmen wird im Bild gezeigt").
//
// Kriterium des Plans (.hermes/plans/2026-10-16_rahmeneditor-detailbild.md,
// Schritt F): "… und dass der Rahmen der angeklickten Person hervorgehoben
// wird." Hervorgehoben heisst im Editor: `sel` steht auf diesem Rahmen
// (resync faerbt ihn gruen, zeigeAuswahlGriffe baut die Griffe).
//
// Aufruf: node tests/test_quiz_rahmen_personen_leiste.js app.js
//   Gegenprobe (alter Stand): git show HEAD:frontend/app.js > alt_app.js
//                            node tests/test_quiz_rahmen_personen_leiste.js alt_app.js  -> rot
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

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'rahmenPersonWahl', 'rahmenPersonSetzen',
               'rahmenPersonMenueListe', 'editorSpeicherZiel', 'rahmenIndizes', 'rahmenUnbekannt',
               'rahmenPersonText', 'rahmenPersonenLeiste', 'rahmenWahlAusLeiste',
               'quizNamenFuerRegion'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

// Sandkasten: die ECHTEN Funktionen laufen gegen Attrappen der Nachbarn.
// `bestaetigtLokal` bildet den lokalen Merker nach (Schluessel = Bildpfad+Region).
function baueSandkasten() {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        const bestaetigtLokal = {};
        function bboxRegionSchluessel() { return 'R'; }
        function istBestaetigtLokal(pfad, region) { return bestaetigtLokal[pfad + '|' + region] || ''; }
        ${quelle}
        return {
            aufbauen: (rahmen, personen, gesichter, person, pfad) => {
                _quizEditor = { bbox_norm_live: rahmen, personen: personen || [],
                                gesichter: gesichter || [], bildPfad: pfad || '' };
                _aktuelleQuizPerson = person || ''; _aktuellerQuizPfad = pfad || '';
                return _quizEditor;
            },
            merken: (pfad, region, wert) => { bestaetigtLokal[pfad + '|' + region] = wert; },
            leiste: () => rahmenPersonenLeiste(_quizEditor, _quizEditor.gesichter || [], _quizEditor.bildPfad || ''),
            wahl: (person) => rahmenWahlAusLeiste(_quizEditor, _quizEditor.gesichter || [], _quizEditor.bildPfad || '', person),
            indizes: () => rahmenIndizes(_quizEditor),
        };
    `;
    return new Function(koerper)();
}

const ZWEI = [[0.10, 0.10, 0.20, 0.20], [0.55, 0.12, 0.18, 0.18]];

console.log('\n1) Zwei Rahmen mit je eigener Person (Schritt G) — beide in der Leiste');
{
    const s = baueSandkasten();
    s.aufbauen(ZWEI, ['Anna', 'Tim'], [], '', '');
    const l = s.leiste();
    pruefe(l.length === 2, 'die Leiste nennt beide Personen', JSON.stringify(l));
    pruefe(l[0] && l[0].idx === 0 && l[0].person === 'Anna', 'Rahmen 0 -> Anna', JSON.stringify(l[0]));
    pruefe(l[1] && l[1].idx === 1 && l[1].person === 'Tim', 'Rahmen 1 -> Tim', JSON.stringify(l[1]));
}

console.log('\n2) Bestaetigte Namen aus der Gesichtsliste, "unbekannt" bleibt draussen');
{
    const s = baueSandkasten();
    // Rahmen 0 ist ausdruecklich unbekannt ('' aus Schritt E) -> KEIN Eintrag,
    // auch wenn die Gesichtsliste dort einen Namen kennt.
    const gesichter = [{ bbox_norm: ZWEI[0], bestaetigt: ['Anna'] },
                       { bbox_norm: ZWEI[1], bestaetigt: ['Tim'] }];
    s.aufbauen(ZWEI, ['', undefined], gesichter, '', '');
    const l = s.leiste();
    pruefe(l.length === 1, 'nur der Rahmen mit Person steht drin', JSON.stringify(l));
    pruefe(l[0] && l[0].idx === 1 && l[0].person === 'Tim', 'Rahmen 1 -> Tim aus bestaetigt', JSON.stringify(l[0]));
    pruefe(!l.some((e) => e.person === 'Anna'), '"unbekannt" bekommt keinen Namen angedichtet');
}

console.log('\n3) Lokaler Merker (bestaetigt) wird mitgelesen');
{
    const s = baueSandkasten();
    s.aufbauen(ZWEI, [undefined, undefined], [{ bbox_norm: ZWEI[0] }, { bbox_norm: ZWEI[1] }], '', 'bild/a.jpg');
    s.merken('bild/a.jpg', 'R', 'Anna');
    const l = s.leiste();
    pruefe(l.length === 1 && l[0].person === 'Anna' && l[0].idx === 0,
        'bestätigter Name erscheint in der Leiste', JSON.stringify(l));
}

console.log('\n4) Ohne bekannte Person: KEINE Eintraege (nichts erfunden)');
{
    const s = baueSandkasten();
    // Globale Zielperson gesetzt — sie gilt fuer das ganze Bild und darf NICHT
    // jedem Rahmen denselben Namen anhaengen.
    s.aufbauen(ZWEI, [undefined, undefined], [{ bbox_norm: ZWEI[0] }, { bbox_norm: ZWEI[1] }], 'Anna', 'bild/a.jpg');
    const l = s.leiste();
    pruefe(l.length === 0, 'leere Leiste statt erfundener Namen', JSON.stringify(l));
}

console.log('\n5) Dieselbe Person in zwei Rahmen: genau EIN Eintrag (der erste Rahmen)');
{
    const s = baueSandkasten();
    s.aufbauen(ZWEI, ['Anna', 'Anna'], [], '', '');
    const l = s.leiste();
    pruefe(l.length === 1 && l[0].idx === 0, 'der erste Rahmen gewinnt', JSON.stringify(l));
}

console.log('\n6) Klick waehlt GENAU den Rahmen der angeklickten Person');
{
    const s = baueSandkasten();
    s.aufbauen(ZWEI, ['Anna', 'Tim'], [], '', '');
    pruefe(s.wahl('Tim') === 1, 'Tim -> Rahmen 1');
    pruefe(s.wahl('anna') === 0, 'Gross-/Kleinschreibung egal');
    pruefe(s.wahl(' Anna ') === 0, 'Leerzeichen werden getrimmt');
    pruefe(s.wahl('Lisa') === -1, 'unbekannte Person -> kein Rahmen');
    pruefe(s.wahl('') === -1, 'leerer Name -> kein Rahmen');
    pruefe(s.wahl(null) === -1, 'null -> kein Rahmen');
}

console.log('\n7) Leere Plaetze sind keine Rahmen (Indizes bleiben richtig)');
{
    const s = baueSandkasten();
    const rahmen = [null, ZWEI[1]];
    s.aufbauen(rahmen, [undefined, 'Tim'], [], '', '');
    const l = s.leiste();
    pruefe(s.indizes().length === 1, 'nur ein vollstaendiger Rahmen', JSON.stringify(s.indizes()));
    pruefe(l.length === 1 && l[0].idx === 1, 'der Rahmen behaelt seinen echten Index', JSON.stringify(l));
}

console.log('\n8) Quelltext-Waechter (Verdrahtung + Cache-Schluessel)');
{
    const bau = src.slice(src.indexOf('// Schritt F (18.10.2026): die PERSONEN-LEISTE'),
                          src.indexOf('if (_quizEditor.dreh) { try { big.style.transform'));
    pruefe(bau.length > 0, 'der Leisten-Block steht in der Werkzeugleiste');
    pruefe(/if \(!_quizEditor\.refKontext\) \{\r?\n {20}const personenLeiste/.test(src),
        'die Leiste entsteht nur ausserhalb der Referenz-Nachbearbeitung');
    pruefe(/vollbild-personen-leiste/.test(bau), 'die Leiste hat eine eigene Kennung');
    pruefe(/sel = idx; resync\(\); zeigeAuswahlGriffe\(\);/.test(bau),
        'der Klick waehlt den Rahmen aus (Hervorhebung)');
    pruefe(/const idx = rahmenWahlAusLeiste\(_quizEditor/.test(bau),
        'der Klick holt den Rahmen aus der reinen Funktion');
    pruefe(/if \(idx < 0\) return;/.test(bau), 'unbekannte Person waehlt NICHTS aus');
    pruefe(/personWahlMalen\(\); personenLeisteMalen\(\);/.test(src),
        'zeigeAuswahlGriffe malt die Leiste mit');
    pruefe(/personenLeiste\.style\.display = 'flex';/.test(bau), 'gefuellte Leiste wird sichtbar');
    pruefe(/if \(!eintraege\.length\) \{ personenLeiste\.style\.display = 'none'; return; \}/.test(bau),
        'leere Leiste bleibt verborgen');
    const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    pruefe(/^\d{8}[A-Z]$/.test(vApp), 'index.html laedt app.js mit ?v= (Muster)', vApp);
    pruefe(vApp >= '20261018L', '?v= app.js ist mindestens 20261018L (Schritt F gebumpt)', vApp);
}

console.log('\n' + (fehler ? 'FEHLER: ' + fehler : 'alle Pruefungen bestanden'));
process.exit(fehler ? 1 : 0);
