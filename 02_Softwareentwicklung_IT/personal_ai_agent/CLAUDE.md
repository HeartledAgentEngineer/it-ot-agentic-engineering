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
| **Kein externer STT (Whisper)** (MVP) | Browser-API als Fallback | ✅ Keine Audio-Daten extern |
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
| 25.09.2026 | **Gedächtnis sichtbar + Qualität, Chat-Konsistenz, Katalog-Löschen, Quiz-Suche.** (1) Erinnerungen waren da (175 auf dem Handy), wurden aber **nie angezeigt** — jetzt Blatt mit Liste/Löschen/Zähler. (2) Korrekturen wurden still verworfen (0,90-Ähnlichkeit: „zehn/elf" 0,950, „Rex/Max" 0,933) → neue Fassung ersetzt, alte bleibt in `history`; Relevanz statt Vollbestand (`ALLES_MITGEBEN_BIS=300` entfernt, `MEMORY_TOP_K=8`, Block max. 1200 Zeichen); Arten `fakt/termin/zustand` mit Datumserkennung, vergangene Termine auffindbar (Zahnarzt 2026), sanftes Vergessen ohne Löschen; `GET /api/memory/erklaeren` + `POST /api/memory/migration` (Trockenlauf). (3) Chat nach Reload: stiller Fallback auf das jüngste Gespräch und stilles Umbiegen auf `conv_main` behoben, Bild nur noch aus frisch gefundenen Dateien (Vorschau an ihre Nachricht gebunden), sichtbares Feld `#chat-aktuell`. (4) Einzel-Löschen einer Referenz verschwieg Fehlschläge (immer „✓ gelöscht") → jetzt „NICHT gelöscht" mit Grund, Kennzeichnung „ohne Bild", toten Confirm-Dialog repariert. (5) Quiz-Suche filterte nur die 5 Backend-Kandidaten → jetzt alle Katalog-Personen, Kennzeichnung statt Ausblenden, „als neue Person anlegen" im Dropdown. **Prüfbefehl: 304 grün, Exit 0; 11/11 JS-Tests grün·Cache `?v=20260925C`** | Sebastians Befunde (Wortlaut in den Changelogs); alle Ursachen mit Datei:Zeile belegt, Gegenproben dokumentiert | Hermes |

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

1. LLM-Calls an OpenRouter (nur Text, keine Audios/Bilder)
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