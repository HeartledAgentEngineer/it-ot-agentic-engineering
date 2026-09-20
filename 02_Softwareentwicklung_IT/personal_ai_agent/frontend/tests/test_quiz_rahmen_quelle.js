// QUELLTEXT-NACHWEISE fuer den Quiz-/Rahmen-Umbau (Fix 2026-09-15).
// Prueft am ECHTEN app.js, dass die vereinbarten Regeln wirklich im Code
// stehen — inkl. der Stellen, die im Live-Test am Handy wehgetan haben:
//   * Pull-to-Refresh darf den Browser nicht mehr ausloesen
//   * Rahmen werden normalisiert (0..1) geankert, gedreht und geklemmt
//   * "Speichern" fragt bereits Bestaetigtes nicht erneut ab
//   * Referenz-Nachbearbeitung laeuft ueber die stabile ref_id zurueck
//   Aufruf: node tests/test_quiz_rahmen_quelle.js app.js
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

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

let fails = 0;
const ck = (name, ist, soll) => {
  if (ist === soll) console.log('  OK   ' + name);
  else { console.log('  FAIL ' + name + ': erwartet ' + soll + ', war ' + ist); fails++; }
};
const hat = (name, text) => ck(name, src.includes(text), true);
const hatRe = (name, re) => ck(name, re.test(src), true);
const inFn = (name, fn, text) => {
  const body = extractFn(fn);
  if (!body) { console.log('  FAIL ' + name + ': Funktion ' + fn + ' nicht gefunden'); fails++; return; }
  ck(name, body.includes(text), true);
};
const inFnRe = (name, fn, re) => {
  const body = extractFn(fn);
  if (!body) { console.log('  FAIL ' + name + ': Funktion ' + fn + ' nicht gefunden'); fails++; return; }
  ck(name, re.test(body), true);
};

console.log('\nA) Vollbild-Editor loest den Browser NICHT aus (Pull-to-Refresh weg)');
{
  inFn('touch-action:none am Editor-Overlay', 'zeigeBildVollbild', 'overscroll-behavior:none;touch-action:none');
  inFn('overscroll-behavior:contain am Container', 'zeigeBildVollbild', 'touch-action:none;overscroll-behavior:contain');
  inFn('bildBox ohne Pan/Zoom des Browsers', 'zeigeBildVollbild', "line-height:0;touch-action:none");
  inFn('Bild selbst touch-action:none', 'zeigeBildVollbild', 'object-fit:contain;touch-action:none');
  inFn('preventDefault in touchmove (passive:false)', 'zeigeBildVollbild',
       "ov.addEventListener('touchmove', _keineBrowserGeste, { passive: false })");
  inFn('preventDefault in pointermove (passive:false)', 'zeigeBildVollbild',
       "ov.addEventListener('pointermove', _keineBrowserGeste, { passive: false })");
  inFn('preventDefault in gesturestart', 'zeigeBildVollbild', "'gesturestart'");
  inFn('preventDefault wird wirklich gerufen', 'zeigeBildVollbild', 'ev.preventDefault()');
  inFn('Ziehen ruft preventDefault', 'zeigeBildVollbild', 'mev.preventDefault()');
  inFn('setPointerCapture fuer die Maus', 'zeigeBildVollbild', 'setPointerCapture');
  inFn('releasePointerCapture beim Loslassen', 'zeigeBildVollbild', 'releasePointerCapture');
}

