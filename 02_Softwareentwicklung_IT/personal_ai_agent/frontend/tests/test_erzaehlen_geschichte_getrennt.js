// Erzählen: Bildgeschichte/Anlassgeschichte getrennt von den Notizen (G1, 02.11.2026).
//
// Plan: .hermes/plans/2026-11-02_geschichte-sprachmodell.md, Schritt G1, Prüfkriterien
// (d) Geschichte landet nicht im Notizfeld/der Notizliste und zählt nicht,
// (e) Neu-Erzeugen ersetzt die Anzeige, die alte Zeile bleibt,
// (i) „Das ist keine Notiz, sondern eine Geschichte" hängt genau eine Zeile an,
// (o) nach dem Speichern ist eine neue Notiz bzw. Bildgeschichte ohne Neuladen am richtigen Ort.
//
// Die Funktionen werden wörtlich aus dem ECHTEN erzaehlen.js geschnitten und mit Attrappen
// (kleine Schein-Oberfläche, Schein-Backend) ausgeführt — es wird nichts nachgebaut.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_erzaehlen_geschichte_getrennt.js erzaehlen.js
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

/** Funktion (auch ``async function``) exakt aus dem Quelltext schneiden (Klammern zählen). */
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

// ---------------------------------------------------------------------------
console.log('\n1) istNotiz — EINE Stelle, liest das Backend-Feld');
const reine = new Function(
  ['istNotiz', 'erzaehlGeschichteKoerper', 'erzaehlGeschichtenJeBild', 'erzaehlGeschichteArtFuer', 'erzaehlNeuesteGeschichte']
    .map((n) => extractFn(n)).join('\n')
  + '; return { istNotiz, erzaehlGeschichteKoerper, erzaehlGeschichtenJeBild, erzaehlGeschichteArtFuer, erzaehlNeuesteGeschichte };')();
const { istNotiz, erzaehlGeschichteKoerper, erzaehlGeschichtenJeBild, erzaehlGeschichteArtFuer, erzaehlNeuesteGeschichte } = reine;

pruefe('ist_notiz true -> Notiz', istNotiz({ ist_notiz: true }) === true);
pruefe('ist_notiz false -> keine Notiz', istNotiz({ ist_notiz: false }) === false);
pruefe('ist_notiz false schlägt fehlendes art (Altbestand)', istNotiz({ ist_notiz: false, ist_altbestand: true, art: null }) === false);
pruefe('ist_notiz true schlägt art nicht um (das Backend rechnet)', istNotiz({ ist_notiz: true, art: 'bildgeschichte' }) === true);
pruefe('Antwort ohne ist_notiz, ohne art -> Notiz', istNotiz({ text: 'x' }) === true);
pruefe('Antwort ohne ist_notiz, mit art -> keine Notiz', istNotiz({ art: 'anlassgeschichte' }) === false);
pruefe('null/undefined/Text/Zahl -> keine Notiz, kein Wurf',
  istNotiz(null) === false && istNotiz(undefined) === false && istNotiz('kaputt') === false && istNotiz(5) === false);

console.log('\n2) erzaehlGeschichteKoerper — alte Signatur gilt weiter, neue Felder optional');
const alt = erzaehlGeschichteKoerper('ev-1', 'Text', 4711, 'id-alt', 'Frage');
pruefe('alte Signatur: Rumpf wie früher',
  JSON.stringify(alt) === JSON.stringify({ ereignis_kennung: 'ev-1', text: 'Text', quelle: 'tippen', datei_kennung: 4711, ersetzt: 'id-alt', abfrage: 'Frage' }),
  JSON.stringify(alt));
pruefe('ohne neue Felder: weder art noch notiz_bestaetigt',
  !('art' in alt) && !('notiz_bestaetigt' in alt));
