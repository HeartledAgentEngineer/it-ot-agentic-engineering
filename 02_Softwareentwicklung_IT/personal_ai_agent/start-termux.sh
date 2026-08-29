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

# Der Projektordner ist der Ordner, in dem dieses Skript liegt. Ueber
# ~/.shortcuts ist $0 ein Symlink, der zuerst aufgeloest werden muss.
#
# Vorher stand hier fest $HOME/personal_ai_agent. Das passte nie zur
# Anleitung, die das Repo nach ~/it-ot-agentic-engineering/... klont — das
# Skript brach also gleich in der ersten Zeile ab. Selbst herausfinden, wo
# man liegt, geht immer; raten geht schief.
skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
PROJEKT="${PROJEKT:-$(cd "$(dirname "$skript")" && pwd)}"
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

# Speicherzugriff einmalig/einrichten (idempotent): legt ~/storage an (Symlinks
# zu Download/DCIM/Documents...) für die Handy-Dateisuche. Muss nur beim ersten
# Mal + nach Termux-Neuinstallation laufen; hier im Start ist es selbstheilend.
# Fehlt die Android-Berechtigung, erscheint der System-Dialog — das Skript
# bricht NICHT ab, der Server startet trotzdem (Dateisuche dann eben ohne).
command -v termux-setup-storage >/dev/null 2>&1 && termux-setup-storage

# Verhindert, dass Android den Server beim Bildschirmsperren einschlaefert.
# Ohne das bricht ein laufender Stream ab, sobald das Display ausgeht.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Alten Agenten-Server beenden, bevor der neue startet — so kann es nie
# zwei uvicorn-Instanzen auf demselben Port geben.
#
# Frueher stand hier nur `pkill -f "uvicorn app.main:app"`. Das matchte den
# echten Prozess (python -m uvicorn ... --reload) oft nicht, der alte Server
# blieb auf dem Port — deshalb "Address already in use" / "already processed"
# + der neue Server (mit frischer Config) kam nie wirklich hoch. Jetzt killen
# wir alle uvicorn-Varianten und warten, bis der Port frei ist.
echo "── Alter Server wird beendet ──────────────────"
# Sanft beenden (SIGTERM), damit uvicorn sauber herunterfaehrt und die
# alte Termux-Session nicht als 'durchgestrichen/Code 137' stehenbleibt.
# Nur wenn der Server nach kurzer Zeit noch lebt, wird hart gekillt (-9).
pkill -TERM -f "uvicorn app.main:app" 2>/dev/null
pkill -TERM -f "python -m uvicorn" 2>/dev/null
pkill -TERM -f "uvicorn" 2>/dev/null

# Warten, bis er wirklich weg ist (sanft), sonst als Fallback hart beenden.
i=0
while [ $i -lt 10 ]; do
    if ! (command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":$PORT ") \
       && ! pgrep -f "uvicorn" >/dev/null 2>&1; then
        break
    fi
    i=$((i+1))
    sleep 1
done
# Haengt er immer noch, bleibt nur der harte Abbruch (letzter Ausweg).
if pgrep -f "uvicorn" >/dev/null 2>&1; then
    echo "  sanftes Beenden fehlgeschlagen – letzter Versuch (kill -9)"
    pkill -9 -f "uvicorn" 2>/dev/null
fi

# Kurz warten, bis der Port wirklich frei ist (statt nur sleep 1).
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if command -v ss >/dev/null 2>&1; then
        if ! ss -tln 2>/dev/null | grep -q ":$PORT "; then
            break
        fi
    fi
    sleep 1
done
echo "Alter Server gestoppt / Port frei."

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
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
