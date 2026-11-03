// Schlaf von der Uhr (03.11.2026, Issue #12): Hey Agent liest Health Connect und übergibt die
// Nächte an die Seite (window.heyAgentSchlafEmpfangen); die Seite schickt sie angemeldet an
// POST /api/alltag/schlaf und zeigt den Stand im Checks-Fenster. Daten erfunden.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_schlaf.js schlaf.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'schlaf.js');
const src = fs.readFileSync(pfadJs, 'utf8');
const html = fs.readFileSync(path.join(path.dirname(path.resolve(pfadJs)), 'index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(path.dirname(path.resolve(pfadJs)), 'app.js'), 'utf8');

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

console.log('\n1) schlafNaechteLesen — was die App liefert, robust lesen');
const lesen = fn('schlafNaechteLesen')();
pruefe('gültige Liste', lesen('[{"quelle_kennung":"a"}]').length === 1);
pruefe('Objekt mit naechte', lesen('{"naechte":[{"quelle_kennung":"a"},{"quelle_kennung":"b"}]}').length === 2);
pruefe('kaputtes JSON -> null', lesen('{kaputt') === null);
pruefe('kein Text -> null', lesen(undefined) === null && lesen(5) === null);

console.log('\n2) schlafAbgleichText — Ergebnis von POST /api/alltag/schlaf als Klartext');
const abgleich = fn('schlafAbgleichText')();
pruefe('neue Nächte', abgleich({ ok: true, neu: 2, aktualisiert: 0, unveraendert: 5, abgelehnt: 0 }) === 'Uhr abgeglichen: 2 neue Nächte, 5 unverändert.',
  abgleich({ ok: true, neu: 2, aktualisiert: 0, unveraendert: 5, abgelehnt: 0 }));
pruefe('eine neue Nacht, eine aktualisiert', abgleich({ ok: true, neu: 1, aktualisiert: 1, unveraendert: 0, abgelehnt: 0 }) === 'Uhr abgeglichen: 1 neue Nacht, 1 aktualisiert.');
pruefe('nichts Neues', abgleich({ ok: true, neu: 0, aktualisiert: 0, unveraendert: 3, abgelehnt: 0 }) === 'Uhr abgeglichen: nichts Neues (3 Nächte schon da).');
pruefe('abgelehnte werden genannt', /2 unlesbar/.test(abgleich({ ok: true, neu: 0, aktualisiert: 0, unveraendert: 0, abgelehnt: 2 })));
pruefe('Fehler ehrlich', /nicht übernommen/.test(abgleich(null)));

console.log('\n3) schlafStandText — Kopfzeile im Checks-Fenster');
const stand = fn('schlafStandText')();
pruefe('ohne Nächte', stand({ ok: true, anzahl: 0 }) === 'Schlaf (Uhr): noch keine Nächte');
pruefe('mit Nächten', stand({ ok: true, anzahl: 4, letzte_nacht_zum: '2026-11-03' }) === 'Schlaf (Uhr): 4 Nächte, zuletzt Nacht zum 03.11.2026');
pruefe('keine Antwort', stand(null) === 'Schlaf (Uhr): Stand nicht abrufbar');

console.log('\n4) schlafBrueckeHinweis — Knopf nur in der App wirksam');
const hinweis = fn('schlafBrueckeHinweis')();
pruefe('ohne Brücke ehrlicher Hinweis', /Hey-Agent-App/.test(hinweis(undefined)));
pruefe('mit Brücke leer', hinweis({ abgleichen() {} }) === '');

console.log('\n5) schlafEmpfangen — schickt angemeldet an die API');
(async () => {
  const aufrufe = [];
  const meldungen = [];
  let neuGeladen = 0;
  const fetchAttrappe = async (url, opt) => { aufrufe.push({ url, opt }); return { ok: true, json: async () => ({ ok: true, neu: 1, aktualisiert: 0, unveraendert: 0, abgelehnt: 0 }) }; };
  const empfangen = fn('schlafEmpfangen', 'API_BASE', 'fetch', 'schlafNaechteLesen', 'schlafAbgleichText', '_schlafMeldung', 'ladeSchlaf')(
    '', fetchAttrappe, lesen, abgleich, (t) => meldungen.push(t), () => { neuGeladen++; });
  await empfangen('[{"quelle_kennung":"a","beginn":"2026-11-02T23:00:00+01:00","ende":"2026-11-03T06:00:00+01:00"}]');
  pruefe('genau ein POST an /api/alltag/schlaf', aufrufe.length === 1 && aufrufe[0].url === '/api/alltag/schlaf' && aufrufe[0].opt.method === 'POST');
  pruefe('mit Sitzungs-Cookie', aufrufe[0].opt.credentials === 'same-origin');
  pruefe('Körper {naechte: [...]}', JSON.parse(aufrufe[0].opt.body).naechte.length === 1);
  pruefe('Meldung und Stand neu', meldungen[meldungen.length - 1] === 'Uhr abgeglichen: 1 neue Nacht.' && neuGeladen === 1, JSON.stringify(meldungen));
  aufrufe.length = 0;
  await empfangen('{kaputt');
  pruefe('kaputte Übergabe -> kein POST, Meldung', aufrufe.length === 0 && /nicht lesbar/.test(meldungen[meldungen.length - 1]));

  console.log('\n6) Verdrahtung');
  pruefe('index.html lädt schlaf.js mit ?v=', /<script src="schlaf\.js\?v=\d{8}[A-Z]"><\/script>/.test(html));
  for (const id of ['schlaf-block', 'schlaf-stand', 'schlaf-text', 'schlaf-abgleichen', 'schlaf-status']) {
    pruefe('index.html hat #' + id, html.includes('id="' + id + '"'));
  }
  pruefe('Empfänger global erreichbar', /window\.heyAgentSchlafEmpfangen\s*=\s*schlafEmpfangen/.test(src));
  pruefe('Checks-Fenster lädt auch den Schlaf', /typeof ladeSchlaf === 'function'/.test(appJs));
  pruefe('kein innerHTML', !/innerHTML/.test(src));

  console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
  process.exit(fehler ? 1 : 0);
})();
