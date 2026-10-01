// Weck-Overlay (großer Sprachknopf am Handy) – Prüfblatt (30.09.2026).
//
// Dieser Test prüft OHNE Netz und OHNE echten Browser:
//   * die drei REINEN Funktionen werden wörtlich aus dem ECHTEN wecken.js
//     geschnitten und in Node ausgeführt (wie test_erzaehlen.js) – es wird
//     nichts nachgebaut,
//   * die Verdrahtung läuft gegen eine DOM-ATTRAPPE (fake DOM-Objekte):
//     Knopf wird angelegt (mindestens 64 px, feste Position), Antippen löst
//     GENAU den bestehenden Mikrofon-Knopf aus, die Zustandstexte aus
//     #mic-status werden übernommen (MutationObserver), ohne Mikrofon-Element
//     passiert nichts,
//   * der Quelltext baut KEINEN eigenen Audio-/Netz-Weg (kein Aufruf von
//     getUserMedia/MediaRecorder/AudioWorklet/fetch/XMLHttpRequest),
//   * index.html lädt wecken.js seit 01.10.2026 NICHT mehr (Wunsch Sebastian).
//
// Aufruf (aus dem Repo-Ordner):  node frontend/tests/test_wecken.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'wecken.js');
const src = fs.readFileSync(pfadJs, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadJs));
let html = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Funktion exakt aus dem Quelltext schneiden (Klammern zählen) – dasselbe
 *  Verfahren wie in test_erzaehlen.js/test_vollbild_zoom.js. */
function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('nicht gefunden: ' + name);
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

// Die reinen Funktionen aus dem ECHTEN Quelltext laden und ausführen.
eval(extractFn('weckenPhase'));
eval(extractFn('weckenPhasentext'));
eval(extractFn('weckenAktion'));

// ═══════════════════════════════════════════════════════════════════════
// 1) Reine Funktionen – nur übersetzen, nichts erfinden
// ═══════════════════════════════════════════════════════════════════════
console.log('\n1) weckenPhase – ableiten aus dem Text von #mic-status (app.js:1143)');
pruefe('leer -> bereit', weckenPhase('') === 'bereit');
pruefe('nur Leerzeichen -> bereit', weckenPhase('   ') === 'bereit');
pruefe('null -> bereit (kein Wurf)', weckenPhase(null) === 'bereit');
pruefe('undefined -> bereit (kein Wurf)', weckenPhase(undefined) === 'bereit');
pruefe('Zahl -> bereit (kein Wurf)', weckenPhase(42) === 'bereit');
pruefe('„Mikrofon offen“ -> hoert_zu (app.js:1145)', weckenPhase('Mikrofon offen') === 'hoert_zu');
pruefe('„hört zu“ -> hoert_zu (app.js:1146)', weckenPhase('hört zu') === 'hoert_zu');
pruefe('„denkt nach“ -> denkt_nach (app.js:1147)', weckenPhase('denkt nach') === 'denkt_nach');
pruefe('„spricht“ -> spricht (app.js:1149)', weckenPhase('spricht') === 'spricht');
pruefe('mit Leerzeichen drumherum -> gleich', weckenPhase('  hört zu  ') === 'hoert_zu');
pruefe('unbekannter Text -> bereit (keine Erfindung)', weckenPhase('irgendwas') === 'bereit');

console.log('\n2) weckenPhasentext – genau die vier Zustände');
pruefe('hoert_zu -> „hört zu“', weckenPhasentext('hoert_zu') === 'hört zu');
pruefe('denkt_nach -> „denkt nach“', weckenPhasentext('denkt_nach') === 'denkt nach');
pruefe('spricht -> „spricht“', weckenPhasentext('spricht') === 'spricht');
pruefe('bereit -> „bereit“', weckenPhasentext('bereit') === 'bereit');
pruefe('Unbekanntes -> „bereit“ (Rückfall)', weckenPhasentext('x') === 'bereit');

console.log('\n3) weckenAktion – was ein Tipp auslöst');
pruefe('bereit -> starten', weckenAktion('bereit') === 'starten');
pruefe('hoert_zu -> stoppen (Tipp während der Aufnahme stoppt)', weckenAktion('hoert_zu') === 'stoppen');
pruefe('denkt_nach -> nichts (Erkennung nicht stören)', weckenAktion('denkt_nach') === '');
pruefe('spricht -> nichts (Vorlesen nicht stören)', weckenAktion('spricht') === '');

// ═══════════════════════════════════════════════════════════════════════
// 4) DOM-Attrappe: Verdrahtung wirklich ausführen (kein Netz, kein Browser)
// ═══════════════════════════════════════════════════════════════════════

/** Minimale DOM-Attrappe: gerade so viel, wie wecken.js wirklich benutzt.
 *  Bewusst klein – sie wächst nur, wenn der Quelltext mehr braucht. */