const gen = erzaehlGeschichteKoerper('ev-1', 'Text', 4711, 'id-alt', null, 'generiert', 'bildgeschichte');
pruefe('quelle und art werden gesetzt', gen.quelle === 'generiert' && gen.art === 'bildgeschichte' && gen.ersetzt === 'id-alt');
pruefe('notiz_bestaetigt nur bei echtem true',
  erzaehlGeschichteKoerper('e', 't', null, null, null, 'tippen', null, true).notiz_bestaetigt === true
  && !('notiz_bestaetigt' in erzaehlGeschichteKoerper('e', 't', null, null, null, 'tippen', null, false))
  && !('notiz_bestaetigt' in erzaehlGeschichteKoerper('e', 't', null, null, null, 'tippen', null, 'ja')));
pruefe('ohne dateiKennung (Gruppe): keine datei_kennung',
  !('datei_kennung' in erzaehlGeschichteKoerper('e', 't', null, null, null, 'generiert', 'anlassgeschichte')));

console.log('\n3) Zähler je Bild — nur Notizen');
const zahlen = erzaehlGeschichtenJeBild([
  { datei_kennung: 11, ist_notiz: true }, { datei_kennung: 11, ist_notiz: true },
  { datei_kennung: 11, ist_notiz: false, art: 'bildgeschichte' },
  { datei_kennung: 12, ist_notiz: false, ist_altbestand: true },
  { datei_kennung: 12 },                       // alte Antwort ohne ist_notiz, ohne art -> Notiz
  { datei_kennung: 13, art: 'bildgeschichte' }, // alte Antwort mit art -> keine Notiz
]);
pruefe('Bild 11: zwei Notizen, die Bildgeschichte zählt nicht', zahlen['11'] === 2, JSON.stringify(zahlen));
pruefe('Bild 12: Altbestand zählt nicht, Zeile ohne Feld ist Notiz', zahlen['12'] === 1, JSON.stringify(zahlen));
pruefe('Bild 13: nur eine Geschichte -> kein Eintrag', !('13' in zahlen), JSON.stringify(zahlen));

console.log('\n4) erzaehlGeschichteArtFuer / erzaehlNeuesteGeschichte');
pruefe('Notiz mit Bild -> bildgeschichte', erzaehlGeschichteArtFuer({ datei_kennung: 5 }) === 'bildgeschichte');
pruefe('Kennung 0 zählt als Bild', erzaehlGeschichteArtFuer({ datei_kennung: 0 }) === 'bildgeschichte');
pruefe('Notiz zur Gruppe -> anlassgeschichte', erzaehlGeschichteArtFuer({ datei_kennung: null }) === 'anlassgeschichte');
const liste = [
  { id: 'a', art: 'bildgeschichte', datei_kennung: 101, zeit: '2026-11-01T10:00:00', text: 'alt' },
  { id: 'b', art: 'bildgeschichte', datei_kennung: 101, zeit: '2026-11-02T10:00:00', text: 'neu' },
  { id: 'c', art: 'bildgeschichte', datei_kennung: 102, zeit: '2026-11-03T10:00:00', text: 'anderes Bild' },
  { id: 'd', art: 'anlassgeschichte', datei_kennung: null, zeit: '2026-11-01T11:00:00', text: 'Anlass' },
  { id: 'e', ist_notiz: true, datei_kennung: 101, zeit: '2026-11-05T10:00:00', text: 'Notiz' },
];
pruefe('neueste Bildgeschichte des Bildes', (erzaehlNeuesteGeschichte(liste, 'bildgeschichte', 101) || {}).id === 'b');
pruefe('Kennung als Zahl oder Text', (erzaehlNeuesteGeschichte(liste, 'bildgeschichte', '102') || {}).id === 'c');
pruefe('Anlassgeschichte nur ohne Bild', (erzaehlNeuesteGeschichte(liste, 'anlassgeschichte', null) || {}).id === 'd');
pruefe('keine Geschichte -> null, kein Wurf',
  erzaehlNeuesteGeschichte(liste, 'bildgeschichte', 999) === null && erzaehlNeuesteGeschichte(null, 'bildgeschichte', 1) === null);

