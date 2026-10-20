// Namensfelder in der Oberfläche — Vorname / Nachname / Spitznamen (20.10.2026, Schritt 3).
//
// Prüft die reinen Funktionen aus gruppen_quiz.js (Spitznamen-Liste, Änderungs-
// körper, Herkunfts-Hinweis, Suche über die Felder) und die Verdrahtung in
// index.html (drei Eingabefelder, Hinweiszeile, Versionsstand) sowie style.css.
// Backend-Gegenstück: backend/tests/test_namensfelder_schreiben.py.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_gruppen_namensfelder.js gruppen_quiz.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2] && process.argv[2].endsWith('gruppen_quiz.js')
    ? process.argv[2] : path.join(__dirname, '..', 'gruppen_quiz.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');

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

const namen = ['gruppenSuchformen', 'gruppenPersonPasst', 'gruppenSpitznamenListe',
               'gruppenSpitznamenZuviele', 'gruppenNamensfelderKoerper',
               'gruppenNamensfelderHinweis', 'gruppenPersonPasstNamensfelder'];
const f = new Function(namen.map((n) => funktionAusschneiden(src, n)).join('\n')
    + '; return { ' + namen.join(', ') + ' };')();

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

console.log('gruppenSpitznamenListe');
{
    pruefe(JSON.stringify(f.gruppenSpitznamenListe(' Mausi , Anni ,, Mausi '))
        === JSON.stringify(['Mausi', 'Anni']), 'getrennt, getrimmt, doppelte weg');
    pruefe(JSON.stringify(f.gruppenSpitznamenListe('ANNI, anni')) === JSON.stringify(['ANNI']),
        'gross/klein gilt als derselbe Spitzname');
    pruefe(JSON.stringify(f.gruppenSpitznamenListe('Anna Maria')) === JSON.stringify(['Anna Maria']),
        'ohne Komma bleibt der ganze Text ein Spitzname');
    pruefe(JSON.stringify(f.gruppenSpitznamenListe('')) === '[]', 'leer ergibt keine Spitznamen');
    pruefe(JSON.stringify(f.gruppenSpitznamenListe(null)) === '[]', 'null ergibt keine Spitznamen');
}

console.log('gruppenSpitznamenZuviele');
{
    pruefe(f.gruppenSpitznamenZuviele(Array(10).fill('x')) === false, '10 sind erlaubt');
    pruefe(f.gruppenSpitznamenZuviele(Array(11).fill('x')) === true, '11 sind zu viel');
    pruefe(f.gruppenSpitznamenZuviele(null) === false, 'keine Liste ist nicht zu viel');
}

console.log('gruppenNamensfelderKoerper');
{
    const profil = { vorname: 'Anni', nachname: 'Beispiel', spitznamen: ['Mausi'] };
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(profil, 'Anni', 'Beispiel', 'Mausi')) === '{}',
        'unverändert heisst: nichts mitschicken');
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(profil, 'Anne', 'Beispiel', 'Mausi')) === '{"vorname":"Anne"}',
        'nur das geänderte Feld kommt mit');
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(profil, '', 'Beispiel', 'Mausi')) === '{"vorname":""}',
        'leeren schickt einen leeren Wert (Ableitung greift wieder)');
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(profil, 'Anni', 'Beispiel', 'Mausi, Anna'))
        === '{"spitznamen":["Mausi","Anna"]}', 'Spitznamen als Liste');
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(profil, 'Anni', 'Beispiel', ''))
        === '{"spitznamen":[]}', 'Spitznamen leeren');
    // Abgeleitetes Feld unverändert: der Name bleibt die Kennung, nichts wird behauptet.
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper({ vorname: 'Anna', nachname: 'Beispiel' },
        'Anna', 'Beispiel', '')) === '{}', 'abgeleitete Felder bleiben unberührt');
    pruefe(JSON.stringify(f.gruppenNamensfelderKoerper(null, '', '', '')) === '{}',
        'fehlendes Profil ohne Eingabe: nichts mitzuschicken');
}

console.log('gruppenNamensfelderHinweis');
{
    pruefe(f.gruppenNamensfelderHinweis({ namensfelder_quelle: 'profil' }).indexOf('Von Hand') === 0,
        'Hinweis für von Hand gesetzte Felder');
    pruefe(f.gruppenNamensfelderHinweis({ namensfelder_quelle: 'abgeleitet' }).includes('abgeleitet'),
        'Hinweis für abgeleitete Felder');
    pruefe(f.gruppenNamensfelderHinweis({}) === '' && f.gruppenNamensfelderHinweis(null) === '',
        'ohne Quelle kein Hinweis');
}

console.log('gruppenPersonPasstNamensfelder');
{
    const p = { name: 'Anna Beispiel', vorname: 'Anni', nachname: 'Beispiel',
                spitznamen: ['Mausi', 'Anna'] };
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Anna') === true, 'Name passt');
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Mausi') === true, 'Spitzname passt');
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Anni') === true, 'Vorname passt');
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Beispiel') === true, 'Nachname passt');
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Maus') === true, 'Wortanfang genügt');
    pruefe(f.gruppenPersonPasstNamensfelder(p, 'Zoe') === false, 'kein Treffer bleibt kein Treffer');
    pruefe(f.gruppenPersonPasstNamensfelder(p, '') === true, 'leere Suche passt immer');
    pruefe(f.gruppenPersonPasstNamensfelder(null, 'Anna') === false, 'ohne Person kein Treffer');
    pruefe(f.gruppenPersonPasstNamensfelder({ name: 'Tim' }, 'Mausi') === false,
        'Person ohne Felder wird nicht erfunden');
}

console.log('Verdrahtung index.html / style.css / gruppen_quiz.js');
{
    ['gruppen-person-vorname', 'gruppen-person-nachname', 'gruppen-person-spitznamen',
     'gruppen-person-namensfelder-hinweis'].forEach((id) => {
        pruefe(html.indexOf('id="' + id + '"') !== -1, 'Feld im HTML: ' + id);
    });
    // Mindestens der Stand dieser Änderung (spätere Änderungen zählen weiter hoch).
    const version = (html.match(/gruppen_quiz\.js\?v=(\d{8}[A-Z])/) || [])[1] || '';
    pruefe(version >= '20261020C',
        'Versionsstand hochgezählt (Browser holt die neue Datei)');
    pruefe(css.indexOf('.gruppen-namensfelder') !== -1, 'Stil für die Felderzeile vorhanden');
    pruefe(src.indexOf('gruppenNamensfelderKoerper(profil,') !== -1,
        'Speichern schickt die Felder über den Änderungs-Körper');
    pruefe(src.indexOf('namensfelderZeigen(profil)') !== -1,
        'Profil zeigt die Felder beim Öffnen');
    pruefe(src.indexOf('gruppenPersonPasstNamensfelder(p, frage)') !== -1,
        'die Personensuche geht über die Felder');
    pruefe(src.indexOf('gruppe-profil"') === -1, 'kein Tippfehler in der Route');
}

console.log(fehler ? '\n' + fehler + ' Prüfung(en) rot' : '\nAlle Prüfungen grün');
process.exit(fehler ? 1 : 0);
