#!/data/data/com.termux/files/usr/bin/bash
#
# Gemeinsame Grundlagen fuer die Widget-Skripte. Wird eingebunden, nicht
# direkt aufgerufen. Das einbindende Skript setzt vorher HIER auf den
# Ordner, in dem es wirklich liegt.

set -u

# Der Projektordner ist immer der Elternordner von termux/. Damit ist egal,
# wohin das Repo geklont wurde.
PROJEKT="$(cd "$HIER/.." && pwd)"
PORT="${PORT:-8080}"
URL="http://localhost:$PORT"

# ── Laeuft der Agent schon? ─────────────────────────────────────────────
# Gefragt wird der Server selbst, nicht eine Prozessliste: Nur wer auf
# /api/health antwortet, ist wirklich bereit. Ein Prozess, der noch die
# Vektordatei laedt, wuerde sonst als fertig gelten.
agent_antwortet() {
    curl -s --max-time 2 "$URL/api/health" >/dev/null 2>&1
}

# ── Oberflaeche oeffnen ─────────────────────────────────────────────────
# Ist die PWA installiert, faengt sie den Aufruf ab und oeffnet sich selbst
# statt des Browsers — genau das gewuenschte "App, die keine App ist".
oberflaeche_oeffnen() {
    if command -v termux-open-url >/dev/null 2>&1; then
        termux-open-url "$URL" >/dev/null 2>&1 && return 0
    fi
    am start -a android.intent.action.VIEW -d "$URL" >/dev/null 2>&1
}

# ── Meldungen ───────────────────────────────────────────────────────────
# Ein Widget-Druck oeffnet die Session oft nur kurz. termux-toast blendet
# die Meldung deshalb ueber allem ein; fehlt termux-api, bleibt es beim
# Terminal.
melde() {
    echo "$1"
    command -v termux-toast >/dev/null 2>&1 && termux-toast -g middle "$1"
}