console.log('\nB) Normalisierte Ankerung (0..1) ueberall');
{
  inFn('gelber Rahmen nutzt bbox_norm zuerst', 'markiereGesichtImBild', "g.bbox_norm && g.bbox_norm.length >= 4");
  inFn('gelber Rahmen rechnet aus Pixeln nur als Fallback', 'markiereGesichtImBild', 'bboxNormVonPixeln(b, iw, ih)');
  inFnRe('gelber Rahmen nutzt bboxAnzeigeRahmen (gedeckelt)', 'markiereGesichtImBild', /bboxAnzeigeRahmen\(norm\)/);
  inFn('Editor fuehrt bbox_norm_live als Wahrheit', 'zeigeBildVollbild', 'bbox_norm_live');
  inFn('Editor seedet aus bbox_norm', 'zeigeBildVollbild', 'bboxNormClampen(g.bbox_norm)');
  inFn('Pixel-Reste werden nach dem Laden umgerechnet', 'zeigeBildVollbild', 'bboxNormClampen(bboxNormVonPixeln(pr, iw, ih))');
  inFn('anderes Bild -> keine alten Rahmen', 'zeigeBildVollbild', 'const gleichesBild = (_quizEditor.src === src)');
  inFn('Zeichnen speichert normalisiert', 'zeigeEinzeichnen', 'bboxNormVonPixeln([orig.x, orig.y, orig.w, orig.h], iwN, ihN)');
  inFn('Speichern rechnet norm -> Pixel', 'speichereEditorRahmen', 'bboxPixelVonNorm(norm, iw, ih)');
  inFn('Speichern sendet bbox_norm mit', 'speichereEditorRahmen', 'bbox_norm: norm');
  inFn('Titel-Anzeige im Vollbild nutzt bbox_norm', 'zeigeReferenzBearbeiten', 'ref.bbox_norm');
}

