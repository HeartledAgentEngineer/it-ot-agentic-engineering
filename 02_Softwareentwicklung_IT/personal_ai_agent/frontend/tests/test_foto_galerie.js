// N13b — Bilder im Chat: Anzeige (Galerie + Diashow) — Prüfblatt.
//
// Auftrag: docs/auftrag-n13b-bilder-anzeige.md (Schritt N13b des Nachtlaufs,
// Vorgänger N13a liefert GET /api/fotos/bilder mit den Datei-Kennungen).
//
// Dieser Test prüft:
//   * die vier REINEN Funktionen werden wörtlich aus dem ECHTEN app.js
//     geschnitten und in Node ausgeführt — es wird nichts nachgebaut,
//   * die Regeln aus Teil A inklusive der Grenzfälle (leere Eingabe, null,
//     true als Kennung, ok:false, fehlende Felder, Klemmung von maxKacheln,
//     Umlauf der Diashow, Richtung 0/"x"),
//   * die Verdrahtung aus Teil B per Quelltext-Prüfung (Zweig in sendMessage,
//     data-foto-galerie/-kacheln/-gross, revokeObjectURL, keine Speicher-APIs,
//     sw.js legt für /api/ nichts in den Cache),
//   * den Cache-Bump in index.html.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_foto_galerie.js app.js
const fs = require('fs');
const path = require('path');

// Standardpfad robust auflösen: Der Aufruf funktioniert aus dem Ordner
// `frontend` (node tests/test_foto_galerie.js) UND aus dem Repo-Wurzelordner.
// Ein ausdrücklich übergebenes Argument hat Vorrang.
const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(pfadApp, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadApp));
let html = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}
let css = '';
try { css = fs.readFileSync(path.join(verzeichnis, 'style.css'), 'utf8'); } catch (_) {}
let sw = '';
try { sw = fs.readFileSync(path.join(verzeichnis, 'sw.js'), 'utf8'); } catch (_) {}

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

// Der Galerie-Bereich (Teil A + Teil B) als zusammenhängender Quelltext-
// Abschnitt — Grundlage der Quelltext-Prüfungen weiter unten.
const galerieCode = (() => {
  const anfang = src.indexOf('// N13b — Bilder im Chat: Anzeige (Galerie + Diashow)');
  const ende = src.indexOf('// ===== Ende Bilder-Galerie (N13b) =====');
  if (anfang === -1 || ende === -1 || ende < anfang) return '';
  return src.slice(anfang, ende);
})();

// Die vier reinen Funktionen aus dem ECHTEN Quelltext laden und ausführen.
eval(extractFn('fotoFrageErkennen'));
eval(extractFn('fotoKacheln'));
eval(extractFn('fotoGalerieZeilen'));
eval(extractFn('fotoDiashowNaechster'));

console.log('\n1) fotoFrageErkennen — Bild-Wort UND Zeige-Wort nötig');
pruefe('null -> null', fotoFrageErkennen(null) === null);
pruefe('undefined -> null', fotoFrageErkennen(undefined) === null);
pruefe('leere Zeichenkette -> null', fotoFrageErkennen('') === null);
pruefe('nur Leerzeichen -> null', fotoFrageErkennen('   ') === null);
pruefe('Zahl als Eingabe -> null (kein Wurf)', fotoFrageErkennen(4711) === null);
pruefe('true als Eingabe -> null', fotoFrageErkennen(true) === null);
pruefe('Objekt als Eingabe -> null', fotoFrageErkennen({ text: 'fotos' }) === null);

const w1 = fotoFrageErkennen('zeig mir die fotos');
pruefe('„zeig mir die fotos" trifft', w1 !== null && w1 !== undefined);
pruefe('  ohne Jahr -> jahr null', !!w1 && w1.jahr === null);
pruefe('  ohne Event -> event null', !!w1 && w1.event === null);

const w2 = fotoFrageErkennen('Zeig mir die Fotos vom Urlaub 2023');
pruefe('Jahr 2023 wird erkannt', !!w2 && w2.jahr === 2023);
pruefe('Jahr ist eine ZAHL, kein Text', !!w2 && typeof w2.jahr === 'number');
pruefe('Event „urlaub" klein geschrieben', !!w2 && w2.event === 'urlaub');

