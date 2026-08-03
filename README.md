# Agentic Engineering â€” Portfolio: Software von der Web-Anwendung bis zur Maschinensteuerung

> **English summary:** Engineering portfolio of a software developer with an automation background (B.Sc. Electrical & Information Engineering). It covers two isolated domains: **IT** â€” web, voice-to-text, RAG and document-automation projects built with Python and Node.js â€” and **OT** â€” a TwinCAT 3 elevator control coupled with a Node.js ADS bridge and a Three.js 3D HMI as a hardware-in-the-loop simulation. All projects follow a disciplined, phase-based agentic-engineering workflow, documented at the end of this page.

Alle Projekte hier sind mit KI-Coding-Agenten entstanden â€” nach festem Regelwerk, nicht ad hoc.
Das Regelwerk dahinter ([CLAUDE.md](CLAUDE.md)) habe ich aus etablierten Praktiken
zusammengestellt und Ã¼ber mehrere Projekte an meine Arbeit angepasst; entstanden ist es neben
der Arbeit in der Automatisierungstechnik, heute wende ich es vor allem auf Anwendungssoftware an. Das Repository bÃ¼ndelt zwei getrennte DomÃ¤nen:

* **[02_Softwareentwicklung_IT](02_Softwareentwicklung_IT/README.md):** EigenstÃ¤ndige Software-Projekte: Web-Anwendung (Flask), systemweites Diktier-Tool (Windows), semantische Wissensdatenbank (RAG) und deklarative Dokumentengenerierung.
* **[01_IT-OT_Integration](01_IT-OT_Integration/README.md):** Kopplung einer industriellen SPS-Steuerung (TwinCAT 3, Structured Text) mit einer browserbasierten 3D-Visualisierung Ã¼ber eine Node.js-ADS-BrÃ¼cke â€” als Hardware-in-the-Loop-Simulation ohne physische Anlage.

Beide DomÃ¤nen laufen vollstÃ¤ndig isoliert und tauschen keine Daten aus.

---

## ProjektÃ¼bersicht

| Projekt | Stack | Status | Doku |
|---|---|---|---|
| **Aufzug Digital Twin** | TwinCAT 3 (Structured Text), Node.js, `ads-client`, WebSockets, Three.js | Funktionaler Prototyp (HIL-Simulation) | [README](01_IT-OT_Integration/TwinCAT%20Projekts/README.md) |
| **Concertify** (Konzert-Playlists) | Python, Flask, SQLite, Server-Sent Events, Spotify-/Ticketmaster-API | Funktionaler Prototyp (lokaler Einsatz) | [README](02_Softwareentwicklung_IT/concertify/README.md) |
| **typeFREE** (Diktier-Tool) | Python, OpenAI Whisper (`whisper-1`, direkt + OpenRouter-Fallback), OpenRouter/Gemini 2.0 Flash (TextglÃ¤ttung), Keyboard-Hooks, pytest | Produktiv im Eigeneinsatz (Windows); 67 automatisierte PrÃ¼fungen; mitlaufende Kostenrechnung | [README](02_Softwareentwicklung_IT/typeFREE/README.md) |
| **RAG-System** (Wissensdatenbank) | Python, FastAPI, PostgreSQL/`pgvector`, Mistral `mistral-embed` (1024-D), Hybrid-Suche (RRF) | Funktionaler Prototyp | [README](02_Softwareentwicklung_IT/RAG-Systeme/README.md) |
| **Document Automation** | Node.js, `docx` (OpenXML), Puppeteer, `pdf-lib` | Stabil (lokales Tool) | [README](02_Softwareentwicklung_IT/document_automation/README.md) |
| **EichhÃ¶rnchen-Spiel** | HTML5 Canvas, Vanilla JS (eine Datei) | Abgeschlossen (Rapid-Prototyping-Demo) | [README](02_Softwareentwicklung_IT/eichhoernchen_spiel/README.md) |

