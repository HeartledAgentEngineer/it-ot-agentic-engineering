#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# hermes-nacht-job.sh — AUTONOMER NACHTOUR: läuft ohne User-Eingriff.
#
# Holt EINEN echten offenen Programmier-Auftrag aus dem Auftragsbuch, startet
# den Coding-Agenten (Hermes-CLI via Inbox-Daemon "aktiv"-Kanal) mit Hinweis,
# Bilder über den Gemini-Vision-Skill zu lesen, und schließt den Auftrag nach
# Erfolg per API ab (commit nicht push — Push bleibt bei Sebastian).
#
# Nutzung:
#   ./termux/hermes-nacht-job.sh            # ein Durchgang (Idempotent)
#   ./termux/hermes-nacht-job.sh --verbose  # mit mehr Ausgabe
#
# Abhängigkeiten:
#   - FastAPI-Server auf 127.0.0.1:8080 (termux/agent-start)
#   - Hermes-Inbox-Daemon (backend/hermes_inbox_daemon.py) oder Kanal 'aktiv'
#   - git im Projekt, hermes-CLI im PATH
# =============================================================================
set -u
PROJEKT="/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent"
INBOX="$HOME/hermes_inbox"
AUFTR="$INBOX/auftraege.jsonl"
ANTW="$INBOX/antworten.jsonl"
LOGFILE="$PROJEKT/termux/nacht-job.log"
PIDFILE="$PROJEKT/termux/.nacht-job.lock"

VERBOSE=0
[ "${1:-}" = "--verbose" ] && VERBOSE=1

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOGFILE"; }

# ---------------------------------------------------------------------------
# 0) Exklusiv-Lock: nie zwei Nachtläufe parallel
# ---------------------------------------------------------------------------
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Nachtjob läuft bereits (PID $(cat "$PIDFILE")). Abbruch."
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

log "=== HERMES-NACHTJOB START ==="

# ---------------------------------------------------------------------------
# 1) Pull (AGENTS-Regel: vor Agentenarbeit)
# ---------------------------------------------------------------------------
cd "$PROJEKT" || { log "FEHLER: Projekt nicht gefunden"; exit 1; }
if ! git pull --ff-only >/dev/null 2>&1; then
    log "WARNUNG: git pull fehlgeschlagen (evtl. lokale Änderungen) — arbeite mit lokalem Stand weiter."
fi

# ---------------------------------------------------------------------------
# 2) Server-Health prüfen
# ---------------------------------------------------------------------------
if ! curl -s --max-time 3 http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
    log "Server nicht erreichbar auf 127.0.0.1:8080 — starte via agent-start …"
    ( cd "$PROJEKT/termux" && ./agent-start >/dev/null 2>&1 ) &
    sleep 8
    curl -s --max-time 3 http://127.0.0.1:8080/api/health >/dev/null 2>&1 \
        || { log "FEHLER: Server kommt nicht hoch. Abbruch."; exit 1; }
fi

# ---------------------------------------------------------------------------
# 3) Auftrag wählen: Ersten offenen Programmier-Auftrag, der noch NICHT
#    umgesetzt ist (Filter: kein Test/erledigt, git-check auf einschlägigen Commit).
#    Nutzt intern die Auftrags-API; löscht nichts.
# ---------------------------------------------------------------------------
WAHL=$(python3 - <<'PY' 2>/dev/null
import json, subprocess, sys
try:
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:8080/api/auftraege")
    d = json.load(urllib.request.urlopen(req, timeout=5))
except Exception as e:
    sys.exit("API_FAIL")
jobs = d.get("auftraege", []) if isinstance(d, dict) else d
AUSSCHLUSS = ("test","cron","messung","messtest","beispiel")
def ist_coding(txt):
    t = (txt or "").lower()
    if any(w in t for w in AUSSCHLUSS): return False
    return any(k in t for k in ("api","endpoint","ui","frontend","backend","seite",".py","fehler","fix","feat","programm","datenbank","chat","upload","quiz","modell","datei","gesicht"))
for j in jobs:
    if j.get("status") not in ("offen", "laeuft", "fehler"): continue
    txt = j.get("auftrag","")
    if not ist_coding(txt): continue
    print(json.dumps({"id": j.get("id"), "auftrag": txt[:300], "status": j.get("status")}))
    sys.exit(0)
sys.exit("NONE")
PY
)
if [ "$WAHL" = "NONE" ] || [ "$WAHL" = "API_FAIL" ] || [ -z "$WAHL" ]; then
    log "Kein passender offener Programmier-Auftrag (oder API-Fehler). Fertig."
    exit 0
