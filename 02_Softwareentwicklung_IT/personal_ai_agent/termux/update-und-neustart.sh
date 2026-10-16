#!/data/data/com.termux/files/usr/bin/bash
#
# Update und Neustart aus der Browser-Oberflaeche.
# Das Skript selbst laeuft abgekoppelt; der API-Endpunkt sendet seine Antwort
# vorher. Der Pull muss erfolgreich sein, bevor der laufende Server endet.

set -u

SKRIPT="$0"
[ -L "$SKRIPT" ] && SKRIPT="$(readlink "$SKRIPT")"
TERMUX_ORDNER="$(cd "$(dirname "$SKRIPT")" 2>/dev/null && pwd)"
PROJEKT="$(cd "$TERMUX_ORDNER/.." 2>/dev/null && pwd)"

DOWNLOADS="$HOME/storage/downloads"
[ -d "$DOWNLOADS" ] || DOWNLOADS="/sdcard/Download"
LOG_ORDNER="$DOWNLOADS/hermes_diag"
LOG_DATEI="$LOG_ORDNER/update-und-neustart.log"
if ! mkdir -p "$LOG_ORDNER" 2>/dev/null || ! : >> "$LOG_DATEI"; then
    printf '%s\n' "FEHLER: Protokoll unter $LOG_DATEI nicht beschreibbar; Update abgebrochen." >&2
    exit 1
fi

protokoll() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_DATEI"
}

protokoll "Update und Neustart gestartet."
if [ -z "$PROJEKT" ] || [ ! -d "$PROJEKT/backend" ]; then
    protokoll "FEHLER: Projektordner mit backend/ nicht gefunden; Server nicht beendet."
    exit 1
fi
if [ ! -f "$PROJEKT/termux/backend-beenden.sh" ]; then
    protokoll "FEHLER: termux/backend-beenden.sh fehlt; Server nicht beendet."
    exit 1
fi
if [ ! -f "$HOME/agent-ensure.sh" ]; then
    protokoll "FEHLER: ~/agent-ensure.sh fehlt; Server nicht beendet."
    exit 1
fi

cd "$PROJEKT" || {
    protokoll "FEHLER: Projektordner nicht erreichbar; Server nicht beendet."
    exit 1
}

# Git-Fehlergrund mitschreiben, Zugangsdaten in URLs aber nie protokollieren.
git pull --ff-only 2>&1 | sed -E 's#(://)[^/@[:space:]]+@#\1[redacted]@#g' >> "$LOG_DATEI"
PULL_STATUS=${PIPESTATUS[0]}
if [ "$PULL_STATUS" -ne 0 ]; then
    protokoll "FEHLER: git pull --ff-only fehlgeschlagen (Exit $PULL_STATUS); Server nicht beendet und nicht neu gestartet."
    exit "$PULL_STATUS"
fi
protokoll "Git-Pull erfolgreich."

# Kleine Pause: Die HTTP-Antwort ist bereits gesendet; der Browser kann die
# Rueckmeldung anzeigen, bevor der Server verschwindet.
protokoll "Warte 1 Sekunde vor dem Beenden des Servers."
sleep 1

bash "$PROJEKT/termux/backend-beenden.sh" >> "$LOG_DATEI" 2>&1
STOP_STATUS=$?
if [ "$STOP_STATUS" -ne 0 ]; then
    protokoll "FEHLER: Backend konnte nicht sicher beendet werden (Exit $STOP_STATUS); Start nicht versucht."
    exit "$STOP_STATUS"
fi
protokoll "Backend beendet; starte ~/agent-ensure.sh."

sh "$HOME/agent-ensure.sh" >> "$LOG_DATEI" 2>&1
START_STATUS=$?
if [ "$START_STATUS" -ne 0 ]; then
    protokoll "FEHLER: ~/agent-ensure.sh fehlgeschlagen (Exit $START_STATUS)."
    exit "$START_STATUS"
fi
protokoll "~/agent-ensure.sh wurde erfolgreich aufgerufen."
exit 0
