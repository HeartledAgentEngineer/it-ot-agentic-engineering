# Changelog 01.10.2026 — Gradle-Wrapper für die Android-App (Spec A1a erfüllt)

## Was gefehlt hat

Die Spec `docs/spec-a1-android-hey-agent.md` fordert für Schritt A1a:
„SDK per Kommandozeile, Gradle-Wrapper, leeres Projekt `android/` baut —
Prüfkriterium `gradlew.bat assembleDebug` Exit 0".

Im Projekt lagen aber nur `android/gradle/wrapper/gradle-wrapper.properties` und
`android/local.properties`. **Es fehlten `gradlew`, `gradlew.bat` und
`gradle/wrapper/gradle-wrapper.jar`** — der Bau war damit nur mit einer
handinstallierten Gradle-Version möglich, nicht mit dem einen Befehl aus der
Spec. Zusätzlich: `gradle` lag nicht im Suchpfad.

## Änderung

Der Wrapper wurde mit der auf dem PC vorhandenen Gradle-Version **8.9**
erzeugt (`gradle wrapper --gradle-version 8.9`):

| Datei | Größe |
|---|---|
| `android/gradlew` | 8.762 Bytes |
| `android/gradlew.bat` | 2.966 Bytes |
| `android/gradle/wrapper/gradle-wrapper.jar` | 43.504 Bytes |

Unverändert geblieben sind `gradle-wrapper.properties`, `local.properties`
(SDK-Pfad `C:/Users/sebas/tools/android-sdk`) und sämtlicher Kotlin-Code.

## Beweis (frisch gefahren, 01.10.2026)

```
cd 02_Softwareentwicklung_IT/personal_ai_agent/android
export JAVA_HOME="C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
./gradlew assembleDebug --console=plain
→ BUILD SUCCESSFUL in 43s | 33 actionable tasks: 33 up-to-date | Exit 0
```

Damit ist das Prüfkriterium aus A1a erfüllt — der Bau **wiederholt** sich mit
einem Befehl, ohne dass Gradle vorher von Hand installiert werden muss.

## Befund: die App ist schon gebaut und läuft am Handy

Die dabei gefundene APK `android/app/build/outputs/apk/debug/app-debug.apk`
(9.962.383 Bytes) ist vom **30.09.2026, 20:26** und damit aus Claudes
Abend-Dauerlauf (Journal: S1 „App-Nachkontrolle `e5f3c3d`, am Handy belegt —
force-stop → bereit nach 8,1 s"). Der Bauzustand ist also nicht nur behauptet,
sondern lag fertig vor; mein Lauf hat nur die **Wiederholbarkeit** belegt.

## Was jetzt fehlt (unverändert)

- **A1c** Hörer-Dienst in der App (openWakeWord offline, Vordergrunddienst,
  Dauer-Benachrichtigung) — der Kern der „offenen Pipeline", Issue #1, Code
  bereitet die Cloud-Sitzung vor.
- **A1d** Gesprächsschleife (Weckwort → Aufnahme → Transkript → Chat →
  Vorlesen, Folge-Modus 8 s).
- **T4** aus Claudes Plan: Live-Probe des Werkzeug-Schalters am Handy, mit
  Sebastian.

Erstellt von Hermes (Ausführer), 01.10.2026.
