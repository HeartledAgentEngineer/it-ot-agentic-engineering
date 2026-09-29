#!/data/data/com.termux/files/usr/bin/bash
#
# nachpflege-einrichten.sh — richtet den naechtlichen Nachpflege-Job ein.
#
# Warum es dieses Skript gibt
# ===========================
# termux/nachpflege-job.sh ist der Nachtjob; er laeuft aber nur, wenn Android
# ihn weckt. Dieses Skript registriert ihn wiederkehrend, taeglich. Es ist
# IDEMPOTENT: laeuft der Job schon, passiert nichts.
#
# Vom PC aus laesst sich auf dem Handy KEIN Befehl starten (gemessen: adb shell
# am startservice ... com.termux.RUN_COMMAND -> "Error: Not found; no service
# started."; adb shell run-as com.termux -> "package not debuggable"). Deshalb
# ruft start-termux.sh dieses Skript beim Widget-Tipp auf — der Widget-Tipp ist
# der einzige Weg aufs Handy.
#
# Weg 1 (bevorzugt): termux-job-scheduler, feste JOB_ID, taeglich
#                    (--period-ms 86400000), --persisted damit der Job einen
#                    Neustart uebersteht. Nicht unterstuetzte Schalter werden
#                    zur Laufzeit erkannt und weggelassen (im Log genannt).
# Weg 2 (Rueckfall): crond vorhanden -> eine Zeile in den Crontab des Nutzers
#                    ($PREFIX/var/spool/cron/crontabs/$(whoami), termux-services).
#                    Eine vorhandene eigene Zeile wird ERSETZT, nicht doppelt
#                    angehaengt.
# Weg 3: beides nicht vorhanden -> ehrliche Zeile + Exit 4. Kein stiller
#        Durchlauf.
#
# Grenzen (hart): keine Loeschbefehle, nichts loeschen (nur die eigene alte
# Crontab-Zeile ersetzen, nicht die Datei wegwerfen), kein Datentransfer nach
# aussen. Ergebnis (Weg, Uhrzeit, Exit) geht in dieselbe Berichtsdatei, die auch
# der Job fuellt: hermes_diag/nachpflege_letzte.txt.
#
set -u

# Feste Job-Kennung (eine Zahl) und feste Uhrzeit (nachts). Die Kennung macht
# die Idempotenz-Pruefung eindeutig — sie darf sich nicht aendern.
JOB_ID=1901
UHRZEIT="03:00"
STUNDE=3
MINUTE=0

# Pfad des eigentlichen Jobs: neben diesem Skript (Repo-Ordner termux/).
skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"
JOB_SKRIPT="$HIER/nachpflege-job.sh"

LOG="$HOME/nachpflege-einrichten.log"

# Log begrenzen (nur die letzten 500 Zeilen behalten).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 204800 ]; then
    tail -n 500 "$LOG" > "$LOG.neu" 2>/dev/null && mv -f "$LOG.neu" "$LOG"
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
}

# Berichtsdatei im freigegebenen Download-Ordner (der Termux-Heimordner ist
# ueber ADB nicht lesbar). Nur Weg/Zahlen, kein Inhalt, kein Geheimnis.
BERICHT_BASIS="$HOME/storage/downloads"
[ -d "$BERICHT_BASIS" ] || BERICHT_BASIS="/sdcard/Download"
BERICHT_ORDNER="$BERICHT_BASIS/hermes_diag"
mkdir -p "$BERICHT_ORDNER" 2>/dev/null
BERICHT="$BERICHT_ORDNER/nachpflege_letzte.txt"
bericht() { printf 'nachpflege_einrichtung %s weg=%s uhrzeit=%s exit=%s\n' \
    "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$UHRZEIT" "$2" >> "$BERICHT" 2>/dev/null; }

if [ ! -f "$JOB_SKRIPT" ]; then
    log "FEHLER: nachpflege-job.sh nicht gefunden ($JOB_SKRIPT) - nichts eingerichtet."
    bericht "fehler" "1"
    exit 1
fi

# ── Weg 1: termux-job-scheduler ───────────────────────────────────────────────
if command -v termux-job-scheduler >/dev/null 2>&1; then
    # Erst fragen: schon eingerichtet? Dann ist nichts zu tun (idempotent).
    if termux-job-scheduler --list 2>/dev/null | grep -q "$JOB_ID"; then
        log "schon eingerichtet (JOB_ID $JOB_ID) - nichts zu tun."
        bericht "job-scheduler-schon-da" "0"
        exit 0
    fi

    # Tatsaechlich unterstuetzte Schalter zur Laufzeit pruefen, nicht raten.
    HILFE="$(termux-job-scheduler --help 2>&1 || true)"
    hat_schalter() { printf '%s' "$HILFE" | grep -q -- "$1"; }

    PERSIST=""
    if hat_schalter "--persisted"; then
        PERSIST="--persisted true"
    else
        log "Schalter --persisted nicht unterstuetzt - weggelassen (Neustart-Ueberleben dann nicht garantiert)."
    fi

    # shellcheck disable=SC2086
    if termux-job-scheduler \
            --job-id "$JOB_ID" \
            --script "$JOB_SKRIPT" \
            --period-ms 86400000 \
            $PERSIST >/dev/null 2>&1; then
        log "eingerichtet ueber termux-job-scheduler: JOB_ID $JOB_ID, taeglich um $UHRZEIT."
        bericht "job-scheduler" "0"
        exit 0
    fi
    log "termux-job-scheduler wurde gefunden, die Registrierung schlug aber fehl - versuche crond."
fi

# ── Weg 2: crond (termux-services) ────────────────────────────────────────────
if command -v crond >/dev/null 2>&1; then
    CRONTAB="$PREFIX/var/spool/cron/crontabs/$(whoami)"
    mkdir -p "$(dirname "$CRONTAB")" 2>/dev/null
    if [ -f "$CRONTAB" ]; then
        # Vorhandene EIGENE Zeile ersetzen statt doppelt anhaengen. Die Datei
        # bleibt bestehen; es wird nur die eine Zeile neu geschrieben.
        grep -v "nachpflege-job.sh" "$CRONTAB" > "$CRONTAB.neu" 2>/dev/null \
            && mv -f "$CRONTAB.neu" "$CRONTAB"
    fi
    printf '%s %s * * * bash %s\n' "$MINUTE" "$STUNDE" "$JOB_SKRIPT" >> "$CRONTAB"
    log "eingerichtet ueber crond: Eintrag $MINUTE $STUNDE * * * in $CRONTAB (taeglich um $UHRZEIT)."
    bericht "crond" "0"
    exit 0
fi

# ── Weg 3: nichts vorhanden -> ehrliche Zeile, kein stiller Durchlauf ─────────
log "WEDER termux-job-scheduler NOCH crond vorhanden - keine Einrichtung moeglich (Exit 4)."
bericht "keins" "4"
exit 4
