# Änderungsprotokoll 30.09.2026 — Hey Agent: Nachkontrolle beim Zurückkehren

## Anlass (am Handy belegt, 20:20)

`/health` über `adb forward` → HTTP 000, obwohl Termux und Hey Agent liefen. Im Termux-Fenster:
Start-Eintrag hatte das Backend gestartet („Backend bereit nach 4 s“), danach
`[Process completed (signal 9) - press Enter]`. Im Log zur selben Zeit mehrfach
`lowmemorykiller: Kill … reason: device is in medium stall and watermark low`.
Android hat die Termux-Sitzung hart beendet, das Backend lief darin und war mit weg.
Die App prüfte `/health` nur beim Kaltstart und zeigte danach eine tote Seite.

## Änderung

- Neu `android/app/src/main/java/de/sebastian/heyagent/Nachkontrolle.kt` (reine Logik):
  prüfen nur, wenn kein Start läuft und nicht der Ladebildschirm zu sehen ist; Seite + Backend weg
  → neu starten; Fehleransicht + Backend wieder da → Seite laden; „weg“ erst nach 2 Versuchen
  à 1,5 s (ein Aussetzer startet nichts neu).
- `MainActivity.kt`: merkt sich die Ansicht (Seite/Laden/Fehler), `onResume` fährt die
  Nachkontrolle im Hintergrund-Thread; ändert sich die Lage währenddessen, passiert nichts.
- `BackendStartLogik.fehlerText(ZEITUEBERSCHREITUNG)`: nennt jetzt den Fall
  „Process completed“ (Enter drücken, Hey Agent neu öffnen).
- Neu `NachkontrolleTest.kt`: 8 JUnit-Tests.
- `android/README.md`: Abschnitt „Nachkontrolle beim Zurückkehren“, Klassentabelle, offene Punkte.

## Prüfung

- `gradle --no-daemon testDebugUnitTest assembleDebug` → BUILD SUCCESSFUL, Exit 0;
  JUnit **36/36 grün** (BackendStartLogik 12, DateiAuswahlRegel 10, MikrofonRegel 6,
  Nachkontrolle 8).
- **Am Handy Ende zu Ende (20:27):** installiert, `am force-stop com.termux` → `/health` 000 →
  Home, dann `heyagent://start` → Log `Nachkontrolle: Backend weg - starte neu`,
  `Backend-Start: bereit=true dauer=8111 ms` → `/health` 200, Hey Agent vorn.

## Offen

- Vorbeugung gegen das Beenden: Entwickleroptionen → „Einschränkungen für untergeordnete
  Prozesse deaktivieren“ (Systemeinstellung, Sebastians Griff).
- Tote Sitzung bei offenem Termux („Process completed“) braucht weiter ein Enter von Hand.
