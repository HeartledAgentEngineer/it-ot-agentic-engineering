# Changelog 2026-09-25 — Sprachaufnahme im Chat sichtbar und vollständig

Auftrag (Sebastian): Mikrofon-Knopf im Chat-Eingabebereich, Aufnahme, Upload an
das Backend zur Transkription, Text landet im Eingabefeld, **sichtbarer Zustand**,
Antwort optional vorlesen.

Beim Nachsehen: Die Aufnahme selbst gab es schon (getUserMedia + AudioWorklet →
WAV → `/api/transcribe`). Zwei Lücken blieben — beide sind jetzt zu:

1. Der in der **Roadmap (D3)** zugesagte Pfad `POST /api/sprache/transkript`
   existierte nicht, und
2. der Zustand stand **nur im Tooltip** des Mikrofon-Knopfs. Auf dem Handy gibt
   es keinen Tooltip — „wann kann ich sprechen?" war damit unsichtbar, genau das,
   was die Roadmap verlangt („man muss sehen, wann man sprechen kann").

## 1. Backend: der zugesagte Pfad

`backend/app/router/transcribe.py`:

- **Neu `POST /api/sprache/transkript`** (multipart/form-data, Feld `file`).
  Es ist **dieselbe Funktion** wie `/api/transcribe` — ein Aufruf, keine zweite
  Kopie der Logik. `/api/transcribe` bleibt bedient, damit ältere Aufrufer nicht
  brechen.
- Genutzt wird die **bestehende Kette** aus `app/services/llm_service.py`:
  `transcribe()` (Modellkette `microsoft/mai-transcribe-2` →
  `microsoft/mai-transcribe-1.5` → Rückfall `openai/whisper-large-v3` mit
  `language="de"` und `WHISPER_VOKABULAR`) und
  `polish_text()` (`POLISH_MODELS`). Nichts neu erfunden, **kein neuer Anbieter**.
- Unverändert: Grenze 25 MB (HTTP 413), leere Datei → HTTP 400, kein Text →
  `{"text": null, "error": …}`.

## 2. Datenschutz: Audio nur im Speicher

- Die Datei wird blockweise gelesen, im Arbeitsspeicher zusammengesetzt und nach
  der Transkription verworfen. Der Router kennt **kein `tempfile`** und keinen
  Schreibzugriff (im Test festgehalten).
- Das Audio geht ausschließlich an **OpenRouter** — denselben Empfänger, den auch
  der Text-Chat nutzt. Kein zweiter Anbieter, kein ElevenLabs, kein Google.
- Geloggt wird nur die **Byte-Zahl**, nie der Audioinhalt. Ein Test prüft den
  Router-Quelltext auf Datei-Schreibzugriffe.

## 3. Frontend: sichtbarer Zustand

`frontend/index.html` (neue Zeile über der Eingabe), `frontend/style.css`,
`frontend/app.js`:

| Zustand | Anzeige | Wann |
|---|---|---|
| `recording` | **Mikrofon offen** | Zugriff erteilt, Audio-Kette steht |
| `hoert_zu` | **hört zu** | ab dem ersten echten Audioblock (vorher könnte es still sein) |
| `transcribing` / `polishing` | **denkt nach** | während Erkennung + Glättung |
| `spricht` | **spricht** | solange die Browser-Stimme liest |

- Neues Element `#mic-status` (im Eingabebereich, `role="status"`,
  `aria-live="polite"`, im Ruhezustand `hidden`). Zusätzlich trägt der
  Mikrofon-Knopf den Zustand als `aria-label` — vorher war es nur `title`.
- Der erkannte Text landet jetzt **ausdrücklich im Eingabefeld**
  (`setzeEingabe()`: Höhe und Senden-Knopf folgen wie beim Tippen) und geht von
  dort wie eine getippte Nachricht raus. Das **sofortige Senden** bleibt: Eine
  Zwischennachricht per Sprache muss auch während laufender Arbeit absendbar
  sein (Wunsch 2026-09-15) — es ist keine stille Änderung, sondern dasselbe
  Verhalten mit sichtbarem Zwischenschritt.
- Vorhandener Text wird **angehängt**, nicht ersetzt.

## 4. Aufnahme: bewusst ohne MediaRecorder

Die Aufnahme läuft weiter über `getUserMedia` + AudioWorklet (`pcm-recorder.js`)
und baut die **WAV-Datei selbst** (PCM 16 Bit, Mono). MediaRecorder liefert nur
WebM/Opus — der Anbieter lehnt das mit HTTP 400 ab (so auch in TypeFREE). Der
ältere Plan-Eintrag „MediaRecorder mit MIME `audio/webm`" war in der Praxis nicht
tragfähig; die Begründung steht als Kommentar im Code.

## 5. Antwort optional vorlesen

- Der Vorlese-Knopf an jeder Antwort bleibt der Weg (primär `/api/speak`,
  Rückfall **Browser-Stimme** via `SpeechSynthesis`), und der Rückfall setzt
  jetzt den Zustand: `utterance.onstart` → „spricht", `onend`/`onerror` → aus.
- Keine Automatik: Es wird nur vorgelesen, wenn der Knopf gedrückt wird.

## 6. Nachtrag: Gedanken-Blasen einklappen, keine leeren Blasen

Nachtrag vom selben Tag (`frontend/app.js`, `frontend/style.css`) — der Verlauf
war nach dem Mitlesen voller `🧠 Gedanke`-Blasen, und vor dem ersten Textzeichen
stand schon ein Zeitstempel (bei Gedanken zusätzlich das 🧠) im Chat.

**a) Einklappen nach dem Textende.** Eine Gedanken-Blase tippt ihren Text und
schrumpft danach von selbst (`klappeGedankeEin`), ausgelöst am **Ende der
Tipp-Kette** (also erst, wenn der Text vollständig steht), nach
`GEDANKE_EINKLAPPEN_MS` = 2500 ms Lesezeit. Sichtbar bleibt eine schmale Zeile
`Uhrzeit · 🧠 erste Zeile, gekürzt` (`.gedanken-kurz`, CSS-`ellipsis`). Antippen
klappt wieder auf (`klappeGedankeAus`) — dann bleibt die Blase offen
(`data-gedanke-manuell`), die Automatik greift nicht erneut. Blase für Blase: der
Auslöser hängt an jeder Blase einzeln, nicht am Gesamtverlauf.

