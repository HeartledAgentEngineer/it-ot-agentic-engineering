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
               'gruppenMeta', 'gruppenZwillingText'];
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
    === '12 von 986 Gruppen benannt · 3.400 von 31.781 Gesichtern · 2 unbekannt', 'Fortschrittszeile');
pruefe(f.gruppenFortschritt({ ok: false }) === '', 'ohne Stand leer');
pruefe(f.gruppenMeta({ groesse: 120, bilder: 90, videos: 1, von: '2015-01-01', bis: '2025-09-01' })
    === '120 Gesichter · 90 Fotos · 1 Video · 2015–2025', 'Kopfzeile');
pruefe(/zwei Menschen/.test(f.gruppenZwillingText({ name: 'Tim', gemeinsame_bilder: 4 })),
    'gemeinsame Fotos → Hinweis „wohl zwei Menschen"');
pruefe(f.gruppenZwillingText({ name: null, gemeinsame_bilder: 0 }) === 'Ähnlich: eine andere Gruppe',
    'ohne Namen, ohne gemeinsame Fotos');

console.log('Verdrahtung');
pruefe(/<button id="gruppen-btn" class="icon-btn"/.test(html), 'Knopf 👥 in der Kopfzeile');
['gruppen-sheet', 'gruppen-close', 'gruppen-kacheln', 'gruppen-name', 'gruppen-namen',
 'gruppen-speichern', 'gruppen-spaeter', 'gruppen-unbekannt', 'gruppen-zurueck',
 'gruppen-zurueck-fertig', 'gruppen-meldung', 'gruppen-fortschritt'].forEach((id) => {
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

console.log('Cache-Bump');
const v = html.match(/gruppen_quiz\.js\?v=(\d{8}[A-Z])/);
pruefe(v && v[1] >= '20261001A', 'gruppen_quiz.js mit Version');
const c = html.match(/style\.css\?v=(\d{8}[A-Z])/);
pruefe(c && c[1] >= '20261001A', 'style.css-Version 20261001A oder neuer');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
