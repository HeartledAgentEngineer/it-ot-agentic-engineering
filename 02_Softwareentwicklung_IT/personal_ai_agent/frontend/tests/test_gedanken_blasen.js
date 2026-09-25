// Gedanken-Blasen: einklappen nach dem Textende + keine leeren Blasen.
//
// Auftrag (Sebastian, 25.09.2026):
//   1) Blasen vom Typ „🧠 Gedanke" klappen — Blase für Blase — von selbst ein,
//      NACHDEM ihr Text fertig getippt ist. Sichtbar bleibt eine schmale Zeile
//      (Zeit + 🧠 + Kurzfassung); Antippen klappt sie wieder auf. Beim
//      Einklappen darf der Verlauf nicht springen.
//   2) Keine leeren Blasen: Blase erst mit echtem Text zeigen, Zeitstempel und
//      Symbol erst mit dem ersten Textzeichen rendern.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_gedanken_blasen.js app.js
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
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Rumpf einer Top-Level-Funktion: ab `function <name>` bis zur ersten
 *  schließenden Klammer in Spalte 0 (Stil dieser Datei). */
function koerper(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start === -1) return '';
  const rest = src.slice(start);
  const ende = rest.indexOf('\n}');
  return ende === -1 ? rest : rest.slice(0, ende + 2);
}

// ── 1) Einklappen nach dem Textende ────────────────────────────────────────

const ein = koerper('klappeGedankeEin');
const aus = koerper('klappeGedankeAus');
const gedanke = koerper('fuegeGedankeMitAbbruchHinzu');
const kurz = koerper('gedankeKurzfassung');
const pos = koerper('mitGehaltenerScrollposition');

