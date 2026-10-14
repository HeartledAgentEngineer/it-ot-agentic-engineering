#!/data/data/com.termux/files/usr/bin/bash
#
# tls-umstellung.sh - laufenden Server von HTTP auf HTTPS umstellen (HTTPS-Plan H3b).
#
# WARUM es diese Datei gibt:
# Kommt das Serverzertifikat erst in der Start-Vorbereitung aufs Handy
# (termux/start-vorbereiten.sh), laeuft der Server schon - und zwar noch als
# reiner HTTP-Server auf 0.0.0.0, offen im WLAN. Die vier Startwege rufen diese
# Datei nach der Vorbereitung; sie steht EINMAL hier statt viermal kopiert.
#
# Ablauf:
#   1. ``backend-starten.sh --modus-pruefen``: 0 = passt -> nichts tun.
#   2. Bei 3: laeuft ueberhaupt ein Server (``backend-beenden.sh --laeuft-noch``)?
#      Nein -> nichts umzustellen, der regulaere Start folgt (Exit 0).
#   3. Schleifenschutz: Steht in backend/hermes_diag/tls_umstellung_gescheitert.txt
#      dieselbe sha256-Kombination von server.crt und ca.crt wie jetzt, war genau
#      dieses Zertifikatspaar schon einmal erfolglos -> KEIN neuer Versuch (nur
#      eine Logzeile). Neue Zertifikatsdateien geben wieder genau einen Versuch frei.
#   4. Logzeile "Umstellung HTTP -> HTTPS", ``backend-beenden.sh`` (genau einmal).
#   5. Ohne --nur-beenden: ``backend-starten.sh <Startschalter>``, dann auf
#      Bereitschaft warten (``--modus-pruefen`` wird 0). Wird es auch danach
#      nicht 0: KEIN zweiter Versuch, sondern die Warnungsdatei mit den
#      sha256-Werten (Exit 4).
#
# Aufruf:  tls-umstellung.sh [--nur-beenden] [Startschalter fuer backend-starten.sh ...]
#   --nur-beenden   fuer Aufrufer, die den Server gleich selbst starten (Widget,
#                   start-termux.sh, neu-start-nach-lauf.sh): nur beenden, nicht starten.
#   Startschalter  (--abloesen, --reload, --log DATEI) gehen unveraendert an
#                   backend-starten.sh.
#
# Exit: 0 = nichts getan (passt / kein Server / Schleifenschutz),
#       10 = umgestellt, Server laeuft im neuen Modus (oder bei --nur-beenden: beendet),
#       4  = Umstellung gescheitert (Warnungsdatei geschrieben, kein weiterer Versuch).
# Wartezeit auf Bereitschaft: UMSTELLUNG_WARTEN_S (Standard 90 Sekunden).

set -u

skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"
BACKEND="$(cd "$HIER/../backend" 2>/dev/null && pwd)"
STARTEN="$HIER/backend-starten.sh"
BEENDEN="$HIER/backend-beenden.sh"
TLS_ORDNER="${AGENT_TLS_ORDNER:-$HOME/.agent_tls}"
WARNUNG="$BACKEND/hermes_diag/tls_umstellung_gescheitert.txt"
WARTEN_S="${UMSTELLUNG_WARTEN_S:-90}"

NUR_BEENDEN=0
START_SCHALTER=()
for _arg in "$@"; do
    if [ "$_arg" = "--nur-beenden" ]; then
        NUR_BEENDEN=1
    else
        START_SCHALTER+=("$_arg")
    fi
done

log() { echo "Umstellung: $*"; }

sha256_von() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" 2>/dev/null | cut -d' ' -f1
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 -r "$1" 2>/dev/null | cut -d' ' -f1
    else
        echo "unbekannt"
    fi
}

SHA_CRT="$(sha256_von "$TLS_ORDNER/server.crt")"
SHA_CA="$(sha256_von "$TLS_ORDNER/ca.crt")"

# 1. Passt der laufende Modus schon?
bash "$STARTEN" --modus-pruefen >/dev/null 2>&1
_rc=$?
if [ "$_rc" -eq 0 ]; then
    exit 0
fi

# 2. Nichts laeuft -> nichts umzustellen; der regulaere Start nimmt gleich den richtigen Modus.
if ! bash "$BEENDEN" --laeuft-noch; then
    log "kein Server laeuft - der Start waehlt den Modus selbst."
    exit 0
fi

# 3. Schleifenschutz ueber Laeufe hinweg.
if [ -f "$WARNUNG" ] \
   && grep -qx "server.crt sha256=$SHA_CRT" "$WARNUNG" 2>/dev/null \
   && grep -qx "ca.crt sha256=$SHA_CA" "$WARNUNG" 2>/dev/null; then
    log "mit diesem Zertifikatspaar schon einmal gescheitert (siehe $WARNUNG) - kein neuer Versuch."
    exit 0
fi

# 4. Umstellen: genau einmal beenden.
log "Umstellung HTTP -> HTTPS (laufender Server passt nicht zum Zertifikatsstand)"
if ! bash "$BEENDEN"; then
    log "Beenden des alten Servers misslungen."
    UMSTELLUNG_GRUND="Beenden des alten Servers misslungen"
else
    if [ "$NUR_BEENDEN" = "1" ]; then
        log "alter Server beendet; der Aufrufer startet ihn gleich neu."
        exit 10
    fi
    bash "$STARTEN" ${START_SCHALTER[@]+"${START_SCHALTER[@]}"}
    UMSTELLUNG_GRUND="Server startete, antwortet aber nicht im TLS-Modus"
    # Pruefung vor jedem Warten UND nach dem letzten: der Server braucht einige
    # Sekunden (Vektordatei laden), die erste Abfrage kommt fast immer zu frueh.
    _i=0
    while :; do
        if bash "$STARTEN" --modus-pruefen >/dev/null 2>&1; then
            log "Server laeuft jetzt mit HTTPS (HTTP nur lokal)."
            exit 10
        fi
        [ "$_i" -ge "$WARTEN_S" ] && break
        _i=$((_i + 1))
        sleep 1
    done
fi

# 5. Gescheitert: kein zweiter Versuch, Warnung mit den Zertifikats-Pruefsummen.
if mkdir -p "$(dirname "$WARNUNG")" 2>/dev/null; then
    {
        echo "tls_umstellung_gescheitert $(date '+%Y-%m-%dT%H:%M:%S')"
        echo "grund: $UMSTELLUNG_GRUND"
        echo "server.crt sha256=$SHA_CRT"
        echo "ca.crt sha256=$SHA_CA"
    } > "$WARNUNG" 2>/dev/null
fi
log "FEHLGESCHLAGEN ($UMSTELLUNG_GRUND) - kein weiterer Versuch; Warnung: $WARNUNG"
exit 4
