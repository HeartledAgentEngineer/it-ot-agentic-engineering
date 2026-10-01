// Personen benennen im Gruppenmodus — Oberfläche (01.10.2026).
//
// Prüft die reinen Funktionen aus gruppen_quiz.js (Gesichtsausschnitt,
// Zeitraum, Fortschritt, Zwillings-Hinweis) und die Verdrahtung in index.html.
// Backend-Tests: backend/tests/test_gruppen_quiz.py.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_gruppen_quiz.js gruppen_quiz.js
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

const namen = ['gruppenAusschnitt', 'gruppenZeitraum', 'gruppenZahl', 'gruppenFortschritt',
               'gruppenMeta', 'gruppenZwillingText', 'gruppenProfilText',
               'gruppenNummer', 'gruppenVerbundenText', 'gruppenAntwortText',
               'gruppenSchnellNamen', 'gruppenDiktatOffen'];
const f = new Function(namen.map((n) => funktionAusschneiden(src, n)).join('\n')
    + '; return { ' + namen.join(', ') + ' };')();

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

console.log('gruppenAusschnitt');
{
    // Original 1000x750, Vorschau 480x360 (Faktor 0,48); Gesicht 100x100 bei (450, 300)
    const a = f.gruppenAusschnitt([450, 300, 100, 100], 1000, 750, 480, 360, 0.35);
    const mitteX = a.x + a.w / 2, mitteY = a.y + a.h / 2;
    pruefe(Math.abs(mitteX - 240) < 1e-9 && Math.abs(mitteY - 168) < 1e-9, 'Gesicht in der Mitte des Ausschnitts');
    pruefe(Math.abs(a.w - 48 * 1.7) < 1e-9 && a.w === a.h, 'quadratisch, Gesicht + 35 % Rand je Seite');
    const rand = f.gruppenAusschnitt([0, 0, 100, 100], 1000, 750, 480, 360, 0.35);
    pruefe(rand.x === 0 && rand.y === 0, 'am Bildrand eingeklemmt, nie außerhalb');
    const riesig = f.gruppenAusschnitt([0, 0, 1000, 750], 1000, 750, 480, 360, 0.35);
    pruefe(riesig.w <= 360 && riesig.y === 0, 'nie größer als das Vorschaubild');
    pruefe(f.gruppenAusschnitt([450, 300, 100, 100], 1000, 750, 360, 480) === null,
        'Vorschau anders gedreht (Hoch statt Quer) → null statt falscher Ausschnitt');
    pruefe(f.gruppenAusschnitt(null, 1000, 750, 480, 360) === null
        && f.gruppenAusschnitt([1, 2, 3, 4], 0, 750, 480, 360) === null, 'Unsinn → null');
}

console.log('Texte');
pruefe(f.gruppenZeitraum('2016-01-01', '2025-08-01') === '2016–2025', 'Zeitraum über Jahre');
pruefe(f.gruppenZeitraum('2022-06-18', '2022-06-18') === '2022', 'ein Jahr');
pruefe(f.gruppenZeitraum(null, null) === '', 'ohne Daten leer');
pruefe(f.gruppenZahl(31781) === '31.781', 'Tausenderpunkt');
pruefe(f.gruppenFortschritt({ ok: true, benannt: 12, gruppen: 986, gesichter: 31781,
    gesichter_benannt: 3400, unbekannt: 2 })
    === '12 von 986 Vorschlägen benannt · 3.400 von 31.781 Gesichtern · 2 unbekannt', 'Fortschrittszeile (Vorschläge, nicht „Gruppen“)');
pruefe(f.gruppenFortschritt({ ok: false }) === '', 'ohne Stand leer');
pruefe(f.gruppenMeta({ groesse: 120, bilder: 90, videos: 1, von: '2015-01-01', bis: '2025-09-01' })
    === '120 Gesichter · 90 Fotos · 1 Video · 2015–2025', 'Kopfzeile');
pruefe(/zwei Menschen/.test(f.gruppenZwillingText({ name: 'Tim', gemeinsame_bilder: 4 })),
    'gemeinsame Fotos → Hinweis „wohl zwei Menschen"');
pruefe(f.gruppenZwillingText({ name: null, gemeinsame_bilder: 0 }) === 'Ähnlich: ein noch unbenannter Vorschlag – dieselbe Person?',
    'ohne Namen, ohne gemeinsame Fotos: Frage nach derselben Person');
