#!/data/data/com.termux/files/usr/bin/bash
#
# GEMEINSAME START-VORBEREITUNG (10.10.2026) - DIE eine Wahrheit fuer den
# App-Weg (termux/agent-ensure.sh) und den Widget-Weg (termux/agent-start).
#
# Anlass: Die Wissensdatei-Uebernahme hing im Widget-Weg allein; wuerde nur der
# App-Knopf benutzt, liefe sie nie. Entscheidung Sebastian (10.10.2026): App-
# Knopf und Widget machen DIESELBEN Schritte, und zwar ueber diese eine Datei -
# kein Schritt steht mehr zweimal irgendwo.
#
# Reihenfolge (jeder Schritt einzeln abgesichert, darf den Start NIE verhindern):
#   1. git pull --ff-only   (nur Vorspulen; eigene Commits/lokale Aenderungen
#                            werden nie ueberschrieben - dann alter Stand)
#   2. hey-agent-einrichten.sh  (profile.d-Eintrag + Bruecke ~/agent-ensure.sh
#      + allow-external-apps pruefen/setzen - selbstheilend)
#   3. pCloud-Schluessel aus dem Download-Ordner in backend/.env
#   4. Vorlese-Schluessel (OPENROUTER_TTS_KEY) auf demselben Weg
#   5. Datendateien vom PC (Werkzeug tools/handy/uebergabe_uebernehmen.py)
#   6. Wissensdatei memory.db (termux/wissensdatei-uebernehmen.sh)
#   6b. Ergebnisse kabellos aus der pCloud (termux/pcloud-uebernehmen.sh) —
#       holt, was der PC in /Agent/uebergabe gelegt hat
#   7. Weckruf-Sperre (Aufruf termux-wake-lock)
#   8. Sicherung auf Auftrag (termux/sicherung-auftrag.sh) - NUR ohne --laufend
#      (im Widget-Weg ist der Server beendet; beim App-Druck auf einen
#      laufenden Server wird bewusst nicht aus dem laufenden Betrieb gesichert)
#   9. Postfach-Daemon sicherstellen (Skript hermes_inbox_daemon.py)
#
# Aufruf:
#   bash termux/start-vorbereiten.sh [--laufend] [Projektordner]
#     --laufend     : der Server laeuft bereits und bleibt laufen; nur die
#                     schnellen, idempotenten Uebernahmen laufen (Schritt 8 entfaellt).
#     Projektordner : Standard ist der Elternordner dieses Skripts.
#
# Eigenschaften (bewusst, vom Nutzer am 10.10.2026 so entschieden):
#   * Laeuft AUCH, wenn der Server schon antwortet - Pull und Wissensdatei-
#     Uebernahme sind schnell und idempotent (gleiche sha256 = nichts tun) und
#     liefen sonst nie, weil der Server im Alltag dauerhaft laeuft.
#   * Der Serverstart selbst bleibt Sache der Aufrufer; hier wird NIE ein
#     Prozess beendet.
#   * Exit immer 0 (Ausnahme: Projektordner fehlt -> Exit 1 mit Meldung).

set -u

# Eigenen Ort aufloesen (ein Symlink-Aufruf ist nicht vorgesehen, die
# Aufloesung ist nur Absicherung).
_skript="$0"
[ -L "$_skript" ] && _skript="$(readlink "$_skript")"
HIER="$(cd "$(dirname "$_skript")" && pwd)"

LAUFEND=0
PROJEKT_ARG=""
for _arg in "$@"; do
    case "$_arg" in
        --laufend) LAUFEND=1 ;;
        "") ;;
        *) PROJEKT_ARG="$_arg" ;;
    esac
done

if [ -n "$PROJEKT_ARG" ]; then
    PROJEKT="$PROJEKT_ARG"
else
    PROJEKT="$(cd "$HIER/.." && pwd)"
fi

if [ ! -d "$PROJEKT/backend" ]; then
    echo "FEHLER: Projektordner ohne backend/ - PROJEKT='$PROJEKT'"
    exit 1
fi

cd "$PROJEKT" || { echo "FEHLER: kann nicht nach $PROJEKT wechseln"; exit 1; }

echo "── Vorbereitung (ein Ablauf fuer App und Widget) ──"

# ── 1. Aktualisieren ────────────────────────────────────────────────────────
# Nur Vorspulen, und nur wenn das Handy wirklich hinter origin liegt. Eigene
# Handy-Commits oder lokale Aenderungen werden nie ueberschrieben; dann geht es
# mit dem vorhandenen Stand weiter (nie abbrechen).
echo "── Aktualisieren ──────────────────────────────"
if git fetch origin --quiet 2>/dev/null; then
    if git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
        if git pull --ff-only --quiet; then
            echo "Stand: $(git log --oneline -1)"
        else
            echo "⚠️  Pull nicht moeglich (lokale Aenderungen?) – es geht mit dem vorhandenen Stand weiter."
        fi
    else
        echo "ℹ️  Handy hat eigene Commits – kein Pull, es geht mit dem vorhandenen Stand weiter."
    fi
else
    echo "⚠️  git fetch fehlgeschlagen (Netz?) – es geht mit dem vorhandenen Stand weiter."
fi

# ── 2. App-Einrichtung erneuern (profile.d, Bruecke, allow-external-apps) ───
# Wiederholbar und selbstheilend; laeuft nach dem Pull, damit immer die
# neueste Fassung wirkt. Darf den Start nie verhindern.
if [ -f "$HIER/hey-agent-einrichten.sh" ]; then
    sh "$HIER/hey-agent-einrichten.sh" || true
