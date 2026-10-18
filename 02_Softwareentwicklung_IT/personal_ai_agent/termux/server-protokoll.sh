#!/data/data/com.termux/files/usr/bin/bash
#
# server-protokoll.sh - EINE Stelle fuer den Pfad der Server-Protokolldatei
# (To-do Punkt 16, 18.10.2026).
#
# WARUM es diese Datei gibt:
# Frueher wurde der Server im Vordergrund gestartet; seine Ausgaben standen im
# Termux-Fenster. Seit er abgekoppelt im Hintergrund laeuft (damit er das
# Schliessen von Termux ueberlebt), landen sie nirgends sichtbar - Sebastian:
# "Frueher war es so, dass in Termux der Server gesteuert wurde und ich den
# Verlauf sehen konnte ... Das ist nicht mehr moeglich."
#
# Deshalb schreibt der Server jetzt in EINE gemeinsame Datei, die die
# Oberflaeche anzeigt. Wo sie liegt, steht NUR hier - nicht viermal in den
# Startwegen. Eingebunden (nicht aufgerufen) wird die Datei von
# termux/backend-starten.sh, der einzigen Startstelle: alle Startwege
# (Widget agent-start, App agent-ensure.sh, Terminal start-termux.sh,
# neu-start-nach-lauf.sh) rufen sie und erben den exportierten Wert.
#
# Der Pfad ist per Umgebung ueberschreibbar (AGENT_SERVER_PROTOKOLL) - das
# nutzen die Tests und ein abweichender Aufbau, ohne dass hier etwas zu
# aendern waere. Der Server selbst (backend/app/services/protokoll.py) liest
# genau diese Variable; ohne sie wird NICHT geschrieben (kein stiller
# Schreibzugriff in ein fremdes Heimverzeichnis).
#
# Geschrieben wird mit Zeitstempel und Rotation vom Server selbst
# (logging.handlers.RotatingFileHandler) - nicht durch Umleiten der Ausgabe:
# eine Umleitung mit Filter wuerde die Abkopplung (setsid) zerstoeren und den
# Server wieder an die Sitzung binden.

if [ -n "${AGENT_SERVER_PROTOKOLL:-}" ]; then
    SERVERPROTOKOLL="$AGENT_SERVER_PROTOKOLL"
elif [ -n "${HOME:-}" ]; then
    SERVERPROTOKOLL="$HOME/agent-server.log"
else
    SERVERPROTOKOLL=""
fi

if [ -n "$SERVERPROTOKOLL" ]; then
    export AGENT_SERVER_PROTOKOLL="$SERVERPROTOKOLL"
fi
