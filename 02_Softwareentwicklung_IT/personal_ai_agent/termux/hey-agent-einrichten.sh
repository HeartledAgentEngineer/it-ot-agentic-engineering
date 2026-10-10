#!/data/data/com.termux/files/usr/bin/sh
#
# hey-agent-einrichten.sh - Einrichtung fuer den App-Knopf "Hey Agent".
# Darf beliebig oft laufen; seit dem 10.10.2026 ruft die gemeinsame Start-
# Vorbereitung (termux/start-vorbereiten.sh) es bei jedem Start auf, damit
# alles selbstheilend aktuell bleibt.
#
# Was es tut:
#   1. legt $PREFIX/etc/profile.d/hey-agent.sh an. Jede Termux-Sitzung liest
#      profile.d (Login-Shell, am Handy gemessen) - aber NICHT ~/.bashrc.
#      Der Eintrag ruft termux/agent-ensure.sh --app-zurueck und findet den
#      Projektordner ueber den vollen Pfad (kein Raten ueber ~/.shortcuts).
#      Rueckgaengig: die Datei in einen anderen Ordner verschieben.
#   2. legt ~/agent-ensure.sh als DUENNE WEITERLEITUNG (Bruecke) auf
#      termux/agent-ensure.sh im Projektordner an. Die App ruft den festen
#      Pfad ~/agent-ensure.sh; eine KOPIE dort veraltete still (zweite
#      Wahrheit, Befund 10.10.2026). Die Bruecke kann nicht veralten; eine
#      alte Kopie wird einmalig als ~/agent-ensure.sh.vor_<datum> gesichert
#      (nie geloescht).
#   3. setzt allow-external-apps=true in ~/.termux/termux.properties, falls es
#      fehlt (F-Droid-/GitHub-Termux ignoriert RUN_COMMAND von fremden Apps
#      sonst STILL - der Knopf tut dann scheinbar nichts), und laedt die
#      Termux-Einstellungen neu (termux-reload-settings, wenn vorhanden).
#      Es wird nur angehaengt, nie etwas entfernt.
#
# Von Hand (aus dem Projektordner):  sh termux/hey-agent-einrichten.sh

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
HOOK="$PREFIX/etc/profile.d/hey-agent.sh"

# ---
# Voller Pfad von agent-ensure.sh aus dem eigenen Ort - NICHT ueber ~/.shortcuts/agent
# raten: die Verknuepfung zeigt auf termux/agent-start, ihr Ordner ist termux/ und nicht
# der Projektordner (am Handy gemessen 30.09.2026).
HIER="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
ENSURE="$HIER/agent-ensure.sh"
if [ ! -f "$ENSURE" ]; then
    echo "FEHLER: $ENSURE fehlt."
    exit 1
fi

mkdir -p "$PREFIX/etc/profile.d"
cat > "$HOOK" <<EOF
# Hey Agent: beim Oeffnen einer Termux-Sitzung das Backend sicherstellen und zur App
# zurueckkehren (angelegt von termux/hey-agent-einrichten.sh, siehe termux/agent-ensure.sh).
[ -f "$ENSURE" ] && sh "$ENSURE" --app-zurueck
EOF

echo "OK: $HOOK angelegt."
if ! grep -q "profile.d" "$PREFIX/etc/profile" 2>/dev/null; then
    echo "WARNUNG: $PREFIX/etc/profile erwaehnt profile.d nicht - bitte nachsehen."
fi

