// Alltagsprotokoll S6 (03.11.2026): Oberfläche — Sprechen/Tastatur, Rückfragen je fehlendem Feld,
// Tagesablauf mit Ergänzen/Löschen. S9: Ekman-Gefühle, Diktat in jedem Feld, keine Schlafknöpfe
// (Schlaf kommt von der Uhr). Nur erfundene Einträge.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_alltag.js alltag.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'alltag.js');
const ordner = path.dirname(path.resolve(pfadJs));
const src = fs.readFileSync(pfadJs, 'utf8');
const html = fs.readFileSync(path.join(ordner, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(ordner, 'style.css'), 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) console.log('  OK   ' + name);
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('nicht gefunden: ' + name);
  const start = src.slice(Math.max(0, i - 6), i) === 'async ' ? i - 6 : i;
  let tiefe = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') tiefe++;
    else if (src[k] === '}') { tiefe--; if (tiefe === 0) { k++; break; } }
  }
  return src.slice(start, k);
}
const fn = (name, ...abh) => new Function(...abh, extractFn(name) + '; return ' + name + ';');

console.log('\n1) alltagOffenText — Kopfzeile aus GET /api/alltag/offen');
const offen = fn('alltagOffenText')();
pruefe('schläft', offen({ ok: true, offene_stunden: 0, schlaeft: true }) === 'Du schläfst — keine Erinnerung.');
pruefe('alles eingetragen', offen({ ok: true, offene_stunden: 0, schlaeft: false }) === 'Alles eingetragen.');
pruefe('eine Stunde', offen({ ok: true, offene_stunden: 1, schlaeft: false }) === '1 Stunde offen');
pruefe('mehrere Stunden', offen({ ok: true, offene_stunden: 3, schlaeft: false }) === '3 Stunden offen');
pruefe('keine Antwort', offen(null) === '');

console.log('\n2) alltagEintragText — eine Zeile im Tagesablauf');
const STUFEN = { 5: 'sehr gut', 4: 'gut', 3: 'mittel', 2: 'schlecht', 1: 'sehr schlecht' };
const zeile = fn('alltagEintragText', 'alltagUhrzeit', 'ALLTAG_EREIGNIS_TEXT')(
  fn('alltagUhrzeit')(), { schlafen: 'Schlafen gegangen', aufwachen: 'Aufgewacht' });
pruefe('Stunde voll', zeile({ art: 'stunde', von: '2026-11-03T14:40:00+01:00', bis: '2026-11-03T15:40:00+01:00',
  aktivitaet: 'Wäsche gemacht', stimmung: 4, anspannung: 30, gefuehle: ['Ärger', 'Müdigkeit'] }, STUFEN)
  === '14:40–15:40 · Wäsche gemacht · Stimmung gut · Anspannung 30 · Ärger, Müdigkeit',
  zeile({ art: 'stunde', von: '2026-11-03T14:40:00+01:00', bis: '2026-11-03T15:40:00+01:00', aktivitaet: 'Wäsche gemacht', stimmung: 4, anspannung: 30, gefuehle: ['Ärger', 'Müdigkeit'] }, STUFEN));
pruefe('Stunde nur Originalworte', zeile({ art: 'stunde', von: '2026-11-03T09:00:00+01:00', bis: '2026-11-03T10:00:00+01:00',
  originalworte: 'Gelesen, mittel' }, STUFEN) === '09:00–10:00 · „Gelesen, mittel"');
pruefe('Schlaf-Ereignis', zeile({ art: 'schlaf', ereignis: 'aufwachen', zeit: '2026-11-03T07:05:00+01:00' }, STUFEN) === '07:05 · Aufgewacht');
pruefe('Anspannung 0 wird gezeigt', /Anspannung 0/.test(zeile({ art: 'stunde', von: '2026-11-03T09:00:00+01:00', bis: '2026-11-03T10:00:00+01:00', anspannung: 0 }, STUFEN)));

console.log('\n3) alltagNachtText — Nacht der Uhr');
const nacht = fn('alltagNachtText')();
pruefe('Nacht mit Dauer', nacht({ einschlafen: '23:10', aufwachen: '06:50', schlaf_min: 425 }) === 'Uhr: 23:10–06:50 · 7 Std. 5 Min. Schlaf');

