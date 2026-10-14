#!/data/data/com.termux/files/usr/bin/bash
#
# backend-starten.sh - die EINZIGE Stelle, die das Backend startet (HTTPS-Plan H3b).
#
# WARUM es diese Datei gibt:
# Bis 14.10.2026 starteten vier Skripte (agent-start, start-termux.sh,
# agent-ensure.sh, neu-start-nach-lauf.sh) den Server jeweils selbst mit eigenem
# uvicorn-Aufruf. Seit H3a gibt es zwei Betriebsarten (mit/ohne Zertifikat);
# stuende die Wahl viermal, liefe sie irgendwann auseinander. Jetzt gilt sie hier.
#
#   * Alle drei Dateien da und nicht leer (server.crt, server.key, ca.crt in
#     $AGENT_TLS_ORDNER, Standard ~/.agent_tls)  ->  python serve.py
#       HTTPS 0.0.0.0:8443 (Heimnetz) + HTTP NUR 127.0.0.1:$PORT (Geraet selbst).
#   * Sonst  ->  python -m uvicorn app.main:app --host $HOST_BIND --port $PORT
#       wie bisher; ``--reload`` wirkt nur in diesem Zweig.
#
# Aufruf:
#   backend-starten.sh [--reload] [--log DATEI] [--abloesen]
#   backend-starten.sh --modus-pruefen
#
#   --reload          Quellcode-Neuladen (nur ohne Zertifikat; mit Zertifikat gibt
#                     es kein Reload, das Skript sagt es in einer Zeile).
#   --log DATEI       Ausgabe des Servers an DATEI anhaengen.
#   --abloesen        Server vom Terminal geloest (setsid, sonst nohup; stdin von
#                     /dev/null) im Hintergrund starten und zurueckkehren. Das
#                     Skript gibt die PID aus.
#                     OHNE --abloesen ersetzt sich das Skript selbst durch den
#                     Server (exec): Der Aufrufer haengt ein ``&`` an das Skript
#                     und bekommt in ``$!`` direkt die Server-PID (kill -0, wait
#                     und der Exit-Code des Servers funktionieren wie vorher).
#   --modus-pruefen   startet NICHTS. Exit 0 = laufender Server passt zum
#                     gewuenschten Modus, Exit 3 = Umstellung noetig.
#                     Gewuenscht ist TLS, wenn alle drei Dateien da sind - fehlt
#                     eine, ist HTTP gewuenscht und die Antwort IMMER 0 (kein
#                     Zwang, kein Neustart). Bei gewuenschtem TLS ist 0 nur dann,
#                     wenn (a) curl --cacert <ca.crt> https://127.0.0.1:8443/api/health
#                     gelingt (volle Pruefung gegen die uebergebene eigene CA,
#                     nie -k, nie der Systembestand) UND (b) ss -tln den HTTP-Port
#                     nur auf Loopback zeigt. Alles andere ist 3.
#
# PORT und HOST_BIND werden gezielt aus backend/.env gelesen (nur diese zwei
# Schluessel, nichts anderes aus der Datei wird ausgegeben). Der Wert aus der .env
# gilt vor einem schon gesetzten PORT; fehlt er, gilt $PORT bzw. 8080.
# HOST_BIND ohne Eintrag: 0.0.0.0 (wie bisher). Beide werden exportiert, damit
# serve.py dieselben Werte sieht.

set -u

skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"
BACKEND="$(cd "$HIER/../backend" 2>/dev/null && pwd)"

RELOAD=0
LOG=""
ABLOESEN=0
PRUEFEN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --reload) RELOAD=1 ;;
        --abloesen) ABLOESEN=1 ;;
        --modus-pruefen) PRUEFEN=1 ;;
        --log)
            shift
            if [ $# -eq 0 ]; then echo "backend-starten: --log braucht eine Datei" >&2; exit 2; fi
            LOG="$1" ;;
        *) echo "backend-starten: unbekannter Schalter: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ -z "$BACKEND" ] || [ ! -d "$BACKEND" ]; then
    echo "backend-starten: backend/ nicht gefunden (neben termux/ erwartet)" >&2
    exit 1
fi
cd "$BACKEND" || exit 1

