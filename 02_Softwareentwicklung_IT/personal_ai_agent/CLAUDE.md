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
- Vektor-DB (ChromaDB) bleibt lokal
- Embeddings werden lokal berechnet (sentence-transformers)

---

## 🏗️ Architektur-Entscheidungen

| Entscheidung | Begründung | Sicherheitsimplikation |
|-------------|-----------|----------------------|
| **Phone-First** (Termux) | Kein VPS nötig, API-Key bleibt lokal | ✅ Key sicher auf Gerät |
| **DeepSeek V4 Flash** via OpenRouter | Günstig, leistungsstark | ⚠️ Nur Text-Calls, keine Datenweitergabe |
| **ChromaDB lokal** | Vektor-DB auf dem Gerät | ✅ Keine externen DB-Zugriffe |
| **Embeddings lokal** (sentence-transformers) | Kein externer Embedding-Service | ✅ Daten verlassen Gerät nur für LLM |
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