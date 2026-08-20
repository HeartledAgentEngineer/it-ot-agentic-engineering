#!/usr/bin/env bash
# git_stand.sh — Vor-Jede-Session-Stand des Git-Repos zeigen.
# Laeuft auf Windows (Git-Bash/MSYS) und Linux/Termux gleich.
#
# Zweck (AGENTS.md "Dokumentation folgt dem Code" + Sync-Routine):
#   Vor dem Arbeiten/Committen/Pushen klar machen, wo der aktuelle Stand ist:
#   branch, letzter commit, ahead/behind zu origin, uncommittete dateien.
#   Wer falsch pusht, erzeugt nur Konflikte — dieses Skript sagt vorher, ob
#   gepullt werden muss.
#
# Sicherheit: IM GRUNDMODUS read-only (nur `git fetch` aktualisiert remote-ref
# lokal; das ist gefahrlos). Ein EXPLIZITES `pull`-Argument wird gepullt.
# Push macht dieses Skript NIEMALS autonom — Push bleibt bei Sebastian.

set -e
# --- Pfad: eigenes Repo-Wurzel; sonst aktuelles Verzeichnis ------------
REPO="${1:-.}"
cd "$REPO" || { echo "Ordner nicht gefunden: $REPO"; exit 1; }

echo "==========================================================="
echo " Git-Stand  |  $(basename "$(pwd)")"
echo "==========================================================="

# 1) Branch
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
echo " Branch:          $BR"

# 2) letzter lokaler commit
echo " Letzter Commit:  $(git log -1 --format='%h  %s  (%cI)' 2>/dev/null || echo 'keiner')"

# 3) remote status (ahead/behind) — fetch ist gefahrlos
git fetch origin >/dev/null 2>&1
UPSTREAM="origin/${BR}"
BEHIND=$(git rev-list --count "HEAD..${UPSTREAM}" 2>/dev/null || echo "?")
AHEAD=$(git rev-list --count "${UPSTREAM}..HEAD" 2>/dev/null || echo "?")
echo " Ahead (lokal neu):   $AHEAD"
echo " Behind (remote neu): $BEHIND"

# 4) uncommittet
UNCOMMITTED=$(git status --short 2>/dev/null | wc -l)
echo " Uncommittet/neu: $UNCOMMITTED (siehe Zeilen unt.)"
git status --short 2>/dev/null | sed 's/^/    /'

# 5) Empfehlung (laut Sync-Routine)
if [ "${BEHIND:-0}" != "0" ] && [ "${BEHIND:-0}" != "?" ]; then
  echo
  echo " >>> WICHTIG: remote hat $BEHIND neuen Commit(s). VOR dem Arbeiten/Pushen"
  echo "     'git pull --rebase' ausfuehren (oder --pull benutzen)."
fi
if [ "${AHEAD:-0}" != "0" ] && [ "${AHEAD:-0}" != "?" ]; then
  echo " >>> Hinweis: lokal $AHEAD neu. Diese sind noch NIE gepusht (push bleibt bei dir)."
fi
echo "==========================================================="

# Optional: pull vor Session
if [ "${1:-}" = "--pull" ]; then
  echo "--> Pull --rebase wird ausgefuehrt..."
  git pull --rebase origin main 2>&1
  echo "--> Fertig."
fi
exit 0