#!/data/data/com.termux/files/usr/bin/bash
#
# Startskript fuer Termux — holt Updates und startet den Server.
#
# Der Auftrags-Watcher bleibt aus; WATCHER=1 schaltet ihn an (Begruendung unten).
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

# Verhindert, dass Android den Server beim Bildschirmsperren einschlaefert.
# Ohne das bricht ein laufender Stream ab, sobald das Display ausgeht.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# ── Watcher (standardmaessig AUS) ──────────────────────────────────────────
# Der Watcher holt Auftraege ueber GET /naechster ab und weckt Hermes. Er
# funktioniert: am 18.08. lief er stundenlang zuverlaessig und holte drei
# liegengebliebene Auftraege binnen neun Sekunden ab.
#
# Trotzdem steht er auf AUS, aus einem harten Grund:
#
#   /naechster liefert nur OFFENE Auftraege und setzt sie sofort auf
#   "laeuft". Wer zuerst fragt, bekommt den Auftrag. Laeuft der Watcher, ist
#   binnen drei Sekunden nichts mehr offen - und Hermes, der ueber denselben
#   Endpunkt abholt, findet nichts mehr vor. Er meldet dann "nichts zu tun",
#   obwohl im Buch etwas liegt.
#
# Solange Hermes der Bearbeiter ist, darf der Watcher also nicht laufen. Das
# ist keine Schwaeche des Watchers, sondern eine Frage der Zustaendigkeit:
# zwei Abholer an einer Warteschlange, von denen nur einer arbeitet.
#
# Einschalten, sobald der Watcher selbst der Bearbeiter ist - etwa wenn ein
# eigenes Harness die Auftraege uebernimmt:
#
#   WATCHER=1 ./start-termux.sh
#
# Er startet dann VOR uvicorn, weil `exec uvicorn` diese Shell ersetzt.
# Dass das Backend in den ersten Sekunden noch nicht antwortet, ist
# eingeplant: der Watcher schreibt einmal "Server nicht erreichbar - warte"
# ins Log und meldet sich wieder, sobald er durchkommt. Ein zweiter Aufruf
# startet keinen zweiten Watcher - die PID-Datei faengt das ab.
if [ "${WATCHER:-0}" = "1" ]; then
    echo
    echo "── Watcher ────────────────────────────────────"
    if [ -x "$PROJEKT/termux-hermes-watcher.sh" ]; then
        # HERMES_API aus PORT ableiten. Sonst pollt der Watcher stur auf
        # 8080, waehrend der Server auf einem anderen Port lauscht — und
        # meldet dann stundenlang "Server nicht erreichbar".
        HERMES_API="http://127.0.0.1:$PORT" "$PROJEKT/termux-hermes-watcher.sh"
    else
        echo "⚠️  termux-hermes-watcher.sh fehlt oder ist nicht ausfuehrbar."
        echo "    Nachholen mit: chmod +x $PROJEKT/termux-hermes-watcher.sh"
    fi
    # Der Watcher haengt nicht an dieser Sitzung (setsid) und laeuft weiter,
    # wenn der Server mit Strg+C endet. Beim naechsten Start faellt das nicht
    # auf, weil er sich dann einfach wieder verbindet.
    echo "Stoppen:  ./termux-hermes-watcher.sh stop"
    echo "Nachsehen: ./termux-hermes-watcher.sh status"
fi

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
