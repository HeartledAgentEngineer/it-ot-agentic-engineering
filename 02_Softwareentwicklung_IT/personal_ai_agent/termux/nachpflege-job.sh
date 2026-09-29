#!/data/data/com.termux/files/usr/bin/bash
#
# nachpflege-job.sh — naechtliche Nachpflege des Archiv-Index, OHNE PC.
#
# Warum es dieses Skript gibt
# ===========================
# Das Werkzeug backend/scripts/archiv_nachpflege.py (Schritt N22) pflegt einen
# BESTEHENDEN Archiv-Index inkrementell nach (nur anhaengen, idempotent). Es
# laeuft aber nur, wenn jemand es startet. Schritt N23 verankert den Lauf im
# Android-Oekosystem: das Handy pflegt sich nachts selbst, auch wenn der PC aus
# ist. Dieses Skript ist der eigentliche Nachtjob; eingerichtet wird er von
# nachpflege-einrichten.sh (termux-job-scheduler oder crond).
#
# Grenzen (hart)
# ==============
# Erlaubt ist ausschliesslich: eigene Sperrdatei entfernen, eigenes Log kuerzen,
# eigene Berichtsdatei schreiben, Index ANHAENGEN (macht das Werkzeug). Verboten
# sind Loeschbefehle, das Verschieben oder Loeschen von Index, Archiv oder Fotos,
# jeder Datentransfer nach aussen und jeder Abruf von einer Gegenstelle (im
# Waechter-Test geprueft). Es wird nichts angelegt, wenn Quelle oder Index fehlen
# — dann eine ehrliche Zeile ins Log (Exit 3).
#
# Aufruf zum Testen (in Termux):  bash termux/nachpflege-job.sh
#
set -u

# Projektordner wie in termux/agent-ensure.sh bestimmen: den Widget-Symlink
# ~/.shortcuts/agent aufloesen (zeigt auf start-termux.sh). PROJEKT ist
# ueberschreibbar.
if [ -z "${PROJEKT:-}" ]; then
    verweis="$HOME/.shortcuts/agent"
    if [ -L "$verweis" ]; then
        ziel="$(readlink "$verweis")"
        PROJEKT="$(cd "$(dirname "$ziel")" 2>/dev/null && pwd)"
    fi
fi

LOG="$HOME/nachpflege.log"
LOCK="$HOME/.nachpflege.lock"

# Log begrenzen (nur die letzten 500 Zeilen behalten) — gleiches Muster wie
# termux/agent-ensure.sh: erst bei > 200 KB kuerzen.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 204800 ]; then
    tail -n 500 "$LOG" > "$LOG.neu" 2>/dev/null && mv -f "$LOG.neu" "$LOG"
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
}

# ── Sperre gegen Doppellaeufe (atomar per mkdir, wie termux/agent-start) ──────
# Der Lock traegt einen Zeitstempel. Eine EIGENE, veraltete Sperre (aelter als
# 6 Stunden = 21600 s) wird entfernt — nur die eigene Sperrdatei, sonst nichts.
# Entfernt wird ohne rekursives Loeschen: die Zeitdatei weg, dann rmdir des
# leeren Ordners.
_sperre_loesen() {
    rm -f "$LOCK/zeit" 2>/dev/null
    rmdir "$LOCK" 2>/dev/null
}
sperre_nehmen() {
    mkdir "$LOCK" 2>/dev/null && {
        date +%s > "$LOCK/zeit" 2>/dev/null
        return 0
    }
    _zeit="$(cat "$LOCK/zeit" 2>/dev/null || true)"
    _alt=0
    [ -n "$_zeit" ] && _alt=$(( $(date +%s) - _zeit ))
    if [ -n "$_zeit" ] && [ "$_alt" -gt 21600 ]; then
        _sperre_loesen
        if mkdir "$LOCK" 2>/dev/null; then
            date +%s > "$LOCK/zeit" 2>/dev/null
            log "veraltete eigene Sperre (aelter als 6 h) entfernt - Lauf uebernommen"
            return 0
        fi
    fi
    return 1
}

if ! sperre_nehmen; then
    log "Ein Nachpflege-Lauf laeuft schon (Sperre $LOCK) - nichts zu tun."
    exit 0
fi
trap '_sperre_loesen' EXIT INT TERM