function fakeElement(tag) {
  return {
    tagName: String(tag || '').toUpperCase(),
    id: '',
    type: '',
    title: '',
    textContent: '',
    style: {},
    attributes: {},
    children: [],
    listeners: {},
    setAttribute(k, v) { this.attributes[k] = String(v); },
    getAttribute(k) {
      return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null;
    },
    addEventListener(art, fn) { (this.listeners[art] = this.listeners[art] || []).push(fn); },
    appendChild(kind) { this.children.push(kind); return kind; },
    click() { this.klickZaehler = (this.klickZaehler || 0) + 1; },
  };
}

/** Ein kompletter Testlauf: Modul gegen frische Attrappen ausführen.
 *  mitMic/mitStatus steuern, ob die BESTEHENDEN Elemente vorhanden sind. */
function baueLauf(optionen) {
  const opts = optionen || {};
  const erzeugte = [];
  const beobachter = [];

  const mic = fakeElement('button');
  const status = fakeElement('div');
  status.textContent = '';

  const elemente = {};
  if (opts.mitMic !== false) elemente['mic-btn'] = mic;
  if (opts.mitStatus !== false) elemente['mic-status'] = status;

  const body = fakeElement('body');
  const doc = {
    getElementById(id) { return elemente[id] || null; },
    createElement(tag) { const el = fakeElement(tag); erzeugte.push(el); return el; },
    body,
  };

  function FakeMutationObserver(cb) {
    this.cb = cb;
    this.ziel = null;
    this.optionen = null;
    beobachter.push(this);
  }
  FakeMutationObserver.prototype.observe = function (ziel, optionen) {
    this.ziel = ziel; this.optionen = optionen || {};
  };
  FakeMutationObserver.prototype.disconnect = function () {};

  // Feste Uhr: macht den Doppel-Tipp-Schutz prüfbar, ohne echt zu warten.
  let uhr = 1000000;
  const FakeDate = { now() { return uhr; } };

  // Wie im Browser laden: document/MutationObserver/Date sind genau die
  // globalen Namen, die der Quelltext erwartet. Kein Netz, kein echtes DOM.
  const starten = new Function('document', 'MutationObserver', 'Date', src);
  starten(doc, FakeMutationObserver, FakeDate);

  return {
    erzeugte, beobachter, mic, status, body,
    vor(ms) { uhr += ms; },
    tippe() {
      const knopf = erzeugte.find((e) => e.id === 'wecken-btn');
      const klicker = knopf && knopf.listeners.click;
      if (!klicker || !klicker.length) throw new Error('wecken-btn hat keinen Klick-Horch');
      klicker.forEach((fn) => fn({ type: 'click' }));
    },
    laufen() {
      const a = beobachter[0];
      if (!a) throw new Error('kein MutationObserver registriert');
      a.cb([]);
    },
  };
}

console.log('\n4) Attrappe: Knopf wird angelegt, Observer hängt an #mic-status');
const lauf = baueLauf({});
const overlay = lauf.erzeugte.find((e) => e.id === 'wecken-overlay');
const knopf = lauf.erzeugte.find((e) => e.id === 'wecken-btn');
const anzeige = lauf.erzeugte.find((e) => e.id === 'wecken-status');
pruefe('Overlay, Knopf und Anzeige wurden gebaut', !!overlay && !!knopf && !!anzeige);
pruefe('Overlay hängt im DOM (document.body)', lauf.body.children.indexOf(overlay) !== -1);
pruefe('Knopf ist ein echter <button>', !!knopf && knopf.tagName === 'BUTTON' && knopf.type === 'button');
const groesse = knopf ? /width:(\d+)px/.exec(knopf.style.cssText || '') : null;
pruefe('Knopf ist mindestens 64 px groß (gefunden: ' + (groesse ? groesse[1] + 'px' : '?') + ')',
  !!groesse && Number(groesse[1]) >= 64);
pruefe('Knopf ist rund (border-radius:50%)', /border-radius:50%/.test(knopf ? knopf.style.cssText : ''));
pruefe('Knopf hat feste Position (position:fixed)', /position:fixed/.test(overlay ? overlay.style.cssText : ''));
pruefe('Anzeige steht im Ruhezustand auf „bereit“', anzeige ? anzeige.textContent === 'bereit' : false);
pruefe('Observer beobachtet die bestehende Zeile #mic-status',
  lauf.beobachter.length === 1 && lauf.beobachter[0].ziel === lauf.status);

