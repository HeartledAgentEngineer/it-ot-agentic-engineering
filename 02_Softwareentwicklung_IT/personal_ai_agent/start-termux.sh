#!/data/data/com.termux/files/usr/bin/bash
#
# Startskript fuer Termux — holt Updates und startet den Server.
#
# Einrichtung einmalig:
#   pkg install termux-api          # fuer den Weckruf-Sperrmechanismus
#   mkdir -p ~/.shortcuts
#   ln -sf ~/personal_ai_agent/start-termux.sh ~/.shortcuts/agent
#   chmod +x ~/personal_ai_agent/start-termux.sh
#
# Danach: Termux:Widget aus F-Droid installieren, Widget auf den
# Startbildschirm legen, "agent" antippen. Ein Druck holt den neuen Stand
# und startet den Server — kein Tippen mehr.
#
# Der Weg ueber ~/.shortcuts ist Absicht: Termux:Widget zeigt genau die
# Skripte dort an, und ein Symlink bleibt aktuell, wenn das Repo sich
# aendert. Eine Kopie waere sofort veraltet.

set -u

PROJEKT="${PROJEKT:-$HOME/personal_ai_agent}"
PORT="${PORT:-8080}"

cd "$PROJEKT" || { echo "Projektordner nicht gefunden: $PROJEKT"; exit 1; }

echo "── Aktualisieren ──────────────────────────────"
# --ff-only: Bei lokalen Aenderungen lieber abbrechen als einen
# Merge-Konflikt mitten im Start zu erzeugen.
if git pull --ff-only; then
    echo "Stand: $(git log --oneline -1)"
else
    echo
    echo "⚠️  git pull fehlgeschlagen – der Server startet mit dem alten Stand."
    echo "    Meist liegen lokale Aenderungen vor. Nachsehen mit: git status"
    echo
fi

# Verhindert, dass Android den Server beim Bildschirmsperren einschlaefert.
# Ohne das bricht ein laufender Stream ab, sobald das Display ausgeht.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo
echo "── Server startet ─────────────────────────────"
echo "Im Browser:   http://localhost:$PORT"
ip=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
[ -n "${ip:-}" ] && echo "Im Heimnetz:  http://$ip:$PORT"
echo "Beenden mit Strg+C  (Lautstaerke-hoch + C)"
echo

cd backend || { echo "backend/ fehlt"; exit 1; }

# exec: Der Server ersetzt die Shell, damit Strg+C ihn direkt erreicht
# und nicht nur das Skript beendet.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
