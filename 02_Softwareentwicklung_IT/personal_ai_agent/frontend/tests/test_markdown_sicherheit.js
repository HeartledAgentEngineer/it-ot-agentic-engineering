// Markdown-Ausgabe ohne Skript-Einschleusung (P0, 12.10.2026) — GEGEN DEN ECHTEN Quelltext.
//
// Befund B5: parseMarkdown setzte Modellantworten roh in innerHTML. Ein
// <img src=x onerror=…> in einer Antwort lief als Skript und konnte den
// API-Schlüssel abgreifen; ein Anführungszeichen in einem Link brach aus dem
// href-Attribut aus. Jetzt wird alles außer Codeblöcken zuerst maskiert.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_markdown_sicherheit.js app.js
const fs = require('fs');
const src = fs.readFileSync(process.argv[2] || 'app.js', 'utf8');

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

// Bewusst KEIN document: escapeHtml muss ohne DOM auskommen.
eval(extractFn('escapeHtml'));
eval(extractFn('inlineMarkdown'));
eval(extractFn('tabelleZuHtml'));
eval(extractFn('codeBlockZuHtml'));
eval(extractFn('parseMarkdown'));
eval(extractFn('parseMarkdownPartial'));

/** Steht ein echtes (nicht maskiertes) Tag mit diesem Namen im HTML? */
const hatTag = (html, tag) => new RegExp('<' + tag + '[\\s>/]', 'i').test(html);
/** Alle href-Werte der erzeugten Links. */
const hrefs = (html) => [...html.matchAll(/<a href="([^"]*)"/g)].map(m => m[1]);
/** Ein Attribut, das mit on… beginnt, innerhalb eines echten Tags. */
const hatEventAttribut = (html) => /<[a-z][^>]*\son[a-z]+\s*=/i.test(html);

console.log('escapeHtml (rein, ohne DOM)');
pruefe('maskiert & < > " \'', escapeHtml('&<>"\'') === '&amp;&lt;&gt;&quot;&#39;', escapeHtml('&<>"\''));
pruefe('null und undefined werden leer', escapeHtml(null) === '' && escapeHtml(undefined) === '');
pruefe('Zahlen werden Text', escapeHtml(42) === '42');

console.log('Angriffe werden NICHT zu HTML');
let h = parseMarkdown('Hallo <img src=x onerror=alert(1)> Welt');
pruefe('<img onerror> bleibt Text', !hatTag(h, 'img') && h.includes('&lt;img'), h);
pruefe('kein on…-Attribut im img-Fall', !hatEventAttribut(h), h);

h = parseMarkdown('<script>alert(1)</script>');
pruefe('<script> bleibt Text', !hatTag(h, 'script') && h.includes('&lt;script&gt;'), h);

h = parseMarkdown('[x](https://a"onmouseover=alert(1))');
// Kein Markdown-Link; nur die Roh-URL davor wird verlinkt und endet vor &quot;.
pruefe('Markdown-Link mit " wird kein Link', !h.includes('>x</a>') && hrefs(h).join('|') === 'https://a', h);
pruefe('kein Ausbruch aus dem Attribut (Markdown-Link)', !hatEventAttribut(h), h);

h = parseMarkdown('https://a.de/"onmouseover=alert(1)');
pruefe('Roh-URL endet vor &quot;', hrefs(h).join('|') === 'https://a.de/', hrefs(h).join('|'));
pruefe('kein Ausbruch aus dem Attribut (Roh-URL)', !hatEventAttribut(h), h);

h = parseMarkdown("https://a.de/'onmouseover=alert(1)");
pruefe('Roh-URL endet vor &#39;', hrefs(h).join('|') === 'https://a.de/', hrefs(h).join('|'));

