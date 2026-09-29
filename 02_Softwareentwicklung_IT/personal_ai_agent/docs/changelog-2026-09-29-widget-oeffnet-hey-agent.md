# Widget-Tipp öffnet die Hey-Agent-App (29.09.2026)

## Anlass

Erster Test mit der nativen App am Handy: Das Widget „agent“ (`start-termux.sh`) hat
gepullt und den Server gestartet. Danach öffnete es aber die ältere **Chrome-Web-App**
statt der neuen App „Hey Agent“.

## Ursache

`start-termux.sh`, Block „App statt Browser öffnen“: Das Skript suchte nur nach einem
Paket `org.chromium.webapk*` und fiel sonst auf den Browser zurück. Die native App
(`de.sebastian.heyagent`) kannte es nicht.

## Änderung

- Neue Reihenfolge beim Öffnen:
  1. **Hey Agent** (`am start -n de.sebastian.heyagent/.MainActivity`), falls installiert.
  2. Die Chrome-Web-App (wie bisher).
  3. Der Browser (wie bisher).
- Scheitert der Start der App, geht es mit den bisherigen Rückfällen weiter.
- Pull, Serverstart und alle anderen Blöcke des Skripts bleiben unverändert.

## Prüfung

- Neu: `backend/tests/test_start_app_wahl.py` mit 3 Wächter-Tests (offline, liest den
  Skripttext). Vor der Änderung waren 2 davon rot.
- `bash -n start-termux.sh`: Exit 0.
- Prüfbefehl des Projekts: siehe Commit.

## Offen

Die App kann Termux **nicht selbst** starten. Das Play-Store-Termux
(`googleplay.2026.06.21`) hat keinen `RUN_COMMAND`-Dienst (am Handy gemessen:
`Unable to start service … RunCommandService … not found`). Bis zu einer Lösung gilt:
erst das Widget tippen, dann öffnet sich die App von selbst.
