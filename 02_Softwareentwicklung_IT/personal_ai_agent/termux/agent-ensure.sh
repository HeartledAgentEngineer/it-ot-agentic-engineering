#!/data/data/com.termux/files/usr/bin/sh
#
# agent-ensure.sh — der App-Weg: Backend sicherstellen, ohne laufenden Betrieb
# anzufassen. Seit 10.10.2026 gibt es EINEN gemeinsamen Startweg: App-Knopf und
# Widget tippen denselben Ablauf. Die Vorbereitung (git pull + alle Uebernahmen
# inkl. Wissensdatei memory.db) steht EINMAL in termux/start-vorbereiten.sh und
# wird hier aufgerufen; in dieser Datei steht kein Uebernahme-Schritt doppelt.
#
# Aufrufwege aus der Android-App "Hey Agent":
#   a) F-Droid-/GitHub-Termux: per RUN_COMMAND-Intent, unsichtbar, auf den
#      festen Pfad ~/agent-ensure.sh - das ist seit 10.10.2026 nur noch eine
#      duenne Weiterleitung auf DIESE Datei im Projektordner (angelegt von
#      termux/hey-agent-einrichten.sh; eine Kopie dort veraltete still).
#   b) Play-Store-Termux (hat kein RUN_COMMAND): die App oeffnet Termux, und
#      $PREFIX/etc/profile.d/hey-agent.sh ruft beim Sitzungsstart
#      agent-ensure.sh --app-zurueck
#      Dann holt das Skript nach dem Start die App ueber heyagent://start
#      zurueck. Einrichtung einmalig: sh termux/hey-agent-einrichten.sh
#      (NICHT ~/.bashrc: Termux startet Login-Shells, die lesen es nicht.)
#
# Verhalten (Entscheidung 10.10.2026; Befund: bei dauerhaft laufendem Server
# liefen Pull und Wissensdatei-Uebernahme sonst NIE):
#   * Die gemeinsame Vorbereitung laeuft bei JEDEM Lauf - auch wenn /health
#     schon antwortet (beides schnell und idempotent). Mit --laufend entfaellt
#     darin nur die Sicherung auf Auftrag (kein Sichern aus laufendem Betrieb).
#   * Der Serverstart selbst wird uebersprungen, wenn das Backend antwortet:
#     kein Neustart, kein Ruecksprung zur App (sonst spraenge jedes manuelle
#     Termux-Oeffnen in die App).
#   * Nur wenn /health NICHT antwortet, startet das Backend - ueber
#     termux/backend-starten.sh (die einzige Startstelle; abgeloest, mit --reload).
#   * AUSNAHME Umstellung HTTP -> HTTPS (H3b): Nach der Vorbereitung prueft
#     termux/tls-umstellung.sh, ob der laufende Modus zum Zertifikatsstand passt.
#     Kam das Zertifikat erst jetzt, wird der alte HTTP-Server genau einmal
#     beendet und neu gestartet. Die Pruefung steht VOR dem Ausstieg bei
#     laufendem Server - sonst bliebe der HTTP-Server im WLAN offen.
#
# Log: ~/agent-ensure.log (wird bei jedem Lauf angehaengt, bei > 200 KB gekuerzt)

PORT="${PORT:-8080}"
LOG="$HOME/agent-ensure.log"
WARTEN_S=45          # so lange auf /health warten, bevor die App zurueckgeholt wird

APP_ZURUECK=0
[ "${1:-}" = "--app-zurueck" ] && APP_ZURUECK=1

# Meldung ins Log und - beim Aufruf aus der Termux-Sitzung - auch auf den Schirm.
sag() {
    log "$*"
    [ "$APP_ZURUECK" = 1 ] && echo "Hey Agent: $*"
}

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

# Laeuft das Backend schon? EINMAL fragen; das Ergebnis steuert nur noch den
# Serverstart, nicht mehr die Vorbereitung (Entscheidung 10.10.2026).
if health_ok; then LAEUFT=1; else LAEUFT=0; fi

# Projektordner bestimmen. Zuerst ueber den eigenen Ort: das Skript liegt in
# <Projekt>/termux/ (so ruft es der Starteintrag aus profile.d). Liegt es als Kopie
# in ~ (Aufruf per RUN_COMMAND), hilft die Widget-Verknuepfung ~/.shortcuts/agent.
# Sie zeigt auf termux/agent-start - ihr Ordner ist also termux/, der Projektordner
# dessen Elternordner (am Handy gemessen 30.09.2026).
if [ -z "${PROJEKT:-}" ]; then
    PROJEKT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
    [ -d "$PROJEKT/backend" ] || PROJEKT=""
