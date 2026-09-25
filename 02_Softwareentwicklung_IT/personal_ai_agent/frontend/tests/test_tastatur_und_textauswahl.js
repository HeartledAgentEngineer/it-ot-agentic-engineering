// Tastatur + Textauswahl im Chat-Frontend (25.09.2026).
//
// Auftrag (Sebastian): Zwei Dinge am Handy reparieren.
//   1) TEXT AUSWÄHLBAR: Langer Druck auf eine Nachricht muss die NATIVE Auswahl
//      starten (Griffe, Lupe, Kopieren-Menue) – auch über mehrere Nachrichten
//      hinweg. Kurzer Tipp darf weiter die bestehenden Aktionen auslösen
//      (eingeklappte Gedanken-Blasen auf-/zuklappen).
//   2) TOPLEISTE BLEIBT SICHTBAR, WENN DIE TASTATUR AUFGEHT: nicht wegscrollen,
//      nicht ausblenden. Kopfzeile fest/sticky oben mit z-index, Scrollcontainer
//      ist die Nachrichtenliste, Höhe an der SICHTBAREN Fläche (visualViewport /
//      dvh) statt 100vh.
//
// Der Test liest app.js, style.css und index.html als TEXT und prüft Aussagen
// über den Quelltext (Stil der übrigen Tests in diesem Ordner). Jede Prüfung
// schlägt fehl, wenn die zugesicherte Regel wieder verschwindet.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_tastatur_und_textauswahl.js app.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || 'app.js';
const src = fs.readFileSync(pfadApp, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadApp));
let html = '';
let css = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}
try { css = fs.readFileSync(path.join(verzeichnis, 'style.css'), 'utf8'); } catch (_) {}

