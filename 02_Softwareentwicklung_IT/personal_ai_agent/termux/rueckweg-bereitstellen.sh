#!/data/data/com.termux/files/usr/bin/bash
#
# RUECKWEG Handy -> PC: eigene Datendateien bereitstellen (12.10.2026).
#
# Warum es dieses Skript gibt:
#   Die Uebergabe laeuft bisher nur PC -> Handy. Die Dateien, die die APP AM
#   GERAET erzeugt — geschichten.jsonl (die eigenen Erzaehlungen zu Anlaessen und
#   anlass_umbenennung.jsonl (eigene Anlassnamen) — liegen im Termux-Heimordner
#   $HOME/foto_sortierung, und der ist ueber das Kabel NICHT lesbar (gemessen:
#   "Permission denied"). Ohne diesen Schritt kann der PC sie nie pruefen
#   (Nachweis "Eigene Geschichten" / "Eigene Titel") und nie lesen.
#
#   Dieses Skript KOPIERT sie in den freigegebenen Download-Ordner; das
#   PC-Werkzeug tools/handy/rueckweg_holen.py holt sie von dort ab.
#
# Was es genau tut (je Datei aus RUECKWEG_NAMEN):
#   * fehlt die Datei am Geraet -> ehrliche Zeile, nichts weiter.
#   * gibt es im Ziel schon eine Fassung mit GLEICHER Groesse -> uebersprungen
#     (nichts wird geschrieben).
#   * sonst: eine vorhandene Ziellaessung wird ZUERST als "<name>.vorher"
#     danebengelegt (Rueckweg), dann per cp nach "<name>.teil" und per mv an
#     ihren Platz — es steht nie eine halbe Datei im Zielordner.
#
# Regeln (hart):
#   * Es wird NICHTS geloescht und am QUELLORDNER nichts geaendert — nur
#     kopiert. Im Zielordner entstehen/ersetzt werden ausschliesslich die
#     eigenen Dateien dieses Rueckwegs (und deren .vorher/.teil).
#   * Kein Netz, kein pCloud, kein Upload. Kein fremdes Programm ausser cp/mv.
#   * Exit IMMER 0 — dieses Skript darf den App-Start NIE verhindern.
#
# Aufruf (Termux, ueblicherweise aus termux/start-vorbereiten.sh):
#   bash termux/rueckweg-bereitstellen.sh
#
# Fuer Tests sind drei Werte umleitbar: RUECKWEG_QUELLE (Standard
# $HOME/foto_sortierung), RUECKWEG_ZIEL (Standard
# /sdcard/Download/hermes_rueckweg) und RUECKWEG_NAMEN (die Dateiliste).

set -u

QUELLE="${RUECKWEG_QUELLE:-$HOME/foto_sortierung}"
ZIEL="${RUECKWEG_ZIEL:-/sdcard/Download/hermes_rueckweg}"

# Die Dateien des Rueckwegs. DIESE Zeile ist die eine Quelle: ein
# Waechter-Test haelt sie mit ERLAUBTE_NAMEN in tools/handy/rueckweg_holen.py
# zusammen, damit beide Seiten nicht auseinanderlaufen.
RUECKWEG_NAMEN="${RUECKWEG_NAMEN:-geschichten.jsonl anlass_umbenennung.jsonl}"

meldung() { printf '%s\n' "$*"; }

meldung "── Rueckweg bereitstellen (Handy -> PC) ──"
meldung "Quelle: $QUELLE"
meldung "Ziel:   $ZIEL"

if [ ! -d "$QUELLE" ]; then
    meldung "Quelle nicht vorhanden — nichts bereitzustellen. (Kein Fehler.)"
    exit 0
fi

if [ ! -d "$ZIEL" ]; then
    if ! mkdir -p "$ZIEL" 2>/dev/null; then
        meldung "Zielordner nicht anlegbar (keine Speicherfreigabe?) — nichts bereitgestellt."
        exit 0
    fi
fi

bereitgestellt=0
uebersprungen=0
fehlend=0
unvollstaendig=0

for name in $RUECKWEG_NAMEN; do
    quelle="$QUELLE/$name"
    ziel="$ZIEL/$name"

    if [ ! -f "$quelle" ]; then
        meldung "  $name: am Geraet noch nicht angelegt — uebersprungen."
        fehlend=$((fehlend + 1))
        continue
    fi

    groesse_quelle="$(wc -c < "$quelle" 2>/dev/null | tr -d ' ')"
    if [ -f "$ziel" ]; then
        groesse_ziel="$(wc -c < "$ziel" 2>/dev/null | tr -d ' ')"
        if [ -n "$groesse_quelle" ] && [ "$groesse_quelle" = "$groesse_ziel" ]; then
            meldung "  $name: schon bereitgestellt (gleich gross, $groesse_quelle Bytes)."
            uebersprungen=$((uebersprungen + 1))
            continue
        fi
        # Alte Fassung beiseitelegen (Rueckweg) — nie ueberschreiben ohne Kopie.
        if ! cp "$ziel" "$ziel.vorher" 2>/dev/null; then
            meldung "  $name: alte Fassung liess sich nicht sichern — uebersprungen."
            uebersprungen=$((uebersprungen + 1))
            continue
        fi
    fi

    if ! cp "$quelle" "$ziel.teil" 2>/dev/null; then
        meldung "  $name: Kopie nicht moeglich — uebersprungen."
        uebersprungen=$((uebersprungen + 1))
        continue
    fi
    if ! mv "$ziel.teil" "$ziel" 2>/dev/null; then
        meldung "  $name: Umbenennen nicht moeglich — Kopie liegt als .teil, uebersprungen."
        unvollstaendig=$((unvollstaendig + 1))
        continue
    fi

    groesse_neu="$(wc -c < "$ziel" 2>/dev/null | tr -d ' ')"
    if [ -n "$groesse_quelle" ] && [ "$groesse_quelle" != "$groesse_neu" ]; then
        meldung "  $name: Groesse weicht ab (Quelle $groesse_quelle, Kopie $groesse_neu) — gemeldet."
        unvollstaendig=$((unvollstaendig + 1))
        continue
    fi

    meldung "  $name: bereitgestellt ($groesse_neu Bytes) — holt der PC per Kabel."
    bereitgestellt=$((bereitgestellt + 1))
done

meldung "Zusammenfassung: bereitgestellt $bereitgestellt - unveraendert $uebersprungen - noch nicht angelegt $fehlend - unvollstaendig $unvollstaendig"
exit 0
