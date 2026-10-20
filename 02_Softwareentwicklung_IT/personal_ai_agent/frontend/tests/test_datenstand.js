// Datenstand der Fotoquellen (18.10.2026, gesamtplan T0) — Anzeige in der Oberfläche.
//
// Auftrag: „Fotoquellen wirklich bis zum Handy nachweisen." Ergebnis für
// Sebastian ist eine Statuszeile je Quelle: entpackt → Bildindex →
// Gesichtserkennung → Gruppenbestand → auf diesem Handy. Der Bericht kommt von
// /api/datenstand/fotoquellen (Server auf DIESEM Gerät).
//
// Dieser Test schneidet den REINEN Teil aus dem echten app.js (Namenstabelle
// und die drei Funktionen) und prüft: Zahlen im Klartext, „nicht gemessen"
// statt 0, Quellennamen, ehrliche Kopfzeile, Robustheit (kein Wurf bei Unsinn),
// keine Symbole (Sebastians Regel) und die Verdrahtung im echten
// index.html/app.js/style.css. Kein Netz, kein DOM, keine Nutzerdaten.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_datenstand.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const pfadHtml = path.join(__dirname, '..', 'index.html');
const pfadCss = path.join(__dirname, '..', 'style.css');
const src = fs.readFileSync(pfadApp, 'utf8');
const html = fs.readFileSync(pfadHtml, 'utf8');
const css = fs.readFileSync(pfadCss, 'utf8');

// Der reine Teil: von der Namenstabelle bis vor die Verdrahtung (IIFE).
const anfang = src.indexOf('const DATENSTAND_QUELLEN_NAMEN');
if (anfang === -1) throw new Error('Namenstabelle nicht gefunden: DATENSTAND_QUELLEN_NAMEN');
const ende = src.indexOf('(function () {', anfang);
if (ende === -1) throw new Error('Verdrahtung (IIFE) nach dem reinen Teil nicht gefunden');
const reinerTeil = src.slice(anfang, ende);

const namen = ['datenstandZahl', 'datenstandStand', 'datenstandZeilen'];
const f = new Function(reinerTeil + '\nreturn {' + namen.join(', ') + '};')();
const zahl = f.datenstandZahl;
const stand = f.datenstandStand;
const zeilen = f.datenstandZeilen;

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ok  ' + txt); } else { console.log('  FEHLER ' + txt); fehler++; }
}

// Keine Häkchen-/Statussymbole (Sebastians Regel: Klartext statt Symbole).
const verboteneSymbole = /[\u2713\u2714\u2705\u274C\u26A0\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

const antwortOk = {
    ok: true,
    gelesen_am: '2026-10-18T22:45:39+02:00',
    quellen: [
        { quelle_typ: 'fotos', gelesen_am: '2026-10-18T22:45:39+02:00',
          bilder_im_plan: 7616, bilder_im_index: 7616, bilder_mit_gesichtslauf: 7530,
          erkannte_gesichter: 20060, gesichter_im_gruppenbestand: 6522,
          offene_gruppen: 1349, spaeter_gruppen: 0, handy_stand_geprueft: true },
        { quelle_typ: 'papas_album', gelesen_am: '2026-10-18T22:45:39+02:00',
          bilder_im_plan: null, bilder_im_index: null, bilder_mit_gesichtslauf: null,
          erkannte_gesichter: null, gesichter_im_gruppenbestand: null,
          offene_gruppen: null, spaeter_gruppen: null, handy_stand_geprueft: true },
    ],
    gruppenbestand: { gruppen: 1367, benannt: 18, offen: 1349, spaeter: 0, gesichter: 30830 },
    handy_stand_geprueft: true,
    fehlende_werte: ['papas_album.bilder_im_plan', 'papas_album.erkannte_gesichter'],
    hinweis: 'Summen je Quelle.',
    aus_cache: true,
    dauer_sekunden: 12.34,
};

// ── Zahlen ──────────────────────────────────────────────────────────────────
pruefe(zahl(7616) === '7.616', 'Zahl mit Tausenderpunkt (deutsch): ' + zahl(7616));
pruefe(zahl(0) === '0', 'die Null ist eine Zahl und kein fehlender Wert');
pruefe(zahl(null) === 'nicht gemessen', 'null heißt „nicht gemessen"');
pruefe(zahl(undefined) === 'nicht gemessen', 'undefined heißt „nicht gemessen"');
pruefe(zahl('7616') === 'nicht gemessen', 'Text ist kein Messwert');
pruefe(zahl(NaN) === 'nicht gemessen', 'NaN ist kein Messwert');

// ── Kopfzeile ───────────────────────────────────────────────────────────────
const kopf = stand(antwortOk);
pruefe(kopf.includes('Stand 2026-10-18 22:45'), 'Kopfzeile nennt Tag und Uhrzeit');
pruefe(kopf.includes('Messung 12,3 s'), 'Kopfzeile nennt die Messdauer in Sekunden (Komma)');
pruefe(kopf.includes('aus dem Speicher'), 'Kopfzeile sagt, woher der Wert kommt (Speicher)');
pruefe(stand({ ...antwortOk, aus_cache: false }).includes('gerade frisch gemessen'),
    'frisch gemessene Werte werden als solche benannt');
pruefe(stand(null) === 'Datenstand nicht abrufbar.', 'ohne Antwort steht der ehrliche Grund da');
pruefe(stand({ ok: false }) === 'Datenstand nicht abrufbar.', 'ok=false wird ehrlich gemeldet');
pruefe(!verboteneSymbole.test(kopf), 'Kopfzeile kommt ohne Symbole aus');

// ── Zeilen ──────────────────────────────────────────────────────────────────
const z = zeilen(antwortOk);
pruefe(z[0] === 'Fotos', 'bekannter Quellentyp bekommt den lesbaren Namen: ' + z[0]);
pruefe(z[1].includes('im Plan 7.616'), 'Zahlenzeile nennt Plan, Index und Gesichtslauf');
pruefe(z[1].includes('mit Gesichtslauf 7.530'), 'Zahlenzeile nennt den Gesichtslauf');
pruefe(z[2].includes('erkannte Gesichter 20.060'), 'Zahlenzeile nennt die Gesichter');
pruefe(z[3].includes('auf diesem Gerät geprüft: ja'), 'die fünfte Station steht im Klartext da');
pruefe(z[4] === 'Papas Album', 'auch die zweite Quelle bekommt ihren Namen: ' + z[4]);
pruefe(z[5].includes('im Plan nicht gemessen'),
    'ein fehlender Wert steht als „nicht gemessen" da (nie als 0)');
pruefe(z[5].indexOf('im Plan 0') === -1, 'nirgends eine erfundene Null');
pruefe(z[z.length - 1].startsWith('Nicht gemessen: 2 Werte'), 'die fehlenden Werte werden gezählt');
pruefe(zeweiligeKurz(z), 'mehr als sechs fehlende Werte werden gekürzt');
pruefe(!verboteneSymbole.test(z.join('\n')), 'die Zeilen kommen ohne Symbole aus');

function zeweiligeKurz(liste) {
    const viele = { ...antwortOk, fehlende_werte: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] };
    const text = zeilen(viele).slice(-1)[0];
    return text.includes('8 Werte') && text.endsWith('…') && !text.includes('g, h');
}
pruefe(zeilen({ ...antwortOk, quellen: [] })[0] === 'Keine Quelle gemeldet.',
    'ohne Quelle steht ein klarer Satz da');