let fehler = 0;
let geprueft = 0;
function pruefe(name, bedingung, detail) {
  geprueft++;
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Alle CSS-Blöcke als { selektor, rumpf } (verschachtelte @media-Blöcke werden
 *  mitgenommen; für die hiesigen Regeln reicht der erste Selektor-Teil). */
function cssBloecke(text) {
  const bloecke = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    bloecke.push({ selektor: m[1].trim(), rumpf: m[2] });
  }
  return bloecke;
}
// Kommentare raus: Sonst würde z. B. ein Kommentar, der eine verbotene Regel
// ERWÄHNT („100vh gibt es hier bewusst nicht mehr"), als Regel durchgehen.
const cssRein = css.replace(/\/\*[\s\S]*?\*\//g, '');
const bloecke = cssBloecke(cssRein);

/** Der CSS-Block, dessen Selektor-Liste den Ausdruck enthält (erster Treffer). */
function regelMit(selektorRe) {
  return bloecke.find(b => selektorRe.test(b.selektor)) || { selektor: '', rumpf: '' };
}

/** Quelltext-Stelle ab `marke` bis zum ersten `\n});` – für Event-Handler. */
function stelle(marke) {
  const start = src.indexOf(marke);
  if (start === -1) return '';
  const rest = src.slice(start);
  const ende = rest.indexOf('\n});');
  return ende === -1 ? rest : rest.slice(0, ende + 3);
}

console.log('\n1) Textauswahl in Sprechblasen');
// Die Regel, die die Auswahl überhaupt erst erlaubt.
const auswahl = bloecke.find(b => /user-select:\s*text/.test(b.rumpf)
  && /\.message-content/.test(b.selektor)) || { selektor: '', rumpf: '' };
pruefe('es gibt eine Regel für Blaseninhalt mit user-select: text',
  /user-select:\s*text/.test(auswahl.rumpf) && /-webkit-user-select:\s*text/.test(auswahl.rumpf),
  'kein user-select: text für .message-content');
pruefe('dieselbe Regel erlaubt das native Menue (-webkit-touch-callout: default)',
  /-webkit-touch-callout:\s*default/.test(auswahl.rumpf),
  'touch-callout fehlt (ohne default blendet Android das Kopieren-Menue nicht ein)');
pruefe('die Auswahl gilt für den ganzen Verlauf, nicht nur je Blase',
  /#messages/.test(auswahl.selektor) && /#chat-container/.test(auswahl.selektor)
  && /\.gedanken-inhalt/.test(auswahl.selektor),
  'Selektor-Liste deckt den Verlauf nicht ab – Auswahl bräche an Nachbargrenzen ab');

// Kein Block darf die Auswahl im Verlauf wieder abschalten.
const ausschalter = bloecke.filter(b =>
  /user-select\s*:\s*none/.test(b.rumpf)
  && /(message-content|gedanken|#messages|#chat-container|\.message\b)/.test(b.selektor));
pruefe('keine user-select:none-Regel trifft Blaseninhalt',
  ausschalter.length === 0,
  'Blocker gefunden: ' + ausschalter.map(b => b.selektor).join(' | '));

// Auch inline (app.js) darf im Verlauf nichts blockiert werden. Erlaubt sind
// nur zwei Stellen, die NICHT der Chat-Verlauf sind: das Bild-Vollbild und das
// eigene Popup-Menue (dessen Beschriftungen sollen sich nicht markieren lassen).
const zeilen = src.split('\n');
const inlineNone = zeilen.map((z, i) => ({ z, nr: i + 1 }))
  .filter(o => /user-select\s*:\s*none|userSelect\s*=\s*'none'/.test(o.z));
const inlineBlocker = inlineNone.filter(o => {
  const umfeld = zeilen.slice(Math.max(0, o.nr - 7), o.nr).join('\n');
  return !/object-fit:contain/.test(o.z) && !/kontextMenue/.test(umfeld);
});
pruefe('app.js blockiert die Auswahl an keiner Stelle im Verlauf (Inline-Stile)',
  inlineBlocker.length === 0,
  inlineBlocker.map(o => 'Zeile ' + o.nr).join(', '));
pruefe('index.html setzt nirgends user-select:none',
  !/user-select/.test(html) || !/user-select\s*:\s*none/.test(html));
pruefe('kein selectstart-Blocker (würde die Auswahl abwürgen)',
  !/addEventListener\('selectstart'/.test(src) && !/onselectstart/.test(html));

console.log('\n2) Langer Druck startet die Auswahl (kein preventDefault auf Blasentext)');
const kontext = stelle("dom.messages.addEventListener('contextmenu'");
pruefe('der contextmenu-Handler existiert noch', kontext.length > 0);
pruefe('Blasentext wird im contextmenu-Handler erkannt und freigegeben',
  /closest\('\.message-content, \.gedanken-inhalt, \.gedanken-kurz'\)[\s\S]{0,160}?return;/.test(kontext),
  'kein Rückzug für Blasentext gefunden');
const posFrei = kontext.indexOf('return;   // bewusst KEIN e.preventDefault()');
const posPdv = kontext.indexOf('e.preventDefault()');
pruefe('kein preventDefault auf Blasentext (Rückzug steht VOR dem ersten preventDefault)',
  posFrei !== -1 && posPdv !== -1 && posFrei < posPdv,
  'preventDefault würde die native Auswahl verhindern');
pruefe('das eigene Menue wird dabei geschlossen (kein Rest über der Auswahl)',
  /closest\('\.message-content[\s\S]{0,160}?kontextMenueSchliessen\(\)/.test(kontext));
pruefe('das eigene Menue bleibt für die nicht auswählbaren Teile erhalten',
  /const text = kontextTextAusBlase\(blase\)/.test(kontext) && posPdv !== -1);

console.log('\n3) Kurzer Tipp löst weiter die bestehenden Aktionen aus');
const gedankeClick = stelle("div.addEventListener('click', () => {");
pruefe('Gedanken-Blase klappt per Tipp weiter auf und zu',
  /klappeGedankeAus\(div\)/.test(gedankeClick) && /klappeGedankeEin\(div\)/.test(gedankeClick));
pruefe('bei laufender Auswahl schaltet der Tipp die Blase NICHT um',
  /window\.getSelection/.test(gedankeClick) && /isCollapsed/.test(gedankeClick)
  && gedankeClick.indexOf('window.getSelection') < gedankeClick.indexOf("classList.contains('gedanken-eingeklappt')"));
const bildClick = stelle("dom.messages.addEventListener('click', (ev) => {");
pruefe('bei laufender Auswahl öffnet ein Tipp nicht das Bild-Vollbild',
  /window\.getSelection/.test(bildClick) && /isCollapsed/.test(bildClick)
  && bildClick.indexOf('window.getSelection') < bildClick.indexOf('zeigeBildVollbild'),
  'Bild-Vollbild würde die Auswahl zerstören');

console.log('\n4) Topleiste bleibt sichtbar (keine 100vh, sticky mit z-index)');
const huelle = regelMit(/#app/);
pruefe('kein 100vh für den Hauptcontainer',
  huelle.rumpf.length > 0 && !/100vh/.test(huelle.rumpf)
  && !/height:\s*100vh/.test(cssRein),
  'height: 100vh steht noch im Stylesheet');
pruefe('die Hülle richtet sich an der sichtbaren Höhe aus (vdh/visualViewport)',
  /var\(--vv-hoehe/.test(huelle.rumpf) && /100dvh/.test(huelle.rumpf));
pruefe('die Hülle sitzt fest am oberen Rand des sichtbaren Ausschnitts',
  /position:\s*fixed/.test(huelle.rumpf) && /var\(--vv-oben/.test(huelle.rumpf));
const kopf = regelMit(/#header/);
pruefe('Kopfzeile sticky/fixed mit z-index',
  /position:\s*(sticky|fixed)/.test(kopf.rumpf) && /top:\s*0/.test(kopf.rumpf)
  && parseInt((kopf.rumpf.match(/z-index:\s*(\d+)/) || [])[1] || '0', 10) > 120,
  'Kopfzeile ohne sticky/fixed/z-index');
pruefe('die Kopfzeile ist nicht abschaltbar (kein display:none/hidden Benz auf #header)',
  !/#header[^{]*\{[^}]*display:\s*none/.test(cssRein) && !/\bid="header"[^>]*hidden/.test(html));
pruefe('keine Höhen-Bedingung in @media (würde den Kopf bei kleiner Fläche abschalten)',
  !/@media[^{]*(height|vh|dvh)/.test(cssRein));
const liste = regelMit(/#chat-container/);
pruefe('Scrollcontainer ist die Nachrichtenliste (flex:1, overflow-y:auto, min-height:0)',
  /flex:\s*1/.test(liste.rumpf) && /overflow-y:\s*auto/.test(liste.rumpf)
  && /min-height:\s*0/.test(liste.rumpf),
  'ohne min-height:0 schrumpft die Liste nicht auf Tastatur-Höhe');
const eingabe = regelMit(/#input-area/);
pruefe('Eingabebereich schrumpft nicht und bleibt unter der Liste',
  /flex-shrink:\s*0/.test(eingabe.rumpf));
pruefe('index.html: #app = Kopfzeile, Verlauf, Eingabebereich (in dieser Reihenfolge)',
  html.indexOf('id="app"') !== -1
  && html.indexOf('id="header"') > html.indexOf('id="app"')
  && html.indexOf('id="chat-container"') > html.indexOf('id="header"')
  && html.indexOf('id="input-area"') > html.indexOf('id="chat-container"'));

console.log('\n5) Höhen-Brücke aus visualViewport (app.js)');
pruefe('app.js liest die sichtbare Höhe aus und setzt --vv-hoehe',
  /function huelleAnSichtbareHoehe\(\)/.test(src)
  && /vv\.height/.test(src)
  && /setProperty\('--vv-hoehe'/.test(src));
pruefe('app.js setzt auch die Verschiebung --vv-oben (Android schiebt die Seite hoch)',
  /setProperty\('--vv-oben',\s*Math\.round\(vv\.offsetTop/.test(src));
pruefe('es gibt die Rückfall-Kette ohne visualViewport (nur dvh, kein Absturz)',
  /if \(!vv\)/.test(src) && /removeProperty\('--vv-hoehe'\)/.test(src));
pruefe('Auslöser Tastatur/Tastatur zu: visualViewport resize+scroll, focusin/focusout',
  /visualViewport\.addEventListener\('resize'/.test(src)
  && /visualViewport\.addEventListener\('scroll'/.test(src)
  && /addEventListener\('focusin', huelleNachziehen\)/.test(src)
  && /addEventListener\('focusout'/.test(src));
pruefe('die Anpassung läuft gebündelt (ein Frame, kein Dauerlauf)',
  /requestAnimationFrame/.test(src) && /if \(_huelleFrame\) return/.test(src));
pruefe('beim Verkleinern bleibt man unten stehen (kein Sprung hinter die Tastatur)',
  /const warUnten = isAtBottom\(\)/.test(src) && /if \(warUnten\) scrollToBottom\(true\)/.test(src));
pruefe('index.html bittet den Browser zusätzlich um resizes-content',
  /interactive-widget=resizes-content/.test(html),
  'viewport-Meta ohne interactive-widget – nur visualViewport bleibt übrig');
pruefe('kein Auto-Polling für die Höhe (keine setInterval-Schleife)',
  !/setInterval\(huelleNachziehen/.test(src));

console.log('\n6) Keine neue Abhängigkeit, Handy, Cache-Bump');
pruefe('kein CDN/keine externe Quelle im Frontend',
  !/<script[^>]+src="https?:/.test(html) && !/<link[^>]+href="https?:/.test(html));
pruefe('kein Framework/Modul-Import in app.js',
  !/^\s*import\s/m.test(src) && !/require\(/.test(src));
pruefe('index.html lädt app.js mit ?v=20260925G',
  /app\.js\?v=20260925G/.test(html), 'Cache-Bump für app.js fehlt');
pruefe('index.html lädt style.css mit ?v=20260925F',
  /style\.css\?v=20260925F/.test(html), 'Cache-Bump für style.css fehlt');

console.log('\nERGEBNIS: ' + geprueft + ' Prüfungen, '
  + (fehler ? fehler + ' rot' : 'alle grün'));
process.exit(fehler ? 1 : 0);
