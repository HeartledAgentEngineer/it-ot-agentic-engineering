// Sprachaufnahme im Chat-Frontend (25.09.2026).
//
// Auftrag (Sebastian): „Mikrofon-Knopf im Chat, Aufnahme, Upload an das
// Backend, Text ins Eingabefeld, Zustand sichtbar, Antwort optional vorlesen."
//
// Dieser Test prüft quelltext-nah, dass die Oberfläche
//   * den Mikrofon-Knopf im Eingabebereich hat und ihn verdrahtet,
//   * wirklich aufnimmt (getUserMedia + AudioWorklet) und eine WAV-Datei
//     (PCM 16 Bit) baut — bewusst NICHT über MediaRecorder, weil der Anbieter
//     WebM/Opus mit HTTP 400 ablehnt,
//   * das Audio als multipart/form-data an POST /api/sprache/transkript gibt,
//   * den erkannten Text sichtbar in das Eingabefeld setzt,
//   * den Zustand sichtbar anzeigt („Mikrofon offen", „hört zu",
//     „denkt nach", „spricht") statt nur im Tooltip,
//   * die Antwort über die Browser-Stimme vorlesen kann (SpeechSynthesis),
//   * ohne neue Abhängigkeit auskommt (kein CDN, kein Framework) und
//     weiterhin für das Handy gebaut ist.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_sprachaufnahme.js app.js
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
 *  schließenden Klammer in Spalte 0 (Stil dieser Datei). */
function koerper(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start === -1) return '';
  const rest = src.slice(start);
  const ende = rest.indexOf('\n}');
  return ende === -1 ? rest : rest.slice(0, ende + 2);
}

/** Block einer const-Deklaration: ab `const <name>` bis zum ersten `};`. */
function block(name) {
  const start = src.indexOf('const ' + name);
  if (start === -1) return '';
  const rest = src.slice(start);
  const ende = rest.indexOf('};');
  return ende === -1 ? rest : rest.slice(0, ende + 2);
}

// 1) Mikrofon-Knopf im Eingabebereich
pruefe('index.html hat den Mikrofon-Knopf IM Eingabebereich',
  html.indexOf('id="input-area"') !== -1 && html.indexOf('id="mic-btn"') > html.indexOf('id="input-area"'),
  '#mic-btn fehlt oder liegt außerhalb von #input-area');
pruefe('der Knopf startet und stoppt die Aufnahme',
  /dom\.micBtn\.addEventListener\('click'/.test(src)
  && /startRecording\(\)/.test(src) && /stopRecording\(\)/.test(src));

// 2) Aufnahme: Mikrofon + WAV (PCM 16)
const start = koerper('startRecording');
pruefe('Aufnahme holt das Mikrofon (getUserMedia)',
  /navigator\.mediaDevices\.getUserMedia/.test(start),
  'getUserMedia fehlt in startRecording');
pruefe('Aufnahme läuft über den AudioWorklet',
  /audioWorklet\.addModule\('pcm-recorder\.js'\)/.test(start)
  && /new AudioWorkletNode\(audioContext, 'pcm-recorder'\)/.test(start));
pruefe('Mikrofon wird beim Stoppen wieder freigegeben',
  /getTracks\(\)\.forEach\(track => track\.stop\(\)\)/.test(koerper('releaseAudioStream')));
const wav = koerper('encodeWav');
pruefe('WAV-Datei wird selbst gebaut (RIFF/WAVE, PCM 16 Bit, Mono)',
  /'RIFF'/.test(wav) && /'WAVE'/.test(wav)
  && /setUint16\(22, 1, true\)/.test(wav) && /setUint16\(34, 16, true\)/.test(wav)
  && /type: 'audio\/wav'/.test(wav));
pruefe('bewusst KEIN MediaRecorder (WebM/Opus wird vom Anbieter abgelehnt)',
  !/new MediaRecorder/.test(src) && /MediaRecorder liefert nur WebM\/Opus/.test(src),
  'MediaRecorder im Code oder Begründung fehlt');

// 3) Upload an das Backend (multipart/form-data)
const sendung = koerper('sendAudioForTranscription');
pruefe('Audio geht als multipart/form-data an POST /api/sprache/transkript',
  /new FormData\(\)/.test(sendung)
  && /formData\.append\('file', audioBlob, 'audio\.wav'\)/.test(sendung)
  && /\/api\/sprache\/transkript/.test(sendung)
  && /method: 'POST'/.test(sendung));
pruefe('der alte Pfad wird nicht mehr gerufen',
  !/api\/transcribe/.test(src),
  'app.js ruft noch /api/transcribe');

// 4) Der erkannte Text landet im Eingabefeld
const setze = koerper('setzeEingabe');
pruefe('setzeEingabe() schreibt in das Eingabefeld',
  setze.length > 0 && /dom\.input\.value = text/.test(setze),
  'Hilfsfunktion setzeEingabe fehlt');
pruefe('das Diktat wird über setzeEingabe() in die Eingabe gesetzt',
  /setzeEingabe\(gesamt\)/.test(sendung));
pruefe('vorhandener Text wird angehängt, nicht ersetzt',
  /const vorhanden = dom\.input\.value\.trim\(\)/.test(sendung)
  && /vorhanden \+ ' ' : ''\) \+ diktat/.test(sendung));