console.log('\n4) alltagRueckfragen — fehlende Felder in fester Reihenfolge');
const rueck = fn('alltagRueckfragen')();
pruefe('Reihenfolge', JSON.stringify(rueck(['aktivitaet', 'gefuehle', 'stimmung'])) === '["stimmung","gefuehle","aktivitaet"]');
pruefe('Unbekanntes fällt weg', JSON.stringify(rueck(['essen', 'anspannung'])) === '["anspannung"]');
pruefe('leer', rueck(undefined).length === 0);

console.log('\n5) alltagGefuehle — nur Grundgefühle aus der Liste');
const gef = fn('alltagGefuehle')();
const EKMAN = ['Freude', 'Trauer', 'Angst', 'Ärger', 'Ekel', 'Überraschung'];
pruefe('nur erlaubte, ohne Doppelte', JSON.stringify(gef(['Ärger', 'genervt', 'Ärger', 'Angst'], EKMAN)) === '["Ärger","Angst"]');
pruefe('ohne Liste nichts', gef(['Freude'], null).length === 0 && gef(null, EKMAN).length === 0);

console.log('\n5b) alltagAnhaengen — Diktat an ein Feld anhängen');
const anh = fn('alltagAnhaengen')();
pruefe('leeres Feld', anh('', ' Wäsche gemacht ') === 'Wäsche gemacht');
pruefe('anhängen mit Leerzeichen', anh('Wäsche gemacht', 'dann Kaffee') === 'Wäsche gemacht dann Kaffee');
pruefe('nichts verstanden', anh('Wäsche', '  ') === 'Wäsche');

console.log('\n6) alltagAntwortText — Meldung nach dem Eintragen');
const antw = fn('alltagAntwortText')();
pruefe('vollständig', antw({ ok: true, fehlt: [] }) === 'Eingetragen.');
pruefe('mit Lücken', antw({ ok: true, fehlt: ['stimmung'] }) === 'Eingetragen — eine Frage noch.');
pruefe('mehrere Lücken', antw({ ok: true, fehlt: ['stimmung', 'gefuehle'] }) === 'Eingetragen — 2 Fragen noch.');
pruefe('Fehler mit gesicherten Worten', antw({ ok: false, grund: 'Kein Schlüssel.', eintrag: { id: 'x' } }) === 'Kein Schlüssel. Deine Worte sind gesichert.');
pruefe('Fehler ohne Eintrag', antw({ ok: false, grund: 'Kaputt.' }) === 'Kaputt.');
pruefe('keine Antwort', antw(null) === 'Nicht gespeichert — bitte noch einmal.');

console.log('\n7) alltagAufnahmeGewuenscht — ?alltag=aufnahme aus dem Pop-up');
const gewuenscht = fn('alltagAufnahmeGewuenscht')();
pruefe('aufnahme', gewuenscht('?alltag=aufnahme') === true);
pruefe('anderes', gewuenscht('?alltag=tag') === false && gewuenscht('') === false);

