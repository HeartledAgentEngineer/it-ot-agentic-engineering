#!/data/data/com.termux/files/usr/bin/bash
#
# Startskript fuer Termux — holt Updates und startet den Server.
#
# Einrichtung einmalig:
#   pkg install termux-api          # fuer den Weckruf-Sperrmechanismus
#   mkdir -p ~/.shortcuts
#   ln -sf ~/personal_ai_agent/start-termux.sh ~/.shortcuts/agent
#   chmod +x ~/personal_ai_agent/start-termux.sh
#
# Danach: Termux:Widget aus F-Droid installieren, Widget auf den
# Startbildschirm legen, "agent" antippen. Ein Druck holt den neuen Stand
# und startet den Server — kein Tippen mehr.
#
# Der Weg ueber ~/.shortcuts ist Absicht: Termux:Widget zeigt genau die
# Skripte dort an, und ein Symlink bleibt aktuell, wenn das Repo sich
# aendert. Eine Kopie waere sofort veraltet.

set -u

# Der Projektordner ist der Ordner, in dem dieses Skript liegt. Ueber
# ~/.shortcuts ist $0 ein Symlink, der zuerst aufgeloest werden muss.
#
# Vorher stand hier fest $HOME/personal_ai_agent. Das passte nie zur
# Anleitung, die das Repo nach ~/it-ot-agentic-engineering/... klont — das
# Skript brach also gleich in der ersten Zeile ab. Selbst herausfinden, wo
# man liegt, geht immer; raten geht schief.
skript="$0"
[ -L "$skript" ] && skript="$(readlink "$skript")"
PROJEKT="${PROJEKT:-$(cd "$(dirname "$skript")" && pwd)}"
PORT="${PORT:-8080}"

cd "$PROJEKT" || { echo "Projektordner nicht gefunden: $PROJEKT"; exit 1; }

echo "── Aktualisieren ──────────────────────────────"
# Synchronisation MIT Vergleich (kein blinder Reset): Es kann sein, dass
# vom HANDY aus entwickelt wurde (z. B. im Urlaub) — dann ist der Handy-Stand
# neuer und darf NICHT überschrieben werden.
#   - Handy liegt VOR origin (Handy neuere Commits)  → push (Entwicklung hoch)
#   - Handy liegt HINTER origin (PC neuere Commits)  → pull --ff-only
#   - echte Divergenz (beide eigene Commits)         → NICHT blind resetten,
#     sondern anhalten + Hinweis (Nutzer entscheidet).
if git fetch origin --quiet 2>/dev/null; then
    if git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
        echo "📤 Handy-Stand ist neuer – push (Urlaub-Entwicklung wird hochgeladen)"
        git push origin HEAD:main && echo "Stand: $(git log --oneline -1)"
    elif git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
        git pull --ff-only --quiet && echo "Stand: $(git log --oneline -1)" || {
            echo "⚠️  Pull fehlgeschlagen – Server startet mit dem alten Stand. Lokale Änderungen:"
            git status --short 2>/dev/null | head -8
        }
    else
        echo
        echo "⚠️  Echte Divergenz: Handy UND Remote haben eigene Commits."
        echo "    Nicht blind überschreiben. Nachsehen mit: git log --oneline --graph -5"
        echo
    fi
else
    echo
    echo "⚠️  git fetch fehlgeschlagen (Netz?) – Server startet mit dem alten Stand."
    echo
fi
echo "Stand jetzt: $(git log --oneline -1 2>/dev/null | cut -c1-70)"

# Hey-Agent-App: Starteintrag in $PREFIX/etc/profile.d anlegen/erneuern, damit die
# App das Backend selbst starten kann (wiederholbar, siehe termux/hey-agent-einrichten.sh).
# Darf den Serverstart nie verhindern.
if [ -f "$PROJEKT/termux/hey-agent-einrichten.sh" ]; then
    sh "$PROJEKT/termux/hey-agent-einrichten.sh" 2>&1 | head -2 | sed 's/^/  /' || true
fi

