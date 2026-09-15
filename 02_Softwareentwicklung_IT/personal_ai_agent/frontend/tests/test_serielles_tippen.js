// Testet: Zwischenmeldungen und Antwort erscheinen SERIELL (kein paralleles
// Tippen) und das Tipp-Tempo folgt dem Zahnrad-Regler im Chat.
//
// Gemeldeter Fall (Sebastian 2026-09-15): „zwei tippende Blasen" — die
// Gedanken-Blasen tippten zwar in einer Kette, aber die Antwort blendete
// gleichzeitig daneben ein. Außerdem sollte das Tempo über den Regler
// (state.streamMs) auch für die Zwischenmeldungen gelten.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_serielles_tippen.js app.js
const fs = require('fs');

const pfad = process.argv[2] || 'app.js';
const src = fs.readFileSync(pfad, 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
    if (bedingung) {
        console.log('  ✔ ' + name);
    } else {
        console.log('  ✘ ' + name + (detail ? ' — ' + detail : ''));
        fehler++;
    }
}

console.log(`\nSerielles Tippen (${pfad}):\n`);

// 1) Die Antwort-Einblendung wartet, solange eine Gedanken-Blase tippt.
const start = src.indexOf('const _zeigeEingeblendet = () => {');
pruefe('_zeigeEingeblendet gefunden', start !== -1);
if (start !== -1) {
    const abschnitt = src.slice(start, start + 900);
    pruefe('Antwort wartet auf tippenden Block (kein Parallel-Tippen)',
        /_gedankenTippWartend\s*>\s*0\)\s*return;/.test(abschnitt),
        'Wächter `if (_gedankenTippWartend > 0) return;` fehlt');
    pruefe('Antwort blendet weiterhin blockweise ein (8 Zeichen)',
        /slice\(0,\s*8\)/.test(abschnitt));
}

// 2) Tipp-Tempo der Zwischenmeldungen kommt aus dem Zahnrad.
pruefe('Tipp-Tempo nutzt state.streamMs (Zahnrad)',
    /_tempoFaktor\s*=\s*Math\.max\(/.test(src) && /state\.streamMs/.test(src));

// 3) Die Gedanken-Blasen bleiben eine Kette (seriell, mit Rückstand-Erkennung).
pruefe('Gedanken tippen in einer Kette (_gedankenTippWartend++)',
    /_gedankenTippWartend\+\+/.test(src));

console.log(fehler ? `\n${fehler} Prüfung(en) fehlgeschlagen\n` : '\nAlle Prüfungen grün\n');
process.exit(fehler ? 1 : 0);