# OpenRouter-Schlüssel im Workspace

Stand: 27.09.2026

## Wer benutzt welchen Schlüssel

| Schlüssel | Verbrauch (27.09.) | Wer benutzt ihn |
|---|---|---|
| **Hermes Agent** | 151,90 USD | Der Hermes-Desktop selbst **und** seit dem 27.09.2026 auch alle Workspace-Werkzeuge: Critic-Skill (`pruefe.mjs`), `grillAnAgent`, Codex- und Claude-Code-Läufe |
| **personal_ai_agent** | 13,78 USD | Der Termux-Agent auf dem Handy (eigene `.env` auf dem Gerät) |
| **typeFREE** | 0,31 USD | **Bewusst separat** — die Sprachtranskription läuft über einen eigenen Schlüssel, damit sich ihre Kosten klar von den Agent-Kosten trennen lassen |
| **critic-Skill** | 0,36 USD | Restbestand früherer Konfiguration, nicht mehr in Gebrauch |

## Wo die Werte liegen

- `%LOCALAPPDATA%\hermes\.env` → **Quelle** (der Hermes-Agent-Schlüssel, Zeile 12)
- `workspace agentic engineering\.env` → Workspace-Werkzeuge (auf Hermes-Agent umgestellt)
- `02_Softwareentwicklung_IT\typeFREE\.env` → typeFREE (**unverändert**, eigener Schlüssel)

`OPENROUTER_MANAGEMENT_KEY` steht zusätzlich in `hermes\.env`. Dieser Schlüssel kann
**nur lesen** (Keys, Verbrauch, Limits) und **keine** Modellanfragen auslösen.

## Regeln

- **`.env` und `.env.bak*` sind per `.gitignore` gesperrt.** Sicherungen der `.env`
  enthalten dieselben Schlüssel und dürfen nie ins Repository.
- Beim Umstellen wird **immer** eine Sicherung `.env.bak-JJJJMMTT-HHMM` angelegt
  (rückholbar per Kopie zurück).
- Werte werden **nie** im Chat ausgegeben, nur die letzten drei Zeichen zur Kontrolle.
- Werkzeug: `hermes/scripts/key_umstellen.py` (liest die Quelle, sichert, ersetzt nur
  die Zeile `OPENROUTER_API_KEY`, lässt alle anderen Werte unangetastet).

## Warum nicht alle Schlüssel zusammenlegen

Der `typeFREE`-Schlüssel bleibt absichtlich getrennt: Die Sprachtranskription hat ein
eigenes Kostenprofil (Abrechnung pro Audio-Stunde), und eine Vermischung würde die
Trennung von Agent- und Diktat-Kosten zerstören. Der Handy-Agent hat aus demselben
Grund seine eigene `.env` auf dem Gerät.