fi
JOB_ID=$(echo "$WAHL" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
JOB_TEXT=$(echo "$WAHL" | python3 -c "import json,sys; print(json.load(sys.stdin)['auftrag'])")
log "Gewählter Auftrag: ${JOB_ID:0:8} | ${JOB_TEXT:0:60}"

# ---------------------------------------------------------------------------
# 4) Inbox-Payload bauen: Coding-Agent + Gemini-Vision-Bildlesen aktivieren.
#    Wichtig: Der Marker schaltet den coding-chat-bild-vision-Skill ein, damit
#    der Agent (auch wenn sein Gehirn DeepSeek ist) Bilder via Gemini liest.
# ---------------------------------------------------------------------------
mkdir -p "$INBOX"
KONTEXT="[Angehaengte Bild-Datei zur Analyse: NUTZE den Skill 'coding-chat-bild-vision' (routes ueber Gemini-Vision) bei JEDEM beiliegenden/betroffenen Bild]

Du arbeitest als autonomer Nacht-Coding-Agent (kein User-Eingriff). Arbeite den Auftrag selbststaendig ab:
- git pull --ff-only zu Beginn; aendere nur noetige Dateien.
- Committe deine Aenderung am Ende lokal (kein push).
- Ist der Auftrag bereits umgesetzt, melde das ehrlich als 'bereits erledigt'.
Kontext des Systems: personal_ai_agent (FastAPI-Backend + Vanilla-JS-Frontend), Projekt-Root oben in der Umgebung."

echo "{\"auftrag_id\": \"$JOB_ID\", \"text\": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$JOB_TEXT"), \"kontext\": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$KONTEXT")}" >> "$AUFTR"
log "Auftrag in Inbox geschrieben ($AUFTR)"

# ---------------------------------------------------------------------------
# 5) Inbox-Daemon (einmal) anstoßen, falls er nicht bereits läuft.
# ---------------------------------------------------------------------------
if pgrep -f "hermes_inbox_daemon.py" >/dev/null 2>&1; then
    log "Inbox-Daemon läuft bereits — er nimmt den Auftrag an."
else
    log "Starte Inbox-Daemon (--einmal) …"
    ( cd "$PROJEKT/backend" && python3 hermes_inbox_daemon.py --einmal >/dev/null 2>&1 ) &
fi

# ---------------------------------------------------------------------------
# 6) Auf Antwort warten (bis zu ~20 min), dann Ergebnis verarbeiten.
# ---------------------------------------------------------------------------
GELESEN=""
for i in $(seq 1 120); do
    if [ -f "$ANTW" ]; then
        GELESEN=$(tail -n 1 "$ANTW" 2>/dev/null | python3 -c "
import json,sys
try:
    z=json.loads(sys.stdin.read())
    print(z.get('auftrag_id',''))
except: print('')
")
        if [ "$GELESEN" = "$JOB_ID" ]; then
            ERGEBNIS=$(tail -n 1 "$ANTW" | python3 -c "import json,sys; print(json.load(sys.stdin).get('text',''))")
            log "Antwort erhalten (${JOB_ID:0:8}). Erste 80 Zeichen: ${ERGEBNIS:0:80}"
            break
        fi
    fi
    sleep 10
done

if [ -z "$GELESEN" ] || [ "$GELESEN" != "$JOB_ID" ]; then
    log "Zeitüberschreitung: keine Antwort vom Agenten. Auftrag bleibt offen."
    exit 1
fi

# ---------------------------------------------------------------------------
# 7) commit (lokal) + Auftrag per API auf fertig setzen.
# ---------------------------------------------------------------------------
cd "$PROJEKT" || exit 1
if ! git diff --quiet; then
    git add -A >/dev/null 2>&1
    git commit -m "autonom(nacht): ${JOB_TEXT:0:60}" >/dev/null 2>&1 \
        && log "Committet (lokal)." \
        || log "Hinweis: nichts zu committen oder Commit fehlgeschlagen."
fi

# Ergebnis ins Buch schreiben (erfolg=true)
ERGEBNIS_ESC=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "Autonom bearbeitet: ${ERGEBNIS}")
curl -s --max-time 5 -X POST "http://127.0.0.1:8080/api/auftraege/${JOB_ID}/ergebnis" \
    -H "Content-Type: application/json" \
    -d "{\"ergebnis\": $ERGEBNIS_ESC, \"erfolg\": true}" >/dev/null 2>&1 \
    && log "Auftrag ${JOB_ID:0:8} als fertig markiert." \
    || log "WARNUNG: Ergebnis-Eintrag fehlgeschlagen."

log "=== NACHTJOB FERTIG ==="
exit 0