# Speicherzugriff einmalig/einrichten (idempotent): legt ~/storage an (Symlinks
# zu Download/DCIM/Documents...) für die Handy-Dateisuche. Muss nur beim ersten
# Mal + nach Termux-Neuinstallation laufen; hier im Start ist es selbstheilend.
# Fehlt die Android-Berechtigung, erscheint der System-Dialog — das Skript
# bricht NICHT ab, der Server startet trotzdem (Dateisuche dann eben ohne).
command -v termux-setup-storage >/dev/null 2>&1 && termux-setup-storage

# ── Archiv-Index übernehmen (selbstheilend) ───────────────────────────────────
# Der übertragbare Wissensspeicher-Index ist zu groß, um ihn über Git zu
# transportieren, und ADB kann nicht in den Termux-Heimordner schreiben
# (App-Sandbox). Deshalb wird er per Kabel nach /sdcard/Download/ geschoben —
# und hier beim Start nach ~/ geholt. Der Server sucht ihn dort.
# Ein schon vorhandener Index wird NICHT gelöscht, sondern als
# ~/archiv_index_alt.db beiseitegelegt (Rückweg bleibt offen).
QUELLE_INDEX="$HOME/storage/downloads/archiv_index.db"
[ -f "$QUELLE_INDEX" ] || QUELLE_INDEX="/sdcard/Download/archiv_index.db"
if [ -f "$QUELLE_INDEX" ]; then
    echo "── Archiv-Index übernehmen ────────────────────"
    if [ -f "$HOME/archiv_index.db" ]; then
        mv -f "$HOME/archiv_index.db" "$HOME/archiv_index_alt.db" \
            && echo "  · vorheriger Index liegt jetzt als ~/archiv_index_alt.db"
    fi
    if mv "$QUELLE_INDEX" "$HOME/archiv_index.db" 2>/dev/null; then
        echo "  ✔ übernommen: ~/archiv_index.db ($(du -h "$HOME/archiv_index.db" 2>/dev/null | cut -f1))"
    else
        echo "  ⚠ Übernahme fehlgeschlagen ($QUELLE_INDEX) – Server startet trotzdem."
    fi
fi

# ── Nachpflege-Job einrichten (selbstheilend, idempotent) ─────────────────────
# Warum hier: Das Handy soll den Archiv-Index nachts selbst nachpflegen (N22/N23),
# auch wenn der PC aus ist. Vom PC aus lässt sich auf dem Handy KEIN Befehl
# starten (gemessen: adb shell am startservice ... com.termux.RUN_COMMAND →
# „Error: Not found; no service started."; adb shell run-as com.termux →
# „package not debuggable"). Der einzige Weg aufs Handy ist dieser Widget-Tipp.
# Deshalb richtet der Start den Job einmalig ein; ist er schon eingerichtet,
# tut das Einricht-Skript nichts (die Idempotenz sitzt dort).
# Der Aufruf steht bewusst NACH dem Git-Abgleich und NACH dem Index-Block,
# damit der Job auf den frisch übernommenen Index geht.
# Mit „|| true": die Einrichtung darf den Serverstart NIEMALS verhindern.
bash "$PROJEKT/termux/nachpflege-einrichten.sh" || true

# ── pCloud-Zugang übernehmen (selbstheilend) ─────────────────────────────────
# pCloud-Zugang aus dem Download-Ordner in backend/.env uebernehmen — eine
# gemeinsame Quelle fuer alle drei Startwege (start-termux.sh, Widget
# agent-start, App agent-ensure.sh; Issue #3 Befund 1, 02.10.2026). Darf den
# Start nie verhindern (|| true); fehlt die Datei, passiert nichts.
bash "$PROJEKT/termux/pcloud-schluessel-uebernehmen.sh" "backend/.env" || true
# Vorlese-Schluessel (OPENROUTER_TTS_KEY, 06.10.2026) auf demselben Weg - vom PC
# gelegt mit tools/handy/vorlese_schluessel_senden.py. Darf den Start nie verhindern.
bash "$PROJEKT/termux/schluessel-uebernehmen.sh" "backend/.env" vorlese_schluessel.txt "Vorlese-Schlüssel" OPENROUTER_TTS_KEY || true

