# Hey Agent: Mikrofon für die Seite (30.09.2026)

## Anlass

Erster Test der Sprachaufnahme in der App: „Mikrofon nicht verfügbar … Permission denied“. Die
App lehnte bisher jede Mikrofon-Anfrage der Seite ab (`onPermissionRequest` → `deny()`), und das
Manifest hatte kein `RECORD_AUDIO`. Das war bewusst für den ersten Bauabschnitt so gewählt.

## Änderung

- Manifest: `RECORD_AUDIO` + `MODIFY_AUDIO_SETTINGS`.
- Neu `MikrofonRegel.kt`: reine Entscheidungsregel `ERLAUBEN` / `ANDROID_FRAGEN` / `ABLEHNEN`.
  Nur das Mikrofon, nur für die Seite des eigenen Backends, nie die Kamera.
- `MainActivity`:
  - `onPermissionRequest` folgt der Regel.
  - Fehlt die Android-Erlaubnis, startet der Android-Dialog („Audio aufnehmen?“, über
    `ActivityResultContracts.RequestPermission`). Die Anfrage der Seite wartet und bekommt nach
    dem Ja das Mikrofon.
  - Nach dauerhaftem Ablehnen öffnet ein Hinweis auf Wunsch die App-Einstellungen
    (`ACTION_APPLICATION_DETAILS_SETTINGS`).

## Prüfung

- Neu `MikrofonRegelTest.kt`: 6 JUnit-Tests. Zusammen mit `BackendStartLogikTest` 18 von 18 grün.
- `assembleDebug` grün, per `adb install -r` auf dem Handy. `dumpsys package`: `RECORD_AUDIO`
  angemeldet, noch nicht erteilt (der Dialog kommt beim ersten Mikrofon-Tipp).
- Offen: Der Tipp aufs Mikrofon am Handy (Dialog → Aufnahme) ist noch nicht belegt.