fi

# ── 3./4. Schluessel aus dem Download-Ordner uebernehmen ────────────────────
# Eine gemeinsame Quelle fuer alle Startwege (Issue #3 Befund 1, 02.10.2026;
# Vorlese-Schluessel 06.10.2026). Fehlt die Datei, passiert nichts.
# Darf den Start nie verhindern (|| true).
bash "$HIER/pcloud-schluessel-uebernehmen.sh" "$PROJEKT/backend/.env" || true
# Vorlese-Schluessel (OPENROUTER_TTS_KEY, 06.10.2026) auf demselben Weg - vom PC
# gelegt mit tools/handy/vorlese_schluessel_senden.py. Darf den Start nie verhindern.
bash "$HIER/schluessel-uebernehmen.sh" "$PROJEKT/backend/.env" vorlese_schluessel.txt "Vorlese-Schlüssel" OPENROUTER_TTS_KEY || true

# ── 5. Datendateien vom PC uebernehmen ──────────────────────────────────────
# Gleiches Werkzeug, gleiche Liste wie bisher (sha256 hart, alte Fassung als
# *.vorher, entfernt nur die eigene Uebergabedatei). Darf den Start NIE
# verhindern (|| true); fehlt die Uebergabedatei (Normalfall), passiert nichts.
QUELLE_DATEN="$HOME/storage/downloads"
[ -d "$QUELLE_DATEN" ] || QUELLE_DATEN="/sdcard/Download"
PROTO_DATEN="$QUELLE_DATEN/hermes_diag"
mkdir -p "$PROTO_DATEN" 2>/dev/null || true
if [ -d "$PROTO_DATEN" ]; then
    python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
        --quelle "$QUELLE_DATEN" \
        --ziel "$HOME/foto_sortierung" \
        --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl ordner_ereignisse.jsonl bild_beschreibungen.jsonl bild_orte.csv \
        --protokoll "$PROTO_DATEN/uebergabe_letzte.txt" || true
else
    python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py" \
        --quelle "$QUELLE_DATEN" \
        --ziel "$HOME/foto_sortierung" \
        --dateien fotos_dateien.json fotos_uebersicht.json ereignisse.jsonl beziehungen.jsonl beziehungen.json personen_beispiele.json gesicht_zuordnung.jsonl kontakte.json fotobuch_ereignisse.jsonl ordner_ereignisse.jsonl bild_beschreibungen.jsonl bild_orte.csv || true
fi

# ── 6. Wissensdatei (memory.db) uebernehmen ─────────────────────────────────
# sha256-Vergleich: gleich -> nichts tun; sonst zuerst sichern, dann kopieren;
# Protokoll nach hermes_diag/wissensdatei_uebernahme.log. Kein Netz, kein
# Cloud-Abruf. Darf den Start NIEMALS verhindern (|| true).
bash "$HIER/wissensdatei-uebernehmen.sh" || true

# ── 6b. Ergebnisse kabellos aus der pCloud uebernehmen ──────────────────────
# Kabellose Uebergabe (Sebastian 10.10.2026): Der PC laedt die Ergebnisdateien
# mit tools/pcloud/uebergabe_hochladen.py in den pCloud-Ordner /Agent/uebergabe;
# dieses Skript holt sie beim Start in den Datenordner. Vorhandene Fassungen
# werden vorher als *.vor_<datum> gesichert, kopiert wird ueber .teil + Pruefsumme
# (Muster wissensdatei-uebernehmen.sh). Ausdruecklich erlaubt sind auch die
# Gesichts-Vektoren (eigenes Geraet, eigenes Konto, kein fremder Anbieter).
# Darf den Start NIE verhindern (|| true); fehlender Token/kein Netz -> klare
# Zeile, es geht mit dem vorhandenen Stand weiter.
bash "$HIER/pcloud-uebernehmen.sh" "$PROJEKT" || true

# ── 7. Weckruf-Sperre ───────────────────────────────────────────────────────
# Verhindert, dass Android den Server beim Bildschirmsperren einschlaefert.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# ── 8. Sicherung auf Auftrag ────────────────────────────────────────────────
# Liegt vom PC eine Auftragsdatei im Download-Ordner (tools/handy/sicherung_auftrag.py),
# wird EINMAL verschluesselt gesichert - Server und Daemon sind in diesem Moment
# beendet, der Stand ist frisch gezogen. Mit --laufend bewusst uebersprungen:
# aus dem laufenden Betrieb wird nicht gesichert (Entscheidung 10.10.2026).
if [ "$LAUFEND" != "1" ]; then
    bash "$HIER/sicherung-auftrag.sh" || true
fi

# ── 9. Postfach-Daemon sicherstellen ────────────────────────────────────────
# Guarded, damit NUR EIN Daemon laeuft (mehrere waeren mehrere Antwort-Instanzen).
# Laeuft er schon, passiert nichts.
_daemon_skript="hermes_inbox_daemon.py"
if [ -f "$PROJEKT/backend/$_daemon_skript" ]; then
    if ! pgrep -f "$_daemon_skript" >/dev/null 2>&1; then
        mkdir -p "$HOME/hermes_inbox" 2>/dev/null || true
        ( cd "$PROJEKT/backend" && nohup python "$_daemon_skript" >> "$HOME/hermes_inbox/daemon.log" 2>&1 & )
        echo "── Inbox-Daemon gestartet (bidirektionaler Spiegel) ──"
    else
        echo "Inbox-Daemon laeuft bereits."
    fi
fi

exit 0
