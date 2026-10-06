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
               'gruppenGeburtstagText', 'gruppenTrefferInfo', 'gruppenAlleInfo', 'gruppenAusschlussKnopf', 'gruppenDiktatOffen',
               'gruppenSuchformen', 'gruppenPersonPasst', 'gruppenPersonInfo', 'gruppenVorschlagKopf',
               'gruppenKontaktText', 'gruppenRueckgaengigText', 'gruppenNotizZeit',
               'gesichtKennung', 'gesichtRahmen'];
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

console.log('gesichtKennung');
pruefe(f.gesichtKennung({ fileid: 123 }) === 123, 'Gesichterliste: fileid');
pruefe(f.gesichtKennung({ bild_id: '456' }) === '456',
    'Personenvorschlag: bild_id (sonst leere Kacheln bei benannten Personen)');
pruefe(f.gesichtKennung({ fileid: 123, bild_id: '456' }) === 123, 'fileid hat Vorrang');
pruefe(f.gesichtKennung({ fileid: '', bild_id: '456' }) === '456', 'leeres fileid → bild_id');
pruefe(f.gesichtKennung(null) === null && f.gesichtKennung({}) === null,
    'ohne Kennung → null');

console.log('gesichtRahmen');
{
    const r = f.gesichtRahmen({ bbox: [400, 300, 200, 150], breite: 1600, hoehe: 1200 });
    pruefe(Array.isArray(r.bbox_norm) && r.bbox_norm.length === 4, 'vier Werte');
    pruefe(Math.abs(r.bbox_norm[0] - 0.25) < 1e-9 && Math.abs(r.bbox_norm[1] - 0.25) < 1e-9
        && Math.abs(r.bbox_norm[2] - 0.125) < 1e-9 && Math.abs(r.bbox_norm[3] - 0.125) < 1e-9,
        'auf 0..1 normiert (x, y, Breite, Höhe)');
    pruefe(r.bbox[2] === 200 && r.bbox[3] === 150, 'Pixel-bbox bleibt erhalten');
    pruefe(f.gesichtRahmen({ bbox: [1, 2, 3, 4] }) === null
        && f.gesichtRahmen({ bbox: [1, 2, 3, 4], breite: 0, hoehe: 100 }) === null,
        'ohne Bildmaße → null (kein Rahmen auf dem falschen Fleck)');
    pruefe(f.gesichtRahmen({ bbox: [1, 2, 0, 40], breite: 100, hoehe: 100 }) === null
        && f.gesichtRahmen({ bbox: null, breite: 100, hoehe: 100 }) === null,
        'unbrauchbare bbox → null');
    const rand = f.gesichtRahmen({ bbox: [0, 0, 1600, 1200], breite: 1600, hoehe: 1200 });
    pruefe(rand.bbox_norm[2] === 1 && rand.bbox_norm[3] === 1, 'ganzes Bild → 1 x 1');
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
pruefe(f.gruppenAusschlussKnopf(0) === 'Gesichter antippen zum Ausschließen'
    && f.gruppenAusschlussKnopf(1) === '🚫 1 Gesicht ausschließen'
    && f.gruppenAusschlussKnopf(3) === '🚫 3 Gesichter ausschließen', 'Ausschluss-Knopf');
pruefe(f.gruppenAlleInfo({ ok: true, gesamt: 412, ausgeschlossen: 2 }, 48)
    === 'Tippe die Gesichter an, die NICHT zu dieser Person gehören. · 412 Gesichter · 48 geladen · 2 schon ausgeschlossen',
    'Infozeile der Gesamtansicht');
pruefe(f.gruppenGeburtstagText('1997-03-14') === '14.03.1997' && f.gruppenGeburtstagText('--08-02') === '02.08.'
    && f.gruppenGeburtstagText(null) === '' && f.gruppenGeburtstagText('Quatsch') === '', 'Geburtstag lesbar');
pruefe(f.gruppenTrefferInfo({ name: 'Leon', beziehung: 'Bruder', kontakt: true }, 'person')
    === 'schon benannt · Bruder · 📇 verknüpft', 'Treffer-Info Person');
pruefe(f.gruppenTrefferInfo({ name: 'Lea', geburtstag: '--08-02', nummern: 2, verknuepft_mit: 'Lea S.' }, 'kontakt')
    === '📇 Kontakt · 🎂 02.08. · 2 Nummern · schon bei Lea S.', 'Treffer-Info Kontakt (ohne Nummern im Klartext)');
pruefe(/nameSpeichern\(p\.name\)/.test(src) && /nameSpeichern\(k\.verknuepft_mit \|\| k\.name, k\.id\)/.test(src)
    && /addEventListener\('click', \(\) => nameSpeichern\(\)\)/.test(src),
    'Treffer speichert direkt; Speichern-Knopf übergibt kein Klick-Ereignis als Namen');
pruefe(/t\.textContent = titel;/.test(src) && /i\.textContent = info;/.test(src)
    && !/innerHTML = [^';]*\b(titel|info|name)\b/.test(src), 'Namen nur als Text, nie als HTML');

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
['gruppen-sheet', 'gruppen-close', 'gruppen-kacheln', 'gruppen-name', 'gruppen-treffer', 'gruppen-alle', 'gruppen-alle-ansicht', 'gruppen-alle-zurueck',
 'gruppen-alle-raster', 'gruppen-alle-mehr', 'gruppen-alle-ausschliessen', 'gruppen-alle-info',
 'gruppen-beziehung', 'gruppen-notiz', 'gruppen-profil-info',
 'gruppen-speichern', 'gruppen-spaeter', 'gruppen-unbekannt', 'gruppen-zurueck',
 'gruppen-zurueck-fertig', 'gruppen-meldung', 'gruppen-fortschritt',
 'gruppen-nummer', 'gruppen-verbunden', 'gruppen-notiz-mikro'].forEach((id) => {
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
pruefe(v && v[1] >= '20261002B', 'gruppen_quiz.js mit Version 20261002B oder neuer');
pruefe(/\/api\/gruppen\/gesichter\?kennung=/.test(src) && /\/api\/gruppen\/ausschliessen/.test(src)
    && /new IntersectionObserver/.test(src), 'Gesamtansicht lädt seitenweise und Vorschaubilder erst beim Sichtbarwerden');
const c = html.match(/style\.css\?v=(\d{8}[A-Z])/);
pruefe(c && c[1] >= '20261002B', 'style.css-Version 20261002B oder neuer');
pruefe(!/gruppen-schnellnamen|<datalist/.test(html), 'Namensknöpfe und datalist sind durch das Suchfeld ersetzt');
pruefe(/\/api\/gruppen\/suche\?limit=8&q=/.test(src) && /kontakt_id = String\(kontaktId\)/.test(src),
    'Suchfeld fragt die Suche und schickt beim Kontakt die Kennung mit');
pruefe(/if \(nr === _suchNr\) trefferZeigen/.test(src), 'nur die neueste Suchantwort wird gezeigt');

console.log('Benannt: Personen wieder aufrufen und bearbeiten (02.10.2026)');
pruefe(f.gruppenPersonPasst('Leon Müller', 'mue') && f.gruppenPersonPasst('Leon Müller', 'mul')
    && f.gruppenPersonPasst('Leon Müller', 'le mü'), 'Filter: Wortanfang, Umlaute egal, mehrere Wörter');
pruefe(!f.gruppenPersonPasst('Leon Müller', 'eon') && f.gruppenPersonPasst('Tim', '') && f.gruppenPersonPasst('Tim', '  '),
    'Filter: Wortmitte passt nicht, leer passt immer');
pruefe(f.gruppenPersonInfo({ gesichter: 1234, vorschlaege: 2, beziehung: 'Bruder', erinnerungen: 1, kontakt: true })
    === '1.234 Gesichter · 2 Vorschläge · Bruder · 1 Erinnerung · 📇', 'Listenzeile einer Person');
pruefe(f.gruppenPersonInfo({ gesichter: 5, vorschlaege: 1 }) === '5 Gesichter', 'Listenzeile ohne Profil');
pruefe(f.gruppenVorschlagKopf({ kennung: 'Person_1001', groesse: 120, von: '2015-01-01', bis: '2025-09-01' })
    === 'Vorschlag 1001 · 120 Gesichter · 2015–2025', 'Kopf eines Vorschlags');
pruefe(f.gruppenKontaktText({ id: '13', name: 'Tim B.', nummern: ['+49170', '040'], geburtstag: '--08-02' })
    === '📇 Tim B. · 🎂 02.08. · 2 Nummern', 'Kontaktzeile ohne Nummern im Klartext');
pruefe(/Kein Kontakt verknüpft/.test(f.gruppenKontaktText(null)), 'ohne Kontakt ein Hinweis');
pruefe(f.gruppenRueckgaengigText({ art: 'umbenennen' }) === '↩ Umbenennen zurückgenommen'
    && f.gruppenRueckgaengigText({ art: 'name' }) === '↩ letzte Antwort zurückgenommen'
    && f.gruppenRueckgaengigText(null) === '↩ letzte Antwort zurückgenommen', 'Rückmeldung nach Rückgängig je Art');
pruefe(f.gruppenNotizZeit('2026-10-02T11:45:00') === '02.10.2026' && f.gruppenNotizZeit('') === '', 'Datum einer Erinnerung');
['gruppen-reiter-offen', 'gruppen-reiter-benannt', 'gruppen-benannt-ansicht', 'gruppen-benannt-filter',
 'gruppen-benannt-info', 'gruppen-benannt-liste', 'gruppen-person', 'gruppen-person-titel', 'gruppen-person-zurueck',
 'gruppen-person-meta', 'gruppen-person-vorschlaege', 'gruppen-person-name', 'gruppen-person-umbenennen',
 'gruppen-person-beziehung', 'gruppen-person-notiz', 'gruppen-person-mikro', 'gruppen-person-speichern',
 'gruppen-person-notizen', 'gruppen-person-kontakt', 'gruppen-person-kontaktsuche',
 'gruppen-person-kontakttreffer', 'gruppen-person-rueckgaengig'].forEach((id) => {
    pruefe(html.indexOf('id="' + id + '"') !== -1 && src.indexOf("'" + id + "'") !== -1,
        '#' + id + ' im HTML und im Skript');
});
pruefe(/\/api\/gruppen\/personen'/.test(src) && /\/api\/gruppen\/person\?name=/.test(src)
    && /\/api\/gruppen\/umbenennen'/.test(src) && /\/api\/gruppen\/loesen'/.test(src), 'Benannt nutzt die vier neuen Routen');
pruefe(/kontakt_id: String\(kontaktId\)/.test(src) && /'\/api\/gruppen\/profil', koerper/.test(src),
    'Profil speichern und Kontakt verknüpfen über /api/gruppen/profil');
pruefe(/if \(zustand\.reiter !== 'offen'\) return;/.test(src), 'eine späte Antwort aus „Offen“ überschreibt „Benannt“ nicht');
pruefe(/Wirklich lösen\? Noch einmal tippen/.test(src), 'Vorschlag lösen braucht zwei Tipps');
pruefe(/n\.textContent = p\.name;/.test(src) && /text\.textContent = n\.text \|\| '';/.test(src)
    && !/innerHTML = [^']/.test(src), 'Namen und Erinnerungen nur per textContent');
pruefe(/alleOeffnen\(v\.kennung, true\)/.test(src) && /alle\.vonPerson && zustand\.person/.test(src),
    'Alle Gesichter auch aus der Personenansicht, Zurück führt dorthin');
pruefe(/\.gruppen-reiter-knopf\.aktiv \{/.test(css) && /\.gruppen-person\[hidden\] \{ display: none; \}/.test(css),
    'Stil für Reiter und Personenansicht');
const v3 = html.match(/gruppen_quiz\.js\?v=(\d{8}[A-Z])/);
const c3 = html.match(/style\.css\?v=(\d{8}[A-Z])/);
pruefe(v3 && v3[1] >= '20261002C' && c3 && c3[1] >= '20261002C', 'Cache-Bump 20261002C (Skript und Stil)');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