(async () => {
  console.log('\n8) alltagSenden / alltagFeldSpeichern — API-Aufrufe');
  const aufrufe = [];
  const fetchAttrappe = async (url, opt) => {
    aufrufe.push({ url, opt });
    return { ok: true, json: async () => ({ ok: true, eintrag: { id: 'neu-1' }, fehlt: [] }) };
  };
  const senden = fn('alltagSenden', 'API_BASE', 'fetch')('', fetchAttrappe);
  const a = await senden('Wäsche gemacht', 'sprache');
  pruefe('POST /api/alltag/eintrag', aufrufe[0].url === '/api/alltag/eintrag' && aufrufe[0].opt.method === 'POST');
  pruefe('Körper {text, quelle}', aufrufe[0].opt.body === JSON.stringify({ text: 'Wäsche gemacht', quelle: 'sprache' }));
  pruefe('mit Sitzungs-Cookie', aufrufe[0].opt.credentials === 'same-origin');
  pruefe('Antwort durchgereicht', a && a.eintrag.id === 'neu-1');

  aufrufe.length = 0;
  const feld = fn('alltagFeldSpeichern', 'API_BASE', 'fetch')('', fetchAttrappe);
  const neu = await feld('alt-1', 'stimmung', 4);
  pruefe('PATCH mit Feld', aufrufe[0].url === '/api/alltag/eintrag/alt-1' && aufrufe[0].opt.method === 'PATCH'
    && aufrufe[0].opt.body === '{"stimmung":4}');
  pruefe('neue Kennung zurück', neu === 'neu-1');

  const kaputt = async () => { throw new Error('offline'); };
  pruefe('Netzfehler -> null', (await fn('alltagSenden', 'API_BASE', 'fetch')('', kaputt)('x', 'tastatur')) === null);
  pruefe('Netzfehler beim Ergänzen -> null', (await fn('alltagFeldSpeichern', 'API_BASE', 'fetch')('', kaputt)('a', 'stimmung', 1)) === null);

  console.log('\n8b) alltagMikrofonOeffnen — gibt bei jedem Fehler das Mikrofon frei (Hermes S9 R2)');
  const oeffnen = fn('alltagMikrofonOeffnen', 'alltagMikrofonSchliessen')(fn('alltagMikrofonSchliessen')());
  function attrappen(fehlerBei) {
    const z = { gestoppt: 0, geschlossen: 0 };
    const medien = { getUserMedia: async () => ({ getTracks: () => [{ stop: () => z.gestoppt++ }] }) };
    class Ctx {
      constructor() { if (fehlerBei === 'ctx') throw new Error('ctx'); this.state = 'running'; this.destination = {};
        this.audioWorklet = { addModule: async () => { if (fehlerBei === 'modul') throw new Error('modul'); } }; }
      createMediaStreamSource() { return { connect() {} }; }
      close() { z.geschlossen++; }
    }
    class Knoten { constructor() { if (fehlerBei === 'knoten') throw new Error('knoten'); this.port = {}; } connect() {} }
    return { z, medien, Ctx, Knoten };
  }
  for (const stelle of ['ctx', 'modul', 'knoten']) {
    const a = attrappen(stelle);
    let geworfen = false;
    try { await oeffnen(a.medien, a.Ctx, a.Knoten); } catch (_) { geworfen = true; }
    pruefe('Fehler bei ' + stelle + ': Spur gestoppt, Fehler weitergereicht', geworfen && a.z.gestoppt === 1,
      JSON.stringify(a.z));
    if (stelle !== 'ctx') pruefe('Fehler bei ' + stelle + ': AudioContext geschlossen', a.z.geschlossen === 1);
  }
  const gut = attrappen(null);
  const offen = await oeffnen(gut.medien, gut.Ctx, gut.Knoten);
  offen.knoten.port.onmessage({ data: 'pcm' });
  pruefe('Erfolg: nichts gestoppt, Stücke werden gesammelt', gut.z.gestoppt === 0 && offen.stuecke.length === 1);

  console.log('\n9) Verdrahtung');
  pruefe('index.html lädt alltag.js nach app.js', /<script src="app\.js\?v=\d{8}[A-Z]"><\/script>[\s\S]*<script src="alltag\.js\?v=\d{8}[A-Z]"><\/script>/.test(html));
  const ids = ['alltag-btn', 'alltag-sheet', 'alltag-close', 'alltag-offen', 'alltag-aufnahme', 'alltag-tastatur',
    'alltag-text-block', 'alltag-text', 'alltag-senden', 'alltag-mic-status', 'alltag-text-mic', 'alltag-rueckfrage', 'alltag-frage', 'alltag-antworten',
    'alltag-ueberspringen', 'alltag-meldung', 'alltag-tag-vor', 'alltag-datum', 'alltag-tag-weiter',
    'alltag-tag-liste', 'alltag-tag-leer'];
  for (const id of ids) pruefe('index.html hat #' + id, html.includes('id="' + id + '"'));
  pruefe('alle IDs eindeutig', ids.every((id) => html.split('id="' + id + '"').length === 2));
  pruefe('kein innerHTML', !/innerHTML/.test(src));
  for (const weg of ['alltag-schlafen', 'alltag-aufwachen', 'alltag-wach-liegen', 'alltag-wieder-schlafen']) {
    pruefe('Schlafknopf #' + weg + ' ist weg', !html.includes('id="' + weg + '"') && !src.includes("'" + weg + "'"));
  }
  pruefe('kein Schlaf-Schnellknopf mehr', !/alltagKnopf|\/api\/alltag\/ereignis/.test(src));
  pruefe('keine eigenen Gefühlsworte', !src.includes('alltag-gefuehl-eigene'));
  pruefe('Diktat-Knopf am Tätigkeitsfeld', src.includes("'alltag-aktivitaet-mic'"));
  pruefe('Feld-Diktat hängt an', /alltagAnhaengen\(/.test(src.replace('function alltagAnhaengen(', '')));
  pruefe('nutzt encodeWav aus app.js', /encodeWav\(/.test(src));
  pruefe('Diktat über /api/sprache/transkript', src.includes('/api/sprache/transkript'));
  pruefe('Stand an die App (S7)', /HeyAgentAlltag/.test(src));
  pruefe('Blatt im Stil', /#alltag-sheet\s*\{/.test(css) && /#alltag-sheet\[hidden\]/.test(css));
  pruefe('hidden schlägt display:flex im Blatt', /#alltag-sheet \[hidden\]\s*\{\s*display:\s*none/.test(css));
  pruefe('großer Knopf am Handy', /\.alltag-gross\s*\{[^}]*min-height:\s*(5\d|[6-9]\d)px/.test(css));

  console.log('\n10) Wochenübersicht (S14)');
  const schlafKurz = fn('alltagSchlafKurz')();
  pruefe('Schlaf 450 min = 7:30', schlafKurz(450) === '7:30');
  pruefe('Schlaf 425 min = 7:05', schlafKurz(425) === '7:05');
  pruefe('ohne Nacht ein Strich', schlafKurz(null) === '–');
  const prozent = fn('alltagStimmungProzent')();
  pruefe('Stimmung 5 = voller Balken', prozent(5) === 100);
  pruefe('Stimmung 1 = kleiner Rest', prozent(1) === 8);
  pruefe('Stimmung 3 = Mitte', prozent(3) === 54);
  pruefe('ohne Stimmung kein Balken', prozent(null) === 0);
  const komma = fn('alltagKomma')();
  pruefe('Komma statt Punkt', komma(3.5) === '3,5' && komma(4) === '4');
  const tagText = fn('alltagWochenTagText')();
  pruefe('Wochentag und Datum', tagText({ datum: '2026-11-03', wochentag: 'Di' }) === 'Di 03.11.');
  const werte = fn('alltagWochenWerte', 'alltagSchlafKurz', 'alltagKomma')(schlafKurz, komma);
  pruefe('Werte eines Tages', werte({ eintraege: 4, stimmung: 3.8, schlaf_min: 440 }) === 'Stimmung 3,8 · 7:20 Std. Schlaf · 4 Einträge',
    werte({ eintraege: 4, stimmung: 3.8, schlaf_min: 440 }));
  pruefe('ein Eintrag ohne Nacht', werte({ eintraege: 1, stimmung: 2, schlaf_min: null }) === 'Stimmung 2 · 1 Eintrag');
  pruefe('nur Nacht', werte({ eintraege: 0, stimmung: null, schlaf_min: 480 }) === '8:00 Std. Schlaf');
  pruefe('leerer Tag', werte({ eintraege: 0, stimmung: null, schlaf_min: null }) === 'Nichts eingetragen');
  const schnittText = fn('alltagWochenSchnittText', 'alltagSchlafKurz', 'alltagKomma')(schlafKurz, komma);
  pruefe('Schnitt der Woche', schnittText({ stimmung: 3.4, anspannung: 40, schlaf_min: 440 })
    === 'Im Schnitt: Stimmung 3,4 · Anspannung 40 · 7:20 Std. Schlaf');
  pruefe('Schnitt ohne Werte', schnittText({ stimmung: null, anspannung: null, schlaf_min: null }) === '');
  for (const id of ['alltag-woche', 'alltag-woche-liste', 'alltag-woche-schnitt', 'alltag-woche-erkenntnisse']) {
    pruefe('index.html hat #' + id, html.split('id="' + id + '"').length === 2);
  }
  pruefe('Woche über /api/alltag/woche', src.includes('/api/alltag/woche?bis='));
  pruefe('Woche bleibt beim Antippen stehen', src.includes("'/api/alltag/woche?bis=' + zustand.wocheBis")
    && /zustand\.wocheBis = neu/.test(src));
  pruefe('Zeile springt zum Tag', /alltag-woche-tag-/.test(src));
  pruefe('Balken im Stil', /\.alltag-balken\s*\{/.test(css));

  console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
  process.exit(fehler ? 1 : 0);
})();
