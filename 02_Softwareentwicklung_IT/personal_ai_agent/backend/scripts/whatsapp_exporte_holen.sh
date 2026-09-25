#!/usr/bin/env bash
# Holt WhatsApp-Chatexporte vom Handy (USB) in das Archiv.
#
# Warum es diesen Umweg gibt: WhatsApp verschluesselt seine Datenbank
# (msgstore.db.crypt14, ~68 MB) - ohne Root ist sie nicht lesbar. Der
# eingebaute "Chat exportieren"-Weg liefert dagegen reinen Text, und fuer
# das Auslesen liegt im Archiv bereits ein vollstaendiger Adapter
# (src/adapters/whatsapp.py, 19 Tests).
#
# Arbeitsweise: passt auf /sdcard/Download auf, zieht jede neue Datei
# "WhatsApp*Chat*mit*.txt" byte-genau nach raw/whatsapp/ und meldet jeden
# Fund. Nichts wird auf dem Handy geloescht - der Nutzer entscheidet
# selbst, wann er den geteilten Download-Ordner aufraeumt.
#
# Aufruf:   bash backend/scripts/whatsapp_exporte_holen.sh [--einmal] [--sekunden N]
# Ohne --einmal laeuft es als Wache weiter, bis es abgebrochen wird.

set -u

GERAET="${GERAET:-ZY22K9RGLQ}"
SEKUNDEN="${SEKUNDEN:-30}"
HANDY_ORDNER="${HANDY_ORDNER:-/sdcard/Download}"
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ZIEL="$HIER/Chats von GPT, GEMINI, Claude/raw/whatsapp"
MANIFEST="$ZIEL/.geholt.txt"

EINMAL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --einmal)    EINMAL=1 ;;
    --sekunden)  shift; SEKUNDEN="$1" ;;
  esac
  shift
done

mkdir -p "$ZIEL"
touch "$MANIFEST"

meldung() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$1"; }

hole_neue() {
  # Dateinamen auf dem Handy einsammeln (nur Exporte von WhatsApp)
  local liste
  liste="$(adb -s "$GERAET" shell "ls $HANDY_ORDNER 2>/dev/null" | tr -d '\r' \
           | grep -iE '\.txt$' | grep -iE 'whatsapp.*chat.*mit' || true)"
  [ -z "$liste" ] && return 0

  local name ziel schon groesse_handy groesse_pc
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    ziel="$ZIEL/$name"
    schon="$(grep -Fx "$name" "$MANIFEST" 2>/dev/null || true)"
    [ -n "$schon" ] && continue

    # Groesse auf dem Handy merken, holen, Groessen vergleichen
    groesse_handy="$(adb -s "$GERAET" shell "stat -c %s '$HANDY_ORDNER/$name' 2>/dev/null" | tr -d '\r' | head -1)"
    if ! adb -s "$GERAET" pull "$HANDY_ORDNER/$name" "$ziel" >/dev/null 2>&1; then
      meldung "FEHLER beim Holen: $name"
      continue
    fi
    groesse_pc="$(stat -c %s "$ziel" 2>/dev/null || echo 0)"
    if [ -n "$groesse_handy" ] && [ "$groesse_handy" != "$groesse_pc" ]; then
      meldung "UNVOLLSTAENDIG: $name (Handy $groesse_handy B, PC $groesse_pc B) - bleibt auf der Liste"
      continue
    fi
    echo "$name" >> "$MANIFEST"
    meldung "geholt: $name  ($((groesse_pc / 1024)) KB, byte-genau geprueft)"
  done <<< "$liste"
}

meldung "Wache laeuft (Geraet $GERAET, alle ${SEKUNDEN}s, Ziel: raw/whatsapp/)"
while true; do
  hole_neue
  [ "$EINMAL" = "1" ] && break
  sleep "$SEKUNDEN"
done
