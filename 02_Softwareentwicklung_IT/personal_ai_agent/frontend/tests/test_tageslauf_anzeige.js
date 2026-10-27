// Tagesimport im Checks-Fenster (C3, 26.10.2026) — Anzeige und Bedienung.
//
// Plan: .hermes/plans/2026-10-25_tagesimport-handy.md, Abschnitt "C3 im Einzelnen".
// Das Backend liefert GET /api/tageslauf (Schalter, Kamera-Ordner, letzter Bericht,
// Gemini-Erinnerung) und nimmt POST /api/tageslauf/einstellungen entgegen.
//
// Dieser Test schneidet den REINEN Teil aus dem echten app.js (Namenstabelle und die
// Textfunktionen bis zur Marke "Tageslauf: Anzeige und Bedienung") und prüft: Klartext
// ohne Symbole, ehrliche Fälle (kein Bericht, veralteter Bericht, Gemini fällig),
// Robustheit (kein Wurf bei Unsinn), Rückmeldetexte nach dem Speichern, dazu die
// Verdrahtung im echten index.html/app.js/style.css (Block im Checks-Fenster, eindeutige
// IDs, Anzeige nur per textContent, kein Polling, Cache-Schlüssel).
// Kein Netz, kein DOM, keine Nutzerdaten.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_tageslauf_anzeige.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(pfadApp, 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');

const anfang = src.indexOf('const TAGESLAUF_BAUSTEIN_NAMEN');
if (anfang === -1) throw new Error('Namenstabelle nicht gefunden: TAGESLAUF_BAUSTEIN_NAMEN');
const ende = src.indexOf('// ── Tageslauf: Anzeige und Bedienung', anfang);
if (ende === -1) throw new Error('Marke "Tageslauf: Anzeige und Bedienung" nach dem reinen Teil nicht gefunden');
const reinerTeil = src.slice(anfang, ende);

const namen = ['tageslaufText', 'tageslaufSchalterText', 'tageslaufGespeichertText', 'tageslaufFehlerText'];
const f = new Function(reinerTeil + '\nreturn {' + namen.join(', ') + '};')();

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ok  ' + txt); } else { console.log('  FEHLER ' + txt); fehler++; }
}

