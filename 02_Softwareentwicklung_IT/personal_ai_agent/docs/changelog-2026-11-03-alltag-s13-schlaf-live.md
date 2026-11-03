# Changelog 03.11.2026 – Alltag S13: still im Schlaf, Meldung nach dem Aufwachen

**Wunsch Sebastian:** Kein Pop-up, solange er schläft. Abends gehen die Erinnerungen stündlich weiter, bis er schläft. Eine Stunde nach dem Aufwachen soll kommen: „Was hast du gemacht, wie geht's dir?". Die Lücke vor dem Schlafengehen wird nicht nachgefragt. Nachtragen geht weiter von Hand.

## Regel (`AlltagErinnerungRegel`, JUnit-getestet)

- **Abends live** (S13b):
  - Schlaf gilt, wenn der Bildschirm seit 45 Minuten aus ist und zwischen 20:00 und 3:00 ausgeschaltet wurde.
  - Kurzes Aufleuchten unter 2 Minuten, etwa durch eine Nachricht, zählt nicht.
  - Liefert die Uhr Puls nach Health Connect und liegt der Schnitt der letzten 30 Minuten über 75, gilt Sebastian als wach. Die Schwelle ist eine Annahme und wird später nachgestellt.
  - Im Live-Schlaf ist nichts offen. Ein Eintrag nach dem Einschlafen hebt ihn auf.
- **Nachtruhe ab 3:00:**
  - Sie endet mit dem Aufwachen laut Uhr (spätestes Sitzungsende in der Ruhezeit) oder mit einem eigenen Eintrag, spätestens um 11:00.
  - Was abends offen war, verfällt.
- **Morgens:** Eine Stunde nach dem Aufwachen kommt „Guten Morgen! Du bist seit 1 Stunde wach – was hast du gemacht, wie geht's dir?".
- **Nickerchen am Tag** beenden keine Ruhezeit.
- **Bewusst geänderter Test:** Die alte Erwartung „Schlaf-Knopf verfällt nach 24 h → 26 Stunden offen" heißt jetzt 4, weil die Nacht nicht mehr mitzählt.

## App

- **`BildschirmLeser`** (neu):
  - Liest nur „Bildschirm an/aus" der letzten 12 Stunden, keine App-Namen.
  - Braucht den Nutzungsdatenzugriff. Ohne ihn liefert er eine leere Liste.
- **`SchlafLeser`:**
  - Neu sind die Erlaubnisse Puls (`READ_HEART_RATE`) und Lesen im Hintergrund, sofern das Handy es kann.
  - Ebenfalls neu sind die Enden der Schlafsitzungen sowie die Pulswerte der letzten Stunde.
- **Worker** (`CoroutineWorker`, stündlich):
  - Holt Aufwachzeit und Puls im Hintergrund.
  - Fängt jeden Fehler ab.
  - Schreibt nur Anzahlen ins Log.
- **Knopf „Mit der Uhr abgleichen":** Fragt Schlaf, Puls und Hintergrund zusammen. Danach bietet er einmal je App-Start den Nutzungsdatenzugriff an.
- **Gespeichert** wird nur der Zeitpunkt des Aufwachens. Der Live-Schlaf wird jede Stunde neu entschieden und nicht gemerkt.
- **Version** 0.4-aufwachen (versionCode 4).

## Grenzen

- Health Connect zeigt eine Schlafsitzung erst nach dem Aufwachen und dem Abgleich der Uhr-App. Bis dahin bleibt es morgens still, längstens bis 11:00.
- Wer abends lange ohne Handy fernsieht, gilt womöglich als schlafend. Laut Sebastian sind die Abendmeldungen am wenigsten wichtig.
- Eine eigene Wear-OS-App auf der Uhr (Xiaomi Watch 2 Pro) könnte den Schlaf direkt melden. Sie ist ein eigener, späterer Abschnitt.
