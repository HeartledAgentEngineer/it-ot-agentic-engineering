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
#   * gibt es im Ziel schon eine Fassung mit GLEICHEM INHALT -> uebersprungen
#     (nichts wird geschrieben). Verglichen wird der Inhalt, NICHT die Groesse:
#     ein geaenderter Name oder eine geaenderte Zuordnung kann genau so lang
#     sein wie die alte Fassung (Gruppierung v2, G0). Vergleich mit "cmp -s";
#     fehlt cmp, mit der sha256sum-Pruefsumme; fehlt beides, wird IMMER kopiert
#     (die alte Fassung liegt dann trotzdem als ".vorher" daneben).
#   * sonst: eine vorhandene Ziellaessung wird ZUERST als "<name>.vorher"
#     danebengelegt (Rueckweg), dann per cp nach "<name>.teil" und per mv an
#     ihren Platz — es steht nie eine halbe Datei im Zielordner.
#
# G0 (Auflage 2 der Gruppierung-v2-Planfassung 5.3, 20.10.2026):
#   * personen_bestaetigt.json und personen_vorgaben.json sind PFLICHT. Fehlt
#     eine von beiden im Quellordner, endet das Skript mit **Exit 1** und nennt
#     die fehlende Datei (vorher war das nur ein Hinweis). Der App-Start wird
#     davon NICHT blockiert: der Aufrufer (termux/start-vorbereiten.sh) ruft das
#     Skript mit "|| true" auf.
#   * Zu diesen zwei Dateien wird ein **Geraetestand** in den Zielordner
#     geschrieben (geraetestand.json): je Datei Bytes, sha256 und die
#     durchgezaehlten Eintraege, dazu der Zeitpunkt. Der PC (personen_gruppieren.py,
#     entscheidungen_pruefen) haelt ihn gegen seine Kopie; ohne diesen Nachweis
#     rechnet v2 nur als Trockenmessung. Fehlen sha256sum/date oder ein Python,
#     wird KEIN Geraetestand erzeugt (ehrliche Zeile) — der Nachweis gilt dann
#     als nicht erbracht, es wird nie still etwas angenommen.
#
# Regeln (hart):
#   * Es wird NICHTS geloescht und am QUELLORDNER nichts geaendert — nur
#     kopiert. Im Zielordner entstehen/ersetzt werden ausschliesslich die
#     eigenen Dateien dieses Rueckwegs (und deren .vorher/.teil).
#   * Kein Netz, kein pCloud, kein Upload. Kein fremdes Programm ausser cp/mv
#     (und, nur fuer den Geraetestand, sha256sum/wc/date sowie optional python).
#   * Exit 0 = alles bereitgestellt; Exit 1 = eine Pflichtdatei fehlt (G0).
#     Ein fehlender Quellordner ist derselbe Fall (dann fehlen beide).
#
# Aufruf (Termux, ueblicherweise aus termux/start-vorbereiten.sh):
#   bash termux/rueckweg-bereitstellen.sh
#
# Fuer Tests sind vier Werte umleitbar: RUECKWEG_QUELLE (Standard
# $HOME/foto_sortierung), RUECKWEG_ZIEL (Standard
# /sdcard/Download/hermes_rueckweg), RUECKWEG_NAMEN (die Dateiliste) und
# RUECKWEG_PFLICHT (die Pflichtdateien).

set -u

QUELLE="${RUECKWEG_QUELLE:-$HOME/foto_sortierung}"
ZIEL="${RUECKWEG_ZIEL:-/sdcard/Download/hermes_rueckweg}"

# Die Dateien des Rueckwegs. DIESE Zeile ist die eine Quelle: ein
# Waechter-Test haelt sie mit ERLAUBTE_NAMEN in tools/handy/rueckweg_holen.py
# zusammen, damit beide Seiten nicht auseinanderlaufen.
#
# personen_bestaetigt.json und personen_vorgaben.json sind die eigene
# Namensarbeit am Handy (Gruppierung v2, G0): ohne sie kennt der PC nur den
# Stand vom 08.10.
RUECKWEG_NAMEN="${RUECKWEG_NAMEN:-geschichten.jsonl anlass_umbenennung.jsonl personen_bestaetigt.json personen_vorgaben.json}"

