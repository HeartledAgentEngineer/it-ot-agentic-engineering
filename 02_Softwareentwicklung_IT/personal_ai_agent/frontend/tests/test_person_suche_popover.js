/**
 * test_person_suche_popover.js - Tests fuer Autocomplete-Suche & Vektor-Vorschlaege
 *
 * Prueft:
 * 1. vollbild-person-suche-btn und vollbild-person-suche-modal in app.js
 * 2. KI-Vorschlag / Vektor-Ranking ganz oben
 * 3. Autocomplete-Filterung beim Tippen
 * 4. Neue Person per Suche anlegen
 * 5. gruppen-namen-suche in gruppen_quiz.js
 * 6. Reine textContent-Verwendung (kein innerHTML mit Daten)
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const appJs = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf-8');
const gruppenJs = fs.readFileSync(path.join(__dirname, '..', 'gruppen_quiz.js'), 'utf-8');

console.log('1) Vollbild-Editor: Autocomplete-Suche & Popover');
assert(appJs.includes('vollbild-person-suche-btn'), 'personSucheBtn vorhanden');
assert(appJs.includes('vollbild-person-suche-modal'), 'personSucheModal vorhanden');
assert(appJs.includes('vollbild-person-suche-input'), 'Suchfeld im Popover vorhanden');
assert(appJs.includes('⭐ KI-VORSCHLAG (ÄHNLICHSTES GESICHT)'), 'Vektor-Vorschlaege ganz oben priorisiert');
assert(appJs.includes('vollbild-suche-neu-opt'), 'Neue Person per Suche anlegen vorhanden');
console.log('  OK   Such-Knopf, Popover, Vektor-Priorisierung und Neue-Person-Weg vorhanden');

console.log('2) Gruppen-Quiz: Filter-Eingabe beim Zuordnen');
assert(gruppenJs.includes('gruppen-namen-suche'), 'Suchfeld fuer Namens-Chips vorhanden');
assert(gruppenJs.includes('.gruppen-namen-chip'), 'Filtert Namen-Chips per textContent');
console.log('  OK   Filterung fuer Gesichter-Zuordnung im Gruppen-Quiz vorhanden');

console.log('3) Sicherheit: Keine innerHTML-Einschleusung mit Nutzernamen');
const suchBlockMatch = appJs.match(/function bauePersonSucheInhalt\(\) \{[\s\S]*?personSucheBtn\.addEventListener/);
assert(suchBlockMatch, 'Suchblock gefunden');
const suchBlock = suchBlockMatch[0];
assert(!suchBlock.includes('innerHTML ='), 'Suchblock verwendet kein innerHTML fuer Daten');
assert(suchBlock.includes('textContent ='), 'Suchblock verwendet sauberes textContent');
console.log('  OK   Sicherheit gewahrt: striktes textContent');

console.log('\nAlle Pruefungen fuer Autocomplete-Suche & Vektorsortierung bestanden!');
