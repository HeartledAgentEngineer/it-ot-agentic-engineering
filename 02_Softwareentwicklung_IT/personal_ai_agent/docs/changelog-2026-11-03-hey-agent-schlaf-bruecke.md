# Changelog 03.11.2026 — Hey Agent liest den Schlaf aus Health Connect (Issue #12)

## Was

- `SchlafLeser.kt`: liest `SleepSessionRecord` der letzten 30 Tage (nur `READ_SLEEP`).
- `SchlafUebertragung.kt`: Stufen 0..7 → `unbekannt/wach/schlafend/aus_dem_bett/leicht/tief/rem/wach`,
  Zeiten als ISO mit Offset (`+00:00` statt `Z`), JSON im Format von `POST /api/alltag/schlaf`,
  JS-Aufruf mit maskiertem String (kein Ausbruch über `"`, `'`, `<`, U+2028).
- `MainActivity.kt`: Brücke `window.HeyAgentSchlaf.abgleichen()`, Health-Connect-Erlaubnisdialog
  (nur auf Knopfdruck), stiller Abgleich einmal pro App-Start, Rückgabe an die Seite nur, wenn
  sie vom eigenen Backend kommt.
- Manifest: `android.permission.health.READ_SLEEP`, Pflicht-Erklärseite
  `SchlafErklaerungActivity` + Alias für `VIEW_PERMISSION_USAGE`, Paket-Sichtbarkeit Health Connect.
- `frontend/schlaf.js`: zweiter Empfänger `window.heyAgentSchlafMeldung(text)`; Cache `schlaf.js?v=20261103B`.
- App-Version 0.2-schlaf (versionCode 2).

## Warum

Termux darf Health Connect nicht lesen, nur eine Android-App mit Erlaubnis. Hey Agent ist
schon die App, in der die Seite läuft — der kürzeste Weg ohne neue App und ohne Netz.

## Prüfung

- `gradlew testDebugUnitTest`: alle JUnit-Tests grün, davon 7 neu (`SchlafUebertragungTest`,
  vorher mit `TODO()`-Gerüst rot).
- `gradlew assembleDebug`: grün.
- `node tests/test_schlaf.js schlaf.js`: grün.
- **Nicht geprüft:** echter Abgleich am Handy (Gerät war beim Bau nicht verbunden).
