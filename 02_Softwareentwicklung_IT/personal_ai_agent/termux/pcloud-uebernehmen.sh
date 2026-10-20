#!/data/data/com.termux/files/usr/bin/bash
#
# Kabellose Uebergabe (Handy-Seite): Ergebnisse aus dem pCloud-Ordner beim
# Start uebernehmen (10.10.2026).
#
# Anlass (Sebastians ausdrueckliche Entscheidung, 10.10.2026): Die Uebergabe
# der Ergebnisse an das Handy lief bisher NUR ueber das Kabel (PC legt Dateien
# in den freigegebenen Download-Ordner, tools/handy/uebergabe_uebernehmen.py
# holt sie). Ohne Kabel blieb das Handy auf dem alten Stand. Jetzt geht derselbe
# Weg wahlweise KABELLOS: Der PC laedt die Dateien mit
# tools/pcloud/uebergabe_hochladen.py in den pCloud-Ordner /Agent/uebergabe,
# dieses Skript holt sie beim Start. Ausdruecklich freigegeben sind auch die
# Gesichts-Vektoren und der Gesichtskatalog (eigenes Geraet, eigenes pCloud-
# Konto, kein fremder Anbieter — siehe Projekt-CLAUDE.md, Datenschutz).
#
# Aufbau (Shell steuert, Python spricht mit pCloud — wie ueberall sonst):
#   1. Der Netz-Teil (tools/handy/pcloud_dateien_holen.py) holt die Dateien in
#      einen Staging-Ordner unter dem Heimordner und schreibt die geholten
#      Namen in eine Liste. Fehlt der Token / kein Netz / leerer Ordner -> klare
#      Zeile, es geht nichts kaputt.
#   2. Fuer JEDEN geholten Namen uebernimmt dieses Skript die Datei an ihren
#      Platz, nach dem Muster von termux/wissensdatei-uebernehmen.sh:
#        * gleiche sha256 (Quelle = Ziel): NICHTS passiert (idempotent).
#        * sonst: die vorhandene Ziel-Fassung ZUERST als <ziel>.vor_<datum>
#          sichern (bei Kollision _2, _3, …), dann kopieren — erst als .teil,
#          nach bestandener Pruefsumme an ihren Platz. Es entsteht nie eine
#          halbe Datei.
#      Es wird NIE etwas geloescht; die Staging-Datei bleibt liegen.
#   3. Jede Aktion wird protokolliert (Zeit, Name, Groesse, sha256,
#      kopiert/uebersprungen) im hermes_diag-Ordner des freigegebenen
#      Download-Ordners, von wo der PC ueber das Kabel nachsehen kann.
#   4. Fehlertolerant: fehlender Token, kein Netz, leere Liste, nicht lesbare
#      Pruefsumme und misslungene Kopien schreiben eine klare Zeile und lassen
#      den Start normal weiterlaufen.
#   5. Schnellpruefung mit Pruefstempel (20.10.2026, wie bei
#      termux/wissensdatei-uebernehmen.sh): Anlass war, dass bei JEDEM Oeffnen
#      der App fuer jede Datei volle sha256 ueber Quelle UND Ziel gerechnet
#      wurde, auch ohne Aenderung - das lastete das Handy aus. Jetzt steht nach
#      erfolgreichem Vergleich ("gleich") und nach erfolgreicher Uebernahme neben
#      jedem Ziel <ziel>.pruefstempel (Hilfsdatei termux/pruefstempel.sh).
#      Stimmen beim naechsten Lauf Groesse und mtime von Quelle UND Ziel exakt
#      und ist der Stempel juenger als PRUEFSTEMPEL_MAX_ALTER_S (Standard 86400 s),
#      wird fuer diese Datei KEINE Pruefsumme gerechnet (Protokollzeile
#      "PCLOUD-Uebergabe <NAME> uebersprungen (Groesse und Zeit unveraendert seit
#      letzter Pruefung, keine Pruefsumme)"). Jede Unklarheit = volle Pruefung
#      wie bisher; Sicherung/.teil/Pruefsumme-Schutz unveraendert. Umgehung:
#      PRUEFSTEMPEL_AUS=1. Hinweis: Der Netz-Teil (Schritt 1) legt die Staging-
#      Dateien bei jedem Lauf NEU an (neue mtime der Quelle); dann passt der
#      volle Stempel nicht, aber die Pruefsumme des unveraenderten ZIELS wird
#      aus dem Stempel wiederverwendet (stempel_ziel_sha: Ziel-Groesse + mtime
#      + Alter muessen passen), es wird nur die (kleinere) Quelle gerechnet.
#      Grenze: gleiche Groesse + gleiche mtime-Sekunde bei anderem Inhalt faellt
#      bis zur Tagesgrenze nicht auf.
#
# Aufruf:  bash termux/pcloud-uebernehmen.sh [projektordner]
#   Ueberschreibbar (fuer Tests/andere Ablagen; auf dem Handy nicht noetig):
#     PCLOUD_UEBERGABE_ZIEL      Zielordner  (Standard: $HOME/foto_sortierung —
#                                dort lesen die Dienste die Ergebnisdateien, wie
#                                beim Kabelweg tools/handy/uebergabe_uebernehmen.py)
#     PCLOUD_UEBERGABE_STAGING   Staging     (Standard: $HOME/.cache/pcloud_uebergabe)
#     PCLOUD_UEBERGABE_LISTE     Namensliste (Standard: <Staging>/liste.txt)
#     PCLOUD_UEBERGABE_PROTOKOLL Protokoll   (Standard: <Download>/hermes_diag/
#                                pcloud_uebernahme.log, Rueckfall $HOME/...)
#     PCLOUD_UEBERGABE_ENV       .env mit Token/Host (Standard: <Projekt>/backend/.env)
# Exit: IMMER 0 — dieses Skript darf den Start NIEMALS abbrechen (der Aufrufer
#       sichert zusaetzlich mit "|| true" ab).

