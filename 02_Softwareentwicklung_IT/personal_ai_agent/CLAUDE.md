# CLAUDE.md – Projektrichtlinien & Sicherheitskriterien

> **Projekt:** Personal AI Agent (grillAnAgent)
> **Erstellt:** 02.08.2026
> **Zweck:** Definiert Sicherheitskriterien, Architekturentscheidungen und Arbeitsweise für Cline/Claude Code.

---

## 🛡️ Sicherheitskriterien (MUSS bei jeder Änderung geprüft werden)

### API-Keys & Secrets
- **NIE** API-Keys in Code, Frontend oder öffentliche Dateien schreiben
- API-Key gehört ausschließlich in `.env` (in `.gitignore`)
- `.env` niemals commiten
- Bei Deployment: Key via Environment-Variable, nicht in Config

### Datei-Sicherheit
- Jede Datei-Operation (create/edit/delete) auf Sicherheitsrelevanz prüfen
- Bestehende `.gitignore`-Einträge beachten
- Keine sensiblen Daten in Logs schreiben

### Netzwerk-Sicherheit (Phone-First)
- Backend läuft NUR lokal (localhost/127.0.0.1) – kein öffentlicher Port
- API-Key wird NIE an den Client (Frontend) gesendet
- Frontend kommuniziert NUR mit lokalem Backend
- Keine Drittanbieter-CDN/Tracker im Frontend

### Datenschutz
- Keine Nutzerdaten an Dritte senden (außer OpenRouter LLM-Call)
- Vektor-Speicher lokal: **kein ChromaDB** — die Erinnerungen liegen als JSON-Datei
  `chroma_data/memory_store.json` (berichtigt 25.09.2026)
- Embeddings laufen über **OpenRouter** (Modell `text-embedding-3-small`); der früher
  geplante lokale sentence-transformers ist auf **keinem** Gerät installiert (geprüft
  25.09.2026). Nur die Suchanfrage verlässt das Gerät — keine Bilder, keine Archive

---

## 🏗️ Architektur-Entscheidungen

| Entscheidung | Begründung | Sicherheitsimplikation |
|-------------|-----------|----------------------|
| **Phone-First** (Termux) | Kein VPS nötig, API-Key bleibt lokal | ✅ Key sicher auf Gerät |
| **DeepSeek V4 Flash** via OpenRouter | Günstig, leistungsstark | ⚠️ Nur Text-Calls, keine Datenweitergabe |
| **Vektor-Speicher lokal (kein ChromaDB)** | Erinnerungen liegen als JSON-Datei `chroma_data/memory_store.json` (berichtigt 25.09.2026) | ✅ Keine externen DB-Zugriffe |
| **Embeddings über OpenRouter** (`text-embedding-3-small`) | Lokaler Embedder fehlt auf beiden Geräten (geprüft 25.09.2026); Kosten Bruchteile eines Cents | ⚠️ Nur die Suchanfrage verlässt das Gerät — keine Bilder, keine Archivinhalte |
| **PWA statt Native App** | Schnell, keine Store-Abhängigkeit | ⚠️ Service Worker nur für Cache |
| **TTS via Browser SpeechSynthesis** | Lokal, keine Kosten, kein Datenabfluss | ✅ Kein externer TTS-Service |
| **Spracherkennung über OpenRouter** (`microsoft/mai-transcribe-2` → `microsoft/mai-transcribe-1.5` → `openai/whisper-large-v3`) | Beste Erkennung im Test: mai-transcribe-2 mit **0,3 % Wortfehlern an 140 s natürlichem Deutsch in 3,8 s** (0,10 $/h; mai-transcribe-1.5 gleich genau, aber 11,8 s und 0,36 $/h; whisper-large-v3 1,2 % in 4,5 s). Drei Wege, damit ein Diktat nicht an einem Anbieter-Ausfall scheitert; nur Whisper kann `language` und Vokabular mitgeben | ⚠️ Die Aufnahme **verlässt das Gerät** und geht an OpenRouter — wie der Text-Chat auch; **kein** weiterer Anbieter kommt hinzu. Die frühere Zeile „Kein externer STT / keine Audio-Daten extern" war falsch und ist am 25.09.2026 korrigiert |
| **CORS: Allow all origins** | Lokaler Betrieb (gleiches Gerät) | ⚠️ Nur im Heimnetz sicher |