# ── PORT und HOST_BIND ──────────────────────────────────────────────────────
PORT="${PORT:-8080}"
HOST_BIND="0.0.0.0"
_env_port=$(grep -E "^PORT=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_port" ] && PORT="$_env_port"
_env_host=$(grep -E "^HOST_BIND=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_host" ] && HOST_BIND="$_env_host"
case "$PORT" in
    ''|*[!0-9]*)
        echo "backend-starten: PORT '$PORT' ist keine Zahl - nehme 8080"
        PORT=8080 ;;
esac
export PORT HOST_BIND

TLS_ORDNER="${AGENT_TLS_ORDNER:-$HOME/.agent_tls}"
export AGENT_TLS_ORDNER="$TLS_ORDNER"
PORT_HTTPS=8443

# Dieselbe Bedingung wie tls_bereit() in backend/serve.py: alle drei Dateien da
# UND nicht leer. Eine einzige Definition fuer Start und Modusprufung.
tls_bereit() {
    for _name in server.crt server.key ca.crt; do
        [ -s "$TLS_ORDNER/$_name" ] || return 1
    done
    return 0
}

# ── Modusprüfung ────────────────────────────────────────────────────────────
# Zeigt ss den HTTP-Port NUR auf Loopback? Jede andere Lauschadresse (0.0.0.0,
# *, [::], eine WLAN-Adresse) zaehlt als offen. Ohne ss laesst sich das nicht
# belegen - dann gilt es als NICHT lokal (sicherere Richtung: Umstellung).
http_nur_lokal() {
    command -v ss >/dev/null 2>&1 || return 1
    _adressen="$(ss -tln 2>/dev/null | awk -v p=":$PORT" '$4 ~ (p "$") { print $4 }')"
    for _a in $_adressen; do
        case "$_a" in
            "127.0.0.1:$PORT"|"[::1]:$PORT") ;;
            *) return 1 ;;
        esac
    done
    return 0
}

modus_pruefen() {
    if ! tls_bereit; then
        echo "Modus: HTTP gewuenscht (Zertifikatsdateien unvollstaendig) - passt"
        return 0
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "Modus: TLS gewuenscht, aber curl fehlt - Umstellung noetig"
        return 3
    fi
    if ! curl -sf --max-time 3 --cacert "$TLS_ORDNER/ca.crt" \
            "https://127.0.0.1:$PORT_HTTPS/api/health" >/dev/null 2>&1; then
        echo "Modus: TLS gewuenscht, HTTPS antwortet nicht (oder Kette passt nicht zur ca.crt) - Umstellung noetig"
        return 3
    fi
    if ! http_nur_lokal; then
        echo "Modus: TLS gewuenscht, HTTP-Port $PORT lauscht nicht nur auf Loopback - Umstellung noetig"
        return 3
    fi
    echo "Modus: TLS gewuenscht und aktiv - passt"
    return 0
}

if [ "$PRUEFEN" = "1" ]; then
    modus_pruefen
    exit $?
fi

# ── Start ───────────────────────────────────────────────────────────────────
if tls_bereit; then
    echo "Backend-Modus: TLS (python serve.py: HTTP 127.0.0.1:$PORT, HTTPS 0.0.0.0:$PORT_HTTPS)"
    if [ "$RELOAD" = "1" ]; then
        echo "Hinweis: --reload gibt es mit Zertifikat nicht und wird ignoriert."
    fi
    BEFEHL=(python serve.py)
else
    echo "Backend-Modus: HTTP (uvicorn auf $HOST_BIND:$PORT, kein vollstaendiges Zertifikat)"
    BEFEHL=(python -m uvicorn app.main:app --host "$HOST_BIND" --port "$PORT")
    [ "$RELOAD" = "1" ] && BEFEHL+=(--reload)
fi

if [ "$ABLOESEN" = "1" ]; then
    # Vom Terminal geloest: neue Sitzung (setsid) bzw. SIGHUP-fest (nohup), kein
    # stdin. Ohne --log gehen die Meldungen ins Leere statt ans Terminal.
    if command -v setsid >/dev/null 2>&1; then
        _loeser=(setsid)
    else
        _loeser=(nohup)
    fi
    "${_loeser[@]}" "${BEFEHL[@]}" >> "${LOG:-/dev/null}" 2>&1 < /dev/null &
    echo "Backend gestartet (PID $!)"
    exit 0
fi

# Nicht abgeloest: das Skript wird zum Server. Der Aufrufer backgroundet es mit
# ``&`` und haelt in $! die Server-PID.
if [ -n "$LOG" ]; then
    exec "${BEFEHL[@]}" >> "$LOG" 2>&1
fi
exec "${BEFEHL[@]}"
