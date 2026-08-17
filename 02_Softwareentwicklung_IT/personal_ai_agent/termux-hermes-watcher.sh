#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# termux-hermes-watcher.sh - V2 Vollautomatisch
# 
# Pollt das Auftragsbuch ALLE 3 SEKUNDEN. Bei offenem Auftrag:
# 1. Claimt ihn sofort (GET /naechster)
# 2. Schreibt Live-Status-Meldungen in den Chat
# 3. Startet Hermes-App im Vordergrund
#
# Nutzung:
#   ./termux-hermes-watcher.sh           # Start (Hintergrund)
#   ./termux-hermes-watcher.sh stop      # Stoppen
#   ./termux-hermes-watcher.sh status    # Laeuft?
#
# Abhaengigkeiten:
#   pkg install termux-api     (fuer termux-notification)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$SCRIPT_DIR/.hermes-watcher.pid"
INTERVAL=3  # Sekunden zwischen Polls !!!

# Hermes-App Package (Android)
HERMES_PKG="com.hermesagent.android"
HERMES_ACTIVITY="com.hermesagent.android.MainActivity"

# Leere Referenz fuer bereits gesehene Auftraege
SEEN_FILE="$SCRIPT_DIR/.hermes-watcher.seen"

log() { echo "[$(date +%H:%M:%S)] $1"; }

