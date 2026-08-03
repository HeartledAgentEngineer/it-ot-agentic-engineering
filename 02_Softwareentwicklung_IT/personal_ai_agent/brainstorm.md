# 🧠 BRAINSTORM – Universeller KI-Agent für den Alltag

> **Phase 1** | Datum: 02.08.2026 | Status: Brainstorm (roh)
> Nächster Schritt: Phase 1b — grillAnAgent

---

## 🎯 Vision

Ein **datenschutzkonformer, persönlicher KI-Agent**, der mir im Alltag hilft:
- Spracheingabe-gesteuert (Handy/PC)
- Zugriff auf Mails, Cloud, Bilder
- Persönliches Gedächtnis (Vektor-DB)
- DSGVO/Voik-UFO-konform (deutsche/europäische Server)
- Später: Alexa-Integration, Multi-Agenten (Spezialisten für verschiedene Tasks)
- Budget: ~20€/Monat
- Unabhängig von US-Cloud-Diensten (kein OpenAI, kein Gemini-Training mit meinen Daten)

---

## 🏗️ Architektur-Entscheidungen

| Entscheidung | Wert | Begründung |
|---|---|---|
| **Multi-Agentisch** | ✅ Produkt + Entwicklung | Produkt: Spezial-Agenten. Entwicklung: Sub-Agenten im Workspace |
| **Start-Infrastruktur** | Hetzner VPS (~5€/Monat) + OpenRouter | Später Migration zu Azure |
| **Cloud-Ziel** | Azure Free Trial (200$ + 12 Monate) | Später ggf. Student-Lizenz über Uni-Kontakte |
| **LLM-Backend** | OpenRouter (verschiedene Modelle, kein Claude-"Klein") | Flexibel, DSGVO-Optionen, kostengünstig |
| **Spracheingabe** | Hybrid (lokal + Cloud) | Lokal: Whisper auf Handy (CPU). Cloud: Whisper via API bei Bedarf |
| **Gedächtnis** | Vektor-DB (zuerst SQLite + Embeddings, später pgvector) | Persönliches Langzeitgedächtnis |
| **Android-Trigger** | Gemini/"OK Google" als Wakeword | Per Deep-Link öffnet Gemini unsere App — kein Datenabfluss außer Trigger-Wort |
| **Entwicklungstool** | Cline (dieser Workspace) | Multi-Agentische Entwicklung mit Claude Code |

---

## 🗺️ Mögliche Features (gesammelt)

> **Sortiert nach Priorität für erste Iterationen**

### Must-have (MVP – Erster Slice)
- [x] **Sprach-Chat mit Gedächtnis** — Sprechen + Agent merkt sich Dinge
- [ ] Vektor-DB für Langzeitgedächtnis
- [ ] Web-Interface (PWA) für PC + Handy
- [ ] Lokales STT auf Android (Whisper tiny/base)
- [ ] Deep-Link-Trigger von Gemini ("Hey Gemini, öffne meinen Agenten")

### Nice-to-have (Zweite Iteration)
- [ ] E-Mail-Integration (IMAP/pCloud)
- [ ] Cloud-Zugriff (pCloud API)
- [ ] Web-Suche/Browser-Funktion
- [ ] Bildersortierung/-analyse

### Future (Langfristig)
- [ ] MCP-Server — damit Cline (ich) auf Agenten-Gedächtnis zugreifen kann
- [ ] Multi-Agenten-Orchestrierung (Spezialisten: Mail-Agent, Bilder-Agent, Termin-Agent)
- [ ] Alexa-Integration
- [ ] Vollständige Azure-Migration
- [ ] Fine-Tuning / Personalisierung über Zeit

---

## 📐 Technologie-Stack (geplant)

| Komponente | Technologie | Alternative |
|---|---|---|
| **Backend** | Python (FastAPI) | Node.js (Express) |
| **LLM-Gateway** | OpenRouter API | Azure OpenAI Service |
| **Vektor-DB** | Chroma / SQLite-vss | pgvector (Postgres) |
| **Spracherkennung (lokal)** | Whisper.cpp (Android/Termux) | Vosk |
| **Spracherkennung (Cloud)** | Whisper via OpenRouter | Azure Speech |
| **Text-to-Speech** | OpenRouter TTS / lokale Engine | ElevenLabs |
| **Android-App** | WebView PWA + Deep Links | Native Android (Kotlin) |
| **Hosting (Phase 1)** | Hetzner VPS (5€/Monat) | Azure B1s VM |
| **CI/CD** | GitHub Actions | Manuell |

---

## 🔧 Erster Vertical Slice (MVP)

**"Sprach-Chat mit Gedächtnis"**

```
[Handy]  "Hey Gemini, öffne meinen Agenten"
    → Deep-Link öffnet PWA mit aktivem Mikrofon
    → Lokales Whisper transkribiert Sprache (kein Google!)
    → Transkript → OpenRouter (LLM) → Antwort
    → Gedächtnis: Embedding + Vektor-DB (Kontext merken)
    → Antwort zurück → TTS (lokal/Cloud) → gesprochene Antwort
```

### Was kann der MVP schon?
- Sprach-Chat in beide Richtungen (sprechen + Antwort hören)
- Der Agent merkt sich Dinge aus vorherigen Gesprächen
- Läuft auf PC + Handy (PWA)
- Datenschutz: keine Audiodaten zu Google/OpenAI

### Was kann er NOCH nicht?
- ❌ Mails lesen
- ❌ Cloud-Zugriff
- ❌ Web-Suche
- ❌ Bilder sortieren
- ❌ Alexa

---

## ⚠️ Offene Fragen (für Phase 2 — Alignment)

1. **Modell-Auswahl**: Welches OpenRouter-Modell für den Agenten? (Haiku? Sonstiges?)
2. **TTS**: Soll die Antwort gesprochen werden (lokal? Cloud?)
3. **Authentifizierung**: Wie stellen wir sicher, dass nur ich den Agenten nutze?
4. **PWA vs. Native**: Reicht eine Web-App mit Deep-Link, oder native Android-App?
5. **Gedächtnis-Struktur**: Was soll gemerkt werden? Alles? Nur Zusammenfassungen? Nur Fakten?
6. **Azure-Timing**: Free Trial jetzt aktivieren oder erst bei Deployment?

---

## 💰 Budget-Schätzung (MVP, monatlich)

| Posten | Kosten | Notiz |
|---|---|---|
| Hetzner VPS (CX22) | ~5,90 € | 2 vCPU, 4 GB RAM |
| OpenRouter API | ~5-15 € | Bei moderater Nutzung |
| Domain (optional) | ~1-2 € | z.B. agent.sebastian.domain |
| Azure (später) | 0 € (Free Trial) | 200$ Guthaben + 12 Monate Free |
| **Gesamt MVP** | **~10-20 €/Monat** | ✅ Budget eingehalten |

---

*Geschrieben von Cline (Agent) im Auftrag von Sebastian*