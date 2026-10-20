#!/data/data/com.termux/files/usr/bin/bash
#
# Pruefstempel: Schnellpruefung statt voller sha256 bei jedem Start
# (20.10.2026). Wird NICHT einzeln aufgerufen, sondern per "." eingebunden von
#   termux/wissensdatei-uebernehmen.sh   und   termux/pcloud-uebernehmen.sh
#
# Anlass (gemessen 20.10.2026): Jedes Oeffnen der Handy-App stiess die
# Start-Vorbereitung an; darin rechneten beide Skripte bei JEDEM Lauf volle
# sha256 ueber Quelle UND Ziel (memory.db hat 230 MB), obwohl nichts geaendert
# war. Das lastete das Handy aus (App: "wird geladen ..."/"Server nicht
# erreichbar").
#
# Prinzip: Nach einer erfolgreichen Pruefung (Quelle = Ziel, entweder gleich
# befunden oder frisch kopiert) steht neben dem Ziel eine kleine Stempeldatei
# "<ziel>.pruefstempel" mit drei Zeilen:
#   1. Stempelzeile: Quellpfad | Quellgroesse Quell-mtime | Zielgroesse Ziel-mtime
#   2. die sha256, die damals gepruft wurde
#   3. Zielgroesse Ziel-mtime (damit das Ziel allein wiedererkannt werden kann)
# Beim naechsten Lauf gilt die Schnellpruefung, wenn
#   * die Stempeldatei existiert, lesbar und vollstaendig ist,
#   * ihre erste Zeile EXAKT der aktuellen Stempelzeile entspricht und
#   * sie juenger ist als PRUEFSTEMPEL_MAX_ALTER_S (Standard 86400 = 1 Tag;
#     danach wieder volle Pruefung).
# JEDE Unklarheit (Stempel fehlt/kaputt, stat scheitert, Ziel fehlt, Uhr
# zurueckgestellt) heisst: volle Pruefung wie bisher.
#
# Funktionen:
#   stempel_zeile    <quelle> <ziel>                 gibt die Stempelzeile aus
#   stempel_passt    <stempeldatei> <quelle> <ziel>  Exit 0 = Schnellpruefung ok
#   stempel_ziel_sha <stempeldatei> <ziel>           gibt die gestempelte sha256
#                                                    aus, wenn das ZIEL (Groesse +
#                                                    mtime) und das Alter passen;
#                                                    sonst Exit 1 (nur Ziel-Teil,
#                                                    fuer Quellen, die bei jedem
#                                                    Lauf neu entstehen)
#   stempel_schreiben <stempeldatei> <quelle> <ziel> <sha256>
#                                                    schreibt den Stempel atomar
#                                                    (.teil, dann mv); Fehler sind
#                                                    harmlos, Exit immer 0
# Umgehung: PRUEFSTEMPEL_AUS=1 -> stempel_passt/stempel_ziel_sha liefern immer 1.
#
# Nur lokale Dateioperationen (stat, date, printf, mv). Es wird nie etwas
# geloescht. Reine Funktionsdefinitionen - beim Einbinden passiert nichts.

_stempel_stat() { stat -c '%s %Y' -- "$1" 2>/dev/null; }

stempel_zeile() {
    local q z
    q="$(_stempel_stat "$1")" || return 1
    z="$(_stempel_stat "$2")" || return 1
    [ -n "$q" ] && [ -n "$z" ] || return 1
    printf '%s|%s|%s' "$1" "$q" "$z"
}

_stempel_jung_genug() {
    local max m jetzt
    max="${PRUEFSTEMPEL_MAX_ALTER_S:-86400}"
    case "$max" in ''|*[!0-9]*) max=86400 ;; esac
    m="$(stat -c %Y -- "$1" 2>/dev/null)" || return 1
    jetzt="$(date +%s 2>/dev/null)" || return 1
    [ -n "$m" ] && [ -n "$jetzt" ] || return 1
    case "$m" in *[!0-9]*) return 1 ;; esac
    case "$jetzt" in *[!0-9]*) return 1 ;; esac
    [ "$jetzt" -ge "$m" ] || return 1
    [ $((jetzt - m)) -lt "$max" ]
}

_stempel_sha_gueltig() {
    case "$1" in *[!0-9a-f]*) return 1 ;; esac
    [ "${#1}" -eq 64 ]
}

stempel_passt() {
    [ "${PRUEFSTEMPEL_AUS:-0}" = "1" ] && return 1
    local datei="$1" erste zweite aktuell
    [ -f "$datei" ] && [ -r "$datei" ] || return 1
    { IFS= read -r erste && IFS= read -r zweite; } < "$datei" 2>/dev/null || return 1
    [ -n "$erste" ] || return 1
    _stempel_sha_gueltig "$zweite" || return 1
    aktuell="$(stempel_zeile "$2" "$3")" || return 1
    [ "$erste" = "$aktuell" ] || return 1
    _stempel_jung_genug "$datei"
}

stempel_ziel_sha() {
    [ "${PRUEFSTEMPEL_AUS:-0}" = "1" ] && return 1
    local datei="$1" erste zweite dritte z
    [ -f "$datei" ] && [ -r "$datei" ] || return 1
    { IFS= read -r erste && IFS= read -r zweite && IFS= read -r dritte; } < "$datei" 2>/dev/null || return 1
    _stempel_sha_gueltig "$zweite" || return 1
    [ -n "$dritte" ] || return 1
    z="$(_stempel_stat "$2")" || return 1
    [ -n "$z" ] && [ "$dritte" = "$z" ] || return 1
    _stempel_jung_genug "$datei" || return 1
    printf '%s' "$zweite"
}

stempel_schreiben() {
    local datei="$1" zeile z
    _stempel_sha_gueltig "${4:-}" || return 0
    zeile="$(stempel_zeile "$2" "$3")" || return 0
    z="$(_stempel_stat "$3")" || return 0
    { printf '%s\n%s\n%s\n' "$zeile" "$4" "$z" > "$datei.teil"; } 2>/dev/null || return 0
    mv -f -- "$datei.teil" "$datei" 2>/dev/null || return 0
    return 0
}