pruefe('Einklappen existiert (klappeGedankeEin) und setzt eine Zustandsklasse',
  /function klappeGedankeEin\(/.test(src)
  && /classList\.add\('gedanken-eingeklappt'\)/.test(ein));
pruefe('Aufklappen existiert (klappeGedankeAus)',
  /function klappeGedankeAus\(/.test(src)
  && /classList\.remove\('gedanken-eingeklappt'\)/.test(aus));
pruefe('es wird kurz gewartet, dann sanft geschrumpft (Konstante vorhanden)',
  /const GEDANKE_EINKLAPPEN_MS\s*=\s*\d+/.test(src)
  && /setTimeout\(/.test(gedanke) && /klappeGedankeEin\(div\)/.test(gedanke),
  'kein zeitgesteuertes Einklappen gefunden');
pruefe('eingeklappt bleibt eine schmale Zeile: Zeit + 🧠 + Kurzfassung',
  /'🧠 '/.test(ein) && /gedankeKurzfassung\(/.test(ein)
  && /dataset\.gedankeZeit/.test(ein) && /gedanken-kurz/.test(ein));
pruefe('Kurzfassung = erste Zeile, gekürzt (mit …)',
  /split\('\\n'\)/.test(kurz) && /find\(Boolean\)/.test(kurz)
  && /GEDANKE_KURZ_MAX/.test(kurz) && /…/.test(kurz));
pruefe('Antippen klappt wieder auf — und die Blase bleibt dann offen',
  /div\.addEventListener\('click'/.test(gedanke)
  && /klappeGedankeAus\(div\)/.test(gedanke)
  && /gedankeManuell/.test(gedanke));
pruefe('kein automatisches Einklappen gegen den Nutzerwunsch',
  /if \(div\.dataset\.gedankeManuell !== '1'\) klappeGedankeEin\(div\)/.test(gedanke));

// Einklappen erst NACH dem vollständigen Tippen (nicht vorher).
const posWartend = src.indexOf("_gedankenTippWartend = Math.max(0, _gedankenTippWartend - 1)");
const posEinklappen = src.indexOf('GEDANKE_EINKLAPPEN_MS', posWartend);
pruefe('eingeklappt wird erst nach dem letzten getippten Zeichen',
  posWartend !== -1 && posEinklappen > posWartend,
  'Einklappen hängt nicht am Ende der Tipp-Kette');

// Scrollposition halten — kein Sprung/Ruckeln.
pruefe('Scrollposition wird gehalten (verschwundene Höhe genau einmal ausgeglichen)',
  /let letzteHoehe = el\.scrollHeight/.test(pos)
  && /const weggefallen = letzteHoehe - hoehe/.test(pos)
  && /el\.scrollTop = ziel/.test(pos)
  && /isAtBottom\(\)/.test(pos));
pruefe('doppeltes Abziehen ist ausgeschlossen (Bezugswert läuft mit)',
  /letzteHoehe = hoehe;/.test(pos) && /letzterScroll = ziel;/.test(pos)
  && /selbstGeklemmt/.test(pos), 'Bezugswert wird nicht nachgeführt');
pruefe('wer unten steht, bleibt unten',
  /if \(warUnten\) \{ scrollToBottom\(true\); return; \}/.test(pos));
pruefe('das Einklappen nutzt den Positions-Schutz',
  /mitGehaltenerScrollposition\(/.test(ein) && /mitGehaltenerScrollposition\(/.test(aus));
pruefe('nach der Schrumpf-Animation wird nachgezogen (kein Rest-Sprung)',
  /addEventListener\('transitionend', ausgleich/.test(ein) && /setTimeout\(ausgleich/.test(ein));
pruefe('sanftes Schrumpfen ist im Stylesheet (Übergang auf .gedanken-inhalt)',
  /\.gedanken-inhalt[\s\S]{0,400}transition:\s*max-height/.test(css),
  'CSS-Übergang fehlt');
pruefe('eingeklappter Zustand ist gestylt (Kurzzeile sichtbar, Rest aus)',
  /\.gedanken-eingeklappt \.gedanken-kurz[\s\S]{0,80}display:\s*block/.test(css)
  && /\.gedanken-eingeklappt \.gedanken-inhalt[\s\S]{0,120}max-height:\s*0/.test(css));

// ── 2) Keine leeren Blasen ─────────────────────────────────────────────────

const add = koerper('addMessage');
const zeige = koerper('zeigeBlaseMitText');
pruefe('leere Live-Blase wird als solche erkannt',
  /const _liveLeer = _ohneInhalt && zeit === undefined && role === 'assistant'/.test(add));
pruefe('leere Live-Blase bleibt verborgen, bis Text da ist',
  /if \(_liveLeer\) div\.hidden = true;/.test(add)
  && /div\.hidden = false;/.test(zeige));
pruefe('Zeitstempel entsteht erst mit dem ersten Textzeichen (nicht vorher)',
  /zeitDiv\.hidden = true;/.test(add) && /zeitDiv\.dataset\.lazyZeit = '1';/.test(add)
  && /\[data-lazy-zeit="1"\]/.test(zeige)
  && /zeit\.hidden = false;/.test(zeige));
pruefe('Datumspille wird aufgeschoben statt allein zu stehen',
  /div\.dataset\.bannerIso = bannerIso;/.test(add)
  && /insertBefore\(baueDatumBanner\(bannerIso\), div\)/.test(zeige));
pruefe('Gedanken-Blase: 🧠-Kopf und Zeitstempel starten verborgen',
  /kopf\.hidden = true;/.test(gedanke) && /zeitSpan\.hidden = true;/.test(gedanke));
pruefe('Gedanken-Blase: Symbol/Zeit erscheinen mit dem ERSTEN Zeichen',
  /if \(i === 0\)[\s\S]{0,300}kopf\.hidden = false;/.test(gedanke)
  && /if \(i === 0\)[\s\S]{0,300}zeitSpan\.hidden = false;/.test(gedanke));
pruefe('Gedanken-Blase entsteht gar nicht erst ohne Text',
  /const rein = String\(text \|\| ''\)\.replace[\s\S]{0,120}if \(!rein\) return;/.test(gedanke));
pruefe('Hermes-Stream zeigt keinen leeren Kasten mehr (kein „…"-Platzhalter)',
  !/ph\.textContent = '…'/.test(src)
  && /zeigeBlaseMitText\(_hermesBlase, contentDiv, antwort\)/.test(src));
pruefe('normale Antwort-Blase wird nur mit echtem Inhalt gezeigt',
  /if \(\(antwort \|\| ''\)\.trim\(\)\) zeigeAntwortBlase\(\);/.test(src)
  && /zeigeBlaseMitText\(_antwortBlase, null, null\)/.test(src));
pruefe('Sichtbarkeits-Garantie in finishReply nutzt denselben Weg',
  /zeigeBlaseMitText\(_blaseAussen, null, null\)/.test(koerper('finishReply')));
pruefe('Aufräumen leerer Blasen bleibt als letzter Riegel erhalten',
  /if \(!inhalt\) \{ try \{ m\.remove\(\); \} catch \(_e\) \{\} \}/.test(src));

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