# Davon PFLICHT (G0): fehlt eine, wird nichts bereitgestellt und der Aufruf
# endet mit Exit 1. Die Liste steht woertlich auch in
# personen_gruppieren.PFLICHTQUELLEN (ein Waechter-Test haelt beide zusammen).
RUECKWEG_PFLICHT="${RUECKWEG_PFLICHT:-personen_bestaetigt.json personen_vorgaben.json}"

# Der Geraetestand, den dieses Skript ERZEUGT (kein Kopiervorgang):
# tools/handy/rueckweg_holen.py holt ihn mit (ERLAUBTE_NAMEN).
RUECKWEG_ERZEUGT="${RUECKWEG_ERZEUGT:-geraetestand.json}"

meldung() { printf '%s\n' "$*"; }

# Haben die beiden Dateien denselben INHALT? Rueckgabe 0 = ja, 1 = nein oder
# nicht festzustellen (dann wird kopiert - lieber einmal zu viel als eine
# geaenderte Datei ueberspringen). Reihenfolge: cmp -s, sonst sha256sum,
# sonst "nicht festzustellen".
gleicher_inhalt() {
    if command -v cmp >/dev/null 2>&1; then
        cmp -s "$1" "$2" 2>/dev/null
        return $?
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        summe_a="$(sha256sum < "$1" 2>/dev/null)"
        summe_b="$(sha256sum < "$2" 2>/dev/null)"
        summe_a="${summe_a%% *}"
        summe_b="${summe_b%% *}"
        if [ -n "$summe_a" ] && [ "$summe_a" = "$summe_b" ]; then
            return 0
        fi
        return 1
    fi
    return 1
}

meldung "── Rueckweg bereitstellen (Handy -> PC) ──"
meldung "Quelle: $QUELLE"
meldung "Ziel:   $ZIEL"

if [ ! -d "$QUELLE" ]; then
    meldung "Quelle nicht vorhanden — es fehlen ALLE Pflichtdateien (G0)."
    for name in $RUECKWEG_PFLICHT; do
        meldung "  PFLICHTDATEI FEHLT am Geraet: $name"
    done
    meldung "Ohne die Pflichtdateien wird nichts bereitgestellt — Exit 1. (Der App-Start laeuft weiter: der Aufrufer ignoriert diesen Code.)"
    exit 1
fi

if [ ! -d "$ZIEL" ]; then
    if ! mkdir -p "$ZIEL" 2>/dev/null; then
        meldung "Zielordner nicht anlegbar (keine Speicherfreigabe?) — nichts bereitgestellt."
        exit 0
    fi
fi

# G0: Die Pflichtdateien muessen VOR dem Kopieren da sein. Fehlt eine, wird
# nichts bereitgestellt (auch nichts anderes) und der Aufruf endet mit Exit 1.
fehlende_pflicht=""
for name in $RUECKWEG_PFLICHT; do
    [ -f "$QUELLE/$name" ] || fehlende_pflicht="$fehlende_pflicht $name"
done
if [ -n "$fehlende_pflicht" ]; then
    for name in $fehlende_pflicht; do
        meldung "  PFLICHTDATEI FEHLT am Geraet: $name"
    done
    meldung "Ohne die Pflichtdateien wird nichts bereitgestellt (G0) — Exit 1."
    meldung "Der App-Start wird davon nicht blockiert (der Aufrufer ignoriert diesen Code)."
    exit 1
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
        if gleicher_inhalt "$quelle" "$ziel"; then
            meldung "  $name: schon bereitgestellt (gleicher Inhalt, $groesse_quelle Bytes)."
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

# ── Geraetestand (G0, Auflage 2) ───────────────────────────────────────────
#
# Zu den zwei Pflichtdateien schreibt das Geraet einen Nachweis in den
# Zielordner: je Datei Bytes, sha256 und die durchgezaehlten Eintraege, dazu
# den Zeitpunkt. Der PC haelt ihn gegen seine Kopie (personen_gruppieren.py,
# entscheidungen_pruefen). Dieselben Zaehlregeln wie dort: benannte Kennungen
# und Namen in personen_bestaetigt.json, die vier Listenlaengen aus
# personen_vorgaben.json. Fehlt ein Python, steht "zaehler": null — dann gilt
# der Nachweis als NICHT erbracht (der PC schreibt damit nichts).
python_programm() {
    # Nicht nur "da", sondern auch benutzbar: die Windows-Store-Attrappe von
    # python3 existiert als Datei, laesst sich aber nicht aufrufen. Ein
    # Fehlversuch faellt hier durch — und der Nachweis gilt dann ehrlich als
    # nicht erbracht (zaehler null).
    for kandidat in python3 python; do
        if command -v "$kandidat" >/dev/null 2>&1 \
           && "$kandidat" -c 'import json, sys' >/dev/null 2>&1; then
            printf '%s' "$kandidat"
            return 0
        fi
    done
    return 1
}

