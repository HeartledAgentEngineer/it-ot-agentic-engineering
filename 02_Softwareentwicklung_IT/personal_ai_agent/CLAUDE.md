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

| 26.09.2026 | **pCloud-Zugang für das Backend — ohne App-Registrierung.** Der offizielle Weg (App Console + OAuth 2.0) war blockiert: die Anmeldung im Entwicklerbereich (`docs.pcloud.com`) hängt (Google-Rücksprung; in Comet sind Drittanbieter-Cookies blockiert), und das Konto läuft über Google. Gewählter Weg: Der **pCloud-Client am PC** ist bereits angemeldet — sein Anmelde-Wert liegt in `%LOCALAPPDATA%\pCloud\data.db` (Tabelle `setting`, Feld `auth`, 39 Zeichen; `location_id = 2` = Europa). Ausgelesen **nur lesend** (`file:…?immutable=1`, laufender Client bleibt unberührt), **nie ausgegeben**, direkt nach `backend/.env` geschrieben (`PCLOUD_TOKEN`, `PCLOUD_HOST=eapi.pcloud.com`; `.env` ist per `.gitignore` gesperrt). **Beleg:** `userinfo` → `result: 0` (premium, E-Mail bestätigt, 2.199 GB Quota / 390,5 GB belegt), `listfolder` Wurzel → 18 Einträge. Regeln bleiben im Code (pCloud hat keinen „nur lesen"-Scope): Standard lesen, Schreiben nur in `Agent/`, Umbenennen/Verschieben/Löschen nur nach Rückfrage, `Crypto Folder` tabu, `P:\` nie rekursiv. Doku: `docs/changelog-2026-09-26-pcloud-zugang.md` | Ohne API-Zugang bleibt der Agent am Handy blind (Android hat kein Laufwerk, `rclone mount` bräuchte FUSE + root) — Foto-Sortierung (Stufe B) und Personen-Clustering brauchen den Zugang | Hermes |

| 28.09.2026 | **Nachtlauf 26./27.09.2026 abgeschlossen (Schritt N10).** Abschlussbericht `docs/abschlussbericht-nachtlauf-2026-09-26.md` trägt den Stand des Dauerlaufs in belegten Zahlen zusammen (Quellen: Plan-Journal mit 1.416 Zeilen und 24 Changelog-Dateien vom 27.09.2026; keine eigene Messung, keine erfundene Zahl). Kern: ein **echter Fehler** wurde gefunden und behoben — `cv2…alignCrop` bekam an drei Stellen nur die 5×2-Landmarken statt der vollen 15-Werte-Zeile, dadurch bekam jedes Gesicht **eines** Bildes denselben Vektor (belegt an 131 von 131 Paaren mit Distanz 0,0000); Fix in `tools/foto_sortierung/gesicht_erkennen.py` **und** `backend/face_infer.py` (Produktionsweg war mit betroffen) plus Wächter; die N9b/N9d-Zahlen sind als **ungültig** markiert. Offen/gesperrt: echtes Sortieren (N8) bis zum Blick auf die 39 sicheren Event-Vorschläge und die 1.146 datumslosen Dateien, Übergabe der Übersichtsdatei ans Handy, ein vom Anbieter abgelehnter Anlass (403 `PROHIBITED_CONTENT`), N16/N18. Prüfbefehl: **1687 passed, Exit 0** (Baseline 1503); die Zeile `personal_ai_agent` in `../CLAUDE_EXTENDS.md` auf denselben Stand gezogen. Doku: `docs/changelog-2026-09-28-n10-abschlussbericht.md` | 20+ Nachtlauf-Schritte lagen über ein 1.416-Zeilen-Journal und 24 Changelogs verstreut — eine Seite mit dem Stand in Zahlen fehlte; der Fehler in der Merkmalberechnung hätte die Personen-Stufe dauerhaft unbrauchbar gemacht | Hermes |

| 28.09.2026 | **WhatsApp-Zuordnung Chat <-> Telefonbuch (privat; Bericht nur Zahlen).** Neu `tools/whatsapp/zuordnung_bauen.py` (nur lesend): Bruecke ist die Nummer; Telefonbuch per ADB (985 Eintraege, 55 Geburtstage), Nummern-Normalisierung +49/0049/0/+49 (0), Gruppenmitglieder aus `group_participant_user` + `group_participants` (Textform) mit Ersatzweg ueber `message_system_chat_participant`/Absender — die Tabelle `group_participant` fehlt in diesem Schema (PRAGMA geprueft). Ergebnis-JSON AUSSERHALB des Repos: `foto_sortierung/whatsapp_zuordnung.json`, Nummern nur als letzte 4 Ziffern maskiert. Gemessen: 744 von 2.471 Chats mit Kontakt-Treffer; Gruppen 66 vollstaendig / 121 teilweise / 44 unbekannt (43 ohne Mitgliederdaten); 6.242 Mitglieder (2.006 mit Treffer). Neu `backend/tests/test_whatsapp_zuordnung.py` (21 Offline-Tests, erfundene Beispieldaten). Pruefbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` -> **1897 passed, Exit 0**. Doku: `docs/changelog-2026-09-28-whatsapp-zuordnung.md` | Personenzuordnung fuer die Foto-Sortierung; Kontaktdaten duerfen nicht ins Repo, Berichte nennen nur Zaehlungen | Hermes |

| 28.09.2026 | **Auftrag E8a: Erzähl-Diashow.** Neu `backend/app/services/erzaehl_service.py` (liest `ereignisse.jsonl` nur lesend, defekte Zeilen gezählt statt geworfen) + `backend/app/router/erzaehlen.py` (`GET /api/erzaehlen/ereignisse`, `GET /api/erzaehlen/ereignisse/{kennung}`, `POST/GET /api/erzaehlen/geschichten`, Key-Schutz wie alle anderen `/api`-Routen). Geschichten hängen **nur an** `geschichten.jsonl` (`open(..., "a")` + `flush` + `fsync`, Schicht „mensch"), Anker ist Bildkennung + Ereignis-Schnappschuss, Korrekturen sind neue Zeilen mit `ersetzt: <alte id>` (Liste zeigt nur die neueste Fassung). Erlaubte `quelle`-Werte (Nachtrag Planer während der Umsetzung): `tippen \| sprache \| import` — Oberfläche setzt weiter nur tippen/sprache, die Validierung akzeptiert `import` zusätzlich (spätere Übernahme aus Hermes). Frontend: neue eigenständige Datei `frontend/erzaehlen.js` (kein Umbau von `app.js`) — Vollbild-Blatt mit Ereignisliste + Diashow, Bilder per fetch→Blob→Objekt-URL wie die bestehende Galerie, Mikrofon über dieselbe AudioWorklet→WAV→`/api/sprache/transkript`-Kette wie `app.js`, Sprachbefehle „weiter"/„zurück"/„speichern". Cache-Bump `style.css?v=20260928B`, neu `erzaehlen.js?v=20260928B`. Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **2606 passed, Exit 0** (Baseline 2558, davon 48 neue Tests); `node --check frontend/erzaehlen.js` + `node frontend/tests/test_erzaehlen.js` (40 Prüfungen) + alle 14 übrigen `frontend/tests/*.js` → Exit 0 (eine Zeile in `test_foto_galerie.js` musste auf den neuen `style.css`-Cache-Bump nachgezogen werden — reiner Versions-Abgleich). Doku: `docs/changelog-2026-09-28-e8a-erzaehl-diashow.md`, `docs/auftrag-e8a-erzaehl-diashow.md` | Bilder liegen sortiert, aber ohne Sebastians eigene Worte dazu; die Diashow macht das Nacherzählen zu einer eigenen Tätigkeit am PC wie am Handy | Hermes (Ausführer: Subagent) |
| 29.09.2026 | **N27d Personen-Andockung (Verknuepfungsschicht N27, Schritt 4 von 5).** Neu `tools/foto_sortierung/personen_andocken.py` (1.140 Zeilen) + `backend/tests/test_personen_andockung.py` (1.258 Zeilen / 144 Testfunktionen, offline): fuehrt Ereignis-Knoten (`ereignisse.jsonl`), Gesichts-Cluster (`personen_cluster.lauf_rechnen`, Verfahren „vollstaendig", Schwelle 0,45, Altbestand `personen_n9f/kennungen.json`) und Chat-Andockung (`chat_andockung.jsonl`) zusammen und schreibt **ausserhalb des Repos** `personen_andockung.jsonl` (je Anlass die Personen) und `personen_vorschlaege.json` (Namensvorschlaege). **Ein Name erscheint nur aus der Nutzer-Datei `personen_bestaetigt.json`** — Vorschlag und Name sind getrennte Felder, das Werkzeug benennt nie selbst; `--trocken` ist Standard, Repo-Ziel **Exit 2**. Gemessen: 151 Vektorzeilen, 12 Personen (2 neu/10 wiederverwendet), 5 Anlaesse mit Personen, 12/12 mit Kandidatennamen, 34 Namen; zwei Schreiblaeufe mit festem `--stand` byte-gleich (2.833 B / 7.454 B); ohne Bestaetigung 0 Namen. Pruefbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` -> **2558 passed, Exit 0** (Baseline 2414). Find dieser Runde offengelegt: die Vormessung filterte die `beteiligte` auf Zeichenketten, sie sind aber Objekte — mit ihnen waeren es 44 statt 34 Namen; umgesetzt ist `chat_name` mit `beteiligte` als Rueckfall. Doku: `docs/changelog-2026-09-29-n27d-personen-andockung.md`, `docs/auftrag-n27d-personen-andockung.md`. **Pruefer (andere Modellfamilie): Runden 1-3 `openai/gpt-5.6-luna` (fuenf echte Doku-/Datenschutz-Punkte: Zeilenzahl 1.136->1.140, Beispielname, Sternchen-Maske, Eigner-Name, Auftrag ohne Endstand; dazu ein Methodenartefakt beim Export ohne `.git`), Abnahme Runde 4 auf dem Endstand `50e86c3` mit `google/gemini-3.7-flash` (luna war bei OpenRouter rate-limitiert): BESTANDEN, 0 Abweichungen** | Verknuepfungsschicht: Personen je Ereignis mit bestaetigungsgebundener Benennung; Massenlauf der Gesichter (~15 h) bleibt eigener Schritt | Hermes (Ausfuehrer: Subagent, Pruefer: gpt-5.6-luna / gemini-3.7-flash) |
| 29.09.2026 | **N27e Ableitung "wer war mit wem wo" (Verknuepfungsschicht N27, Schritt 5 von 5, letzter).** Neu `tools/foto_sortierung/beziehungen_ableiten.py` (1.097 Zeilen) + `backend/tests/test_beziehungen_ableiten.py` (1.530 Zeilen / 183 Testfunktionen, offline): leitet aus `personen_andockung.jsonl`, `chat_andockung.jsonl` und `ereignisse.jsonl` **nur lesend** belegbare Aussagen ab, jede mit **Datum + Quelle**, in drei getrennten Unterarten (`fotos` ≥ 2 Personen am selben Anlass · `gemeinsam_im_chat` ≥ 2 benannte Kontakte im selben Chat am selben Tag · `fotos_und_chat` Person × Kontakt am selben Anlass); unbestätigte Kennungen bleiben `Person_00x` mit `name: null`, Kandidatenlisten werden nie gelesen, jede Zeile trägt einen deutschen `hinweis` (Mitgliedschaft ≠ Anwesenheit, Bildnähe ≠ Beziehung); `--trocken` ist Standard, Repo-Ziel **Exit 2**, `--datum` fragt einen Tag ab, `--nur-bestaetigt` schaltet auf die strenge Lesart; Ausgabe ausschließlich außerhalb des Repos. Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **2.789 passed, Exit 0** (Baseline 2.606). Live: **5 / 2.127 / 2.127 Zeilen, 0 defekt · 23 + 14.902 + 126 = 15.051 Aussagen · 12 Kennungen · 0 bestätigte Namen · 253 Kontakte · 2016-05-04 bis 2025-08-16**; zwei Schreibläufe mit festem `--stand` **byte-gleich** (12.601.994 B, sha256 `549eafbc59bf6e58…`; 715 B, sha256 `083503afbb462602…`); Repo-Ziel **Exit 2**, ungültiges `--datum` **Exit 2**, `--nur-bestaetigt` **0** Aussagen. Doku: `docs/changelog-2026-09-29-n27e-beziehungen.md`, `docs/auftrag-n27e-beziehungen.md`. **Prüfer (andere Modellfamilie): `openai/gpt-5.6-luna` — Journal.** | Hermes (Ausfuehrer: Subagent, Pruefer: gpt-5.6-luna) |

## Sicherheit: Duplikate (Sebastians Freigabe 27.09.2026)

> Wörtlich: „Wenn wirklich doppelte Bilder in der ganzen Sortierung sind, in der
> ganzen Cloud, oder auf dem Upload-Ordner im Vergleich zum Bilder- und
> Videoordner, dann können die doppelten gelöscht werden."

- **Erlaubt ist Löschen ausschließlich bei beweisbar identischen Dateien.**
  Beweis = **gleiche Prüfsumme (`hash`) UND gleiche Größe**, von der pCloud-API
  geliefert — kein Namensvergleich, kein Augenmaß, kein Download.
- **Gelöscht wird immer die Kopie im Stapel** (`Automatic Upload`), **nie** das
  Original in `Bilder & Videos`. Bestehende Ordnung bleibt die Wahrheit.
- **Erst Liste, dann Löschen:** Vor jedem Löschlauf wird die Paarliste gezeigt
  (Zahl, Größe, Beispiele). Löschungen kommen **einzeln ins Manifest**
  (Zeit, Datei-Kennung, Name, Prüfsumme, Größe).
- **Alles andere bleibt wie bisher:** ohne Prüfsummen-Beweis wird nicht gelöscht
  — dann nur verschoben.

---

## Sicherheit: Fotos, Gesichter, Menschenmengen

- **Menschenmengen** (Konzerte, Veranstaltungen, weit entfernte Personen):
  **keine Verpixelung nötig**, dürfen thematisch sortiert und als Kontaktbogen
  gezeigt werden — aber **kein Gesichts-Anlernen, keine Personen-Cluster,
  keine Referenzseiten** daraus.
- **Vordergrund-Prüfung:** Bei Massenfotos prüfen, ob im Vordergrund eine
  **bekannte** Person (Katalog) ist → dann diesem Menschen zuordnen.
  Nur fremde Menge → **weglassen** (nicht clustern, nur thematisch einsortieren).
- **Gruppen-/Nahaufnahmen:** unbekannte Gesichter erzeugen **unbenannte**
  Gruppen (`Person_001` …), benannt wird **nur** nach Sebastians Bestätigung.
- **Biometrie bleibt lokal:** Gesichts-Vektoren und Katalog (`gesichter_katalog.json`)
  verlassen den PC **nie** (nicht ins Repo, nicht an ein Fremd-LLM).
- **Schwelle statt Gefühl:** „Menge oder Gruppe" entscheidet der Code über
  Gesichtsgröße und Gesichter-Anzahl, nicht der Augenschein.

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

---

## 🤝 Übergabe an andere Coding-Agenten (Claude Code / Codex)

**Datenschutz-Grenze (bindend): andere Agenten arbeiten NUR am Code.** Keine
Chat-Inhalte, keine Fotos, keine Kontakt-Namen/-Nummern, keine Gesichtsdaten,
keine Archiv-Datenbanken, kein Ordner `Chats von GPT, GEMINI, Claude/`.
Personenbezogene Daten werden **ausschließlich** über Hermes + OpenRouter
verarbeitet (`provider_routing.data_collection: deny`). Braucht ein
Code-Auftrag persönliche Daten: abbrechen und an Hermes zurückgeben.

**Einstiegspunkt: `HANDOVER-CLAUDE-CODE.md`** (im Projektordner, englisch).
Dort stehen: Prüfbefehl, aktueller Stand mit Zahlen, Datenablagen außerhalb des
Repos, Datenschutz-Regeln, Git-Regeln (`--only` statt `-A`), Kostenregeln und
die offenen Schritte N15…N27.

Wer als fremder Agent hier startet: **erst `HANDOVER-CLAUDE-CODE.md` lesen**,
dann `docs/plan-nachtlauf-2026-09-26.md`. Diese `CLAUDE.md` **nicht** per
`/init` überschreiben — sie ist handgepflegt und enthält Datenschutz- und
Rechtsentscheidungen.