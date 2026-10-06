#!/data/data/com.termux/files/usr/bin/bash
#
# Einen Schluessel aus dem Download-Ordner in backend/.env uebernehmen —
# gemeinsamer Weg fuer alle Geheimnisse, die per Kabel aufs Handy kommen
# (pCloud-Zugang seit 02.10.2026, Vorlese-Schluessel seit 06.10.2026).
#
# Aufruf:  bash termux/schluessel-uebernehmen.sh <env-datei> <uebergabe> <titel> <PFLICHT> [WEITERE ...]
#   uebergabe: Dateiname (gesucht in $HOME/storage/downloads, sonst
#              /sdcard/Download) oder ein Pfad mit "/".
#   titel:     Ueberschrift in der Ausgabe (z. B. "Vorlese-Schlüssel").
#   PFLICHT:   dieser Variablenname muss danach in der .env stehen, sonst bleibt
#              die Uebergabedatei liegen (erneut starten).
#   WEITERE:   weitere Namen, die mit uebernommen werden duerfen.
#
# Regeln (unveraendert aus pcloud-schluessel-uebernehmen.sh, 02.10.2026):
# Geheimnisse wandern NIE ueber Git (das Repo ist oeffentlich). Uebernommen
# werden NUR die genannten Namen; alle anderen Zeilen der .env bleiben
# unangetastet - deshalb wird zeilenweise ersetzt/angehaengt statt die Datei
# neu zu schreiben. Ein vorhandener Wert wird ersetzt (der neue gilt), vorher
# liegt der alte Stand als <env>.vorher beiseite (Rueckweg offen).
# Nach erfolgreicher Uebernahme wird die Uebergabedatei GELOESCHT: sonst bliebe
# das Geheimnis im freigegebenen Download-Ordner liegen (dort kann jede App
# lesen). Fehlt die Datei (der Normalfall, sobald einmal uebernommen),
# passiert NICHTS: keine Ausgabe, kein Fehler. Exit immer 0 - der Aufrufer
# haengt trotzdem "|| true" an: dieser Schritt darf einen Start NIE verhindern.

ENV_DATEI="${1:-}"
UEBERGABE="${2:-}"
TITEL="${3:-Schlüssel}"
PFLICHT="${4:-}"
if [ -z "$ENV_DATEI" ] || [ -z "$UEBERGABE" ] || [ -z "$PFLICHT" ]; then
    echo "Aufruf: $0 <env-datei> <uebergabe> <titel> <PFLICHT> [WEITERE ...]"
    exit 0
fi
shift 3
ERLAUBT=" $* "

case "$UEBERGABE" in
    */*) QUELLE="$UEBERGABE" ;;
    *)   QUELLE="$HOME/storage/downloads/$UEBERGABE"
         [ -f "$QUELLE" ] || QUELLE="/sdcard/Download/$UEBERGABE" ;;
esac
[ -f "$QUELLE" ] || exit 0

echo "── $TITEL übernehmen ───────────────────"
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
        *=*) ;;
        *) continue ;;
    esac
    schluessel="${zeile%%=*}"
    case "$ERLAUBT" in
        *" $schluessel "*) ;;
        *) continue ;;                     # nur die genannten Namen
    esac
    wert="${zeile#*=}"
    wert="${wert%\"}"; wert="${wert#\"}"   # Anfuehrungszeichen dulden
    # Leerer Wert darf einen vorhandenen Schluessel nicht loeschen.
    [ -n "$wert" ] || continue
    if grep -q "^$schluessel=" "$ENV_DATEI"; then
        # sed mit | als Trenner: Werte koennen / + = enthalten.
        # & \ und | sind im Ersatzteil Sonderzeichen und werden nur
        # HIER maskiert (beim Anhaengen unten waeren sie sonst doppelt).
        ersatz="$(printf '%s' "$wert" | sed 's/[&\\|]/\\&/g')"
        sed -i "s|^$schluessel=.*|$schluessel=$ersatz|" "$ENV_DATEI"
    else
        printf '%s\n' "$schluessel=$wert" >> "$ENV_DATEI"
    fi
    uebernommen="1"
    namen="$namen $schluessel"
done < "$QUELLE"
if [ -n "$uebernommen" ] && grep -q "^$PFLICHT=" "$ENV_DATEI"; then
    rm -f "$QUELLE"
    echo "  ✔ übernommen:$namen (in $ENV_DATEI) – Übergabedatei gelöscht"
else
    echo "  ⚠ Übernahme fehlgeschlagen – $QUELLE bleibt liegen (erneut starten)."
    echo "    Prüfen: enthält die Datei eine Zeile $PFLICHT=…?"
fi
exit 0