pruefe(!/dieselbe Person\?/.test(f.gruppenZwillingText({ name: 'Tim', gemeinsame_bilder: 2 })),
    'gemeinsame Fotos: keine Frage nach derselben Person');
pruefe(f.gruppenProfilText({ ok: true, beziehung: 'Bruder', notizen: [{}, {}] }) === 'Bekannt: Bruder · 2 Erinnerungen', 'Profilzeile');
pruefe(f.gruppenProfilText({ ok: true, beziehung: '', notizen: [] }) === '' && f.gruppenProfilText(null) === '', 'leeres Profil ohne Zeile');

console.log('Wechsel sichtbar, „= dieselbe Person" ohne Namen (01.10.2026)');
pruefe(f.gruppenNummer('Person_1003') === 'Vorschlag 1003' && f.gruppenNummer('') === '', 'Vorschlagsnummer aus der Kennung');
pruefe(f.gruppenVerbundenText([]) === '' && f.gruppenVerbundenText(null) === '', 'ohne Verbundene keine Zeile');
pruefe(/1 weiteren Vorschlag — der Name gilt für alle/.test(f.gruppenVerbundenText([{}])), 'ein Verbundener');
pruefe(/2 weiteren Vorschlägen/.test(f.gruppenVerbundenText([{}, {}])), 'zwei Verbundene');
pruefe(/verbunden — der Name, den du jetzt vergibst, gilt für beide/.test(f.gruppenAntwortText('gleich', { name: null }, false)),
    'gleich ohne Namen: erklärt, was passiert ist (vorher: „nichts passiert")');
pruefe(f.gruppenAntwortText('gleich', { name: 'Tim', weitere: 1 }, true)
    === '✓ als dieselbe Person gemerkt (Tim) · auch für 1 verbundenen Vorschlag → nächster Vorschlag', 'gleich mit Namen + Wechsel');
pruefe(f.gruppenAntwortText('name', { name: 'Leon', notiz: true, weitere: 2 }, true)
    === '✓ Leon gespeichert · Erinnerung angelegt · auch für 2 verbundene Vorschläge → nächster Vorschlag', 'Name mit Verbundenen');
pruefe(f.gruppenAntwortText('verschieden', {}, false) === '✓ als zwei Menschen gemerkt', 'ohne Wechsel kein Pfeil');
pruefe(/gruppen-wechsel/.test(src) && /@keyframes gruppen-einblenden/.test(css)
    && /prefers-reduced-motion: reduce\) \{\s*\.gruppen-karte\.gruppen-wechsel/.test(css), 'Wechsel-Animation, abschaltbar über „Bewegung reduzieren"');
pruefe(/⏭ Weiter \(später\)/.test(html), 'Knopf heißt „Weiter (später)"');

console.log('Schon vergebene Namen per Antippen (01.10.2026)');
pruefe(JSON.stringify(f.gruppenSchnellNamen(['Leon', 'leon ', '', null, 'Oma'], 40)) === '["Leon","Oma"]',
    'ohne Leere und Doppelte (Groß/Klein egal)');
pruefe(f.gruppenSchnellNamen(['a', 'b', 'c'], 2).length === 2, 'höchstens max Knöpfe');
pruefe(f.gruppenSchnellNamen(undefined).length === 0, 'ohne Namen keine Knöpfe');
pruefe(/nameSpeichern\(n\)/.test(src) && /addEventListener\('click', \(\) => nameSpeichern\(\)\)/.test(src),
    'Knopf speichert direkt; Speichern-Knopf übergibt kein Klick-Ereignis als Namen');
