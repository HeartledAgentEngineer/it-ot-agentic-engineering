#!/data/data/com.termux/files/usr/bin/bash
#
# pCloud-Zugang aus dem Download-Ordner in backend/.env uebernehmen.
#
# Aufruf:  bash termux/pcloud-schluessel-uebernehmen.sh <env-datei> [quelle]
#          quelle: Standard $HOME/storage/downloads/pcloud_token.txt,
#                  sonst /sdcard/Download/pcloud_token.txt
#
# Warum ein eigenes Skript (02.10.2026, Issue #3 Befund 1): Die Uebernahme
# stand nur in start-termux.sh. Das Widget "agent" startet aber
# termux/agent-start, die App startet termux/agent-ensure.sh - keiner der
# beiden kam an dem Block vorbei. Der Schluessel lag deshalb seit 27.09.
# unbenutzt im Download-Ordner, die Gesichter-Kacheln im Quiz blieben leer.
# Jetzt rufen ALLE DREI Startwege dieses eine Skript auf (eine Quelle).
#
# Der pCloud-Schluessel ist ein Geheimnis und darf NICHT ueber Git wandern
# (das Repo ist oeffentlich). Er wird per Kabel als pcloud_token.txt in den
# Download-Ordner gelegt und hier in backend/.env uebernommen.
# Uebernommen werden NUR die Zeilen PCLOUD_TOKEN und PCLOUD_HOST. Alle anderen
# Zeilen der .env (z. B. OPENROUTER_API_KEY) bleiben unangetastet - deshalb
# wird zeilenweise ersetzt/angehaengt statt die Datei neu zu schreiben.
# Ein vorhandener Wert wird ersetzt (der neue Schluessel gilt), vorher liegt
# der alte Stand als <env>.vorher beiseite (Rueckweg offen).
# Nach erfolgreicher Uebernahme wird die Uebergabedatei GELOESCHT: sonst
# bliebe das Geheimnis im freigegebenen Download-Ordner liegen (dort kann
# jede App lesen).
# Fehlt die Datei (der Normalfall, sobald einmal uebernommen), passiert
# NICHTS: keine Ausgabe, kein Fehler. Exit immer 0 - der Aufrufer haengt
# trotzdem "|| true" an: dieser Schritt darf einen Start NIE verhindern.

ENV_DATEI="${1:-}"
QUELLE_TOKEN="${2:-}"
if [ -z "$ENV_DATEI" ]; then
    echo "Aufruf: $0 <env-datei> [quelle]"
    exit 0
fi
if [ -z "$QUELLE_TOKEN" ]; then
    QUELLE_TOKEN="$HOME/storage/downloads/pcloud_token.txt"
    [ -f "$QUELLE_TOKEN" ] || QUELLE_TOKEN="/sdcard/Download/pcloud_token.txt"
fi
[ -f "$QUELLE_TOKEN" ] || exit 0

echo "── pCloud-Zugang übernehmen ───────────────────"
if [ -f "$ENV_DATEI" ]; then
    cp -f "$ENV_DATEI" "$ENV_DATEI.vorher" \
        && echo "  · Sicherung angelegt: $ENV_DATEI.vorher (Rückweg offen)"
else
    : > "$ENV_DATEI"
    echo "  · $ENV_DATEI war nicht vorhanden – neu angelegt."
fi
# Werte werden NIE ausgegeben: gelesen wird still, gemeldet werden nur
# Schluesselnamen und Zustaende (Protokolle landen auf /sdcard).
uebernommen=""
namen=""
while IFS= read -r zeile || [ -n "$zeile" ]; do
    zeile="${zeile%$'\r'}"                 # Zeilenende vom PC (Windows) weg
    case "$zeile" in
        PCLOUD_TOKEN=*|PCLOUD_HOST=*)
            schluessel="${zeile%%=*}"
            wert="${zeile#*=}"
            wert="${wert%\"}"; wert="${wert#\"}"   # Anfuehrungszeichen dulden
            # Leerer Wert darf einen vorhandenen Schluessel nicht loeschen.
            [ -n "$wert" ] || continue
            if grep -q "^$schluessel=" "$ENV_DATEI"; then
                # sed mit | als Trenner: Token/Host koennen / + = enthalten.
                # & \ und | sind im Ersatzteil Sonderzeichen und werden nur
                # HIER maskiert (beim Anhaengen unten waeren sie sonst doppelt).
                ersatz="$(printf '%s' "$wert" | sed 's/[&\\|]/\\&/g')"
                sed -i "s|^$schluessel=.*|$schluessel=$ersatz|" "$ENV_DATEI"
            else
                printf '%s\n' "$schluessel=$wert" >> "$ENV_DATEI"
            fi
            uebernommen="1"
            namen="$namen $schluessel"
            ;;
    esac
done < "$QUELLE_TOKEN"
if [ -n "$uebernommen" ] && grep -q '^PCLOUD_TOKEN=' "$ENV_DATEI"; then
    rm -f "$QUELLE_TOKEN"
    echo "  ✔ übernommen:$namen (in $ENV_DATEI) – Übergabedatei gelöscht"
else
    echo "  ⚠ Übernahme fehlgeschlagen – $QUELLE_TOKEN bleibt liegen (erneut starten)."
    echo "    Prüfen: enthält die Datei eine Zeile PCLOUD_TOKEN=…?"
fi
exit 0