pruefe(zeilen({ ...antwortOk, quellen: [{ quelle_typ: 'unbekannt_xy' }] })[0] === 'unbekannt_xy',
    'unbekannter Quellentyp wird unverändert gezeigt');
pruefe(zeilen({ ...antwortOk, quellen: [null, 42] }).length === 10,
    'Unsinn in der Liste wirft nicht und ergibt trotzdem Zeilen');
pruefe(zeilen(null)[0] === 'Datenstand nicht abrufbar.', 'ohne Antwort bleibt es bei Klartext');
pruefe(zeilen({ ok: true }).length === 1, 'Antwort ohne Quellenliste ergibt genau einen Satz');
const ohneGruppen = zeilen({ ...antwortOk, gruppenbestand: null });
pruefe(!ohneGruppen.some((t) => t.startsWith('Gruppenbestand')), 'ohne Gruppenstand keine Gruppenzeile');
const ohneFehlend = zeilen({ ...antwortOk, fehlende_werte: 'kaputt' });
pruefe(!ohneFehlend.some((t) => t.startsWith('Nicht gemessen')), 'kaputte Fehlwertliste wird nicht gezeigt');

// ── Verdrahtung ─────────────────────────────────────────────────────────────
pruefe(html.includes('id="datenstand-btn"'), 'index.html hat den Knopf „Datenstand"');
pruefe(html.includes('id="datenstand-liste"'), 'index.html hat die Liste');
pruefe(html.includes('id="datenstand-neu"'), 'index.html hat den Knopf „Neu messen"');
pruefe(src.includes("/api/datenstand/fotoquellen"), 'app.js ruft die Route des Datenstands');
pruefe(src.includes("frisch ? '?neu=true' : ''"), '„Neu messen" misst ausdrücklich frisch');
pruefe(src.includes('replaceChildren()'), 'die Liste wird ersetzt, nicht angehängt');
pruefe(!reinerTeil.includes('innerHTML'), 'der reine Teil schreibt kein HTML');
pruefe(!reinerTeil.includes('document.'), 'der reine Teil greift nicht aufs DOM zu');
pruefe(src.includes('textContent'), 'geschrieben wird mit textContent');
pruefe(css.includes('.datenstand') && css.includes('#datenstand-liste'),
    'style.css gestaltet den Bereich');
pruefe(css.includes('max-height: 40vh'), 'die Liste rollt selbst (Chat behält den Platz)');
pruefe(/app\.js\?v=\d/.test(html) && /style\.css\?v=\d/.test(html),
    'beide Dateien tragen einen Cache-Schlüssel');

// Der Bereich steht flach im Fluss — kein Kasten über dem Chat (Befund Punkt 9).
const blockHtml = html.slice(html.indexOf('id="datenstand"'));
pruefe(blockHtml.slice(0, 400).includes('hidden'), 'der Bereich ist zugeklappt (hidden)');
pruefe(!/position:\s*(fixed|absolute)/.test(css.slice(css.indexOf('.datenstand {'))),
    'der Bereich liegt im Fluss und nicht über dem Chat');

console.log('\n' + (fehler === 0 ? 'Alle Prüfungen bestanden.' : fehler + ' Prüfung(en) fehlgeschlagen.'));
process.exit(fehler === 0 ? 0 : 1);
