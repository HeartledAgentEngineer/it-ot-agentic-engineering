#!/data/data/com.termux/files/usr/bin/sh
#
# hey-agent-einrichten.sh - einmalig in Termux ausfuehren (darf beliebig oft laufen).
#
# Legt $PREFIX/etc/profile.d/hey-agent.sh an. Diese Datei liest JEDE Termux-Sitzung
# beim Start: Termux startet Sitzungen als Login-Shell (bash -l, am Handy gemessen),
# und die Login-Shell liest $PREFIX/etc/profile -> profile.d/*.sh, aber NICHT ~/.bashrc.
#
# Der Eintrag ruft beim Oeffnen einer Sitzung  termux/agent-ensure.sh --app-zurueck
#   - laeuft das Backend: sofort Ende, nichts passiert
#   - sonst: neuesten Stand ziehen (nur Vorspulen), Backend starten, auf /health
#     warten, zurueck zur App "Hey Agent" (heyagent://start)
#
# Die Hook-Datei wird jedes Mal ganz neu geschrieben, nie angehaengt - also nichts doppelt.
# Rueckgaengig: die Datei $PREFIX/etc/profile.d/hey-agent.sh in einen anderen Ordner
# verschieben, z. B.  mv "$PREFIX/etc/profile.d/hey-agent.sh" ~/hey-agent.sh.aus
#
# Aufruf: das Widget (termux/agent-start) ruft es bei jedem Tipp selbst auf.
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
if grep -q "profile.d" "$PREFIX/etc/profile" 2>/dev/null; then
    echo "OK: $PREFIX/etc/profile liest profile.d - der Eintrag greift bei jeder neuen Sitzung."
else
    echo "WARNUNG: $PREFIX/etc/profile erwaehnt profile.d nicht - bitte Claude Bescheid geben."
fi
echo "Test: Termux ueber 'Exit' in der Benachrichtigung beenden, dann Hey Agent antippen."
