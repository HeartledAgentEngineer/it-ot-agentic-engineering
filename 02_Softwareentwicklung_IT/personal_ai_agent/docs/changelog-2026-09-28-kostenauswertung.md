# Changelog 28.09.2026 — Kostenauswertung (OpenRouter + lokale Sitzungsdaten)

## Was neu ist

`tools/kosten/auswertung.py` — sammelt **nur aggregierte Zahlen**:

| Abschnitt | Quelle |
|---|---|
| Guthaben (aufgeladen / verbraucht / übrig) | `GET /api/v1/credits` |
| Aktivität der letzten 30 Tage je Tag **und** Modell (Kosten, Anfragen, Prompt-/Completion-Tokens) | `GET /api/v1/activity` |
| Wochensummen aus der lokalen Hermes-Sitzungsdatenbank | `state.db`, Tabelle `sessions` — **nur Zahlen-Spalten** |
| Urlaubsfenster (30.08.–13.09.2026) getrennt | Markierung im Bericht |

Ausgabe: `.hermes/bus/auswertung-kosten.md` (**außerhalb des Repos**, wird nicht
versioniert). Keine Nachrichtentexte, keine Sitzungstitel, keine Namen.

## Gemessener Stand (28.09.2026)

- Aufgeladen **208,00 $**, verbraucht **198,72 $**, verfügbar **9,28 $**
- Letzte 30 Tage: **138,47 $** über **32.512** Anfragen; davon **54,41 $** (39 %)
  im Urlaubsfenster
- Treiber: `deepseek-v4-flash-0731` **70,09 $** (2,88 **Mrd.** Prompt-Tokens),
  `deepseek-v4.1-flash` **59,93 $**
- Billig im Vergleich: alle Bild-/Screenshot-Aufrufe (`gemini-2.5-flash`)
  **3,62 $**, Einbettungen **0,40 $**, Prüfer (`gpt-5.6-luna`) **1,41 $**

**Folgerung:** Der Hebel ist die **Kontextmenge**, nicht der Modellpreis —
neue Sitzung pro Aufgabe, Cache warm halten, Archive über Werkzeuge statt in den
Chat.

## Schlüsselablage (Nebenbefund)

Der normale OpenRouter-Schlüssel liegt in `%LOCALAPPDATA%\hermes\.env`
(Hermes), der Management-Schlüssel in `backend/.env` (Projekt). Das Werkzeug
liest beide nur zur Laufzeit und gibt sie nie aus.