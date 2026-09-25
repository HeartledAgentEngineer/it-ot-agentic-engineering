// QUIZ-SUCHE VOLLSTÄNDIG: alle Personen des Katalogs anbieten, kennzeichnen
// statt ausblenden, "neue Person" direkt im Dropdown, Liste wird neu berechnet.
//
// Befund Sebastian 2026-09-25 (sinngemäß): "Wenn ich eine Person suche, soll er
// ja durch so eine Antwortauswahl kommen mit den Accounts. Den finde ich nicht.
// Das passiert nicht. Nur bei einigen Personen. Personen sollen auftauchen —
// nicht David ausblenden."
//
// Prüft am ECHTEN app.js:
//   A) alle drei Aufrufstellen übergeben die Katalog-Liste (nicht nur optionen)
//   B) Kennzeichnungs-Texte vorhanden, bestätigte Personen werden NICHT entfernt
//   C) "➕ ... als neue Person anlegen" ruft den BESTEHENDEN Weg auf (kein neues
//      Formular)
//   D) Liste wird nach einer Bestätigung neu berechnet (kein Einfrieren)
//   E) reine Logik-Tests der Suchfunktion (Kandidat zuerst, dann alphabetisch,
//      leere Eingabe -> keine Liste, Kennzeichnung, neue-Person-Option)
//
// Aufruf: node tests/test_quiz_suche_vollstaendig.js app.js
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('Funktion nicht gefunden: ' + name);
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

// Alle AUFRUFE (nicht die Definition) einer Funktion, jeweils mit Klammer-Bilanz.
function extractCalls(name) {
  const calls = [];
  let i = 0;
  while ((i = src.indexOf(name + '(', i)) !== -1) {
    if (src.slice(Math.max(0, i - 9), i) === 'function ') { i += name.length; continue; }
    let depth = 0, k = i + name.length;
    for (; k < src.length; k++) {
      if (src[k] === '(') depth++;
      else if (src[k] === ')') { depth--; if (depth === 0) { k++; break; } }
    }
    calls.push(src.slice(i, k));
    i = k;
  }
  return calls;
}

let fails = 0;
const ck = (name, ist, soll) => {
  if (ist === soll) console.log('  OK   ' + name);
  else { console.log('  FAIL ' + name + ': erwartet ' + JSON.stringify(soll) + ', war ' + JSON.stringify(ist)); fails++; }
};
const grund = (text) => console.log('       Grund: ' + text);

