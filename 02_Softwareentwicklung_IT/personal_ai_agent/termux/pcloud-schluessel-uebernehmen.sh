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
# Seit 06.10.2026 steckt die Logik im gemeinsamen Skript
# termux/schluessel-uebernehmen.sh (auch fuer den Vorlese-Schluessel) - hier
# stehen nur noch die pCloud-Namen. Uebernommen werden NUR PCLOUD_TOKEN
# (Pflicht) und PCLOUD_HOST; Sicherung <env>.vorher, Uebergabedatei wird nach
# erfolgreicher Uebernahme geloescht, Werte werden nie ausgegeben, Exit immer 0.

ENV_DATEI="${1:-}"
if [ -z "$ENV_DATEI" ]; then
    echo "Aufruf: $0 <env-datei> [quelle]"
    exit 0
fi
bash "$(dirname "$0")/schluessel-uebernehmen.sh" "$ENV_DATEI" "${2:-pcloud_token.txt}" \
    "pCloud-Zugang" PCLOUD_TOKEN PCLOUD_HOST
exit 0