set -u

HIER="$(cd "$(dirname "$0")" && pwd)"
PROJEKT="${1:-$(cd "$HIER/.." && pwd)}"

# Pruefstempel-Hilfsfunktionen (Schnellpruefung). Fehlt die Hilfsdatei, gibt es
# nur Ersatzfunktionen: nie Schnellpruefung, immer volle Pruefung wie bisher.
if [ -f "$HIER/pruefstempel.sh" ]; then
    . "$HIER/pruefstempel.sh"
fi
if ! command -v stempel_passt >/dev/null 2>&1; then
    stempel_passt() { return 1; }
    stempel_ziel_sha() { return 1; }
    stempel_schreiben() { return 0; }
fi

STAGING="${PCLOUD_UEBERGABE_STAGING:-$HOME/.cache/pcloud_uebergabe}"
ZIEL_ORDNER="${PCLOUD_UEBERGABE_ZIEL:-$HOME/foto_sortierung}"
LISTE="${PCLOUD_UEBERGABE_LISTE:-$STAGING/liste.txt}"
ENV_DATEI="${PCLOUD_UEBERGABE_ENV:-$PROJEKT/backend/.env}"

# ── Protokoll-Ort bestimmen (gleiches Muster wie die uebrigen Uebernahmen) ────
# Der Termux-Heimordner ist ueber das Kabel NICHT lesbar, der freigegebene
# Download-Ordner schon. Dort liegt das Protokoll.
if [ -z "${PCLOUD_UEBERGABE_PROTOKOLL:-}" ]; then
    BASIS="$HOME/storage/downloads"
    [ -d "$BASIS" ] || BASIS="/sdcard/Download"
    PCLOUD_UEBERGABE_PROTOKOLL="$BASIS/hermes_diag/pcloud_uebernahme.log"
fi

_protokoll_vorbereiten() { mkdir -p "$(dirname "$PCLOUD_UEBERGABE_PROTOKOLL")" 2>/dev/null; }
if ! _protokoll_vorbereiten; then
    PCLOUD_UEBERGABE_PROTOKOLL="$HOME/pcloud_uebernahme.log"
    _protokoll_vorbereiten || PCLOUD_UEBERGABE_PROTOKOLL=""
fi

protokoll() {
    [ -n "$PCLOUD_UEBERGABE_PROTOKOLL" ] || return 0
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$PCLOUD_UEBERGABE_PROTOKOLL" 2>/dev/null
    return 0
}

# Protokoll kurz halten (Muster agent-ensure.sh): ab mehr als 200 KB bleiben die
# letzten 500 Zeilen. Geloescht wird nichts, nur gekuerzt.
if [ -n "$PCLOUD_UEBERGABE_PROTOKOLL" ] && [ -f "$PCLOUD_UEBERGABE_PROTOKOLL" ]; then
    _kb="$(wc -c < "$PCLOUD_UEBERGABE_PROTOKOLL" 2>/dev/null || echo 0)"
    if [ "${_kb:-0}" -gt 204800 ]; then
        tail -n 500 "$PCLOUD_UEBERGABE_PROTOKOLL" > "$PCLOUD_UEBERGABE_PROTOKOLL.neu" 2>/dev/null \
            && mv -f "$PCLOUD_UEBERGABE_PROTOKOLL.neu" "$PCLOUD_UEBERGABE_PROTOKOLL" 2>/dev/null
    fi
