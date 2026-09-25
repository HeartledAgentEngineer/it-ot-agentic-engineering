// Selbsttest-Blatt: Umwandlung JSON -> Klartext (25.09.2026).
//
// Auftrag (Sebastian): Der Zustand des Systems soll OHNE Kabel ablesbar und
// als Bildschirmfoto teilbar sein. Das Blatt darf nichts erfinden und nichts
// verschweigen — fehlende Quellen müssen als ✗/⚠ erscheinen, nicht als leere
// Zeile und nicht als Absturz.
//
// Dieser Test prüft:
//   * die REINE Funktion selbsttestText() wird aus dem echten app.js
//     ausgeschnitten und in einer Stub-Umgebung ausgeführt (wie
//     test_quiz_geo.js) — es wird nichts nachgebaut,
//   * vollständige Daten -> ✓-Zeilen mit den echten Zahlen,
//   * FEHLENDE Felder -> kein Absturz, ✗/⚠ statt Lücke,
//   * Warnzeichen ⚠ bei auffälligem Zustand (Daemon aus, Zählfehler),
//   * das Blatt hängt an der Kopfzeile, lädt /api/selbsttest und pollt NICHT.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_selbsttest.js app.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || 'app.js';
const src = fs.readFileSync(pfadApp, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadApp));
let html = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}

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

// Die reine Funktion aus dem ECHTEN Quelltext laden und ausführen.
eval(extractFn('selbsttestText'));

console.log('\n1) Vollständige Daten -> ✓-Zeilen mit echten Zahlen');
const gesund = {
  commit: { ok: true, zeile: 'abc1234 Selbsttest eingebaut', error: null },
  index: { pfad: '/home/x/archiv_index.db', existiert: true, groesse_mb: 263.4,
           nachrichten: 1234, chunks: 5678, error: null },
  daemon: { laeuft: true, log_pfad: '/home/x/hermes_inbox/daemon.log',
            log_groesse_bytes: 2048, log_alter_s: 12.6,
            log_letzte_zeilen: ['Zeile A', 'Zeile B', 'Zeile C'], error: null },
  letzte_antwort: {
    antworten: { pfad: '/a', existiert: true, zeilen: 3, laenge: 42, auszug: '{"ok":true}', error: null },
    status: { pfad: '/s', existiert: true, zeilen: 5, laenge: 12, auszug: 'laeuft', error: null },
  },
  gedaechtnis: { anzahl: 42, error: null },
  sprache: { modelle: ['microsoft/mai-transcribe-2', 'openai/whisper-large-v3'],
             transcribe_registriert: true, speak_registriert: true, error: null },
  uhrzeit: { iso: '2026-09-25T14:03:11+02:00', lokal: '25.09.2026 14:03:11', zeitzone: 'CEST', error: null },
};
const text = selbsttestText(gesund);
pruefe('Kopfzeile trägt die Serverzeit', text.split('\n')[0].includes('25.09.2026 14:03:11'));
pruefe('Serverzeit mit Zeitzone', text.split('\n')[0].includes('CEST'));
pruefe('Commit erscheint als ✓ mit Kurz-Hash', /✓ Commit: abc1234 Selbsttest eingebaut/.test(text));
pruefe('Archiv-Index nennt MB, Nachrichten und Abschnitte',
  /✓ Archiv-Index: 263\.4 MB · 1234 Nachrichten · 5678 Abschnitte/.test(text));
pruefe('Daemon erscheint als ✓ „läuft"', /✓ Inbox-Daemon: läuft/.test(text));
pruefe('Log-Größe, Alter und letzte Zeile stehen dabei',
  text.includes('Log 2 KB') && text.includes('zuletzt vor 13 s') && text.includes('letzte Zeile: Zeile C'));
pruefe('Letzte Antwort mit Zeilen/Zeichen/Auszug',
  /✓ Letzte antworten\.jsonl: 3 Zeilen · 42 Zeichen/.test(text) && text.includes('„{"ok":true}“'));
pruefe('Erinnerungszahl steht da', /✓ Erinnerungen: 42/.test(text));
pruefe('Sprachkette wird mit Pfeil verbunden',
  text.includes('microsoft/mai-transcribe-2 → openai/whisper-large-v3'));
pruefe('Registrierte Sprachwege erscheinen', text.includes('Erkennung ✓') && text.includes('Sprachausgabe ✓'));
pruefe('kein ✗ und kein ⚠ im gesunden Zustand', !text.includes('✗') && !text.includes('⚠'), text);

console.log('\n2) Fehlende Felder -> kein Absturz, ✗/⚠ statt Lücke');
let leerText = '';
let geworfen = false;
try { leerText = selbsttestText({}); } catch (e) { geworfen = true; }
pruefe('leeres Objekt wirft NICHT', geworfen === false);
pruefe('Commit fehlt -> ✗ „nicht ermittelbar"', /✗ Commit: nicht ermittelbar/.test(leerText));
pruefe('Archiv-Index fehlt -> ✗', /✗ Archiv-Index: fehlt/.test(leerText));
pruefe('Daemon unbekannt -> ⚠ „nicht feststellbar"', /⚠ Inbox-Daemon: nicht feststellbar/.test(leerText));
pruefe('unbekannte Zahlen werden „?" statt NaN',
  leerText.includes('Erinnerungen: ?') && !leerText.includes('NaN') && !leerText.includes('undefined'));
