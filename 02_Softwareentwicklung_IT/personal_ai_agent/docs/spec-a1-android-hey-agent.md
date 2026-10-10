# Spec A1 — Android-App „Hey Agent"

Stand: 2026-09-29 · Status: Entwurf zur Entscheidung (kein Code) · Bezug: Backend läuft nur auf dem Handy (Termux, Port 8080).

## 1. Ziel (Priorität)

1. „Hey Agent" sagen -> Gespräch wie Gemini: sprechen, Antwort wird vorgelesen, Bilder erscheinen, Folgefragen ohne erneutes Weckwort.
2. Beim Aufruf läuft das Backend: die App startet Termux selbst im Hintergrund und wartet auf den Health-Check.
3. (nachrangig) Timer/Wecker.

## 2. Nicht-Ziele

- Kein Cloud-Weckwort, kein Google-/Picovoice-Dienst fürs Dauerlauschen.
- Keine native Neuschreibung von Chat, Galerie, Diashow (bleibt `frontend/`).
- Kein Play-Store-Release, keine Release-Signatur (zunächst Debug-Signatur, Installation per `adb install`).
- Kein Backend auf dem PC, kein Root, kein Ersetzen von Termux.
- Timer/Wecker erst nach A1e.

## 3. Ist-Stand (aus dem Code gelesen)

- `start-termux.sh`: git-Abgleich, Storage-Setup, `termux-wake-lock`, alte uvicorn/Daemon beenden, dann `python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload &`. Die Datei ist über `~/.shortcuts/agent` (Termux:Widget) verlinkt. Dauer bis „bereit": nicht gemessen (in A1b messen).
- Auth: alle `/api/*`-Router verlangen `X-API-Key` (`auth.require_api_key`); offen sind `/api/health`, `/health`, `/ping`, `/status`.
- Passende Endpunkte: `POST /api/sprache/transkript` (multipart `file`, WAV -> `{text}`), `POST /api/chat/stream`, `POST /api/chat`, `POST /api/speak` (Text -> MP3, `voice`/`model` optional), `GET /api/voices`, `/api/erzaehlen/*` (Ereignisse, Geschichten), `/api/fotos/*`, `/api/selbsttest`.
- Frontend: Spracheingabe (`startRecording`/`stopRecording`/`encodeWav`, `pcm-recorder.js`), Vorlesen (`speakResponse`, `addSpeakControls`, Vorleser-Objekt in `finishReply`), Diashow `erzaehlen.js`. Aufnahme dort per Knopf, ohne Sprechende-Erkennung, ohne Dauerschleife.

## 4. Architektur (Text)

```
+------------------------- Android-App "Hey Agent" (Kotlin) --------------------------+
|  MainActivity (WebView -> http://127.0.0.1:8080)   <-- JS-Brücke "HeyAgent" -->      |
|        ^ zeigt Chat, Bilder, Diashow, spielt TTS-MP3 (bestehender Code)              |
|        |                                                                             |
|  ListenService (Foreground-Service, Typ microphone, dauerhafte Notification)         |
|    AudioRecord 16 kHz -> [Weckwort: openWakeWord ONNX] -> [VAD + Aufnahme] -> WAV    |
|                                                            |                         |
|  BackendClient (OkHttp, X-API-Key aus Keystore) <----------+                         |
|    /api/health (Warten)  /api/sprache/transkript  -> Text -> WebView.agentSend(text) |
|  TermuxLauncher: RUN_COMMAND-Intent -> start-termux.sh (Hintergrund)                 |
+----------------------------------------------------------------------------------------+
        | Intent                                   | HTTP localhost
        v                                          v
   Termux (Foreground-Service) --> uvicorn :8080 (FastAPI) --> OpenRouter (nur nach Weckwort)
```

Kernidee: **Natives Kotlin besitzt das Mikrofon für die ganze Gesprächsschleife** (Weckwort, VAD, Aufnahme). Die WebView besitzt Anzeige und Wiedergabe. Grund: Zwei gleichzeitige Mikrofon-Nutzer (Service-`AudioRecord` und WebView-`getUserMedia`) stören sich — Android 10+ schaltet die Aufnahme der nicht im Vordergrund liegenden App stumm bzw. bevorzugt die sichtbare. Ein einziger Besitzer vermeidet das.

