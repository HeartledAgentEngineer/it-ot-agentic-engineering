#!/data/data/com.termux/files/usr/bin/bash
#
# Einmalige Einrichtung des Startknopfes.
#
# Legt einen Symlink in ~/.shortcuts an. Termux:Widget zeigt genau die
# Skripte von dort als Knoepfe an. Ein Symlink statt einer Kopie ist
# Absicht: Er bleibt aktuell, wenn sich das Repo aendert.
#
# Voraussetzung: Termux:Widget aus F-Droid (nicht aus dem Play Store).

set -u

skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
HIER="$(cd "$(dirname "$skript")" && pwd)"

ZIEL="$HOME/.shortcuts"

mkdir -p "$ZIEL"
# Termux:Widget weigert sich, Skripte auszufuehren, auf die auch Gruppe
# oder andere schreiben duerfen. 700 ist hier keine Zierde, sondern
# Bedingung.
chmod 700 "$ZIEL"

chmod +x "$HIER/agent-start"

ln -sf "$HIER/agent-start" "$ZIEL/agent"

echo "Fertig. Im Startbildschirm liegt jetzt der Knopf:"
echo
echo "   agent   →   Server starten und Oberflaeche oeffnen"
echo
echo "Noch zu tun, falls nicht geschehen:"
echo "  1. Termux:Widget aus F-Droid installieren"
echo "  2. Auf dem Startbildschirm lange druecken → Widgets → Termux"
echo "  3. Das Widget ablegen und 'agent' antippen"
echo
ls -l "$ZIEL"