# CPU nicht einschlafen lassen (wie die Nachbarskripte).
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# ── Quelle und Index bestimmen ────────────────────────────────────────────────
# Kandidaten in dieser Reihenfolge; ARCHIV_QUELLE/ARCHIV_INDEX schlagen alles.
QUELLE="${ARCHIV_QUELLE:-}"
if [ -z "$QUELLE" ]; then
    for k in "$HOME/archiv/db/memory.db" \
             "$HOME/db/memory.db" \
             "$HOME/Chats von GPT, GEMINI, Claude/db/memory.db"; do
        [ -f "$k" ] && QUELLE="$k" && break
    done
fi
INDEX="${ARCHIV_INDEX:-$HOME/archiv_index.db}"

# Fehlt eine der beiden: ehrliche Zeile + Exit 3, es wird NICHTS angelegt.
if [ -z "$QUELLE" ] || [ ! -f "$QUELLE" ]; then
    log "Quelle fehlt: keine memory.db gefunden (ARCHIV_QUELLE setzen). Nichts angelegt."
    exit 3
fi
if [ ! -f "$INDEX" ]; then
    log "Index fehlt: $INDEX nicht gefunden (ARCHIV_INDEX setzen). Nichts angelegt."
    exit 3
fi

if [ -z "${PROJEKT:-}" ] || [ ! -f "$PROJEKT/backend/scripts/archiv_nachpflege.py" ]; then
    log "FEHLER: Projektordner oder Werkzeug nicht gefunden (PROJEKT='${PROJEKT:-}')."
    exit 1
fi

# ── Bericht fuer den PC vorbereiten ───────────────────────────────────────────
# Der Termux-Heimordner ist ueber ADB nicht lesbar — deshalb liegt der Bericht
# im freigegebenen Download-Ordner (dasselbe Muster wie die anderen Skripte).
# Aus dem Pfad wird nur der Dateiname gemeldet (Maske) und die Groesse in MB,
# kein Pfad, kein Inhalt, kein Geheimnis.
BERICHT_BASIS="$HOME/storage/downloads"
[ -d "$BERICHT_BASIS" ] || BERICHT_BASIS="/sdcard/Download"
BERICHT_ORDNER="$BERICHT_BASIS/hermes_diag"
mkdir -p "$BERICHT_ORDNER" 2>/dev/null
BERICHT="$BERICHT_ORDNER/nachpflege_letzte.txt"

QUELLE_MASKE="$(basename "$QUELLE")"
INDEX_MB=$(( $(wc -c < "$INDEX" 2>/dev/null || echo 0) / 1048576 ))

# ── Lauf: Werkzeug aufrufen ───────────────────────────────────────────────────
start_zeit="$(date '+%Y-%m-%dT%H:%M:%S')"
log "Nachpflege startet: Quelle=$QUELLE_MASKE Index=$INDEX (${INDEX_MB} MB)"

cd "$PROJEKT" || { log "FEHLER: Projektordner nicht gefunden"; exit 1; }

python "$PROJEKT/backend/scripts/archiv_nachpflege.py" \
    --quelle-db "$QUELLE" \
    --index "$INDEX" \
    --schreiben --mit-vektoren >> "$LOG" 2>&1
rc=$?

# Exit 3 = kein OpenRouter-Schluessel. Dann EINMAL ohne --mit-vektoren
# wiederholen, damit der Text trotzdem in den Index kommt (nur ohne Vektor).
if [ "$rc" = "3" ]; then
    log "kein OpenRouter-Schluessel (Exit 3) - wiederhole ohne --mit-vektoren (Text kommt trotzdem in den Index)"
    python "$PROJEKT/backend/scripts/archiv_nachpflege.py" \
        --quelle-db "$QUELLE" \
        --index "$INDEX" \
        --schreiben >> "$LOG" 2>&1
    rc=$?
fi

# ── Bericht schreiben (Kopfzeile + letzte 50 Log-Zeilen) ──────────────────────
zeit="$(date '+%Y-%m-%dT%H:%M:%S')"
INDEX_MB=$(( $(wc -c < "$INDEX" 2>/dev/null || echo 0) / 1048576 ))
{
    printf 'nachpflege_bericht %s quelle=%s index_mb=%s exit=%s\n' \
        "$zeit" "$QUELLE_MASKE" "$INDEX_MB" "$rc"
    tail -n 50 "$LOG" 2>/dev/null
} > "$BERICHT" 2>/dev/null

if [ "$rc" != "0" ]; then
    log "Nachpflege endete mit Exit $rc (Bericht: $BERICHT)"
    exit "$rc"
fi

log "Nachpflege fertig (seit $start_zeit), Bericht: $BERICHT"
exit 0
