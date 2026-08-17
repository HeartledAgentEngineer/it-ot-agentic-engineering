#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# termux-hermes-watcher.sh - V3
#
# Pollt das Auftragsbuch alle 3 Sekunden. Liegt ein offener Auftrag vor:
#   1. abholen (GET /naechster - setzt atomar offen -> laeuft)
#   2. Uebernahme als Zwischenmeldung in den Chat schreiben
#   3. Hermes-App in den Vordergrund holen
#
# Nutzung:
#   ./termux-hermes-watcher.sh            Start im Hintergrund
#   ./termux-hermes-watcher.sh stop       Stoppen
#   ./termux-hermes-watcher.sh status     Laeuft er? Wann zuletzt geprueft?
#   ./termux-hermes-watcher.sh foreground Ein einzelner Durchlauf (Test)
#   ./termux-hermes-watcher.sh log        Die letzten 40 Logzeilen
#
# Abhaengigkeiten:
#   pkg install termux-api    (termux-notification, termux-wake-lock)
#
# -----------------------------------------------------------------------------
# Was sich gegenueber V2 geaendert hat und warum:
#
#   * Der Vorabcheck auf "?limit=1" ist weg. Er sah nur den neuesten Auftrag;
#     war der bereits fertig, blieb ein aelterer offener fuer immer liegen.
#     /naechster erledigt Suche und Abholen ohnehin in einem atomaren Schritt.
#
#   * Die .seen-Liste ist weg. Sie wurde erst NACH dem Abholen geprueft - ein
#     bekannter Auftrag wurde also auf "laeuft" gesetzt und dann verworfen.
#     Das Abholen selbst ist die Duplikatsperre: offen -> laeuft geht nur einmal.
#
#   * Der Component-Name fuer `am start` war doppelt qualifiziert
#     ("pkg/.pkg.MainActivity") und damit ungueltig - Hermes ist nie von
#     allein gestartet. Jetzt drei Stufen mit geprueftem Rueckgabewert.
#
#   * Alles laeuft in ein Logfile. Vorher schrieb log() auf stdout, das im
#     Hintergrundprozess ins Leere lief: eine Stoerung sah aus wie Ruhe.
# =============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$SCRIPT_DIR/.hermes-watcher.pid"
LOGFILE="$SCRIPT_DIR/.hermes-watcher.log"
ALIVEFILE="$SCRIPT_DIR/.hermes-watcher.alive"

API="${HERMES_API:-http://127.0.0.1:8080}"
INTERVAL="${HERMES_INTERVAL:-3}"
LOG_MAX_BYTES=1048576  # 1 MB, danach wird einmal rotiert

# Hermes-App (Android).
#
# Der Klassenname ist voll qualifiziert und liegt in einem ANDEREN Namensraum
# als das Paket: Paket "com.hermesagent.android", Klasse "com.hermes.android".
# Die Kurzform "paket/.MainActivity" funktioniert deshalb nicht - sie wuerde
# zu com.hermesagent.android.MainActivity expandieren, was es nicht gibt.
#
# Gemessen am Geraet (Motorola edge 50, 17.08.2026) mit:
#   adb shell cmd package resolve-activity --brief com.hermesagent.android
# Sollte Hermes umziehen, ist das der Befehl, der den neuen Wert liefert.
HERMES_PKG="${HERMES_PKG:-com.hermesagent.android}"
HERMES_ACTIVITY="${HERMES_ACTIVITY:-com.hermes.android.MainActivity}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
rotiere_log() {
    [ -f "$LOGFILE" ] || return 0
    local groesse
    groesse=$(wc -c < "$LOGFILE" 2>/dev/null || echo 0)
    if [ "$groesse" -gt "$LOG_MAX_BYTES" ]; then
        mv -f "$LOGFILE" "$LOGFILE.alt" 2>/dev/null
    fi
}

