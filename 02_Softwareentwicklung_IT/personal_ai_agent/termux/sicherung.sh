#!/data/data/com.termux/files/usr/bin/bash
#
# Verschluesselte Komplettsicherung von Termux (08.10.2026).
#
# Anlass: Umzug von der Google-Play-Fassung auf die F-Droid-Fassung. Die beiden
# sind unterschiedlich signiert, die alte muss deinstalliert werden, und dabei
# loescht Android ALLE Termux-Daten. Vorher muss eine gepruefte Sicherung da sein.
#
# Was gesichert wird (je ein verschluesselter Teil):
#   home.tar.age  - der ganze Termux-Heimordner (Repo mit .env, Datenbanken,
#                   foto_sortierung, Erinnerungen, Verlaeufe, Hermes, Widgets)
#   distro_<name>.tar.age - je Linux-Umgebung (proot-distro, z. B. debian mit
#                   der Gesichtserkennung), gesichert mit "proot-distro backup".
#                   Die Programme in usr/ selbst werden neu installiert
#                   (pakete_manuell.txt), nicht zurueckkopiert.
#   pakete_manuell.txt - Liste der von Hand installierten Pakete (unverschluesselt,
#                   enthaelt nur Paketnamen)
#   MANIFEST.txt  - Groesse, sha256 und Eintragszahl je Teil (fuer die Pruefung am PC)
#   FERTIG        - wird als Letztes geschrieben; fehlt sie, ist die Sicherung unvollstaendig
#
# Verschluesselt wird mit age an einen oeffentlichen Schluessel (age1...). Der
# private Schluessel liegt nur am PC und in Bitwarden - am Handy kann die
# Sicherung also niemand lesen, auch keine andere App im Download-Ordner.
#
# Regeln: liest nur und schreibt nur in einen NEUEN Ordner. Gibt es den Zielordner
# schon, bricht das Skript ab (nie ueberschreiben). Nichts wird geloescht ausser
# der eigenen Zaehl-Zwischendatei.
#
# Aufruf in Termux (vorher: pkg install age, termux-setup-storage):
#   bash ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/termux/sicherung.sh
#
# Exit: 0 fertig · 2 Schluessel fehlt/ungueltig · 3 age/tar fehlt ·
#       4 Zielordner gibt es schon · 5 Zielordner nicht anlegbar · 6 Sichern scheiterte

set -u -o pipefail

BASIS="${TERMUX_BASIS:-/data/data/com.termux/files}"
ZIEL_WURZEL="${SICHERUNG_ZIEL:-/sdcard/Download/termux-sicherung}"
STAND="${SICHERUNG_STAND:-$(date +%Y-%m-%d_%H%M)}"
ZIEL="$ZIEL_WURZEL/$STAND"
PORT="${PORT:-8080}"
ZWISCHEN="${TMPDIR:-$BASIS/usr/tmp}"

meldung() { printf '%s\n' "$*"; }

# ── Schluessel finden ─────────────────────────────────────────────────────
empfaenger_finden() {
    for kandidat in "${SICHERUNG_EMPFAENGER:-}" "$HOME/.sicherung_empfaenger.txt" \
                    "/sdcard/Download/sicherung_empfaenger.txt"; do
        [ -n "$kandidat" ] && [ -f "$kandidat" ] && { printf '%s\n' "$kandidat"; return 0; }
    done
    return 1
}

EMPFAENGER_DATEI="$(empfaenger_finden)" || {
    meldung "Abbruch: oeffentlicher Schluessel fehlt."
    meldung "  Erwartet in ~/.sicherung_empfaenger.txt oder /sdcard/Download/sicherung_empfaenger.txt"
    meldung "  (eine Zeile, beginnt mit age1...). Erzeugt wird er am PC mit age-keygen."
    exit 2
}
EMPFAENGER="$(grep -m1 -o 'age1[0-9a-z]*' "$EMPFAENGER_DATEI" || true)"
if [ -z "$EMPFAENGER" ]; then
    meldung "Abbruch: in $EMPFAENGER_DATEI steht kein Schluessel der Form age1..."
    exit 2
