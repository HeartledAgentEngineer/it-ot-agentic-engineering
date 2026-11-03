// „✓ Profil speichern" nimmt einen geänderten Namen mit (F5, 03.11.2026).
//
// Befund: Name im Kontaktbuch geändert, „Profil speichern" gedrückt — der Name blieb alt.
// Der Name hatte einen eigenen Knopf „✎ Ändern"; profilSpeichern las das Namensfeld nie.
// Jetzt: geänderter Name -> erst umbenennen, dann die übrigen Profilfelder mit den VORHER
// gelesenen Werten speichern (umbenennen() zeichnet die Felder neu).
//
// Aufruf (aus dem Ordner frontend):  node tests/test_gruppen_profil_name.js gruppen_quiz.js
const fs = require('fs');
const path = require('path');

const pfad = path.resolve(process.argv[2] || path.join(__dirname, '..', 'gruppen_quiz.js'));
const src = fs.readFileSync(pfad, 'utf8');
const html = fs.readFileSync(path.join(path.dirname(pfad), 'index.html'), 'utf8');

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
function pruefe(bed, txt) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt); fehler++; }
}

const speichern = funktionAusschneiden(src, 'profilSpeichern');
pruefe(/el\('gruppen-person-name'\)/.test(speichern), 'profilSpeichern liest das Namensfeld');
pruefe(/await umbenennen\(/.test(speichern), 'geänderter Name wird über umbenennen() gespeichert');
const posLesen = speichern.indexOf("el('gruppen-person-beziehung').value");
const posUmb = speichern.indexOf('await umbenennen(');
pruefe(posLesen !== -1 && posUmb !== -1 && posLesen < posUmb,
    'Profilfelder werden VOR dem Umbenennen gelesen (sonst gehen Eingaben verloren)');
pruefe(/name-geaendert|nameGeaendert/.test(speichern), 'Erfolg ohne weitere Felder meldet nicht „Nichts geändert"');
const w = html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/);
pruefe(w && w[1] >= '20261103A', 'gruppen_quiz.js mindestens 20261103A');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
