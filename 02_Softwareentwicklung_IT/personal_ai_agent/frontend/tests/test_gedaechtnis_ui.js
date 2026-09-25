// QUELLTEXT-NACHWEISE fuer die Erinnerungs-Anzeige (2026-09-25).
//
// Befund Sebastian: „Ich muesste das ganze Gedaechtniskonzept noch mal
// ueberdenken, weil die Erinnerungen sind auch ziemlich schlecht. Ich habe
// einfach nur nix fuer Erinnerungen."
//
// Belegt im Backend: Der Agent lernt mit (GET /api/health des Handys meldete
// memory_count=175), die Erinnerungen gehen auch in den Prompt - aber die
// Oberflaeche rief /api/memory NIE auf. Sichtbar war nur die Zahl im Fuss
// („N Erinnerungen"). Kein Eintrag zu sehen, keiner zu loeschen.
//
// Dieser Test prueft am ECHTEN app.js + index.html:
//   A) Blatt und Knopf existieren ueberhaupt
//   B) Die Liste kommt vom echten Endpunkt (nicht aus Attrappen)
//   C) Leerer Bestand wird erklaert statt als leeres Blatt gezeigt
//   D) Ein Lade-Fehlschlag wird SICHTBAR gemeldet
//   E) Einzel-Loeschen prueft die Antwort und meldet Fehlschlaege sichtbar
//   F) Kein „Alle loeschen" (nicht ruecknehmbarer Rundumschlag)
//   G) Erinnerungstexte werden escaped (kein HTML aus Nutzerdaten)
//   H) Oeffnen/Schliessen ist verdrahtet (Knopf, x, Hintergrund, Escape)
//   I) Cache-Bump steht in index.html
//
// Aufruf: node tests/test_gedaechtnis_ui.js app.js
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

let fails = 0;
const ck = (name, ist, soll) => {
  if (ist === soll) console.log('  OK   ' + name);
  else { console.log('  FAIL ' + name + ': erwartet ' + soll + ', war ' + ist); fails++; }
};
const hatHtml = (name, text) => ck(name, html.includes(text), true);
const hat = (name, text) => ck(name, src.includes(text), true);
const hatNicht = (name, text) => ck(name, src.includes(text), false);
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

console.log('\nA) Blatt und Knopf existieren (index.html)');
{
  hatHtml('Erinnerungs-Blatt vorhanden', 'id="memory-sheet"');
  hatHtml('Liste vorhanden', 'id="memory-list"');
  hatHtml('Hinweiszeile vorhanden', 'id="memory-hint"');
  hatHtml('Schliessen-Knopf vorhanden', 'id="memory-close"');
  hatHtml('Knopf im Fuss oeffnet es', 'id="gedaechtnis-btn"');
  // Der Fuss-Text war vorher ein <span> ohne jede Funktion.
  ck('Fuss-Text ist jetzt ein Knopf', /<button id="gedaechtnis-btn"[^>]*>Gedächtnis aktiv<\/button>/.test(html), true);
  hat('dom-Referenzen im Skript', "memorySheet: document.getElementById('memory-sheet')");
}

console.log('\nB) Die Liste kommt vom echten Endpunkt');
{
  inFn('Abruf ueber GET /api/memory', 'zeichneErinnerungen', '`${API_BASE}/api/memory?limit=200`');
  inFnNicht('keine erfundenen Eintraege im Code', 'zeichneErinnerungen', 'Beispiel-Erinnerung');
  inFn('Antwort wird ausgewertet (res.ok)', 'zeichneErinnerungen', 'if (!res.ok) throw new Error');
  inFn('Eintraege werden gezeichnet', 'zeichneErinnerungen', 'dom.memoryList.appendChild(zeile)');
  inFn('neueste zuerst', 'zeichneErinnerungen', 'liste.slice().reverse()');
  // Die Liste ist gedeckelt (limit=200); die Gesamtzahl kommt aus /count,
  // sonst behauptet die Anzeige bei großem Bestand eine zu kleine Zahl.
  inFn('Gesamtzahl aus /api/memory/count', 'erinnerungenZahl', '`${API_BASE}/api/memory/count`');
  inFn('Deckel wird ehrlich benannt', 'zeichneErinnerungen', 'hier die ${liste.length} jüngsten');
  inFn('Zaehler im Fuss wird mitgezogen', 'zeichneErinnerungen', 'updateFooterNote(gesamt !== null');
}

