// Zählzeile unter der Anlassgeschichte + Stopp beim automatischen Vorlesen (03.11.2026).
//
// Befund (Sebastian, Handy): Die KI-Anlassgeschichte war nur ein Satz; Bildbeschreibungen und
// Notizen fehlten scheinbar. Welche Quelle fehlt, darf nicht an Claude gehen (private Daten) —
// deshalb zeigt die App selbst nur ZAHLEN: Quelle (KI/Vorlage), Bilder, Beschreibungen, Notizen,
// Personen. Außerdem las die App nach dem Erzeugen automatisch vor, ohne Knopf -> kein "Stopp".
//
// Aufruf (aus dem Ordner frontend):  node tests/test_erzaehlen_datenzeile.js
const fs = require('fs');
const path = require('path');

const pfad = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const src = fs.readFileSync(pfad, 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

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

console.log('Zählzeile: reine Funktion');
const zeile = new Function(funktionAusschneiden(src, 'erzaehlDatenZeile') + '\nreturn erzaehlDatenZeile;')();
const voll = zeile({ erzaehlquelle: 'ki', anzahl_dateien: 14, beschreibungen: ['a', 'b'], anzahl_notizen: 3,
                     personen: ['X', 'Y'] });
pruefe(voll === 'KI · 14 Bilder · 2 Beschreibungen · 3 Notizen · 2 Personen', 'volle Zeile', voll);
const vorlage = zeile({ erzaehlquelle: 'vorlage', anzahl_dateien: 1, beschreibungen: [], anzahl_notizen: 0, personen: [] });
pruefe(vorlage === 'Vorlage (ohne KI) · 1 Bild · 0 Beschreibungen · 0 Notizen · 0 Personen', 'Vorlage + Einzahl', vorlage);
pruefe(zeile(null) === '' && zeile(undefined) === '', 'ohne Daten leer, kein Wurf');
const ohneZahl = zeile({ erzaehlquelle: 'ki' });
pruefe(ohneZahl.indexOf('undefined') === -1 && ohneZahl.indexOf('NaN') === -1, 'fehlende Felder ohne undefined/NaN', ohneZahl);
pruefe(!/X|Y/.test(voll), 'zeigt nur Zahlen, keine Namen');

console.log('Zählzeile: Verdrahtung');
pruefe(/id="erzaehl-anlassgeschichte-daten"/.test(html), 'index.html hat den Platz für die Zählzeile');
const erstellen = funktionAusschneiden(src, 'anlassGeschichteErstellen');
pruefe(/erzaehlDatenZeile\(/.test(erstellen), 'anlassGeschichteErstellen füllt die Zählzeile');
const erzeugen = funktionAusschneiden(src, 'geschichteErzeugen');
pruefe(/daten:\s*res\.daten/.test(erzeugen), 'geschichteErzeugen gibt die Daten der Antwort weiter');

console.log('Automatisches Vorlesen nach dem Erzeugen hat einen Stopp-Knopf');
pruefe(/vorlesenText\(ergebnis\.geschichte,\s*el\('erzaehl-anlassgeschichte-vorlesen'\)\)/.test(erstellen),
    'Anlassgeschichte: Vorlesen mit dem 🔊-Knopf der Geschichte');
pruefe(/vorlesenText\(ergebnis\.geschichte,\s*el\('erzaehl-bildgeschichte-vorlesen'\)\)/.test(src),
    'Bildgeschichte: Vorlesen mit dem 🔊-Knopf der Geschichte');

console.log('Cache');
const w = html.match(/erzaehlen\.js\?v=([0-9A-Z]+)/);
pruefe(w && w[1] >= '20261103A', 'erzaehlen.js mindestens 20261103A', w && w[1]);

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
