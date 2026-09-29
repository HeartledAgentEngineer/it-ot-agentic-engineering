#!/data/data/com.termux/files/usr/bin/sh
#
# agent-ensure.sh — startet das Backend NUR, wenn es nicht antwortet.
#
# Gegenstueck zu start-termux.sh, aber bewusst schlanker: kein git-Abgleich,
# kein Beenden laufender Prozesse, keine Datei-Uebernahmen. Die Android-App
# "Hey Agent" ruft dieses Skript per Termux-RUN_COMMAND-Intent auf, sobald
# ihr Health-Check fehlschlaegt. Laeuft der Server schon, passiert nichts
# (idempotent). "Update + Neustart" bleibt Sache von start-termux.sh.
#
# Einrichtung einmalig (in Termux):
#   1. Externe Apps erlauben:
#        mkdir -p ~/.termux
#        echo "allow-external-apps=true" >> ~/.termux/termux.properties
#        termux-reload-settings
#      (Zeile nur einmal eintragen; Termux schliessen/oeffnen, falls der
#       Intent danach noch ignoriert wird.)
#   2. Skript ins Home kopieren und ausfuehrbar machen:
#        cp <Repo>/02_Softwareentwicklung_IT/personal_ai_agent/termux/agent-ensure.sh ~/agent-ensure.sh
#        chmod +x ~/agent-ensure.sh
#      (Kopie noetig, weil die App den festen Pfad ~/agent-ensure.sh ruft.
#       Nach Aenderungen am Skript im Repo erneut kopieren.)
#   3. Projektordner: wird aus dem Symlink ~/.shortcuts/agent (zeigt auf
#      start-termux.sh) abgeleitet — dieselbe Einrichtung wie fuer start-termux.sh.
#      Alternativ PROJEKT=/pfad/zum/personal_ai_agent setzen.
#
# Log: ~/agent-ensure.log (wird bei jedem Lauf angehaengt, bei > 200 KB gekuerzt)

PORT="${PORT:-8080}"
LOG="$HOME/agent-ensure.log"

# Log begrenzen (nur die letzten 500 Zeilen behalten).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 204800 ]; then
    tail -n 500 "$LOG" > "$LOG.neu" 2>/dev/null && mv -f "$LOG.neu" "$LOG"
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
}

# Antwortet /health? (curl bevorzugt, sonst Python als Rueckfall.)
health_ok() {
    if command -v curl >/dev/null 2>&1; then
        curl -sf --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1
    else
        python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/health', timeout=2)" >/dev/null 2>&1
    fi
}

if health_ok; then
    log "Backend laeuft bereits (Port $PORT) - nichts zu tun."
    exit 0
fi

# Projektordner bestimmen: gleiche Logik wie start-termux.sh (Symlink aufloesen).
if [ -z "${PROJEKT:-}" ]; then
    verweis="$HOME/.shortcuts/agent"
    if [ -L "$verweis" ]; then
        ziel="$(readlink "$verweis")"
        PROJEKT="$(cd "$(dirname "$ziel")" 2>/dev/null && pwd)"
    fi
fi
if [ -z "${PROJEKT:-}" ] || [ ! -d "$PROJEKT/backend" ]; then
    log "FEHLER: Projektordner nicht gefunden (PROJEKT='${PROJEKT:-}'). ~/.shortcuts/agent einrichten oder PROJEKT setzen."
    exit 1
fi

# CPU nicht einschlafen lassen (wie start-termux.sh).
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

cd "$PROJEKT/backend" || { log "FEHLER: backend/ fehlt in $PROJEKT"; exit 1; }

log "Backend antwortet nicht - starte uvicorn (Projekt: $PROJEKT)"
# Bindung aus der .env lesen (gleiches Muster wie neu-start-nach-lauf.sh).
# Standard bleibt 0.0.0.0: ohne HOST_BIND in der .env ändert sich nichts.
# Mit HOST_BIND=127.0.0.1 lauscht der Server nur lokal (empfohlen fürs
# Hotel-WLAN / fremde Netze) — die Entscheidung trifft die .env, nicht der Code.
HOST_BIND="0.0.0.0"
_env_host=$(grep -E "^HOST_BIND=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_host" ] && HOST_BIND="$_env_host"
# Gleicher Startbefehl wie start-termux.sh, aber vom Terminal geloest (nohup),
# weil dieses Skript im Hintergrund per Intent laeuft und danach endet.
nohup python -m uvicorn app.main:app --host "$HOST_BIND" --port "$PORT" --reload >> "$LOG" 2>&1 &
log "uvicorn gestartet (PID $!)"
exit 0