console.log('\nC) Leerer Bestand wird erklaert');
{
  inFn('Leerfall hat einen eigenen Text', 'zeichneErinnerungen', 'Noch keine Erinnerungen gespeichert.');
  inFn('er erklaert, wie Eintraege entstehen', 'zeichneErinnerungen', 'wenn du im Chat etwas über dich erzählst');
}

console.log('\nD) Lade-Fehlschlag wird sichtbar');
{
  inFn('Fehlschlag landet in der Hinweiszeile', 'zeichneErinnerungen',
       "dom.memoryHint.textContent = 'Erinnerungen nicht abrufbar");
  inFnNicht('kein stilles Verschlucken', 'zeichneErinnerungen', 'catch (err) {}');
}

console.log('\nE) Einzel-Loeschen prueft die Antwort');
{
  inFn('DELETE auf den Einzel-Eintrag', 'loescheErinnerung',
       '`${API_BASE}/api/memory/${encodeURIComponent(id)}`');
  inFn('Methode DELETE gesetzt', 'loescheErinnerung', "{ method: 'DELETE' }");
  inFn('Antwort wird geprueft', 'loescheErinnerung', 'if (!res.ok) throw new Error');
  inFn('Fehlschlag wird sichtbar gemeldet', 'loescheErinnerung', 'Entfernen fehlgeschlagen');
  inFn('Fehlschlag sagt, dass der Eintrag bleibt', 'loescheErinnerung', 'der Eintrag ist noch da');
  inFn('nie eine leere Kennung senden', 'loescheErinnerung', 'if (!id) return;');
  inFn('nachfragen vor dem Loeschen', 'loescheErinnerung', 'window.confirm');
  inFn('Liste wird danach neu gezeichnet', 'loescheErinnerung', 'await zeichneErinnerungen()');
}

console.log('\nF) Kein "Alle loeschen" (nicht ruecknehmbar)');
{
  hatNicht('kein Aufruf von /api/memory/clear', '/api/memory/clear');
  inFnNicht('kein Sammel-Loeschen in der Funktion', 'loescheErinnerung', 'forEach');
}

console.log('\nG) Erinnerungstexte werden escaped');
{
  inFn('Text escaped', 'zeichneErinnerungen', 'text.innerHTML = escapeHtml(m.content');
  inFn('Meta escaped', 'zeichneErinnerungen', 'kopf.innerHTML = escapeHtml(teile.join');
  // Gegenprobe: ungefiltertes Einsetzen waere die Luecke.
  inFnNicht('kein rohes m.content ins HTML', 'zeichneErinnerungen', 'innerHTML = m.content');
}

console.log('\nH) Oeffnen/Schliessen ist verdrahtet');
{
  hat('Knopf oeffnet das Blatt', "dom.gedaechtnisBtn.addEventListener('click', oeffneGedaechtnisBlatt)");
  hat('x schliesst das Blatt', "dom.memoryClose.addEventListener('click', schliesseGedaechtnisBlatt)");
  hat('Hintergrund schliesst das Blatt', 'if (e.target === dom.memorySheet) schliesseGedaechtnisBlatt()');
  hat('Escape schliesst das Blatt', "dom.memorySheet && !dom.memorySheet.hidden) schliesseGedaechtnisBlatt()");
  inFn('Blatt wird beim Oeffnen gefuellt', 'oeffneGedaechtnisBlatt', 'zeichneErinnerungen()');
  inFn('Schliessen versteckt es', 'schliesseGedaechtnisBlatt', 'dom.memorySheet.hidden = true');
}

console.log('\nI) Cache-Bump in index.html');
{
  // Bewusst versions-UNSPEZIFISCH: Der Test darf nicht brechen, wenn ein
  // anderer Fix denselben Cache-Parameter weiterdreht (A -> B -> C ...).
  // Geprueft wird: der ALTE Parameter ist weg, und es steht ueberhaupt einer
  // dran (Muster ?v=JJJJMMTT<Buchstabe>).
  const altesApp = /app\.js\?v=20260920B/.test(html);
  const altesCss = /style\.css\?v=20260920B/.test(html);
  ck('app.js traegt neuen Cache-Parameter',
     /app\.js\?v=\d{8}[A-Z]/.test(html) && !altesApp, true);
  ck('style.css traegt neuen Cache-Parameter',
     /style\.css\?v=\d{8}[A-Z]/.test(html) && !altesCss, true);
  ck('alter app.js-Parameter ist weg', altesApp, false);
}

console.log('\n  --> Fehler: ' + fails);
process.exit(fails ? 1 : 0);
