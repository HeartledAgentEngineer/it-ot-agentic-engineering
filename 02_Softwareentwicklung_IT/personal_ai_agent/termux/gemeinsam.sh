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
# Geoeffnet wird die native App "Hey Agent" (android/, seit 29.09.2026) ueber
# ihre eigene Adresse heyagent://start - kein Browser mehr (Sebastians Wunsch
# 29.09.2026, die alte Chrome-Web-App ist geloescht). Eine Adresse loest
# Android immer auf, auch wenn Termux die App als Paket nicht sehen darf.
# Scheitert der Start, steht die Meldung von Android im Terminal.
oberflaeche_oeffnen() {
    _am_ausgabe="$(am start -a android.intent.action.VIEW -d "heyagent://start" 2>&1)" && {
        echo "✔ Hey Agent geoeffnet"
        return 0
    }
    melde "Hey Agent liess sich nicht oeffnen - bitte die App von Hand antippen"
    printf '%s\n' "$_am_ausgabe" | head -4 | sed 's/^/    /'
    return 1
}

# ── Meldungen ───────────────────────────────────────────────────────────
# Ein Widget-Druck oeffnet die Session oft nur kurz. termux-toast blendet
# die Meldung deshalb ueber allem ein; fehlt termux-api, bleibt es beim
# Terminal.
melde() {
    echo "$1"
    command -v termux-toast >/dev/null 2>&1 && termux-toast -g middle "$1"
}