fi

# ── 1. Netz-Teil: Dateien aus der pCloud in das Staging holen ────────────────
mkdir -p "$STAGING" 2>/dev/null || true
if ! command -v sha256sum >/dev/null 2>&1; then
    protokoll "PCLOUD-Uebergabe FEHLER: sha256sum fehlt - nichts uebernommen, Start laeuft weiter."
    exit 0
fi

HOLER="$PROJEKT/tools/handy/pcloud_dateien_holen.py"
if [ ! -f "$HOLER" ]; then
    protokoll "PCLOUD-Uebergabe: $HOLER fehlt - nichts geholt, Start laeuft weiter."
    exit 0
fi
# "|| true" doppelt: der Holer beendet sich zwar immer mit 0, aber ein fehlendes
# python oder ein abgebrochener Lauf darf den Start trotzdem nicht anhalten.
python "$HOLER" --env "$ENV_DATEI" --ziel "$STAGING" --liste "$LISTE" 2>&1 \
    | while IFS= read -r _zeile; do echo "$_zeile"; protokoll "$_zeile"; done || true

# ── 2. Liste pruefen ────────────────────────────────────────────────────────
if [ ! -f "$LISTE" ]; then
    protokoll "PCLOUD-Uebergabe: keine Liste ($LISTE) - nichts uebernommen, Start laeuft weiter."
    exit 0
fi

sha256_von() { sha256sum -- "$1" 2>/dev/null | cut -d' ' -f1; }
groesse_von() { stat -c %s -- "$1" 2>/dev/null || echo '?'; }

mkdir -p "$ZIEL_ORDNER" 2>/dev/null || true

uebernommen=0
uebersprungen=0
fehler=0