log() {
    local zeile
    zeile="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$zeile"
    echo "$zeile" >> "$LOGFILE" 2>/dev/null
}

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# Ruft die API auf und trennt Rumpf von Statuscode. Ein Fehler wird geloggt,
# nicht verschluckt - das war der Kern des Problems in V2.
api_post() {
    local pfad="$1" payload="$2" zweck="$3"
    local antwort status rumpf

    antwort=$(curl -s --max-time 5 -w '\n%{http_code}' \
        -X POST "${API}${pfad}" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>/dev/null)

    if [ -z "$antwort" ]; then
        log "FEHLER: $zweck - keine Antwort von $API"
        return 1
    fi

    status=$(printf '%s' "$antwort" | tail -n1)
    rumpf=$(printf '%s' "$antwort" | sed '$d')

    if [ "$status" != "200" ] && [ "$status" != "201" ]; then
        log "FEHLER: $zweck - HTTP $status: $(printf '%s' "$rumpf" | head -c 200)"
        return 1
    fi
    return 0
}

# Text -> JSON-String.
#
# Gelesen wird ausdruecklich aus sys.stdin.buffer und fest als UTF-8 dekodiert.
# `sys.stdin.read()` wuerde die Zeichensatz-Einstellung der Umgebung benutzen;
# steht die nicht auf UTF-8, zerbrechen Umlaute und Emojis zu einzelnen
# Surrogaten - der Server antwortet dann mit HTTP 500 und die Meldung ist weg.
# json.dumps schreibt per Vorgabe reines ASCII, das ueberlebt jeden Transport.
json_text() {
    python3 -c "
import json, sys
print(json.dumps(sys.stdin.buffer.read().decode('utf-8', 'replace').strip()))
" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Ist python3 brauchbar?
#
# Ohne diese Pruefung ist der Watcher blind: Das Abholen setzt den Auftrag
# serverseitig auf "laeuft", und wenn danach das Auswerten scheitert, ist der
# Auftrag verschluckt - er kommt erst nach Ablauf der Frist zurueck. Lieber
# gar nicht erst anfangen.
# ---------------------------------------------------------------------------
python_pruefen() {
    if ! printf '{}' | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
        log "ABBRUCH: python3 ist nicht benutzbar - der Watcher kann Auftraege"
        log "         nicht auswerten. Auf Termux: pkg install python"
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Auftrag abholen
#   stdout: "<kurz-id>|<voll-id>|<kategorie>|<auftragstext>"
#   rc 0 = Auftrag geholt | 1 = Server weg | 2 = nichts offen
#   rc 3 = Auftrag da, aber nicht auswertbar (bereits abgeholt!)
# ---------------------------------------------------------------------------
auftrag_abholen() {
    local antwort status rumpf

    antwort=$(curl -s --max-time 5 -w '\n%{http_code}' \
        "${API}/api/auftraege/naechster" 2>/dev/null)
    [ -z "$antwort" ] && return 1

    status=$(printf '%s' "$antwort" | tail -n1)
    rumpf=$(printf '%s' "$antwort" | sed '$d')

    if [ "$status" != "200" ]; then
        log "FEHLER: Abholen - HTTP $status: $(printf '%s' "$rumpf" | head -c 200)"
        return 1
    fi

    # "Nichts zu tun" ohne python3 erkennbar. Nur so laesst sich ein leeres
    # Auftragsbuch von einem gescheiterten Auswerten unterscheiden - sonst
    # sieht ein kaputter Watcher aus wie ein ruhiger.
    if printf '%s' "$rumpf" | grep -q '"auftrag": *null'; then
        return 2
    fi

    local zeile
    # Auch hier fest UTF-8 rein und raus - der Auftragstext ist diktiert und
    # steckt voller Umlaute.
    zeile=$(printf '%s' "$rumpf" | python3 -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    roh = sys.stdin.buffer.read().decode('utf-8', 'replace')
    a = (json.loads(roh) or {}).get('auftrag')
    if a:
        felder = [
            a.get('id','')[:8],
            a.get('id',''),
            a.get('kategorie','?'),
            ' '.join((a.get('auftrag') or '').split())[:100],
        ]
        print('|'.join(felder))
except Exception:
    pass
" 2>/dev/null)

    if [ -z "$zeile" ]; then
        log "FEHLER: Auftrag abgeholt, aber nicht auswertbar. Er steht jetzt auf"
        log "        'laeuft' und kommt erst nach Ablauf der Frist zurueck."
        log "        Antwort war: $(printf '%s' "$rumpf" | head -c 200)"
        return 3
    fi

    printf '%s' "$zeile"
    return 0
}

zwischenmeldung() {
    local auftrag_id="$1" meldung="$2"
    local text
    text=$(printf '%s' "$meldung" | json_text)
    [ -z "$text" ] && return 1
    api_post "/api/auftraege/${auftrag_id}/status" "{\"meldung\": $text}" \
        "Zwischenmeldung fuer $auftrag_id"
}

# ---------------------------------------------------------------------------
# Hermes-App in den Vordergrund holen
#
# Drei Stufen, jede mit geprueftem Ergebnis. `am start` meldet Fehler auf
# stdout statt ueber den Rueckgabewert, deshalb wird die Ausgabe mitgelesen.
# ---------------------------------------------------------------------------
hermes_starten() {
    local ausgabe rc

    ausgabe=$(am start -n "${HERMES_PKG}/${HERMES_ACTIVITY}" 2>&1)
    rc=$?
    if [ "$rc" -eq 0 ] && ! printf '%s' "$ausgabe" | grep -qi "error\|exception"; then
        log "Hermes gestartet (am start ${HERMES_PKG}/${HERMES_ACTIVITY})"
        return 0
    fi
    log "am start fehlgeschlagen: $(printf '%s' "$ausgabe" | head -c 200)"

    # Zweite Stufe: braucht keinen Activity-Namen, nimmt den Launcher-Eintrag.
    ausgabe=$(monkey -p "$HERMES_PKG" -c android.intent.category.LAUNCHER 1 2>&1)
    if printf '%s' "$ausgabe" | grep -q "Events injected: 1"; then
        log "Hermes gestartet (monkey/Launcher)"
        return 0
    fi
    log "monkey fehlgeschlagen: $(printf '%s' "$ausgabe" | head -c 200)"

    # Dritte Stufe: Wenn die App nicht von allein hochkommt, muss der Nutzer
    # es erfahren - stilles Scheitern ist der schlimmste Ausgang.
    termux-notification \
        --id hermes-job \
        --title "Hermes konnte nicht starten" \
        --content "Auftrag liegt bereit. Bitte Hermes von Hand oeffnen." \
        --priority high \
        --action "am start -n ${HERMES_PKG}/${HERMES_ACTIVITY}" >/dev/null 2>&1

    log "WARNUNG: Hermes liess sich nicht starten - Benachrichtigung gesetzt"
    return 1
}

# ---------------------------------------------------------------------------
# Einen abgeholten Auftrag verarbeiten
# ---------------------------------------------------------------------------
auftrag_verarbeiten() {
    local zeile="$1"
    local kurz_id kategorie text

    kurz_id=$(printf '%s' "$zeile" | cut -d'|' -f1)
    kategorie=$(printf '%s' "$zeile" | cut -d'|' -f3)
    text=$(printf '%s' "$zeile" | cut -d'|' -f4-)

    log "AUFTRAG $kurz_id ($kategorie): $text"

    zwischenmeldung "$kurz_id" \
        "🔄 Auftrag ${kurz_id} abgeholt (${kategorie}): ${text}" \
        || log "WARNUNG: Uebernahme-Meldung kam nicht im Auftragsbuch an"

    if hermes_starten; then
        zwischenmeldung "$kurz_id" \
            "⚡ Hermes-App wurde geoeffnet. Der Auftrag liegt im Auftragsbuch bereit."
    else
        zwischenmeldung "$kurz_id" \
            "⚠️ Hermes-App liess sich nicht automatisch oeffnen - bitte von Hand starten."
    fi
}

# ---------------------------------------------------------------------------
# Dauerlauf
# ---------------------------------------------------------------------------
run_watcher() {
    rotiere_log
    log "=== HERMES-WATCHER V3 gestartet (Takt ${INTERVAL}s, API ${API}) ==="

    python_pruefen || exit 1

    termux-wake-lock >/dev/null 2>&1 && log "Wake-Lock gesetzt" \
        || log "Kein Wake-Lock (termux-api fehlt?) - Android kann den Watcher schlafen legen"

    local server_weg=0

    while true; do
        # Lebenszeichen: erlaubt der Oberflaeche zu erkennen, ob der Watcher
        # noch atmet, statt stumm auf einen Auftrag zu warten.
        date +%s > "$ALIVEFILE" 2>/dev/null

        local zeile rc
        zeile=$(auftrag_abholen)
        rc=$?

        case $rc in
            0)
                [ "$server_weg" -eq 1 ] && log "Server wieder erreichbar"
                server_weg=0
                auftrag_verarbeiten "$zeile"
                ;;
            1)
                if [ "$server_weg" -eq 0 ]; then
                    log "Server nicht erreichbar ($API) - warte"
                    server_weg=1
                fi
                ;;
            2)
                [ "$server_weg" -eq 1 ] && log "Server wieder erreichbar"
                server_weg=0
                ;;
            3)
                # Auswerten gescheitert. Weiterlaufen waere sinnlos: Der
                # naechste Takt holt den naechsten Auftrag und verschluckt
                # ihn genauso. Lieber laut stehenbleiben.
                server_weg=0
                termux-notification \
                    --id hermes-watcher-fehler \
                    --title "Hermes-Watcher gestoppt" \
                    --content "Auftrag konnte nicht ausgewertet werden. Siehe Log." \
                    --priority high >/dev/null 2>&1
                log "ABBRUCH: siehe Fehler oben"
                exit 1
                ;;
        esac

        sleep "$INTERVAL"
    done
}

