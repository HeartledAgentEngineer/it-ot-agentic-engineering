// QUELLTEXT-NACHWEISE fuer den Fix "einzelne Referenz loeschen" (2026-09-20).
//
// Befund Sebastian: "Bei den abgespeicherten Ausschnittbildern waren wieder
// welche ohne Bild. Und: ich wollte EINS löschen, musste aber ALLE löschen."
//
// Ursache (belegt im Backend-Test test_gesichter_ref_loeschen.py): die
// Loesch-Antwort des Servers wurde im Referenz-Vollbild VERWORFEN und der
// Erfolg ("✓ gelöscht") vorgetaeuscht — ein Fehlschlag blieb unsichtbar, also
// blieb nur "Alle löschen".
//
// Dieser Test prueft am ECHTEN app.js:
//   A) Ein Fehlschlag wird SICHTBAR gemeldet (nie stillschweigend "✓ gelöscht")
//   B) Es wird NIE eine leere/undefined ID gesendet
//   C) Referenzen ohne Ausschnittbild sind gekennzeichnet (bleiben loeschbar)
//   D) Auch "Alle Referenzen löschen" wertet die Antworten aus
//
// Aufruf: node tests/test_ref_loeschen_ui.js app.js
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
const hatNicht = (name, text) => ck(name, src.includes(text), false);
const hatRe = (name, re) => ck(name, re.test(src), true);
const hatNichtRe = (name, re) => ck(name, re.test(src), false);
const inFn = (name, fn, text) => {
  const body = extractFn(fn);
  if (!body) { console.log('  FAIL ' + name + ': Funktion ' + fn + ' nicht gefunden'); fails++; return; }
  ck(name, body.includes(text), true);
};
const inFnNicht = (name, fn, text) => {
  const body = extractFn(fn);
  if (!body) { console.log('  FAIL ' + name + ': Funktion ' + fn + ' nicht gefunden'); fails++; return; }
  ck(name, body.includes(text), false);
};
const inFnRe = (name, fn, re) => {
  const body = extractFn(fn);
  if (!body) { console.log('  FAIL ' + name + ': Funktion ' + fn + ' nicht gefunden'); fails++; return; }
  ck(name, re.test(body), true);
};

console.log('\nA) Ein Fehlschlag wird SICHTBAR gemeldet (Vollbild-Referenzliste)');
{
  // Der Loesch-Knopf ist ein Inline-Handler in zeigeReferenzenVollbild.
  inFn('es gibt eine Status-Anzeige je Zeile', 'zeigeReferenzenVollbild', 'delStatus');
  inFn('Status wird an die Zeile gehaengt', 'zeigeReferenzenVollbild', 'z.appendChild(delStatus)');
  inFn('Fehlschlag wird als NICHT geloescht gemeldet', 'zeigeReferenzenVollbild',
       "delStatus.textContent = '⚠️ NICHT gelöscht: '");
  inFn('Erfolg erst NACH Pruefung der Antwort', 'zeigeReferenzenVollbild',
       'if (res.ok && d && d.ok) {');
  inFn('Serverantwort wird wirklich gelesen', 'zeigeReferenzenVollbild', 'await res.json()');
  inFn('Fehlertext aus der Antwort (detail/fehler)', 'zeigeReferenzenVollbild',
       "d.detail || d.fehler");
  inFn('HTTP-Status als Fallback gemeldet', 'zeigeReferenzenVollbild', "'HTTP ' + res.status");
  inFn('Netzwerkfehler wird gemeldet', 'zeigeReferenzenVollbild', 'Netzwerkfehler');
  inFn('Knopf bleibt aktiv, wenn nichts geloescht wurde', 'zeigeReferenzenVollbild',
       'del.disabled = false;');
  // KERN-NEGATIVPROBE: kein "fetch(...DELETE) gefolgt von Erfolgs-Fake".
  hatNichtRe('kein Fake-Erfolg direkt nach blindem fetch',
             /await fetch\([^\n]*DELETE[^\n]*\);\s*\n\s*z\.style\.opacity/);
}