pruefe('auch null und Text als Eingabe sind harmlos',
  (() => { try { selbsttestText(null); selbsttestText('quatsch'); selbsttestText(undefined); return true; }
           catch (e) { return false; } })());
pruefe('Kopfzeile bleibt vorhanden (Serverzeit unbekannt)',
  leerText.split('\n')[0].includes('Serverzeit: unbekannt'));

console.log('\n3) Warnzeichen ⚠ bei auffälligem Zustand');
const daemonAus = JSON.parse(JSON.stringify(gesund));
daemonAus.daemon.laeuft = false;
const ausText = selbsttestText(daemonAus);
pruefe('Daemon aus -> ⚠ und „läuft NICHT"', /⚠ Inbox-Daemon: läuft NICHT/.test(ausText));
pruefe('Daemon aus ist NICHT mehr ✓', !/✓ Inbox-Daemon/.test(ausText));

const indexWarn = JSON.parse(JSON.stringify(gesund));
indexWarn.index.error = 'Datenbank nicht lesbar (OperationalError)';
const warnText = selbsttestText(indexWarn);
pruefe('Index mit Zählfehler -> ⚠, aber Größe bleibt genannt',
  /⚠ Archiv-Index: 263\.4 MB/.test(warnText) && warnText.includes('Datenbank nicht lesbar'));
pruefe('Zählfehler ist NICHT als ✗ gemeldet', !/✗ Archiv-Index/.test(warnText));

const gedWarn = JSON.parse(JSON.stringify(gesund));
gedWarn.gedaechtnis = { anzahl: null, error: 'Gedächtnis nicht lesbar (RuntimeError)' };
pruefe('Erinnerungen mit Fehler -> ✗ mit Begründung',
  /✗ Erinnerungen: \? · Gedächtnis nicht lesbar/.test(selbsttestText(gedWarn)));

const antwortWarn = JSON.parse(JSON.stringify(gesund));
antwortWarn.letzte_antwort.antworten = { pfad: '/a', existiert: false, zeilen: null, laenge: null, auszug: null, error: 'antworten.jsonl fehlt' };
pruefe('fehlende antworten.jsonl -> ✗ mit Dateinamen',
  /✗ Letzte antworten\.jsonl: antworten\.jsonl fehlt/.test(selbsttestText(antwortWarn)));

const sprachWarn = JSON.parse(JSON.stringify(gesund));
sprachWarn.sprache.transcribe_registriert = false;
pruefe('nicht registrierter Sprachweg -> „Erkennung ✗"',
  selbsttestText(sprachWarn).includes('Erkennung ✗'));

console.log('\n4) Blatt in der Oberfläche (Knopf, Blatt, Laden, KEIN Auto-Polling)');
pruefe('index.html hat den Selbsttest-Knopf in der Kopfzeile',
  /id="selbsttest-btn"/.test(html) && html.indexOf('id="selbsttest-btn"') < html.indexOf('id="chat-sheet"'));
pruefe('index.html hat das Selbsttest-Blatt mit Textfeld und Aktualisieren',
  /id="selbsttest-sheet"/.test(html) && /id="selbsttest-text"/.test(html)
  && /id="selbsttest-reload"/.test(html) && /Aktualisieren/.test(html));
pruefe('der Knopf öffnet das Blatt', /dom\.selbsttestBtn\.addEventListener\('click', oeffneSelbsttestBlatt\)/.test(src));
pruefe('das Blatt holt GET /api/selbsttest', /fetch\(`\$\{API_BASE\}\/api\/selbsttest`\)/.test(src));
pruefe('Anzeige läuft über selbsttestText(daten)', /zeigeSelbsttest\(selbsttestText\(daten\)\)/.test(src));
pruefe('Anzeige per textContent (kein innerHTML -> keine Injektion)',
  /dom\.selbsttestText\.textContent = klartext/.test(src));
pruefe('Aktualisieren ruft ladeSelbsttest erneut', /dom\.selbsttestReload\.addEventListener\('click', ladeSelbsttest\)/.test(src));
pruefe('KEIN Auto-Polling des Selbsttests',
  !/setInterval\([^)]*ladeSelbsttest/.test(src) && !/setInterval\([^)]*Selbsttest/.test(src));
pruefe('Schließen über × und Hintergrund ist verdrahtet',
  /dom\.selbsttestClose\.addEventListener\('click', schliesseSelbsttestBlatt\)/.test(src)
  && /if \(e\.target === dom\.selbsttestSheet\) schliesseSelbsttestBlatt\(\)/.test(src));
pruefe('Escape schließt auch das Selbsttest-Blatt',
  /e\.key === 'Escape' && dom\.selbsttestSheet/.test(src));

console.log('\n5) Datenschutz & Cache-Bump');
pruefe('kein CDN/keine externe Quelle im Frontend',
  !/<script[^>]+src="https?:/.test(html) && !/<link[^>]+href="https?:/.test(html));
pruefe('kein API-Schlüssel im Frontend', !/sk-or-v1-/.test(src) && !/sk-or-v1-/.test(html));
pruefe('index.html lädt app.js mit ?v=20260925F', /app\.js\?v=20260925F/.test(html), 'Cache-Bump fehlt');
pruefe('index.html lädt style.css mit ?v=20260925E', /style\.css\?v=20260925E/.test(html), 'Cache-Bump fehlt');

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
