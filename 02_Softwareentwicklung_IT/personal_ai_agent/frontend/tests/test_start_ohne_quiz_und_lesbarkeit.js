// Start ohne Quiz + Lesbarkeit von Antworten (29.09.2026)
//
// Befund (Sebastian, Handy): (1) Beim Öffnen der App „ging das Quiz wieder
// los". Ursache: stelleVerlaufWiederHer() baut die letzte Chat-Nachricht mit
// [QUIZ-OFFEN] als LAUFENDE Quiz-Karte nach und setzt _quizAktiv = true —
// eine einmal nicht beantwortete Frage startete so bei jedem Öffnen neu.
// (2) Recherche-Antworten liefen rechts über die Blase hinaus: Quellen-Links
// sind Flex-Kinder mit white-space:nowrap ohne min-width:0 -> die Ellipse
// greift nie, lange Titel sprengen die Blase. (3) Links in Antworten hatten
// die Browser-Standardfarbe (dunkelblau) auf dunklem Grund.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_start_ohne_quiz_und_lesbarkeit.js
const fs = require('fs');
const path = require('path');

const js = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}
function regel(selektor) {
    const i = css.indexOf(selektor + ' {');
    if (i === -1) return '';
    return css.slice(i, css.indexOf('}', i));
}

console.log('Start ohne Quiz');
pruefe(js.indexOf('_baueOffeneQuizKarte(contentDiv, m);') === -1,
    'Verlauf-Wiederherstellung baut KEINE laufende Quiz-Karte mehr');
pruefe(/function _quizFortsetzenKnopf\(/.test(js),
    'offene Frage bekommt stattdessen einen Knopf "Quiz fortsetzen"');
pruefe(/_quizFortsetzenKnopf\(contentDiv\)/.test(js),
    'der Knopf wird beim Wiederherstellen angehängt');

console.log('Lesbarkeit');
const quelle = regel('.sources a');
pruefe(/min-width:\s*0/.test(quelle) && /display:\s*block/.test(quelle),
    'Quellen-Links schrumpfen (min-width:0, block) -> Ellipse greift, Blase bleibt heil');
const link = regel('.message-content a');
pruefe(/color:/.test(link), 'Links in Antworten haben eine eigene, helle Farbe');
pruefe(/overflow-wrap:\s*anywhere/.test(link), 'lange Link-Texte brechen um');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