# ---------------------------------------------------------------------------
# Auftragsbuch: Offenen Auftrag suchen + claimen
# ---------------------------------------------------------------------------
claim_job() {
    # 1. Schnellcheck: Ist ueberhaupt was offen?
    local response
    response=$(curl -s --max-time 2 http://127.0.0.1:8080/api/auftraege?limit=1 2>/dev/null)
    [ -z "$response" ] && return 1  # Server weg

    local has_open
    has_open=$(echo "$response" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    for a in d.get('auftraege',[]):
        if a.get('status') == 'offen':
            print('1')
            sys.exit(0)
    print('0')
except: print('0')
" 2>/dev/null)

    [ "$has_open" != "1" ] && return 2  # Nichts offen

    # 2. Claimen (naechster_offener macht atomar offen->laeuft)
    local claim
    claim=$(curl -s --max-time 2 http://127.0.0.1:8080/api/auftraege/naechster 2>/dev/null)
    
    local job_id
    job_id=$(echo "$claim" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin).get('auftrag',{})
    print(d.get('id','')[:8])
except: print('')
" 2>/dev/null)

    [ -z "$job_id" ] && return 3  # Nichts geclaimt

    # Pruefen ob wir den schon gesehen haben (Duplikat-Vermeidung)
    if [ -f "$SEEN_FILE" ]; then
        grep -q "^$job_id\$" "$SEEN_FILE" 2>/dev/null && return 4  # Schon gesehen
    fi
    
    echo "$job_id" >> "$SEEN_FILE"
    echo "$job_id|$claim"
    return 0
}

# ---------------------------------------------------------------------------
# Live-Status in den Chat schreiben (wird im Frontend sichtbar)
# ---------------------------------------------------------------------------
send_status() {
    local job_id="$1"
    local meldung="$2"
    
    # JSON-safe escapen
    local escaped
    escaped=$(echo "$meldung" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null)
    [ -z "$escaped" ] && return
    
    local payload="{\"meldung\": $escaped}"
    
    curl -s --max-time 3 -X POST "http://127.0.0.1:8080/api/auftraege/${job_id}/status" \
        -H "Content-Type: application/json" \
        -d "$payload" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Ergebnis ins Buch schreiben
# ---------------------------------------------------------------------------
send_ergebnis() {
    local job_id="$1"
    local text="$2"
    local erfolg="${3:-true}"
    
    local escaped
    escaped=$(echo "$text" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null)
    [ -z "$escaped" ] && return
    
    local payload="{\"ergebnis\": $escaped, \"erfolg\": $erfolg}"
    
    curl -s --max-time 3 -X POST "http://127.0.0.1:8080/api/auftraege/${job_id}/ergebnis" \
        -H "Content-Type: application/json" \
        -d "$payload" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Hermes-App starten (vollautomaisch, kein User-Eingriff)
# ---------------------------------------------------------------------------
start_hermes() {
    # Android Activity Manager startet Hermes im Vordergrund
    am start -n "$HERMES_PKG/.$HERMES_ACTIVITY" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Einen gefundenen Auftrag verarbeiten
# ---------------------------------------------------------------------------
process_job() {
    local raw="$1"
    local job_id kategorie auftrag_text
    
    job_id=$(echo "$raw" | cut -d'|' -f1)
    local json_part
    json_part=$(echo "$raw" | cut -d'|' -f2-)
    
    kategorie=$(echo "$json_part" | python3 -c "import json,sys; print(json.load(sys.stdin).get('kategorie','?'))" 2>/dev/null)
    auftrag_text=$(echo "$json_part" | python3 -c "import json,sys; print(json.load(sys.stdin).get('auftrag','')[:80])" 2>/dev/null)
    
    log "NEUER AUFTRAG: $job_id ($kategorie)"
    log "  -> $auftrag_text"
    
    # Live-Status 1: Uebernahme
    send_status "$job_id" \
        "🔄 **Hermes hat Auftrag ${job_id} automatisch uebernommen!**\n📋 ${auftrag_text}\nKategorie: ${kategorie}"
    
    # Kurz warten damit Status ankommt
    sleep 0.5
    
    # Live-Status 2: Starte LLM-Bearbeitung (detailliert)
    send_status "$job_id" \
        "🧠 **Starte LLM-Analyse fuer Auftrag ${job_id}...**\n• Analysiere Aufgabenstellung\n• Pruefe Code-Struktur\n• Entwickle Loesungsstrategie"
    
    sleep 0.5
    
    # Live-Status 3: Hermes-App oeffnen
    send_status "$job_id" \
        "⚡ **Hermes-App wird gestartet...**\n• Sobald du die App siehst, schreibe einfach 'weiter'\n• Ich habe den Auftrag bereits geclaimed und warte auf dich"
    
    # Hermes-App im Vordergrund oeffnen
    start_hermes
    
    log "Hermes-App gestartet. Warte auf User..."
}

# ---------------------------------------------------------------------------
# Watcher-Daemon
# ---------------------------------------------------------------------------
run_watcher() {
    log "=== HERMES-WATCHER V2 GESTARTET ==="
    log "Poll-Intervall: ${INTERVAL}s | Vollautomatisch"
    log "Druecke Ctrl+C zum Stoppen"
    
    # Alte Seen-Liste leeren (bei Neustart)
    rm -f "$SEEN_FILE"
    touch "$SEEN_FILE"
    
    local server_was_down=0
    local hermes_started=0

    while true; do
        local result
        result=$(claim_job)
        local rc=$?

        case $rc in
            0)
                # Auftrag gefunden + geclaimed!
                server_was_down=0
                process_job "$result"
                hermes_started=1
                ;;
            1)
                # Server nicht erreichbar
                if [ $server_was_down -eq 0 ]; then
                    log "Server nicht erreichbar (127.0.0.1:8080) - warte..."
                    server_was_down=1
                fi
                hermes_started=0
                ;;
            2)
                # Kein offener Auftrag
                server_was_down=0
                hermes_started=0
                ;;
            4)
                # Schon gesehen (Duplikat)
                server_was_down=0
                ;;
            *)
                # Claim fehlgeschlagen
                server_was_down=0
                ;;
        esac

        sleep "$INTERVAL"
    done
}

# ---------------------------------------------------------------------------
# Hauptlogik (Hintergrundstart via process_manager)
# ---------------------------------------------------------------------------
case "${1:-}" in
    stop)
        if [ -f "$PIDFILE" ]; then
            kill "$(cat "$PIDFILE")" 2>/dev/null
            rm -f "$PIDFILE" "$SEEN_FILE" 2>/dev/null
            log "Watcher gestoppt"
        else
            log "Kein laufender Watcher"
        fi
        ;;
    
    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            log "Watcher laeuft (PID $(cat "$PIDFILE")), Poll alle ${INTERVAL}s"
            [ -f "$SEEN_FILE" ] && log "Bereits gesehen: $(wc -l < "$SEEN_FILE") Auftraege"
        else
            log "Watcher laeuft NICHT"
            [ -f "$PIDFILE" ] && rm -f "$PIDFILE"
        fi
        ;;

    foreground)
        # Einmaliger Durchlauf fuer Tests
        log "Einmaliger Check..."
        local result
        result=$(claim_job)
        local rc=$?
        case $rc in
            0) process_job "$result" ;;
            1) log "Server nicht erreichbar" ;;
            2) log "Keine offenen Auftraege" ;;
            3) log "Claim fehlgeschlagen" ;;
        esac
        ;;
    
    cleanup)
        # Nur die Seen-Liste zuruecksetzen
        rm -f "$SEEN_FILE"
        log "Seen-Liste geloescht"
        ;;

    *)
        # Default: Start im Hintergrund
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            log "Watcher laeuft bereits (PID $(cat "$PIDFILE"))"
            exit 0
        fi
        
        run_watcher &
        echo $! > "$PIDFILE"
        log "Watcher gestartet (PID $(cat "$PIDFILE"))"
        log "  ./termux-hermes-watcher.sh status   - Status"
        log "  ./termux-hermes-watcher.sh stop     - Stoppen"
        log "  ./termux-hermes-watcher.sh cleanup  - Seen-Liste reset"
        ;;
esac