fi

# ── Werkzeuge ─────────────────────────────────────────────────────────────
for werkzeug in age tar sha256sum; do
    command -v "$werkzeug" >/dev/null 2>&1 || {
        meldung "Abbruch: '$werkzeug' fehlt. In Termux: pkg install age tar coreutils"
        exit 3
    }
done

# ── Ziel: immer neu, nie ueberschreiben ───────────────────────────────────
if [ -e "$ZIEL" ]; then
    meldung "Abbruch: $ZIEL gibt es schon. Eine vorhandene Sicherung wird nie ueberschrieben."
    exit 4
fi
mkdir -p "$ZIEL" 2>/dev/null || {
    meldung "Abbruch: $ZIEL laesst sich nicht anlegen. Einmal termux-setup-storage ausfuehren."
    exit 5
}
mkdir -p "$ZWISCHEN" 2>/dev/null || ZWISCHEN="$ZIEL"

# ── Laeuft der Agent? Dann schreibt er evtl. gerade in Datenbanken ────────
if command -v curl >/dev/null 2>&1 && \
   curl -s --max-time 2 "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
    meldung "Hinweis: Der Agent laeuft gerade. Fuer eine saubere Sicherung besser vorher beenden"
    meldung "         (Termux-Fenster mit dem Server schliessen). Es geht trotzdem weiter."
fi

meldung "Sicherung nach $ZIEL"
meldung "Schluessel: ${EMPFAENGER:0:12}... (aus $EMPFAENGER_DATEI)"

# ── Paketliste (nur Namen) ────────────────────────────────────────────────
if command -v apt-mark >/dev/null 2>&1; then
    apt-mark showmanual > "$ZIEL/pakete_manuell.txt" 2>/dev/null || true
else
    meldung "  (apt-mark fehlt - keine Paketliste)"
fi
# Python-Pakete liegen in usr/ (nicht gesichert): Liste fuer die Wiederherstellung (10.10.2026)
if command -v pip >/dev/null 2>&1; then
    pip freeze > "$ZIEL/pip_alt.txt" 2>/dev/null || true
fi

# ── Manifest-Zeile: Groesse, sha256, Eintraege (-1 = nicht gezaehlt) ───────
manifest_eintrag() {
    local datei="$1" eintraege="$2" groesse summe
    groesse="$(wc -c < "$datei" | tr -d ' ')"
    summe="$(sha256sum "$datei" | cut -d' ' -f1)"
    printf '%s groesse=%s eintraege=%s sha256=%s\n' \
        "$(basename "$datei")" "$groesse" "$eintraege" "$summe" >> "$ZIEL/MANIFEST.txt"
    meldung "    fertig: $([ "$eintraege" -ge 0 ] && echo "$eintraege Eintraege, ")$(( groesse / 1048576 )) MB"
}

# Erste Fehlerzeilen zeigen (vorher wurden sie verschluckt - 08.10.2026, Lauf 22:35).
fehler_zeigen() {
    [ -s "$1" ] || return 0
    meldung "    Meldungen ($(wc -l < "$1" | tr -d ' ') Zeilen, die ersten 5):"
    head -5 "$1" | sed 's/^/      /'
}

# ── Heimordner sichern: tar | age ─────────────────────────────────────────
# tar meldet Exit 1, wenn sich eine Datei waehrend des Lesens aendert (z. B. ein
# Log). Das ist eine Warnung, kein Abbruch; Exit >= 2 ist ein echter Fehler.
teil_sichern() {
    local name="$1"; shift
    local ausgabe="$ZIEL/$name.tar.age"
    local liste="$ZWISCHEN/.sicherung_liste_$name.$$"
    local fehler="$ZWISCHEN/.sicherung_fehler_$name.$$"
    meldung "  $name: wird gesichert ..."
    tar -C "$BASIS" -cf - --index-file="$liste" -v "$@" "$name" 2>"$fehler" \
        | age -r "$EMPFAENGER" -o "$ausgabe"
    local stufen=("${PIPESTATUS[@]}")
    local eintraege=0
    [ -f "$liste" ] && eintraege="$(wc -l < "$liste" | tr -d ' ')"
    if [ "${stufen[0]}" -ge 2 ] || [ "${stufen[1]}" -ne 0 ] || [ ! -s "$ausgabe" ]; then
        meldung "Abbruch: $name scheiterte (tar ${stufen[0]}, age ${stufen[1]})."
        fehler_zeigen "$fehler"
        rm -f "$liste" "$fehler"
        exit 6
    fi
    if [ "${stufen[0]}" -eq 1 ]; then
        meldung "    Hinweis: Dateien haben sich beim Lesen geaendert (Logs?)."
        fehler_zeigen "$fehler"
    fi
    rm -f "$liste" "$fehler"
    manifest_eintrag "$ausgabe" "$eintraege"
}