console.log('\n5) Antippen löst GENAU den bestehenden Mikrofon-Knopf aus');
pruefe('vorher wurde noch nichts ausgelöst', !lauf.mic.klickZaehler);
lauf.tippe();
pruefe('erster Tipp -> genau ein Klick auf #mic-btn (Start)', lauf.mic.klickZaehler === 1);
lauf.tippe();
pruefe('sofortiger Doppel-Tipp -> immer noch ein Klick (Sperre)', lauf.mic.klickZaehler === 1);
lauf.vor(800);
lauf.tippe();
pruefe('Tipp während der Start unterwegs ist -> kein zweiter Start', lauf.mic.klickZaehler === 1);
lauf.status.textContent = 'Mikrofon offen';
lauf.laufen();
pruefe('„Mikrofon offen“ wird als „hört zu“ angezeigt', anzeige.textContent === 'hört zu');
pruefe('Knopf-Titel nennt den Zustand', /hört zu/.test(knopf.title));
lauf.vor(300);
lauf.tippe();
pruefe('Tipp während der Aufnahme -> Klick auf #mic-btn (Stopp)', lauf.mic.klickZaehler === 2);
lauf.status.textContent = 'denkt nach';
lauf.laufen();
pruefe('„denkt nach“ wird angezeigt', anzeige.textContent === 'denkt nach');
lauf.vor(1000);
lauf.tippe();
pruefe('Tipp während der Erkennung tut nichts', lauf.mic.klickZaehler === 2);
lauf.status.textContent = '';
lauf.laufen();
pruefe('leerer Status -> wieder „bereit“', anzeige.textContent === 'bereit');
lauf.vor(5000);
lauf.tippe();
pruefe('nach dem Zurücksetzen startet ein Tipp wieder', lauf.mic.klickZaehler === 3);

console.log('\n6) Zustandstexte werden übernommen (nichts erfunden)');
const lauf2 = baueLauf({});
const anzeige2 = lauf2.erzeugte.find((e) => e.id === 'wecken-status');
const faelle = [
  ['', 'bereit'],
  ['Mikrofon offen', 'hört zu'],
  ['hört zu', 'hört zu'],
  ['denkt nach', 'denkt nach'],
  ['spricht', 'spricht'],
];
for (const fall of faelle) {
  lauf2.status.textContent = fall[0];
  lauf2.laufen();
  pruefe('Status „' + (fall[0] || '(leer)') + '“ -> Anzeige „' + fall[1] + '“',
    anzeige2.textContent === fall[1], 'gefunden: ' + anzeige2.textContent);
}
pruefe('Phase steht als data-phase am Overlay',
  lauf2.erzeugte.find((e) => e.id === 'wecken-overlay').getAttribute('data-phase') === 'spricht');

console.log('\n7) Ohne Mikrofon-Element passiert nichts (kein Ersatz-Weg)');
const ohne = baueLauf({ mitMic: false });
pruefe('kein Element gebaut, wenn #mic-btn fehlt',
  ohne.erzeugte.length === 0 && ohne.body.children.length === 0);
pruefe('kein Beobachter registriert, wenn #mic-btn fehlt', ohne.beobachter.length === 0);
const ohne2 = baueLauf({ mitStatus: false });
pruefe('kein Element gebaut, wenn #mic-status fehlt',
  ohne2.erzeugte.length === 0 && ohne2.body.children.length === 0);

// ═══════════════════════════════════════════════════════════════════════
// 8) Quelltext-Regeln: kein eigener Audio-/Netz-Weg, kein Fremdanbieter
// ═══════════════════════════════════════════════════════════════════════
console.log('\n8) Quelltext-Regeln (Datenschutz: kein zweiter Weg zum Mikrofon)');
pruefe('kein Aufruf von getUserMedia', !/getUserMedia\s*\(/.test(src));
pruefe('kein Zugriff auf navigator.mediaDevices', !/navigator\.mediaDevices/.test(src));
pruefe('kein new MediaRecorder', !/new\s+MediaRecorder/.test(src));
pruefe('kein new AudioWorkletNode', !/new\s+AudioWorkletNode/.test(src));
pruefe('kein fetch/XMLHttpRequest (kein neues Netz)', !/fetch\s*\(/.test(src) && !/XMLHttpRequest/.test(src));
pruefe('keine externen Adressen im Quelltext', !/https?:\/\//.test(src));
pruefe('löst den BESTEHENDEN Knopf aus (getElementById mic-btn + click)',
  /getElementById\('mic-btn'\)/.test(src) && /\.click\(\)/.test(src));
pruefe('liest den BESTEHENDEN Zustand (#mic-status + MutationObserver)',
  /getElementById\('mic-status'\)/.test(src) && /new MutationObserver/.test(src));

// ═══════════════════════════════════════════════════════════════════════
// 9) index.html: Overlay NICHT eingebunden (Entscheidung Sebastian 01.10.2026)
// ═══════════════════════════════════════════════════════════════════════
// Der Sprechknopf doppelte das Mikrofon in der Eingabeleiste („bringt ja gar
// nix, der muss auf jeden Fall weg"). Gebraucht wird das Weckwort von außen
// (A1c, Dienst in der App). Die Datei bleibt und wird oben weiter geprüft.
console.log('\n9) index.html: Overlay nicht eingebunden (Wunsch Sebastian 01.10.)');
pruefe('index.html lädt wecken.js NICHT mehr', !/<script[^>]+wecken\.js/.test(html));
pruefe('das Mikrofon in der Eingabeleiste bleibt (#mic-btn und #mic-status)',
  /id="mic-btn"/.test(html) && /id="mic-status"/.test(html));

console.log(fehler ? `\n${fehler} Prüfung(en) rot` : '\nalle Prüfungen grün');
process.exit(fehler ? 1 : 0);
