# Android-App „Hey Agent" — Schritt A1b (WebView-Hülle)

Stand: 2026-09-29. Bezug: `../docs/spec-a1-android-hey-agent.md`.
**Status: Quellcode geschrieben, noch nie gebaut** (kein Android-SDK auf dem PC, siehe „Ungeprüft").

## Zweck

Eine schlanke Android-App, die das Frontend des Agenten als Vollbild-WebView zeigt
(`http://127.0.0.1:8080/`) und dafür sorgt, dass das Backend läuft: Ist es nicht
erreichbar, startet die App es über Termux und wartet, bis es antwortet. Mikrofon,
Weckwort und Gesprächsschleife folgen in A1c/A1d — das Manifest hat bewusst noch
**kein** `RECORD_AUDIO`.

## Architektur (Ausschnitt A1b aus der Spec)

```
+---------------- Android-App "Hey Agent" (Kotlin) -----------------+
|  MainActivity: Ladebildschirm  ->  WebView -> http://127.0.0.1:8080 |
|  BackendWaechter: GET /health (2 s) -> ggf. Termux starten -> Poll   |
|  TermuxLauncher: RUN_COMMAND-Intent -> ~/agent-ensure.sh             |
|  KeySpeicher: API-Schluessel in EncryptedSharedPreferences           |
+----------------------------------------------------------------------+
        | Intent (com.termux.RUN_COMMAND)      | HTTP Loopback
        v                                      v
   Termux --> agent-ensure.sh --> uvicorn :8080 (FastAPI, Backend)
```

Klassen (`app/src/main/java/de/sebastian/heyagent/`):

| Datei | Aufgabe | Android-frei? |
|---|---|---|
| `BackendStartLogik.kt` | Zeit-/Pollinglogik, Status- und Fehlertexte | ja (JUnit-testbar) |
| `BackendWaechter.kt` | Ablauf Health-Check → Start → Polling, `HttpHealthPruefer` | ja (JUnit-testbar) |
| `TermuxLauncher.kt` | Intent an Termux, „Termux öffnen" | nein |
| `KeySpeicher.kt` | verschlüsselter Schlüsselspeicher | nein |
| `MainActivity.kt` | WebView, Ladebildschirm, Zurück-Taste, Schlüsselabfrage | nein |
| `AppKonfig.kt` | Adresse, Port, Termux-Pfade an einer Stelle | ja |

Die `applicationId` (`de.sebastian.heyagent`) steht in `app/build.gradle.kts`
(zusammen mit `namespace`); ändern = dort zwei Zeilen und das Kotlin-Paket.

## API-Schlüssel: gewählter Weg

**Befund aus dem Code (nur gelesen):** `frontend/index.html` lädt `<script src="api/konfig">`.
Der Backend-Endpunkt `/api/konfig` (`backend/app/main.py`, bewusst ohne Schlüssel erreichbar)
liefert `window.__API_KEY__ = "…"`, und `frontend/app.js` (Z. 32–59) patcht damit `window.fetch`
so, dass jeder Aufruf an `/api/*` automatisch den Kopf `X-API-Key` bekommt.

**Folge:** Die WebView braucht für die Seite selbst **keine** Schlüssel-Injektion — weder
`shouldInterceptRequest` (sähe ohnehin keinen POST-Body) noch `evaluateJavascript`. Ein per
JS gesetztes `window.__API_KEY__` würde vom `api/konfig`-Skript ohnehin überschrieben.

Trotzdem, wie gefordert:
- Erster Start: Eingabemaske (Passwortfeld) für den Schlüssel → `EncryptedSharedPreferences`
  (AES-256, Android-Keystore). „Später" ist möglich; die App fragt dann nicht wieder.
- Der gespeicherte Schlüssel geht als Kopf `X-API-Key` in `loadUrl(url, headers)` (nur die
  erste Dokument-Anfrage) und steht den **nativen** Aufrufen der nächsten Schritte (Transkript,
  `/api/speak` aus dem Hintergrunddienst in A1c/A1d) zur Verfügung — dort gibt es keine
  Seite, die ihn selbst abholt.
- Der Schlüssel steht nie im Code oder Repo und wird nie geloggt.

Sicherheitshinweis: `/api/konfig` ist offen. Schutz gegen Fremde im WLAN ist laut Backend-Kommentar
`HOST_BIND=127.0.0.1`; die App spricht ohnehin nur den Loopback an.

## WebView-Härtung

JavaScript und DOM-Storage an; `allowFileAccess=false`, `allowContentAccess=false`,
`MIXED_CONTENT_NEVER_ALLOW`; Klartext-HTTP nur für `127.0.0.1`/`localhost`
(`res/xml/network_security_config.xml`, Basis = kein Klartext); Navigation zu fremden Adressen
wird an den Browser übergeben statt in der WebView geladen; Mikrofon-/Kamera-Anfragen der Seite
werden abgelehnt (das Mikrofon gehört später dem nativen Dienst); `allowBackup=false`.
`mediaPlaybackRequiresUserGesture=false` (Spec 5.5), damit das Vorlesen ohne Extra-Tipp startet.
Zurück-Taste = WebView-Verlauf, danach beendet sie die App.

**Randabstände (Android 15):** Mit `targetSdk 35` zeichnet Android jede App bis unter Status-
und Navigationsleiste (erzwungenes „edge-to-edge"). `MainActivity.randAbstaendeSetzen()` legt
deshalb die Systemleisten, die Kamera-Aussparung und die Tastatur als Innenabstand um den
Inhalt. Ohne das lag die Kopfzeile der Seite unter der Benachrichtigungsleiste (erster Test am
Handy, 29.09.2026).

## App-Symbol

Adaptives Symbol nur aus Vektoren (`res/mipmap-anydpi-v26/ic_launcher*.xml`, Teile in
`res/drawable/ic_launcher_*.xml`): violetter Verlauf in der Akzentfarbe des Frontends,
weiße Sprechblase mit Sprach-Wellen, kleiner Funke. Alles liegt im sicheren Kreis (Radius 33 dp),
damit runde und eckige Masken nichts abschneiden. Eine einfarbige Fassung (`monochrome`) dient den
„Designfarben"-Symbolen ab Android 13. Achtung: In XML-Kommentaren ist `--` verboten.

## Voraussetzungen zum Bauen (noch nicht installiert)

- JDK 17 (vorhanden: Temurin 17.0.18)
- Android-SDK-Kommandozeilentools (`cmdline-tools/latest`) mit
  `sdkmanager "platforms;android-35" "build-tools;35.0.0" "platform-tools"` und akzeptierten Lizenzen
- `local.properties` mit `sdk.dir=…` (ist gitignored)
- Gradle-Wrapper: **die Jar-Datei ist nicht eingecheckt** (Binärdatei). Es liegt nur
  `gradle/wrapper/gradle-wrapper.properties` (Gradle 8.9). Beim ersten Bau einmal
  `gradle wrapper` ausführen (braucht ein installiertes Gradle; alternativ die Wrapper-Dateien
  aus Android Studio übernehmen); danach genügt `./gradlew`.
- Plugin-Versionen: AGP 8.7.3, Kotlin 2.0.21, `security-crypto` 1.1.0-alpha06 (alle nicht
  getestet — bei Auflösungsfehlern Versionen anpassen).

## Bauen und Installieren

```
cd 02_Softwareentwicklung_IT/personal_ai_agent/android
gradle wrapper                       # einmalig, erzeugt gradlew(.bat) + Wrapper-Jar
./gradlew testDebugUnitTest          # reine JVM-Tests (BackendStartLogikTest)
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

(Windows: `gradlew.bat` statt `./gradlew`.) Zeit bis „bereit" steht im Logcat:
`adb logcat -s HeyAgent` → Zeile `Backend-Start: bereit=… dauer=… ms`.

## Einrichtung Termux (einmalig, am Handy)

1. `~/.termux/termux.properties`: Zeile `allow-external-apps=true` eintragen, dann
   `termux-reload-settings`. Ohne das ignoriert Termux den Intent.
2. Skript ins Home kopieren und ausführbar machen:
   `cp <Repo>/02_Softwareentwicklung_IT/personal_ai_agent/termux/agent-ensure.sh ~/agent-ensure.sh && chmod +x ~/agent-ensure.sh`
   (Die App ruft den festen Pfad `/data/data/com.termux/files/home/agent-ensure.sh`. Nach Änderungen im Repo erneut kopieren.)
3. Das Skript findet den Projektordner über den Symlink `~/.shortcuts/agent` (Einrichtung von
   `start-termux.sh`, siehe dort); alternativ `PROJEKT=…` setzen.
4. In den Android-Einstellungen der App „Hey Agent" die Berechtigung „Termux-Befehle ausführen"
   (`com.termux.permission.RUN_COMMAND`) erteilen (Einstellungen → Apps → Hey Agent → Berechtigungen → Zusätzliche Berechtigungen; Bezeichnung je nach Hersteller).
5. Empfohlen: Akku-Optimierung für Termux auf „Nicht optimieren" (Hintergrundstart, Spec 5.1).

`agent-ensure.sh` startet das Backend **nur**, wenn `/health` nicht antwortet: kein `git pull`,
kein Beenden laufender Prozesse. Startbefehl wie in `start-termux.sh`
(`python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload` in `backend/`).
Log: `~/agent-ensure.log`. „Update + Neustart" bleibt `start-termux.sh`.

## Prüfkriterium A1b (aus der Spec)

Termux ist **beendet** (aus der Übersicht weggewischt), App antippen → Chat lädt binnen 60 s
ohne weiteren Fingertipp; `/api/selbsttest` per WebView liefert 200; Log zeigt die Zeit bis
„bereit". Prüfbefehl für den Code: `./gradlew testDebugUnitTest assembleDebug` Exit 0.

## Ungeprüft / bekannte offene Punkte

- **Nichts davon wurde gebaut oder gestartet.** Kotlin- und XML-Quellcode nur von Hand
  gegengelesen; kein `kotlinc`, kein Android-SDK auf dem PC. Die JUnit-Tests sind nie gelaufen
  (ihre Erwartungswerte wurden von Hand durchgerechnet). Compilerfehler beim ersten Bau sind möglich.
- `agent-ensure.sh`: nur `sh -n` (Syntax) geprüft, nicht in Termux ausgeführt. Die Shebang zeigt
  auf den Termux-`sh`, weil Termux kein `/bin/sh` hat.
- Ob der `RUN_COMMAND`-Start bei ausgeschaltetem Bildschirm/aus dem Hintergrund klappt, ist
  ungeklärt (Spec 5.1) — in A1b startet die sichtbare App.
- Kein Launcher-Symbol gestaltet (Standardsymbol des Systems).
- Der Ladebildschirm zeigt keinen Neustart, falls das Backend erst nach dem Laden der Seite stirbt
  (nur `onReceivedError` der Hauptseite → Fehleransicht).
- Schlüssel-Eingabe bei Fehleingabe: falscher Schlüssel wird nicht validiert; ändern/löschen
  vorerst nur durch App-Daten löschen.
- Nicht Teil von A1b: Mikrofon, Weckwort, Vordergrunddienst, native Wiedergabe, Timer/Wecker,
  Standard-Assistent.
