// SCHRITT A (16.10.2026) — "Rahmen speichern" darf nur behaupten, was wirklich passiert.
//
// Warum dieser Test am ECHTEN app.js-Quelltext prueft:
// Die Oberflaeche meldete bisher in BEIDEN Wegen, die einen Rahmen speichern, dass eine
// Referenz gespeichert sei — auch im Quiz-/Gruppenweg, der gar nicht sagen kann, ob ein
// neuer Vektor entstanden ist (Feld `vektor_erneuert` gibt es dort nicht; A0 fuehrte es
// nur im Referenz-Endpunkt ein). Genau das war Sebastians Befund "Rahmen verschieben,
// speichern, Position ist nicht im Datenbestand".
//
// Geprueft wird:
//   * der GESICHTER-Weg (Referenz-Endpunkt) behauptet eine Referenz NUR im Zweig
//     `if (d.vektor_erneuert)` und nennt sonst den ehrlichen Grund (`d.vektor_grund`)
//   * der GRUPPEN-/QUIZ-Weg behauptet KEINE Referenz mehr
//   * Gegenprobe: dieselben Pruefungen weisen die ALTE Fassung zurueck (sonst waere der
//     Test gruen, egal was im Code steht)
//   * Cache-Bump: index.html laedt app.js nicht mit einem alten ?v= (Muster + Mindestwert)
//
// Aufruf: node tests/test_quiz_rahmen_referenz_ehrlich.js app.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2], 'utf8');
const htmlPfad = path.join(path.dirname(process.argv[2]), 'index.html');
const html = fs.existsSync(htmlPfad) ? fs.readFileSync(htmlPfad, 'utf8') : '';

function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) return null;
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

// Die beiden ECHTEN Zeichenketten (Auflage 8 des Plans: nicht die erfundene Wendung
// "als Referenz gesichert" zitieren, sondern den Code lesen).
const WEG_A_BEHAUPTUNG = "'✓ Rahmen in der Referenz von '";
const WEG_A_ZUSTAND = 'if (d.vektor_erneuert)';
const WEG_A_GRUND = 'd.vektor_grund';
const WEG_B_ALT = '— Zuordnung gespeichert; ob ein neuer Vektor entstand, meldet dieser Weg nicht.';
// A3 (16.10.2026): der Quiz-Weg meldet jetzt selbst, OB eine Referenz entstand und
// WOZU die Koordinaten gehoeren. Behauptet wird sie nur beim GESENDETEN Rahmen.
const WEG_B_ZUSTAND = "d.referenz_geschrieben && d.rahmen_gespeichert === 'gesendet'";
const WEG_B_BEHAUPTUNG = 'der verschobene Rahmen liegt als Referenz im Datenbestand.';
const WEG_B_RUECKFALL = 'else if (d.referenz_geschrieben)';
const WEG_B_KEINE = '— KEINE neue Referenz: ';
const WEG_B_ALT2 = '— Rahmen + Referenz gespeichert.';

let fails = 0;
const ck = (name, ist, soll) => {
  if (ist === soll) console.log('  OK   ' + name);
  else { console.log('  FAIL ' + name + ': erwartet ' + JSON.stringify(soll) + ', war ' + JSON.stringify(ist)); fails++; }
};