const w3 = fotoFrageErkennen('welche bilder habe ich von 1999');
pruefe('1999 ist kein 20xx-Jahr -> jahr null', !!w3 && w3.jahr === null);
pruefe('„welche bilder" trifft trotzdem', w3 !== null);

pruefe('„zeige fotos von 2021" -> 2021',
  (fotoFrageErkennen('zeige fotos von 2021') || {}).jahr === 2021);
pruefe('„Bilder anschauen" trifft (ohne Jahr/Event)',
  (() => { const r = fotoFrageErkennen('Bilder anschauen'); return !!r && r.jahr === null && r.event === null; })());
pruefe('„galerie der fotos" trifft', fotoFrageErkennen('galerie der fotos') !== null);
pruefe('„fotos" OHNE Zeige-Wort trifft nicht', fotoFrageErkennen('fotos') === null);
pruefe('„ich habe ein bild" trifft nicht', fotoFrageErkennen('ich habe ein bild') === null);
pruefe('„zeig mir den text" (kein Bild-Wort) trifft nicht', fotoFrageErkennen('zeig mir den text') === null);
pruefe('„öffne die galerie" (kein Bild-Wort) trifft nicht', fotoFrageErkennen('öffne die galerie') === null);
pruefe('Groß-/Kleinschreibung ist egal', fotoFrageErkennen('ZEIG MIR DIE BILDER VON 2020') !== null);
pruefe('erstes Ereignis der festen Liste zählt (urlaub vor geburtstag)',
  (fotoFrageErkennen('zeig fotos vom geburtstag und vom urlaub') || {}).event === 'urlaub');
pruefe('Event „party" wird erkannt', (fotoFrageErkennen('zeige bilder von der party') || {}).event === 'party');
pruefe('Event „konzert" wird erkannt', (fotoFrageErkennen('zeige fotos vom konzert') || {}).event === 'konzert');
pruefe('Event „festival" wird erkannt', (fotoFrageErkennen('zeige fotos vom festival') || {}).event === 'festival');
pruefe('unbekanntes Ereignis -> event null', (fotoFrageErkennen('zeige fotos vom grillabend') || {}).event === null);
pruefe('nur das ERSTE Jahr zählt (2020 vor 2021)',
  (fotoFrageErkennen('zeige fotos von 2020 und 2021') || {}).jahr === 2020);

console.log('\n1b) Zählfragen, Upload und Löschen bleiben ausgenommen');
pruefe('„wie viele fotos habe ich" -> null', fotoFrageErkennen('wie viele fotos habe ich') === null);
pruefe('„wieviel bilder sind es" -> null', fotoFrageErkennen('wieviel bilder sind es') === null);
pruefe('„anzahl fotos anzeigen" -> null', fotoFrageErkennen('anzahl fotos anzeigen') === null);
pruefe('„zeig mir die anzahl der bilder" -> null', fotoFrageErkennen('zeig mir die anzahl der bilder') === null);
pruefe('„fotos hochladen" -> null', fotoFrageErkennen('fotos hochladen') === null);
pruefe('„zeig mir den upload der fotos" -> null', fotoFrageErkennen('zeig mir den upload der fotos') === null);
pruefe('„zeig mir die fotos zum löschen" -> null', fotoFrageErkennen('zeig mir die fotos zum löschen') === null);

console.log('\n2) fotoKacheln — Kennungen, Reihenfolge, Klemmung');
pruefe('null -> leere Liste', fotoKacheln(null).length === 0);
pruefe('undefined -> leere Liste', fotoKacheln(undefined).length === 0);
pruefe('Text -> leere Liste', fotoKacheln('quatsch').length === 0);
pruefe('ok:false -> leere Liste',
  fotoKacheln({ ok: false, events: [{ dateien: [{ datei_id: 5 }] }] }).length === 0);
pruefe('ok fehlt -> leere Liste', fotoKacheln({ events: [{ dateien: [{ datei_id: 5 }] }] }).length === 0);
pruefe('events fehlt -> leere Liste', fotoKacheln({ ok: true }).length === 0);
pruefe('events ist kein Feld -> leere Liste', fotoKacheln({ ok: true, events: 'x' }).length === 0);
pruefe('leere events -> leere Liste', fotoKacheln({ ok: true, events: [] }).length === 0);