console.log('\nC) Ziehen/Groesse/Drehen konsistent (clampen, Rueckrichtung)');
{
  inFn('Verschieben nutzt bboxVerschieben', 'zeigeBildVollbild', 'bboxVerschieben(px, dOrg[0], dOrg[1], iw, ih)');
  inFn('Groesse nutzt bboxSkalieren', 'zeigeBildVollbild', 'bboxSkalieren(px, griffUmrechnen(');
  inFnRe('Verschieben wird geklemmt (bboxClampen via bboxVerschieben)', 'bboxVerschieben', /bboxClampen\(/);
  inFnRe('Groesse wird geklemmt', 'bboxSkalieren', /bboxClampen\(/);
  inFn('Groesse hat Mindestkante 8 px', 'bboxSkalieren', 'w < 8');
  inFnRe('Zeichnen dreht den Rahmen mit (bboxNormRotieren)', 'zeigeBildVollbild', /bboxNormRotieren\(norm, iw, ih, dreh\)/);
  inFn('Griffe drehen mit dem Bild', 'zeigeBildVollbild', 'griffUmrechnen');
  inFn('Rueckrichtung beim Ziehen (bboxDeltaDrehen)', 'zeigeBildVollbild', 'bboxDeltaDrehen(dxAnz, dyAnz, dreh)');
  inFn('Werkzeug: Drehen-Knopf', 'zeigeBildVollbild', "'⟳'");
  inFn('Werkzeug: Undo-Knopf', 'zeigeBildVollbild', 'undoLetzte');
  inFn('Werkzeug: Speichern-Knopf', 'zeigeBildVollbild', 'speichereEditorRahmen(sel, iw, ih, speichernBtn)');
  inFnRe('Griffe sind 16 px (nicht riesig)', 'zeigeBildVollbild', /width:16px;height:16px/);
  ck('kein 28%-Aufschlag mehr (alte Rieskaesten)', src.includes('bh * 0.28'), false);
  ck('kein 0.28-Aufschlag mehr', src.includes('0.28'), false);
}

console.log('\nD) Speichern fragt bereits Bestaetigtes NICHT erneut ab');
{
  hat('lokale Bestaetigungs-Markierung existiert', 'let _quizBestaetigt = {}');
  hatRe('merkeBestaetigt-Funktion', /function merkeBestaetigt\(/);
  hatRe('istBestaetigtLokal-Funktion', /function istBestaetigtLokal\(/);
  inFn('Gruppenquiz liest die backend-Flags je Gesicht', 'starteGruppenQuiz', 'g.bestaetigt');
  inFn('Gruppenquiz liest lokale Bestaetigung', 'starteGruppenQuiz', 'istBestaetigtLokal(pfad, reg)');
  inFnRe('Gruppenquiz ueberspringt bestaetigte Gesichter', 'starteGruppenQuiz', /ueberspringeBestaetigte\(\)/);
  inFn('ueberspringen geht weiter statt neu zu fragen', 'starteGruppenQuiz', 'markiereBildErledigt()');
  inFn('Antwort merkt die Region', 'starteGruppenQuiz', 'merkeBestaetigt(pfad, reg, person)');
  inFn('Einzelantwort merkt die Region', 'quizBeantworten', 'merkeBestaetigt(pfad, bboxRegionSchluessel(normE), person)');
  inFn('Speichern merkt die Region', 'speichereEditorRahmen', 'merkeBestaetigt(pPfad, region, person)');
  inFn('Einzelgesicht wird nach Speichern abgeschlossen', 'speichereEditorRahmen', 'macheQuizFertig(_letzteQuizKarte, person, true');
  inFn('Zeichnen merkt die Region', 'zeigeEinzeichnen', 'bboxRegionSchluessel(normNeu)');
  hatRe('Regions-Schluessel im 1%-Raster', /Math\.round\(Number\(v\) \* 100\) \/ 100/);
}

console.log('\nE) Referenz-Nachbearbeitung (Katalog -> Referenz -> Bild -> speichern)');
{
  hatRe('zeigeReferenzBearbeiten existiert', /function zeigeReferenzBearbeiten\(/);
  inFn('Referenz-Kontext wird gesetzt', 'zeigeReferenzBearbeiten', 'refKontext: { name: name, ref_id: ref.ref_id');
  inFn('Person bleibt dieselbe (kein neuer Name)', 'zeigeReferenzBearbeiten', '_aktuelleQuizPerson = name');
  inFn('Rahmen kommt vorhanden mit', 'zeigeReferenzBearbeiten', 'bbox_norm: norm');
  inFn('Speichern geht an die Referenz-Route', 'speichereEditorRahmen',
       '/api/gesichter/referenzen/${encodeURIComponent(refKontext.name)}/${encodeURIComponent(refKontext.ref_id)}/bbox');
  inFn('mit neuem Embedding aus dem Ausschnitt', 'speichereEditorRahmen', 'embedding_erneuern: true');
  inFn('Referenz-Liste wird danach neu geladen', 'speichereEditorRahmen', 'refKontext.onGespeichert');
  inFn('Referenz-Ansicht laedt neu', 'zeigeReferenzenVollbild', 'ladeReferenzen();');
  inFn('Ausschnitt-Tipp oeffnet die Nachbearbeitung', 'zeigeReferenzenVollbild', 'zeigeReferenzBearbeiten(name, r, dd.data_url');
  inFn('Katalog verweist auf das Rahmen-Anpassen', 'bauePersonKarte', 'Referenzen ansehen / Rahmen anpassen');
  inFn('Editor kennt den Referenz-Kontext', 'zeigeBildVollbild', 'optionen.refKontext');
  inFn('Referenz-Editor startet ohne Alt-Rahmen', 'zeigeBildVollbild', 'refKontext: optionen.refKontext,');
  inFn('Kein "Naechstes Bild" bei der Referenz', 'zeigeBildVollbild', '&& !_quizEditor.refKontext');
  inFn('ehrlicher Hinweis ohne Person/Ziel', 'speichereEditorRahmen', 'erst Ja/Person wählen');
}

console.log('\nF) Abbrechen-Knopf (Spec-Schritt 9)');
{
  ck('Abbrechen existiert zweimal (Einzelbild + Gruppenbild)',
     (src.match(/✖ Abbrechen/g) || []).length, 2);
  inFn('Formular der Einzelkarte hat Abbrechen', 'zeigeQuizKarte', "macheQuizButton('✖ Abbrechen'");
  inFn('Gruppen-Formular hat Abbrechen', 'starteGruppenQuiz', "macheQuizButton('✖ Abbrechen'");
  inFn('Abbrechen legt nichts an (nur zuklappen)', 'starteGruppenQuiz', "form.style.display = 'none'");
}

console.log('\n  --> Fehler: ' + fails);
process.exit(fails ? 1 : 0);