zaehler_json() {                                    # $1 = Art, $2 = Pfad
    programm="$(python_programm)" || { printf 'null'; return 0; }
    "$programm" - "$1" "$2" <<'PY' 2>/dev/null || printf 'null'
import json, sys

art, pfad = sys.argv[1], sys.argv[2]
with open(pfad, encoding="utf-8") as datei:
    daten = json.load(datei)
if not isinstance(daten, dict):
    raise SystemExit(1)
if art == "bestaetigt":
    roh = daten.get("bestaetigt") or {}
    if not isinstance(roh, dict):
        raise SystemExit(1)
    namen = sum(1 for wert in roh.values()
                if isinstance(wert, str) and wert.strip())
    print(json.dumps({"benannte_kennungen": len(roh), "namen": namen}))
else:
    zahlen = {}
    for feld, schluessel in (("gleich", "gleich"), ("verschieden", "verschieden"),
                             ("ausgeschlossen", "ausgeschlossen"),
                             ("fest", "zugeordnet")):
        wert = daten.get(schluessel)
        zahlen[feld] = len(wert) if isinstance(wert, (list, dict)) else 0
    print(json.dumps(zahlen))
PY
}

stand_geschrieben=0
if command -v sha256sum >/dev/null 2>&1 && command -v date >/dev/null 2>&1; then
    stand="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    if [ -n "$stand" ]; then
        {
            printf '{\n'
            printf '  "stand": "%s",\n' "$stand"
            printf '  "quelle": "handy",\n'
            printf '  "pflicht": ['
            zuerst=1
            for name in $RUECKWEG_PFLICHT; do
                [ "$zuerst" -eq 1 ] || printf ', '
                printf '"%s"' "$name"
                zuerst=0
            done
            printf '],\n'
            printf '  "dateien": {\n'
            zuerst=1
            for name in $RUECKWEG_PFLICHT; do
                quelle="$QUELLE/$name"
                [ -f "$quelle" ] || continue
                summe="$(sha256sum < "$quelle" 2>/dev/null)"
                summe="${summe%% *}"
                [ -n "$summe" ] || continue
                bytes="$(wc -c < "$quelle" 2>/dev/null | tr -d ' ')"
                case "$name" in
                    *bestaetigt*) art=bestaetigt ;;
                    *)            art=vorgaben ;;
                esac
                zahlen="$(zaehler_json "$art" "$quelle")"
                [ -n "$zahlen" ] || zahlen=null
                [ "$zuerst" -eq 1 ] || printf ',\n'
                printf '    "%s": {"bytes": %s, "sha256": "%s", "zaehler": %s}' \
                       "$name" "$bytes" "$summe" "$zahlen"
                zuerst=0
            done
            printf '\n  }\n}\n'
        } > "$ZIEL/$RUECKWEG_ERZEUGT.teil" 2>/dev/null \
            && mv "$ZIEL/$RUECKWEG_ERZEUGT.teil" "$ZIEL/$RUECKWEG_ERZEUGT" \
            && stand_geschrieben=1
    fi
fi

if [ "$stand_geschrieben" -eq 1 ]; then
    meldung "  $RUECKWEG_ERZEUGT: Geraetestand geschrieben (sha256 + Zaehlung beider Pflichtdateien)."
else
    meldung "  $RUECKWEG_ERZEUGT: KEIN Geraetestand erzeugt (sha256sum/date fehlen oder Ziel nicht schreibbar)."
    meldung "    Folge: der PC kann den Nachweis nicht fuehren und rechnet v2 nur als Trockenmessung."
fi

meldung "Zusammenfassung: bereitgestellt $bereitgestellt - unveraendert $uebersprungen - noch nicht angelegt $fehlend - unvollstaendig $unvollstaendig"
exit 0