# ── Foto- und Verknüpfungs-Datendateien übernehmen (selbstheilend) ───────────
# Warum: Das Handy braucht ~/foto_sortierung/fotos_dateien.json (Datei-Kennungen
# für die Bildvorschau) und ~/foto_sortierung/fotos_uebersicht.json (die Zahlen
# der Übersicht). Dazu kommen drei Verknüpfungs-Dateien, die dieselben Dienste
# am Handy lesen: ereignisse.jsonl (Ereignisliste für die Erzähl-Diashow),
# beziehungen.jsonl und beziehungen.json (Antworten auf "was war am <Datum>?").
# Seit 01.10.2026 zusätzlich personen_beispiele.json + gesicht_zuordnung.jsonl
# (Personen benennen im Gruppenmodus, app/services/gruppen_quiz.py).
# Alle fünf entstehen am PC (Werkzeuge tools/foto_sortierung/) und sind zu groß
# und zu privat für Git. Der Termux-Heimordner ist über das Kabel
# NICHT beschreibbar (App-Sandbox) — deshalb legt der PC sie per Kabel in den
# freigegebenen Download-Ordner, und hier werden sie beim Start übernommen.
# Genau das Muster von Archiv-Index und pCloud-Schlüssel oben, mit einer
# Verschärfung: der Prüfsummen-Vergleich (sha256) ist HART. Eine vorhandene alte
# Fassung wird als *.vorher beiseitegelegt (Rückweg offen, es wird nie ohne
# Sicherung überschrieben), danach entfernt das Werkzeug ausschließlich die
# eigene Übergabedatei. Es wird sonst NICHTS angefasst.
# Jeder Lauf schreibt seine Zeilen in das Protokoll im Diagnose-Ordner (derselbe
# Ordner, den das Skript unten als $DIAG benutzt) — von dort kann der PC über
# das Kabel nachsehen, ob und wann die Übernahme lief; der Termux-Heimordner ist
# ja nicht lesbar.
# Der Abschnitt darf den Serverstart NIE verhindern: alles ist abgefangen
# (|| true). Fehlt die Übergabedatei (Normalfall ab dem zweiten Start), passiert
# nichts — keine Ausgabe, kein Fehler.
QUELLE_DATEN="$HOME/storage/downloads"
# Ohne eingerichteten Speicherzugriff zeigt der erste Pfad ins Leere — dann gilt
# der freigegebene Download-Ordner direkt (gleiches Muster wie Index und Token).
[ -d "$QUELLE_DATEN" ] || QUELLE_DATEN="/sdcard/Download"
DATEN_GEFUNDEN=0
for name in fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl ordner_ereignisse.jsonl; do
    [ -f "$QUELLE_DATEN/$name" ] && DATEN_GEFUNDEN=1
done
if [ "$DATEN_GEFUNDEN" = "1" ]; then
    echo "── Foto- und Verknüpfungs-Datendateien übernehmen ──"
    PROTO_DATEN="$QUELLE_DATEN/hermes_diag"
    mkdir -p "$PROTO_DATEN" 2>/dev/null || true
    if [ -d "$PROTO_DATEN" ]; then
        # Übergebene Namen stehen absichtlich hier (nicht im Werkzeug): der PC
        # bestimmt, was übernommen wird; das Werkzeug kennt keine Sonderfälle.
        python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
            --quelle "$QUELLE_DATEN" \
            --ziel "$HOME/foto_sortierung" \
            --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl ordner_ereignisse.jsonl \
            --protokoll "$PROTO_DATEN/uebergabe_letzte.txt" || true
    else
        python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
            --quelle "$QUELLE_DATEN" \
            --ziel "$HOME/foto_sortierung" \
            --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl ordner_ereignisse.jsonl || true
    fi
fi