const daten = {
  ok: true, anzahl: 2, events: [
    { jahr: 2023, event: 'urlaub', anzahl: 2, dateien: [
      { datei_id: 47110000001, name: 'Bild A' },
      { datei_id: 47110000002, name: 'Bild B' } ] },
    { jahr: 2022, event: 'konzert', anzahl: 1, dateien: [ { datei_id: 47110000003 } ] },
  ],
};
const k = fotoKacheln(daten);
pruefe('Gesamtzahl stimmt', k.length === 3);
pruefe('Reihung: Event 1 vor Event 2',
  k[0].datei_id === 47110000001 && k[2].datei_id === 47110000003);
pruefe('thumb_klein mit groesse=120x120',
  k[0].thumb_klein === '/api/cloud/thumb?fileid=47110000001&groesse=120x120', k[0].thumb_klein);
pruefe('thumb_gross mit groesse=480x480',
  k[0].thumb_gross === '/api/cloud/thumb?fileid=47110000001&groesse=480x480', k[0].thumb_gross);
pruefe('nur die erlaubten Größen (kein 800x800, kein 32x32)',
  !/800x800|32x32/.test(k[0].thumb_klein + k[0].thumb_gross));
pruefe('datei_id bleibt eine Zahl', typeof k[0].datei_id === 'number');
pruefe('name wird übernommen', k[0].name === 'Bild A');
pruefe('fehlender name -> ""', k[2].name === '');

const sonder = { ok: true, events: [{ dateien: [
  { datei_id: true }, { datei_id: false }, { datei_id: '5' }, { datei_id: 0 },
  { datei_id: -3 }, { datei_id: 3.5 }, { datei_id: null }, null, { datei_id: 7 },
]}]};
const sk = fotoKacheln(sonder);
pruefe('true/false sind KEINE Kennungen', sk.length === 1 && sk[0].datei_id === 7);
pruefe('Text-, Null-, negative und Komma-Kennungen fallen weg', sk.length === 1);
pruefe('Event ohne dateien wird übersprungen',
  fotoKacheln({ ok: true, events: [{ jahr: 2020 }, { dateien: [{ datei_id: 8 }] }] }).length === 1);

const viele = { ok: true, events: [{ dateien: (() => {
  const a = []; for (let i = 1; i <= 45; i++) a.push({ datei_id: i }); return a;
})() }]};
pruefe('maxKacheln fehlt -> 40 (Standard)', fotoKacheln(viele).length === 40);
pruefe('maxKacheln 0 -> 40', fotoKacheln(viele, 0).length === 40);
pruefe('maxKacheln negativ -> 40', fotoKacheln(viele, -5).length === 40);
pruefe('maxKacheln 2 klemmt die Liste', fotoKacheln(daten, 2).length === 2);
pruefe('maxKacheln 2 nimmt die ERSTEN', fotoKacheln(daten, 2)[1].datei_id === 47110000002);
pruefe('maxKacheln über dem Bestand -> alles', fotoKacheln(daten, 99).length === 3);

console.log('\n3) fotoGalerieZeilen — Kopfzeile, Event-Zeilen, Grenzen');
pruefe('null -> genau eine Zeile',
  JSON.stringify(fotoGalerieZeilen(null)) === JSON.stringify(['Keine Bilder gefunden']));
pruefe('leere Antwort -> „Keine Bilder gefunden"',
  JSON.stringify(fotoGalerieZeilen({ ok: true, events: [] })) === JSON.stringify(['Keine Bilder gefunden']));
pruefe('ok:false -> „Keine Bilder gefunden"',
  fotoGalerieZeilen({ ok: false, events: [{ dateien: [{ datei_id: 5 }] }] })[0] === 'Keine Bilder gefunden');
pruefe('Events ohne gültige Kennung -> „Keine Bilder gefunden"',
  fotoGalerieZeilen({ ok: true, events: [{ dateien: [{ datei_id: true }] }] })[0] === 'Keine Bilder gefunden');
pruefe('Text als Eingabe -> „Keine Bilder gefunden"',
  fotoGalerieZeilen('x')[0] === 'Keine Bilder gefunden');

