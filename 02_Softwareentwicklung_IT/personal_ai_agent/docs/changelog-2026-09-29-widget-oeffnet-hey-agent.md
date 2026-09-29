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

## Nachtrag: Öffnen über `heyagent://start`

**Befund am Handy:** Auch nach der ersten Änderung öffnete das Widget den Browser (Comet).
Das Handy-Protokoll zeigt: Termux hat Hey Agent nie aufgerufen. Ursache ist die
Paket-Sichtbarkeit. Termux ist für `targetSdk 37` gebaut und sieht fremde Pakete nur,
wenn es sie ausdrücklich anfragt. `pm list packages` liefert Hey Agent dort nicht, und
`am start -n` fände sie ebenso wenig.

**Änderung:**
- Die App nimmt die eigene Adresse `heyagent://start` an (Intent-Filter im Manifest) und hat
  `launchMode="singleTask"`, damit ein zweiter Aufruf die laufende App nach vorn holt, statt
  eine zweite zu öffnen.
- `start-termux.sh` öffnet die App mit
  `am start -a android.intent.action.VIEW -d "heyagent://start"`. Eine Adresse löst Android
  immer auf, genau wie `http://` beim Browser. Ohne installierte App endet `am` mit Fehler, dann
  folgen wie bisher Web-App und Browser.

**Prüfung:** 4 Wächter-Tests in `backend/tests/test_start_app_wahl.py` (vorher 3 rot).
`assembleDebug` + 12 JUnit grün. Am Handy: `am start … -d heyagent://start` → Exit 0,
`topResumedActivity = de.sebastian.heyagent/.MainActivity`. Dieser Aufruf lief über `adb`,
nicht aus Termux. Der Beleg aus Termux selbst ist der nächste Widget-Tipp.
