// Erzähl-Diashow: Prüfblatt (Auftrag E8a, 28.09.2026).
//
// Dieser Test prüft:
//   * die drei REINEN Funktionen werden wörtlich aus dem ECHTEN erzaehlen.js
//     geschnitten und in Node ausgeführt (wie test_selbsttest.js/test_foto_galerie.js) —
//     es wird nichts nachgebaut,
//   * erzaehlSprachbefehl: nur EXAKTE Treffer auf weiter/zurück/speichern
//     (samt Varianten) lösen einen Befehl aus, alles andere ist Diktat-Text,
//   * erzaehlTitel: event -> thema -> "Ohne Titel", nimmt ein vorhandenes
//     titel-Feld direkt an,
//   * erzaehlIndex: geklemmt an den Rändern (kein Überlauf), n<=0 -> 0,
//   * index.html lädt erzaehlen.js mit ?v= und enthält #erzaehlen-btn.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_erzaehlen.js erzaehlen.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const src = fs.readFileSync(pfadJs, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadJs));
let html = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Funktion exakt aus dem Quelltext schneiden (Klammern zählen). */
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
// erzaehlSprachbefehl ruft den privaten Helfer _erzaehlNormalisieren —
// beide zusammen ausschneiden, damit nichts nachgebaut wird.
eval(extractFn('_erzaehlNormalisieren'));
eval(extractFn('erzaehlSprachbefehl'));
eval(extractFn('erzaehlTitel'));
eval(extractFn('erzaehlIndex'));

console.log('\n1) erzaehlSprachbefehl — nur exakte Treffer sind ein Befehl');
pruefe('null -> null', erzaehlSprachbefehl(null) === null);
pruefe('undefined -> null', erzaehlSprachbefehl(undefined) === null);
pruefe('leer -> null', erzaehlSprachbefehl('') === null);
pruefe('nur Leerzeichen -> null', erzaehlSprachbefehl('   ') === null);
pruefe('Zahl als Eingabe -> null (kein Wurf)', erzaehlSprachbefehl(42) === null);

pruefe('"weiter" -> weiter', erzaehlSprachbefehl('weiter') === 'weiter');
pruefe('"Weiter" (Groß) -> weiter', erzaehlSprachbefehl('Weiter') === 'weiter');
pruefe('"weiter." (Punkt) -> weiter', erzaehlSprachbefehl('weiter.') === 'weiter');
pruefe('"  weiter  " (Leerzeichen) -> weiter', erzaehlSprachbefehl('  weiter  ') === 'weiter');
pruefe('"nächstes" -> weiter', erzaehlSprachbefehl('nächstes') === 'weiter');
pruefe('"naechstes" -> weiter', erzaehlSprachbefehl('naechstes') === 'weiter');

pruefe('"zurück" -> zurueck', erzaehlSprachbefehl('zurück') === 'zurueck');
pruefe('"zurueck" -> zurueck', erzaehlSprachbefehl('zurueck') === 'zurueck');
pruefe('"vorheriges" -> zurueck', erzaehlSprachbefehl('vorheriges') === 'zurueck');

pruefe('"speichern" -> speichern', erzaehlSprachbefehl('speichern') === 'speichern');
pruefe('"Speichern!" -> speichern', erzaehlSprachbefehl('Speichern!') === 'speichern');

pruefe('"Heute war ein schöner Tag" -> null (Diktat)', erzaehlSprachbefehl('Heute war ein schöner Tag') === null);
pruefe('"bitte weiter machen" -> null (kein exaktes Wort)', erzaehlSprachbefehl('bitte weiter machen') === null);
pruefe('"weitergehen" -> null (kein exaktes Wort)', erzaehlSprachbefehl('weitergehen') === null);
pruefe('"ich möchte speichern und dann..." -> null', erzaehlSprachbefehl('ich möchte speichern und dann weiterreden') === null);