# Verhindert, dass Android den Server beim Bildschirmsperren einschlaefert.
# Ohne das bricht ein laufender Stream ab, sobald das Display ausgeht.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Alten Agenten-Server beenden, bevor der neue startet — so kann es nie
# zwei uvicorn-Instanzen auf demselben Port geben.
#
# Frueher stand hier nur `pkill -f "uvicorn app.main:app"`. Das matchte den
# echten Prozess (python -m uvicorn ... --reload) oft nicht, der alte Server
# blieb auf dem Port — deshalb "Address already in use" / "already processed"
# + der neue Server (mit frischer Config) kam nie wirklich hoch. Jetzt killen
# wir alle uvicorn-Varianten und warten, bis der Port frei ist.
echo "── Alter Server wird beendet ──────────────────"
# Sanft beenden (SIGTERM), damit uvicorn sauber herunterfaehrt und die
# alte Termux-Session nicht als 'durchgestrichen/Code 137' stehenbleibt.
# Nur wenn der Server nach kurzer Zeit noch lebt, wird hart gekillt (-9).
pkill -TERM -f "uvicorn app.main:app" 2>/dev/null
pkill -TERM -f "python -m uvicorn" 2>/dev/null
pkill -TERM -f "uvicorn" 2>/dev/null

# Warten, bis er wirklich weg ist (sanft), sonst als Fallback hart beenden.
i=0
while [ $i -lt 10 ]; do
    if ! (command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":$PORT ") \
       && ! pgrep -f "uvicorn" >/dev/null 2>&1; then
        break
    fi
    i=$((i+1))
    sleep 1
done
# Haengt er immer noch, bleibt nur der harte Abbruch (letzter Ausweg).
if pgrep -f "uvicorn" >/dev/null 2>&1; then
    echo "  sanftes Beenden fehlgeschlagen – letzter Versuch (kill -9)"
    pkill -9 -f "uvicorn" 2>/dev/null
fi

# Kurz warten, bis der Port wirklich frei ist (statt nur sleep 1).
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if command -v ss >/dev/null 2>&1; then
        if ! ss -tln 2>/dev/null | grep -q ":$PORT "; then
            break
        fi
    fi
    sleep 1
done
echo "Alter Server gestoppt / Port frei."

echo
echo "── Server startet ─────────────────────────────"
echo "Im Browser:   http://localhost:$PORT"
ip=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
[ -n "${ip:-}" ] && echo "Im Heimnetz:  http://$ip:$PORT"
echo "Beenden mit Strg+C  (Lautstaerke-hoch + C)"
echo

cd backend || { echo "backend/ fehlt"; exit 1; }

# ── Aufräumen: liegengebliebene Job-Sessions ─────────────────────────────────
# Eigene Job-Sessions heissen 'hermes_agent_<ms>_<n>'. Stirbt der Server vorher
# (Neustart/Absturz/Akku), bleiben sie in Termux als tote, rot durchgestrichene
# Eintraege stehen und mussten einzeln manuell geschlossen werden
# (Wunsch Sebastian 2026-09-15: automatisch aufraeumen).
# Die persistente Andock-Session (hermes / hermes_code / hermes_termux) bleibt
# UNBERUEHRT — nur das Job-Muster wird beendet.
if command -v tmux >/dev/null 2>&1; then
    ALTE_SESSIONS="$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep '^hermes_agent_' || true)"
    if [ -n "$ALTE_SESSIONS" ]; then
        echo "── Aufräumen: alte Job-Sessions ───────────────"
        for s in $ALTE_SESSIONS; do
            if tmux kill-session -t "$s" 2>/dev/null; then
                echo "  ✔ beendet: $s"
            fi
        done
    fi
fi

# ── Inbox-Daemon (Track C) ────────────────────────────────────────────────────
# Track C (lokaler Hermes) antwortet NICHT direkt, sondern über die Datei-Inbox
# ~/hermes_inbox: der Daemon liest auftraege.jsonl und schreibt antworten.jsonl.
# Ohne laufenden Daemon wird ein Auftrag abgelegt und NIE beantwortet — Symptom:
# „Hermes denkt nach …", dann kommt keine Antwort ("ins Leere").
# Deshalb wird er hier idempotent mitgestartet (Wunsch Sebastian 2026-09-15).
# Läuft er schon, wird nichts doppelt gestartet (kein zweiter Daemon auf der
# gleichen Inbox -> sonst verarbeiten zwei Prozesse dieselben Auftraege).
DAEMON="hermes_inbox_daemon.py"
if pgrep -f "$DAEMON" >/dev/null 2>&1; then
    echo "Inbox-Daemon läuft bereits — Track C bereit."
