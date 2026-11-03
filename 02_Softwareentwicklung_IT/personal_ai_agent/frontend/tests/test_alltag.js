// Alltagsprotokoll S6 (03.11.2026): Oberfläche — Sprechen/Tastatur, Rückfragen je fehlendem Feld,
// Schlaf-Schnellknöpfe, Tagesablauf mit Ergänzen/Löschen. Nur erfundene Einträge.
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

console.log('\n5) alltagGefuehle — Auswahl + eigene Worte');
const gef = fn('alltagGefuehle')();
pruefe('Auswahl und eigene Worte', JSON.stringify(gef(['Ärger'], 'genervt, Ärger,  müde ')) === '["Ärger","genervt","müde"]');
pruefe('zu lang fällt weg, höchstens 8', gef([], 'a,b,c,d,e,f,g,h,i,' + 'x'.repeat(41)).length === 8);

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
  console.log('\n8) alltagSenden / alltagFeldSpeichern / alltagKnopf — API-Aufrufe');
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

  aufrufe.length = 0;
  const knopf = fn('alltagKnopf', 'API_BASE', 'fetch')('', fetchAttrappe);
  await knopf('wach_liegen');
  pruefe('POST /api/alltag/ereignis', aufrufe[0].url === '/api/alltag/ereignis' && aufrufe[0].opt.body === '{"ereignis":"wach_liegen"}');

  const kaputt = async () => { throw new Error('offline'); };
  pruefe('Netzfehler -> null', (await fn('alltagSenden', 'API_BASE', 'fetch')('', kaputt)('x', 'tastatur')) === null);
  pruefe('Netzfehler beim Ergänzen -> null', (await fn('alltagFeldSpeichern', 'API_BASE', 'fetch')('', kaputt)('a', 'stimmung', 1)) === null);

  console.log('\n9) Verdrahtung');
  pruefe('index.html lädt alltag.js nach app.js', /<script src="app\.js\?v=\d{8}[A-Z]"><\/script>[\s\S]*<script src="alltag\.js\?v=\d{8}[A-Z]"><\/script>/.test(html));
  const ids = ['alltag-btn', 'alltag-sheet', 'alltag-close', 'alltag-offen', 'alltag-aufnahme', 'alltag-tastatur',
    'alltag-text-block', 'alltag-text', 'alltag-senden', 'alltag-mic-status', 'alltag-schlafen', 'alltag-aufwachen',
    'alltag-wach-liegen', 'alltag-wieder-schlafen', 'alltag-rueckfrage', 'alltag-frage', 'alltag-antworten',
    'alltag-ueberspringen', 'alltag-meldung', 'alltag-tag-vor', 'alltag-datum', 'alltag-tag-weiter',
    'alltag-tag-liste', 'alltag-tag-leer'];
  for (const id of ids) pruefe('index.html hat #' + id, html.includes('id="' + id + '"'));
  pruefe('alle IDs eindeutig', ids.every((id) => html.split('id="' + id + '"').length === 2));
  pruefe('kein innerHTML', !/innerHTML/.test(src));
  pruefe('nutzt encodeWav aus app.js', /encodeWav\(/.test(src));
  pruefe('Diktat über /api/sprache/transkript', src.includes('/api/sprache/transkript'));
  pruefe('Stand an die App (S7)', /HeyAgentAlltag/.test(src));
  pruefe('Blatt im Stil', /#alltag-sheet\s*\{/.test(css) && /#alltag-sheet\[hidden\]/.test(css));
  pruefe('hidden schlägt display:flex im Blatt', /#alltag-sheet \[hidden\]\s*\{\s*display:\s*none/.test(css));
  pruefe('großer Knopf am Handy', /\.alltag-gross\s*\{[^}]*min-height:\s*(5\d|[6-9]\d)px/.test(css));

  console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
  process.exit(fehler ? 1 : 0);
})();
