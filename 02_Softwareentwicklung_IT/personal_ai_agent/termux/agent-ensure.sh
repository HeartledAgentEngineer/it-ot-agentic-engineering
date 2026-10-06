#!/data/data/com.termux/files/usr/bin/sh
#
# agent-ensure.sh — startet das Backend NUR, wenn es nicht antwortet.
#
# Gegenstueck zu start-termux.sh, aber bewusst schlanker: kein Beenden
# laufender Prozesse. Laeuft der Server schon, passiert nichts (idempotent) -
# auch kein Pull und keine Uebernahme. Sonst: Pull, pCloud-Schluessel und die
# Foto-/Personen-Dateien aus dem Download-Ordner uebernehmen, dann Start.
#
# Zwei Aufrufwege aus der Android-App "Hey Agent":
#   a) F-Droid-/GitHub-Termux: per RUN_COMMAND-Intent, unsichtbar.
#   b) Play-Store-Termux (hat kein RUN_COMMAND): die App oeffnet Termux, und
#      $PREFIX/etc/profile.d/hey-agent.sh ruft beim Sitzungsstart
#      agent-ensure.sh --app-zurueck
#      Dann zieht das Skript den neuesten Stand (nur Vorspulen), startet das
#      Backend, wartet auf /health und holt die App ueber heyagent://start
#      zurueck. Einrichtung einmalig: sh termux/hey-agent-einrichten.sh
#      (NICHT ~/.bashrc: Termux startet Login-Shells, die lesen es nicht.)
# Voller Abgleich in beide Richtungen + Neustart bleibt Sache von start-termux.sh.
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

if health_ok; then
    log "Backend laeuft bereits (Port $PORT) - nichts zu tun."
    exit 0
fi

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

# CPU nicht einschlafen lassen (wie start-termux.sh).
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Neuesten Stand holen - NUR Vorspulen (pull --ff-only), und nur wenn das Handy
# wirklich hinter origin liegt. Eigene Handy-Commits oder lokale Aenderungen
# werden nie ueberschrieben; dann startet der Server mit dem vorhandenen Stand.
if git -C "$PROJEKT" fetch origin --quiet 2>/dev/null; then
    if git -C "$PROJEKT" merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
        if git -C "$PROJEKT" pull --ff-only --quiet 2>>"$LOG"; then
            sag "Stand: $(git -C "$PROJEKT" log --oneline -1 2>/dev/null)"
        else
            sag "Pull nicht moeglich (lokale Aenderungen?) - starte mit altem Stand"
        fi
    else
        sag "Handy hat eigene Commits - kein Pull, starte mit vorhandenem Stand (Abgleich per Widget)"
    fi
else
    sag "git fetch fehlgeschlagen (Netz?) - starte mit altem Stand"
fi

cd "$PROJEKT/backend" || { log "FEHLER: backend/ fehlt in $PROJEKT"; exit 1; }

# pCloud-Zugang aus dem Download-Ordner in backend/.env uebernehmen — eine
# gemeinsame Quelle fuer alle drei Startwege (start-termux.sh, Widget
# agent-start, App agent-ensure.sh; Issue #3 Befund 1, 02.10.2026). Darf den
# Start nie verhindern (|| true); fehlt die Datei, passiert nichts.
bash "$PROJEKT/termux/pcloud-schluessel-uebernehmen.sh" "$PROJEKT/backend/.env" >> "$LOG" 2>&1 || true
# Vorlese-Schluessel (OPENROUTER_TTS_KEY, 06.10.2026) auf demselben Weg - vom PC
# gelegt mit tools/handy/vorlese_schluessel_senden.py. Darf den Start nie verhindern.
bash "$PROJEKT/termux/schluessel-uebernehmen.sh" "$PROJEKT/backend/.env" vorlese_schluessel.txt "Vorlese-Schlüssel" OPENROUTER_TTS_KEY >> "$LOG" 2>&1 || true

# Datendateien vom PC uebernehmen (01.10.2026, Plan Foto-Gedaechtnis Schritt 2).
# Vorher lief die Uebernahme NUR in start-termux.sh (Widget-Tipp) - der echte
# App-Start kam dort nie vorbei, vom PC per Kabel gelegte Dateien blieben im
# Download-Ordner liegen. Gleiches Werkzeug, gleiche Liste wie start-termux.sh
# (sha256 hart, alte Fassung als *.vorher, entfernt nur die eigene
# Uebergabedatei). Darf den Start NIE verhindern (|| true); fehlt die
# Uebergabedatei (Normalfall), passiert nichts.
QUELLE_DATEN="$HOME/storage/downloads"
[ -d "$QUELLE_DATEN" ] || QUELLE_DATEN="/sdcard/Download"
PROTO_DATEN="$QUELLE_DATEN/hermes_diag"
mkdir -p "$PROTO_DATEN" 2>/dev/null || true
if [ -d "$PROTO_DATEN" ]; then
    python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
        --quelle "$QUELLE_DATEN" \
        --ziel "$HOME/foto_sortierung" \
        --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl \
        --protokoll "$PROTO_DATEN/uebergabe_letzte.txt" >> "$LOG" 2>&1 || true
else
    python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
        --quelle "$QUELLE_DATEN" \
        --ziel "$HOME/foto_sortierung" \
        --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl >> "$LOG" 2>&1 || true
fi

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
sag "Backend startet (PID $!) ..."

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
