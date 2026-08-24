# Übergabe / Changelog — autonomer Lauf 2026-08-24 (nachmittags)

## Was in diesem Lauf gebaut + gepusht wurde

| Commit | Inhalt |
|---|---|
| `477254a` | **Hermes-Delegation bei Fähigkeits-Grenze** (Task 3 Fähigkeiten-Plan): Weiche delegiert bei Terminal/Datei/System/Tool-Install an Hermes, auch ohne ist_auftrag-Coding-Erkennung |
| `5e3f4d2` | **Critic-Härtung**: Wortgrenzen (Regex) in der Grenz-Erkennung — keine False Positives ("digital"→git, "darunter"→run); ASCII-Funktionsname `stoesst_an_grenze` (PEP8) |
| `e0d0a1a` | **Smart-Output (UI)**: Hermes-Auswahl-Dialoge (rohe `\|`-Menüs) → klickbare Option-Buttons statt Rohtext |
| `be37c60` | **Doku**: Fähigkeiten/Hermes-Delegation/Smart-Output + Kosten- & Termux-Strategie |
| `bbe48b4` | **Endpoint-Test**: /api/chat-Weiche end-to-end abgesichert (Coding→Buch, normal→LLM, Hermes nicht gerufen) |

**Teststand:** 32 Tests grün (pytest), Prüfbefehl: `cd 02_Softwareentwicklung_IT/personal_ai_agent/backend && .venv/Scripts/python -m pytest -q`.

## Retrospektive / Stand

- **Fähigkeiten-Feature (Task 1-3):** fertig — der Agent kennt seine Grenzen
  (System-Prompt) und delegiert gezielt an Hermes als Toolcall.
- **Smart-Output:** Hermes-Menüs werden klickbar (kein roher `|`-String mehr).
- **Handy:** Server läuft (health ok, 62 Erinnerungen), Zustand stabil/ruhig.
  Die neuen Änderungen sind auf GitHub — **müssen auf dem Handy gepullt + Server
  neu gestartet werden** (Widget `agent`), um aktiv zu werden.

## Offene Punkte (To-do, kein Verlust)

- **`/chat/stream`-Weiche:** nutzt noch die manuelle Track-Logik (bewusst — sie
  braucht die SSE-Live-Strecke; `route_auftrag` liefert sie nicht). Nächster
  Refactor-Schritt, wenn live testbar. Nicht überstürzt umgebaut.
- **Ein-Chat-Architektur** (ein fortlaufendes Fenster), **pCloud** (braucht Token),
  **Modell-Kategorien**, **Archiv-Anbindung** (memory.db → archiv_service,
  Sebastian will später), **TTS/STT deutsch** (Hermes-Konfig).
- **Uncommittet im Worktree:** `docs/auftrag-modell-score-bester-mix-2026-08-24.md`
  — von Sebastian, nicht angefasst.

## Hinweis zu Termux

torch/sentence-transformers sind auf dem Handy oft nicht installierbar →
lokale Embeddings fallen aus (`_embeddings_available=False`); App fällt auf
API-Embeddings/ohne Vektorsuche zurück. Siehe `docs/kosten-termux-strategie.md`.
