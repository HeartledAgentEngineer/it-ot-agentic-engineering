#!/data/data/com.termux/files/usr/bin/bash
#
# backend-beenden.sh - die EINZIGE Stelle, die das Backend beendet (HTTPS-Plan H3b).
#
# WARUM es diese Datei gibt:
# Drei Skripte (agent-start, start-termux.sh, neu-start-nach-lauf.sh) hatten je
# eigene pkill-Muster auf "uvicorn". Seit H3a kann der Server auch als
# ``python serve.py`` laufen - ein Muster, das nur uvicorn kennt, liesse ihn
# stehen, und ein alter HTTP-Server bliebe im WLAN offen. Jetzt steht die Liste
# der Prozessarten einmal hier, zusammen mit der Pruefung, dass danach wirklich
# nichts mehr laeuft und die Ports frei sind.
#
# Beendet werden drei Prozessarten:
#   * ``uvicorn app.main:app``   (alter Aufruf, auch mit --reload-Kindprozessen)
#   * ``python -m uvicorn``
#   * ``python serve.py``        (zwei Zugaenge, H3a)
# Erst SIGTERM (uvicorn faehrt sauber herunter, die Termux-Sitzung bleibt nicht
# als "Code 137" stehen), nach der Wartezeit SIGKILL.
# Der Inbox-Daemon (hermes_inbox_daemon.py) wird hier NICHT beendet - das
# erledigen weiter die Aufrufer, die es brauchen.
#
# Aufruf:
#   backend-beenden.sh              beenden + pruefen
#   backend-beenden.sh --laeuft-noch   beendet NICHTS: Exit 0, wenn noch eine der
#                                   drei Prozessarten laeuft, sonst 1
#                                   (die Prozessliste steht so nur hier)
#
# Exit 0 = kein solcher Prozess mehr UND die Ports $PORT und 8443 sind frei
# (``ss -tln``). Sonst 1 (Prozess lebt noch) bzw. 2 (Port noch belegt).
# PORT: aus backend/.env (wie backend-starten.sh), sonst $PORT, sonst 8080.
#
# Wartezeiten (Sekunden) sind ueber BEENDEN_WARTEN_S (nach TERM, Standard 10)
# und BEENDEN_KILL_WARTEN_S (nach KILL, Standard 5) einstellbar - fuer Tests.

set -u

skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"
BACKEND="$(cd "$HIER/../backend" 2>/dev/null && pwd)"

# Die drei Muster fuer pkill -f (je ein Aufruf, damit jede Art einzeln erwischt wird)
# und ein gemeinsames Muster fuer pgrep -f.
MUSTER_1="uvicorn app.main:app"
MUSTER_2="python -m uvicorn"
MUSTER_3="python.* serve\.py"
MUSTER_ALLE="uvicorn app\.main:app|python -m uvicorn|python.* serve\.py"

laeuft_noch() {
    pgrep -f "$MUSTER_ALLE" >/dev/null 2>&1
}

if [ "${1:-}" = "--laeuft-noch" ]; then
    laeuft_noch
    exit $?
fi

PORT="${PORT:-8080}"
if [ -n "$BACKEND" ] && [ -f "$BACKEND/.env" ]; then
    _env_port=$(grep -E "^PORT=" "$BACKEND/.env" 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
    [ -n "$_env_port" ] && PORT="$_env_port"
fi
case "$PORT" in ''|*[!0-9]*) PORT=8080 ;; esac
PORT_HTTPS=8443

WARTEN_S="${BEENDEN_WARTEN_S:-10}"
KILL_WARTEN_S="${BEENDEN_KILL_WARTEN_S:-5}"

signal_senden() {
    # $1 = TERM oder KILL
    pkill -"$1" -f "$MUSTER_1" 2>/dev/null
    pkill -"$1" -f "$MUSTER_2" 2>/dev/null
    pkill -"$1" -f "$MUSTER_3" 2>/dev/null
}

warten_bis_weg() {
    # $1 = Sekunden; kehrt frueher zurueck, sobald nichts mehr laeuft
    _i=0
    while [ "$_i" -lt "$1" ]; do
        laeuft_noch || return 0
        _i=$((_i + 1))
        sleep 1
    done
    laeuft_noch || return 0
    return 1
}

# Belegt irgendetwas die Ports? (Lauschende Sockets, egal welche Adresse.)
ports_belegt() {
    command -v ss >/dev/null 2>&1 || return 1       # nicht pruefbar -> siehe unten
    ss -tln 2>/dev/null | awk -v a=":$PORT" -v b=":$PORT_HTTPS" \
        '$4 ~ (a "$") || $4 ~ (b "$") { gefunden = 1 } END { exit gefunden ? 0 : 1 }'
}

if laeuft_noch; then
    echo "Backend wird beendet (TERM) ..."
    signal_senden TERM
    if ! warten_bis_weg "$WARTEN_S"; then
        echo "  sanftes Beenden reichte nicht - letzter Versuch (KILL)"
        signal_senden KILL
        warten_bis_weg "$KILL_WARTEN_S" || true
    fi
else
    echo "Kein Backend-Prozess gefunden."
fi

if laeuft_noch; then
    echo "FEHLER: Backend-Prozess laeuft noch."
    exit 1
fi

# Der Port wird erst nach dem Prozessende frei; kurz nachwarten.
if command -v ss >/dev/null 2>&1; then
    _i=0
    while ports_belegt && [ "$_i" -lt "$KILL_WARTEN_S" ]; do
        _i=$((_i + 1))
        sleep 1
    done
    if ports_belegt; then
        echo "FEHLER: Port $PORT oder $PORT_HTTPS ist noch belegt."
        exit 2
    fi
else
    echo "Hinweis: ss fehlt - Ports $PORT und $PORT_HTTPS lassen sich nicht pruefen."
fi
echo "Backend beendet, Ports $PORT und $PORT_HTTPS frei."
exit 0