const gz = fotoGalerieZeilen(daten);
pruefe('Kopfzeile hat die vorgegebene Form',
  gz[0] === 'Treffer: 2 Events, 3 Bilder', gz[0]);
pruefe('Event-Zeile hat die vorgegebene Form',
  gz[1] === '· urlaub (2023) — 2 Bilder', gz[1]);
pruefe('zweite Event-Zeile',
  gz[2] === '· konzert (2022) — 1 Bild', gz[2]);
pruefe('höchstens 5 Zeilen', gz.length <= 5);

const fuenfEvents = { ok: true, anzahl: 5, events: (() => {
  const namen = ['eins', 'zwei', 'drei', 'vier', 'fuenf'], a = [];
  namen.forEach((n) => a.push({ jahr: 2020, event: n, anzahl: 1, dateien: [{ datei_id: 1 }] }));
  return a;
})()};
const fz = fotoGalerieZeilen(fuenfEvents);
pruefe('fünf Events -> genau 5 Zeilen', fz.length === 5);
pruefe('die fünfte Event-Zeile fällt weg', fz[4] === '· vier (2020) — 1 Bild', fz[4]);
pruefe('ohne anzahl-Feld zählt die Zahl der Kennungen',
  fotoGalerieZeilen({ ok: true, events: [{ event: 'urlaub', jahr: 2023,
    dateien: [{ datei_id: 1 }, { datei_id: 2 }] }] })[1] === '· urlaub (2023) — 2 Bilder');
pruefe('ohne Jahr steht „unbekannt"',
  fotoGalerieZeilen({ ok: true, events: [{ event: 'urlaub', dateien: [{ datei_id: 1 }] }] })[1]
    === '· urlaub (unbekannt) — 1 Bild');
pruefe('ohne anzahl-Feld zählt die Kopfzeile die Event-Liste',
  fotoGalerieZeilen({ ok: true, events: [{ event: 'urlaub', dateien: [{ datei_id: 1 }] }] })[0]
    === 'Treffer: 1 Event, 1 Bild');
pruefe('Kopfzeile zählt nur GÜLTIGE Kennungen',
  fotoGalerieZeilen({ ok: true, anzahl: 1, events: [{ event: 'urlaub', jahr: 2020,
    dateien: [{ datei_id: 1 }, { datei_id: true }, { datei_id: 0 }] }] })[0]
    === 'Treffer: 1 Event, 1 Bild');

console.log('\n4) fotoDiashowNaechster — Umlauf und Richtung');
pruefe('vorwärts 0 -> 1', fotoDiashowNaechster(0, 3, 1) === 1);
pruefe('vorwärts vom Ende umlaufend', fotoDiashowNaechster(2, 3, 1) === 0);
pruefe('zurück von 0 umlaufend', fotoDiashowNaechster(0, 3, -1) === 2);
pruefe('zurück 2 -> 1', fotoDiashowNaechster(2, 3, -1) === 1);
pruefe('Richtung 0 zählt als vorwärts', fotoDiashowNaechster(0, 3, 0) === 1);
pruefe('Richtung "x" zählt als vorwärts', fotoDiashowNaechster(0, 3, 'x') === 1);
pruefe('Richtung undefined zählt als vorwärts', fotoDiashowNaechster(0, 3, undefined) === 1);
pruefe('Richtung -1 bleibt zurück', fotoDiashowNaechster(1, 3, -1) === 0);
pruefe('anzahl 0 -> 0', fotoDiashowNaechster(0, 0, 1) === 0);
pruefe('anzahl negativ -> 0', fotoDiashowNaechster(0, -4, 1) === 0);
pruefe('einzige Kachel bleibt bei 0 (vor)', fotoDiashowNaechster(0, 1, 1) === 0);
pruefe('einzige Kachel bleibt bei 0 (zurück)', fotoDiashowNaechster(0, 1, -1) === 0);
pruefe('Index außerhalb wird eingefangen', fotoDiashowNaechster(7, 3, 1) === 2);
pruefe('Ergebnis ist immer im gültigen Bereich', (() => {
  for (let i = -5; i < 10; i++) {
    const r = fotoDiashowNaechster(i, 4, 1);
    if (r < 0 || r > 3) return false;
  }
  return true;
})());