**Bewusst nicht versioniert:** Zwei mobile Prototypen (Concertify Android, typeFREE Android) wurden nach technischer Evaluierung eingestellt und sind nicht Teil des Repositories â€” u. a. weil API-SchlÃ¼ssel in einer verteilten APK per Dekompilierung auslesbar wÃ¤ren. Die Pivot-BegrÃ¼ndungen stehen im [Bereichs-README](02_Softwareentwicklung_IT/README.md).

### Portfolio-Landkarte

```mermaid
graph LR
    subgraph OT["01 â€” IT-OT-Integration"]
        E["Aufzug Digital Twin (TwinCAT 3 Â· ADS Â· 3D-HMI Â· Physik-Simulation 20 Hz)"]
    end

    subgraph IT["02 â€” Softwareentwicklung IT"]
        C["Concertify (Flask)"]
        T["typeFREE (Windows)"]
        R["RAG-System (FastAPI)"]
        D["Document Automation (Node.js)"]
        S["EichhÃ¶rnchen-Spiel (Canvas)"]
    end

    subgraph APIs["Angebundene KI- & Cloud-APIs"]
        WH["OpenAI Whisper (direkt + OpenRouter)"]
        G2F["Gemini 2.0 Flash (via OpenRouter)"]
        MB["Mistral Embed"]
        G2["Google Gemini (direkt)"]
        SP["Spotify Â· Ticketmaster Â· setlist.fm"]
    end

    subgraph AE["Agentic Engineering Plattform"]
        CLI["VS Code + Cline Â· Claude Code Â· Antigravity"]
        MOD["DeepSeek V4 Â· Gemini 2.5 Flash Â· Haiku (OpenRouter)"]
        WF["8-Phasen-Workflow Â· FremdprÃ¼fung Â· DSGVO-Zone"]
    end

    C["Concertify (Flask)"] --> SP
    C --> G2
    T["typeFREE (Windows)"] --> WH
    T --> G2F
    R["RAG-System (FastAPI)"] --> G2
    R --> MB
```

