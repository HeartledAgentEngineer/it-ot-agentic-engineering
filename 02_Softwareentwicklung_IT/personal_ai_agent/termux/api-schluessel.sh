#!/data/data/com.termux/files/usr/bin/bash
# api-schluessel.sh — gibt NUR den Wert der Zeile API_KEY= einer Einstellungsdatei aus.
#
# P0 (12.10.2026): Vorher holten die Termux-Werkzeuge den Schlüssel über
# /api/konfig — denselben offenen Weg, über den ihn jede fremde Webseite abholen
# konnte. Der Weg ist entfernt; die Werkzeuge lesen ihn jetzt selbst.
#
# Bewusst ohne `source`: Die übrigen Schlüssel der Datei (OpenRouter, pCloud)
# landen so nicht in der Shell-Umgebung des Aufrufers.
#
# Aufruf:  api-schluessel.sh <einstellungsdatei>
# Ausgabe: der Wert auf stdout (Exit 0) — sonst nichts und Exit 1
#          (Datei fehlt/unlesbar, keine API_KEY-Zeile, leerer Wert).
datei="${1:-}"
[ -n "$datei" ] && [ -r "$datei" ] || exit 1

zeile="$(grep -m1 -E '^[[:space:]]*(export[[:space:]]+)?API_KEY[[:space:]]*=' "$datei" 2>/dev/null)"
wert="$(printf '%s' "${zeile#*=}" | tr -d '\r' \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
          -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")"
[ -n "$wert" ] || exit 1
printf '%s\n' "$wert"
