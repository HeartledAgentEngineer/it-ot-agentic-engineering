#!/data/data/com.termux/files/usr/bin/bash
# Streamt einen Text von DIESER Termux-Hermes-Session an den Frontend-Chat.
#
# Wunsch Sebastian (2026-09-01): Jede Antwort dieser Session erscheint live,
# nachrichtenweise zeichengestreamt (SSE, Frontend-Design) im Frontend-Chat.
#
# Aufruf:
#   stream_an_frontend.sh "Mein Antworttext ..."     (Argument)
#   echo "Text" | stream_an_frontend.sh              (Stdin, bei Sonderzeichen)
#
# Der Text laeuft ueber POST /api/hermes/stream in den conv_main-Dialog.

set -u

TEXT="${1:-}"
DELAY="${2:-120}"

# Falls kein Argument: von stdin lesen (sauber bei mehrzeiligen/UMlaut-Texten).
if [ -z "$TEXT" ] && [ ! -t 0 ]; then
    TEXT="$(cat)"
fi

if [ -z "$TEXT" ]; then
    echo "kein text (wie nutze ich?): stream_an_frontend.sh 'text' ODER echo 'text' | stream_an_frontend.sh" >&2
    exit 2
fi

PORT="${PORT:-8080}"
URL="http://127.0.0.1:${PORT}/api/hermes/stream"

# API-Key aus der Einstellungsdatei (P0, 12.10.2026; der frühere Weg über den
# Server ist entfernt). backend/.env geht vor, wie im Backend.
PROJEKT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
KEY="$(bash "$PROJEKT/termux/api-schluessel.sh" "$PROJEKT/backend/.env" 2>/dev/null)" \
    || KEY="$(bash "$PROJEKT/termux/api-schluessel.sh" "$PROJEKT/.env" 2>/dev/null)" \
    || KEY=""
[ -n "$KEY" ] || echo "stream_an_frontend: kein API_KEY in der Einstellungsdatei - Abruf ohne Schluessel." >&2

# JSON-sicher einpacken (Umlaute, Zeilenumbrueche).
JSON_BODY="$(python3 - "$TEXT" "$DELAY" <<'PYEOF'
import json, sys
text = sys.argv[1]
delay = int(sys.argv[2]) if len(sys.argv) > 2 else 120
print(json.dumps({"text": text, "conversation_id": "conv_main", "delay_ms": delay}, ensure_ascii=False))
PYEOF
)"

echo "── streame ${#TEXT} Zeichen an Frontend-Chat (conv_main) ──" >&2
curl -s -N -X POST -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
     --data-binary "$JSON_BODY" "$URL" >/dev/null
echo "fertig." >&2