Detail-Diagramme (DatenflÃ¼sse, APIs, Schichten) liegen in den jeweiligen Projekt-READMEs.  
Das Data-Flow-Diagramm der IT-Projekte (02) findet sich im [zugehÃ¶rigen Bereichs-README](02_Softwareentwicklung_IT/README.md#architektur--datenflÃ¼sse).

---

## Verzeichnisstruktur

```
â”œâ”€â”€ .claude/skills/                      # AusfÃ¼hrbare Agenten-Verfahren
â”‚   â”œâ”€â”€ grill-me/                        #   Alignment-Interview (Phase 2)
â”‚   â””â”€â”€ critic/                          #   FremdprÃ¼fung durch zweites Modell (pruefe.mjs)
â”œâ”€â”€ 01_IT-OT_Integration/
â”‚   â””â”€â”€ TwinCAT Projekts/
â”‚       â”œâ”€â”€ README.md
â”‚       â””â”€â”€ Elevator_TC/                # TwinCAT-3-Projekt
â”‚           â”œâ”€â”€ Elevator_TC/            #   SPS-Code: FB_Elevator, FB_Door, E_ElevatorState â€¦
â”‚           â”œâ”€â”€ ads_bridge/             #   Node.js ADS-WebSocket-BrÃ¼cke (server.js)
â”‚           â””â”€â”€ elevator_3d_demo.html   #   Three.js 3D-HMI
â”œâ”€â”€ 02_Softwareentwicklung_IT/
â”‚   â”œâ”€â”€ README.md
â”‚   â”œâ”€â”€ concertify/                     # Flask-App: routes/ services/ domain/ repositories/ + tests/
â”‚   â”œâ”€â”€ typeFREE/                       # Windows-Diktier-Client + Installer (typefree.py, installer/)
â”‚   â”œâ”€â”€ RAG-Systeme/                    # ingest.py Â· query_db.py Â· main.py (FastAPI) Â· static/
â”‚   â”œâ”€â”€ document_automation/            # build_cv.js Â· build_pdf.js Â· merge_pdfs.js
â”‚   â””â”€â”€ eichhoernchen_spiel/            # index.html (Canvas-Demo)
â”œâ”€â”€ CLAUDE.md                           # Globales Agenten-Regelwerk (die eine Quelle)
â”œâ”€â”€ AGENTS.md                           # Herstellerneutraler Wegweiser auf CLAUDE.md
â”œâ”€â”€ sync-rules.ps1                      # Erzeugt die Bereichs-CLAUDE.md aus CLAUDE_EXTENDS.md
â””â”€â”€ README.md
```

---

## Architektur-Entscheidungen

**1. TwinCAT: Hardware-in-the-Loop statt Physik in der SPS.** SPS-Laufzeiten haben keine native Physik. Statt die Steuerungslogik mit kÃ¼nstlichen VerzÃ¶gerungen zu verfÃ¤lschen, simuliert die Node.js-BrÃ¼cke das mechanische Verhalten (KabinenhÃ¶he, TÃ¼ren) im 50-ms-Zyklus und liefert simulierte Sensorwerte an die reale SPS-Logik zurÃ¼ck. Die Schrittkette nutzt ein typsicheres Enum (`eStep : E_ElevatorState`); Not-Halt und Brandfall haben auf SPS-Ebene Vorrang und sind vom HMI nicht Ã¼bersteuerbar. â†’ [Details](01_IT-OT_Integration/TwinCAT%20Projekts/README.md)

**2. Concertify: Pivot von Mobile zu lokalem Web-Server.** Die setlist.fm-API limitiert global auf ~2 Anfragen/Sekunde pro IP. Eine Multi-User-Mobile-App hÃ¤tte dieses Kontingent sofort erschÃ¶pft; der Wechsel zu einem lokalen Single-User-Flask-Server lÃ¶st den IP-Konflikt ohne Serverkosten. Lange Sync-LÃ¤ufe werden Ã¼ber Server-Sent Events mit Live-Fortschritt und atomare JSON-Snapshots abgefedert. â†’ [Details](02_Softwareentwicklung_IT/concertify/README.md)

**3. RAG-System: AblÃ¶sung von n8n durch eine Python-Pipeline.** Der erste Entwurf als visueller n8n-Cloud-Workflow lieÃŸ sich schlecht versionieren und nicht automatisiert testen. Die Migration zu Skripten ([ingest.py](02_Softwareentwicklung_IT/RAG-Systeme/ingest.py), [query_db.py](02_Softwareentwicklung_IT/RAG-Systeme/query_db.py)) macht die Kernlogik â€” absatz- und satzgrenzenbasiertes Chunking, Hybrid-Suche aus `pgvector`-Vektorsuche und BM25 via Reciprocal Rank Fusion â€” als testbaren, diffbaren Code sichtbar. â†’ [Details](02_Softwareentwicklung_IT/RAG-Systeme/README.md)

**4. typeFREE: Clipboard-Injektion statt Tastatur-Simulation.** Diktate werden im RAM aufgezeichnet, per Whisper transkribiert, durch OpenRouter/Gemini 2.0 Flash von FÃ¼llwÃ¶rtern befreit und Ã¼ber die Zwischenablage (`Strg+V`) in das aktive Fenster injiziert. Das EinfÃ¼gen als ein Block statt zeichenweiser Tastensimulation vermeidet Umlaut-Codierungsfehler und Timing-Probleme. â†’ [Details](02_Softwareentwicklung_IT/typeFREE/README.md)

**5. Document Automation: deklarative Dokumente statt manueller Formatierung.** LebenslÃ¤ufe und Anschreiben werden aus strukturierten Daten per Code generiert (OpenXML/`docx`, Puppeteer-PDF-Rendering). InhaltsÃ¤nderungen kÃ¶nnen das Layout nicht mehr zerschieÃŸen; die Engine ist strikt von den privaten Bewerbungsdaten getrennt, die nie ins Repository gelangen. â†’ [Details](02_Softwareentwicklung_IT/document_automation/README.md)

---

## Agentic Engineering als Methode

Alle Projekte sind mit KI-Coding-Agenten entstanden â€” nicht ad hoc, sondern entlang eines festen Regelwerks, das selbst Teil des Repositories ist.  
Dieser Abschnitt beschreibt nicht nur die Methode, sondern auch die **persÃ¶nliche Reise**, die dahinter steht: 9 Monate Experimentieren mit Plattformen, Modellen und Kostenmodellen, deren Erkenntnisse in jeden Aspekt des Workflows eingeflossen sind.

### Meine Reise: Von Claude Code zum Multi-Modell-System

| Zeit | Setup | Warum? |
|---|---|---|
| **2025** | Erste Gehversuche: Chatbots personalisiert, System-Prompts mit Ingenieurs-Denkweise optimiert | PrÃ¤-Agenten-Ã„ra â€” den Grundstein fÃ¼r strukturierte Prompt-Architektur gelegt |
| **Januar 2026** | Start mit **Claude Code** (Enterprise-Team-Lizenz, Sonnet, Opus) | Erster KI-Coding-Agent im professionellen Einsatz |
| **MÃ¤rzâ€“Mai 2026** | Berufliche Praxis: TwinCAT 3, VB.NET-HMI, IO-Listen-Generierung, Schaltplan-Vergleich | KI als "Experience-Partner" â€” schneller lernen, nicht langsamer; Vorreiter im Team gegen alte Denkweise |
| **Juniâ€“Juli 2026** | **Antigravity** + Google One (2Ã— 12 â‚¬) â€” Test gÃ¼nstigerer Alternative | Kosten sparen, aber unzufrieden mit Ergebnissen |
| **August 2026** | **VS Code + Cline** (Agent-Harness) + **OpenRouter** + Multi-Modell | Claude Code-Limits verschÃ¤rft; DSGVO-konforme, kosteneffiziente Alternative gefunden |

**Das heutige Setup:** Nicht *ein* Tool, sondern ein orchestriertes System aus Plattformen und Modellen:

| Aufgabe | Werkzeug | Modell |
|---|---|---|
| Planung & Implementierung | VS Code + Cline | **DeepSeek V4** (kostengÃ¼nstig) |
| Bildverarbeitung | VS Code + Cline (Modell-Wechsel) | **Gemini 2.5 Flash** (beste Bild-Interpretation) |
| FremdprÃ¼fung (Critic) | OpenRouter (API-Gateway) | **Anthropic Haiku** (DSGVO-konform, andere Modellfamilie) |
| Alternativ-Plattformen | Claude Code / Antigravity | Je nach VerfÃ¼gbarkeit & Kontingent |

> **Die Kern-Erkenntnis:** Nicht das Tool entscheidet Ã¼ber QualitÃ¤t, sondern das **System aus orchestrierten Modellen**, das je nach Aufgabe, Kosten und Compliance das passende Modell wÃ¤hlt.

### Phasenbasierter Entwicklungszyklus

Jedes Feature durchlÃ¤uft acht Phasen: **Brainstorm â†’ Alignment â†’ Planung â†’ Implementierung â†’ Testing â†’ Recap â†’ Refactor â†’ Commit**. Gearbeitet wird in kleinen vertikalen Slices mit atomaren Commits; nach jeder Phase wird der Agenten-Kontext geleert, weil Modelle bei wenig und prÃ¤zisem Kontext am zuverlÃ¤ssigsten arbeiten. Drei Regeln stechen heraus:

* Im *Alignment* werden alle architektonischen Verzweigungen per Interview geklÃ¤rt, bevor Code entsteht â€” der Agent trifft keine Gestaltungsentscheidung selbst.
* *Testing*, *Recap* und *Refactor* dÃ¼rfen nie Ã¼bersprungen werden.
* In den Phasen *Planung*, *Testing* und *Refactor* prÃ¼ft ein **fremdes Modell** gegen (siehe unten). In der *Implementierung* ist das ausdrÃ¼cklich untersagt: Kritik wÃ¤hrend des Bauens zerfasert die Umsetzung.

### Ein Regelwerk, drei Einstiege

Damit die Regeln nicht an mehreren Stellen auseinanderlaufen, gibt es genau **eine** Quelle:

| Datei | Rolle |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Die Quelle: Leitplanken, Arbeitsweise, 8-Phasen-Workflow |
| [AGENTS.md](AGENTS.md) | Herstellerneutraler Wegweiser fÃ¼r Agenten, die diese Konvention lesen (Codex, Antigravity, Cursor) â€” er verweist, er kopiert nicht |
| `CLAUDE_EXTENDS.md` je Bereich | Nur die Zusatzregeln der DomÃ¤ne: SPS-Namenskonventionen (Ungarische PrÃ¤fixe, Zehner-Schrittketten) in OT, Design- und SEO-Vorgaben in IT |

[sync-rules.ps1](sync-rules.ps1) erzeugt daraus die Bereichs-`CLAUDE.md`: ein Verweis auf die Wurzel-Datei plus die lokale Erweiterung.

**Der Umbau dahinter:** UrsprÃ¼nglich kopierte das Skript das komplette Basis-Regelwerk in jede Bereichsdatei. Das erzeugte zwei Probleme â€” die Kopien konnten unbemerkt von der Quelle abdriften, und jeder Agent lud dieselben ~130 Zeilen ein zweites Mal in seinen Kontext. Heute steht dort ein zweizeiliger Verweis; die Basisregeln liest der Agent ohnehin von der Wurzel aus mit.

### Zwei ausfÃ¼hrbare Skills statt Prosa-Regeln

Die zwei heikelsten Stellen im Zyklus sind nicht als Merksatz formuliert, sondern als Verfahren mit festem Ablauf, Abbruchkriterium und einer Tabelle typischer Ausreden samt Gegenrede.

**[`grill-me`](.claude/skills/grill-me/SKILL.md) â€” der Grill *vor* dem Bauen.** Alignment als ausfÃ¼hrbares Verfahren: erst ein Register aus 8â€“15 Annahmen zum Widersprechen, dann sokratische Einzelfragen â€” eine pro Nachricht, immer mit 2â€“4 konkreten Optionen und einer begrÃ¼ndeten Empfehlung, sodass eine Antwort aus einem Buchstaben bestehen kann. Danach drei Angriffe auf das eigene Ergebnis (*â€žDas scheitert, wenn â€¦"*), erst dann die `alignment.md`. Die eiserne Regel: keine Datei-Ã„nderung am Zielprojekt, bevor das Alignment freigegeben ist. Zeichnen sich mehr als ~15 Fragen ab, gilt nicht die Fragenzahl als Problem, sondern der Slice â€” dann wird geteilt.

**[`critic`](.claude/skills/critic/SKILL.md) â€” der Grill *nach* dem Bauen.** Generator-Critic-Muster Ã¼ber zwei Modellfamilien: ein Modell baut, ein Modell einer anderen Familie prÃ¼ft, weil beide unterschiedliche blinde Flecken haben. Zwei Konstruktionsprinzipien: Das fremde Modell bekommt den Code im Prompt Ã¼bergeben â€” es liest keine Dateien und fÃ¼hrt nichts aus. Und es liefert **Befunde, keine Urteile**: entschieden wird je Punkt vom Menschen, nie automatisch behoben. Einstiegspunkt ist [`pruefe.mjs`](.claude/skills/critic/pruefe.mjs), das Prompt, Format und Fehlerbehandlung mitbringt:

| Motor | Aufruf | Kontingent | EinschrÃ¤nkung |
|---|---|---|---|
| **Haiku via OpenRouter** (DSGVO-Standard) | `--openrouter` oder Flag-frei | API-Kosten | DSGVO-konform, Daten nicht zur Produktverbesserung; API-Key per Header |
| Gemini-API (Fallback) | `--gemini` | 1.500 LÃ¤ufe/Tag | API-SchlÃ¼ssel nÃ¶tig, per Header Ã¼bertragen â€” nie in der URL |
| Antigravity | `--agy` | 20 LÃ¤ufe/Tag | kein SchlÃ¼ssel nÃ¶tig, max. 30.000 Zeichen |
| Codex (Sonderfall) | explizit | Monatskontingent | schÃ¤rfer bei NebenlÃ¤ufigkeit, nur auf ausdrÃ¼cklichen Wunsch |

### Was die FremdprÃ¼fung messbar gelehrt hat

1. **GroÃŸer PrÃ¼fumfang kostet Befunde.** Gleicher Code, gleiches Modell: Bei 27.000 Tokens meldete der Critic einen schweren Befund (Feldzugriff auf ein mÃ¶glicherweise nicht gesetztes Objekt). Im Wiederholungslauf mit 62.000 Tokens fehlte genau dieser Befund. Konsequenz: lieber drei gezielte LÃ¤ufe Ã¼ber einzelne Dateien als einer Ã¼ber alles â€” das Kontingent ist reichlich, die Aufmerksamkeit des Modells ist der Engpass.
2. **Schweregrade sind unzuverlÃ¤ssig.** Dieselbe SQL-Injection kam je nach Modell als *kritisch* oder *hoch* zurÃ¼ck, ein sicherer Absturz als *mittel*. Jeder Befund wird deshalb nachgestuft und die Korrektur kenntlich gemacht, statt das Protokoll durchzureichen.
3. **Ein leeres Protokoll ist keine Freigabe.** Die FremdprÃ¼fung findet andere Dinge als ein Testlauf, nicht dieselben â€” sie ersetzt die Testphase nicht.
4. **Fehlerausgaben nie unterdrÃ¼cken.** Wird `stderr` verworfen, ist ein Kontingent- oder Authentifizierungsfehler nicht mehr von einem leeren Ergebnis zu unterscheiden. Genau daran ist der erste Aufbau mehrfach gescheitert.

### DSGVO-konforme Zone: OpenRouter als API-Gateway

Ein zentrales Merkmal der aktuellen Architektur: **OpenRouter dient als DSGVO-konformes API-Gateway**, das die Nutzung von Modellen (z. B. Anthropic Haiku fÃ¼r die FremdprÃ¼fung) ermÃ¶glicht, ohne dass Daten zur Produktverbesserung verwendet werden dÃ¼rfen.

| Aspekt | Umsetzung |
|---|---|
| Datenverarbeitung | OpenRouter verarbeitet Anfragen DSGVO-konform; keine Nutzung der Inhalte fÃ¼r Modell-Training |
| API-Key-Handling | SchlÃ¼ssel per Header (nie in der URL), zusÃ¤tzlich abgesichert durch `.env` und `.gitignore` |
| Kostenkontrolle | Pay-per-Use statt Abo â€” gÃ¼nstiger als Flatrate-Modelle bei geringem Volumen |
| Zukunfts-Roadmap | Concertify soll von direkter Gemini-API auf OpenRouter umgestellt werden |

### Grenze der FremdprÃ¼fung: was das Repository nicht verlÃ¤sst

Im kostenlosen Tier nutzt der Anbieter Ã¼bermittelte Inhalte zur Produktverbesserung. Deshalb geht ausschlieÃŸlich Code aus [02_Softwareentwicklung_IT](02_Softwareentwicklung_IT/README.md) an ein fremdes Modell. **SPS- und OT-Code aus [01_IT-OT_Integration](01_IT-OT_Integration/README.md), Kundendaten und alles unter NDA sind ausgenommen** â€” festgehalten als Bereichsdirektive in [CLAUDE.md](CLAUDE.md), nicht als guter Vorsatz.  
Selbst mit OpenRouter bleibt diese Grenze bestehen â€” DSGVO-konform heiÃŸt nicht automatisch "darf das Repository verlassen".

### QualitÃ¤ts-Gates: Architekt & WÃ¤chter

Jede grÃ¶ÃŸere Ã„nderung durchlÃ¤uft zwei komplementÃ¤re Rollen: Der **Architekt** entwirft (strikte Schichtung `routes â†’ services â†’ domain â†’ repositories`, Dependency Injection Ã¼ber Konstruktoren), der **WÃ¤chter** prÃ¼ft anschlieÃŸend gegen einen festen Katalog:

| Check | Kriterium |
|---|---|
| Kapselung | Keine Schicht greift an einer anderen vorbei |
| Dependency Injection | AbhÃ¤ngigkeiten Ã¼ber Konstruktor/Abstraktionen, keine versteckten Globals |
| Testbarkeit | Kernlogik testbar ohne echte I/O |
| KomplexitÃ¤t | Methoden kompakt halten, Early Returns statt Verschachtelung |
| Frontend | Event-Delegation statt Inline-Handler |

Angewendet und dokumentiert ist das System im Concertify-Projekt: [dual_engineering_system.md](02_Softwareentwicklung_IT/concertify/docs/dual_engineering_system.md). Sichtbares Ergebnis ist die Testsuite unter [concertify/tests/](02_Softwareentwicklung_IT/concertify/tests/) (Unit-Tests je Schicht: `domain/`, `repositories/`, `services/`).

---

## Security & Privacy by Design

* **Secrets-Kapselung:** API-SchlÃ¼ssel liegen ausschlieÃŸlich in `.env`-Dateien, die per `.gitignore` ausgeschlossen sind. Eine [.env.example](02_Softwareentwicklung_IT/concertify/.env.example) dokumentiert die erwarteten Variablen, ohne Werte offenzulegen.
* **Keine Keys in verteilten Clients:** Die mobilen Prototypen wurden u. a. deshalb nicht versioniert, weil clientseitig eingebettete API-SchlÃ¼ssel per Dekompilierung extrahierbar wÃ¤ren; fÃ¼r OAuth kam dort der PKCE-Flow zum Einsatz, der ohne `Client Secret` auf dem EndgerÃ¤t auskommt.
* **Lokale Verarbeitung sensibler Daten:** Die Dokumentengenerierung lÃ¤uft vollstÃ¤ndig lokal; private Bewerbungsdaten sind vom versionierten Code getrennt und nicht Teil des Repositories.
* **Transparente Cloud-Grenzen:** Wo externe LLM-APIs genutzt werden (Whisper, Mistral, Gemini), ist das in den Projekt-READMEs ausgewiesen â€” inklusive der DatenflÃ¼sse.

---

## Schnellstart

### Concertify (Flask-Webapp)
```bash
cd 02_Softwareentwicklung_IT/concertify
pip install -r requirements.txt
python app.py
# â†’ http://localhost:5000
```

### typeFREE (Windows-Diktier-Client)
```bash
cd 02_Softwareentwicklung_IT/typeFREE/windows
pip install -r requirements.txt
python typefree.py
# LÃ¤uft im Systemtray; Aufnahme per Alt + Ã„ (halten).
# SchlÃ¼ssel stehen in einer .env neben dem Programm â€” nie im Code, nie in der EXE.
# PrÃ¼fungen: set PYTHONPATH=. && python -m pytest windows/tests -v
```

### RAG-System (Wissensdatenbank)
```bash
cd 02_Softwareentwicklung_IT/RAG-Systeme
pip install -r requirements.txt
python init_db.py      # Schema anlegen (PostgreSQL/pgvector, z. B. Supabase)
python ingest.py       # Dokumente einlesen und einbetten
python query_db.py     # CLI-Abfrage â€” alternativ: python main.py (FastAPI-Web-UI, Port 8000)
```

### Aufzug Digital Twin (TwinCAT + ADS-BrÃ¼cke)
1. `01_IT-OT_Integration/TwinCAT Projekts/Elevator_TC/Elevator_TC.sln` in TwinCAT 3 Ã¶ffnen, Konfiguration aktivieren, SPS in den Run-Modus versetzen.
2. BrÃ¼cke starten:
   ```bash
   cd "01_IT-OT_Integration/TwinCAT Projekts/Elevator_TC/ads_bridge"
   npm install
   npm start
   ```
3. `elevator_3d_demo.html` im Browser Ã¶ffnen.

### EichhÃ¶rnchen-Spiel
`02_Softwareentwicklung_IT/eichhoernchen_spiel/index.html` direkt im Browser Ã¶ffnen â€” keine AbhÃ¤ngigkeiten.
