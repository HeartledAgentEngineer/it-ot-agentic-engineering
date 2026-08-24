# Kosten- & Termux-Strategie (Personal AI Agent)

## Kosten-Strategie (bewusste Entscheidung, 2026-08)

Ziel: **günstig bleiben** — unter 100 €/Monat bei fast durchgehender Nutzung,
ohne auf teure Top-Modelle (Claude Opus, GPT-Top) als Standard umzusteigen.

**Grundsatz: DeepSeek V4 Flash (oder vergleichbar günstig) als Massen-Modell.**
- Der Agent arbeitet mit einem kleinen, günstigen Modell (z. B. `deepseek-v4-flash`),
  das durch **engere Steuerung durch den Nutzer** (klarere Schritte, gezielte
  Knotenpunkte) kompensiert wird.
- 3× günstige Durchläufe kosten weniger als 1× teures Modell (gemessene
  Live-Preise: Flash ≈ 1/50 bis 1/130 des Preises von Top-Modellen pro Token).
- **Kein Max-/Pro-Abo** für Massen-Workflow nötig (nur lohnt, wenn Opus-Qualität
  als Standard massiv genutzt würde).

**Empfehlung: hybrid** — günstiges Modell als Massen-Worker, ein stärkeres Modell
nur bei seltenen schwierigen Knotenpunkten (Architektur, kniffliger Fehler), wo
Qualität echte Zeit spart. Das ist kein Abo, sondern gezielt zugekauft.

## Termux-Begrenzungen (wichtig fürs Handy)

Der Agent läuft produktiv auf einem Android-Handy via Termux. Dort gelten
Paket-/Ressourcen-Grenzen:

- **torch / sentence-transformers** sind auf Termux oft **nicht installierbar**
  (schwere .so-Bibliotheken). Folge: `memory_service` setzt `_embeddings_available
  = False` — die **lokale Embedding-Erzeugung fällt aus**. Das Backend fällt
  dann auf andere Mittel zurück (z. B. Mistral-Embeddings-API, wenn konfiguriert,
  oder Suche ohne Vektoren).
- **pdfminer** kann nach `pip install` brechen (serben `.so`-Abhängigkeiten);
  auf Termux gelegentlich nur mit `pip install --no-binary`-Umweg stabil.
- **tmux** muss installiert sein (`pkg install tmux`), damit der lokale
  Hermes-CLI (Track C) interaktiv läuft.
- Ressourcen (RAM) sind begrenzt → lange Streams/Agenten-Schleifen können
  abbrechen/Timeout (daher gestaffelte Timeouts in `hermes_local`).

**Leitlinie:** Code, der auf dem Handy laufen soll, sollte **nicht** zwingend
torch-/py-/.so-schwere Abhängigkeiten voraussetzen — wo möglich über die
OpenRouter-API statt lokaler ML-Loads.