// ---------------------------------------------------------------------------
console.log('\nA) Alle drei Aufrufstellen übergeben die KATALOG-Liste (nicht nur optionen)');
{
  const calls = extractCalls('baueSuchMitVorschlaegen');
  ck('genau drei Aufrufstellen (Gruppenbild, Rahmen, Einzelbild)', calls.length, 3);
  grund('Die Suche wurde zuvor an drei Stellen nur mit den Runden-Kandidaten '
      + 'gefuettert (Gruppenbild / selbst gezogener Rahmen / Einzelbild) — genau '
      + 'deshalb fehlten alle uebrigen Katalog-Personen.');

  calls.forEach((call, nr) => {
    const stelle = (call.match(/quizKatalogNamen\(\)/) || []).length;
    const nurOptionen = /^baueSuchMitVorschlaegen\(\s*optionen\s*,/.test(call);
    ck('Aufruf ' + (nr + 1) + ': übergibt quizKatalogNamen() als Katalog-Liste', stelle >= 1, true);
    ck('Aufruf ' + (nr + 1) + ': NICHT mehr nur `optionen` als erste Liste', !nurOptionen, true);
    ck('Aufruf ' + (nr + 1) + ': Kandidaten kommen als (optionen || []) rein', /\(\s*optionen\s*\|\|\s*\[\]\s*\)/.test(call), true);
  });
  grund('Reihenfolge bleibt innen: Kandidaten (Backend-Wahrscheinlichkeit) zuerst, '
      + 'danach die uebrigen Katalog-Namen alphabetisch (s. Abschnitt E).');

  const lade = extractFn('ladeQuizKatalogNamen');
  ck('Katalog-Quelle ist GET /api/gesichter', lade.indexOf('/api/gesichter') !== -1, true);
  ck('Katalog wird je Person aus personen[].name gelesen', lade.indexOf('p && p.name') !== -1, true);
  const bau = extractFn('baueSuchMitVorschlaegen');
  ck('Suchfeld laedt den Katalog selbst nach (ladeQuizKatalogNamen)', bau.indexOf('ladeQuizKatalogNamen(false)') !== -1, true);
  ck('Suchfeld startet die Ladung, wenn noch kein Katalog da ist', bau.indexOf('if (!katalog.length) katalogFrisch();') !== -1, true);
}

// ---------------------------------------------------------------------------
console.log('\nB) Kennzeichnen statt Ausblenden');
{
  const bau = extractFn('baueSuchMitVorschlaegen');
  ck('Text "✓ schon auf diesem Bild" vorhanden', bau.indexOf('✓ schon auf diesem Bild') !== -1, true);
  ck('Text "✓ schon bestätigt" vorhanden', bau.indexOf('✓ schon bestätigt') !== -1, true);
  ck('Marker hängen an den Vorschlag (v.aufBild / v.bestaetigt)',
     bau.indexOf('if (v.aufBild) marken.push') !== -1 && bau.indexOf('if (v.bestaetigt) marken.push') !== -1, true);
  grund('Sebastians ausdruecklicher Wunsch: "Personen sollen auftauchen — nicht '
      + 'David ausblenden." Deshalb Markierung am Eintrag, kein Entfernen.');

  const logik = extractFn('quizSuchVorschlaege');
  ck('Logik kennzeichnet (Index-Vergleich), statt zu filtern',
     logik.indexOf('aufBild: aufBild.indexOf(name.toLowerCase()) !== -1') !== -1
     && logik.indexOf('bestaetigt: bestaetigt.indexOf(name.toLowerCase()) !== -1') !== -1, true);
  ck('kein Ruecksprung (return) nennt aufBild oder bestaetigt (kein Ausblenden)',
     (logik.match(/if \([^;]*?\) return;/g) || [])
       .every(g => !/aufBild|bestaetigt/.test(g)), true);
  ck('Builder zeichnet ALLE Vorschlaege (kein vorschlaege.filter)',
     bau.indexOf('vorschlaege.filter(') === -1, true);
  ck('Builder zeigt die Liste ueber forEach', bau.indexOf('vorschlaege.forEach(v => {') !== -1, true);
}

// ---------------------------------------------------------------------------
console.log('\nC) "als neue Person anlegen" nutzt den BESTEHENDEN Weg (kein neues Formular)');
{
  const bau = extractFn('baueSuchMitVorschlaegen');
  ck('Option "➕ … als neue Person anlegen" existiert', bau.indexOf("' als neue Person anlegen'") !== -1, true);
  ck('Klick geht ueber neuePersonWaehlen(v.name)', bau.indexOf('neuePersonWaehlen(v.name)') !== -1, true);
  ck('neuePersonWaehlen ruft den Kontext-Weg onNeu(name)',
     bau.indexOf("typeof ktx.onNeu === 'function'") !== -1 && bau.indexOf('ktx.onNeu(name)') !== -1, true);
  ck('ohne onNeu bleibt der bestehende Weg (onwaehl)',
     /neuePersonWaehlen = \(name\) => \{[\s\S]*?onwaehl\(String\(name \|\| ''\)\.trim\(\)\)/.test(bau), true);
  grund('Der "Neue Person"-Weg existiert bereits als Formular in der Quiz-Karte; '
      + 'die Suche oeffnet ihn nur und belegt den Namen vor.');

  const calls = extractCalls('baueSuchMitVorschlaegen');
  const mitOnNeu = calls.filter(c => /onNeu:\s*\(n\)\s*=>/.test(c));
  ck('zwei Aufrufstellen mit vorhandenem Formular reichen onNeu herein', mitOnNeu.length, 2);
  ck('Gruppen-Formular wird vorbelegt (inp.value = n)', /onNeu[\s\S]*?inp\.value = n;[\s\S]*?form\.style\.display = 'block';/.test(calls[0]), true);
  ck('Einzelbild-Formular wird vorbelegt (neuName.value = n)',
     calls.some(c => /onNeu[\s\S]*?neuName\.value = n;[\s\S]*?neuForm\.style\.display = 'block';/.test(c)), true);

  ck('KEIN zusaetzliches "➕ Neue Person"-Formular erfunden (weiterhin 2 Knoepfe)',
     (src.match(/➕ Neue Person/g) || []).length, 2);
  ck('Suchfeld baut keinen eigenen Button/Formular', bau.indexOf('macheQuizButton') === -1, true);
}

// ---------------------------------------------------------------------------
console.log('\nD) Liste wird neu berechnet (kein Einfrieren nach einer Bestätigung)');
{
  const bau = extractFn('baueSuchMitVorschlaegen');
  ck('Aufbau-Funktion aktualisieren() existiert', bau.indexOf('const aktualisieren = () => {') !== -1, true);
  ck('aktualisieren() rechnet die Liste bei JEDEM Aufbau neu',
     bau.indexOf('const vorschlaege = quizSuchVorschlaege(kandidaten, katalog, q, ktx);') !== -1, true);
  ck('frischer Katalog ersetzt den alten Stand (kein eingefrorenes Array)',
     bau.indexOf('katalog = namen || [];') !== -1, true);
  ck('Tippen baut die Liste neu (input -> aktualisieren)',
     bau.indexOf("inp.addEventListener('input', aktualisieren);") !== -1, true);
  ck('Oeffnen laedt neu (focus -> katalogFrisch)',
     /addEventListener\('focus'[\s\S]{0,200}katalogFrisch\(\)/.test(bau), true);

  ck('Katalog-Cache verwerfbar (quizKatalogVerwerfen existiert)', /function quizKatalogVerwerfen\(\)/.test(src), true);
  ck('Verwerfen nach Zuordnung im Gruppenbild', extractFn('starteGruppenQuiz').indexOf('quizKatalogVerwerfen()') !== -1, true);
  ck('Verwerfen nach Zuordnung im Einzelbild', extractFn('quizBeantworten').indexOf('quizKatalogVerwerfen()') !== -1, true);
  ck('Cache ist kurz (TTL statt Dauerzustand)', /QUIZ_KATALOG_TTL_MS = 60 \* 1000/.test(src), true);
  grund('Nach Person/neuer Person/uebersprungen wird onwaehl/onNeu gerufen, der '
      + 'Eingabe- und Dropdown-Inhalt geleert und der Katalog-Cache verworfen — '
      + 'beim naechsten Oeffnen/Tippen steht die frische Liste.');

  ck('ehrlicher Ladehinweis vorhanden', bau.indexOf('⏳ Personenkatalog lädt …') !== -1, true);
  ck('ehrliche Fehlermeldung statt still leer',
     /⚠️ ' \+ fehler \+ ' — nur Vorschläge'/.test(bau) && src.indexOf("Personenkatalog nicht ladbar") !== -1, true);
}

// ---------------------------------------------------------------------------
console.log('\nE) Reine Listen-Logik (quizSuchVorschlaege) — echter Code, ohne DOM');
{
  // Kein 'use strict' im Testfile -> direkter eval legt die Funktion an.
  eval(extractFn('quizSuchVorschlaege'));

  // E1: Kandidat zuerst (Backend-Wahrscheinlichkeit), danach alphabetisch
  const e1 = quizSuchVorschlaege(['Annabel'], ['Annabel', 'Anna', 'Bea'], 'Anna', null);
  ck('E1 Kandidat steht oben (obwohl "Anna" alphabetisch zuerst kaeme)',
     e1.map(v => v.name).join(','), 'Annabel,Anna');
  ck('E1 Kandidat ist als Vorschlag markiert', e1[0].kandidat, true);
  ck('E1 Katalog-Treffer ist kein Vorschlag', (e1[1] || {}).kandidat, false);
  ck('E1 bereits bekannter Name -> KEINE neue-Person-Option', e1.every(v => !v.neu), true);

  // E2: mehrere Katalog-Treffer alphabetisch, Kandidaten davor
  const e2 = quizSuchVorschlaege(['Zoe'], ['Zoe', 'Anna', 'Bea', 'Zara'], 'a', null);
  ck('E2 ohne Kandidaten-Treffer: neu-Option zuerst, danach alphabetisch',
     e2.map(v => v.neu ? ('neu:' + v.name) : v.name).join(','), 'neu:a,Anna,Bea,Zara');

  // E3: Kennzeichnung statt Ausblenden
  const e3 = quizSuchVorschlaege([], ['Anna', 'Bea'], 'Anna',
                                 { aufBild: ['Anna'], bestaetigt: ['Anna'] });
  ck('E3 schon zugeordnete Person BLEIBT in der Liste', e3.length, 1);
  ck('E3 Marker "schon auf diesem Bild"', e3[0].aufBild, true);
  ck('E3 Marker "schon bestaetigt"', e3[0].bestaetigt, true);
  const e3b = quizSuchVorschlaege(['Bea'], ['Bea'], 'Bea', { aufBild: ['Bea'] });
  ck('E3b zugeordnete Person auch als Backend-Kandidat sichtbar (nicht ausgeblendet)',
     e3b.length, 1);
  ck('E3b Marker gesetzt', e3b[0].aufBild && e3b[0].kandidat, true);

  // E4: neue Person anlegen
  const e4 = quizSuchVorschlaege([], ['Anna', 'Bea'], 'Clara', null);
  ck('E4 unbekannte Eingabe -> genau die neue-Person-Option', e4.length, 1);
  ck('E4 sie steht an ERSTER Stelle und traegt neu:true', e4[0].neu, true);
  ck('E4 Name uebernommen (getrimmt)', e4[0].name, 'Clara');
  const e4b = quizSuchVorschlaege([], ['Anna', 'Bea'], '  Clara  ', null);
  ck('E4b getippte Leerzeichen werden getrimmt', e4b[0].name, 'Clara');
  const e4c = quizSuchVorschlaege(['Clara'], [], 'Clara', null);
  ck('E4c Name existiert schon als Kandidat -> keine neue-Person-Option', e4c.every(v => !v.neu), true);

  // E5: leere Eingabe -> keine Liste
  ck('E5 leere Eingabe -> leere Liste', quizSuchVorschlaege(['Anna'], ['Anna'], '', null).length, 0);
  ck('E5 nur Leerzeichen -> leere Liste', quizSuchVorschlaege(['Anna'], ['Anna'], '   ', null).length, 0);

  // E6: keine Dubletten, Obergrenze 8
  const e6 = quizSuchVorschlaege(['Zoe'], ['Zoe', 'zoe', ' Zoe '], 'zoe', null);
  ck('E6 Dubletten (Kandidat vs. Katalog) zusammengefasst', e6.length, 1);
  const viele = [];
  for (let i = 1; i <= 12; i++) viele.push('A' + i);
  const e7 = quizSuchVorschlaege([], viele, 'a', null);
  ck('E7 Obergrenze 8 Eintraege', e7.length, 8);
  ck('E7 neu-Option bleibt trotzdem an erster Stelle', e7[0].neu, true);

  // E8: die 8er-Grenze schneidet MARKIERTE Personen nie ab
  const sortiert = viele.slice().sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase(), 'de'));
  const markiert = sortiert[sortiert.length - 1];   // alphabetisch letzter -> hinter der Grenze
  const abgeschnitten = sortiert[7];                // unmarkiert, ebenfalls hinter der Grenze
  const e8 = quizSuchVorschlaege([], viele, 'a', { aufBild: [markiert] });
  ck('E8 markierte Person ueber der Grenze bleibt sichtbar',
     e8.some(v => v.name === markiert && v.aufBild), true);
  ck('E8 unmarkierte ueber der Grenze bleiben abgeschnitten',
     e8.some(v => v.name === abgeschnitten), false);
  ck('E8 genau 8 Eintraege + 1 markierter', e8.length, 9);
}

// ---------------------------------------------------------------------------
// F) VERHALTEN im Stub-DOM: das echte Suchfeld tippen/klicken (Katalog, Marker,
//    neue Person, ehrlicher Lade-/Fehlerzustand) — ohne Browser.
console.log('\nF) Verhalten des Suchfelds (echter Code, Stub-DOM)');
async function AbschnittF() {
  const warte = (ms) => new Promise(r => setTimeout(r, ms));
  const fakeEl = (tag) => {
    const el = {
      tag: tag || 'div',
      children: [], style: {}, value: '', _innerHTML: '', _h: {},
      appendChild(c) { el.children.push(c); return c; },
      addEventListener(ev, fn) { (el._h[ev] = el._h[ev] || []).push(fn); },
      fire(ev, arg) { (el._h[ev] || []).forEach(f => f(arg || {})); },
      focus() {}, remove() {},
    };
    Object.defineProperty(el, 'innerHTML', {
      get() { return el._innerHTML; },
      set(v) { el._innerHTML = v; if (v === '') el.children.length = 0; },
    });
    return el;
  };
  const textOf = (el) => (el.children || []).map(c => c.textContent).join(' | ');
  const dekl = (re, name) => {
    const m = src.match(re);
    if (!m) { console.log('  FAIL Deklaration in app.js fehlt: ' + name); fails++; return ''; }
    return m[0] + '\n';
  };

  global.document = { createElement: (t) => fakeEl(t) };
  // Echter Code aus app.js: Zustand + Katalog-Lader + Suche (gleicher eval-Scope).
  eval('const API_BASE = "";\n'
    + dekl(/let _quizKatalogNamen = null;[^\n]*/, '_quizKatalogNamen')
    + dekl(/let _quizKatalogZeit = 0;[^\n]*/, '_quizKatalogZeit')
    + dekl(/let _quizKatalogFehler = '';[^\n]*/, '_quizKatalogFehler')
    + dekl(/const QUIZ_KATALOG_TTL_MS = 60 \* 1000;[^\n]*/, 'QUIZ_KATALOG_TTL_MS')
    + extractFn('quizKatalogVerwerfen') + '\n'
    + extractFn('quizKatalogNamen') + '\n'
    + extractFn('quizKatalogFehlerText') + '\n'
    + ('async ' + extractFn('ladeQuizKatalogNamen')) + '\n'   // async-Funktion: Keyword mitnehmen
    + extractFn('quizSuchVorschlaege') + '\n'
    + extractFn('baueSuchMitVorschlaegen') + '\n');

  global.fetch = async () => ({
    json: async () => ({ personen: [{ name: 'Anna' }, { name: 'Bea' }, { name: 'David' }] }),
  });
  quizKatalogVerwerfen();
  const gewaehlt = [], neuWeg = [];
  const w = baueSuchMitVorschlaegen(['Zoe'], [], (n) => gewaehlt.push(n),
    { aufBild: ['Anna'], bestaetigt: ['Anna'], onNeu: (n) => neuWeg.push(n) });
  const inp = w.children[0], status = w.children[1], dd = w.children[2];

  // F1: ehrlicher Ladehinweis, solange der Katalog laedt
  ck('F1 Ladehinweis sichtbar waehrend des Ladens',
     status.textContent.indexOf('⏳ Personenkatalog lädt') === 0 && status.style.display === '', true);
  await warte(40);
  ck('F2 nach dem Laden kein Ladehinweis mehr', status.style.display, 'none');
  ck('F2 alle 3 Katalog-Namen im Suchfeld-Cache', quizKatalogNamen().length, 3);

  // F3: Tippen 'da' -> neue-Person-Option + Katalog-Treffer David
  inp.value = 'da'; inp.fire('input');
  ck('F3 zwei Eintraege (neue Person + David)', dd.children.length, 2);
  ck('F3 neue-Person-Option steht oben', textOf(dd.children[0]).indexOf('➕ da als neue Person anlegen'), 0);
  ck('F3 Katalog-Treffer David auftaucht (nicht nur Backend-Kandidaten)',
     textOf(dd.children[1]).indexOf('David') !== -1, true);

  // F4: Tippen 'an' -> Anna ist KANDIDAT-unabhaengig da und MARKIERT (nicht ausgeblendet)
  inp.value = 'an'; inp.fire('input');
  const annaEintrag = dd.children.filter(c => textOf(c).indexOf('Anna') !== -1)[0];
  ck('F4 zugeordnete Person bleibt als Option waehlbar', !!annaEintrag, true);
  ck('F4 Marker "schon auf diesem Bild"', textOf(annaEintrag).indexOf('✓ schon auf diesem Bild') !== -1, true);
  ck('F4 Marker "schon bestaetigt"', textOf(annaEintrag).indexOf('✓ schon bestätigt') !== -1, true);

  // F5: Klick auf "als neue Person anlegen" -> BESTEHENDER Weg (onNeu)
  dd.children[0].fire('pointerup', { stopPropagation() {} });
  ck('F5 Klick oeffnet den bestehenden Weg mit vorbelegtem Namen', neuWeg.join(','), 'an');
  ck('F5 Eingabefeld geleert, Liste geschlossen', inp.value === '' && dd.style.display, 'none');

  // F6: Klick auf eine Katalog-Person -> bestehender Antwortweg
  inp.value = 'dav'; inp.fire('input');
  const dav = dd.children.filter(c => textOf(c).indexOf('David') !== -1)[0];
  dav.fire('pointerup', { stopPropagation() {} });
  ck('F6 Katalog-Person ist waehlbar (Antwortweg gerufen)', gewaehlt.join(','), 'David');

  // F6b: Enter mit exakt bekannter Person -> Antwortweg; unbekannter Name -> neue Person
  inp.value = 'david'; inp.fire('keydown', { key: 'Enter' });
  ck('F6b Enter mit vorhandenem Namen waehlt die Person', gewaehlt.join(','), 'David,david');
  inp.value = 'Neuling'; inp.fire('keydown', { key: 'Enter' });
  ck('F6b Enter mit neuem Namen oeffnet den neue-Person-Weg', neuWeg.join(','), 'an,Neuling');

  // F7: Fehlerfall -> sichtbare Meldung, aber Vorschlaege bleiben nutzbar
  global.fetch = async () => { throw new Error('offline'); };
  quizKatalogVerwerfen();
  const w2 = baueSuchMitVorschlaegen(['Zoe'], [], () => {}, {});
  const inp2 = w2.children[0], status2 = w2.children[1], dd2 = w2.children[2];
  await warte(40);
  ck('F7 Ladefehler wird sichtbar gemeldet (nicht still leer)',
     status2.textContent.indexOf('⚠️ Personenkatalog nicht ladbar') === 0
     && status2.textContent.indexOf('nur Vorschläge') !== -1, true);
  inp2.value = 'zo'; inp2.fire('input');
  ck('F7 Kandidaten bleiben trotzdem waehlbar',
     dd2.children.some(c => textOf(c).indexOf('Zoe') !== -1), true);
}

(async () => {
  await AbschnittF();
  console.log('\n  --> Fehler: ' + fails);
  process.exit(fails ? 1 : 0);
})();
