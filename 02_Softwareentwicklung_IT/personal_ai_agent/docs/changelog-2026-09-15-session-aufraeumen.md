# Änderung 15.09.2026 — tmux-Sessions räumen sich selbst auf

## Problem (Sebastian, seit längerem)

Beim Arbeiten am Handy sammelten sich **mehrere tmux-Sessions**. Eine stand als
**rotes, durchgestrichenes „agent"** in der Termux-Liste — er musste in die
Session hinein und **Enter** drücken, damit sie wirklich schließt. Jedes Mal
manuell: unerwünscht.

## Ursache

Eigene Job-Sessions heißen `hermes_agent_<millis>_<nr>`
(`hermes_local.py`, `LocalHermesJob.__init__`). Normalerweise werden sie am Ende
eines Auftrags beendet (`beende()` im `finally` → `tmux kill-session`).

**Stirbt aber der Server vorher** — Widget-Neustart, Absturz, Akku, harter
Abbruch — läuft dieses `finally` nie. Die Session bleibt als **tote Session**
liegen. Termux zeigt sie weiter an (rot/durchgestrichen), und niemand räumt sie
weg: es gab **keinen Start-Aufräumer**.

## Fix

**1. Aufräumen beim Server-Start** (`backend/app/main.py`, `lifespan`):
```python
aufgeraeumt = raeume_alte_job_sessions_auf()
```

**2. Aufräumen beim Widget-Start** (`start-termux.sh`, vor dem `exec uvicorn`):
```bash
ALTE_SESSIONS="$(tmux list-sessions -F '#{session_name}' | grep '^hermes_agent_' || true)"
for s in $ALTE_SESSIONS; do tmux kill-session -t "$s"; done
```
So wird auch dann aufgeräumt, wenn der Server gar nicht erst hochkommt.

**3. Neue Funktion** (`backend/app/services/hermes_local.py`):
- `raeume_alte_job_sessions_auf() -> int` — beendet nur Sessions mit dem
  Job-Muster.
- `_soll_beendet_werden(name, geschuetzt)` — die Entscheidungsregel, testbar.

**Was NIE angefasst wird** (wichtig, sonst zerstört man Arbeit):
`hermes_termux`, `hermes_code`, die konfigurierte `HERMES_LOCAL_SESSION` und
grundsätzlich alles, was nicht `hermes_agent_…` heißt — fremde Sessions gehören
dem Nutzer.

## Zweiter Fund im selben Bereich

Die **Selbstheilung des Inbox-Daemons** beim Server-Start lief nur unter
`if settings.hermes_local_kanal == "aktiv"`. Der Standardwert ist **leer**, also
griff sie **nie** — ein toter Daemon blieb tot (genau die Ursache von
„Hermes reagiert nicht"). Jetzt greift sie bei leerem **oder** `aktiv`-Kanal,
sobald `hermes`/`tmux` nutzbar sind.

## Verifikation

```bash
bash -n start-termux.sh                        # Exit 0
cd backend && .venv/Scripts/python -m pytest tests/ -q    # 216 passed, Exit 0
```

Neue Tests `backend/tests/test_tmux_aufraeumen.py` (4): nur das Job-Muster gilt
als aufräumbar · geschützte Session bleibt · der Lauf killt genau die
Job-Sessions · ohne tmux passiert nichts (harmlos).

## Offen / Live zu prüfen

- Am Handy nach dem Widget-Start: `tmux ls` — es sollten **keine**
  `hermes_agent_*`-Leichen und keine roten Einträge mehr stehen.
- **Flake im Gate:** `tests/test_gesichter_service.py::test_kontext_block_enthaelt_namen`
  fiel in einem von zwei vollen Läufen um (isoliert und in Zweier-Kombination
  grün). Das ist dieselbe Klasse wie der frühere Isolationsfehler (geteilter
  Modulzustand) und sollte gehärtet werden — sonst blockiert der neue
  pre-commit-Hook Commits zufällig.