# Die Liste zeilenweise lesen; leere Zeilen ueberspringen. IFS wird nicht
# veraendert, damit Dateinamen mit Leerzeichen erhalten bleiben.
while IFS= read -r NAME || [ -n "$NAME" ]; do
    [ -n "$NAME" ] || continue
    # Reiner Dateiname: kein Pfadanteil (der Holer schreibt nur Namen).
    case "$NAME" in
        */*|*\\*|.|..) protokoll "PCLOUD-Uebergabe: ungueltiger Name '$NAME' - uebersprungen."; fehler=$((fehler+1)); continue ;;
    esac

    QUELLE="$STAGING/$NAME"
    ZIEL="$ZIEL_ORDNER/$NAME"

    if [ ! -f "$QUELLE" ]; then
        protokoll "PCLOUD-Uebergabe $NAME Quelle fehlt: $QUELLE - nichts uebernommen."
        continue
    fi

    # Schnellpruefung: Groesse + Zeit von Quelle und Ziel unveraendert seit der
    # letzten Pruefung -> keine Pruefsumme.
    STEMPEL="$ZIEL.pruefstempel"
    if stempel_passt "$STEMPEL" "$QUELLE" "$ZIEL"; then
        protokoll "PCLOUD-Uebergabe $NAME uebersprungen (Groesse und Zeit unveraendert seit letzter Pruefung, keine Pruefsumme): quelle=$QUELLE ziel=$ZIEL"
        uebersprungen=$((uebersprungen+1))
        continue
    fi

    S="$(sha256_von "$QUELLE")"
    if [ -z "$S" ]; then
        protokoll "PCLOUD-Uebergabe FEHLER: Pruefsumme der Quelle nicht lesbar: $QUELLE - $NAME uebersprungen."
        fehler=$((fehler+1)); continue
    fi
    NG="$(groesse_von "$QUELLE")"

    ZZ=""; NZ=""; ZZ_AUS_STEMPEL=0
    if [ -f "$ZIEL" ]; then
        # Ziel unveraendert (Groesse + mtime + Stempelalter) -> gestempelte
        # Pruefsumme wiederverwenden statt das Ziel erneut zu lesen.
        # Der Stempel wird dann NICHT erneuert: sein Alter bleibt die Uhr fuer
        # die naechste volle Pruefung (sonst wuerde er nie ablaufen).
        ZZ_AUS_STEMPEL=1
        ZZ="$(stempel_ziel_sha "$STEMPEL" "$ZIEL")" || ZZ=""
        if [ -z "$ZZ" ]; then ZZ_AUS_STEMPEL=0; ZZ="$(sha256_von "$ZIEL")"; fi
        if [ -z "$ZZ" ]; then
            protokoll "PCLOUD-Uebergabe FEHLER: Pruefsumme des Ziels nicht lesbar: $ZIEL - $NAME uebersprungen."
            fehler=$((fehler+1)); continue
        fi
        NZ="$(groesse_von "$ZIEL")"
    fi

    # Gleiche Pruefsumme -> nichts tun (idempotent).
    if [ -n "$ZZ" ] && [ "$ZZ" = "$S" ]; then
        protokoll "PCLOUD-Uebergabe $NAME uebersprungen (Pruefsumme gleich, nichts kopiert): quelle=$QUELLE groesse=$NG sha256=$S ziel=$ZIEL groesse=$NZ sha256=$ZZ"
        [ "$ZZ_AUS_STEMPEL" = "1" ] || stempel_schreiben "$STEMPEL" "$QUELLE" "$ZIEL" "$S"
        uebersprungen=$((uebersprungen+1))
        continue
    fi

    # Anders/neu: ZUERST sichern, DANN kopieren.
    SICHERUNG=""
    if [ -n "$ZZ" ]; then
        _basis="$ZIEL.vor_$(date '+%Y-%m-%d')"
        SICHERUNG="$_basis"
        _n=2
        while [ -e "$SICHERUNG" ] && [ "$_n" -le 100 ]; do
            SICHERUNG="${_basis}_$_n"
            _n=$((_n + 1))
        done
        if [ -e "$SICHERUNG" ]; then
            protokoll "PCLOUD-Uebergabe FEHLER: kein freier Sicherungspfad neben $ZIEL - $NAME nichts kopiert."
            fehler=$((fehler+1)); continue
        fi
        if cp -p -- "$ZIEL" "$SICHERUNG" 2>/dev/null; then
            protokoll "PCLOUD-Uebergabe $NAME Sicherung angelegt: $SICHERUNG (alte Fassung groesse=$NZ sha256=$ZZ)"
        else
            protokoll "PCLOUD-Uebergabe FEHLER: Sicherung $ZIEL -> $SICHERUNG fehlgeschlagen - $NAME nichts kopiert."
            fehler=$((fehler+1)); continue
        fi
    fi

    TEIL="$ZIEL.teil"
    if ! cp -- "$QUELLE" "$TEIL" 2>/dev/null; then
        protokoll "PCLOUD-Uebergabe FEHLER: Kopie $QUELLE -> $TEIL nicht moeglich - $NAME Ziel unveraendert."
        fehler=$((fehler+1)); continue
    fi
    ST="$(sha256_von "$TEIL")"
    if [ "$ST" != "$S" ]; then
        protokoll "PCLOUD-Uebergabe FEHLER: Pruefsumme der Kopie weicht ab (Quelle sha256=$S, Kopie ${ST:-nicht lesbar}) - $NAME Ziel unveraendert."
        fehler=$((fehler+1)); continue
    fi
    if ! mv -f -- "$TEIL" "$ZIEL" 2>/dev/null; then
        protokoll "PCLOUD-Uebergabe FEHLER: Kopie konnte nicht an ihren Platz ($ZIEL) gesetzt werden - $NAME Ziel unveraendert."
        fehler=$((fehler+1)); continue
    fi

    NG2="$(groesse_von "$ZIEL")"
    ZZ2="$(sha256_von "$ZIEL")"
    protokoll "PCLOUD-Uebergabe $NAME uebernommen (kopiert): quelle=$QUELLE groesse=$NG sha256=$S ziel=$ZIEL groesse=$NG2 sha256=$ZZ2 sicherung=${SICHERUNG:-keine}"
    # Stempel mit den Werten NACH dem Kopieren.
    stempel_schreiben "$STEMPEL" "$QUELLE" "$ZIEL" "$ZZ2"
    echo "  uebernommen: $NAME (${NG2} B)"
    [ -n "$SICHERUNG" ] && echo "    vorherige Fassung gesichert: $SICHERUNG"
    uebernommen=$((uebernommen+1))
done < "$LISTE"

protokoll "PCLOUD-Uebergabe fertig: uebernommen=$uebernommen uebersprungen=$uebersprungen fehler=$fehler"
[ "$uebernommen" -gt 0 ] && echo "PCLOUD-Uebergabe: $uebernommen uebernommen, $uebersprungen uebersprungen."
exit 0
