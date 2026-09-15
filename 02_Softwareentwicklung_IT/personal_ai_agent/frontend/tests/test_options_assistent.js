// Testet die Options-Menü-Logik GEGEN DEN ECHTEN Quelltext (frontend/app.js).
//
// Gemeldeter Fall (Sebastian 2026-09-15): Kommt eine Abfrage mit Frage und
// mehreren Antworten, standen ALLE Antworten flach untereinander und die
// Fragen waren nicht mehr sichtbar. Erwartung: Fragen werden NACHEINANDER
// gestellt (Frage immer sichtbar über ihren Optionen), am Ende geht EINE
// Nachricht mit allen Antworten an den Agenten.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_options_assistent.js app.js                 # NEU -> grün
//   git show HEAD:frontend/app.js > /tmp/alt_app.js
//   node tests/test_options_assistent.js /tmp/alt_app.js        # ALT -> rot
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

function extractFn(name, pflicht = true) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) {
    if (pflicht) throw new Error('nicht gefunden: ' + name);
    return '';
  }
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

// ---- minimale DOM-Stubs (nur was bauOptionsUi/_bauOptionsAssistent braucht) ----
function makeEl(tag) {
  const el = {
    tagName: tag,
    className: '',
    children: [],
    listeners: {},
    style: {},
    _text: '',
    _html: '',
    appendChild(c) { el.children.push(c); return c; },
    addEventListener(typ, fn) { (el.listeners[typ] = el.listeners[typ] || []).push(fn); },
    klick() { (el.listeners.click || []).forEach(fn => fn()); },
  };
  Object.defineProperty(el, 'textContent', { get: () => el._text, set: v => { el._text = v; } });
  Object.defineProperty(el, 'innerHTML', {
    get: () => el._html,
    set: v => { el._html = v; if (v === '') el.children = []; },
  });
  return el;
}
global.document = { createElement: makeEl };

// sendMessage-Aufrufe mitschreiben
const gesendet = [];
global.sendMessage = (t) => gesendet.push(t);

eval(extractFn('parseOptionsMenue'));
eval(extractFn('_bauOptionsAssistent', false));
eval(extractFn('bauOptionsUi'));

function alleButtons(el, out = []) {
  (el.children || []).forEach(c => { if (c.tagName === 'button') out.push(c); alleButtons(c, out); });
  return out;
}
function kommendeTexte(el, out = []) {
  (el.children || []).forEach(c => { if (c._text) out.push(c._text); kommendeTexte(c, out); });
  return out;
}

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

// Rohe Hermes-Ausgabe mit ZWEI Fragen (Zeilen teils per Layout-Pipe getrennt,
// wie es die CLI ausgibt) — 4 Antworten, 2 Fragen.
const ROH = 'Ich brauche zwei Angaben.'
  + '| F1: Wo soll es laufen?'
  + '| ❯ 1. Termux'
  + '| 2. PC'
  + '| F2: Wie soll gepusht werden?'
  + '| ❯ 1. Token'
  + '| 2. SSH';

console.log('--- Parser: Frage-Blöcke statt flacher Liste ---');
const menu = parseOptionsMenue(ROH);
// Beim ALTEN Stand gibt es kein fragen-Array -> alle Prüfungen werden rot
// gemeldet, statt mitten im Lauf abzubrechen.
const f2 = (menu && menu.fragen && menu.fragen[1]) || { frage: '', optionen: [] };
pruefe('Menü erkannt', !!menu);
pruefe('Antworten bleiben bei ihrer Frage (2 Blöcke)',
  !!menu && menu.fragen && menu.fragen.length === 2,
  menu && JSON.stringify(menu.fragen));
pruefe('Frage 2 ist sichtbar (früher verloren)',
  f2.frage.includes('gepusht'),
  menu && (menu.fragen || []).map(f => f.frage).join(' || '));
pruefe('Optionen korrekt zugeordnet',
  f2.optionen.map(o => o.text).join(',') === 'Token,SSH');
pruefe('flache Liste bleibt verfügbar (Rückwärtskompatibilität)',
  !!menu && menu.optionen.length === 4);

console.log('--- Assistent: Fragen nacheinander durchklicken ---');
gesendet.length = 0;
const box = bauOptionsUi(menu);
if (box.children) {
  let btns = alleButtons(box);
  let texte = kommendeTexte(box).join(' | ');
  pruefe('Frage 1 zuerst sichtbar', texte.includes('Wo soll es laufen?'), texte);
  pruefe('Frage 2 noch NICHT sichtbar', !texte.includes('gepusht'), texte);
  pruefe('nur die 2 Optionen von Frage 1 angeboten', btns.length === 2, 'buttons=' + btns.length);
  pruefe('Schrittzähler steht da', texte.includes('Frage 1 von 2'), texte);

  // Antwort auf Frage 1 anklicken -> erst dann erscheint Frage 2, noch KEIN Senden
  btns[0].klick();
  btns = alleButtons(box);
  texte = kommendeTexte(box).join(' | ');
  pruefe('nach der Wahl: Frage 2 erscheint', texte.includes('gepusht'), texte);
  pruefe('Schrittzähler steht auf Frage 2 von 2', texte.includes('Frage 2 von 2'), texte);
  pruefe('nur die 2 Optionen von Frage 2 angeboten', btns.length === 2, 'buttons=' + btns.length);
  pruefe('noch nichts gesendet', gesendet.length === 0, JSON.stringify(gesendet));

  // Antwort auf Frage 2 -> jetzt genau EINE Nachricht mit beiden Antworten
  btns[0].klick();
  pruefe('nach der letzten Wahl: genau EINE Nachricht gesendet', gesendet.length === 1, JSON.stringify(gesendet));
  const nachricht = gesendet[0] || '';
  pruefe('Antwort 1 enthalten', nachricht.includes('Termux'), nachricht);
  pruefe('Antwort 2 enthalten', nachricht.includes('Token'), nachricht);
  pruefe('Frage 1 steht bei Antwort 1 (Zuordnung eindeutig)', nachricht.includes('Wo soll es laufen?'), nachricht);
  pruefe('Frage 2 steht bei Antwort 2', nachricht.includes('gepusht'), nachricht);
  pruefe('keine Optionen mehr klickbar (abgeschlossen)', alleButtons(box).length === 0);
} else {
  fehler++; console.log('  FEHL bauOptionsUi lieferte keinen Baum (kein fragen-Array = alter Stand)');
}

console.log(fehler === 0 ? '\nERGEBNIS: alle Prüfungen grün' : '\nERGEBNIS: ' + fehler + ' Prüfung(en) rot');
process.exit(fehler === 0 ? 0 : 1);