else
    echo "── Inbox-Daemon startet (Track C) ─────────────"
    mkdir -p "$HOME/hermes_inbox"
    nohup python "$DAEMON" >> "$HOME/hermes_inbox/daemon.log" 2>&1 &
    sleep 1
    if pgrep -f "$DAEMON" >/dev/null 2>&1; then
        echo "  ✔ Daemon läuft (Log: ~/hermes_inbox/daemon.log)"
    else
        echo "  ⚠ Daemon konnte nicht starten — lokale Übergabe bliebe ohne Antwort."
        echo "    Prüfen: python backend/hermes_inbox_daemon.py --einmal"
    fi
fi

# ── Diagnose-Ablage für die Fehlersuche über das Kabel ────────────────────────
# Warum: Der Termux-Heimatordner ist über das Kabel NICHT lesbar (adb shell läuft
# als anderer Benutzer). Deshalb legt das Skript bei jedem Start die letzten
# Zeilen des Inbox-Protokolls und der letzten Antworten in den freigegebenen
# Download-Ordner — von dort kann man sie vom PC aus lesen.
# Es wird nichts hochgeladen und nichts ins Repo geschrieben; die Dateien werden
# bei jedem Start überschrieben (reine Nachschau-Hilfe).
INBOX_DIR="${HERMES_INBOX_DIR:-$HOME/hermes_inbox}"
DIAG_BASIS="$HOME/storage/downloads"
[ -d "$DIAG_BASIS" ] || DIAG_BASIS="/sdcard/Download"
DIAG="$DIAG_BASIS/hermes_diag"
if [ -d "$INBOX_DIR" ] && mkdir -p "$DIAG" 2>/dev/null; then
    tail -200 "$INBOX_DIR/daemon.log"     > "$DIAG/daemon_letzte.txt"      2>/dev/null
    tail -3  "$INBOX_DIR/antworten.jsonl" > "$DIAG/antworten_letzte.jsonl" 2>/dev/null
    tail -3  "$INBOX_DIR/status.jsonl"    > "$DIAG/status_letzte.jsonl"    2>/dev/null
    tail -2  "$INBOX_DIR/auftraege.jsonl" > "$DIAG/auftraege_letzte.jsonl" 2>/dev/null
    echo "  ℹ Diagnose abgelegt: $DIAG (Protokoll + letzte Antworten)"
else
    echo "  ℹ Keine Diagnose-Ablage (Postfach oder Download-Ordner nicht gefunden)"
fi

# ── Beleg: steht der Nachtjob wirklich in der Job-Liste von Android? ──────────
# Warum dieses Stueck: Auf das Handy kommt von aussen NICHTS — der Widget-Tipp
# ist der einzige Weg (vom PC laesst sich kein Befehl starten, und der
# Termux-Heimordner ist ueber das Kabel nicht lesbar). Ob der Nachpflege-Job
# danach wirklich bei Android registriert ist, schrieb bisher niemand
# irgendwohin — es war nur behauptet. Deshalb legt dieser Block den Beleg in
# den freigegebenen Download-Ordner, den der PC per Kabel lesen kann
# (PC-Werkzeug: tools/handy/diag_holen.py). Rein lesend: kein rm, kein Netz,
# kein Geheimnis. Der Block braucht das Postfach ($INBOX_DIR) NICHT —
# hermes_diag soll auch ohne Postfach entstehen. Die erwartete Kennung stammt
# aus termux/nachpflege-einrichten.sh (dort steht die feste JOB_ID).
JOB_ID_ERWARTET=1901
if mkdir -p "$DIAG" 2>/dev/null; then
    {
        printf 'beleg job-liste %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')"
        printf 'JOB_ID_ERWARTET=%s\n' "$JOB_ID_ERWARTET"
        if command -v termux-job-scheduler >/dev/null 2>&1; then
            JOB_BELEG_LISTE="$(termux-job-scheduler --list 2>/dev/null || true)"
            if printf '%s' "$JOB_BELEG_LISTE" | grep -q "$JOB_ID_ERWARTET"; then
                printf 'JOB_ID_GEFUNDEN=ja\n'
            else
                printf 'JOB_ID_GEFUNDEN=nein\n'
            fi
            printf -- '--- termux-job-scheduler --list ---\n'
            printf '%s\n' "$JOB_BELEG_LISTE" | tail -n 40
        else
            printf 'JOB_ID_GEFUNDEN=unbekannt\n'
            printf -- '--- termux-job-scheduler --list ---\n'
            printf 'termux-job-scheduler nicht vorhanden (Beleg nicht moeglich)\n'
        fi
    } > "$DIAG/job_liste.txt" 2>/dev/null
    EINRICHT_LOG="$HOME/nachpflege-einrichten.log"
    if [ -f "$EINRICHT_LOG" ]; then
        tail -n 20 "$EINRICHT_LOG" > "$DIAG/nachpflege_einrichtung_letzte.txt" 2>/dev/null
    else
        printf 'Log nicht vorhanden — seit der Einrichtung kein Lauf\n' \
            > "$DIAG/nachpflege_einrichtung_letzte.txt" 2>/dev/null
    fi
    echo "  ℹ Beleg abgelegt: $DIAG/job_liste.txt (Job-Liste + Einricht-Protokoll)"
