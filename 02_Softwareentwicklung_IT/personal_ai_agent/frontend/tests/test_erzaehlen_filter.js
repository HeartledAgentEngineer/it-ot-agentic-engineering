// Zeitfilter und Reihenfolge der Anlässe (F1, 03.11.2026).
//
// Befund: Jahr- und Suchfeld riefen ereignislisteLaden direkt als Event-Handler auf. Das
// Event-Objekt landete als `anhaengen` (immer wahr) -> die Liste wurde nie geleert, sondern
// bekam Treffer ab Versatz 200 angehängt; der Filter schien nicht zu wirken. Dazu kamen
// Tipp-Zwischenstände ("20" als Jahr) und sich überholende Antworten.
// Wunsch: bei den letzten (neuesten) Anlässen starten können.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_erzaehlen_filter.js erzaehlen.js
const fs = require('fs');
const path = require('path');

const pfad = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const src = fs.readFileSync(path.resolve(pfad), 'utf8');
const html = fs.readFileSync(path.join(path.dirname(path.resolve(pfad)), 'index.html'), 'utf8');

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
function pruefe(bed, txt, extra) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt + (extra ? ' — ' + extra : '')); fehler++; }
}

console.log('Abfrage-Parameter: reine Funktion');
let param;
try {
    param = new Function(funktionAusschneiden(src, 'erzaehlListenParameter') + '\nreturn erzaehlListenParameter;')();
} catch (e) {
    pruefe(false, 'erzaehlListenParameter vorhanden', e.message);
    param = () => '';
}
const p = (o) => new URLSearchParams(param(o));
const voll = p({ jahr: ' 2019 ', suche: ' Urlaub ', neuesteZuerst: true, offset: 200, limit: 200 });
pruefe(voll.get('jahr') === '2019', 'Jahr getrimmt', voll.toString());
pruefe(voll.get('suche') === 'Urlaub', 'Suche getrimmt');
pruefe(voll.get('neueste_zuerst') === 'true', 'neueste_zuerst gesetzt');
pruefe(voll.get('offset') === '200' && voll.get('limit') === '200', 'Blättern');
const halb = p({ jahr: '20', suche: '', neuesteZuerst: false, offset: 0, limit: 200 });
pruefe(!halb.has('jahr'), 'unfertiges Jahr ("20") filtert nicht', halb.toString());
pruefe(!halb.has('suche') && !halb.has('neueste_zuerst'), 'leere Suche und alte Reihenfolge fehlen');
pruefe(!p({ jahr: 'abcd', offset: 0, limit: 200 }).has('jahr'), 'Unsinn als Jahr filtert nicht');
pruefe(p({}).get('offset') === '0', 'ohne Angaben kein Wurf, Versatz 0');

console.log('Verdrahtung');
pruefe(!/addEventListener\(\s*'input'\s*,\s*ereignislisteLaden\s*\)/.test(src),
    'Felder übergeben das Event NICHT als „anhaengen"');
const laden = funktionAusschneiden(src, 'ereignislisteLaden');
pruefe(/erzaehlListenParameter\(/.test(laden), 'ereignislisteLaden nutzt erzaehlListenParameter');
pruefe(/listenAnfrage/.test(laden), 'veraltete Antworten werden verworfen (Anfragezähler)');
pruefe(/id="erzaehl-reihenfolge"/.test(html), 'index.html hat den Reihenfolge-Knopf');
pruefe(/gp_erzaehl_neueste_zuerst/.test(src), 'Reihenfolge wird gemerkt');

console.log('Cache');
const w = html.match(/erzaehlen\.js\?v=([0-9A-Z]+)/);
pruefe(w && w[1] >= '20261103B', 'erzaehlen.js mindestens 20261103B', w && w[1]);

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