// ---------------------------------------------------------------------------
// Schein-Oberfläche und Schein-Backend für die Funktionen der Oberfläche.
// ---------------------------------------------------------------------------
class Knoten {
  constructor(tag) {
    this.tagName = tag; this.kinder = []; this.className = ''; this.style = {};
    this._text = ''; this.hidden = false; this.value = ''; this.attribute = {}; this.title = '';
  }
  get textContent() {
    return this.kinder.length ? this.kinder.map((k) => k.textContent).join(' ') : this._text;
  }
  set textContent(t) { this.kinder = []; this._text = String(t); }
  get childElementCount() { return this.kinder.length; }
  appendChild(k) { this.kinder.push(k); return k; }
  setAttribute(n, w) { this.attribute[n] = w; }
  alle(klasse) {
    let treffer = [];
    this.kinder.forEach((k) => {
      if ((k.className || '').split(/\s+/).includes(klasse)) treffer.push(k);
      treffer = treffer.concat(k.alle(klasse));
    });
    return treffer;
  }
}

function baue(optionen) {
  optionen = optionen || {};
  const ids = ['erzaehl-gruppen-geschichten', 'erzaehl-geschichten', 'erzaehl-gruppen-geschichten-kopf',
    'erzaehl-geschichten-kopf', 'erzaehl-bildgeschichte', 'erzaehl-bildgeschichte-text',
    'erzaehl-anlassgeschichte', 'erzaehl-anlassgeschichte-text', 'erzaehl-text', 'erzaehl-hinweis'];
  const knoten = {};
  ids.forEach((id) => { knoten[id] = new Knoten('div'); });
  knoten['erzaehl-text'].value = optionen.notizfeld || '';
  knoten['erzaehl-bildgeschichte'].hidden = true;
  knoten['erzaehl-anlassgeschichte'].hidden = true;

  // Kacheln mit ✎-Marker
  const kacheln = [101, 102].map((fid) => {
    const marker = new Knoten('span');
    return { fid, marker, getAttribute: () => String(fid), querySelector: () => marker };
  });
  knoten['erzaehl-raster'] = { querySelectorAll: () => kacheln };

  const zustand = {
    aktuellesEreignis: 'E-t1', ansicht: optionen.ansicht || 'einzel', index: 0, perspektive: 'ich',
    entwurfJeAnlass: new Map(),
    detail: {
      kennung: 'E-t1', datei_kennungen: [101, 102],
      geschichten: (optionen.geschichten || []).map((g) => Object.assign({}, g)),
    },
  };

  // Schein-Backend: hängt Zeilen an (nur anhängen!) und liefert sie MIT Einordnung zurück.
  const backend = { zeilen: [], aufrufe: [], jsonSenden: [], loeschungen: 0, naechsteId: 1 };
  const fetchAttrappe = async (url, opt) => {
    backend.aufrufe.push({ url, methode: (opt && opt.method) || 'GET' });
    if (opt && opt.method === 'DELETE') backend.loeschungen++;
    const body = JSON.parse(opt.body);
    const zeile = Object.assign({ id: 'neu-' + (backend.naechsteId++), zeit: '2026-11-02T12:00:00+01:00' }, body);
    backend.zeilen.push(zeile);
    const art = body.art || null;
    const antwort = Object.assign({}, zeile, { art, ist_notiz: !art, ist_altbestand: false });
    return { ok: true, json: async () => ({ ok: true, geschichte: antwort }) };
  };
  const meldungen = { vorgelesen: [], alerts: [], bestaetigungen: 0 };
  const stubs = {
    zustand,
    el: (id) => knoten[id] || null,
    document: { createElement: (tag) => new Knoten(tag) },
    apiBase: () => '',
    fetch: fetchAttrappe,
    jsonSenden: async (pfad, koerper) => {
      backend.jsonSenden.push({ pfad, koerper });
      return { ok: true, geschichte: optionen.erzeugt || 'Eine neu erzeugte Geschichte.', fileid: 101 };
    },
    audioVorabFreischalten: () => {},
    vorlesenText: async (t) => { meldungen.vorgelesen.push(t); },
    confirm: () => { meldungen.bestaetigungen++; return true; },
    alert: (t) => { meldungen.alerts.push(t); },
    console,
    istNotiz,
    erzaehlGeschichteKoerper, erzaehlGeschichtenJeBild, erzaehlGeschichteArtFuer, erzaehlNeuesteGeschichte,
    // G2 (02.11.2026): reine Hilfsfunktion, wörtlich aus erzaehlen.js
    erzaehlBeschreibungFehltHinweis: new Function(extractFn('erzaehlBeschreibungFehltHinweis')
      + '; return erzaehlBeschreibungFehltHinweis;')(),
  };
  const eigene = ['aktuelleDateiKennung', 'leseBereichAnzeigen', 'geschichtenAnzeigen', 'kachelMarkerAktualisieren',
    'geschichteAnhaengen', 'geschichteSpeichern', 'geschichteErzeugen', 'alsGeschichteMarkieren'];
  const namen = Object.keys(stubs);
  const quellcode = eigene.map((n) => extractFn(n)).join('\n');
  const funktionen = new Function(...namen, quellcode + '; return { ' + eigene.join(', ') + ' };')(
    ...namen.map((n) => stubs[n]));
  return { knoten, kacheln, zustand, backend, meldungen, f: funktionen };
}