# ---------------------------------------------------------------------------
# Kommandos
# ---------------------------------------------------------------------------
case "${1:-}" in
    stop)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            kill "$(cat "$PIDFILE")" 2>/dev/null
            log "Watcher gestoppt (PID $(cat "$PIDFILE"))"
        else
            log "Kein laufender Watcher"
        fi
        rm -f "$PIDFILE" "$ALIVEFILE" 2>/dev/null
        termux-wake-unlock >/dev/null 2>&1
        ;;

    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            log "Watcher laeuft (PID $(cat "$PIDFILE")), Takt ${INTERVAL}s"
            if [ -f "$ALIVEFILE" ]; then
                alter=$(( $(date +%s) - $(cat "$ALIVEFILE" 2>/dev/null || echo 0) ))
                log "Letzte Pruefung vor ${alter}s"
                [ "$alter" -gt $((INTERVAL * 5)) ] && \
                    log "WARNUNG: Der Prozess lebt, prueft aber nicht mehr"
            fi
        else
            log "Watcher laeuft NICHT"
            rm -f "$PIDFILE" 2>/dev/null
        fi
        ;;

    log)
        if [ -f "$LOGFILE" ]; then
            tail -n 40 "$LOGFILE"
        else
            echo "Noch kein Logfile: $LOGFILE"
        fi
        ;;

    foreground)
        # Ein einzelner Durchlauf zum Pruefen.
        log "Einmaliger Durchlauf"
        python_pruefen || exit 1
        zeile=$(auftrag_abholen)
        case $? in
            0) auftrag_verarbeiten "$zeile" ;;
            1) log "Server nicht erreichbar ($API)" ;;
            2) log "Keine offenen Auftraege" ;;
            3) exit 1 ;;
        esac
        ;;

    dauerlauf)
        # Interner Einstiegspunkt des abgeloesten Hintergrundprozesses.
        # Er traegt sich selbst in die PID-Datei ein - `$!` des Aufrufers
        # waere die PID von setsid und damit nicht die, die gestoppt
        # werden muss.
        echo $$ > "$PIDFILE"
        run_watcher
        ;;

    *)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            log "Watcher laeuft bereits (PID $(cat "$PIDFILE"))"
            exit 0
        fi

        # Eine Leiche von einem abgestuerzten Lauf wuerde sonst sofort als
        # "laeuft schon" durchgehen.
        rm -f "$PIDFILE" 2>/dev/null

        # setsid loest den Watcher von der Termux-Sitzung: Er ueberlebt das
        # Schliessen des Fensters. Ohne das war er beim naechsten Blick weg.
        setsid "$0" dauerlauf >/dev/null 2>&1 &

        # Kurz warten, bis sich der Dauerlauf selbst eingetragen hat.
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            [ -f "$PIDFILE" ] && break
            sleep 0.3
        done

        if [ -f "$PIDFILE" ]; then
            log "Watcher gestartet (PID $(cat "$PIDFILE"))"
        else
            log "FEHLER: Watcher meldete sich nicht - siehe $LOGFILE"
            exit 1
        fi
        log "  ./termux-hermes-watcher.sh status  - laeuft er?"
        log "  ./termux-hermes-watcher.sh log     - letzte Logzeilen"
        log "  ./termux-hermes-watcher.sh stop    - stoppen"
        ;;
esac
