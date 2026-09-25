// Konsistenz im Chat-Frontend (Fix 2026-09-25).
//
// Sebastian-Befund: „Ich habe den Chat geschlossen, dann einen alten Chat
// geöffnet oder einen neuen Chat geöffnet und dann aktualisiert gedrückt —
// und dann kam wieder was ganz anderes. Jetzt kommen auch schon wieder
// Bilder, die ich irgendwann schon mal hatte."
//
// Dieser Test prüft quelltext-nah, dass die Oberfläche
//   * die gemerkte Chat-Kennung wiederherstellt (nicht neu erzeugt),
//   * bei unbekannter Kennung NICHT stillschweigend einen fremden Verlauf
//     lädt, sondern klar meldet + den richtigen Chat anbietet,
//   * sichtbar anzeigt, WELCHER Chat offen ist,
//   * eine Bild-Vorschau an GENAU ihre Nachricht bindet (kein globaler
//     „letztes Bild"-Zustand),
//   * und einen spät eintreffenden Stream den offenen Chat nicht umschaltet.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_chat_konsistenz.js app.js               # NEU -> grün
//   git show HEAD:frontend/app.js > "$TMPDIR/alt_app.js"
//   node tests/test_chat_konsistenz.js "$TMPDIR/alt_app.js" # ALT -> rot
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

/** Rumpf einer Top-Level-Funktion: ab `function <name>` bis zur ersten
 *  schließenden Klammer in Spalte 0. Reicht für diese Datei (Stil: jedes
 *  Top-Level-`}` beginnt eine Zeile). */
function koerper(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start === -1) return '';
  const rest = src.slice(start);
  const ende = rest.indexOf('\n}');
  return ende === -1 ? rest : rest.slice(0, ende + 2);
}

// 1) Stabile Kennung: sie wird GEMERKT und wiederhergestellt — nie neu erzeugt.
pruefe('Kennung kommt aus dem Speicher (localStorage), nicht aus einer Zufalls-Erzeugung',
  /conversationId:\s*localStorage\.getItem\('conversation_id'\)/.test(src),
  'state.conversationId wird nicht mehr aus localStorage wiederhergestellt');
pruefe('keine automatische Vergabe neuer Chat-Nummern im Frontend',
  !/conv_\$\{|next_conversation_id/.test(src),
  'Frontend erzeugt selbst neue Chat-Kennungen');

// 2) Kein stiller Rückfall auf einen fremden Verlauf.
const wiederher = koerper('stelleVerlaufWiederHer');
pruefe('stelleVerlaufWiederHer ruft NICHT mehr die „jüngste" Kennung als Rückfall',
  wiederher.length > 0 && !/letzteGespraechsId\s*\(/.test(wiederher),
  'stiller Rückfall auf das jüngste Gespräch ist noch vorhanden');
pruefe('stelleVerlaufWiederHer lädt zuerst die gemerkte Kennung',
  /state\.conversationId/.test(wiederher) && /zeigeGespraech\(state\.conversationId\)/.test(wiederher));
pruefe('Ladefehler wird ehrlich gemeldet statt fremder Verlauf angezeigt',
  /zeigeVerlaufLadefehler\s*\(/.test(wiederher));

// 3) Unbekannte Kennung: klare Meldung, kein fremder Inhalt.
const zeige = koerper('zeigeGespraech');
pruefe('zeigeGespraech erkennt 404 und zeigt die klare Meldung',
  /res\.status === 404/.test(zeige) && /zeigeChatNichtGefunden\(/.test(zeige));
pruefe('die Meldung sagt klar, dass der Chat leer/nicht gefunden ist',
  src.includes('Dieser Chat ist leer bzw. nicht gefunden'));
pruefe('die Meldung verspricht ausdrücklich KEINEN fremden Verlauf',
  /kein anderer/.test(src) && /Verlauf angezeigt/.test(src));
const nichtGefunden = koerper('zeigeChatNichtGefunden');
pruefe('tote Kennung wird nicht weitergeschleppt (localStorage geräumt)',
  /localStorage\.removeItem\('conversation_id'\)/.test(nichtGefunden));
pruefe('der richtige Chat lässt sich aus der Meldung heraus öffnen',
  /zeigeGespraech\(c\.id\)/.test(nichtGefunden));

// 4) Die vom SERVER aufgelöste Kennung ist die Wahrheit.
pruefe('Server-Kennung wird übernommen (daten.id), nicht die angefragte',
  /const idServer = daten\.id \|\| id;/.test(zeige) && /state\.conversationId = idServer;/.test(zeige));

// 5) Sichtbare Chat-Kennzeichnung.
pruefe('setzeChatAnzeige() existiert', /function setzeChatAnzeige\(/.test(src));
pruefe('die Anzeige wird beim Öffnen eines Chats gesetzt',
  /setzeChatAnzeige\(idServer/.test(zeige));
pruefe('die Anzeige wird beim Chat-Wechsel gesetzt',
  /function chatWechseln\(/.test(src) && /setzeChatAnzeige\(g\)/.test(koerper('chatWechseln')));
pruefe('index.html hat das sichtbare Feld #chat-aktuell',
  /id="chat-aktuell"/.test(html),
  'Platzhalter für die Chat-Kennzeichnung fehlt in index.html');
pruefe('die Anzeige nennt Kennung + Nachrichten-Zahl (nicht nur ein Symbol)',
  /Nachrichten/.test(koerper('setzeChatAnzeige')) && /formatUhrzeit/.test(koerper('setzeChatAnzeige')));

// 6) Bilder gehören zur Nachricht — kein globaler „letztes Bild"-Zustand.
const vorschau = koerper('zeigeBildVorschau');
pruefe('die Vorschau wird an die Nachricht gebunden (dataset.bildPfad)',
  /container\.dataset\.bildPfad = pfad/.test(vorschau),
  'Bindung Vorschau<->Nachricht fehlt');
pruefe('kein globaler „letztes Bild"-Zustand im Code',
  !/state\.letztesBild|_letztesBild|state\.letzterBildPfad/.test(src),
  'globaler Bild-Zustand gefunden');
pruefe('Bild-Vorschau nur für den Chat, aus dem die Antwort kam',
  /abschluss\.bild_vorschau && \(!cid \|\| state\.conversationId === cid\)/.test(src));
pruefe('der RAM-Cache wird beim Verlassen/Start verworfen',
  /function verwerfeBildCache\(/.test(src)
  && /verwerfeBildCache\(state\.conversationId \|\| undefined\)/.test(koerper('chatWechseln'))
  && /verwerfeBildCache\(\);/.test(src));
pruefe('der Cache-Endpunkt des Backends wird gerufen',
  src.includes('/api/chat/bild-cache/verwerfen'));

// 7) Ein spät eintreffender Stream schaltet den offenen Chat nicht um.
pruefe('finishReply kennt den Chat der Anfrage (_sendChatId)',
  /_sendChatId/.test(koerper('finishReply')) && /let _sendChatId = null;/.test(src));
pruefe('die Kennung wird nur bei passendem Chat übernommen',
  /passtZumOffenenChat/.test(koerper('finishReply')));

// 8) Kein Doppel-Rendern durch überholende Ladevorgänge.
pruefe('Reentranz-Schutz für den Verlauf-Aufbau ist vorhanden',
  /let _gespraechToken = 0;/.test(src) && /const token = \+\+_gespraechToken;/.test(zeige));

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
