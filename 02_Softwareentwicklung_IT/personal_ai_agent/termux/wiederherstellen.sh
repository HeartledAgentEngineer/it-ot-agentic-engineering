#!/data/data/com.termux/files/usr/bin/bash
#
# Termux nach dem Umzug (Play -> F-Droid) aus der Sicherung wiederherstellen (10.10.2026).
#
# Gegenstueck zu termux/sicherung.sh. Die Sicherung ist an Sebastians Hauptschluessel
# verschluesselt, dessen privater Teil nur am PC liegt. Er kommt NIE aufs Handy. Darum:
#
#   1. vorbereiten  (Handy) - erzeugt einen Einmal-Schluessel im neuen Termux-Heimordner
#                    und legt nur dessen OEFFENTLICHEN Teil in den Download-Ordner.
#   2. am PC: tools/handy/wiederherstellung_senden.py entschluesselt die Sicherung und
#                    verschluesselt sie im selben Strom neu an den Einmal-Schluessel.
#                    Auf dem gemeinsamen Speicher liegt nie Klartext.
#   3. einspielen   (Handy) - Pakete neu installieren, Heimordner auspacken (vorhandene
#                    Dateien bleiben unberuehrt), Linux-Umgebung zurueckspielen,
#                    Python-Pakete des Agenten installieren.
#
# Regeln: nichts wird ueberschrieben oder geloescht. tar laeuft mit --skip-old-files;
# eine schon vorhandene Linux-Umgebung wird NICHT angefasst ("proot-distro restore"
# wuerde sie sonst ohne Rueckfrage leeren).
#
# Aufruf in Termux (vorher: termux-setup-storage, pkg install age):
#   bash /sdcard/Download/termux-sicherung/wiederherstellen.sh vorbereiten
#   bash /sdcard/Download/termux-sicherung/wiederherstellen.sh einspielen [ordner]
#
# Exit: 0 fertig · 1 Aufruf falsch · 2 Schluessel fehlt · 3 Werkzeug fehlt ·
#       4 Sendung fehlt/unvollstaendig · 5 Pruefsumme falsch · 6 Auspacken scheiterte

set -u -o pipefail

BASIS="${TERMUX_BASIS:-/data/data/com.termux/files}"
HEIM="${HOME:-$BASIS/home}"
ABLAGE="${WIEDERHERSTELLUNG_ABLAGE:-/sdcard/Download/termux-sicherung}"
SCHLUESSEL="$HEIM/.wiederherstellung_einmal.key"
OEFFENTLICH="$ABLAGE/einmal_empfaenger.txt"
PROJEKT_REL="it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent"
LAGER="$BASIS/usr/var/lib/proot-distro"

meldung() { printf '%s\n' "$*"; }

vorbereiten() {
    command -v age-keygen >/dev/null 2>&1 || { meldung "Abbruch: age fehlt. Erst: pkg install age"; exit 3; }
    mkdir -p "$ABLAGE" 2>/dev/null || { meldung "Abbruch: $ABLAGE nicht erreichbar. Erst: termux-setup-storage"; exit 3; }
    if [ ! -f "$SCHLUESSEL" ]; then
        ( umask 077; age-keygen -o "$SCHLUESSEL" 2>/dev/null ) || { meldung "Abbruch: Schluessel nicht erzeugbar."; exit 2; }
    fi
    age-keygen -y "$SCHLUESSEL" > "$OEFFENTLICH" || { meldung "Abbruch: oeffentlicher Schluessel nicht ablegbar."; exit 2; }
    meldung "Einmal-Schluessel bereit: $(cut -c1-12 "$OEFFENTLICH")..."
    meldung "Jetzt am PC: python tools/handy/wiederherstellung_senden.py"
}

# Neueste vollstaendige Sendung finden (Ordner mit FERTIG).
sendung_finden() {
    local ordner
    for ordner in $(ls -d "$ABLAGE"/wiederherstellung_* 2>/dev/null | sort -r); do
        [ -f "$ordner/FERTIG" ] && { printf '%s\n' "$ordner"; return 0; }
    done
    return 1
}

pruefsummen() {
    local ordner="$1" zeile name soll ist
    while read -r zeile; do
        name="${zeile%% *}"
        soll="$(printf '%s\n' "$zeile" | grep -o 'sha256=[0-9a-f]*' | cut -d= -f2)"
        [ -n "$soll" ] || continue
        [ -f "$ordner/$name" ] || { meldung "Abbruch: $name fehlt in der Sendung."; exit 4; }
        ist="$(sha256sum "$ordner/$name" | cut -d' ' -f1)"
        [ "$ist" = "$soll" ] || { meldung "Abbruch: Pruefsumme von $name falsch."; exit 5; }
        meldung "  $name: Pruefsumme ok"
    done < "$ordner/MANIFEST.txt"
}

pakete() {
    local liste="$1/pakete_manuell.txt" paket fehlen=""
    [ -f "$liste" ] || { meldung "  (keine Paketliste - uebersprungen)"; return 0; }
    meldung "Pakete installieren ($(wc -l < "$liste" | tr -d ' ') Stueck, dauert) ..."
    pkg update -y >/dev/null 2>&1 || true
    while read -r paket; do
        [ -n "$paket" ] || continue
        dpkg -s "$paket" >/dev/null 2>&1 && continue
        pkg install -y "$paket" >/dev/null 2>&1 || fehlen="$fehlen $paket"
    done < "$liste"
    # Fertige Termux-Pakete statt Kompilieren mit pip
    for paket in python-numpy python-pillow; do
        dpkg -s "$paket" >/dev/null 2>&1 || pkg install -y "$paket" >/dev/null 2>&1 || fehlen="$fehlen $paket"
    done
    [ -z "$fehlen" ] && meldung "  alle Pakete da" || meldung "  nicht installierbar:$fehlen"
}