# ── Linux-Umgebungen (proot-distro) sichern ───────────────────────────────
# Die Programme in usr/ werden NICHT gesichert: Die Wiederherstellung installiert
# sie neu aus pakete_manuell.txt (Play- und F-Droid-Fassung koennen sich darin
# unterscheiden). Wertvoll ist nur die Debian-Umgebung der Gesichtserkennung
# (/root/facy_venv mit OpenCV), die in keinem Einrichtungsskript steht. Ein
# einfaches tar darf darin nicht alles lesen (Lauf 22:35: tar Exit 2); deshalb
# sichert proot-distro selbst, mit seinen Schein-root-Rechten.
# Ablage (README proot-distro, 08.10.2026): neu containers/<name>/rootfs/, alt
# installed-rootfs/<name>/ (wird beim naechsten login migriert). Lauf 23:00 fand
# nur den alten Pfad und meldete faelschlich "keine Linux-Umgebung".
distro_namen() {
    local lager="$BASIS/usr/var/lib/proot-distro" ordner
    for ordner in "$lager"/containers/*/rootfs/; do
        [ -d "$ordner" ] && basename "$(dirname "$ordner")"
    done
    for ordner in "$lager"/installed-rootfs/*/; do
        [ -d "$ordner" ] && basename "$ordner"
    done
}

distros_sichern() {
    local namen
    namen="$(distro_namen | sort -u)"
    if [ -z "$namen" ]; then
        meldung "  Keine Linux-Umgebung (proot-distro) gefunden"
        meldung "  (gesucht: usr/var/lib/proot-distro/containers/*/rootfs und installed-rootfs/*)."
        return 0
    fi
    if ! command -v proot-distro >/dev/null 2>&1; then
        meldung "Abbruch: Linux-Umgebung vorhanden, aber proot-distro fehlt."
        exit 6
    fi
    local name ausgabe fehler
    for name in $namen; do
        ausgabe="$ZIEL/distro_$name.tar.age"
        fehler="$ZWISCHEN/.sicherung_fehler_distro.$$"
        meldung "  Linux-Umgebung $name: wird gesichert ..."
        proot-distro backup "$name" 2>"$fehler" | age -r "$EMPFAENGER" -o "$ausgabe"
        local stufen=("${PIPESTATUS[@]}")
        if [ "${stufen[0]}" -ne 0 ] || [ "${stufen[1]}" -ne 0 ] || [ ! -s "$ausgabe" ]; then
            meldung "Abbruch: $name scheiterte (proot-distro ${stufen[0]}, age ${stufen[1]})."
            fehler_zeigen "$fehler"
            rm -f "$fehler"
            exit 6
        fi
        rm -f "$fehler"
        manifest_eintrag "$ausgabe" -1
    done
}

printf 'stand=%s\nbasis=%s\n' "$STAND" "$BASIS" > "$ZIEL/MANIFEST.txt"
teil_sichern home --exclude=home/storage --exclude=home/.cache
distros_sichern
date '+%Y-%m-%d %H:%M:%S' > "$ZIEL/FERTIG"

meldung ""
meldung "Fertig. Naechster Schritt am PC: Ordner per Kabel holen und pruefen"
meldung "  (tools/handy/sicherung_pruefen.py). Erst nach gruener Pruefung deinstallieren."
exit 0