// ── Die Pruefungen als REINE Funktion, damit die Gegenprobe sie auf die alte
//    Fassung anwenden kann (dieselbe Logik, andere Eingabe).
function pruefeRahmenMeldungen(fnBody) {
  const fehler = [];
  if (fnBody === null) { fehler.push('Funktion speichereEditorRahmen nicht gefunden'); return fehler; }

  if (fnBody.indexOf(WEG_A_BEHAUPTUNG) === -1) fehler.push('Gesichter-Weg: echte Behauptung fehlt');
  if (fnBody.indexOf(WEG_A_ZUSTAND) === -1) fehler.push('Gesichter-Weg: Zustand aus A0 (' + WEG_A_ZUSTAND + ') fehlt');
  if (fnBody.indexOf(WEG_A_GRUND) === -1) fehler.push('Gesichter-Weg: ehrlicher Grund fehlt');

  // Die Behauptung MUSS HINTER dem Zustand stehen (nur im true-Zweig).
  const posZustand = fnBody.indexOf(WEG_A_ZUSTAND);
  const posBehauptung = fnBody.indexOf(WEG_A_BEHAUPTUNG);
  if (!(posZustand >= 0 && posBehauptung > posZustand)) {
    fehler.push('Gesichter-Weg: Behauptung steht nicht hinter dem Zustand (koennte vorher behaupten)');
  }

  // Gruppen-/Quiz-Weg: keine Referenz-Behauptung ohne geschriebene Referenz.
  if (fnBody.indexOf(WEG_B_ALT2) !== -1) fehler.push('Gruppen-Weg behauptet weiter "Rahmen + Referenz gespeichert"');
  if (/Referenz gespeichert/.test(fnBody)) fehler.push('Gruppen-Weg: Zeichenkette "Referenz gespeichert" noch im Code');
  if (fnBody.indexOf(WEG_B_ALT) !== -1) fehler.push('Gruppen-Weg: A-Formulierung ("meldet dieser Weg nicht") noch im Code');
  if (fnBody.indexOf(WEG_B_ZUSTAND) === -1) fehler.push('Gruppen-Weg: Zustand aus A3 (' + WEG_B_ZUSTAND + ') fehlt');
  if (fnBody.indexOf(WEG_B_RUECKFALL) === -1) fehler.push('Gruppen-Weg: Rueckfall-Zweig (erkannter Rahmen) fehlt');
  if (fnBody.indexOf(WEG_B_KEINE) === -1) fehler.push('Gruppen-Weg: ehrlicher "KEINE neue Referenz"-Zweig fehlt');

  // Die Behauptung MUSS HINTER dem A3-Zustand stehen (nur im gesendeten Zweig).
  const posZustandB = fnBody.indexOf(WEG_B_ZUSTAND);
  const posBehauptungB = fnBody.indexOf(WEG_B_BEHAUPTUNG);
  if (!(posZustandB >= 0 && posBehauptungB > posZustandB)) {
    fehler.push('Gruppen-Weg: Behauptung steht nicht hinter dem A3-Zustand');
  }

  return fehler;
}

console.log('\nA) Gesichter-Weg: Referenz nur, wenn der Vektor wirklich neu ist');
{
  const body = extractFn('speichereEditorRahmen');
  ck('speichereEditorRahmen gefunden', body !== null, true);
  const fehler = pruefeRahmenMeldungen(body);
  ck('keine Beanstandung im echten Code', fehler.join(' | '), '');
}

console.log('\nB) Gruppen-/Quiz-Weg: ehrliche Meldung, kein Referenz-Versprechen');
{
  const body = extractFn('speichereEditorRahmen') || '';
  ck('die A-Formulierung ist weg', body.indexOf(WEG_B_ALT), -1);
  ck('der A3-Zustand ist da', body.indexOf(WEG_B_ZUSTAND) !== -1, true);
  ck('ehrlicher Zweig ohne Referenz ist da', body.indexOf(WEG_B_KEINE) !== -1, true);
}

console.log('\nC) Gegenprobe: die ALTE Fassung faellt durch dieselben Pruefungen');
{
  const alt = [
    'function speichereEditorRahmen(sel, iw, ih, btn) {',
    "    melde('✓ Rahmen in der Referenz von ' + refKontext.name + ' aktualisiert.', true);",
    "    melde('✓ ' + person + ' übernommen — Rahmen + Referenz gespeichert.', true);",
    '}',
  ].join('\n');
  const fehler = pruefeRahmenMeldungen(alt);
  ck('alte Fassung wird beanstandet (Zahl > 0)', fehler.length > 0, true);
  ck('alte Fassung: Zustand aus A0 fehlt', fehler.some((f) => f.indexOf('Zustand aus A0') !== -1), true);
  ck('alte Fassung: Zustand aus A3 fehlt', fehler.some((f) => f.indexOf('Zustand aus A3') !== -1), true);
  ck('alte Fassung: Referenz-Behauptung im Gruppen-Weg erkannt',
     fehler.some((f) => f.indexOf('behauptet weiter') !== -1 || f.indexOf('"Referenz gespeichert"') !== -1), true);
}

console.log('\nD) Cache-Bump: index.html darf app.js nicht mit altem ?v= laden');
{
  const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
  ck('?v= von app.js hat das Muster JJJJMMTT + Buchstabe', /^\d{8}[A-Z]$/.test(vApp), true);
  ck('?v= von app.js ist mindestens 20261016C (Bump fuer Schritt A)', vApp >= '20261016C', true);
  console.log('       (gefunden: ' + (vApp || 'nichts') + ')');
}

console.log('\n  --> Fehler: ' + fails);
process.exit(fails ? 1 : 0);
