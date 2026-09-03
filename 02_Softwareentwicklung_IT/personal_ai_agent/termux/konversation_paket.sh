#!/data/data/com.termux/files/usr/bin/bash
# Kopiert die letzte/n der conv_main-Nachrichten als "Paket" nach
# ~/hermes_inbox/letzte_nachricht.json, damit der Frontend-Poll sie anzeigt.
#
# Wunsch Sebastian (2026-09-01): paketweise Outputs per Cron spiegeln.
# Aufruf: konversation_paket.sh [anzahl]
set -u
PORT="${PORT:-8080}"
ANZAHL="${1:-3}"

URL="http://127.0.0.1:${PORT}/api/conversations/conv_main"
KEY="$(curl -s --max-time 5 http://127.0.0.1:${PORT}/api/konfig 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/')"
[ -z "$KEY" ] && exit 0

DATA="$(curl -s --max-time 8 -H "X-API-Key: $KEY" "$URL" 2>/dev/null)"
[ -z "$DATA" ] && exit 0

# Letzte ANZAHL Assistant-Nachrichten als Paket zusammenbauen (nur neueste).
# DATA in eine Tempo-Datei legen (Python-Heredoc wuerde sonst stdin ueberschreiben).
_TMP="$(mktemp /data/data/com.termux/files/usr/tmp/konvpaket.XXXXXX)"
printf '%s' "$DATA" > "$_TMP"
PAKET="$(python3 - "$ANZAHL" "$_TMP" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[2], encoding="utf-8") as f:
        d = json.load(f)
except Exception:
    sys.exit(0)
msgs = d.get('messages', []) if isinstance(d, dict) else d
ass = [m.get('content','').strip() for m in msgs if m.get('role')=='assistant' and (m.get('content') or '').strip()]
n = max(1, int(sys.argv[1]) if len(sys.argv)>1 else 3)
schleife = ass[-n:]
print('\n\n---\n\n'.join(schleife) if schleife else '')
PYEOF
)"
rm -f "$_TMP"

# Nur schreiben, wenn ein Paket existiert.
if [ -n "$PAKET" ]; then
    python3 - "$PAKET" <<'PYEOF'
import json, sys, uuid, time, os
text = sys.argv[1]
# Poll-Datei, die das Frontend /api/hermes/letzte liest -> Paket erscheint dort.
pfad = os.path.expanduser("~/hermes_inbox/letzte_nachricht.json")
os.makedirs(os.path.dirname(pfad), exist_ok=True)
with open(pfad, "w", encoding="utf-8") as f:
    f.write(json.dumps({"id": str(uuid.uuid4()), "text": text,
                        "zeit": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False))
PYEOF
    echo "paket geschrieben: $(date +%H:%M:%S)" >&2
fi