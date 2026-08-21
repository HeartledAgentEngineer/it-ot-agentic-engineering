# PC-Hermes-Routing (Track A) — Handy-Backend → PC-Hermes

**Zweck:** Erkennt das Backend einen Coding-/Programmierauftrag, wird dieser
**zuerst direkt an den PC-Hermes** (`hermes_gateway.py`) geschickt, wenn der PC
im selben WLAN erreichbar ist. Nur wenn er das nicht ist, geht der Auftrag wie
bisher ins **Auftragsbuch** (Track B, unverändert).

## Wann greift das Routing
- Ausgelöst durch die bestehende Auftragserkennung (`ist_auftrag`) im Chat.
- Der PC-Hermes lernt den Auftrag über den lokalen Hermes-API-Server
  (`/v1/chat/completions`, OpenAI-Format, Modell `hermes-agent`).
- **Kein PC-Hermes erreichbar** → `sende_auftrag()` liefert `None` → der
  Auftrag fällt aufs Buch zurück (kein Abbruch, der Chat bleibt bedienbar).

## Konfiguration (in `backend/.env`, nicht im Code)
```
HERMES_PC_BASE_URL=http://<PC-LAN-IP>:8642
HERMES_PC_API_KEY=<der API-Server-Key>
HERMES_PC_TIMEOUT=30
```
Hinweis: `BASE_URL` ist die **LAN-IP des PCs** (nicht `localhost`, denn das
Backend läuft auf dem Handy). Die IP findest du z. B. per `ipconfig` (PC).

## Dateien
- `backend/app/services/hermes_gateway.py` — der Client (neu).
- `backend/app/config.py` — neue Settings-Felder.
- `backend/app/router/chat.py` — Weiche: erst PC-Hermes, sonst Buch.

## Sicherheitshinweis
Der PC-Hermes-API-Server lauscht für den LAN-Zugriff auf `0.0.0.0`. Dadurch
kann er ungültige Anfragen von anderen Netzgeräten empfangen (harmloser
Log-Spam), und wer den API-Key kennt, hätte PC-Zugriff. Fürs Heim-WLAN ist das
vertretbar; langfristig sollte der Port per Firewall auf das vertraute Subnetz
beschränkt (oder der Key streng geheim) werden.

## Bereinigt (20.08.2026)
- `schaetze_dauer` (Zeitschätzung "ca. 5-15 Minuten") entfernt — sie war
  irreführend und wird nirgends angezeigt.
