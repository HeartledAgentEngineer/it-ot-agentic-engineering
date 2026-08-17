#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# termux-hermes-watcher.sh
# 
# Pollt das Auftragsbuch auf localhost:8080 und benachrichtigt bei neuen
# Programmieraufträgen. Öffnet die Hermes-App via Android Intent.
#
# Nutzung:
#   ./termux-hermes-watcher.sh           # Start (Hintergrund)
#   ./termux-hermes-watcher.sh stop      # Stoppen
#   ./termux-hermes-watcher.sh status    # Status prüfen
#   ./termux-hermes-watcher.sh foreground # Einmalig + Ausgabe
#
# Abhängigkeiten: termux-api (termux-notification)
#   pkg install termux-api
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$SCRIPT_DIR/.hermes-watcher.pid"
INTERVAL=30  # Sekunden zwischen Polls

# Hermes-App Package (Android)
HERMES_PKG="com.hermesagent.android"

# Farben für Konsolenausgabe
GRUEN='\033[0;32m'
GELB='\033[1;33m'
ROT='\033[0;31m'
BLAU='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLAU}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { log "${GRUEN}✅ $1${NC}"; }
warn() { log "${GELB}⚠️  $1${NC}"; }
err()  { log "${ROT}❌ $1${NC}"; }

# ---------------------------------------------------------------------------
# Auftragsbuch abfragen
# ---------------------------------------------------------------------------
check_jobs() {
    local response
    response=$(curl -s --max-time 5 http://127.0.0.1:8080/api/auftraege?limit=3 2>/dev/null)

    if [ -z "$response" ]; then
        return 1  # Server nicht erreichbar
    fi

    # Prüfen, ob ein offener Auftrag existiert
    local offene
    offene=$(echo "$response" | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
    auftraege = data.get('auftraege', [])
    offen = [a for a in auftraege if a.get('status') == 'offen']
    if offen:
        a = offen[0]
        print(f\"{a['id'][:8]}|{a.get('kategorie','?')}|{a['auftrag'][:120]}\")
    else:
        print('')
except:
    print('')
" 2>/dev/null)

    if [ -n "$offene" ]; then
        echo "$offene"
        return 0
    fi
    return 2  # Keine offenen Aufträge
}

# ---------------------------------------------------------------------------
# Benachrichtigung senden
# ---------------------------------------------------------------------------
notify() {
    local job_id="$1"
    local kategorie="$2"
    local beschreibung="$3"

    if command -v termux-notification &>/dev/null; then
        termux-notification \
            --id "hermes-job" \
            --title "📋 Hermes: Neuer Auftrag ($kategorie)" \
            --content "$beschreibung" \
            --button1 "Öffnen" \
            --button1-action "am start -n $HERMES_PKG/.MainActivity" \
            --priority high \
            --alert-once \
            --ongoing
        ok "Benachrichtigung gesendet: $job_id"
    else
        warn "termux-notification nicht gefunden — installiere: pkg install termux-api"
        # Fallback: App trotzdem öffnen
        am start -n $HERMES_PKG/.MainActivity
    fi
}

# ---------------------------------------------------------------------------
# Einmaliger Check (für manuelle Ausführung)
# ---------------------------------------------------------------------------
run_once() {
    log "Prüfe Auftragsbuch..."
    local result
    result=$(check_jobs)
    local rc=$?

    case $rc in
        0)
            local job_id kategorie beschreibung
            job_id=$(echo "$result" | cut -d'|' -f1)
            kategorie=$(echo "$result" | cut -d'|' -f2)
            beschreibung=$(echo "$result" | cut -d'|' -f3)
            warn "Offener Auftrag gefunden: $job_id ($kategorie)"
            echo "  → $beschreibung"
            notify "$job_id" "$kategorie" "$beschreibung"
            return 0
            ;;
        1)
            err "Server nicht erreichbar (127.0.0.1:8080)"
            return 1
            ;;
        2)
            ok "Keine offenen Aufträge"
            return 0
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Watcher-Daemon (Hintergrund)
# ---------------------------------------------------------------------------
run_watcher() {
    log "Hermes-Watcher gestartet (Poll alle ${INTERVAL}s)"
    log "Drücke Ctrl+C zum Stoppen"
    echo ""
    
    local already_notified=""
    local server_was_down=0

    while true; do
        local result
        result=$(check_jobs)
        local rc=$?

        case $rc in
            0)
                local job_id
                job_id=$(echo "$result" | cut -d'|' -f1)
                server_was_down=0
                
                if [ "$already_notified" != "$job_id" ]; then
                    warn "Neuer Auftrag: $job_id"
                    notify "$job_id" "$(echo "$result" | cut -d'|' -f2)" "$(echo "$result" | cut -d'|' -f3)"
                    already_notified="$job_id"
                fi
                ;;
            1)
                if [ $server_was_down -eq 0 ]; then
                    err "Server nicht erreichbar — warte..."
                    server_was_down=1
                    already_notified=""
                fi
                ;;
            2)
                server_was_down=0
                already_notified=""
                ;;
        esac

        sleep "$INTERVAL"
    done
}

# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------
case "${1:-}" in
    stop)
        if [ -f "$PIDFILE" ]; then
            kill "$(cat "$PIDFILE")" 2>/dev/null
            rm -f "$PIDFILE"
            ok "Watcher gestoppt"
        else
            warn "Kein laufender Watcher (PID-Datei nicht gefunden)"
        fi
        ;;
    
    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            ok "Watcher läuft (PID $(cat "$PIDFILE"))"
        else
            warn "Watcher läuft nicht"
            [ -f "$PIDFILE" ] && rm -f "$PIDFILE"
        fi
        ;;

    foreground)
        run_once
        ;;

    *)
        # Default: Start im Hintergrund
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            warn "Watcher läuft bereits (PID $(cat "$PIDFILE"))"
            exit 0
        fi
        
        # PID-Datei im Skript-Verzeichnis — kein nohup nötig, Hermes tracked
        run_watcher &
        echo $! > "$PIDFILE"
        ok "Watcher gestartet (PID $(cat "$PIDFILE"))"
        log "  ./termux-hermes-watcher.sh status  — Status prüfen"
        log "  ./termux-hermes-watcher.sh stop    — Stoppen"
        log "  ./termux-hermes-watcher.sh foreground — Einmal-Check"
        ;;
esac
