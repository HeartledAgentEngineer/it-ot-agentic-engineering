// Erzählen: Hand-Gesichter dürfen keine Gruppenaktion auslösen (Bild-Editor B1, 26.10.2026).
//
// Hintergrund: GET /api/gruppen/bild-gesichter liefert ab B1 auch Hand-Gesichter
// (quelle "hand", kennung null, gid mit Index >= 1000). Der Ausschluss-/Benennen-Weg
// der Gruppen kennt solche Gesichter nicht (Vorschlagskennung fehlt). Die Knöpfe in
// der Erzählen-Bearbeitung (Name / fremd / „ist nicht X") senden darum bei einem
// Hand-Gesicht NICHTS an /api/gruppen/antwort oder /api/gruppen/ausschliessen,
// sondern zeigen einen ehrlichen Hinweis (bis der Bild-Editor in B4 da ist).
//
// Die Funktionen werden wörtlich aus dem ECHTEN erzaehlen.js geschnitten und mit
// Attrappen ausgeführt — es wird nichts nachgebaut.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_erzaehlen_hand_gesichter.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const src = fs.readFileSync(pfadJs, 'utf8');
let html = '';
try { html = fs.readFileSync(path.join(path.dirname(path.resolve(pfadJs)), 'index.html'), 'utf8'); } catch (_) {}

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Funktion (auch ``async function``) exakt aus dem Quelltext schneiden. */
function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('nicht gefunden: ' + name);
  const start = src.slice(Math.max(0, i - 6), i) === 'async ' ? i - 6 : i;
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(start, k);
}

console.log('\n1) erzaehlGesichtHandHinweis — nur Hand-Gesichter bekommen den Hinweis');
const hinweisFn = new Function(extractFn('erzaehlGesichtHandHinweis') + '; return erzaehlGesichtHandHinweis;')();
const hand = hinweisFn({ quelle: 'hand', gid: '111:1000', kennung: null, name: null });
pruefe('unbenanntes Hand-Gesicht -> Hinweis', typeof hand === 'string' && hand.length > 10);
pruefe('Hinweis nennt Hand-Gesicht und Bild-Editor', /Hand-Gesicht/.test(hand) && /Bild-Editor/.test(hand), hand);
pruefe('benanntes Hand-Gesicht -> derselbe Hinweis',
    hinweisFn({ quelle: 'hand', gid: '111:1001', kennung: null, name: 'Nur Handy' }) === hand);
pruefe('erkanntes Gesicht -> kein Hinweis', hinweisFn({ quelle: 'erkennung', gid: '111:0', kennung: 'Person_2001' }) === '');
pruefe('altes Gesicht ohne quelle (ältere Antwort) -> kein Hinweis', hinweisFn({ gid: '111:0', kennung: 'Person_2001' }) === '');
pruefe('null/undefined/Zahl werfen nicht', hinweisFn(null) === '' && hinweisFn(undefined) === '' && hinweisFn(5) === '');

console.log('\n2) gesichtSpeichern — keine Gruppenaktion bei Hand-Gesichtern');
function lauf(gesicht, art, vorschlag) {
  const aufrufe = [];
  const meldungen = [];
  let aenderungen = 0;
  const zustand = { gesichtAuswahl: gesicht, gesichtBeschaeftigt: false };
  const stubs = {
    zustand,
    el: () => ({ value: 'Neuer Name', focus() {} }),
    jsonHolen: (pfad, opt) => { aufrufe.push({ pfad, opt }); return Promise.resolve({ ok: true }); },
    gesichtMelden: (text, rueckgaengig) => { meldungen.push({ text, rueckgaengig }); },
    erzaehlGesichtMeldung: () => 'ok',
    erzaehlGesichtHandHinweis: hinweisFn,
    gesichtBearbeitenSchliessen: () => {},
    nachGesichtAenderung: () => { aenderungen++; },
  };
  const namen = Object.keys(stubs);
  const fn = new Function(...namen, extractFn('gesichtSpeichern') + '; return gesichtSpeichern;')(
    ...namen.map((n) => stubs[n]));
  return fn(art, vorschlag).then(() => ({ aufrufe, meldungen, aenderungen, zustand }));
}

(async () => {
  const faelle = [
    ['unbenanntes Hand-Gesicht: Name', { quelle: 'hand', gid: '111:1000', kennung: null, name: null }, 'name', null],
    ['unbenanntes Hand-Gesicht: Vorschlag antippen', { quelle: 'hand', gid: '111:1000', kennung: null, name: null }, 'name', { name: 'Person A' }],
    ['unbenanntes Hand-Gesicht: fremde Person', { quelle: 'hand', gid: '111:1000', kennung: null, name: null }, 'unbekannt', undefined],
    ['benanntes Hand-Gesicht: „ist nicht X"', { quelle: 'hand', gid: '111:1001', kennung: null, name: 'Nur Handy' }, 'nicht', undefined],
    ['benanntes Hand-Gesicht: anderer Name', { quelle: 'hand', gid: '111:1001', kennung: null, name: 'Nur Handy' }, 'name', null],
  ];
  for (const [titel, g, art, vorschlag] of faelle) {
    const r = await lauf(g, art, vorschlag);
    pruefe(titel + ' -> keine Anfrage an den Server', r.aufrufe.length === 0, JSON.stringify(r.aufrufe));
    pruefe(titel + ' -> ehrlicher Hinweis, kein Rückgängig-Knopf',
        r.meldungen.length === 1 && /Bild-Editor/.test(r.meldungen[0].text) && r.meldungen[0].rueckgaengig === false,
        JSON.stringify(r.meldungen));
    pruefe(titel + ' -> nichts neu geladen, Auswahl bleibt', r.aenderungen === 0 && r.zustand.gesichtAuswahl === g);
  }

  console.log('\n3) erkannte Gesichter laufen unverändert über die Gruppen-Wege');
  const erkannt = { quelle: 'erkennung', gid: '111:0', kennung: 'Person_2001', name: null };
  let r = await lauf(erkannt, 'name', null);
  pruefe('Name -> /api/gruppen/antwort mit Kennung',
      r.aufrufe.length === 1 && r.aufrufe[0].pfad === '/api/gruppen/antwort'
      && JSON.parse(r.aufrufe[0].opt.body).kennung === 'Person_2001');
  r = await lauf({ gid: '111:0', kennung: 'Person_2001', name: 'Person A' }, 'nicht', undefined);
  pruefe('Gesicht ohne quelle (alte Antwort) -> /api/gruppen/ausschliessen',
      r.aufrufe.length === 1 && r.aufrufe[0].pfad === '/api/gruppen/ausschliessen'
      && JSON.parse(r.aufrufe[0].opt.body).gesichter[0] === '111:0');
  r = await lauf(erkannt, 'unbekannt', undefined);
  pruefe('fremd -> /api/gruppen/antwort art unbekannt',
      r.aufrufe.length === 1 && JSON.parse(r.aufrufe[0].opt.body).art === 'unbekannt');

  console.log('\n4) Verdrahtung');
  const rumpf = extractFn('gesichtSpeichern');
  pruefe('die Weiche steht vor jedem jsonHolen-Aufruf', rumpf.indexOf('erzaehlGesichtHandHinweis') !== -1
      && rumpf.indexOf('erzaehlGesichtHandHinweis') < rumpf.indexOf('jsonHolen('));
  pruefe('index.html lädt erzaehlen.js mit ?v=20261031A', /erzaehlen\.js\?v=20261031A/.test(html));

  console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
  process.exit(fehler ? 1 : 0);
})();