const NOTIZ_BILD = { id: 'n1', ist_notiz: true, ist_altbestand: false, art: null, datei_kennung: 101, text: 'Meine Notiz zum Bild', zeit: '2026-11-01T09:00:00', quelle: 'tippen' };
const NOTIZ_GRUPPE = { id: 'n2', ist_notiz: true, ist_altbestand: false, art: null, datei_kennung: null, text: 'Notiz zur Gruppe', zeit: '2026-11-01T09:30:00', quelle: 'tippen' };
const BILDGESCHICHTE = { id: 'b1', ist_notiz: false, ist_altbestand: false, art: 'bildgeschichte', datei_kennung: 101, text: 'Alte Bildgeschichte', zeit: '2026-11-01T10:00:00', quelle: 'generiert' };
const ANLASSGESCHICHTE = { id: 'a1', ist_notiz: false, ist_altbestand: false, art: 'anlassgeschichte', datei_kennung: null, text: 'Alte Anlassgeschichte', zeit: '2026-11-01T10:30:00', quelle: 'generiert' };
const ALTBESTAND = { id: 'x1', ist_notiz: false, ist_altbestand: true, art: null, datei_kennung: 101, text: 'Ein festgehaltener Augenblick aus dem Fotoarchiv.', zeit: '2026-10-20T10:00:00', quelle: 'tippen' };
const ALLE = [NOTIZ_BILD, NOTIZ_GRUPPE, BILDGESCHICHTE, ANLASSGESCHICHTE, ALTBESTAND];

function notizTexte(knoten, id) {
  return knoten[id].alle('erzaehl-geschichte-text').map((k) => k.textContent);
}

