// Service Worker legt den API-Schlüssel nie im Cache ab (P0, 12.10.2026) — GEGEN DEN ECHTEN Quelltext.
//
// Seit P0 setzt der Server den Schlüssel als Meta-Feld in index.html ein. Der
// Service Worker legt HTML-Antworten als Offline-Hülle in den Cache — ohne
// diese Prüfung läge der Schlüssel dort dauerhaft auf dem Gerät.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_sw_schluessel.js sw.js
const fs = require('fs');
const src = fs.readFileSync(process.argv[2] || 'sw.js', 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

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

eval(extractFn('schluesselEntfernen'));

console.log('schluesselEntfernen');
const seite = '<head>\n<meta charset="UTF-8">\n'
  + '<meta name="agent-schluessel" content="GEHEIM-123&amp;x">\n<title>T</title>\n</head>';
const ohne = schluesselEntfernen(seite);
pruefe('Meta-Feld ist leer', ohne.includes('<meta name="agent-schluessel" content="">'), ohne);
pruefe('Schlüssel ist weg', !ohne.includes('GEHEIM-123'));
pruefe('übriger Text unverändert',
  ohne === seite.replace('content="GEHEIM-123&amp;x"', 'content=""'));
pruefe('Seite ohne Meta-Feld bleibt gleich', schluesselEntfernen('<p>x</p>') === '<p>x</p>');
pruefe('leeres Meta-Feld bleibt leer',
  schluesselEntfernen('<meta name="agent-schluessel" content="">')
  === '<meta name="agent-schluessel" content="">');

console.log('Cache-Liste und Fetch-Zweig');
const liste = (src.match(/const STATIC_ASSETS = \[([\s\S]*?)\];/) || [])[1] || '';
const eintraege = [...liste.matchAll(/'([^']*)'/g)].map(m => m[1]);
pruefe('STATIC_ASSETS gefunden', eintraege.length > 0);
pruefe("STATIC_ASSETS ohne '/'", !eintraege.includes('/'), eintraege.join(' '));
pruefe("STATIC_ASSETS ohne '/index.html'", !eintraege.includes('/index.html'), eintraege.join(' '));

const fetchStart = src.indexOf("addEventListener('fetch'");
const fetchTeil = fetchStart === -1 ? '' : src.slice(fetchStart);
const putStelle = fetchTeil.indexOf('cache.put(');
const entfStelle = fetchTeil.indexOf('schluesselEntfernen(');
pruefe('Fetch-Zweig legt Antworten ab', putStelle !== -1);
pruefe('HTML geht vor cache.put durch schluesselEntfernen', entfStelle !== -1 && entfStelle < putStelle);
pruefe('HTML wird am Content-Type erkannt', /text\/html/.test(fetchTeil));

const version = (src.match(/CACHE_NAME = 'personal-ai-agent-v(\d+)'/) || [])[1];
pruefe('CACHE_NAME höher als v17', Number(version) > 17, 'gefunden: v' + version);

console.log(fehler === 0 ? '\nalle Prüfungen grün' : `\n${fehler} Prüfung(en) rot`);
process.exit(fehler === 0 ? 0 : 1);