---

## 📋 Änderungsprotokoll

Jede signifikante Änderung muss hier dokumentiert werden:

| Datum | Änderung | Begründung | Geprüft von |
|-------|----------|-----------|-------------|
| 02.08.2026 | Architektur-Change: VPS → Phone-First (Termux) | API-Key-Sicherheit, Kosten, schnellere Iteration | Cline |
| 28.08.2026 | Test-Suite erweitert: `test_faehigkeiten_grenzfaelle.py` (Wortgrenzen, leere Eingabe, Groß/Klein, Phrasen) — erstellt per Codex-Hybrid (gpt-5.6-terra), reviewed von Hermes | Absicherung der Heuristik gegen Fehltreffer; 48 Tests grün | Hermes (Review) |
| 29.08.2026 | Fix LIVE-Fehler „Fehler im lokalen Hermes-Job: Name T is not defined": `LocalHermesJob.neue_gedanken()` referenzierte ein nie definiertes `t` (Regression aus afd339e — Zeile `t = " ".join(...)` wurde beim Umbruch-Join gelöscht, `if t:` blieb) → NameError bei der ersten fertigen Antwort-Box brach Track C ab. Fix + Box-Ränder (`│`) werden jetzt sauber entfernt. Dazu Ziel-Anzeige: `route_auftrag`/`ChatResponse`/SSE-done tragen `ziel` (pc/handy/buch), Antwort enthält „➡️ Weitergeleitet an: …", Frontend zeigt Ziel-Pille (→ Hermes (PC) / → Hermes (Handy) / → Auftragsbuch); 8 neue Tests, 118 Tests grün | Track C brach live ab; „wohin delegiert?" war unsichtbar | Hermes |
| 15.09.2026 | Prüfbefehl existiert jetzt: `cd backend && .venv/Scripts/python -m pytest tests/ -q`. Stand: **195 grün / 8 rot**. Ursache der roten Tests verifiziert: `_datei_tool` ruft jetzt `llm_service.extrahiere_datei_such_intent()` (LLM-Call) als Vorgate; `test_datei_suche.py` + `test_kontext_delegation.py` mocken das nicht → echte Netz-Calls (~6 s/Test) + Fehlschlag. Hinweis: `02_Softwareentwicklung_IT/CLAUDE.md` (generiert von `sync-rules.ps1` aus `CLAUDE_EXTENDS.md`) behauptet in der Prüfbefehls-Tabelle noch „personal_ai_agent \| fehlt" — beim nächsten `sync-rules.ps1`-Lauf aus `CLAUDE_EXTENDS.md` nachziehen | Verifier-Gate für personal_ai_agent fehlte in der generierten Doku; rote Tests isoliert und Ursache dokumentiert | Hermes |
| 15.09.2026 | **R1 Track-Weiche + R1b Tests grün (208/208):** `route_auftrag()` hat jetzt einen `ziel`-Parameter — bei `ziel="handy"` (Button „An lokalen Hermes übergeben") wird Track A (PC) übersprungen; ebenso lässt die Stream-Weiche `conv_code` direkt lokal laufen (vorher ging der Coding-Chat und der Umlenk-Button immer erst an den PC, der annahm und nichts ans Handy zurückgab). Die 8 roten Tests hatten **zwei** Ursachen: (a) `_datei_tool` macht ein LLM-Vorgate (`extrahiere_datei_such_intent`), das nicht gemockt war → echte Netz-Calls; (b) `test_chat_verlauf.py` löscht `app.router.chat` aus `sys.modules` und importiert neu, wodurch Patches per Modulname ins Leere liefen. Fix: Mock über die Globals der jeweiligen Funktion. Neue Datei `tests/test_route_ziel.py` (5 Tests). Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **208 passed**, Exit 0, ~23 s | Track-A/C-Weiche war dokumentiert, aber nicht wirksam; Testsuite war nicht isoliert | Hermes |
| 25.09.2026 | **Sprachaufnahme im Chat: sichtbar und vollständig (Roadmap D3).** Neu `POST /api/sprache/transkript` (multipart/form-data, Feld `file`) — **dieselbe Funktion** wie das ältere `/api/transcribe` (bleibt bedient), also keine zweite Logik; genutzt wird die bestehende Kette `transcribe()` (mai-transcribe → whisper-Rückfall) und `polish_text()`, **kein neuer Anbieter**. Der eigentliche Befund: Der Zustand der Spracheingabe stand **nur im Tooltip** des Mikrofon-Knopfs — am Handy unsichtbar. Jetzt die sichtbare Zeile `#mic-status` über der Eingabe: „Mikrofon offen" → „hört zu" (erst ab dem ersten Audioblock) → „denkt nach" → „spricht" (Browser-Stimme beim Vorlesen). Das Diktat landet über `setzeEingabe()` sichtbar im Eingabefeld und geht von dort raus (Sofort-Senden bleibt, Wunsch 15.09.2026). Aufnahme bleibt bewusst **ohne** MediaRecorder (WebM/Opus → HTTP 400); Audio lebt nur im Speicher, geht nur an OpenRouter. Neu: `tests/test_sprache_endpunkt.py` (11 Tests, Kette gemockt, Netz-Call-Stolperfalle, Datei-Schreib-Check) und `frontend/tests/test_sprachaufnahme.js` (31 Prüfungen). Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **387 grün, Exit 0** (vorher 376); JS-Test Exit 0. Cache-Bump: `app.js?v=20260925D`, `style.css?v=20260925C` | Zustandsanzeige war am Handy unsichtbar; der in der Roadmap zugesagte Endpunkt-Pfad fehlte | Hermes |
| 25.09.2026 | **Erkennung: bestes Modell zuerst.** `TRANSCRIBE_MODELS` ist jetzt `microsoft/mai-transcribe-2` → `microsoft/mai-transcribe-1.5` → `openai/whisper-large-v3` (vorher zwei Wege, mai-1.5 zuerst). Anlass: sauberer Langtest an **140 s natürlichem Deutsch** (fortlaufender TTS-Text, 325 Wörter) — mai-transcribe-2 **0,3 % Wortfehler in 3,8 s** (0,10 $/h), mai-transcribe-1.5 0,3 % in 11,8 s (0,36 $/h), voxtral-…-stt 0,3 % in 18,9 s, whisper-large-v3 1,2 % in 4,5 s, Voxtral im Chat-Weg 429. Damit ist der Ersatzweg dreifach statt einfach, und der Regelweg dreimal schneller und billiger als vorher. `tests/test_spracheingabe.py` an die Dreier-Kette angepasst (Wege-Assertions + Vokabular-Prüfung am letzten Glied). Alle Wege bleiben **innerhalb OpenRouter**. Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **388 grün, Exit 0** | Sebastians Vorgabe „nur über OpenRouter und das beste Modell"; Messwerte reproduzierbar mit `typeFREE/windows/sprachmessung.py` | Hermes |
| 25.09.2026 | **Spracheingabe: Kette, Rückfallweg, Regeln aus typeFREE.** Beim Nachsehen der eigentliche Befund: die **Glättung lief seit Wochen ins Leere** — `google/gemini-2.0-flash-001` ist bei OpenRouter abgekündigt (404), der Rohtext wurde kommentarlos durchgereicht (derselbe stille Ausfall wie in typeFREE, dort bemerkt, hier ohne Warnung und ohne einen Test). Jetzt: `POLISH_MODELS` = `gemini-2.5-flash` → `gemini-3.5-flash-lite` → `gemini-2.5-flash-lite` (alle per `/models` als lebend geprüft), `polish_text()` läuft die Kette, scheiternde Modelle werden als `WARNING` geloggt, Totalausfall als `ERROR`. `POLISH_ANWEISUNG` um die Regeln 5–8 ergänzt (Anrede bleibt / Sprechakt bleibt / kein Erzähl- oder Fragestil / Fachbegriffe und Denglisch bleiben, „Comet" gegen „Commit") + Verbot „Die Anredeform oder den Sprechakt ändern". Erkennung: `TRANSCRIBE_MODELS` = `microsoft/mai-transcribe-1.5` → `openai/whisper-large-v3` (Rückfall mit `language="de"` und `WHISPER_VOKABULAR`), `_audio_puffer()` liefert je Versuch einen frischen Puffer, Log nennt den liefernden Weg. Beide Wege bleiben **innerhalb OpenRouter** — kein neuer Anbieter. Falsche Architektur-Zeile „Kein externer STT / keine Audio-Daten extern" korrigiert. **Neu: `tests/test_spracheingabe.py` (18 Tests) — der Sprachweg hatte vorher keinen einzigen.** Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **376 grün, Exit 0** (vorher 358). Messwerte (Referenzaudio 69,7 s deutsch, mit `typeFREE/windows/sprachmessung.py`): mai-transcribe **1,1 %** Wortfehler, whisper-large-v3 3,4 %, beide mit vollständigem Ende | Sebastians Auftrag „Verbesserung auch in den Personal AI Agent"; Ursache mit Datei:Zeile belegt, Modelle per `/models` geprüft, Messwerte reproduzierbar | Hermes |

| 25.09.2026 | **Chat-Verlauf aufgeräumt: Gedanken-Blasen klappen ein, keine leeren Blasen (Nachtrag zum selben Auftrag).** `frontend/app.js` + `frontend/style.css`: Eine `🧠 Gedanke`-Blase klappt am **Ende ihrer Tipp-Kette** von selbst ein (2500 ms Lesezeit, `klappeGedankeEin`), sichtbar bleibt eine schmale Zeile `Uhrzeit · 🧠 erste Zeile, gekürzt` (`.gedanken-kurz`); Antippen klappt wieder auf und lässt sie offen (`data-gedanke-manuell`), die Automatik greift nicht erneut. **Kein Sprung:** `mitGehaltenerScrollposition()` gleicht die verschwundene Höhe genau einmal aus — Bezugswert läuft mit (die Animation ändert die Höhe gleitend, sonst würde dieselbe Differenz mehrfach abgezogen) und das eigene Klemmen des Browsers wird nicht doppelt verrechnet; wer unten steht, bleibt unten. Im echten Browser gemessen (Edge headless, 40 Füller, Marker unter der Blase): **0 px Sprung**, Scrollwert-Änderung 34 px = genau der Höhenverlust. **Keine leeren Blasen:** Live-Blase ohne Inhalt bleibt `hidden`, der Zeitstempel entsteht erst mit dem ersten Textzeichen (`data-lazy-zeit`), die Datumspille wird aufgeschoben (`data-banner-iso`) — alles über `zeigeBlaseMitText()` (genutzt von Text-Chat, `finishReply()`, Hermes-Stream; der „…"-Platzhalter ist weg); bei Gedanken sind 🧠-Kopf und Zeit bis zum ersten Zeichen verborgen. Neu `frontend/tests/test_gedanken_blasen.js` (26 Prüfungen), dazu `frontend/tests/test_sprachaufnahme.js` (31). Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **388 passed, Exit 0**; `node --check app.js` OK, alle 13 JS-Tests Exit 0. Cache-Bump: `app.js?v=20260925E`, `style.css?v=20260925D` | Vor dem ersten Textzeichen standen Zeitstempel und 🧠 als leere Blasen im Chat, und mehrere Gedanken füllten nach dem Mitlesen den ganzen Verlauf | Hermes |
| 25.09.2026 | **Selbsttest: Systemzustand ohne Kabel ablesbar.** Neu `GET /api/selbsttest` (`backend/app/router/selbsttest.py`, in `main.py` mit Key-Schutz registriert) liefert **immer** dieselben Felder — `commit` (`git log --oneline -1`), `index` (`~/archiv_index.db`: existiert/Größe MB/COUNT auf `nachrichten`+`chunks`, SQLite nur `mode=ro`), `daemon` (Prozess über `pgrep -f hermes_inbox_daemon.py`, sonst `/proc/*/cmdline`; Größe/Alter + letzte 3 Zeilen von `daemon.log`), `letzte_antwort` (`antworten.jsonl`/`status.jsonl`: Zeilen, volle Länge, **Auszug auf 200 Zeichen gekürzt**), `gedaechtnis` (wie `/api/memory/count`), `sprache` (`TRANSCRIBE_MODELS` + `/api/transcribe` und `/api/speak` registriert), `uhrzeit` (Serverzeit). Fehlt eine Quelle, steht dort ein `error`-Text — **nie ein 500er**, jeder Block mit eigenem try/except und Logging; nur lesend, kein Netz-Call, keine Geheimnisse. Frontend: Kopfzeilen-Knopf `#selbsttest-btn` → Blatt „Selbsttest“ mit **reiner** Funktion `selbsttestText(daten) -> string` (✓/⚠/✗, ohne DOM testbar), Anzeige per `textContent`, **kein Auto-Polling**, „Aktualisieren“-Knopf, Schließen über ×/Hintergrund/Esc. Neu `tests/test_selbsttest.py` (21 Tests, Pfade auf `tmp_path`, kein Netz) und `frontend/tests/test_selbsttest.js` (39 Prüfungen, u. a. fehlende Felder → ✗/⚠ statt Absturz). Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **422 grün, Exit 0** (Baseline vor der Änderung: 388; +21 aus dieser Änderung, +13 aus einem parallel laufenden Strang); `node --check app.js` OK, alle 14 JS-Tests Exit 0. Cache-Bump: `app.js?v=20260925F`, `style.css?v=20260925E`. Doku: `docs/changelog-2026-09-25-selbsttest.md` | Unterwegs kein ADB — der Zustand (Commit, Index, Daemon, Logs, Erinnerungen, Sprachmodelle, Zeit) war nur über die Termux-Konsole prüfbar; jetzt in der App als Screenshot teilbar und für die Zeitstempel-Prüfung nachvollziehbar | Hermes |

---

## 🚫 Verbotene Operationen

1. API-Keys in Code/Config committen
2. `.env`-Dateien versionieren
3. Sensitive Logs (API-Keys, Tokens) ausgeben
4. Nutzerdaten an Dritte senden (außer OpenRouter)
5. Externe CDNs/Tracker im Frontend einbinden
6. Ports >1024 ohne Authentication öffentlich machen

---

## ✅ Erlaubte Operationen

1. LLM-Calls an OpenRouter (Text; Audio **nur** zur Transkription über den Sprachweg `/api/sprache/transkript` — keine Bilder)
2. Lokale Datei-Operationen für Config/Daten
3. Health-Checks ohne Authentifizierung (lokaler Betrieb)
4. Statische Assets cachen (Service Worker)
5. HTTP auf localhost (kein HTTPS nötig für lokalen Betrieb)

---

## 🔄 Workflow für Änderungen

```
1. Sicherheitscheck: Darf diese Änderung gemacht werden?
   → Prüfe Verbotene Operationen Liste
   
2. Begründung: Warum ist diese Änderung nötig?
   → Dokumentiere in Änderungsprotokoll
   
3. Implementierung: Clean Code + Error Handling
   → Keine Secrets, keine Datenleaks
   
4. Review: Entspricht der Architektur-Entscheidung?
   → Phone-First, lokal, sicher
```

---

## 📝 Code-Stil

- **Backend:** Python FastAPI mit Type Hints
- **Frontend:** Vanilla JS, kein Framework (MVP)
- **Kommentare:** Deutsch (User-facing) / Englisch (Code)
- **Error Handling:** Immer try/except mit Logging
- **Keine** Hardcodierten Pfade – immer Config/Env-Variablen