#!/data/data/com.termux/files/usr/bin/bash
#
# Regressionstest fuer die Selbstheilung des Start-Locks in termux/agent-start.
#
# Hintergrund: Bricht die Widget-Session waehrend der Kill-/Start-Phase ab
# (Android beendet die Session, Handy-Neustart, Strg+C), blieb der Lock frueher
# fuer immer liegen -> jeder Widget-Druck meldete nur noch "Ein agent-start
# laeuft gerade" und tat nichts ("Agent startet nicht mehr neu").
# Der Test schneidet die echte Lock-Logik aus agent-start heraus und prueft
# sie isoliert gegen einen temporaeren Projektordner.
#
# Aufruf:  bash termux/test_agent_start_lock.sh
# Exit 0 = alle Pruefungen gruen.

HIER="$(cd "$(dirname "$0")" && pwd)"
SRC="$HIER/agent-start"
BLOCK="$HOME/.agent_start_lock_block.sh"

echo "== 1) Syntaxpruefung von agent-start =="
if bash -n "$SRC"; then echo "  OK   bash -n (Exit 0)"; else echo "  FAIL Syntaxfehler"; exit 1; fi

echo "== 2) Lock-Logik im Einzeltest =="
python3 - "$SRC" "$BLOCK" <<'PY'
import sys
src, out = sys.argv[1], sys.argv[2]
lines = open(src).read().splitlines()
start = next(i for i, l in enumerate(lines) if l.startswith('_LOCK="$PROJEKT'))
end = next(i for i, l in enumerate(lines) if l.startswith('_pkill_server() {'))
if start >= end:
    raise SystemExit("Lock-Block in agent-start nicht gefunden")
open(out, 'w').write("\n".join(lines[start:end]) + "\n")
PY

bash -s <<'SH'
set -u
PROJEKT="$(mktemp -d)"
mkdir -p "$PROJEKT/termux"
source "$HOME/.agent_start_lock_block.sh"
LOCK="$PROJEKT/termux/.agent-start.lock"
fails=0
ck() { if [ "$2" = "$3" ]; then echo "  OK   $1 (=$2)"; else echo "  FAIL $1: erwartet $3, war $2"; fails=$((fails+1)); fi; }

# A) frischer Start darf den Lock nehmen und schreibt die PID
_lock_nehmen; ck "A frisch -> nehmen" $? 0
[ -f "$LOCK/pid" ] && A=1 || A=0; ck "A PID-Datei geschrieben" $A 1
# B) echter paralleler Start (lebender Halter) wird abgelehnt
_lock_nehmen; ck "B lebender Halter -> ablehnen" $? 1
_lock_loesen
# C) verwaist: Halter-PID tot
mkdir -p "$LOCK"; echo 999999 > "$LOCK/pid"
_lock_nehmen; ck "C tote PID -> uebernehmen" $? 0
_lock_loesen
# D) verwaist: leerer Alt-Lock (exakt der gemeldete Bugfall)
mkdir -p "$LOCK"
_lock_nehmen; ck "D leerer Alt-Lock -> uebernehmen" $? 0
_lock_loesen
# E) ueberaltert (>300s) trotz lebender PID
mkdir -p "$LOCK"; echo $$ > "$LOCK/pid"; echo $(( $(date +%s) - 400 )) > "$LOCK/zeit"
_lock_nehmen; ck "E ueberaltert -> uebernehmen" $? 0
_lock_loesen
# F) nach Freigabe ist der Lock weg -> naechster bewusster Neustart moeglich
[ -d "$LOCK" ] && F=0 || F=1; ck "F Lock nach Freigabe weg" $F 1

rm -rf "$PROJEKT"
echo "  --> Fehler: $fails"
exit $fails
SH
