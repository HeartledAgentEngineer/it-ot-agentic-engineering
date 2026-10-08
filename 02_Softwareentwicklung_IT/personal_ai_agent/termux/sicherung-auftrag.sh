#!/data/data/com.termux/files/usr/bin/bash
#
# Sicherung auf Auftrag beim Widget-Start (08.10.2026).
#
# Wunsch Sebastian: am Handy nichts tippen. Der PC legt per Kabel die Datei
# /sdcard/Download/termux-sicherung/AUFTRAG ab (tools/handy/sicherung_auftrag.py).
# Der Widget-Knopf (termux/agent-start) ruft dieses Skript auf, NACHDEM er Server
# und Postfach-Daemon beendet und den neuesten Stand gezogen hat, und BEVOR er
# neu startet. Dann:
#
#   * kein AUFTRAG -> sofort zurueck, nichts passiert (normaler Start)
#   * AUFTRAG da   -> wird zu AUFTRAG.laeuft umbenannt (ein zweiter Widget-Druck
#                     sichert also nicht doppelt), age wird bei Bedarf
#                     installiert, sicherung.sh laeuft, danach heisst die Datei
#                     AUFTRAG.erledigt_<kennung>. Nichts wird geloescht.
#
# Alle Ausgaben gehen zusaetzlich nach lauf_<kennung>.log im selben Ordner; die
# letzte Zeile ist immer "EXIT=<code>". Der PC liest nur diese Datei.
#
# Darf den Agentenstart nie verhindern: agent-start ruft es mit "|| true" auf.

set -u

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORDNER="${SICHERUNG_ZIEL:-/sdcard/Download/termux-sicherung}"
AUFTRAG="$ORDNER/AUFTRAG"

[ -f "$AUFTRAG" ] || exit 0

KENNUNG="$(tr -cd '0-9A-Za-z_-' < "$AUFTRAG" | head -c 40)"
[ -n "$KENNUNG" ] || KENNUNG="$(date +%Y%m%d%H%M%S)"
mv "$AUFTRAG" "$AUFTRAG.laeuft" || exit 0
LOG="$ORDNER/lauf_$KENNUNG.log"

(
    echo "── Sicherung auf Auftrag ($KENNUNG) ───────────"
    echo "Start $(date '+%Y-%m-%d %H:%M:%S')"
    command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
    if ! command -v age >/dev/null 2>&1; then
        echo "age fehlt - wird installiert ..."
        if ! pkg install -y age; then
            echo "Installation von age scheiterte"
            echo "EXIT=3"
            exit 3
        fi
    fi
    bash "$HIER/sicherung.sh"
    code=$?
    echo "EXIT=$code"
    exit "$code"
) 2>&1 | tee -a "$LOG"
code="${PIPESTATUS[0]}"

mv "$AUFTRAG.laeuft" "$AUFTRAG.erledigt_$KENNUNG" 2>/dev/null
exit "$code"