pruefe(/b\.textContent = n;/.test(src) && !/innerHTML = [^';]*\bn\b/.test(src), 'Namen nur als Text, nie als HTML');

console.log('Erinnerung einsprechen (01.10.2026)');
pruefe(f.gruppenDiktatOffen(true, null, '', 0) === true, 'während der Aufnahme offen');
pruefe(f.gruppenDiktatOffen(false, { wert: 'alt', bis: 1000 }, 'alt', 500) === true, 'nach dem Stopp offen, bis Text ankommt');
pruefe(f.gruppenDiktatOffen(false, { wert: 'alt', bis: 1000 }, 'alt neu', 500) === false, 'Text angekommen → frei');
pruefe(f.gruppenDiktatOffen(false, { wert: 'alt', bis: 1000 }, 'alt', 1500) === false, 'Erkennung gescheitert → nach der Frist frei');
pruefe(f.gruppenDiktatOffen(false, null, '', 0) === false, 'ohne Diktat frei');
pruefe(/typeof starteFeldDiktat !== 'function'/.test(src) && /await starteFeldDiktat\(feld, knopf\)/.test(src),
    'nutzt die vorhandene Erkennung aus app.js (kein eigener Audio-/Netzweg), mit Rückfall-Hinweis');
const antwortenRumpf = src.slice(src.indexOf('async function antworten('), src.indexOf('async function rueckgaengig('));
pruefe(/if \(diktatOffen\(\)\)/.test(antwortenRumpf), 'jede Antwort wartet auf ein offenes Diktat (Text landet nie bei der nächsten Person)');
pruefe(/<button id="gruppen-notiz-mikro" class="gruppen-mikro" type="button"/.test(html) && /\.gruppen-mikro \{/.test(css), 'Sprechknopf am Erinnerungsfeld mit Stil');
const appJs = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
pruefe(/^async function starteFeldDiktat\(zielElem, btn\)/m.test(appJs) && /'⬤ Aufnahme läuft…'/.test(appJs),
    'app.js: starteFeldDiktat global und beschriftet die Aufnahme mit ⬤ (darauf verlässt sich nimmtAuf)');

console.log('Verdrahtung');
pruefe(/<button id="gruppen-btn" class="icon-btn"/.test(html), 'Knopf 👥 in der Kopfzeile');
['gruppen-sheet', 'gruppen-close', 'gruppen-kacheln', 'gruppen-name', 'gruppen-namen',
 'gruppen-beziehung', 'gruppen-notiz', 'gruppen-profil-info',
 'gruppen-speichern', 'gruppen-spaeter', 'gruppen-unbekannt', 'gruppen-zurueck',
 'gruppen-zurueck-fertig', 'gruppen-meldung', 'gruppen-fortschritt',
 'gruppen-nummer', 'gruppen-verbunden', 'gruppen-schnellnamen', 'gruppen-notiz-mikro'].forEach((id) => {
    pruefe(html.indexOf('id="' + id + '"') !== -1 && src.indexOf("'" + id + "'") !== -1,
        '#' + id + ' im HTML und im Skript');
});
pruefe(!/onclick=/.test(html.slice(html.indexOf('id="gruppen-sheet"'), html.indexOf('id="erzaehlen-sheet"'))),
    'keine Inline-Handler im Blatt');
pruefe(html.indexOf('src="app.js?v=') < html.indexOf('src="gruppen_quiz.js?v='),
    'gruppen_quiz.js nach app.js (fetch mit API-Key, Vollbild)');
pruefe(/\/api\/gruppen\/naechste/.test(src) && /\/api\/gruppen\/antwort/.test(src)
    && /\/api\/gruppen\/rueckgaengig/.test(src) && /\/api\/gruppen\/stand/.test(src), 'alle vier Routen genutzt');
pruefe(/revokeObjectURL/.test(src) && /groesse=\$\{groesse\}/.test(src), 'Vorschaubilder nur flüchtig (Objekt-URL wird freigegeben)');
pruefe(!/https?:\/\/(?!localhost)/.test(src), 'keine fremde Adresse');
pruefe(/#gruppen-sheet\[hidden\] \{ display: none; \}/.test(css) && /\.gruppen-kacheln \{/.test(css), 'Stil vorhanden');

pruefe(/beziehung: beziehung\.trim\(\), notiz: notiz\.trim\(\)/.test(src), 'Benennen schickt Beziehung und Erinnerung mit');
pruefe(/\/api\/gruppen\/profil\?name=/.test(src), 'bekannter Name zeigt sein Profil');
pruefe(/= dieselbe Person/.test(src) && /≠ andere Person/.test(src), 'Knöpfe sprechen von Personen');

console.log('Cache-Bump');
const v = html.match(/gruppen_quiz\.js\?v=(\d{8}[A-Z])/);
pruefe(v && v[1] >= '20261001E', 'gruppen_quiz.js mit Version 20261001E oder neuer');
const c = html.match(/style\.css\?v=(\d{8}[A-Z])/);
pruefe(c && c[1] >= '20261001E', 'style.css-Version 20261001E oder neuer');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
