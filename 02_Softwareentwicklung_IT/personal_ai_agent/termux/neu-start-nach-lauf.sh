#!/data/data/com.termux/files/usr/bin/bash
#
# Server + Inbox-Daemon NACH einem laufenden Hermes-Lauf neu starten.
#
# WARUM es dieses Skript gibt:
# Backend (uvicorn ohne --reload) und Inbox-Daemon dienen den Code aus, der
# beim Start geladen wurde. Nach einer Code-Aenderung muessen beide neu
# starten — aber NICHT mitten in einem Hermes-Auftrag: dann waere die gerade
# entstehende Antwort verloren. Dieses Skript wartet deshalb, bis kein
# `hermes chat -q`-Lauf mehr aktiv ist, und tauscht danach beide Prozesse aus.
#
# Der Inbox-Daemon wird NICHT hier gestartet: der Server startet ihn beim
# Startup selbst (app/main.py -> sicherstelle_inbox_daemon) — mit dem
# aktuellen Code und dem Modell aus den Settings (DeepSeek V4.1 Flash).
#
# Aufruf (im Hintergrund, damit der wartende Teil niemanden blockiert):
#   bash termux/neu-start-nach-lauf.sh
#
# Log: termux/neu-start-nach-lauf.log

skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"
PROJEKT="$(cd "$HIER/.." && pwd)"
BACKEND="$PROJEKT/backend"
LOG="$HIER/neu-start-nach-lauf.log"

log() { echo "$(date '+%H:%M:%S') | $*" | tee -a "$LOG"; }

log "warte auf das Ende des laufenden Hermes-Laufs…"
# Warten, bis zweimal in Folge kein laufender -q-Lauf mehr da ist (kurze
# Uebergangs-Luecke zwischen zwei Auftraegen nicht als 'fertig' werten).
ruhig=0
for _ in $(seq 1 360); do
    if pgrep -f "hermes chat -q" >/dev/null 2>&1; then
        ruhig=0
    else
        ruhig=$((ruhig + 1))
        [ "$ruhig" -ge 2 ] && break
    fi
    sleep 5
done

if pgrep -f "hermes chat -q" >/dev/null 2>&1; then
    log "⚠️  Es laeuft immer noch ein Hermes-Lauf — kein Neustart (nichts gekillt)."
    exit 1
fi

log "kein laufender Hermes-Lauf mehr — tausche Daemon + Server."

# 1) Inbox-Daemon beenden (der Server startet ihn gleich frisch).
pkill -9 -f "hermes_inbox_daemon.py" 2>/dev/null

# 2) Alten Server hart stoppen.
pkill -9 -f "uvicorn app.main:app" 2>/dev/null
pkill -9 -f "python -m uvicorn" 2>/dev/null
for _ in $(seq 1 20); do
    pgrep -f "uvicorn" >/dev/null 2>&1 || break
    sleep 0.5
done
sleep 1

# 3) Frischen Server starten (laedt neuen Code + startet den Daemon mit).
cd "$BACKEND" || { log "❌ backend/ nicht gefunden"; exit 1; }

PORT="8080"
_env_port=$(grep -E "^PORT=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_port" ] && PORT="$_env_port"
HOST_BIND="0.0.0.0"
_env_host=$(grep -E "^HOST_BIND=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_host" ] && HOST_BIND="$_env_host"

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

setsid python -m uvicorn app.main:app --host "$HOST_BIND" --port "$PORT" \
    >> "$LOG" 2>&1 < /dev/null &

# 4) Warten, bis der Server wirklich antwortet.
bereit=0
for _ in $(seq 1 120); do
    sleep 1
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/health" 2>/dev/null)
    if [ "$code" = "200" ]; then bereit=1; break; fi
done

if [ "$bereit" = "1" ]; then
    log "✅ Neustart fertig — Server antwortet (Port $PORT)."
else
    log "❌ Server kam nicht hoch (siehe $LOG)."
    exit 1
fi

# 5) Beleg: laeuft genau EIN Daemon?
log "Daemon-Prozesse: $(pgrep -f hermes_inbox_daemon.py | tr '\n' ' ')"