// Keine Häkchen-/Statussymbole (Sebastians Regel: Klartext statt Symbole).
const verboteneSymbole = /[✓✔✅❌⚠\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

const lauf = {
    ok: true,
    heute: '2026-10-26',
    an: true,
    einstellungen_lesbar: true,
    kamera_ordner: { gesetzt: true, wert: '/Beispiel/Kamera' },
    gemini: { letzter_export: '2026-10-20', tage_seit_export: 6, faellig: false },
    heute_gelaufen: true,
    bericht_veraltet: false,
    bericht: {
        datum: '2026-10-26', zeit: '2026-10-26T07:30:00', exit: 0, stand_fortgeschrieben: true,
        bausteine: [
            { name: 'wa_bilder', status: 'ok', text: 'WhatsApp-Bilder: 12 hochgeladen' },
            { name: 'wa_chats', status: 'nicht_eingerichtet', text: 'WhatsApp-Chats: nicht eingerichtet (W2 Teil B)' },
            { name: 'kamera', status: 'ok', text: 'Kamera: 30 neue Dateien seit letztem Lauf' },
            { name: 'gemini', status: 'erinnerung', text: 'Gemini: Takeout-Export fällig (alte Meldung)' },
        ],
    },
};

function kopie(aenderung) { return Object.assign(JSON.parse(JSON.stringify(lauf)), aenderung); }

// ── Text bei laufendem Import ───────────────────────────────────────────────
console.log('tageslaufText: Normalfall');
const zeilen = f.tageslaufText(lauf).split('\n');
pruefe(zeilen[0] === 'Tagesimport: an', 'erste Zeile nennt den Schalter: ' + zeilen[0]);
pruefe(zeilen.includes('Kamera-Ordner: /Beispiel/Kamera'), 'Kamera-Ordner steht da');
pruefe(zeilen.includes('Heute: schon gelaufen'), 'Heute-Zeile bei gelaufenem Import');
pruefe(zeilen.some((z) => z.startsWith('Letzter Lauf: 2026-10-26')), 'Letzter Lauf mit Datum');
pruefe(zeilen.some((z) => z.startsWith('Letzter Lauf:') && z.includes('in Ordnung')), 'Exit 0 heißt "in Ordnung"');
pruefe(zeilen.includes('  WhatsApp-Bilder: 12 hochgeladen'), 'Baustein-Text eingerückt als Klartext');
pruefe(zeilen.includes('  Kamera: 30 neue Dateien seit letztem Lauf'), 'Kamera-Baustein steht da');
pruefe(zeilen.some((z) => z.includes('nicht eingerichtet (W2 Teil B)')), 'Platzhalter-Baustein steht da');
pruefe(!zeilen.some((z) => z.includes('alte Meldung')),
    'der Gemini-Baustein aus dem Bericht entfällt (aktuelle Zeile kommt vom Stand)');
pruefe(zeilen.includes('Gemini: letzter Export vor 6 Tagen'), 'Gemini-Zeile aus dem aktuellen Stand');
pruefe(!verboteneSymbole.test(f.tageslaufText(lauf)), 'kommt ohne Symbole aus');
pruefe(!/null|undefined|NaN/.test(f.tageslaufText(lauf)), 'kein "null"/"undefined"/"NaN" im Text');

console.log('tageslaufText: Sonderfälle');
const aus = f.tageslaufText(kopie({ an: false, heute_gelaufen: false, bericht: null,
    kamera_ordner: { gesetzt: false, wert: null }, gemini: { letzter_export: null, tage_seit_export: null, faellig: true } }));
pruefe(aus.split('\n')[0] === 'Tagesimport: aus', 'aus: erste Zeile "Tagesimport: aus"');
pruefe(aus.includes('Kamera-Ordner: nicht eingerichtet'), 'ohne Ordner: "nicht eingerichtet"');
pruefe(aus.includes('Letzter Lauf: noch keiner'), 'ohne Bericht: "noch keiner"');
pruefe(!aus.includes('Heute:'), 'aus: keine Heute-Zeile');
pruefe(aus.includes('Gemini: Takeout-Export fällig (alle 2 Monate)'), 'ohne Export: Erinnerung fällig');

const nochNicht = f.tageslaufText(kopie({ heute_gelaufen: false }));
pruefe(nochNicht.includes('Heute: noch nicht gelaufen'), 'an, aber noch nicht gelaufen');

const alt = f.tageslaufText(kopie({ bericht_veraltet: true, heute_gelaufen: false,
    bericht: Object.assign({}, lauf.bericht, { datum: '2026-10-24' }) }));
pruefe(alt.includes('Letzter Lauf: 2026-10-24 (nicht von heute)'), 'veralteter Bericht wird benannt');

const fehlerLauf = f.tageslaufText(kopie({ bericht: Object.assign({}, lauf.bericht, { exit: 1 }) }));
pruefe(fehlerLauf.includes('Exit 1'), 'Exit ungleich 0 wird genannt');

const unlesbar = f.tageslaufText(kopie({ an: false, einstellungen_lesbar: false }));
pruefe(unlesbar.split('\n')[0] === 'Tagesimport: aus (Einstellungen nicht lesbar)', 'unlesbare Einstellungen ehrlich benannt');

console.log('tageslaufText: Robustheit');
pruefe(f.tageslaufText(null) === 'Tagesimport nicht abrufbar.', 'null -> ehrlicher Satz');
pruefe(f.tageslaufText(undefined) === 'Tagesimport nicht abrufbar.', 'undefined -> ehrlicher Satz');
pruefe(f.tageslaufText({ ok: false }) === 'Tagesimport nicht abrufbar.', 'ok=false -> ehrlicher Satz');
pruefe(f.tageslaufText('text') === 'Tagesimport nicht abrufbar.', 'Text statt Objekt -> ehrlicher Satz');
let geworfen = false;
try {
    f.tageslaufText({ ok: true });
    f.tageslaufText({ ok: true, bericht: { bausteine: 'kaputt' }, gemini: 5, kamera_ordner: 7 });
    f.tageslaufText({ ok: true, bericht: { bausteine: [null, 5, { name: 3, text: null }, { text: 'Kamera: ok' }] } });
} catch (e) { geworfen = true; }
pruefe(!geworfen, 'Unsinn in den Feldern wirft nicht');
const leer = f.tageslaufText({ ok: true });
pruefe(leer.split('\n')[0] === 'Tagesimport: aus' && !/null|undefined|NaN/.test(leer), 'leere Antwort ergibt Standardzeilen ohne "null"');
const fremd = f.tageslaufText(kopie({ bericht: { datum: '2026-10-26', exit: 0, bausteine: [{ name: 'kamera', text: '<b>Kamera</b>' }] } }));
pruefe(fremd.includes('<b>Kamera</b>'), 'Fremdtext bleibt unverändert (wird nur per textContent gezeigt)');

// ── Schalter-Beschriftung ───────────────────────────────────────────────────
console.log('tageslaufSchalterText');
pruefe(f.tageslaufSchalterText(lauf) === 'Tagesimport ausschalten', 'an -> ausschalten');
pruefe(f.tageslaufSchalterText(kopie({ an: false })) === 'Tagesimport einschalten', 'aus -> einschalten');
pruefe(f.tageslaufSchalterText(null) === 'Tagesimport einschalten', 'ohne Antwort -> einschalten');
pruefe(f.tageslaufSchalterText({ ok: true, an: 'true' }) === 'Tagesimport einschalten', 'nur echtes true gilt als an');

// ── Rückmeldungen ───────────────────────────────────────────────────────────
console.log('Rückmeldungen nach dem Speichern');
pruefe(f.tageslaufGespeichertText('an', lauf) === 'Gespeichert: Tagesimport ist jetzt an.', 'an');
pruefe(f.tageslaufGespeichertText('an', kopie({ an: false })) === 'Gespeichert: Tagesimport ist jetzt aus.', 'aus');
pruefe(f.tageslaufGespeichertText('kamera_ordner', lauf) === 'Gespeichert: Kamera-Ordner /Beispiel/Kamera', 'Ordner');
pruefe(f.tageslaufGespeichertText('gemini_export_heute', lauf) === 'Gespeichert: Gemini-Export für heute eingetragen.', 'Gemini');
pruefe(f.tageslaufGespeichertText('sonst', lauf) === 'Gespeichert.', 'unbekannte Art -> "Gespeichert."');
pruefe(f.tageslaufGespeichertText('kamera_ordner', null) === 'Gespeichert.', 'ohne Antwort -> "Gespeichert."');
pruefe(f.tageslaufFehlerText(400, 'Kamera-Ordner nicht zulässig.') === 'Nicht gespeichert: Kamera-Ordner nicht zulässig.', 'Fehlertext vom Server');
pruefe(f.tageslaufFehlerText(409, '') === 'Nicht gespeichert (HTTP 409).', 'ohne Text: HTTP-Status');
pruefe(f.tageslaufFehlerText(500, [{ x: 1 }]) === 'Nicht gespeichert (HTTP 500).', 'Liste als Detail -> HTTP-Status');
pruefe(f.tageslaufFehlerText(undefined, undefined) === 'Nicht gespeichert: keine Antwort vom Server.', 'ohne alles: keine Antwort');
pruefe(!verboteneSymbole.test(namen.map((n) => f[n].toString()).join('')), 'der reine Teil enthält keine Symbole');

// ── Reiner Teil ─────────────────────────────────────────────────────────────
console.log('Reiner Teil');
pruefe(!reinerTeil.includes('innerHTML'), 'schreibt kein HTML');
pruefe(!reinerTeil.includes('document.'), 'greift nicht aufs DOM zu');
pruefe(!reinerTeil.includes('fetch('), 'ruft kein Netz');

// ── Verdrahtung ─────────────────────────────────────────────────────────────
console.log('Block im Checks-Fenster');
const iSheet = html.indexOf('id="selbsttest-sheet"');
const iBlock = html.indexOf('id="tageslauf-block"');
const iProtokoll = html.indexOf('id="server-protokoll"');
const iText = html.indexOf('id="selbsttest-text"');
pruefe(iBlock !== -1, 'index.html hat #tageslauf-block');
pruefe(iBlock > iProtokoll && iBlock < iText && iBlock > iSheet, '#tageslauf-block steht hinter #server-protokoll und vor #selbsttest-text');
pruefe(html.indexOf('id="tageslauf-block"', iBlock + 1) === -1, '#tageslauf-block kommt nur einmal vor');
const ids = ['tageslauf-stand', 'tageslauf-schalter', 'tageslauf-text', 'tageslauf-ordner',
    'tageslauf-ordner-speichern', 'tageslauf-gemini', 'tageslauf-status'];
ids.forEach((id) => {
    const i = html.indexOf('id="' + id + '"');
    pruefe(i > iBlock && i < iText, '#' + id + ' liegt im Block');
    pruefe(html.indexOf('id="' + id + '"', i + 1) === -1, '#' + id + ' kommt nur einmal vor');
});
const blockHtml = html.slice(iBlock, iText);
pruefe(/<button[^>]*id="tageslauf-schalter"[^>]*type="button"|<button[^>]*type="button"[^>]*id="tageslauf-schalter"/.test(blockHtml),
    'Schalter ist ein echter Knopf (type=button)');
pruefe(/<input[^>]*id="tageslauf-ordner"/.test(blockHtml) && /<label[^>]*for="tageslauf-ordner"/.test(blockHtml),
    'Eingabefeld für den Kamera-Ordner mit Beschriftung');
pruefe(/Gemini-Export heute erledigt/.test(blockHtml), 'Knopf "Gemini-Export heute erledigt"');
pruefe(/>\s*Speichern\s*</.test(blockHtml), 'Knopf "Speichern"');
pruefe(!/<block[^>]*hidden/.test(blockHtml.slice(0, 200)) && !/id="tageslauf-block"[^>]*hidden/.test(blockHtml.slice(0, 300)),
    'Block ist nicht zugeklappt (Schalter immer erreichbar)');

console.log('app.js');
pruefe(/fetch\(`\$\{API_BASE\}\/api\/tageslauf`/.test(src), 'app.js lädt GET /api/tageslauf');
pruefe(/\/api\/tageslauf\/einstellungen/.test(src), 'app.js schreibt über /api/tageslauf/einstellungen');
const nachMarke = src.slice(ende);
const blockJs = nachMarke.slice(0, nachMarke.indexOf('// ── Ende Tageslauf') === -1 ? 6000 : nachMarke.indexOf('// ── Ende Tageslauf'));
pruefe(/method:\s*'POST'/.test(blockJs) && /'Content-Type':\s*'application\/json'/.test(blockJs), 'POST mit JSON-Kopf');
pruefe(/credentials:\s*'same-origin'/.test(blockJs), 'Anmeldung per Sitzungs-Cookie wie bei den Nachbarn');
pruefe(!blockJs.includes('innerHTML'), 'Bedienteil schreibt kein HTML');
pruefe(/textContent/.test(blockJs), 'Anzeige per textContent');
pruefe(/function ladeSelbsttest\(\)|async function ladeSelbsttest\(\)/.test(src)
    && /async function ladeSelbsttest\(\) \{\s*ladeTageslauf\(\);/.test(src),
    'ladeSelbsttest (Öffnen und Aktualisieren) lädt auch den Tagesimport');
pruefe(!/setInterval\([^)]*Tageslauf/.test(src) && !/setInterval\([^)]*tageslauf/.test(src), 'KEIN Polling des Tagesimports');
pruefe(/_tageslaufEl\('tageslauf-schalter'\)/.test(blockJs) && /_tageslaufEl\('tageslauf-ordner-speichern'\)/.test(blockJs)
    && /_tageslaufEl\('tageslauf-gemini'\)/.test(blockJs)
    && (blockJs.match(/addEventListener\('click'/g) || []).length >= 3, 'alle drei Knöpfe sind verdrahtet (Klick)');
pruefe(/an:\s*!/.test(blockJs) || /\{ an:/.test(blockJs), 'Schalter sendet ein echtes Bool');
pruefe(/gemini_export_heute:\s*true/.test(blockJs), 'Gemini-Knopf sendet gemini_export_heute: true');
pruefe(/kamera_ordner:/.test(blockJs), 'Speichern sendet kamera_ordner');

console.log('Darstellung und Cache');
pruefe(css.includes('.tageslauf-block') && css.includes('#tageslauf-text'), 'style.css gestaltet den Block');
pruefe(/#selbsttest-sheet \.tageslauf-block/.test(css), 'Block bekommt den Checks-Fenster-Rahmen');
pruefe(/\.tageslauf-block button[^{]*\{[^}]*min-height:\s*(4\d|5\d)px/.test(css), 'große Tippflächen (mindestens 40 px)');
const vApp = (html.match(/app\.js\?v=(\d{8}[A-Z])/) || [])[1];
const vCss = (html.match(/style\.css\?v=(\d{8}[A-Z])/) || [])[1];
pruefe(vApp >= '20261026A', 'app.js-Cache mindestens 20261026A (gefunden: ' + vApp + ')');
pruefe(vCss >= '20261026A', 'style.css-Cache mindestens 20261026A (gefunden: ' + vCss + ')');
pruefe(!/<script[^>]+src="https?:/.test(html), 'kein CDN im Frontend');

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