console.log('\n2) erzaehlTitel — event -> thema -> "Ohne Titel"');
pruefe('nimmt vorhandenes titel-Feld direkt', erzaehlTitel({ titel: 'Schon fertig' }) === 'Schon fertig');
pruefe('event hat Vorrang', erzaehlTitel({ event: 'Geburtstag', thema: 'Feiern' }) === 'Geburtstag');
pruefe('ohne event -> thema', erzaehlTitel({ event: null, thema: 'Haus und Garten' }) === 'Haus und Garten');
pruefe('ohne event/thema -> Ohne Titel', erzaehlTitel({ event: null, thema: null }) === 'Ohne Titel');
pruefe('leere Zeichenketten zählen nicht', erzaehlTitel({ event: '   ', thema: '' }) === 'Ohne Titel');
pruefe('null -> Ohne Titel (kein Wurf)', erzaehlTitel(null) === 'Ohne Titel');
pruefe('undefined -> Ohne Titel (kein Wurf)', erzaehlTitel(undefined) === 'Ohne Titel');
pruefe('Zahl -> Ohne Titel (kein Wurf)', erzaehlTitel(42) === 'Ohne Titel');

console.log('\n3) erzaehlIndex — geklemmt an den Rändern, kein Überlauf');
pruefe('Mitte vor', erzaehlIndex(2, 5, 1) === 3);
pruefe('Mitte zurück', erzaehlIndex(2, 5, -1) === 1);
pruefe('am Ende "vor" bleibt am Ende (kein Umlauf)', erzaehlIndex(4, 5, 1) === 4);
pruefe('am Anfang "zurück" bleibt am Anfang (kein Umlauf)', erzaehlIndex(0, 5, -1) === 0);
pruefe('n=0 -> 0', erzaehlIndex(0, 0, 1) === 0);
pruefe('n negativ -> 0', erzaehlIndex(3, -1, 1) === 0);
pruefe('unbekannte Richtung -> vor', erzaehlIndex(2, 5, 0) === 3);
pruefe('nicht-numerischer Index -> wie 0', erzaehlIndex('x', 5, 1) === 1);
pruefe('n=1 bleibt immer 0', erzaehlIndex(0, 1, 1) === 0 && erzaehlIndex(0, 1, -1) === 0);

console.log('\n4) Verdrahtung: index.html lädt erzaehlen.js mit Cache-Bust und den Knopf');
pruefe('index.html bindet erzaehlen.js mit ?v= ein', /erzaehlen\.js\?v=\d{8}[A-Z]/.test(html), 'nicht gefunden');
pruefe('#erzaehlen-btn existiert', /id="erzaehlen-btn"/.test(html));
pruefe('erzaehlen.js wird NACH app.js eingebunden (API-Key-Patch zuerst)',
  html.indexOf('app.js?v=') < html.indexOf('erzaehlen.js?v='));
pruefe('#erzaehlen-sheet existiert', /id="erzaehlen-sheet"/.test(html));

console.log('\n5) Quelltext-Regeln: fetch -> Blob -> Objekt-URL, kein direktes thumb-URL in src, Freigabe vorhanden');
pruefe('nutzt URL.createObjectURL', src.includes('URL.createObjectURL'));
pruefe('nutzt URL.revokeObjectURL (Freigabe)', src.includes('URL.revokeObjectURL'));
pruefe('lädt Bilder über /api/cloud/thumb', src.includes('/api/cloud/thumb'));
pruefe('nutzt /api/sprache/transkript wie app.js (kein neuer Anbieter)', src.includes('/api/sprache/transkript'));
pruefe('MediaRecorder wird bewusst NICHT instanziiert', !src.includes('new MediaRecorder'));
pruefe('nutzt pcm-recorder.js (AudioWorklet, wie app.js)', src.includes('pcm-recorder.js'));
pruefe('app.js wird NICHT verändert (diese Datei ist eigenständig)', !src.includes('function sendMessage'));

console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
process.exit(fehler ? 1 : 0);
