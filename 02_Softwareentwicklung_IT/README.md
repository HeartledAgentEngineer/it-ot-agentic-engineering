# 02 â€” Softwareentwicklung (IT)

Dieser Bereich bÃ¼ndelt die reinen IT-Software-Projekte des Portfolios: eine Flask-Webanwendung, ein systemweites Windows-Diktier-Tool, eine semantische Wissensdatenbank (RAG) und eine deklarative Dokumenten-Pipeline â€” plus eine kleine Canvas-Demo. Die Ã¼bergreifenden Architektur-Entscheidungen sind im [Root-README](../README.md#architektur-entscheidungen) dokumentiert; die technischen Details stehen in den jeweiligen Projekt-READMEs.

---

## ProjektÃ¼bersicht

| Projekt | Stack | Status (ehrlich) | Doku |
|---|---|---|---|
| **Concertify** (Konzert-Playlists) | Python, Flask, SQLite, Server-Sent Events; Clients fÃ¼r Spotify (spotipy/OAuth), Ticketmaster, setlist.fm, Eventim, Bandsintown, Tavily, Gemini | Funktionaler Prototyp â€” Single-User, lÃ¤uft nur lokal, kein Deployment | [README](concertify/README.md) |
| **typeFREE** (Diktier-Tool) | Python, OpenAI Whisper (`whisper-1`, direkt + OpenRouter-Fallback), OpenRouter/Gemini 2.0 Flash (TextglÃ¤ttung), globale Keyboard-Hooks, System-Tray, pytest | Produktiv im tÃ¤glichen Eigeneinsatz (Windows); 67 automatisierte PrÃ¼fungen; mitlaufende Kostenrechnung im Tray; Android-Companion eingestellt (siehe unten) | [README](typeFREE/README.md) |
| **RAG-System** (Wissensdatenbank) | Python, FastAPI, PostgreSQL/`pgvector`, Mistral `mistral-embed` (1024-D), Hybrid-Suche aus Vektor- und BM25-Suche (RRF) | Funktionaler Prototyp (CLI + Web-UI) â€” Einzelnutzer, kein Rechte-/Mandantenkonzept | [README](RAG-Systeme/README.md) |
| **Document Automation** | Node.js, `docx` (OpenXML), Puppeteer, `pdf-lib` | Stabil als lokales Einzelplatz-Tool; Daten anonymisiert, Ausgaben nicht versioniert | [README](document_automation/README.md) |
| **EichhÃ¶rnchen-Spiel** | HTML5 Canvas, Vanilla JS (eine Datei) | Abgeschlossen â€” Rapid-Prototyping-Demo, keine Weiterentwicklung geplant | [README](eichhoernchen_spiel/README.md) |

Schnellstart-Befehle fÃ¼r alle Projekte stehen gesammelt im [Root-README](../README.md#schnellstart).

---

## Architektur & DatenflÃ¼sse

Das Diagramm zeigt die fÃ¼nf versionierten Projekte und ihre externen Schnittstellen. Document Automation und das EichhÃ¶rnchen-Spiel laufen vollstÃ¤ndig lokal ohne externe Dienste.

```mermaid
flowchart LR
    subgraph Lokal [Rein lokal â€” keine externen Dienste]
        DocAuto[Document Automation<br/>JSON â†’ DOCX/PDF-Pipeline]
        Spiel[EichhÃ¶rnchen-Spiel<br/>Canvas-Demo]
    end

    Concertify[Concertify<br/>Flask Â· SQLite Â· SSE]
    TypeFree[typeFREE<br/>Windows-Client Â· Hotkey Alt+Ã„]
    RAG[RAG-System<br/>FastAPI Â· ingest.py Â· query_db.py]

    subgraph Konzertdaten [Konzert- & Setlist-Quellen]
        TM[(Ticketmaster)]
        SFM[(setlist.fm<br/>~2 Anfragen/s pro IP)]
        Eventim[(Eventim)]
        BIT[(Bandsintown)]
    end

    Spotify[(Spotify Web API)]
    Tavily[(Tavily Search)]
    Gemini[(Google Gemini)]
    G2F[(Gemini 2.0 Flash via OpenRouter)]
    Whisper[(OpenAI Whisper)]
    Mistral[(Mistral AI)]
    PG[(PostgreSQL/pgvector<br/>lokal oder Supabase)]

    Concertify -->|OAuth via spotipy Â· Playlists erstellen| Spotify
    Concertify --> TM
    Concertify --> SFM
    Concertify --> Eventim
    Concertify --> BIT
    Concertify -->|Verifikation & Fallback-Recherche| Tavily
    Concertify -->|KÃ¼nstler-Zuordnung| Gemini

    TypeFree -->|Audio-Transkription| Whisper
    TypeFree -->|TextglÃ¤ttung via OpenRouter| G2F

    RAG -->|Embeddings & Chat| Mistral
    RAG -->|Fallback-QA| Gemini
    RAG -->|Vektor- & BM25-Suche| PG
```

Innerhalb von Concertify ist der Code strikt geschichtet (`routes â†’ services â†’ domain â†’ repositories`, mit Unit-Tests je Schicht unter [tests/](concertify/tests/)) â€” dokumentiert in [dual_engineering_system.md](concertify/docs/dual_engineering_system.md).

---

## Eingestellte Mobile-Prototypen (Pivot-BegrÃ¼ndungen)

Zwei Android-Prototypen wurden bis zum funktionsfÃ¤higen Proof of Concept entwickelt und danach bewusst eingestellt. Sie sind **nicht Teil des Repositories** â€” dies ist die zentrale Stelle, an der die GrÃ¼nde dokumentiert sind.

### Concertify Android (React Native / Expo) â€” der Rate-Limit-Pivot

Die setlist.fm-API limitiert global auf **~2 Anfragen pro Sekunde und IP**. Eine Multi-User-Mobile-App hÃ¤tte dieses Kontingent sofort erschÃ¶pft â€” dauerhafte API-Sperren wÃ¤ren ohne erhebliche zusÃ¤tzliche Server- und Lizenzkosten nicht vermeidbar gewesen. Der Pivot zu einem lokalen Single-User-Flask-Server ([concertify/](concertify/README.md)) lÃ¶st den IP-Konflikt vollstÃ¤ndig, bei null Infrastrukturkosten. Lange Sync-LÃ¤ufe fÃ¤ngt die Web-App Ã¼ber Server-Sent Events mit Live-Fortschritt und atomare JSON-Snapshots ab. Erkenntnisse aus dem Prototyp (zweistufiges Caching: Rohdaten speichern, Filter lokal anwenden) flossen in die Web-Version ein.

### typeFREE Android-Companion â€” an der Plattform-Sandbox gescheitert

Das Kernversprechen von typeFREE â€” diktierten Text systemweit in *jede* fremde App einfÃ¼gen â€” funktioniert unter Windows Ã¼ber globale Keyboard-Hooks und Clipboard-Injektion. Auf Android verhindert die App-Sandbox genau das: Aus einer Expo-/React-Native-App heraus gibt es keinen systemweiten Textzugriff auf andere Apps (z. B. WhatsApp), und Overlay-BeschrÃ¤nkungen des Systems schrÃ¤nkten das geplante Floating-Bubble-Konzept zusÃ¤tzlich ein. Der Prototyp blieb ein kurzes Proof of Concept und wurde verworfen.

### Warum die Prototypen nicht versioniert sind (Sicherheits-Note)

API-SchlÃ¼ssel, die clientseitig in einer verteilten APK liegen, lassen sich per Dekompilierung extrahieren. Beide Codebasen wurden deshalb vom Git-Tracking ausgeschlossen. Wo OAuth nÃ¶tig war (Spotify), kam der PKCE-Flow zum Einsatz, der ohne `Client Secret` auf dem EndgerÃ¤t auskommt â€” das Prinzip â€žkeine Keys in verteilten Clients" ist im [Root-README](../README.md#security--privacy-by-design) als Portfolio-Regel festgehalten.