console.log('\nB) Es wird NIE eine leere/undefined ID gesendet');
{
  inFn('ID wird als String geprueft (kein undefined)', 'zeigeReferenzenVollbild',
       "const rid = (r && r.ref_id != null) ? String(r.ref_id).trim() : '';");
  inFn('leere ID bricht ab (mit Hinweis)', 'zeigeReferenzenVollbild', 'if (!rid) {');
  inFn('Hinweis nennt die fehlende ID', 'zeigeReferenzenVollbild', 'Referenz hat keine ID');
  inFn('URL nutzt die gepruefte ID', 'zeigeReferenzenVollbild', 'encodeURIComponent(rid)');
  inFnNicht('URL nutzt NICHT das rohe r.ref_id', 'zeigeReferenzenVollbild',
            'encodeURIComponent(r.ref_id)');
  // Gleiches Muster in referenzLoeschen (Chat-Blase).
  inFn('referenzLoeschen prueft die ID', 'referenzLoeschen',
       "const rid = (refId != null) ? String(refId).trim() : '';");
  inFn('referenzLoeschen bricht bei leerer ID ab', 'referenzLoeschen', 'if (!rid) {');
  inFn('referenzLoeschen nutzt die gepruefte ID', 'referenzLoeschen', 'encodeURIComponent(rid)');
  inFn('referenzLoeschen meldet Fehlschlag ehrlich', 'referenzLoeschen',
       "alert('⚠️ NICHT gelöscht: '");
  inFn('referenzLoeschen prueft die Antwort', 'referenzLoeschen', 'if (r.ok && d && d.ok)');
  // Der alte Confirm-Bug darf nicht zurueckkommen.
  hatNicht('kein alter Confirm-Bug (!window.confirm && ...)', 'if (!window.confirm && typeof confirm');
}

console.log('\nC) Referenzen OHNE Ausschnittbild sind gekennzeichnet');
{
  inFn('Badge fuer Zeilen ohne Bild', 'zeigeReferenzenVollbild', "ohneBild.textContent = '⚠️ ohne Bild'");
  inFn('Erkennung ueber fehlendes <img>', 'zeigeReferenzenVollbild', "if (!z.querySelector('img')) {");
  inFn('Zeile bleibt sichtbar (kein Zeilen-Abbruch)', 'zeigeReferenzenVollbild', "z.querySelector('img')");
  hat('Platzhalter "kein Bild gespeichert" bleibt', "(kein Bild gespeichert)");
  hat('Platzhalter "Bild fehlt" bleibt', "(Bild fehlt)");
  // Die alte blinde Zeile, die die Loesch-Antwort verworfen hat, ist weg.
  hatNicht('alter blinder Loesch-Button entfernt',
           "await fetch(`${API_BASE}/api/gesichter/referenzen/${encodeURIComponent(name)}/${encodeURIComponent(r.ref_id)}`, { method: 'DELETE' });");
}

console.log('\nD) "Alle Referenzen löschen" wertet die Antworten aus');
{
  inFn('Erfolge werden gezaehlt', 'zeigeReferenzenVollbild', 'okCount++');
  inFn('Fehlschlaege werden gezaehlt', 'zeigeReferenzenVollbild', 'fehlerCount++');
  inFn('Antwort wird geprueft (resp.ok)', 'zeigeReferenzenVollbild', 'if (resp.ok) okCount++');
  inFn('keine leere ID im Sammel-Lauf', 'zeigeReferenzenVollbild',
       "const rid = (r && r.ref_id != null) ? String(r.ref_id).trim() : '';");
  inFn('Sammelmeldung nennt NICHT geloeschte', 'zeigeReferenzenVollbild',
       'NICHT gelöscht.');
  inFnNicht('keine pauschale Erfolgsmeldung ohne Pruefung', 'zeigeReferenzenVollbild',
            "fertig.textContent = '✅ Alle Referenzen von ' + name + ' gelöscht.';");
}

console.log('\n  --> Fehler: ' + fails);
process.exit(fails ? 1 : 0);
