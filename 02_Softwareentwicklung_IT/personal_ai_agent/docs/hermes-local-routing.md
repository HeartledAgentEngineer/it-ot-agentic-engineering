# Handy-Hermes-Routing (Track C) — Programmierauftrag direkt auf dem Geraet

**Zweck:** Wird ein Coding-Auftrag erkannt und der PC-Hermes (Track A) ist
nicht erreichbar (unterwegs, ohne WLAN zum PC), versucht das Backend, den
Auftrag **direkt auf dem Geraet** zu bearbeiten — über den **lokalen
Hermes-CLI (Termux)**. Erst wenn auch der nicht verfuegbar/erfolglos ist,
faellt der Auftrag ins Buch (Track B).

## Wann greift Track C
- Coding-Auftrag erkannt (`ist_auftrag`).
- PC-Hermes (`hermes_gateway`) liefert `None` (nicht erreichbar/konfiguriert).
- Lokaler Hermes-CLI auf dem Geraet (`hermes_local`) uebernimmt den Auftrag.

## Voraussetzung
Der **Hermes-CLI muss auf dem Handy (Termux) installiert** und im `PATH` sein
(`hermes`-Befehl). Sonst liefert `hermes_local.sende_auftrag()` `None` und es
faellt aufs Buch zurueck.

## Reihenfolge (voller Durchlauf)
1. **Track A** — PC-Hermes (im WLAN erreichbar) → Antwort direkt.
2. **Track C** — lokaler Hermes-CLI auf dem Handy (unterwegs ohne PC).
3. **Track B** — Auftragsbuch (wenn beides nicht geht).

## Dateien
- `backend/app/services/hermes_local.py` — der lokale Hermes-CLI-Aufruf (neu).
- `backend/app/router/chat.py` — Weiche ergaenzt um Track C (beide Endpoints).