fi
if [ -z "${PROJEKT:-}" ]; then
    verweis="$HOME/.shortcuts/agent"
    if [ -L "$verweis" ]; then
        ziel="$(readlink "$verweis")"
        PROJEKT="$(cd "$(dirname "$ziel")" 2>/dev/null && pwd)"
        case "$PROJEKT" in
            */termux) PROJEKT="$(dirname "$PROJEKT")" ;;
        esac
    fi
fi
if [ -z "${PROJEKT:-}" ] || [ ! -d "$PROJEKT/backend" ]; then
    sag "FEHLER: Projektordner nicht gefunden (PROJEKT='${PROJEKT:-}'). PROJEKT setzen."
    exit 1
fi

# DIE gemeinsame Start-Vorbereitung: git pull + alle Uebernahmen + Wissensdatei.
# Laeuft IMMER (auch bei laufendem Server) - bei laufendem Server mit --laufend,
# damit die Sicherung auf Auftrag nicht aus dem laufenden Betrieb startet.
_VORBEREITUNG_MODUS=""
[ "$LAEUFT" = "1" ] && _VORBEREITUNG_MODUS="--laufend"
if [ -f "$PROJEKT/termux/start-vorbereiten.sh" ]; then
    bash "$PROJEKT/termux/start-vorbereiten.sh" $_VORBEREITUNG_MODUS "$PROJEKT" >> "$LOG" 2>&1 || true
else
    sag "FEHLER: $PROJEKT/termux/start-vorbereiten.sh fehlt - es startet ohne Uebernahmen."
fi

# Umstellung HTTP -> HTTPS (H3b): VOR dem Ausstieg bei laufendem Server, nach der
# Vorbereitung (die kann das Zertifikat gerade erst uebernommen haben). Exit 10
# oder 4 heisst: das Skript hat den Server selbst neu gestartet (bzw. es
# versucht und Warnung geschrieben) - dann startet unten nichts zweimal.
UMGESTELLT=0
if [ -f "$PROJEKT/termux/tls-umstellung.sh" ]; then
    bash "$PROJEKT/termux/tls-umstellung.sh" --abloesen --reload --log "$LOG" >> "$LOG" 2>&1
    _umstellung=$?
    if [ "$_umstellung" = "10" ] || [ "$_umstellung" = "4" ]; then
        UMGESTELLT=1
        sag "Umstellung HTTP -> HTTPS durchgefuehrt (Ergebnis $_umstellung, Einzelheiten im Log)"
    fi
else
    log "WARNUNG: $PROJEKT/termux/tls-umstellung.sh fehlt - Modus wird nicht geprueft."
fi

if [ "$LAEUFT" = "1" ]; then
    if [ "$UMGESTELLT" = "1" ]; then
        log "Backend lief schon (Port $PORT) - Umstellung hat es neu gestartet, kein weiterer Serverstart."
    else
        log "Backend laeuft bereits (Port $PORT) - Vorbereitung gelaufen, Serverstart uebersprungen."
    fi
    exit 0
fi

if [ "$UMGESTELLT" = "0" ]; then
    log "Backend antwortet nicht - starte das Backend (Projekt: $PROJEKT)"
    # Die einzige Startstelle: Modus (mit/ohne Zertifikat), PORT und HOST_BIND
    # (aus backend/.env, Standard 0.0.0.0) entscheidet backend-starten.sh.
    # Vom Terminal geloest, weil dieses Skript im Hintergrund per Intent laeuft
    # und danach endet; --reload wirkt nur im Modus ohne Zertifikat.
    bash "$PROJEKT/termux/backend-starten.sh" --abloesen --reload --log "$LOG" >> "$LOG" 2>&1
    sag "Backend startet (siehe Log) ..."
fi

if [ "$APP_ZURUECK" = 1 ]; then
    i=0
    while [ $i -lt "$WARTEN_S" ] && ! health_ok; do
        i=$((i+1))
        sleep 1
    done
    if health_ok; then
        sag "Backend bereit nach ${i} s - zurueck zur App"
    else
        sag "Backend nach ${WARTEN_S} s noch nicht bereit - Log: $LOG"
    fi
    # Auch ohne Erfolg zurueck: die App zeigt dann ihre eigene Meldung.
    am start -a android.intent.action.VIEW -d "heyagent://start" >/dev/null 2>&1         || sag "Hey Agent liess sich nicht oeffnen - bitte von Hand starten"
fi
exit 0