(async () => {
  console.log('\n5) (d) Notizliste und Lese-Bereich — Geschichte ist keine Notiz');
  let t = baue({ geschichten: ALLE, ansicht: 'einzel' });
  t.f.geschichtenAnzeigen();
  pruefe('Einzelbild: Notizliste zeigt nur die Notizen (Bild + Gruppe)',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')) === JSON.stringify(['Meine Notiz zum Bild', 'Notiz zur Gruppe']),
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')));
  pruefe('Einzelbild: Lese-Bereich „Bildgeschichte" zeigt die Bildgeschichte',
    t.knoten['erzaehl-bildgeschichte'].hidden === false && t.knoten['erzaehl-bildgeschichte-text'].textContent === 'Alte Bildgeschichte');
  pruefe('Einzelbild: Anlassgeschichte bleibt verborgen', t.knoten['erzaehl-anlassgeschichte'].hidden === true);
  pruefe('Einzelbild: Altbestand steht weder in der Liste noch im Lese-Bereich',
    !notizTexte(t.knoten, 'erzaehl-geschichten').some((x) => /Fotoarchiv/.test(x))
    && !/Fotoarchiv/.test(t.knoten['erzaehl-bildgeschichte-text'].textContent));
  pruefe('Notizfeld wird nicht angefasst', t.knoten['erzaehl-text'].value === '');

  t = baue({ geschichten: ALLE, ansicht: 'uebersicht' });
  t.f.geschichtenAnzeigen();
  pruefe('Übersicht: Gruppen-Notizliste zeigt nur die Gruppen-Notiz',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-gruppen-geschichten')) === JSON.stringify(['Notiz zur Gruppe']),
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-gruppen-geschichten')));
  pruefe('Übersicht: Lese-Bereich „Anlassgeschichte" zeigt die Anlassgeschichte',
    t.knoten['erzaehl-anlassgeschichte'].hidden === false && t.knoten['erzaehl-anlassgeschichte-text'].textContent === 'Alte Anlassgeschichte');
  pruefe('Übersicht: Bildgeschichte bleibt verborgen', t.knoten['erzaehl-bildgeschichte'].hidden === true);

  t = baue({ geschichten: [NOTIZ_BILD, BILDGESCHICHTE, ALTBESTAND] });
  t.f.kachelMarkerAktualisieren();
  pruefe('Kachelzähler ✎: Bild 101 zählt genau die eine Notiz',
    t.kacheln[0].marker.textContent === '✎ 1' && t.kacheln[0].marker.hidden === false,
    t.kacheln[0].marker.textContent);
  pruefe('Kachelzähler ✎: Bild 102 ohne Notiz bleibt leer', t.kacheln[1].marker.hidden === true);

  t = baue({ geschichten: [BILDGESCHICHTE, ALTBESTAND], ansicht: 'einzel' });
  t.f.geschichtenAnzeigen();
  pruefe('ohne Notizen: leere Notizliste (Kopfzeile bleibt zu), Bildgeschichte trotzdem sichtbar',
    t.knoten['erzaehl-geschichten'].childElementCount === 0 && t.knoten['erzaehl-geschichten-kopf'].hidden === true
    && t.knoten['erzaehl-bildgeschichte'].hidden === false);

  console.log('\n6) (d)/(e) Erzeugen: nicht ins Notizfeld, neue Zeile mit ersetzt, alte bleibt');
  t = baue({ geschichten: [NOTIZ_BILD, BILDGESCHICHTE], ansicht: 'einzel', erzeugt: 'Die neue Bildgeschichte.' });
  let r = await t.f.geschichteErzeugen('bildgeschichte', { dateiKennung: 101, beschreibung: 'Ein See', ort: 'Musterstadt', datum: '2021-08-01' });
  pruefe('Erzeugen gelingt', r.ok === true, JSON.stringify(r));
  pruefe('Anfrage an den Generator enthält KEINE notiz',
    t.backend.jsonSenden.length === 1 && t.backend.jsonSenden[0].pfad === '/api/erzaehlen/ki-geschichte'
    && !('notiz' in t.backend.jsonSenden[0].koerper), JSON.stringify(t.backend.jsonSenden));
  pruefe('genau eine neue Zeile angehängt', t.backend.zeilen.length === 1);
  const neu = t.backend.zeilen[0];
  pruefe('Zeile: art bildgeschichte, quelle generiert, am Bild, ersetzt = vorherige Bildgeschichte',
    neu && neu.art === 'bildgeschichte' && neu.quelle === 'generiert' && neu.datei_kennung === 101
    && neu.ersetzt === 'b1' && neu.text === 'Die neue Bildgeschichte.', JSON.stringify(neu));
  pruefe('Notizfeld bleibt leer (Geschichte steht nicht im Notizfeld)', t.knoten['erzaehl-text'].value === '');
  pruefe('Lese-Bereich zeigt die NEUE Fassung',
    t.knoten['erzaehl-bildgeschichte'].hidden === false && t.knoten['erzaehl-bildgeschichte-text'].textContent === 'Die neue Bildgeschichte.');
  pruefe('alte Fassung ist aus der Anzeige-Liste, die Datei wird nur ergänzt (kein DELETE, nur ein POST)',
    !t.zustand.detail.geschichten.some((g) => g.id === 'b1') && t.backend.loeschungen === 0
    && t.backend.aufrufe.length === 1 && t.backend.aufrufe[0].methode === 'POST');
  t.f.geschichtenAnzeigen();
  pruefe('(d) die Notizliste zeigt die neue Geschichte nicht',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')) === JSON.stringify(['Meine Notiz zum Bild']));
  t.f.kachelMarkerAktualisieren();
  pruefe('(d) der Zähler ✎ wächst nicht', t.kacheln[0].marker.textContent === '✎ 1');

  console.log('\n7) Erzeugen mit ungespeichertem Notizfeld: erst als Notiz speichern');
  t = baue({ geschichten: [], ansicht: 'einzel', notizfeld: 'Noch nicht gespeicherte Notiz', erzeugt: 'Geschichte nach der Notiz.' });
  r = await t.f.geschichteErzeugen('bildgeschichte', { dateiKennung: 101 });
  pruefe('zwei Zeilen: zuerst die Notiz, dann die Geschichte', t.backend.zeilen.length === 2, JSON.stringify(t.backend.zeilen));
  pruefe('erste Zeile: Notiz (quelle tippen, ohne art), am Bild',
    t.backend.zeilen[0].quelle === 'tippen' && !('art' in t.backend.zeilen[0])
    && t.backend.zeilen[0].text === 'Noch nicht gespeicherte Notiz' && t.backend.zeilen[0].datei_kennung === 101);
  pruefe('zweite Zeile: Bildgeschichte (generiert), ohne ersetzt (es gab keine)',
    t.backend.zeilen[1].art === 'bildgeschichte' && t.backend.zeilen[1].quelle === 'generiert' && !('ersetzt' in t.backend.zeilen[1]));
  pruefe('Notizfeld ist danach leer (die Geschichte steht dort nicht)', t.knoten['erzaehl-text'].value === '');
  t.f.geschichtenAnzeigen();
  pruefe('(o) die neue Notiz steht ohne Neuladen in der Notizliste, die Geschichte im Lese-Bereich',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')) === JSON.stringify(['Noch nicht gespeicherte Notiz'])
    && t.knoten['erzaehl-bildgeschichte-text'].textContent === 'Geschichte nach der Notiz.');

  console.log('\n8) Anlassweg: art anlassgeschichte, ohne Bild, ersetzt die vorherige');
  t = baue({ geschichten: [NOTIZ_GRUPPE, ANLASSGESCHICHTE], ansicht: 'uebersicht', erzeugt: 'Die neue Anlassgeschichte.' });
  r = await t.f.geschichteErzeugen('anlassgeschichte', {});
  pruefe('Anfrage an /anlass-geschichte ohne notiz',
    t.backend.jsonSenden.length === 1 && t.backend.jsonSenden[0].pfad === '/api/erzaehlen/anlass-geschichte'
    && !('notiz' in t.backend.jsonSenden[0].koerper), JSON.stringify(t.backend.jsonSenden));
  const nAnlass = t.backend.zeilen[0];
  pruefe('Zeile: art anlassgeschichte, generiert, ohne Bild, ersetzt a1',
    nAnlass.art === 'anlassgeschichte' && nAnlass.quelle === 'generiert' && !('datei_kennung' in nAnlass) && nAnlass.ersetzt === 'a1');
  pruefe('Lese-Bereich „Anlassgeschichte" zeigt die neue Fassung',
    t.knoten['erzaehl-anlassgeschichte-text'].textContent === 'Die neue Anlassgeschichte.' && t.knoten['erzaehl-anlassgeschichte'].hidden === false);

  console.log('\n9) Fehler beim Erzeugen: nichts gespeichert, Lese-Bereich bleibt');
  t = baue({ geschichten: [BILDGESCHICHTE], ansicht: 'einzel' });
  const fehlerStubs = t; // jsonSenden wird per Neuaufbau mit Fehlerantwort ersetzt
  const orig = fehlerStubs.backend.jsonSenden;
  // Fehlerfall über einen zweiten Aufbau mit Generator-Fehler:
  const fehlerLauf = baue({ geschichten: [BILDGESCHICHTE], ansicht: 'einzel' });
  const quellcode = ['aktuelleDateiKennung', 'leseBereichAnzeigen', 'geschichteAnhaengen', 'geschichteSpeichern', 'geschichteErzeugen']
    .map((n) => extractFn(n)).join('\n');
  const aufrufe = [];
  const fn = new Function('zustand', 'el', 'jsonSenden', 'fetch', 'apiBase', 'geschichtenAnzeigen', 'kachelMarkerAktualisieren',
    'erzaehlGeschichteKoerper', 'erzaehlNeuesteGeschichte',
    quellcode + '; return geschichteErzeugen;')(
    fehlerLauf.zustand, (id) => fehlerLauf.knoten[id] || null,
    async () => ({ ok: false, fehler: 'Modell nicht erreichbar' }),
    async () => { aufrufe.push('fetch'); return { ok: true, json: async () => ({}) }; },
    () => '', () => {}, () => {}, erzaehlGeschichteKoerper, erzaehlNeuesteGeschichte);
  r = await fn('bildgeschichte', { dateiKennung: 101 });
  pruefe('Fehler wird gemeldet, nichts gespeichert', r.ok === false && /nicht erreichbar/.test(r.fehler) && aufrufe.length === 0, JSON.stringify(r));
  void orig;

  console.log('\n10) (i) „Das ist keine Notiz, sondern eine Geschichte" hängt genau EINE Zeile an');
  t = baue({ geschichten: [NOTIZ_BILD, NOTIZ_GRUPPE], ansicht: 'einzel' });
  t.f.geschichtenAnzeigen();
  const rBild = await t.f.alsGeschichteMarkieren(NOTIZ_BILD);
  pruefe('genau ein POST, keine Löschung', rBild.ok === true && t.backend.zeilen.length === 1 && t.backend.loeschungen === 0);
  const z = t.backend.zeilen[0];
  pruefe('Zeile: ersetzt = alte Notiz, gleicher Text, art bildgeschichte, quelle generiert, gleiches Bild',
    z.ersetzt === 'n1' && z.text === 'Meine Notiz zum Bild' && z.art === 'bildgeschichte'
    && z.quelle === 'generiert' && z.datei_kennung === 101 && z.ereignis_kennung === 'E-t1', JSON.stringify(z));
  pruefe('(o) sofort ohne Neuladen: aus der Notizliste raus, im Lese-Bereich drin',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')) === JSON.stringify(['Notiz zur Gruppe'])
    && t.knoten['erzaehl-bildgeschichte-text'].textContent === 'Meine Notiz zum Bild');
  t.f.kachelMarkerAktualisieren();
  pruefe('Zähler ✎ sinkt auf 0', t.kacheln[0].marker.hidden === true);

  const rGruppe = await t.f.alsGeschichteMarkieren(NOTIZ_GRUPPE);
  pruefe('Notiz zur Gruppe -> art anlassgeschichte, ohne Bild',
    rGruppe.ok === true && t.backend.zeilen.length === 2 && t.backend.zeilen[1].art === 'anlassgeschichte'
    && !('datei_kennung' in t.backend.zeilen[1]) && t.backend.zeilen[1].ersetzt === 'n2');

  console.log('\n11) (o) neue Notiz erscheint ohne Neuladen am richtigen Ort');
  t = baue({ geschichten: [BILDGESCHICHTE], ansicht: 'einzel', notizfeld: 'Frisch getippte Notiz' });
  const gespeichert = await t.f.geschichteSpeichern();
  pruefe('Speichern meldet Erfolg und leert das Feld', gespeichert === true && t.knoten['erzaehl-text'].value === '');
  pruefe('POST-Antwort mit ist_notiz landet in der Liste',
    t.zustand.detail.geschichten.some((g) => g.text === 'Frisch getippte Notiz' && g.ist_notiz === true));
  pruefe('Notizliste zeigt sie, Lese-Bereich zeigt weiter die Bildgeschichte',
    JSON.stringify(notizTexte(t.knoten, 'erzaehl-geschichten')) === JSON.stringify(['Frisch getippte Notiz'])
    && t.knoten['erzaehl-bildgeschichte-text'].textContent === 'Alte Bildgeschichte');
  t = baue({ geschichten: [], ansicht: 'einzel', notizfeld: '   ' });
  pruefe('leeres Feld -> nichts gespeichert, false', (await t.f.geschichteSpeichern()) === false && t.backend.zeilen.length === 0);
  t = baue({ geschichten: [], ansicht: 'einzel', notizfeld: 'Text' });
  await t.f.geschichteSpeichern({ isTrusted: true });   // wie der Click-Event: darf nie ersetzt/abfrage werden
  pruefe('ein Event-Objekt als erstes Argument wird nicht als ersetzt-ID gesendet',
    t.backend.zeilen.length === 1 && !('ersetzt' in t.backend.zeilen[0]) && !('abfrage' in t.backend.zeilen[0]));

  console.log('\n12) Verdrahtung im Quelltext und in index.html');
  const listenerBlock = src.slice(src.indexOf("const speichernBtn = el('erzaehl-speichern-btn')"));
  pruefe('Speichern-Knopf ruft geschichteSpeichern ohne Event-Argument auf',
    /speichernBtn\.addEventListener\('click', \(\) => geschichteSpeichern\(\)\)/.test(listenerBlock));
  pruefe('Bildgeschichten-Knopf nutzt geschichteErzeugen und schreibt nicht ins Notizfeld',
    /geschichteErzeugen\('bildgeschichte'/.test(src) && !/eingabeFeld\.value = res\.geschichte/.test(src));
  pruefe('Anlass-Knopf nutzt geschichteErzeugen', /geschichteErzeugen\('anlassgeschichte'/.test(src));
  pruefe('Notizliste filtert mit istNotiz', /detail\.geschichten\.filter\(\(g\) => g && istNotiz\(g\)\)/.test(src));
  pruefe('Vorlese-Knöpfe der Lese-Bereiche sind verdrahtet',
    /vorlesen\('erzaehl-bildgeschichte-text'/.test(src) && /vorlesen\('erzaehl-anlassgeschichte-text'/.test(src));
  ['erzaehl-bildgeschichte', 'erzaehl-bildgeschichte-text', 'erzaehl-bildgeschichte-vorlesen',
    'erzaehl-anlassgeschichte', 'erzaehl-anlassgeschichte-text', 'erzaehl-anlassgeschichte-vorlesen']
    .forEach((id) => pruefe('index.html enthält #' + id, new RegExp('id="' + id + '"').test(html)));
  pruefe('Überschriften „Bildgeschichte" und „Anlassgeschichte" stehen in index.html',
    />Bildgeschichte<\/span>/.test(html) && />Anlassgeschichte<\/span>/.test(html));
  pruefe('Lese-Bereiche stehen NICHT in den Notiz-Behältern',
    html.indexOf('id="erzaehl-bildgeschichte"') < html.indexOf('id="erzaehl-geschichten"')
    && html.indexOf('id="erzaehl-anlassgeschichte"') < html.indexOf('id="erzaehl-gruppen-geschichten"'));
  pruefe('Cache-Bump: erzaehlen.js?v= mindestens 20261102E',
    ((html.match(/erzaehlen\.js\?v=([0-9]{8}[A-Z])/) || [])[1] || '') >= '20261102E');

  console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
  process.exit(fehler ? 1 : 0);
})();