# ---
# Bruecke ~/agent-ensure.sh (10.10.2026): die App ruft RUN_COMMAND auf den
# festen Pfad /data/data/com.termux/files/home/agent-ensure.sh. Dort lag bisher
# eine KOPIE dieses Skripts - sie veraltete still, sobald sich das Repo
# aenderte. Jetzt steht dort nur die Weiterleitung auf den Stand im Projektordner.
PROJEKT="$(cd "$HIER/.." 2>/dev/null && pwd)"
BRUECKE="$HOME/agent-ensure.sh"
BRUECKE_MARKE="duenne Weiterleitung auf den Projektordner"
mkdir -p "$HOME" 2>/dev/null
if [ -f "$BRUECKE" ] && ! grep -q "$BRUECKE_MARKE" "$BRUECKE" 2>/dev/null; then
    _basis="$BRUECKE.vor_$(date '+%Y-%m-%d')"
    _sicherung="$_basis"
    _n=2
    while [ -e "$_sicherung" ] && [ "$_n" -le 100 ]; do
        _sicherung="${_basis}_$_n"
        _n=$((_n + 1))
    done
    if cp -p "$BRUECKE" "$_sicherung" 2>/dev/null; then
        echo "OK: alte Fassung gesichert: $_sicherung"
    fi
fi
if cat > "$BRUECKE" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
# Hey Agent: $BRUECKE_MARKE (angelegt von termux/hey-agent-einrichten.sh;
# wird dort bei jedem Start neu geschrieben). Hier steht bewusst NICHTS ausser
# der Weiterleitung - die Arbeit macht termux/agent-ensure.sh im Projektordner.
PROJEKT_BEI_EINRICHTUNG="$PROJEKT"
PROJEKT="\${PROJEKT:-}"
if [ -z "\$PROJEKT" ] && [ -L "\$HOME/.shortcuts/agent" ]; then
    _ordner="\$(cd "\$(dirname "\$(readlink "\$HOME/.shortcuts/agent")")" 2>/dev/null && pwd)"
    case "\$_ordner" in
        */termux) PROJEKT="\$(dirname "\$_ordner")" ;;
    esac
fi
if [ -z "\$PROJEKT" ] && [ -n "\$PROJEKT_BEI_EINRICHTUNG" ]; then
    PROJEKT="\$PROJEKT_BEI_EINRICHTUNG"
fi
SKRIPT="\$PROJEKT/termux/agent-ensure.sh"
if [ ! -f "\$SKRIPT" ]; then
    echo "Hey Agent: \$SKRIPT fehlt - bitte im Projektordner 'sh termux/hey-agent-einrichten.sh' ausfuehren."
    echo "\$(date '+%Y-%m-%d %H:%M:%S') BRUECKE: \$SKRIPT fehlt (PROJEKT='\${PROJEKT:-}')" >> "\$HOME/agent-ensure.log" 2>/dev/null
    exit 1
fi
exec sh "\$SKRIPT" "\$@"
EOF
then
    chmod +x "$BRUECKE" 2>/dev/null
    echo "OK: Bruecke angelegt: $BRUECKE -> $ENSURE"
else
    echo "WARNUNG: Bruecke $BRUECKE konnte nicht geschrieben werden - App-Start ohne Weiterleitung."
fi

# ---
# allow-external-apps=true (RUN_COMMAND von fremden Apps). Ohne die Zeile
# ignoriert das F-Droid-/GitHub-Termux den Intent STILL - die stille Falle:
# der App-Knopf tut nichts, und es sieht wie ein kaputter Agent aus.
T_PROP="$HOME/.termux/termux.properties"
mkdir -p "$HOME/.termux" 2>/dev/null
if [ -f "$T_PROP" ] && grep -Eq '^[[:space:]]*allow-external-apps[[:space:]]*=[[:space:]]*true' "$T_PROP" 2>/dev/null; then
    echo "OK: allow-external-apps=true ist gesetzt ($T_PROP)."
else
    if {
        echo ""
        echo "# Hey Agent (10.10.2026): erlaubt der App, Termux-Befehle (RUN_COMMAND) zu starten."
        echo "allow-external-apps=true"
    } >> "$T_PROP" 2>/dev/null; then
        echo "OK: allow-external-apps=true gesetzt ($T_PROP) - Termux laedt die Einstellungen neu."
        if command -v termux-reload-settings >/dev/null 2>&1; then
            termux-reload-settings
        fi
    else
        echo "WARNUNG: $T_PROP nicht beschreibbar - Zeile allow-external-apps=true bitte von Hand eintragen."
    fi
fi