h = parseMarkdown('[klick](javascript:alert(1))');
pruefe('javascript:-Link wird kein Link', hrefs(h).length === 0 && !/href="javascript/i.test(h), h);

h = parseMarkdown('| A | B |\n|---|---|\n| <img src=x onerror=alert(1)> | ok |\n');
pruefe('HTML in Tabellenzelle bleibt Text', hatTag(h, 'table') && !hatTag(h, 'img') && h.includes('&lt;img'), h);

h = parseMarkdown("| Seite | B |\n|---|---|\n| https://x.de's | ok |\n");
pruefe('Apostroph in Tabellenzelle beendet die URL', hrefs(h).join('|') === 'https://x.de', hrefs(h).join('|'));

h = parseMarkdown('Text \u0000L0\u0000 und \u00000\u0000');
pruefe('Nullzeichen aus der Eingabe kann keinen Platzhalter fälschen', !h.includes('\u0000') && !h.includes('undefined'), JSON.stringify(h));

h = parseMarkdownPartial('Anfang\n```\n<img src=x onerror=alert(1)>');
pruefe('offener Codeblock (Stream) maskiert', !hatTag(h, 'img') && h.includes('&lt;img'), h);

h = parseMarkdown('```\n<b>fett?</b>\n```');
pruefe('HTML im Codeblock bleibt Text', h.includes('&lt;b&gt;fett?&lt;/b&gt;') && !hatTag(h, 'b'), h);

console.log('Gegenprobe: Auszeichnung funktioniert weiter');
pruefe('Fett', parseMarkdown('**fett**').includes('<strong>fett</strong>'));
pruefe('Kursiv', parseMarkdown('*kursiv*').includes('<em>kursiv</em>'));
pruefe('Code', parseMarkdown('`a < b`').includes('<code>a &lt; b</code>'));
pruefe('Liste', /<ul><li>eins<\/li>(?:<br>|\n)?<li>zwei<\/li><\/ul>/.test(parseMarkdown('- eins\n- zwei')));
h = parseMarkdown('| Kopf | Zwei |\n|---|---|\n| **a** | b |\n');
pruefe('Tabelle mit Fett in der Zelle', h.includes('<th>Kopf</th>') && h.includes('<td><strong>a</strong></td>'), h);
h = parseMarkdown('```diff\n--- a/x\n+++ b/x\n-alt\n+neu\n```');
pruefe('Diff-Zeilen behalten ihre Klassen', h.includes('<span class="d-plus">+neu</span>') && h.includes('<span class="d-minus">-alt</span>'), h);

console.log('Gegenprobe: Links und URL-Grenzen');
h = parseMarkdown('[Text](https://example.org/x)');
pruefe('Markdown-Link', h.includes('<a href="https://example.org/x" target="_blank" rel="noopener noreferrer">Text</a>'), h);
h = parseMarkdown('Siehe https://example.org/?a=1&b=2 dort');
pruefe('?a=1&b=2 bleibt ein Link', hrefs(h).join('|') === 'https://example.org/?a=1&amp;b=2', hrefs(h).join('|'));
h = parseMarkdown("Auf https://x.de's Seite");
pruefe("x.de's: Link endet vor &#39;", hrefs(h).join('|') === 'https://x.de' && h.includes('</a>&#39;s Seite'), h);
h = parseMarkdown('https://de.wikipedia.org/wiki/X_(Y)');
pruefe('Roh-URL mit Klammern bleibt ganz', hrefs(h).join('|') === 'https://de.wikipedia.org/wiki/X_(Y)', hrefs(h).join('|'));
h = parseMarkdown('[Wiki](https://de.wikipedia.org/wiki/X)');
pruefe('Markdown-Link endet an der schließenden Klammer', hrefs(h).join('|') === 'https://de.wikipedia.org/wiki/X', hrefs(h).join('|'));
h = parseMarkdown('www.example.org');
pruefe('www.-Adresse bekommt https://', hrefs(h).join('|') === 'https://www.example.org', hrefs(h).join('|'));

console.log('Weitere Senken (P0.7)');
pruefe('Rückfall ohne parseMarkdownPartial maskiert (sichtbar)', /:\s*escapeHtml\(sichtbar\)/.test(src));
pruefe('Rückfall ohne parseMarkdownPartial maskiert (antwort)', /parseMarkdownPartial\(antwort\)\s*:\s*escapeHtml\(antwort\)/.test(src));
pruefe('Nachrichtenzahl wird als Zahl gesetzt', /Number\(c\.message_count\)\s*\|\|\s*0/.test(src)
  && !/\$\{c\.message_count\}\s*Nachrichten`\s*\n?\s*\+/.test(src));
pruefe('kein onclick-Attribut in app.js', !/\sonclick\s*=\s*["']/i.test(src));

console.log(fehler === 0 ? '\nalle Prüfungen grün' : `\n${fehler} Prüfung(en) rot`);
process.exit(fehler === 0 ? 0 : 1);
