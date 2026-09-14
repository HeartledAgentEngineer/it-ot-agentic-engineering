// Testet die Quiz-Beenden-Logik GEGEN DEN ECHTEN Quelltext (app.js).
// Es werden die echten Funktionen _quizWeiterAbbrechen/_quizWeiterPlanen/
// beendeQuizAktiv ausgeschnitten und in einer Stub-Umgebung ausgefuehrt:
// genau der gemeldete Fall "waehrend des Auto-Weiter-Fensters beenden".
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

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

// ---- Stubs der Umgebung ----
let _quizAktiv = false;
let _rundeToken = 0;
let _quizWeiterTimer = null;
let _analyseAbort = null;
let _quizOffeneZuordnungen = [];
let naechsteQuizRundeAufrufe = 0;
let addMessageTexte = [];
let kartenGeleert = 0;
function naechsteQuizRunde() { naechsteQuizRundeAufrufe++; }
function addMessage(t) { addMessageTexte.push(t); }
function raeumeQuizKopienAuf() {}
function quizBeantwortenSilent() {}
const fakeKarten = [{ set innerHTML(v) { if (v === '') kartenGeleert++; }, get innerHTML() { return 'x'; } }];
global.document = {
  querySelectorAll(sel) { return sel.indexOf('quizkarte') !== -1 ? fakeKarten : []; },
  querySelector() { return null; },
};

// ---- Echten Code ausschneiden und einbinden ----
eval(extractFn('_quizWeiterAbbrechen'));
eval(extractFn('_quizWeiterPlanen'));
eval(extractFn('beendeQuizAktiv'));

function warte(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  let fails = 0;
  const ck = (name, ist, soll) => {
    if (ist === soll) console.log('  OK   ' + name + ' (=' + ist + ')');
    else { console.log('  FAIL ' + name + ': erwartet ' + soll + ', war ' + ist); fails++; }
  };

  // A) GEGENPROBE: Timer feuert in laufender Sitzung -> naechste Runde kommt
  _quizAktiv = true; naechsteQuizRundeAufrufe = 0;
  _quizWeiterPlanen(150);
  await warte(300);
  ck('A Timer feuert bei laufender Sitzung', naechsteQuizRundeAufrufe, 1);

  // B) DER BUGFALL: waehrend des Auto-Weiter-Fensters beenden
  _quizAktiv = true; naechsteQuizRundeAufrufe = 0; kartenGeleert = 0; addMessageTexte = [];
  _quizWeiterPlanen(1500);       // Auto-Weiter steht aus (wie nach einer Antwort)
  beendeQuizAktiv();             // Nutzer drueckt ✕ innerhalb von 1,5 s
  await warte(2200);             // deutlich laenger als das Timer-Fenster
  ck('B nach Beenden kommt KEINE neue Runde', naechsteQuizRundeAufrufe, 0);
  ck('B Quiz ist aus', _quizAktiv, false);
  ck('B Quiz-Karte wurde geleert', kartenGeleert, 1);
  ck('B Beenden-Meldung gezeigt', addMessageTexte.some(t => t.indexOf('Quiz beendet') !== -1), true);

  // C) Ruhende Analyse wird entwertet (kein spaeteres Nachschieben)
  _quizAktiv = true; _rundeToken = 5; _analyseAbort = { aborted: false, abort() { this.aborted = true; } };
  const alt = _rundeToken, altAb = _analyseAbort;
  beendeQuizAktiv();
  ck('C Lauf-Token erhoeht (alte Runde verwirft sich)', _rundeToken > alt, true);
  ck('C laufende Analyse abgebrochen', altAb.aborted, true);

  // D) Doppeltes Beenden bleibt harmlos
  _quizAktiv = true; naechsteQuizRundeAufrufe = 0;
  beendeQuizAktiv(); beendeQuizAktiv();
  await warte(200);
  ck('D doppeltes Beenden ohne Nachwirkung', naechsteQuizRundeAufrufe, 0);

  console.log('\n  --> Fehler: ' + fails);
  process.exit(fails ? 1 : 0);
})();