console.log('\n5) Verdrahtung im Quelltext (Teil B)');
// Seit 01.10.2026 ist der Stichwort-Abfang aus (Werkzeuge immer an, das Modell
// entscheidet) - siehe tests/test_werkzeuge_schalter.js. Die Galerie bleibt.
pruefe('kein Abfang mehr in sendMessage (Modell entscheidet)',
  (src.match(/fotoFrageErkennen\(/g) || []).length === 1 && !/const fotowunsch/.test(src));  // nur noch die Definition
pruefe('Galerie-Funktion bleibt erhalten', /async function zeigeFotoGalerie\(wunsch\)/.test(src));
pruefe('Blase trägt data-foto-galerie',
  /data-foto-galerie/.test(src) && /data-foto-galerie/.test(galerieCode));
pruefe('Raster trägt data-foto-kacheln', /data-foto-kacheln/.test(galerieCode));
pruefe('Großansicht trägt data-foto-gross', /data-foto-gross/.test(galerieCode));
pruefe('Überschrift „🖼️ Bilder" steht in der Blase', /🖼️ Bilder/.test(galerieCode));
pruefe('Endpunkt /api/fotos/bilder wird geholt', /\/api\/fotos\/bilder\?/.test(galerieCode));
pruefe('limit=5 UND pro_event=40 werden mitgeschickt',
  /'limit=5'/.test(galerieCode) && /'pro_event=40'/.test(galerieCode));
pruefe('Jahr/Event werden nur bei Bedarf mitgeschickt',
  /if \(wunsch && wunsch\.jahr\)/.test(galerieCode) && /if \(wunsch && wunsch\.event\)/.test(galerieCode));
pruefe('Kacheln kommen aus fotoKacheln(daten)', /fotoKacheln\(daten\)/.test(galerieCode));
pruefe('Zeilen kommen aus fotoGalerieZeilen(daten)', /fotoGalerieZeilen\(daten\)/.test(galerieCode));
pruefe('Diashow nutzt fotoDiashowNaechster', /fotoDiashowNaechster\(/.test(galerieCode));
pruefe('Diashow schaltet alle 3000 ms weiter', /\}, 3000\);/.test(galerieCode));
pruefe('Knöpfe ‹ Zurück / Weiter › / Diashow / Stopp / ✕ vorhanden',
  /‹ Zurück/.test(galerieCode) && /Weiter ›/.test(galerieCode)
  && /▶ Diashow/.test(galerieCode) && /⏸ Stopp/.test(galerieCode) && /✕/.test(galerieCode));