**b) Kein Sprung beim Einklappen.** `mitGehaltenerScrollposition()` misst die
Höhe vor der Änderung und gleicht die **verschwundene** Höhe genau einmal aus;
wer unten steht, bleibt unten (`scrollToBottom(true)`), wer weiter oben liest,
behält seine Zeile. Zwei Fallen sind ausdrücklich abgefangen: die Höhe ändert
sich über die 0,35-s-Animation **gleitend** (der Bezugswert läuft mit — sonst
wird dieselbe Differenz mehrfach abgezogen), und der Browser klemmt den
Scrollwert bei kürzerem Inhalt selbst (was er schon getan hat, wird nicht erneut
abgezogen). Gemessen im echten Browser (Edge headless, 40 Füller-Nachrichten,
Marker unter der Blase): **Sprung 0 px**, Scrollwert-Änderung 34 px = genau der
Höhenverlust; am unteren Rand bleibt `isAtBottom()` wahr.

**c) Keine leeren Blasen.** Regel jetzt im Code: Eine Live-Blase ohne Inhalt
bleibt **unsichtbar** (`div.hidden`), ihr **Zeitstempel** entsteht erst mit dem
ersten Textzeichen (`data-lazy-zeit`), und die **Datumspille** wird aufgeschoben
(`data-banner-iso`), bis die Blase sichtbar wird — sonst stünde eine Spille ohne
Nachricht im Verlauf. Alles holt `zeigeBlaseMitText()` nach; sie wird von
`zeigeAntwortBlase()` (Text-Chat), `finishReply()` (Sichtbarkeits-Garantie) und
dem Hermes-Stream (`streamHermesText`) genutzt. Der „…"-Platzhalter der
Hermes-Blase ist damit weg. Bei Gedanken-Blasen sind 🧠-Kopf und Zeitstempel
`hidden`, bis das erste Zeichen getippt ist.

## Verifikation

- Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **388 passed**, Exit 0 (Baseline 376; die 11 neuen stehen in
  `backend/tests/test_sprache_endpunkt.py`).
- Neu `frontend/tests/test_sprachaufnahme.js` (31 Prüfungen) und
  `frontend/tests/test_gedanken_blasen.js` (26 Prüfungen: Einklappen nach
  Textende, Kurzfassung, Antippen, Positions-Schutz, keine leeren Blasen),
  Aufruf aus `frontend/`: `node tests/<datei>.js app.js` → alle grün, Exit 0;
  `node --check app.js` → OK; alle 13 JS-Testdateien Exit 0.
- Laufzeit-Nachweis im echten Browser (Edge headless, CDP 9222): Blase nach dem
  Anlegen **0 px hoch** und ohne Symbol/Zeit → nach dem Tippen sichtbar →
  **nach 2,4 s automatisch eingeklappt** (`18:41:40 · 🧠 …`, Inhaltshöhe 0) →
  Antippen klappt auf und sie bleibt offen; leere Live-Blase vorher
  `hidden` + Zeitstempel `hidden`, nach `zeigeBlaseMitText()` beides sichtbar.
- Cache-Bump (Pflicht): `app.js?v=20260925C` → `?v=20260925D` → **`?v=20260925E`**,
  `style.css?v=20260925B` → `?v=20260925C` → **`?v=20260925D`**.

## Offen

- **Am echten Gerät noch nicht durchgesprochen:** Die Zustandsfolge ist
  quelltext-nah und im headless-Browser geprüft, nicht mit einem echten Mikrofon.
  Der erste Schritt am Handy bleibt: `http://localhost:8080` öffnen, Mikrofon
  erlauben, sprechen.
- Das Einklappen ist im headless-Browser mit **ausgeschalteter Timer-Drosselung**
  gemessen; am Handy (Vordergrund) tickt das Tippen normal.
- Kein Wake-Word, kein Overlay — das sind die eigenen Schritte D1/D4 der Roadmap.
