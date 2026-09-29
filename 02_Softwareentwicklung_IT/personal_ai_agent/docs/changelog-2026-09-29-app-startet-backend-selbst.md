# Hey Agent startet das Backend selbst (29.09.2026, abends)

## Ziel

Hey Agent ist der einzige Einstieg: App antippen, und das Backend läuft, ohne Widget.
Das ist die Grundlage für den späteren Start per Weckwort.

## Befund

Das Play-Store-Termux (`googleplay.2026.06.21`) hat keinen `RunCommandService`. Die App
konnte Termux deshalb nicht fernsteuern. Außerdem wertete sie die Absage nicht aus
(`startForegroundService` liefert dann `null`) und wartete die vollen 60 s.

## Änderung

- **App (`TermuxLauncher.kt`):** `starte()` versucht zuerst `RUN_COMMAND` (F-Droid-Termux).
  Liefert Android `null` oder eine Ausnahme, öffnet die App Termux sofort sichtbar.
- **Termux (`termux/agent-ensure.sh`):** neuer Schalter `--app-zurueck`, gedacht für den
  Aufruf aus `~/.bashrc` beim Öffnen einer Termux-Sitzung:
  1. Läuft das Backend: sofort Ende, kein Pull, kein Rücksprung.
  2. Sonst den neuesten Stand ziehen, nur `pull --ff-only` und nur, wenn das Handy hinter
     `origin` liegt. Eigene Handy-Commits und lokale Änderungen bleiben unangetastet.
  3. Backend starten, bis zu 45 s auf `/health` warten.
  4. Die App über `heyagent://start` zurückholen.
- **Einrichtung (einmalig, in Termux):** eine Zeile in `~/.bashrc`, siehe `android/README.md`,
  Abschnitt „Einrichtung mit dem Play-Store-Termux“. Dazu Akku-Optimierung für Termux aus,
  damit das Backend dauerhaft läuft.

## Prüfung

- Neu: `backend/tests/test_agent_ensure_app.py`, 5 Wächter-Tests (offline, lesen Skript und
  Kotlin-Quelle). Vor der Änderung waren 4 davon rot.
- `bash -n termux/agent-ensure.sh`: Exit 0.
- `assembleDebug` + 12 JUnit grün, App per `adb install -r` auf dem Handy.
- Prüfbefehl des Projekts: siehe Commit.

## Offen

- Der Weg App → Termux → `~/.bashrc` → zurück zur App ist am Handy noch **nicht** Ende zu
  Ende belegt. Das zeigt der erste Start mit ausgeschaltetem Backend.
- Grenze: Ist in Termux schon eine offene, untätige Sitzung, läuft `~/.bashrc` beim Öffnen
  nicht erneut.
- Läuft das Backend dauerhaft, kommt ein neuer Stand nur beim nächsten Start oder per Widget
  an.
