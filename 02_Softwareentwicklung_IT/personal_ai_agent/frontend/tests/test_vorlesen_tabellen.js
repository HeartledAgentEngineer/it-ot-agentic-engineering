// Vorlesen: Markdown-Tabellen als gesprochene Sätze (29.09.2026).
//
// Befund (Sebastian, Handy): Die Stimme las Tabellen Zelle für Zelle mit
// Strichen vor, ohne zu sagen, welche Spalte gemeint ist. Dieser Test
// schneidet die reinen Funktionen aus dem echten app.js aus.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_vorlesen_tabellen.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2] || path.join(__dirname, '..', 'app.js'), 'utf8');

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

const f = new Function(
    ['textFuerStimme', 'tabelleFuerStimme', 'tabellenImTextFuerStimme']
        .map((n) => funktionAusschneiden(src, n)).join('\n')
    + '; return { textFuerStimme, tabelleFuerStimme, tabellenImTextFuerStimme };')();

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

const tabelle = [
    '| Handy | Fotos | mit Ort |',
    '|---|---:|:---:|',
    '| **Xperia T** | 3200 | 80 % |',
    '| Motorola | 2947 |  |',
].join('\n');

console.log('Vorlesen: Tabellen');
const gesprochen = f.tabelleFuerStimme(tabelle);
pruefe(gesprochen.startsWith('Tabelle mit 2 Zeilen.'), 'nennt die Zeilenzahl: ' + gesprochen);
pruefe(gesprochen.includes('Xperia T, Fotos: 3200, mit Ort: 80 %.'), 'Zeile mit Spaltenüberschriften');
pruefe(gesprochen.includes('Motorola, Fotos: 2947.'), 'leere Zelle wird ausgelassen');
pruefe(!/[|*]/.test(gesprochen), 'keine Striche und Sternchen');
pruefe(!gesprochen.includes('---'), 'Trennzeile wird nicht gelesen');
pruefe(f.tabelleFuerStimme('| nur | Kopf |') === 'nur, Kopf.', 'nur Kopfzeile -> Aufzählung');

const text = 'Hier die Übersicht:\n' + tabelle + '\nDas war es.';
const ganz = f.tabellenImTextFuerStimme(text);
pruefe(ganz.includes('Hier die Übersicht:') && ganz.includes('Das war es.'), 'Text um die Tabelle bleibt');
pruefe(!ganz.includes('|'), 'ganzer Text ohne Striche');
pruefe(f.tabellenImTextFuerStimme('Kein Tisch hier.') === 'Kein Tisch hier.', 'Text ohne Tabelle unverändert');

pruefe(/const tabelle = rest\.match\(/.test(src) && /tabelleFuerStimme\(tabelle\[0\]\)/.test(src),
    'Mitlese-Vorleser nimmt Tabellen als ganzes Stück');
pruefe(/if \(bisEnde && !istFertig\(\)\) return null;/.test(src), 'wartet, solange die Tabelle noch einläuft');
pruefe(/const plainText = tabellenImTextFuerStimme\(text\)/.test(src), 'Browser-Rückfallstimme nutzt es auch');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
