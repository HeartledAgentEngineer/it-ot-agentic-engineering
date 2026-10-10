#!/data/data/com.termux/files/usr/bin/bash
#
# Wissensdatei (memory.db) aus dem Download-Ordner in den Termux-Heimordner
# uebernehmen (10.10.2026).
#
# Anlass (Befund des Nachtlaufs 10.10.2026): Der Chat liest die Wissensdatei
# unter $HOME/memory.db. Dort lag eine ALTE Kopie (30.891 Vektorzeilen, Stand
# vor dem WhatsApp-Vollimport); die frische Datei (241.402 WhatsApp-Nachrichten,
# 481 Gespraeche, WhatsApp-Anteil 21.788 Abschnitte) lag unbenutzt in
# /sdcard/Download, weil KEIN Startweg sie uebernahm. Der benutzte Startweg ist
# das Widget -> termux/agent-start; der ruft dieses Skript auf.
# (Die Uebernahme von archiv_index.db in start-termux.sh ist etwas anderes und
# bleibt dort.)
#
# Verhalten:
#   1. Gleiche sha256 (Quelle = Ziel): NICHTS passiert - still, kein Kopieren
#      bei jedem Start (idempotent). Eine Zeile ins Protokoll.
#   2. Andere/neuere Quelle: die vorhandene Ziel-Fassung wird ZUERST als
#      <ziel>.vor_<datum> gesichert, dann kopiert (erst als .teil, nach
#      bestandener Pruefsumme an ihren Platz - nie eine halbe Datei).
#      Es wird NIE etwas geloescht; die Quelle bleibt liegen.
#   3. Jede Aktion wird protokolliert: Zeitpunkt, Groesse und sha256 von Quelle
#      und Ziel, kopiert/uebersprungen - im hermes_diag-Ordner des freigegebenen
#      Download-Ordners, von wo der PC ueber das Kabel nachsehen kann (der
#      Termux-Heimordner ist ueber das Kabel nicht lesbar).
#   4. Fehlertolerant: fehlende Quelle, nicht gemounteter Speicher, nicht
#      lesbare Pruefsumme und misslungene Kopien schreiben eine klare Zeile ins
#      Protokoll und lassen den Start normal weiterlaufen.
#   5. Kein Netz, kein Cloud-Abruf, keine Zugangsdaten. Nur lokale
#      Dateioperationen (cp, mv, sha256sum, stat, Protokoll).
#
# Aufruf:  bash termux/wissensdatei-uebernehmen.sh
#   Ueberschreibbar (fuer Tests/andere Ablagen; auf dem Handy nicht noetig):
#     WISSENSDATEI_QUELLE    Standard: $HOME/storage/downloads/memory.db,
#                            sonst /sdcard/Download/memory.db
#     WISSENSDATEI_ZIEL      Standard: $HOME/memory.db
#     WISSENSDATEI_PROTOKOLL Standard: <Download>/hermes_diag/wissensdatei_uebernahme.log,
#                            Rueckfall $HOME/wissensdatei_uebernahme.log
# Exit: IMMER 0 - dieses Skript darf den Start NIEMALS abbrechen (der Aufrufer
#       sichert zusaetzlich mit "|| true" ab).

set -u

QUELLE="${WISSENSDATEI_QUELLE:-}"
ZIEL="${WISSENSDATEI_ZIEL:-$HOME/memory.db}"

# ── Protokoll-Ort bestimmen ─────────────────────────────────────────────────
# Gleiches Muster wie die uebrigen Start-Uebernahmen (uebergabe_uebernehmen.py,
# nachpflege-job.sh): der Termux-Heimordner ist ueber das Kabel NICHT lesbar,
# der freigegebene Download-Ordner schon. Dort liegt das Protokoll.
if [ -z "${WISSENSDATEI_PROTOKOLL:-}" ]; then
    BASIS="$HOME/storage/downloads"
    [ -d "$BASIS" ] || BASIS="/sdcard/Download"
    WISSENSDATEI_PROTOKOLL="$BASIS/hermes_diag/wissensdatei_uebernahme.log"
fi

_protokoll_vorbereiten() {
    mkdir -p "$(dirname "$WISSENSDATEI_PROTOKOLL")" 2>/dev/null
}
if ! _protokoll_vorbereiten; then
    # Speicher nicht gemountet o. ae.: Protokoll in den Heimordner ausweichen
    # (dort nicht kabel-lesbar, aber die Zeile geht nicht verloren).
    WISSENSDATEI_PROTOKOLL="$HOME/wissensdatei_uebernahme.log"
    _protokoll_vorbereiten || WISSENSDATEI_PROTOKOLL=""
fi

protokoll() {
    [ -n "$WISSENSDATEI_PROTOKOLL" ] || return 0
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$WISSENSDATEI_PROTOKOLL" 2>/dev/null
    return 0
}

# Protokoll kurz halten (Muster agent-ensure.sh/nachpflege-job.sh): ab mehr als
# 200 KB bleiben die letzten 500 Zeilen. Geloescht wird nichts, nur gekuerzt.
if [ -n "$WISSENSDATEI_PROTOKOLL" ] && [ -f "$WISSENSDATEI_PROTOKOLL" ]; then
    _kb="$(wc -c < "$WISSENSDATEI_PROTOKOLL" 2>/dev/null || echo 0)"
    if [ "${_kb:-0}" -gt 204800 ]; then
        tail -n 500 "$WISSENSDATEI_PROTOKOLL" > "$WISSENSDATEI_PROTOKOLL.neu" 2>/dev/null \
            && mv -f "$WISSENSDATEI_PROTOKOLL.neu" "$WISSENSDATEI_PROTOKOLL" 2>/dev/null
    fi