pruefe('leere Erkennung wird ehrlich gemeldet (kein erfundener Text)',
  /Spracherkennung fehlgeschlagen/.test(sendung) && /data\.error/.test(sendung));

// 5) Sichtbarer Zustand: Mikrofon offen / hört zu / denkt nach / spricht
pruefe('index.html hat die sichtbare Zustandszeile #mic-status',
  /id="mic-status"/.test(html) && /role="status"/.test(html),
  'Zustandszeile fehlt in index.html');
const status = block('MIC_STATUS');
for (const wort of ['Mikrofon offen', 'hört zu', 'denkt nach', 'spricht']) {
  pruefe('Zustandstext vorhanden: „' + wort + '"', status.includes(wort));
}
pruefe('der Zustand wird sichtbar geschrieben (nicht nur in den Tooltip)',
  /dom\.micStatus\.textContent = eintrag\.text/.test(koerper('setMicStatus'))
  && /dom\.micStatus\.hidden = !eintrag\.text/.test(koerper('setMicStatus')));
pruefe('„hört zu" kommt erst, wenn wirklich Audioblöcke eintreffen',
  /setMicStatus\('hoert_zu'\)/.test(src) && /pcmChunks\.push\(event\.data\)/.test(src));
pruefe('während Erkennung/Glättung steht „denkt nach"',
  /setMicStatus\('transcribing'\)/.test(sendung) && /setMicStatus\('polishing'\)/.test(sendung));
pruefe('die Zustandszeile ist im Ruhezustand versteckt',
  /dom\.micStatus\.hidden = !eintrag\.text/.test(koerper('setMicStatus'))
  && /id="mic-status"[^>]*hidden/.test(html));

// 6) Antwort optional vorlesen (Browser-Sprachausgabe)
const sprechen = koerper('speakResponse');
pruefe('Browser-Stimme wird benutzt (SpeechSynthesis, deutsch)',
  /new SpeechSynthesisUtterance\(plainText\)/.test(sprechen)
  && /utterance\.lang = 'de-DE'/.test(sprechen)
  && /window\.speechSynthesis\.speak\(utterance\)/.test(sprechen));
pruefe('„spricht" wird beim Vorlesen gesetzt und danach zurückgenommen',
  /utterance\.onstart = \(\) => setMicStatus\('spricht'\)/.test(sprechen)
  && /utterance\.onend = \(\) => setMicStatus\(''\)/.test(sprechen));
pruefe('Vorlesen ist OPTIONAL (Knopf an der Antwort, kein Automatik-Zwang)',
  /function addSpeakControls\(/.test(src) && src.includes('Audio vorlesen'));

// 7) Keine neue Abhängigkeit, mobil, kein Secret
pruefe('kein CDN/keine externe Quelle im Frontend',
  !/<script[^>]+src="https?:/.test(html) && !/<link[^>]+href="https?:/.test(html));
pruefe('kein Framework/Modul-Import in app.js',
  !/^\s*import\s/m.test(src) && !/require\(/.test(src));
pruefe('mobil gebaut (viewport-Meta vorhanden)',
  /name="viewport"/.test(html));
pruefe('kein API-Schlüssel im Frontend',
  !/sk-or-v1-/.test(src) && !/sk-or-v1-/.test(html));

// 8) Cache-Bump (Pflicht bei Frontend-Änderungen)
pruefe('index.html lädt app.js mit ?v=20260925F',
  /app\.js\?v=20260925F/.test(html), 'Cache-Bump fehlt');
pruefe('index.html lädt style.css mit ?v=20260925E',
  /style\.css\?v=20260925E/.test(html), 'Cache-Bump für style.css fehlt');

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);
