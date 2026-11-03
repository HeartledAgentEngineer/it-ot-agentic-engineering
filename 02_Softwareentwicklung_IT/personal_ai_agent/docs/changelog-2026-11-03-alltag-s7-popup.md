# Changelog 03.11.2026 — Alltagsprotokoll S7: Android-Pop-up

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S7. Baut auf S6 auf (`window.HeyAgentAlltag`).
App-Version: `0.3-alltag` (versionCode 3).

## Neu

- **Brücke `HeyAgentAlltag.standSetzen(json)`:** `alltag.js` übergibt nach jedem Speichern die
  Antwort von `/api/alltag/offen`.
  - Die App merkt sich nur zwei Dinge: den **Zeitpunkt** des letzten Eintrags und ob gerade
    geschlafen wird. Inhalte, Gefühle oder Worte speichert sie nicht.
  - Sie liest den Stand nur, wenn die Seite vom eigenen Backend kommt.
- **Stündlicher Worker** (WorkManager, `PeriodicWorkRequest`, `KEEP`): Er rechnet die offenen
  Stunden selbst aus dem gespeicherten Stand und braucht kein Backend. Das Pop-up erscheint
  deshalb auch, wenn Termux gerade nicht läuft.
  - Die Regel ist dieselbe wie im Backend (`AlltagErinnerungRegel`): volle Stunden seit dem
    letzten Eintrag.
  - Im Schlaf gilt 0, der Schlaf-Knopf verfällt aber nach 24 Stunden.
  - Ohne jeden Eintrag gilt 1.
- **Eine Benachrichtigung** mit fester ID, die sich aktualisiert:
  - Text: „Bitte X Stunden nachtragen".
  - Eigener Kanal „Alltagsprotokoll" mit niedriger Wichtigkeit (ohne Ton), `setOnlyAlertOnce`.
  - Auf dem Sperrbildschirm steht nur „Hey Agent".
  - Nach einem Eintrag oder dem Knopf „Schlafen" verschwindet sie sofort.
- **Antippen** öffnet die App mit `?alltag=aufnahme`. Das Blatt geht direkt mit Mikrofon auf.
  Läuft die App schon, lädt sie die Seite mit diesem Zusatz neu.
- **`POST_NOTIFICATIONS`:** Ab Android 13 fragt die App einmal danach, und zwar erst dann, wenn
  das Alltagsprotokoll zum ersten Mal einen Stand meldet, nicht schon beim App-Start.
- Ohne einen einzigen Stand (Protokoll nie geöffnet) gibt es kein Pop-up.

## Abweichung vom Plan

Der Plan sagt „bei `schlaeft = true` lautlos". Das Backend zählt im Schlaf aber 0 offene Stunden.
Die Meldung fällt deshalb im Schlaf ganz weg, statt lautlos „0 Stunden" zu zeigen. Der Kanal ist
ohnehin ohne Ton.

## Prüfung

- Neu: `AlltagErinnerungRegelTest` (11 JUnit-Tests) deckt ab:
  - volle Stunden, unter einer Stunde, Zukunft
  - Schlaf und Verfall nach 24 Stunden
  - ohne Eintrag
  - Text
  - Lesen der `/offen`-Antwort, kaputter Stand
  - Startadresse
  
  Vorher rot (fehlende Klassen).
- Prüfbefehl der App `./gradlew testDebugUnitTest assembleDebug`: Exit 0. Alle 58 JVM-Tests sind
  grün, `app-debug.apk` ist gebaut.
- **Noch nicht am Handy gemessen:** Das Fertig-Kriterium im Plan ist „einen Tag lang auf
  Sebastians Handy (Akku-Optimierung/HyperOS)". Dafür muss die APK installiert und einen Tag
  beobachtet werden. Das Ergebnis kommt hier nach.
