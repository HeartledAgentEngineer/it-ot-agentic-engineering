# Android-App „Hey Agent" — Schritt A1b (WebView-Hülle)

Stand: 2026-09-30. Bezug: `../docs/spec-a1-android-hey-agent.md`.
**Status: gebaut und am Handy installiert** (seit 29.09.2026; was davon am Handy belegt ist,
steht unter „Ungeprüft / bekannte offene Punkte").

## Zweck

Eine schlanke Android-App, die das Frontend des Agenten als Vollbild-WebView zeigt
(`http://127.0.0.1:8080/`) und dafür sorgt, dass das Backend läuft: Ist es nicht
erreichbar, startet die App es über Termux und wartet, bis es antwortet. Die Seite darf das
Mikrofon für die Sprachaufnahme nutzen (siehe „Mikrofon“). Weckwort und Gesprächsschleife
folgen in A1c/A1d.

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
| `MikrofonRegel.kt` | Mikrofon-Freigabe für die Seite (nur eigenes Backend, nie Kamera) | ja (JUnit-testbar) |
| `DateiAuswahlRegel.kt` | Büroklammer: Dateiarten für die Android-Auswahl, Rückgabe an die Seite | ja (JUnit-testbar) |
| `Nachkontrolle.kt` | Beim Zurückkehren: lebt das Backend noch? Sonst neu starten / Seite nachladen | ja (JUnit-testbar) |
| `MainActivity.kt` | WebView, Ladebildschirm, Zurück-Taste, Schlüsselabfrage, Mikrofon, Dateiauswahl | nein |
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
werden nach `MikrofonRegel` entschieden (siehe „Mikrofon“); die Büroklammer öffnet nur für das
eigene Backend die Android-Dateiauswahl (siehe „Büroklammer“); `allowBackup=false`.
`mediaPlaybackRequiresUserGesture=false` (Spec 5.5), damit das Vorlesen ohne Extra-Tipp startet.
Zurück-Taste = WebView-Verlauf, danach beendet sie die App.

**Randabstände (Android 15):** Mit `targetSdk 35` zeichnet Android jede App bis unter Status-
und Navigationsleiste (erzwungenes „edge-to-edge"). `MainActivity.randAbstaendeSetzen()` legt
deshalb die Systemleisten, die Kamera-Aussparung und die Tastatur als Innenabstand um den
Inhalt. Ohne das lag die Kopfzeile der Seite unter der Benachrichtigungsleiste (erster Test am
Handy, 29.09.2026).

## Mikrofon

Die Sprachaufnahme im Chat braucht das Mikrofon in der WebView. Seit 30.09.2026:
- Manifest: `RECORD_AUDIO` und `MODIFY_AUDIO_SETTINGS`.
- `MikrofonRegel.entscheide()` (reine Logik, 6 JUnit-Tests): nur das Mikrofon, nur für das eigene
  Backend (`127.0.0.1:8080`/`localhost:8080`). Kamera und fremde Seiten werden immer abgelehnt,
  auch wenn die Kamera zusammen mit dem Mikrofon angefragt wird.
- Fehlt die Android-Erlaubnis, zeigt die App beim ersten Mikrofon-Tipp den Android-Dialog
  „Audio aufnehmen?“. Nach dem Ja bekommt die wartende Anfrage der Seite sofort das Mikrofon.
- Nach zweimaligem Ablehnen zeigt Android den Dialog nicht mehr. Dann bietet die App an, die
  App-Einstellungen (Berechtigungen) direkt zu öffnen.

## Büroklammer (Dateien anhängen)

Die Büroklammer im Chat ist ein `<input type="file" multiple>` mit Bildern und `.pdf`
(`frontend/index.html`). In einer WebView tut so ein Feld **still nichts**, solange die App
`WebChromeClient.onShowFileChooser` nicht umsetzt — genau das war bis 30.09.2026 der Fall
(am Handy bemerkt: Antippen ohne jede Reaktion). Seit 30.09.2026:
- `onShowFileChooser` öffnet die Android-Dateiauswahl (`ACTION_GET_CONTENT`), nur für das eigene
  Backend. Mehrfachauswahl, wenn die Seite `multiple` setzt.
- **Keine neue Berechtigung:** Die Auswahl gibt der App nur die gewählten Dateien frei, jeweils für
  diesen einen Zugriff. `READ_MEDIA_IMAGES` o. Ä. ist nicht nötig und nicht im Manifest.
- `DateiAuswahlRegel` (reine Logik, 10 JUnit-Tests) übersetzt `accept` in MIME-Typen (`.pdf` →
  `application/pdf`, unbekannte Endung → alle Dateiarten) und wählt die Rückgabe: Abbruch → `null`,
  Mehrfachauswahl als Liste ohne Doppelte. Ein Wächter-Test liest `frontend/index.html` und schlägt
  an, wenn die Seite eine Dateiart erlaubt, die die App nicht kennt.
- Die eigene Auswahl statt `FileChooserParams.createIntent()`: Diese nimmt nur den **ersten**
  accept-Typ (dann wären PDFs nicht wählbar) und keine Mehrfachauswahl.
- Kamera-Aufnahme direkt aus der Büroklammer gibt es nicht (bräuchte `CAMERA` und einen
  FileProvider); Fotos kommen aus der Galerie.

## Nachkontrolle beim Zurückkehren

Android kann die Termux-Sitzung jederzeit hart beenden — am 30.09.2026 am Handy gesehen:
`[Process completed (signal 9)]` bei knappem Speicher (`lowmemorykiller … watermark low`),
das Backend lief in der Sitzung und war mit weg; die App merkte es nicht. Seit 30.09.2026 prüft
die App in `onResume` (Rückkehr aus Termux, Dateiauswahl, Startbildschirm, `heyagent://start`):
- **Seite sichtbar, Backend weg** (2 Versuche à 1,5 s) → Neustart wie beim Kaltstart
  (Ladebildschirm, Termux, warten, Seite laden).
- **Fehleransicht sichtbar, Backend wieder da** → Seite laden, ohne „Erneut versuchen“.
- Während ein Start läuft: nie. Regel in `Nachkontrolle` (8 JUnit-Tests).

**Am Handy belegt (30.09.2026 20:27):** Termux per `force-stop` beendet → `/health` 000 →
Hey Agent wieder nach vorn → Log `Nachkontrolle: Backend weg - starte neu` → `Backend-Start:
bereit=true dauer=8111 ms` → `/health` 200.

Grenze: Ist die Termux-Sitzung tot, Termux aber noch offen (`Process completed`), zeigt das
Öffnen nur die tote Sitzung — dann dort Enter drücken und Hey Agent neu öffnen (steht auch in der
Fehlermeldung). Vorbeugend hilft am Handy **Entwickleroptionen → „Einschränkungen für
untergeordnete Prozesse deaktivieren“** (Android 14+); das ist eine Systemeinstellung und bleibt
Sebastians Griff.

## Öffnen von außen: `heyagent://start`

Die App nimmt die Adresse `heyagent://start` an (`launchMode="singleTask"`: ein zweiter Aufruf
holt die laufende App nach vorn). So öffnet das Widget (`start-termux.sh`) sie nach dem
Serverstart. `pm list packages` und `am start -n` funktionieren aus Termux nicht, weil Termux
(`targetSdk 37`) fremde Pakete nicht sieht. Eine Adresse löst Android dagegen immer auf.

## App-Symbol

Adaptives Symbol nur aus Vektoren (`res/mipmap-anydpi-v26/ic_launcher*.xml`, Teile in
`res/drawable/ic_launcher_*.xml`): violetter Verlauf in der Akzentfarbe des Frontends,
weiße Sprechblase mit Sprach-Wellen, kleiner Funke. Alles liegt im sicheren Kreis (Radius 33 dp),
damit runde und eckige Masken nichts abschneiden. Eine einfarbige Fassung (`monochrome`) dient den
„Designfarben"-Symbolen ab Android 13. Achtung: In XML-Kommentaren ist `--` verboten.

## Voraussetzungen zum Bauen (am 10.10.2026 belegt vorhanden)

- JDK 17: **vorhanden** unter `~/.gradle/jdks/eclipse_adoptium-17-amd64-windows.2` (Temurin 17.0.18,
  von Gradle bereitgestellt; liegt nicht im PATH). Bauen damit:
  `JAVA_HOME=~/.gradle/jdks/eclipse_adoptium-17-amd64-windows.2 ./gradlew assembleDebug`.
  Ein JDK **11** (das `jre` von Android Studio) genügt NICHT — AGP 8.7 verlangt 17.
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

## Einrichtung mit dem Play-Store-Termux (einmalig, am Handy)

Das Play-Store-Termux hat keinen `RunCommandService`. Die App öffnet Termux deshalb sichtbar,
und `$PREFIX/etc/profile.d/hey-agent.sh` startet beim Öffnen der Sitzung
`termux/agent-ensure.sh --app-zurueck`: neuesten Stand ziehen (nur `pull --ff-only`, nur wenn
das Handy hinter `origin` liegt), Backend starten, auf `/health` warten (höchstens 45 s), dann
die App über `heyagent://start` zurückholen. Läuft das Backend schon, endet das Skript sofort,
ohne Pull und ohne Rücksprung.

Warum `profile.d` und nicht `~/.bashrc`: Termux startet Sitzungen als Login-Shell (`bash -l`,
am Handy gemessen). Die liest `$PREFIX/etc/profile` und damit `profile.d/*.sh`, aber nicht
`~/.bashrc`. Ein erster Versuch mit `~/.bashrc` lief deshalb ins Leere.

1. Einmal im Projektordner ausführen (darf beliebig oft laufen):
   `sh termux/hey-agent-einrichten.sh`
   Der Eintrag ruft das Skript direkt im Repo auf, deshalb kommen Änderungen mit jedem Pull an.
   Rückgängig: `profile.d/hey-agent.sh` aus dem Ordner verschieben.
2. Akku-Optimierung für Termux ausschalten (Einstellungen → Apps → Termux → Akku →
   „Nicht eingeschränkt“). Mit der Wachhalte-Sperre der Skripte läuft das Backend dann dauerhaft,
   und die App findet es beim Öffnen sofort.

Grenze: Ist in Termux schon eine **offene, untätige** Sitzung, zeigt das Öffnen nur diese an,
und `profile.d` läuft nicht erneut. Dann einmal `exit` in der Sitzung oder das Widget tippen.

## Einrichtung mit dem F-Droid-/GitHub-Termux (einmalig, am Handy)

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

`agent-ensure.sh` startet das Backend **nur**, wenn `/health` nicht antwortet. Vorher zieht es
den neuesten Stand, aber nur als Vorspulen (`pull --ff-only`, nur wenn das Handy hinter
`origin` liegt); eigene Handy-Commits oder lokale Änderungen bleiben unangetastet. Es beendet
keine laufenden Prozesse. Startbefehl wie in `start-termux.sh` (`python -m uvicorn app.main:app
--host "$HOST_BIND" --port 8080 --reload` in `backend/`). Log: `~/agent-ensure.log`. Abgleich in
beide Richtungen + Neustart bleibt `start-termux.sh`.

## Prüfkriterium A1b (aus der Spec)

Termux ist **beendet** (aus der Übersicht weggewischt), App antippen → Chat lädt binnen 60 s
ohne weiteren Fingertipp; `/api/selbsttest` per WebView liefert 200; Log zeigt die Zeit bis
„bereit". Prüfbefehl für den Code: `./gradlew testDebugUnitTest assembleDebug` Exit 0.

## Ungeprüft / bekannte offene Punkte

- **Aus dem Quellstand neu gebaut (10.10.2026, 08:11):** `./gradlew --offline clean assembleDebug`
  → **BUILD SUCCESSFUL in 2m57s, 34 Tasks ausgeführt** (nicht „up-to-date"), Exit 0. Ergebnis
  `app/build/outputs/apk/debug/app-debug.apk`, **9.723.147 Byte**. Kein Quellstand hatte sich seit
  dem Bau vom 30.09. geändert — ein Lauf ohne `clean` meldete zu Recht „up-to-date"; der
  Neubau erzwingt die volle Kette (Kotlin → dex → Package). **Nicht aufs Handy installiert**
  (Geräteeingriff bleibt bei Sebastian).
- **Gebaut und am Handy installiert (29.09.2026):** `assembleDebug` + 12 JUnit-Tests grün,
  installiert per `adb install -r` auf dem motorola edge 50, Start ohne Absturz.
- **Termux-Start aus der App geht mit dem Play-Store-Termux NICHT.** Dort ist Termux in der
  Fassung `googleplay.2026.06.21` installiert, und diese hat keinen `RunCommandService` und
  keine Berechtigung `com.termux.permission.RUN_COMMAND` (am Handy gemessen: `Unable to start
  service … com.termux/.app.RunCommandService … not found`; die App wartete dann 60 s bis
  `ZEITUEBERSCHREITUNG`). Die Schritte 1, 2 und 4 der Termux-Einrichtung oben gelten nur für
  die F-Droid-/GitHub-Fassung. Lösung für das Play-Store-Termux: siehe „Einrichtung mit dem
  Play-Store-Termux“ oben.
- Behoben (29.09.2026, abends): `TermuxLauncher.starte()` wertet jetzt die Rückgabe von
  `startForegroundService` aus (bei fehlendem Dienst `null`) und öffnet Termux dann sofort
  sichtbar, statt 60 s zu warten. **Ende zu Ende am Handy belegt (30.09.2026 00:29):** Termux
  per `force-stop` beendet, Backend aus → Hey Agent gestartet → 00:29:02 Termux geöffnet →
  00:29:11 `heyagent://start` aus Termux → `Backend-Start: bereit=true dauer=10080 ms`.
- **Büroklammer (30.09.2026): gebaut, 28/28 JUnit-Tests grün, am Handy noch nicht Ende zu Ende
  belegt.** Offen ist der Upload selbst: Die WebView läuft mit `allowContentAccess=false`; das
  betrifft nach der Android-Doku das Laden von `content://`-Adressen, nicht die Dateiauswahl —
  belegt ist es erst mit einem echten Anhang am Handy.
- `agent-ensure.sh`: nur `sh -n` (Syntax) geprüft, nicht in Termux ausgeführt. Die Shebang zeigt
  auf den Termux-`sh`, weil Termux kein `/bin/sh` hat.
- Stirbt das Backend, während die Seite offen **und im Vordergrund** ist, merkt die App es erst
  beim nächsten Zurückkehren (Nachkontrolle in `onResume`), nicht sofort.
- Schlüssel-Eingabe bei Fehleingabe: falscher Schlüssel wird nicht validiert; ändern/löschen
  vorerst nur durch App-Daten löschen.
- Nicht Teil von A1b: Weckwort, Vordergrunddienst, native Wiedergabe, Timer/Wecker,
  Standard-Assistent.
