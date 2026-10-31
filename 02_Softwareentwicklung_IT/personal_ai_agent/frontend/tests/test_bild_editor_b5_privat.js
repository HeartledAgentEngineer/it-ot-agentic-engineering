// test_bild_editor_b5_privat.js — Tests fuer Bild-Editor B5 und selektiven Privat-Schutz
// Node.js Testsuite

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const erzaehlenPath = path.resolve(__dirname, '../erzaehlen.js');
const erzaehlenSrc = fs.readFileSync(erzaehlenPath, 'utf8');

const appPath = path.resolve(__dirname, '../app.js');
const appSrc = fs.readFileSync(appPath, 'utf8');

const htmlPath = path.resolve(__dirname, '../index.html');
const htmlSrc = fs.readFileSync(htmlPath, 'utf8');

let fehler = 0;
function pruefe(bed, msg, detail) {
    if (bed) {
        console.log('  OK   ' + msg);
    } else {
        console.log('  FEHL ' + msg + (detail ? ' -> ' + detail : ''));
        fehler++;
    }
}

console.log('\n1) erzaehlBildIstPrivat — selektive Erkennung sensibler Inhalte');
{
    // Wir extrahieren die Funktion aus erzaehlen.js
    const fnMatch = erzaehlenSrc.match(/function erzaehlBildIstPrivat\([\s\S]*?\n\}/);
    pruefe(!!fnMatch, 'erzaehlBildIstPrivat existiert in erzaehlen.js');
    
    const erzaehlBildIstPrivat = new Function('fileid', 'bildInfo', 'detail', 'privSet', 'entsperrtSet', `
        ${fnMatch[0]}
        return erzaehlBildIstPrivat(fileid, bildInfo, detail, privSet, entsperrtSet);
    `);

    pruefe(erzaehlBildIstPrivat('123', null, null, new Set(['123'])) === true,
        'gespeicherte fileid in privSet ist privat');
    pruefe(erzaehlBildIstPrivat('999', null, null, new Set(['123'])) === false,
        'normale fileid ohne Flag ist NICHT privat');

    pruefe(erzaehlBildIstPrivat('456', null, { intim: true }, new Set()) === true,
        'Ereignis mit intim:true ist privat');
    pruefe(erzaehlBildIstPrivat('456', null, { kategorie: 'Intim' }, new Set()) === true,
        'Ereignis mit Kategorie "Intim" ist privat');
    pruefe(erzaehlBildIstPrivat('456', null, { titel: 'Sehr privater Anlass' }, new Set()) === false,
        'Normaler Ereignistitel mit Wort "privat" loest KEINEN Pauschal-Blur mehr aus');

    pruefe(erzaehlBildIstPrivat('789', { bilder: { '789': { beschreibung: 'Foto am Strand mit Badekleidung' } } }, null, new Set()) === false,
        'Strandfoto mit normaler Beschreibung ist NICHT privat');
    pruefe(erzaehlBildIstPrivat('789', { bilder: { '789': { beschreibung: 'intimer Bereich, Nacktfoto mit Genitalien' } } }, null, new Set()) === true,
        'Foto mit sensiblen Schlagwoertern in Beschreibung ist privat');
    pruefe(erzaehlBildIstPrivat('789', { bilder: { '789': { beschreibung: 'Badefoto mit nacktem Oberkörper am Pool' } } }, null, new Set()) === false,
        'Badefoto mit nacktem Oberkoerper ist NICHT privat');
    pruefe(erzaehlBildIstPrivat('789', { bilder: { '789': { beschreibung: 'Nacktfoto mit Genitalien' } } }, null, new Set(), new Set(['789'])) === false,
        'Manuell entsperrtes Bild ist NIEMALS privat');
}

console.log('\n2) Verdrahtung in index.html: Sperr-Overlay und Steuerleiste');
{
    pruefe(htmlSrc.includes('id="erzaehl-privat-sperre"'), 'erzaehl-privat-sperre existiert im DOM');
    pruefe(htmlSrc.includes('id="erzaehl-bild-editor-btn"'), 'erzaehl-bild-editor-btn existiert im DOM');
    pruefe(htmlSrc.includes('id="erzaehl-privat-toggle"'), 'erzaehl-privat-toggle existiert im DOM');
    pruefe(/✏️\s*Personen bearbeiten/.test(htmlSrc), 'Editor-Knopf ist sichtbar beschriftet');
}

console.log('\n3) Verdrahtung in erzaehlen.js: Editor-Aufruf mit {fileid}');
{
    pruefe(erzaehlenSrc.includes('zeigeBildVollbild'), 'erzaehlen.js bindet zeigeBildVollbild ein');
    pruefe(/zeigeBildVollbild\([^)]*fileid:/.test(erzaehlenSrc), 'zeigeBildVollbild wird mit fileid aufgerufen');
    pruefe(erzaehlenSrc.includes('erzaehl-bild-editor-btn'), 'erzaehl-bild-editor-btn Event-Listener verdrahtet');
    pruefe(erzaehlenSrc.includes('erzaehl-privat-sperre'), 'erzaehl-privat-sperre Aufdeck-Logik verdrahtet');
}

console.log('\n4) Galerie-Grossansicht in app.js: Editor-Knopf ✏️ Personen');
{
    pruefe(appSrc.includes('foto-gross-edit-btn') || appSrc.includes('✏️ Personen'),
        'Galerie-Grossansicht bietet ✏️ Personen bearbeiten');
    pruefe(/oeffneFotoGross[\s\S]*?zeigeBildVollbild/.test(appSrc),
        'Galerie ruft zeigeBildVollbild mit fileid auf');
}

console.log('\n' + (fehler ? 'FEHLER: ' + fehler : 'alle Pruefungen bestanden'));
process.exit(fehler ? 1 : 0);