## 5. Komponenten

### 5.1 Termux-Start (`TermuxLauncher`)

Mechanik nach [Termux-Wiki RUN_COMMAND](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent):
- App-Manifest: `<uses-permission android:name="com.termux.permission.RUN_COMMAND"/>`; Nutzer gewährt sie einmal in den App-Einstellungen (Berechtigung „Termux-Befehle ausführen").
- In Termux einmalig: `allow-external-apps=true` in `~/.termux/termux.properties`, danach `termux-reload-settings`. Ohne das ignoriert Termux den Intent. Setzt `termux/hey-agent-einrichten.sh` inzwischen selbst (idempotent, wird bei jedem Start geprüft).
- Intent an `com.termux/com.termux.app.RunCommandService`, Action `com.termux.RUN_COMMAND`, Extras: `RUN_COMMAND_PATH` (`/data/data/com.termux/files/home/.shortcuts/agent` oder direkt das Skript), `RUN_COMMAND_BACKGROUND=true`, `RUN_COMMAND_WORKDIR`. Start per `startForegroundService()`.
- Android 12+: Der Start klappt zuverlässig, wenn die Sender-App sichtbar ist. Aus dem Hintergrund kommt bei Termux gelegentlich „Unable to start service Intent" ([Diskussion #3640](https://github.com/termux/termux-app/discussions/3640), [#3470](https://github.com/termux/termux-app/discussions/3470)); Abhilfe laut Maintainer: Akku-Optimierung für Termux **aus** („Nicht optimieren").
- Android-14-Einschränkung betrifft `am` **innerhalb** Termux, nicht den Intent von einer App ([Termux execution environment](https://github.com/termux/termux-packages/wiki/Termux-execution-environment)).
- Wichtig: `start-termux.sh` beendet **laufende** uvicorn-Prozesse und startet neu. Für den Aufruf-Fall ist `termux/agent-ensure.sh` da: erst `curl -sf localhost:8080/health`, dann IMMER die gemeinsame Start-Vorbereitung `termux/start-vorbereiten.sh` (git pull + alle Übernahmen inkl. Wissensdatei `memory.db`; 10.10.2026) — auch bei laufendem Server — und nur bei Fehlschlag von health uvicorn starten (kein Kill, kein Neustart eines laufenden Servers). Das Widget (`termux/agent-start`) nutzt denselben Ablauf. `start-termux.sh` bleibt für „Update + Neustart".

**Empfehlung Normalfall:** App-Start (sichtbar) -> `GET /health` -> bei Fehler `RUN_COMMAND` mit `agent-ensure.sh` -> Poll `/health` alle 1 s, max. 60 s -> WebView laden. **Rückfall:** (a) Nach 60 s Meldung + Knopf „Termux öffnen" (Launch-Intent, Nutzer tippt Widget „agent"). (b) Termux:Boot ([termux-boot](https://github.com/termux/termux-boot)): `~/.termux/boot/agent-ensure.sh` mit `termux-wake-lock` startet das Backend nach Neustart; BOOT_COMPLETED darf Termux (Foreground-Service) starten, unsere Mikrofon-App aber nicht (siehe 5.2). (c) Termux:Tasker ist nur ein Plugin-Weg mit demselben Intent — kein Mehrwert, nicht verwenden.

### 5.2 Weckwort (`ListenService`)

Vergleich:

| Option | Offline | Eigenes Wort | Lizenz/Kosten | Bewertung |
|---|---|---|---|---|
| **openWakeWord** (ONNX, Kotlin-Port [openwakeword-android-kt](https://github.com/IamSanjid/openwakeword-android-kt)) | ja, vollständig | ja, Training aus Text per TTS-Synthese (Colab-Notebook des Projekts) | Code Apache-2.0; **mitgelieferte Modelle CC BY-NC-SA** (privat ok); Lizenz der Feature-Modelle (melspectrogram/embedding) laut [Issue #348](https://github.com/dscripka/openWakeWord/issues/348) ungeklärt | **Empfehlung** — nichtkommerziell/privat unkritisch |
| Porcupine | Audio lokal, aber AccessKey-Prüfung online ([Preise](https://picovoice.ai/pricing/)) | ja (Console) | Free-Plan nur nicht-kommerziell, kommerziell ab 6000 USD/Jahr | Rückfall; Online-Lizenzprüfung widerspricht „nichts nach außen" |
| Vosk-Grammatik (+ Silero-VAD, [Beispiel](https://zenn.dev/diced/articles/vosk-silero-vad-wakeword-android?locale=en)) | ja | ja (Grammatik `["hey agent","[unk]"]`) | Apache-2.0 | volle Spracherkennung dauernd -> mehr CPU/Akku; nur Notlösung |
| Android-eigen (`AlwaysOnHotwordDetector`, Assistant-Hotword) | DSP | nur systemeigene Modelle | `HotwordDetectionService` ist Systemschnittstelle | für Drittapps nicht nutzbar |

Wort-Wahl: „Hey Agent" ist kurz, fremdsprachig und fehlerträchtig; A1c testet zwei Kandidaten (z. B. „Hey Agent", „Hallo Agent") mit selbst trainiertem Modell. Falschauslösung/Verpassen wird am Handy gemessen (Schwelle einstellbar).

Foreground-Service ([Typen](https://developer.android.com/develop/background-work/services/fgs/service-types), [Android 14](https://developer.android.com/about/versions/14/changes/fgs-types-required)):
- Manifest: `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`, `RECORD_AUDIO`, `POST_NOTIFICATIONS`; Service mit `android:foregroundServiceType="microphone"`.
- **Harte Regel Android 14:** Ein Mikrofon-Service darf **nicht aus dem Hintergrund** gestartet werden (while-in-use), auch nicht aus BOOT_COMPLETED ([Ausnahmen](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start): Start per sichtbarer Activity, Notification-Tap, Widget, oder App ist `VoiceInteractionService`-Anbieter). Folge: Nach jedem Neustart/Kill muss der Nutzer die App **einmal** öffnen (oder die Benachrichtigung antippen). Danach läuft der Service im Hintergrund weiter. Mit Assistenten-Rolle (5.3) entfällt diese Einschränkung.
- Sichtbarkeit: dauerhafte Notification „Hey Agent hört zu" (Pflicht) und grüner Mikrofon-Punkt in der Statusleiste (Android 12+, nicht abschaltbar). Umschalter „Zuhören an/aus" in Notification.
- Akku: Herstellerangaben für Wake-Word-Engines liegen bei ~1 % pro Stunde (Vendor-Claims, nicht belegt); openWakeWord auf dem Snapdragon der Edge 50 ist laut Projekt für Echtzeit-Betrieb auf schwacher Hardware gedacht — **Messwert kommt aus A1c** (24-h-Test, `adb shell dumpsys batterystats`). Sparmaßnahme: einfacher Energie-Vorfilter vor dem Modell (Modell nur bei Sprache rechnen), Ausschalten bei Ladekabel-Nichtnutzung optional.
- Nach Weckwort fällt der Vorfilter weg, die Schleife (5.4) übernimmt das Mikrofon; WebView nimmt **nie** selbst auf.

### 5.3 Standard-Assistent (optional, Stufe A1e)

- Mechanik: `VoiceInteractionService` + `VoiceInteractionSessionService` + `android.voice_interaction`-XML im Manifest (`BIND_VOICE_INTERACTION`), Rolle per `RoleManager.createRequestRoleIntent(ROLE_ASSISTANT)` ([RoleManager](https://developer.android.com/reference/android/app/role/RoleManager), [AOSP VoiceInteractionService](https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/service/voice/VoiceInteractionService.java)). Auf Motorola (Android 14/15) wählt der Nutzer die App unter Einstellungen -> Apps -> Standard-Apps -> Digitaler Assistent; Power-Taste lang / Wisch aus der Ecke startet dann die Session.
- Vorteil: (1) Power-Taste ruft uns statt Gemini, (2) Mikrofon-Service darf aus dem Hintergrund/Boot starten (Ausnahme `VoiceInteractionService`), (3) System hält den Service am Leben.
- Aufwand: gering bis mittel für die Hülle (Session öffnet `MainActivity` mit Gesprächsmodus); **Risiko:** Hersteller-Verhalten (Moto-Gesten, Google-App fordert Rolle zurück), nur ein Assistent gleichzeitig -> Gemini-Funktionen des Handys entfallen. Nicht ohne Freigabe (Frage 3).
- Hotword-Kopplung an das System (`AlwaysOnHotwordDetector`) ist für Drittapps nicht nutzbar; unser Weckwort bleibt eigener Service.

### 5.4 Gesprächsschleife (Zustandsautomat im `ListenService`)

Zustände: `SCHLAF` (nur Weckwort) -> `ZUHOEREN` -> `DENKEN` -> `SPRECHEN` -> `FOLGE` -> (Timeout) `SCHLAF`.

1. `SCHLAF`: AudioRecord 16 kHz mono; openWakeWord. Treffer -> kurzer Signalton, Bildschirm an, `MainActivity` in den Vordergrund (nur mit Assistenten-Rolle/Overlay sicher; sonst Notification „Antippen" oder Antwort nur hörbar).
2. `ZUHOEREN`: Aufnahme mit Sprechende-Erkennung (Silero-VAD ONNX, 10-ms-Frames; Ende nach ~1,0 s Stille, Maximum 30 s, Mindestlänge 0,4 s gegen Klicks). Ring-Puffer 0,5 s Vorlauf.
3. `DENKEN`: WAV -> `POST /api/sprache/transkript` -> `{text}`. Leerer Text -> zurück in `FOLGE`/`SCHLAF`. Text -> `WebView.evaluateJavascript("window.heyAgentSend(...)")` — der vorhandene Chat sendet über `/api/chat/stream`, rendert Antwort und Bilder.
4. `SPRECHEN`: Bestehende Vorlese-Logik (`/api/speak`, Satz für Satz) spielt in der WebView (`mediaPlaybackRequiresUserGesture=false`). JS meldet über `HeyAgent.onSpeakDone()` Ende. Wiedergabe im Hintergrund: Audio läuft im Service-Prozess nur, wenn die Activity lebt -> für Hintergrund (Bildschirm aus) spielt **native** `MediaPlayer` die MP3 ab (`/api/speak` direkt vom Service aufgerufen); WebView zeigt nur Text/Bilder. Details in A1d.
5. `FOLGE`: Mikrofon wieder auf (Signalton), **ohne Weckwort**; Timeout 8 s ohne Sprache -> `SCHLAF`. Abbruchwörter („Stopp", „danke") lokal per Textvergleich des Transkripts. Barge-in (Unterbrechen beim Sprechen) erst später (Echo-Problem).

Kein Audio verlässt das Gerät vor Schritt 3; das Backend läuft lokal, nach außen geht nur, was es heute schon tut (OpenRouter).

Backend-Lücken (aus `backend/app/router` abgeleitet):
- **Passt:** Transkript, Chat-Stream, TTS, Health.
- **Fehlt/prüfen:** (a) Chat-Stream-Ereignisformat mit Bildern für Gesprächsmodus prüfen (Bilder-Events; A1d liest `chat.py`); (b) „Sprachmodus"-Flag, damit Antworten kurz/vorlesetauglich sind (Kurzantwort-Prompt, keine Tabellen/Markdown) — Anpassung im System-Prompt statt neuem Endpunkt; (c) TTS-Latenz: `/api/speak` liefert komplette MP3 je Aufruf -> Satzzerlegung im Client; (d) optionaler Sammelendpunkt `POST /api/gespraech` (WAV rein, Text+Audio-URL raus) nur falls Latenz zu hoch; (e) schlanker `agent-ensure.sh`; (f) `/health` ohne Key ist vorhanden — reicht für Health-Check.

### 5.5 WebView-Hülle

- `WebView` lädt `http://127.0.0.1:8080/`. Cleartext nur für `localhost`/`127.0.0.1` über `network_security_config.xml` (Domain-Config, `cleartextTrafficPermitted=true`, kein globales `usesCleartextTraffic`). `http://127.0.0.1` gilt als sicherer Kontext, `getUserMedia` wäre damit möglich, wird aber nicht genutzt (Mikro nativ); `onPermissionRequest` lehnt Audio-Capture ab (kein Doppelbesitz) und prüft `origin`.
- API-Key: wird **nicht** im Code/Repo eingebaut. Erst-Einrichtung: Nutzer trägt ihn einmal ein (oder liest ihn per Intent-Antwort von Termux `~/.env`/eigener Datei) -> gespeichert in `EncryptedSharedPreferences`/Android-Keystore. Injektion: `WebViewClient.shouldInterceptRequest` ergänzt `X-API-Key` für Requests an `127.0.0.1:8080` (kein Key im JS/DOM, keine URL-Parameter); native Aufrufe (`BackendClient`) setzen den Header selbst. Offene Punkte: `shouldInterceptRequest` sieht POST-Body nicht -> Proxy-Variante in A1b prüfen (Fallback: Key über `evaluateJavascript` in eine Variable, die `app.js` bereits kennen dürfte — in `app.js` nachsehen, wie der Key heute gesetzt wird).
- Ohne Weiteres: `WebSettings.setJavaScriptEnabled`, DOM-Storage, `mediaPlaybackRequiresUserGesture=false`, Service Worker (`sw.js`) prüfen (SW auf localhost erlaubt).
- **Alternative native UI:** Kotlin/Compose für Chat+Bilder+Diashow = Doppelpflege von ~8000 Zeilen `app.js`. Verworfen.

## 6. Ablauf Aufruf -> Antwort

1. Weckwort (Service läuft) oder Icon/Power-Taste -> Signalton.
2. Backend-Check: `/health` ok? Nein -> `agent-ensure.sh` per Intent, Ansage „Ich starte kurz…", Poll bis ok (max. 60 s).
3. `ZUHOEREN` -> VAD -> WAV -> `/api/sprache/transkript`.
4. Text -> Chat-Stream (WebView) -> Antwort + Bilder auf dem Bildschirm.
5. Vorlesen satzweise; danach `FOLGE` (8 s) ohne Weckwort; Timeout -> `SCHLAF`.

## 7. Datenschutz

- Weckwort-Erkennung, VAD, Ring-Puffer: nur im Arbeitsspeicher des Handys; nichts wird gespeichert oder gesendet, bis das Weckwort trifft. Kein Google-/Picovoice-Dienst, keine Netzwerkberechtigung im Weckwort-Pfad.
- Nach Weckwort: nur die Aufnahme bis zum Sprechende geht an den lokalen Server, von dort wie heute an OpenRouter (Transkription/Chat/TTS). Kein Mitschnitt auf Platte; WAV nur im Speicher.
- API-Key im Keystore, nie im Repo; Netzwerk-Config erlaubt Klartext ausschließlich für Loopback.
- Verhalten sichtbar: Notification + Systemmikrofonpunkt; Umschalter Aus. Manifest: `allowBackup=false`.

## 8. Akku

Größter Posten ist das Dauerlauschen. Maßnahmen: Vorfilter, Modell 1x pro 80-ms-Frame, Zuhören-Umschalter (Nachtruhe per Zeitplan), Messung (A1c): Ausgangswert Prozent/Stunde bei Bildschirm aus. Zielwert: unter 2 % pro Stunde; darüber -> Modus „nur beim Laden lauschen" oder nur per Icon/Power-Taste. Termux-Wake-Lock hält zusätzlich die CPU wach (heute schon so).

## 9. Bau-Werkzeugkette (Windows-PC)

Befund (geprüft):
- **Android-SDK fehlt:** `%LOCALAPPDATA%\Android\Sdk` existiert nicht (auch `ANDROID_HOME` leer, kein `C:\Android`). Kein Android Studio.
- Vorhanden: JDK **Temurin 17.0.18** (reicht für Android-Gradle-Plugin 8.x), `adb` (WinGet Platform-Tools), `scrcpy`, Node; `~/.gradle` existiert (Daemon/JDKs). Kein `gradle` im PATH.
- Plan (A1a): Google „Command line tools only" nach `%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest` entpacken (Download ~150 MB, Nutzerfreigabe nötig), dann `sdkmanager "platforms;android-35" "build-tools;35.0.0" "platform-tools"` (Lizenz mit `--licenses` bestätigt der Nutzer). Gradle **Wrapper** ins Projektverzeichnis `android/` (Gradle 8.x, per Wrapper geladen, keine globale Installation). Build: `gradlew.bat assembleDebug`, Installation: `adb install -r app\build\outputs\apk\debug\app-debug.apk`. `local.properties` (`sdk.dir=`) bleibt gitignored.
- Signatur: Debug-Keystore von Gradle reicht (Sideload). Für dauerhaftes Update ohne Deinstallation dieselbe Debug-Signatur auf dem PC weiterverwenden (Keystore sichern).
- Prüfbefehl für A1a: `gradlew.bat assembleDebug` Exit 0 und APK-Datei vorhanden.
- Zielhinweis `compileSdk`/`targetSdk` 35 (Android 15); `minSdk` 30 genügt.

## 10. Schritte mit Prüfkriterium

| Schritt | Inhalt | Prüfkriterium |
|---|---|---|
| A1a | SDK per Kommandozeile, Gradle-Wrapper, leeres Projekt `android/` baut | `gradlew.bat assembleDebug` Exit 0; `adb install` startet Hallo-Welt-Activity am Handy |
| **A1b** | WebView-Hülle auf 127.0.0.1:8080, Key im Keystore + Header-Injektion, `TermuxLauncher` + `agent-ensure.sh`, Health-Ablauf mit Rückfall | Termux ist **beendet** (Wischen aus Übersicht), App antippen -> Chat lädt binnen 60 s ohne weiteren Fingertipp; `/api/selbsttest` per WebView 200; Log zeigt Zeit bis „bereit" |
| **A1c** | `ListenService` (FGS microphone), openWakeWord mit eigenem Modell, Vorfilter, Umschalter, Notification | „Hey Agent" aus 2 m Abstand löst >= 9 von 10 mal aus, <= 1 Fehlauslösung/Stunde in ruhigem Raum; 24-h-Akkumessung dokumentiert (Ziel < 2 %/h); Kein Netzwerkverkehr im Schlafzustand (`adb shell dumpsys netstats`/Firewall-Log) |
| **A1d** | Gesprächsschleife: VAD, Transkript, Chat-Stream in WebView, Vorlesen (nativ bei Bildschirm aus), Folge-Modus 8 s, Bilder sichtbar | Ablauf „Hey Agent -> Frage -> Antwort hörbar + Bild sichtbar -> Folgefrage ohne Weckwort -> nach 8 s Stille SCHLAF" 5/5 mal ohne Berührung; Latenz Sprechende -> erster Ton gemessen und im Protokoll (Ziel < 4 s) |
| A1e (optional) | `VoiceInteractionService` + Rolle, Power-Taste; Timer/Wecker (`AlarmClock`-Intent) | Power-Taste lang startet unsere App statt Gemini; Neustart-Test: Service läuft nach Boot ohne App-Öffnen; Timer „in 5 Minuten" klingelt |

Jeder Schritt: eigener Commit „code + docs", App-Prüfbefehl grün + Handytest durch Sebastian (Handy-Installation ist Eingriff am Gerät = manuell bzw. Freigabe).

## 11. Risiken

- Android-14-Regel: Mikrofon-Service nicht aus Hintergrund/Boot startbar -> nach Neustart einmal App öffnen (Abhilfe A1e).
- Hersteller-Akkuverwaltung (Motorola) beendet Service/Termux -> Akku-Optimierung für beide Apps aus, Autostart erlauben; Health-Check + Termux-Neustart per Intent fängt es ab.
- `RUN_COMMAND` aus Hintergrund kann scheitern (siehe 5.1) -> Rückfall-Knopf + Termux:Boot.
- Weckwortqualität mit deutschem Akzent/„Agent": selbst trainiertes Modell nötig, Nachtrainieren möglich; Lizenz der openWakeWord-Feature-Modelle ungeklärt (privat unkritisch, bei Weitergabe erneut prüfen).
- Doppelter Mikrofonbesitz (WebView/Service) -> Regel: nur nativ aufnehmen.
- Falschauslösungen -> Bestätigungston + Zuhören nur bei Wortlaut; Schwelle einstellbar.
- Latenz der Kette (Transkript + Chat + TTS über OpenRouter) kann > 4 s liegen -> Satz-Streaming, ggf. Sammelendpunkt (5.4d).
- API-Key-Injektion bei POST-Bodies in WebView (siehe 5.5) -> Proxy-/JS-Variante in A1b klären.
- Termux-Sicherheitsfläche: `allow-external-apps=true` erlaubt **jeder** App mit der Permission Befehle; die Permission ist normal-gefährlich, der Nutzer muss sie pro App gewähren -> nur unsere App bekommt sie.

## 12. Entscheidungsfragen an den Nutzer (max. 4)

1. **Weckwort-Engine: openWakeWord (Empfehlung) oder Porcupine?** Begründung: openWakeWord ist vollständig offline und für private Nutzung kostenlos, Porcupine braucht eine Online-Lizenzprüfung und ist kommerziell teuer.
2. **Wie soll das Weckwort lauten: „Hey Agent" (Empfehlung) oder ein eigenes, unverwechselbares Wort?** Begründung: Ein klar vom Alltag abgesetztes Wort senkt Fehlauslösungen, „Hey Agent" entspricht deinem Wunsch und wird in A1c gegen Alternativen gemessen.
3. **Soll die App später Standard-Assistent werden (Power-Taste statt Gemini)?** Empfehlung: erst A1b–A1d, Assistenten-Rolle dann in A1e testen, weil sie zwar den Mikrofon-Neustart-Zwang löst, aber Gemini auf dem Handy ersetzt.
4. **Antwort vorlesen auch bei ausgeschaltetem Bildschirm (Freisprech-Betrieb)?** Empfehlung: ja, mit nativem Player in A1d, weil „wie Gemini" genau das erwartet und die WebView bei Bildschirm aus nicht zuverlässig spielt.

## 13. Quellen

- Termux RUN_COMMAND: https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent
- Termux-Diskussionen (Hintergrundstart): https://github.com/termux/termux-app/discussions/3640 · https://github.com/termux/termux-app/discussions/3470
- Termux execution environment (Android 14, `am`): https://github.com/termux/termux-packages/wiki/Termux-execution-environment
- Termux:Boot: https://github.com/termux/termux-boot · Termux:Tasker: https://github.com/termux/termux-tasker
- openWakeWord: https://github.com/dscripka/openWakeWord · Lizenzfrage https://github.com/dscripka/openWakeWord/issues/348 · Kotlin-Port https://github.com/IamSanjid/openwakeword-android-kt
- Porcupine: https://picovoice.ai/pricing/ · https://picovoice.ai/docs/quick-start/porcupine-android/
- Vosk-Grammatik + Silero-VAD: https://zenn.dev/diced/articles/vosk-silero-vad-wakeword-android?locale=en
- Foreground-Service-Typen: https://developer.android.com/develop/background-work/services/fgs/service-types · https://developer.android.com/about/versions/14/changes/fgs-types-required
- Hintergrundstart-Beschränkungen: https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- RoleManager: https://developer.android.com/reference/android/app/role/RoleManager · VoiceInteractionService: https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/service/voice/VoiceInteractionService.java
- WebView-Mikrofon/Cleartext (Sekundärquellen): https://www.javathinking.com/blog/allowing-microphone-access-permission-in-webview-android-studio-java/ · https://issues.chromium.org/issues/424995167

## Entscheidungen (Sebastian, 29.09.2026)

1. Weckwort-Engine: **openWakeWord** (offline, ONNX).
2. Weckwort: **„Hey Agent"**.
3. Standard-Assistent: **nein, vorerst nicht** — Gemini bleibt Standard-Assistent (auch für Android Auto). Folge: Nach Neustart muss die App einmal geöffnet werden, damit der Mikrofon-Dienst läuft (Android-14-Regel). Offener Prüfpunkt A1c: Koexistenz mit „Hey Google" — gleichzeitiges Mikrofon-Lauschen zweier Apps am Motorola messen (Android erlaubt nur eingeschränkt parallele Aufnahme; Assistent hat Vorrang).
4. Vorlesen bei ausgeschaltetem Bildschirm: **ja** (nativer Player im Vordergrunddienst).