fi

# ── Quelle bestimmen ────────────────────────────────────────────────────────
if [ -z "$QUELLE" ]; then
    for _k in "$HOME/storage/downloads/memory.db" "/sdcard/Download/memory.db"; do
        if [ -f "$_k" ]; then QUELLE="$_k"; break; fi
    done
    [ -n "$QUELLE" ] || QUELLE="/sdcard/Download/memory.db"
fi

# ── Werkzeuge pruefen (ohne sha256sum gibt es keine Uebernahme) ─────────────
if ! command -v sha256sum >/dev/null 2>&1; then
    protokoll "WISSENSDATEI FEHLER: sha256sum fehlt - nichts uebernommen, Start laeuft weiter."
    exit 0
fi

sha256_von() { sha256sum -- "$1" 2>/dev/null | cut -d' ' -f1; }
groesse_von() { stat -c %s -- "$1" 2>/dev/null || echo '?'; }

# ── 1. Quelle fehlt? -> klare Zeile, nichts tun ─────────────────────────────
if [ ! -f "$QUELLE" ]; then
    protokoll "WISSENSDATEI Quelle fehlt: $QUELLE - nichts uebernommen, Start laeuft weiter."
    exit 0
fi

# ── 2. Pruefsumme der Quelle (das harte Kriterium) ──────────────────────────
S="$(sha256_von "$QUELLE")"
if [ -z "$S" ]; then
    protokoll "WISSENSDATEI FEHLER: Pruefsumme der Quelle nicht lesbar: $QUELLE - nichts uebernommen, Start laeuft weiter."
    exit 0
fi
NG="$(groesse_von "$QUELLE")"

# ── 3. Ziel pruefen ─────────────────────────────────────────────────────────
ZZ=""
NZ=""
if [ -f "$ZIEL" ]; then
    ZZ="$(sha256_von "$ZIEL")"
    if [ -z "$ZZ" ]; then
        protokoll "WISSENSDATEI FEHLER: Pruefsumme des Ziels nicht lesbar: $ZIEL (Quelle sha256=$S, $NG B) - nichts uebernommen, Start laeuft weiter."
        exit 0
    fi
    NZ="$(groesse_von "$ZIEL")"
fi

# ── 4. Gleich? -> nichts tun; nur die Beleg-Zeile ins Protokoll ─────────────
if [ -n "$ZZ" ] && [ "$ZZ" = "$S" ]; then
    protokoll "WISSENSDATEI uebersprungen (Pruefsumme gleich, nichts kopiert): quelle=$QUELLE groesse=$NG sha256=$S ziel=$ZIEL groesse=$NZ sha256=$ZZ"
    exit 0
fi

# ── 5. Anders/neu: ZUERST sichern, DANN kopieren ────────────────────────────
# Sicherungspfad mit Datum; existiert er schon (zweite Uebernahme am selben
# Tag), kommt _2, _3, ... - eine vorhandene Sicherung wird nie ueberschrieben.
# Ist kein freier Name zu finden, wird NICHT kopiert (Rueckweg bleibt Pflicht).
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
        protokoll "WISSENSDATEI FEHLER: kein freier Sicherungspfad neben $ZIEL - nichts kopiert, Start laeuft weiter."
        exit 0
    fi
    if cp -p -- "$ZIEL" "$SICHERUNG" 2>/dev/null; then
        protokoll "WISSENSDATEI Sicherung angelegt: $SICHERUNG (alte Fassung groesse=$NZ sha256=$ZZ)"
    else
        protokoll "WISSENSDATEI FEHLER: Sicherung $ZIEL -> $SICHERUNG fehlgeschlagen - nichts kopiert, Start laeuft weiter."
        exit 0
    fi
fi

# Kopie erst als "<ziel>.teil" im selben Ordner, Pruefsumme vergleichen, dann
# an ihren Platz setzen: es entsteht nie eine halbe Wissensdatei. Bleibt nach
# einem Abbruch eine .teil-Datei liegen, wird sie beim naechsten Lauf
# ueberschrieben - geloescht wird nichts.
TEIL="$ZIEL.teil"
if ! cp -- "$QUELLE" "$TEIL" 2>/dev/null; then
    protokoll "WISSENSDATEI FEHLER: Kopie $QUELLE -> $TEIL nicht moeglich - Ziel unveraendert, Start laeuft weiter."
    exit 0
fi
ST="$(sha256_von "$TEIL")"
if [ "$ST" != "$S" ]; then
    protokoll "WISSENSDATEI FEHLER: Pruefsumme der Kopie weicht ab (Quelle sha256=$S, Kopie ${ST:-nicht lesbar}) - Ziel unveraendert, Start laeuft weiter."
    exit 0
fi
if ! mv -f -- "$TEIL" "$ZIEL" 2>/dev/null; then
    protokoll "WISSENSDATEI FEHLER: Kopie konnte nicht an ihren Platz ($ZIEL) gesetzt werden - Ziel unveraendert, Start laeuft weiter."
    exit 0
fi

# ── 6. Beleg ins Protokoll + kurze Meldung im Widget-Fenster ────────────────
NG2="$(groesse_von "$ZIEL")"
ZZ2="$(sha256_von "$ZIEL")"
protokoll "WISSENSDATEI uebernommen (kopiert): quelle=$QUELLE groesse=$NG sha256=$S ziel=$ZIEL groesse=$NG2 sha256=$ZZ2 sicherung=${SICHERUNG:-keine}"
echo "Wissensdatei uebernommen: $QUELLE -> $ZIEL (${NG2} B)"
if [ -n "$SICHERUNG" ]; then
    echo "  vorherige Fassung gesichert: $SICHERUNG"
fi
exit 0