else
    echo "  ℹ Kein Beleg moeglich (Download-Ordner nicht beschreibbar)"
fi

# ── App statt Browser öffnen ──────────────────────────────────────────────────
# Eine Web-App (display=standalone) kann den Server NICHT starten: sie ist
# reiner Browser-Inhalt, hat keinen nativen Code und keine Shell. Deshalb macht
# es dieses Skript herum: Server starten → warten, bis der Port antwortet →
# Adresse öffnen. Android gibt sie an die INSTALLIERTE App weiter (Chrome leitet
# eine Adresse, die in die App gehört, in deren eigenes Fenster ohne Tabs).
# Damit genügt ein Widget-Tipp: Server läuft, App ist offen.
#
# Der Server läuft im Hintergrund, damit das Skript ihn erst öffnen und danach
# weiterlaufen kann. `wait` hält die Session wie vorher am Server, Strg+C beendet
# ihn weiterhin direkt.
cd "$PROJEKT/backend" 2>/dev/null || true

# Bindung aus der .env lesen (gleiches Muster wie termux/neu-start-nach-lauf.sh
# und termux/agent-ensure.sh). Standard bleibt 0.0.0.0: ohne HOST_BIND in der
# .env ändert sich nichts. Mit HOST_BIND=127.0.0.1 lauscht der Server nur lokal.
HOST_BIND="0.0.0.0"
_env_host=$(grep -E "^HOST_BIND=" .env 2>/dev/null | tail -1 | cut -d= -f2- | cut -d'#' -f1 | tr -d '[:space:]\r"')
[ -n "$_env_host" ] && HOST_BIND="$_env_host"

python -m uvicorn app.main:app --host "$HOST_BIND" --port "$PORT" --reload &
SERVER_PID=$!

# Kurz warten, bis der Port wirklich antwortet (max. ~20 s), dann öffnen.
i=0
while [ $i -lt 40 ]; do
    if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":$PORT "; then
        break
    fi
    i=$((i+1))
    sleep 0.5
done

if command -v am >/dev/null 2>&1; then
    # Geöffnet wird NUR die native App "Hey Agent" (android/, seit 29.09.2026), kein
    # Browser mehr (Sebastians Wunsch 29.09.2026; die alte Chrome-Web-App ist gelöscht).
    # Weg: die eigene Adresse heyagent://start, NICHT `pm list packages` + `am start -n`:
    # Termux (targetSdk 37) sieht fremde Pakete nicht (Paket-Sichtbarkeit). Scheitert
    # der Start, steht die Meldung von Android hier im Fenster statt verschluckt.
    if AM_AUSGABE="$(am start -a android.intent.action.VIEW -d "heyagent://start" 2>&1)"; then
        echo "  ✔ App geöffnet: Hey Agent (heyagent://start)"
    else
        echo "  ⚠ Hey Agent ließ sich nicht öffnen – bitte die App von Hand antippen. Android sagt:"
        printf '%s\n' "$AM_AUSGABE" | head -4 | sed 's/^/    /'
    fi
else
    echo "  ℹ am nicht verfügbar – bitte Hey Agent von Hand antippen."
fi

# Die Shell bleibt am Server: Strg+C beendet ihn wie bisher.
wait $SERVER_PID
