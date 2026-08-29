# Coding-Auftrag: Modell-Scores & gewichteter „bester Mix"

- Datum: 2026-08-24
- Status: Entwurf zur Besprechung (noch nicht implementiert)
- Betroffener Bereich: `personal_ai_agent` Backend + Frontend (Modellauswahl)

## Kontext (aus Nutzerdiktat)

Wenn bei der Modellauswahl **mehrere Stärken** ins Spiel kommen, soll nicht nur ein
einzelnes „bestes Modell", sondern der **beste Mix** angezeigt werden — gesteuert
über eine **Gewichtung**. Dafür braucht jedes Modell einen **Score** pro
Kompetenzbereich (z. B. „wie stark im Coding?"), gestützt auf **Benchmarks** und
bekannte Stärken (Größe, Multimodalität, Reasoning, Kosten). Aus der gewichteten
Kombination wird dann die beste Auswahl abgeleitet und beim Modell-Picken angezeigt.

Das Backend kennt heute schon *qualitative* Stärke-Profile
(`MODELL_STAERKEN_DE`), deutsche Einsatz-Empfehlungen (`MODELL_USECASES_DE`) und
textliche Benchmark-Referenzen (`MODELL_BENCHMARK_REF`), zusammengesetzt in
`llm_service.list_models()`. Es fehlt der **quantitative Score** und die
**gewichtete Optimierung/Anzeige**.

## Ziel

Ein Modellauswahl-Feature, das pro Modell

1. eine **numerische Stärke je Kompetenzdimension** führt (0–100 o. ä.), und
2. daraus einen **gewichteten Gesamt-Score** berechnet (Gewichtung je Anwendungsfall
   bzw. vom Nutzer einstellbar),
3. beim Auswählen den **besten Mix** (bestbewertete Kombination) übersichtlich zeigt.

## Anforderungen

### A) Score-Datenmodell
- Jedes Modell erhält ein Profil: `{ coding, reasoning, multimodal/vision,
  kosten_effizienz, latenz }` als numerische Werte (Normierung z. B. 0–100).
- Quelle ehrlich kennzeichnen:
  - gepflegte Werte (manuell in Code, vgl. bestehende `MODELL_*_DE`-Dicts), oder
  - abgeleitet aus bestimmten Benchmarks (SWE-Bench für Coding, Multimodal-
    Benchmarks, Preis/Latenz aus OpenRouter-Katalog).
  - Keine erfundenen Werte: Fehlt die Quelle → Feld leer, UI zeigt keinen Score
    (Muster der bestehenden „keine erfundene Empfehlung"-Regel).
- Bestehende Dicts (`MODELL_STAERKEN_DE`, `MODELL_BENCHMARK_REF`, `MODELL_USECASES_DE`)
  als Basis nutzen statt neu zu duplizieren.

### B) Gewichtung & Gesamt-Score
- Pro Anwendungsfall (Coding-Agent, Reasoning/Analyse, Bilder/Vision, Budget/Schnell)
  eine **Standardgewichtung** der Dimensionen.
- Optional: Nutzer-Gewichtung einstellbar (Frontend-Slider), die die Standardwerte
  überschreibt.
- Gesamt-Score = gewichtete Summe der Dimensionsscores, eindeutig nachvollziehbar
  (Formel in Doku und UI).

### C) „Bester Mix"-Anzeige
- Rangliste der Modelle sortiert nach gewichtetem Gesamt-Score.
- „Bester Mix": das ehrliche Empfehlungs-Set je Bedarf (z. B. 1 × stark im Coding +
  1 × stark in Vision + 1 × günstig/schnell), also nicht nur das eine Topmodell.
- Anzeige beim Modell-Picken (Frontend `index.html`/`app.js` / Endpoint
  `GET /api/models`), kein Copy-Dump der Fibel in den Chat.

### D) Doku-Pflicht (Code + Docs, Bewerbungsmappe)
- Jede Änderung zieht die zugehörige Doku nach (Skizze/README/Abschnitt Modellwahl),
  zusammen committen. Doku muss codegenau sein.

## Integrationspunkte (Stand Stand-Check)

- `backend/app/modelle_use.py` → hier Scores/Datenmodell ergänzen (neben
  `MODELL_STAERKEN_DE`, `MODELL_BENCHMARK_REF`).
- `backend/app/modelle_de.py` → deutsche Beschreibungen, falls nötig.
- `backend/app/services/llm_service.py` → `_staerke_ableiten()` & `list_models()`
  erweitern (Feld `score`/`scores`, `mix`).
- `backend/app/router/llm_models.py` → `GET /api/models` reichert Antwort an.
- `frontend/app.js`, `frontend/index.html`, `frontend/style.css` → Anzeige des
  bestbewerteten Mix in der Modellauswahl.
- `docs/` → neue/aktualisierte Abschnitte zur Modellwahl.

## Offene Entscheidungspunkte (bitte bestätigen)

1. **Score-Quelle:** manuell gepflegte Scores (wie heute die Stärke-Dicts) ODER
   automatisch aus Benchmarks abgeleitet ODER Hybrid (gepflegt + Benchmark-Referenz
   als Beleg)?
2. **„Bester Mix"-Bedeutung:** (a) reine Rangliste mit gewichtetem Gesamt-Score,
   oder (b) automatisch zusammengestelltes Bedarfs-Set (Coding+Vision+Budget)?
3. **Wichtest Du die Gewichtung selbst** (Slider im UI) oder reichen feste
   Standardgewichtungen pro Anwendungsfall?
4. **Wo speichern:** diesen Auftrag ins `docs/` legen (aktueller Weg), oder ins
   Auftragsbuch `auftraege.json` übernehmen?

## Akzeptanzkriterien (Vorschlag)

- Jedes nutzbare Modell in `GET /api/models` hat einen (gepflegten oder fehlenden)
  Score — nie einen erfundenen.
- Gewichtete Sortierung des bestbewerteten Mix ist im Frontend sichtbar.
- Alle Scores/Formeln sind in der Doku nachvollziehbar.
- `.env` unangetastet, keine Keys im Code.
- Code **und** Doku committen; **kein PUSH** ohne OK-Dialog (Git-Regel).