heim_auspacken() {
    local datei="$1/home.tar.age"
    [ -f "$datei" ] || { meldung "  (kein home.tar.age)"; return 0; }
    meldung "Heimordner auspacken (vorhandene Dateien bleiben) ..."
    age -d -i "$SCHLUESSEL" "$datei" | tar -C "$BASIS" -xpf - --skip-old-files
    local stufen=("${PIPESTATUS[@]}")
    if [ "${stufen[0]}" -ne 0 ] || [ "${stufen[1]}" -ge 2 ]; then
        meldung "Abbruch: Heimordner scheiterte (age ${stufen[0]}, tar ${stufen[1]})."
        exit 6
    fi
    meldung "  fertig"
}

distros_einspielen() {
    local datei name
    for datei in "$1"/distro_*.tar.age; do
        [ -f "$datei" ] || continue
        name="$(basename "$datei" .tar.age)"; name="${name#distro_}"
        if [ -d "$LAGER/containers/$name" ] || [ -d "$LAGER/installed-rootfs/$name" ]; then
            meldung "  Linux-Umgebung $name gibt es schon - bleibt unberuehrt."
            continue
        fi
        command -v proot-distro >/dev/null 2>&1 || { meldung "Abbruch: proot-distro fehlt (pkg install proot-distro)."; exit 3; }
        meldung "Linux-Umgebung $name zurueckspielen ..."
        age -d -i "$SCHLUESSEL" "$datei" | proot-distro restore
        local stufen=("${PIPESTATUS[@]}")
        if [ "${stufen[0]}" -ne 0 ] || [ "${stufen[1]}" -ne 0 ]; then
            meldung "Abbruch: $name scheiterte (age ${stufen[0]}, proot-distro ${stufen[1]})."
            exit 6
        fi
        meldung "  fertig"
    done
}

python_pakete() {
    local sendung="$1" anforderung="$HEIM/$PROJEKT_REL/backend/requirements.txt"
    command -v pip >/dev/null 2>&1 || { meldung "  (pip fehlt - Python-Pakete uebersprungen)"; return 0; }
    meldung "Python-Pakete des Agenten installieren ..."
    if [ -f "$anforderung" ]; then
        pip install -r "$anforderung" >/dev/null 2>&1 && meldung "  Agent: fertig" \
            || meldung "  Agent: nicht alles installierbar - pip install -r $anforderung von Hand"
    fi
    # Alte Liste (pip freeze vor der Deinstallation): fehlende Pakete einzeln nachziehen
    local alt="$sendung/pip_alt.txt"
    [ -f "$alt" ] || alt="$ABLAGE/pip_alt.txt"
    if [ -f "$alt" ]; then
        local zeile fehlen=""
        while read -r zeile; do
            case "$zeile" in ""|\#*|-e*|*" @ "*) continue ;; esac
            pip show "${zeile%%==*}" >/dev/null 2>&1 && continue
            pip install "$zeile" >/dev/null 2>&1 || pip install "${zeile%%==*}" >/dev/null 2>&1 \
                || fehlen="$fehlen ${zeile%%==*}"
        done < "$alt"
        [ -z "$fehlen" ] && meldung "  alte Liste: alles da" || meldung "  alte Liste, nicht installierbar:$fehlen"
    fi
}

einspielen() {
    local sendung="${1:-}"
    [ -n "$sendung" ] || sendung="$(sendung_finden)" || {
        meldung "Abbruch: keine vollstaendige Sendung in $ABLAGE (Ordner wiederherstellung_* mit FERTIG)."
        exit 4
    }
    [ -f "$sendung/FERTIG" ] || { meldung "Abbruch: $sendung ist unvollstaendig (FERTIG fehlt)."; exit 4; }
    [ -f "$SCHLUESSEL" ] || { meldung "Abbruch: Einmal-Schluessel fehlt. Erst: ... wiederherstellen.sh vorbereiten"; exit 2; }
    command -v age >/dev/null 2>&1 || { meldung "Abbruch: age fehlt. Erst: pkg install age"; exit 3; }
    meldung "Wiederherstellung aus $sendung"
    pruefsummen "$sendung"
    [ "${WIEDERHERSTELLUNG_OHNE_PAKETE:-0}" = "1" ] || pakete "$sendung"
    heim_auspacken "$sendung"
    distros_einspielen "$sendung"
    [ "${WIEDERHERSTELLUNG_OHNE_PAKETE:-0}" = "1" ] || python_pakete "$sendung"
    meldung ""
    meldung "Fertig. Naechste Schritte:"
    meldung "  1. bash ~/$PROJEKT_REL/termux/einrichten.sh   (Widget-Knopf neu verknuepfen)"
    meldung "  2. Widget 'agent' auf den Startbildschirm legen und antippen."
}

case "${1:-}" in
    vorbereiten) vorbereiten ;;
    einspielen) shift; einspielen "${1:-}" ;;
    *) meldung "Aufruf: bash $0 vorbereiten | einspielen [ordner]"; exit 1 ;;
esac