pruefe('Escape schließt die Großansicht',
  /e\.key === 'Escape'/.test(galerieCode) && /addEventListener\('keydown'/.test(galerieCode));
pruefe('Hintergrund-Klick schließt die Großansicht', /e\.target === overlay/.test(galerieCode));
pruefe('Anzeige per textContent (kein innerHTML im Galerie-Bereich)',
  !/innerHTML/.test(galerieCode) && /\.textContent\b/.test(galerieCode));

console.log('\n6) Nichts wird gespeichert (harte Regel)');
['localStorage', 'sessionStorage', 'indexedDB', 'IndexedDB',
 'caches.', 'CacheStorage', 'serviceWorker.register'].forEach((wort) => {
  pruefe('kein „' + wort + '" im Galerie-Bereich', galerieCode.indexOf(wort) === -1);
});
pruefe('Galerie-Bereich ist überhaupt auffindbar (Region nicht leer)', galerieCode.length > 1000);
pruefe('Bilder kommen aus Blob + Objekt-URL',
  /URL\.createObjectURL\(/.test(galerieCode) && /res\.blob\(\)/.test(galerieCode));
pruefe('Objekt-URLs werden freigegeben (revokeObjectURL)', /URL\.revokeObjectURL\(/.test(galerieCode));
pruefe('Buchführung _fotoObjekte ist ein Set', /const _fotoObjekte = new Set\(\)/.test(galerieCode));
pruefe('jede erzeugte Objekt-URL wird vermerkt', /_fotoObjekte\.add\(objektUrl\)/.test(galerieCode));
pruefe('fotoObjekteFreigeben leert die Buchführung', /_fotoObjekte\.clear\(\)/.test(galerieCode));
pruefe('Schließen ruft IMMER fotoObjekteFreigeben()',
  /function schliesseFotoGross\(\)[\s\S]*?fotoObjekteFreigeben\(\);/.test(galerieCode));
pruefe('Wechsel gibt das VORHERIGE Bild frei',
  /_fotoGrossUrl\) \{\s*try \{ URL\.revokeObjectURL\(_fotoGrossUrl\)/.test(galerieCode));
pruefe('KEIN direkter /api/cloud/thumb im img.src',
  !/\.\s*src\s*=\s*['"`][^'"`]*\/api\/cloud\/thumb/.test(galerieCode));
pruefe('Kachelbild wird über fotoBildLaden geholt', /fotoBildLaden\(k\.thumb_klein\)/.test(galerieCode));
pruefe('Großbild wird über fotoBildLaden geholt (480x480)', /fotoBildLaden\(k\.thumb_gross\)/.test(galerieCode));
pruefe('einzelner Bildfehler -> „Vorschau nicht verfügbar", Rest bleibt',
  (galerieCode.match(/Vorschau nicht verfügbar/g) || []).length >= 2);
pruefe('Fehlerfall nennt den error-Text des Endpunkts', /daten\.error/.test(galerieCode));
pruefe('Fehlerfall nennt „Bilder nicht abrufbar (…)"', /Bilder nicht abrufbar \(/.test(galerieCode));
pruefe('fehlgeschlagener Bildabruf gibt null zurück (kein Wurf)',
  /catch \(_e\) \{\s*return null;/.test(galerieCode));

console.log('\n7) Service Worker legt für /api/ nichts ab');
pruefe('sw.js ist lesbar', sw.length > 0);
const apiZweig = (() => {
  const i = sw.indexOf("url.pathname.startsWith('/api/')");
  const j = sw.indexOf('// Statische Assets', i);
  return (i === -1 || j === -1) ? '' : sw.slice(i, j);
})();
pruefe('der /api/-Zweig ist auffindbar', apiZweig.length > 0);
pruefe('der /api/-Zweig ist netzwerk-zuerst (fetch(request))', /fetch\(request\)/.test(apiZweig));
pruefe('der /api/-Zweig legt NICHTS in den Cache',
  apiZweig.indexOf('cache.put') === -1 && apiZweig.indexOf('caches.') === -1);
pruefe('sw.js hat keine Sonderregel für /api/cloud/thumb', sw.indexOf('/api/cloud/thumb') === -1);

console.log('\n8) Cache-Bump, Styling und Datenschutz');
const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
const vCss = (html.match(/style\.css\?v=([0-9A-Z]+)/) || [])[1] || '';
pruefe('index.html lädt app.js mit ?v=20261001B', vApp === '20261001B', 'gefunden: ' + vApp);
pruefe('index.html lädt style.css mit ?v=20261001E', vCss === '20261001E', 'gefunden: ' + vCss);
pruefe('?v= app.js ist HÖHER als vorher (20260927B)', vApp > '20260927B', 'gefunden: ' + vApp);
pruefe('?v= style.css ist HÖHER als vorher (20260925F)', vCss > '20260925F', 'gefunden: ' + vCss);
pruefe('kein CDN/keine externe Quelle im Frontend',
  !/<script[^>]+src="https?:/.test(html) && !/<link[^>]+href="https?:/.test(html));
pruefe('kein API-Schlüssel im Frontend',
  !/sk-or-v1-/.test(src) && !/sk-or-v1-/.test(html));
pruefe('style.css hat die Kachel-Regeln',
  /\.foto-kacheln\s*\{/.test(css) && /\.foto-kachel\s*\{/.test(css));
pruefe('style.css hat die Großansicht und die Knöpfe',
  /\.foto-gross\s*\{/.test(css) && /\.foto-knopf\s*\{/.test(css));
pruefe('style.css bleibt im dunklen Look (dunkle Flächen, kein Hellmodus)',
  /background:\s*rgba\(0,\s*0,\s*0,\s*0\.88\)/.test(css) && /--assistant-msg-bg/.test(css));
pruefe('kein externer Import in style.css', !/@import\s+url\(\s*['"]?https?:/.test(css));

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
