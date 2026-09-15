// Testet die Diff-Darstellung von Codeblöcken GEGEN DEN ECHTEN Quelltext.
//
// Gemeldeter Fall (Sebastian 2026-09-15): „Das Einzige, was noch gefehlt hat,
// ist bestimmte Code-Schnipsel anzuzeigen, plus minus." Ein ```diff-Block stand
// bisher wie jeder andere Codeblock als grauer Block da — Hinzufügung und
// Löschung waren nicht unterscheidbar.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_diff_darstellung.js app.js                 # NEU -> grün
//   git show HEAD:frontend/app.js > "$TMPDIR/alt_app.js"
//   node tests/test_diff_darstellung.js "$TMPDIR/alt_app.js"   # ALT -> rot
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

function extractFn(name, pflicht = true) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) {
    if (pflicht) throw new Error('nicht gefunden: ' + name);
    return '';
  }
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

function makeEl(tag) {
  const el = {
    tagName: tag, _text: '',
    appendChild(c) { return c; },
    set textContent(v) { el._text = v; },
    get textContent() { return el._text; },
  };
  Object.defineProperty(el, 'innerHTML', {
    get() {
      return String(el._text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
  });
  return el;
}
global.document = { createElement: makeEl };

eval(extractFn('escapeHtml'));
eval(extractFn('inlineMarkdown', false));
eval(extractFn('tabelleZuHtml', false));
eval(extractFn('codeBlockZuHtml', false));
eval(extractFn('parseMarkdown'));

const diffText = [
  'Hier der Patch:',
  '```diff',
  '--- a/app.js',
  '+++ b/app.js',
  '@@ -1,3 +1,3 @@',
  ' const a = 1;',
  '-const alt = 2;',
  '+const neu = 2;',
  '```',
].join('\n');
const html = parseMarkdown(diffText);

pruefe('Diff-Block wird als pre.diff ausgegeben', html.includes('<pre class="diff">'), html.slice(0, 120));
pruefe('Hinzufügung bekommt d-plus', /class="d-plus">\+const neu/.test(html));
pruefe('Löschung bekommt d-minus', /class="d-minus">-const alt/.test(html));
pruefe('Hunk-Kopf bekommt d-hunk', /class="d-hunk">@@/.test(html));
pruefe('Dateikopfzeilen bekommen d-kopf', html.includes('class="d-kopf"'));
pruefe('Kontextzeile bekommt d-kontext', /class="d-kontext"> const a = 1;/.test(html));
pruefe('kein rohes ``` mehr sichtbar', !html.includes('```'));

// Normaler Codeblock bleibt unverändert ein <pre><code> ohne Diff-Klassen.
const jsHtml = parseMarkdown('```js\nconst x = 1;\n```');
pruefe('normaler Codeblock bleibt <pre><code>', jsHtml.includes('<pre><code>const x = 1;</code></pre>'), jsHtml);
pruefe('normaler Codeblock hat keine Diff-Klassen', !jsHtml.includes('d-plus'));

// Escaping: Markup im Code darf nie als HTML landen (kein Injektionsweg).
const boese = parseMarkdown('```diff\n+<img src=x onerror=alert(1)>\n```');
pruefe('HTML im Diff wird escaped', !boese.includes('<img') && boese.includes('&lt;img'));
pruefe('escaptes HTML bleibt als Hinzufügung erkennbar', boese.includes('class="d-plus"'));

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
