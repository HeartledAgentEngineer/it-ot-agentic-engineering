# typeFREE — Projekt-Direktiven für Claude

## Was ist das?

Systemweite Voice-to-Text-App für Windows:
- Hotkey halten (Standard `Alt + Ä`, auch per `AltGr + Ä` auslösbar; über das Tray-Untermenü „Hotkey wählen" umstellbar) → Mikrofon wird geöffnet und nimmt auf
- Loslassen → transkribiert über OpenRouter (Standard `mai-transcribe-1.5`, bei Ausfall Whisper turbo) → OpenRouter/Gemini glättet → Text wird per Zwischenablage (Strg+V) eingefügt
- Funktioniert systemweit: Terminal, Browser, jedes Textfeld

Architektur, Entscheidungen und Setup: siehe [README.md](README.md).

## Tech-Fakten (gegen `windows/typefree.py` verifiziert)

| Komponente | Technologie |
|------------|-------------|
| Transkription | Drei wählbare Wege (`KETTEN` in `windows/typefree.py`), umschaltbar im Tray oder per `"transkription"` in der `config.json`. **`eu` (Standard) ist die reine OpenRouter-Kette**, seit 14.10.2026 mit nur zwei Gliedern: `microsoft/mai-transcribe-1.5` (2,2–3,4 s an 70 s, 1,1 % Wortfehler, 0,36 $/h), bei Ausfall `openai/whisper-large-v3-turbo` (3,0–3,8 s, 3,4–5,1 %, ~0,012 $/h). mai-2, voxtral-stt und der Voxtral-Audio-Chat sind aus der Kette raus (Client, Preis und Schlüssel bleiben für alte Verbrauchsstände und Messwerkzeuge). Ebenfalls wählbar: `beste` = ElevenLabs Scribe v2, `schnell` = Groq `whisper-large-v3`. Jeder Aufruf mit `language="de"` und Vokabel-Hinweis; fehlt der Schlüssel eines Glieds, rückt das nächste ein. Fällt der gewählte Weg ganz aus, läuft der andere als Rückfall weiter (`RUECKFALL`). Stand im Betrieb 25.09.2026: Auswahl `eu`, Groq- und OpenAI-Schlüssel stillgelegt (Sicherungen `.env.bak-groq`/`.env.bak-openai`) — es geht **nur noch OpenRouter** |
| Text-Glättung | OpenRouter über eine **Modellkette** (`POLISH_MODELLE`): `google/gemini-2.5-flash-lite` (seit 14.10.2026 vorn: 1,3 s Median, günstigstes Modell), Ausweich `google/gemini-2.5-flash` (2,8 s), dann `google/gemini-3.5-flash-lite`. Füllwörter raus, Verhaspler geglättet, **Verhörer aus dem Zusammenhang korrigiert**, **Umgangssprache unangetastet**. `max_tokens=4000` (1000 hätte ein 10-Minuten-Diktat abgeschnitten). Bei Fehler, unplausibel kurzem Ergebnis oder abgekündigtem Modell rückt das nächste Modell nach; erst dann kommt der Rohtext. Drei Ausfälle in Folge → einmaliger Windows-Hinweis |
| Hotkey | Python-`keyboard`-Library (systemweit). Modifier über **Scancode**, nicht über den Namen — deutsches Windows meldet `STRG`/`UMSCHALT`. Zwei Betriebsarten (`hotkey_modus` in der Konfiguration, Tray „Hotkey-Modus"): **`halten`** (Standard, wie bisher) und **`umschalten`** — einmal tippen startet, nochmal tippen beendet. Nur beim Tippen liegt während des Sprechens kein Finger auf der Taste; **der Live-Modus läuft ausschließlich so** (`live_erlaubt`), sonst schaltet er selbst auf „alles auf einmal" zurück |
| Audio | `sounddevice` + `soundfile` + `numpy` (WAV direkt im RAM); Mikrofon wird **nur während der Aufnahme** geöffnet |
| Text einfügen | `windows/zwischenablage.py` (Win32 über `ctypes`, seit 20.10.2026 statt `pyperclip`) + `pyautogui` (Strg+V — unterstützt Umlaute) |
| Status | `pystray`-Tray-Icon, fünf Farben: grau/grün/orange/blau/**rot = Fehler**; kein Overlay, kein tkinter |
| Live-Diktat (im Bau) | Text soll „im Wortfluss" erscheinen (Wunsch 25.09.2026), Umschreiben danach. **Schritte 1–5 fertig:** `stillste_stelle`/`in_happen`/`live_schnitt` schneiden Happen an Sprechpausen (erste Pause nach 1,5 s — bis 06.10.2026 3 s, das ließ den ersten Text erst nach ~5 s kommen; spätestens nach 10 s). Beim Aufnahmestart weckt `verbindung_vorwaermen` das erste EU-Modell (seit 14.10.2026 mai-1.5; 13.10. turbo, vorher mai-2) mit einer Mini-Transkription (0,3 s Stille, `VORWAERM_MODELL`) — der erste Block brauchte kalt 2,2–3,6 s. Gemessen 07.10.2026 in frischen Prozessen: Vorwärmen nur der Verbindung (`/key`) half nicht (erster Block danach 4,5–7,6 s), die Mini-Transkription schon (0,3–0,4 s); sie dauert selbst ~4 s und läuft deshalb im eigenen Thread. `LivePuffer` + `_live_takt` + `_live_worker` sammeln sie in `live_happen`, `_live_schreiber` transkribiert sie, **glättet jeden Block vor dem Tippen** (`_live_glaetten`: `polish_text` mit dem Ende des bisher Getippten als `kontext`, Lite-Modelle zuerst über `POLISH_MODELLE_LIVE`; scheitert die Glättung, kommt der Rohtext) und tippt ihn per `unicode_tippen` am Cursor — **Zeichen für Zeichen** (`_tippen_animiert`, `tipp_pause`: ~30 Zeichen/s, je Block höchstens `LIVE_TIPP_DAUER` = 0,8 s), weil ein Block auf einen Schlag „ruckelt" (Sebastian, 07.10.2026). Beim Loslassen hängt `_live_abschluss` nur den Rest an — **nichts wird gelöscht oder ersetzt** (bis 06.10.2026 glättete er den ganzen Text und ersetzte den Block per Rücktaste; Sebastian: „dass dann alles wieder gelöscht und ersetzt wird, gefällt mir nicht"). Hat Live nichts getippt, übernimmt die normale Verarbeitung (`_live_lief` statt `live_teile` entscheidet, damit ein noch laufender Block nicht doppelt landet). Jeder Happen wird über `_live_buchen` beim liefernden Anbieter gebucht. **Geschaltet wird im Tray** unter „Ausgabe" („Alles auf einmal" / „Live satzweise"), die Wahl steht als `"live": true` in der `config.json`; Standard ist **aus**. Plan: `.hermes/plans/live-diktat.md` |
| Fehlermeldung | Windows-Sprechblase über `tray_icon.notify` + rotes Icon, das rot bleibt bis zur nächsten erfolgreichen Aufnahme |
| Erneuter Versuch | Bei einem Fehlschlag bleibt die Aufnahme im **Arbeitsspeicher** (`aufnahme_merken` → `letzte_aufnahme`) — bewusst nicht auf der Platte. Das Tray-Menü bietet „Letztes Diktat erneut versuchen (N s)" an (`_on_retry`, eigener Thread, ruft `_verarbeite_audio(…, erneut=True)`); ein Erfolg verwirft sie (`retry_verwerfen`). Grund (Sebastian, 25.09.2026): „Ich möchte nicht mehrere Minuten labern und dann ist alles weg" |
| Logdatei | `typefree.log` neben der EXE (`RotatingFileHandler`, 3 × 512 KB) plus `sys.excepthook` und `threading.excepthook`. Jedes Diktat protokolliert Anbieter, Modell und **Zeiten je Stufe** (`zeiten_text`) |
| API-Keys | `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` aus einer `.env` neben der EXE, gelesen von `load_env_file` (eigener Leser, **kein** python-dotenv). **In der installierten Anlage gewinnt die `.env`** gegen eine gleichnamige Umgebungsvariable; beim Start aus dem Quellcode bleibt die Umgebung vorn (Terminal-Tests). Anlass der Regel (06.10.2026): `OPENROUTER_API_KEY` stand in der Windows-Umgebung auf dem Schlüssel „critic-Skill" — jedes Diktat wurde dort gebucht, der eigene Schlüssel „typeFree" blieb bei 0,00 $ |
| App-Name bei OpenRouter | `kopfzeilen_fuer` hängt an jeden OpenRouter-Client (`baue_client`) `HTTP-Referer` (Repo-Adresse, `APP_ADRESSE`), `X-OpenRouter-Title`/`X-Title` = `typeFREE` und `X-OpenRouter-App-Visibility: hidden`. Anlass (06.10.2026): Im Activity-Dashboard stand unter „Top Apps" nur „Unknown". `hidden` hält die App aus den öffentlichen Ranglisten — **wirkt laut OpenRouter-Doku nur bei der allerersten Anfrage**, die die App anlegt; danach nicht mehr änderbar. Groq/OpenAI bekommen keine Kopfzeilen |
| Version | `windows/version.py` (`VERSION`/`COMMIT`, im Quellcode `dev`/`lokal`); `typeFREE.spec` ruft bei jedem Build `ci/version_schreiben.py` auf (`TYPEFREE_VERSION`/`TYPEFREE_COMMIT`, sonst `dev`/git) und erzeugt `windows/_version_build.py` (gitignored, nur in der EXE gelesen — `sys.frozen`, Tag `typefree-vX.Y.Z` → `X.Y.Z`, Eingaben geprüft und per `repr` geschrieben). `startmeldung()` beginnt immer mit „typeFREE gestartet" (danach sucht `update_exe.cmd`), `versions_text()` steht oben im Tray. CI/CD-Plan: `.hermes/plans/2026-10-14_typefree-cicd.md` |
| Ton aus beim Diktat | `windows/ton_aus.py` (seit 20.10.2026): `TonSperre` schaltet beim Aufnahmestart (`start_recording` → `_ton_aus_melden(session)`) das **Standard-Wiedergabegerät** stumm und direkt nach `_close_stream()` wieder an (`stop_and_transcribe`, Mikrofon-tot-Pfad im Wächter; `_on_quit` und `atexit` → `zurueck_alles`). Alle Gerätezugriffe laufen in **einem** Arbeitsfaden mit Warteschlange (`ton-aus`): der Tastatur-Haken wartet nie auf COM, `zurueck` läuft nie vor `aus`, COM wird einmal im Faden initialisiert. **Sitzungsbindung:** `zurueck(sitzung)` wirkt nur für die zuletzt gemeldete Aufnahme (aus(A)→aus(B)→zurück(A) lässt den Ton aus). Schon stummes Gerät bleibt unangetastet; zurückgestellt wird per Gerätekennung genau das stummgeschaltete Gerät. Merker `ton_aus_aktiv.json` (`{"geraete": [...]}`) neben der `config.json` wird **vor** dem Stummschalten geschrieben — nicht schreibbar → kein Stummschalten (Codex-Ergebnisprüfung R1). Beim nächsten Start wird nach hartem Abbruch entstummt (auch eine inzwischen von Hand gesetzte Stummschaltung); Schreiben atomar (Zwischendatei + `os.replace`, R2); nicht erreichbare Geräte — beim Start **oder** ein gescheitertes Zurückstellen nach dem Diktat (R2) — bleiben als offen (`_offen`) im Merker und blockieren keine Aufnahme auf einem anderen Gerät; `zurueck_alles` (Beenden) versucht auch alle offenen, eine neue Aufnahme auf einem anderen Gerät überschreibt sie nicht, und wird das offene Gerät wieder Standard, übernimmt die nächste Aufnahme seine Stummschaltung (nur wenn es noch stumm ist — von Hand wieder laut heißt Rückstand erledigt und normales Stummschalten, R3) und stellt sie mit dem Ende zurück. Das alte Format `{"geraet": id}` wird noch gelesen. Windows-Backend `pycaw`/`comtypes`, faul importiert; fehlt es, nur Log-Warnung. Neu verbinden des Mikrofons berührt den Ton nicht. Schalter `"ton_aus"` (Standard true) + Tray-Häkchen; aus verhindert nur neues Stummschalten. Kurzprobe am echten Gerät 20.10.2026: stumm/zurück je ≤ 0,01 s, Endzustand = Anfang |
| Halluzinationsfilter | `windows/halluzination.py` (seit 20.10.2026, Listen nach Blitztext `HallucinationFilter.swift`, MIT): `ABSPANN` (immer erfunden) und `ZWEIFELHAFT` (nur erfunden bei < `MINDEST_STIMM_SEKUNDEN` = 0,3 s Sprache), Vergleich über `schluessel` (klein, nur Buchstaben/Ziffern, ohne Zahlwörter). `stimm_sekunden` zählt 30-ms-Rahmen mit RMS > 0,01. `abspann_entfernen` schneidet am Ende 1–3 Sätze ab, die zusammen ein Abspann sind (wiederholt). Eingehängt in `_verarbeite_audio` direkt nach `transcribe_audio` (vor dem „Erkannt"-Log): leer oder erfunden → Log ohne Text, `_diktat_buchen` (gebucht wie im Erfolgsfall), Status grau, `retry_verwerfen`, nichts eingefügt. In `_live_stueck_verarbeiten` nach der Leer-Prüfung: erfundener Happen wird gebucht, nicht getippt (deckt Schreiber und `_live_abschluss`-Rest) und zählt `live_verworfen`. Hat Live nichts getippt, aber verworfen, keinen Fehler (`live_fehler`, gesetzt bei Ausnahme in Schreiber oder Rest) und ist der Schreiber innerhalb der Wartefrist fertig geworden (R2; „fertig" = `live_happen` leer und `live_in_arbeit` 0 — der Zähler wird beim Abholen im selben Lock-Abschnitt erhöht und nach jedem Happen gesenkt, ersetzt das frühere `live_beschaeftigt`, das zwischen zwei Happen kurz „frei" zeigte, R3; `_live_worker` legt einen Schnitt nur ab, wenn im selben Lock-Abschnitt die Aufnahme noch läuft — sonst bleibt `live_geschnitten` stehen und der Teil gehört zum Rest, R4), meldet `_live_abschluss` True — kein zweiter, bezahlter Aufruf über die ganze Aufnahme (Codex-Ergebnisprüfung R1); mit Fehler übernimmt wie bisher `_verarbeite_audio`. Beide Zähler setzt `start_recording` zurück. `stop_and_transcribe`: Aufnahme < `MINDEST_AUFNAHME_SEKUNDEN` (0,3 s) → „Aufnahme zu kurz", keine Transkription, keine Buchung |
| Zwischenablage | `windows/zwischenablage.py` (seit 20.10.2026): `sichern_und_schreiben(text)` sichert ALLE Formate und schreibt in **einem** `OpenClipboard`-Durchgang (Besitzer = je Öffnen ein unsichtbares STATIC-Fenster, sonst kann `SetClipboardData` nach dem Leeren scheitern): CF_UNICODETEXT + `ExcludeClipboardContentFromMonitorProcessing` (1-Byte-Block) + `CanIncludeInClipboardHistory`/`CanUploadToCloudClipboard` (DWORD 0) + `typeFREE.Einfuegemarke`. Vollständig nur, wenn jedes GDI-/Nicht-HGLOBAL-Format (CF_BITMAP, CF_ENHMETAFILE, CF_METAFILEPICT, CF_PALETTE, Anzeige-Formate, 0x200–0x3FF) aus einem gesicherten synthetisierbar ist (CF_BITMAP/CF_PALETTE ← CF_DIB/CF_DIBV5); Lesefehler oder > 32 MB → unvollständig → **nichts verändert**, `Ergebnis.geschrieben=False`. Setzfehler nach dem Leeren → im selben Durchgang zurückgeschrieben. Öffnen bis 10 Versuche à 20 ms. `wiederherstellen(snapshot, nummer)` nur bei unveränderter `GetClipboardSequenceNumber` (vorab und nach dem Öffnen geprüft) **und** wenn noch genau dieses Einfügen drinliegt: eigenes Format `typeFREE.Einfuegemarke` mit 16 Zufallsbytes je `sichern_und_schreiben` (`Snapshot.eigene_marke`, Codex R2 — „Letztes Diktat kopieren" schreibt denselben Text ohne Marke und wird so nie überschrieben) plus gleicher Text (`Snapshot.eigener_text`, Füll-Nullen erlaubt). Zwei Diktate kurz hintereinander: `_offen` merkt (Marke, echter Vorinhalt) des letzten noch nicht zurückgestellten Einfügens; findet das nächste dessen Marke noch vor, übernimmt es diese Sicherung (`grund='geerbt'`), sonst ginge der echte Vorinhalt verloren (Codex R3; echte Probe A→B: A zurück nein, B zurück ja, Endzustand byte-gleich); `wiederherstellen` vergisst den Eintrag nur nach erfolgreicher Rückgabe (belegt/Fehler → bleibt gemerkt, Codex R4). Zurückschreiben wird einmal wiederholt (beim Zurückstellen und nach Setzfehler im Durchgang); scheitert es beim Zurückstellen zweimal, legt `_eigenes_zuruecklegen` das Diktat samt Marke wieder hinein, damit das nächste Diktat den Vorinhalt erbt (R5). Restrisiko: scheitert auch das, ist der Vorinhalt weg — Windows zählt die Nummer auch beim Schließen hoch (gemessen 842 → 846 offen → 849 nach Close), abgelesen wird sie danach (Codex R1/1). Kein Besitzerfenster (`CreateWindowExW` NULL) → gar nicht öffnen (R1/3); `EnumClipboardFormats` 0 mit `GetLastError` ≠ 0 → Aufzählfehler → unvollständig (R1/2); wirft Strg+V, startet die Rückgabe trotzdem (R1/4). `privat_kopieren` für den Tray-Eintrag. Einhängen: `_verarbeite_audio` → `_letztes_diktat_merken` (nur RAM) → `_text_einfuegen`: geschrieben → 0,3 s, Strg+V, `_rueckgabe_starten` (Daemon-Faden, `ZWISCHENABLAGE_RUECKGABE_SEKUNDEN` = 1,5); sonst `unicode_tippen` mit Umbrüchen als Leerzeichen. Nähte `zwischenablage_einfuegen/_zurueck/_kopieren`; `conftest.py` sperrt sie und `zwischenablage.standard_api` für alle Tests. Kein `pyperclip` mehr (requirements, spec). Kurzprobe am echten PC 20.10.2026: Endzustand byte-gleich |
| Feste Ersetzungen | `windows/ersetzungen.py` (seit 20.10.2026): `einlesen` (Zeilen `gesprochen => geschrieben`, `#`-Kommentare, kaputte Zeilen gezählt, BOM toleriert), `_vorbereiten` baut EIN Muster (Alternation, längere Normalform zuerst, Wortgrenzen `(?<!\w)`/`(?!\w)`, zwischen Wörtern `[\s\-]+`, IGNORECASE; doppelte Form → untere Zeile gewinnt; `lru_cache`), `anwenden_gezaehlt` ersetzt in einem Durchgang wörtlich (keine Kette, kein `\1`), Lösch-Regel zieht nur den an der Stelle entstandenen Leerraum zusammen. `Ersetzungen(pfad)` liest bei geänderter mtime/Größe neu, fehlende Datei = keine Regeln, Lesefehler = letzte gültige Regeln. In `typefree`: `ersetzungen_pfad()` neben der config.json, `ersetzen(text)` (Fehler → Text unverändert, Log nur Trefferzahl) auf `final_text` in `_verarbeite_audio` (nach der Glättung, nicht im Halluzinations-Verwerfpfad; leer danach → nicht einfügen, buchen, verwerfen) und auf `inhalt` in `_live_stueck_verarbeiten` vor `block_aufteilen` (Rohtext für `geht_weiter` bleibt; Block durch Lösch-Regel leer → gebucht, `live_verworfen` +1, damit der Abschluss nicht neu sendet — Codex R1). Fehler in `ersetzen` loggen nur den Fehlertyp, nie die Meldung (R1). Tray „Ersetzungen bearbeiten …" → `anlegen_falls_fehlt` (Modus `'x'`, überschreibt nie) + Naht `datei_oeffnen` (= `os.startfile`; conftest sperrt sie und lenkt `_ersetzungen` auf eine leere Datei in `tmp_path`) |
| Absätze bei langen Diktaten | `windows/absaetze.py` (seit 20.10.2026 / 29.10.2026): Gliedert lange Diktate automatisch durch Absätze (`\n\n`) an passenden Satzenden (`. ! ? …`). Schwelle: mindestens 45 Wörter oder 4 gehaltvolle Sätze (je mindestens 5 Wörter) seit dem letzten Absatz; vorhandene Absätze bleiben erhalten und setzen den Zähler zurück. Abkürzungen (`z. B.`, `Dr.`, `usw.`) und Zahlen vor Punkten geschützt. Nur Leerraum wird verändert. Schalter `"absaetze"` in `config.json` (Standard false) + Tray-Häkchen „Absätze bei langen Diktaten". Gilt nur für „Alles auf einmal" (Live tippt blockweise). Idee aus Blitztext (macOS, MIT) |
| Konfiguration | `windows/config.json` — gewählter Hotkey (`hotkey_index`) und Ausgabe-Wahl (`live`: true = live satzweise), dazu `ton_aus` (true = Ton aus beim Diktat, Standard), `zwischenablage_zurueck` (true = alter Inhalt kommt nach dem Einfügen zurück, Standard; kein Tray-Eintrag) und `absaetze` (false = Absätze bei langen Diktaten, Standard) |
| Kostenrechnung | `PREISE_JE_MINUTE` je Anbieter (Groq/OpenRouter $0,00185, OpenAI $0,006, Voxtral $0,0059, Scribe $0,0044) + `kosten_fuer` + `verbrauch_buchen(…, anbieter)` + `verbrauch_text` (reine Funktionen), Stand in `verbrauch.json` neben der EXE, Anzeige im Tray-Menü samt Anbieter. Der Betrag wird beim Diktat mit dem Preis des liefernden Anbieters gebucht. Nur die Transkription wird gezählt — Glättung läuft über OpenRouter |
| Tests | `windows/tests/` — **654 Prüfungen** mit pytest in 28 Dateien, überwiegend gegen reine Funktionen; `test_zweitanfrage.py` arbeitet mit echten Fäden, gesteuert über Ereignisse, gegen einen nachgebauten Client (kein Netz). Aufruf: `$env:PYTHONPATH="."; py -3.12 -m pytest windows/tests -q` (die Abhängigkeiten liegen in Python 3.12) |
| Aussteuerung | `aussteuerung(daten)` + `AUSSTEUERUNG_MIN_RMS` (0,02). Jede Aufnahme schreibt „Aussteuerung: Spitze … · RMS …" ins Log; darunter warnt typeFREE. Referenzmessung: fehlerfreies deutsches Audio hatte RMS 0,088–0,095, leise aber fehlerfrei 0,062 |
| Sprachmessung | `windows/sprachmessung.py` — Wortfehlerquote gegen bekannten Text (`wortfehlerquote`, reine Funktion; Test in `tests/test_sprachmessung.py`), optional in Happen mit Kontext. Referenzaudio samt Wortlaut in `windows/referenzaudio/`. Werkzeuge bauen ihre Clients selbst — `transkriptions_clients()` liefert außerhalb der App nur `None`, weil `main()` sie setzt |
| Installer | `installer/setup.cmd` — Batch-Installer mit UAC-Erhöhung, API-Key-Abfrage, Autostart, Desktop-Verknüpfung. Kernlogik in `installer/installer_lib.py` (testbar). Anleitung in `ANLEITUNG-API-KEY.html` (DSGVO in Schritt 6) |

## Versionierte Struktur

```
typeFREE/
├── CLAUDE.md
├── README.md
├── typeFREE.spec              ← PyInstaller-Build aus dem Projekt-Root
├── ci/version_schreiben.py    ← Version + Commit (ruft die Spec bei jedem Build auf)
├── installer/                 ← Installationspaket
│   ├── setup.cmd              ← Installations-Assistent (Batch)
│   ├── installer_lib.py       ← Installations-Logik (Python, testbar)
│   ├── __init__.py
│   ├── ANLEITUNG-API-KEY.html ← DSGVO-konforme Einrichtung (Schritt 6)
│   ├── config.json            ← Hotkey-Voreinstellung
│   └── autostart_admin.cmd    ← Notfall-Autostart
├── build/
│   ├── autostart_admin.cmd    ← separate Admin-Autostart-Hilfe
│   ├── autostart_einrichten.ps1
│   └── build_installer.cmd    ← baut EXE und kopiert in installer/
└── windows/
    ├── typefree.py            ← Hauptscript
    ├── ton_aus.py             ← Ton aus beim Diktat (TonSperre, Windows-Backend)
    ├── halluzination.py       ← Erfundenes erkennen (Abspann, Floskeln, Stimm-Sekunden)
    ├── zwischenablage.py      ← Zwischenablage sichern, privat schreiben, zurückstellen
    ├── ersetzungen.py         ← Feste Ersetzungen (Parser, ein Regex, Lader mit mtime)
    ├── absaetze.py            ← Absätze bei langen Diktaten (Wort-/Satzzählung, Abkürzungsschutz)
    ├── version.py             ← Version/Commit (Build überschreibt per _version_build.py)
    ├── sprachmessung.py       ← Wortfehlerquote gegen bekannten Text messen
    ├── stimmvergleich.py      ← Kandidaten auf derselben Aufnahme vergleichen
    ├── referenzaudio/         ← de_referenz.wav + Wortlaut + Messstand
    ├── requirements.txt
    ├── requirements-dev.txt   ← pytest, nur für die Tests
    ├── config.json
    └── tests/                 ← 654 Prüfungen in 28 Dateien
```

Bewusst nicht versioniert: `build/`, `dist/` (EXE), `windows/_version_build.py` (vom Build erzeugt), `.env` (wird vom Installer erzeugt) sowie der Android-PoC
(Expo/React Native Floating Widget — existiert nur lokal).

## Wichtige technische Erkenntnisse

- **`suppress=True` nur mit Haken, der IMMER `True` liefert** — `keyboard` sperrt jedes Ereignis, für das ein sperrender Haken nicht `True` zurückgibt (auch `None` oder Ausnahme). Ein solcher Haken sperrt sonst die gesamte Tastatur. Einziger Einsatz: `_sperr_haken` (Ä-Sperre, siehe unten), mit `try/except → True` und Test
- **Ä-Sperre (06.10.2026):** Wackelt Alt während der Aufnahme kurz weg, tippte die gehaltene Ä-Taste „ääää" ins Zielfenster (16–150 Stück im Chat). `taste_schlucken` schluckt deshalb das **Drücken** der Haupttaste, solange aufgenommen wird. Das **Loslassen** kommt immer durch — ein geschlucktes Ereignis erreicht auch `on_key_event` nicht, die Aufnahme endete sonst nie. **Im Umschalt-Modus** ist das zweite Tippen genau so ein geschlucktes Drücken — deshalb entscheidet der Sperr-Haken dort selbst (`umschalt_stopp`): ein neues Drücken der Haupttaste beendet, ohne die Zusatztasten zu verlangen (deren Drücken schluckt die Freigabe-Sperre); eine Tastenwiederholung vom ersten Tippen zählt nicht. Ohne das ließ sich die Aufnahme am 06.10.2026 abends nicht beenden
- **Bei gehaltenem Alt kommt Strg+V als Strg+Alt+V an (gemessen in Notepad, 06.10.2026):** nichts wird eingefügt; 3× Rücktaste mit Alt leerte das ganze Dokument (Alt+Rücktaste = Rückgängig). Der Live-Modus tippt aber, während der Hotkey gehalten wird — seine Zwischenstücke kamen deshalb nie an, und der Abschluss löschte per Rücktaste so viele Zeichen, als wären sie da (in einem Dokument: fremder Text). Seitdem `zusatztasten_freigeben` beim Aufnahmestart im Live-Modus: Strg-Tipp (verhindert das Alt-Menü), dann Alt/Strg/Shift per Software los. Danach schluckt `taste_schlucken` weiteres Drücken dieser Tasten bis zum Ende der Aufnahme — außer typeFREEs eigenem Tippen (`eigene_eingabe`, Zeitfenster `EIGENE_EINGABE_NACHLAUF`). **Stand 06.10.2026 abends: wirkt im Betrieb noch nicht** — das Protokoll meldet weiter „Live eingefügt", im Fenster kommt nichts an. Deshalb Messpunkte im Log (`tastenzustand_text`): „Messpunkt Freigabe: vorher … · nachher …" und „Messpunkt vor Live-Einfügen: Alt=… Strg=… Shift=… · Fenster …"
- **Software-Alt ist für `keyboard` unsichtbar:** gedrückte Alt-Tasten aus `SendInput` (Flag `LLKHF_INJECTED|LLKHF_ALTDOWN`) reicht die Bibliothek gar nicht an Haken weiter. Ein Wackeln lässt sich deshalb nicht per Software nachstellen — nur am echten Finger prüfen
- **Keine Tipp-Tests auf Sebastians Desktop ohne Absprache:** Windows-11-Notepad öffnet Dateien als Tab im vorhandenen Fenster, `proc.kill()` schließt sie nicht — ein Test las am 06.10.2026 ein fremdes Fenster aus
- **AltGr = Ctrl+Alt** intern → kann fremde Shortcuts triggern
- **Modifier-Tracking:** `_mods_down`-Set statt `keyboard.is_pressed()` — zuverlässiger
- **Key-Repeat:** KEY_DOWN-Events während laufender Aufnahme ignorieren
- **Loslassen beendet immer:** KEY_UP der Haupttaste stoppt die Aufnahme, auch wenn ein Modifier vorher losgelassen wurde — sonst gehen Diktate verloren
- **Admin-Rechte** nötig für den Keyboard-Hook
- **Logdatei ist Pflicht:** Bei `console=False` in der Spec hinterlässt ein Absturz sonst keine Spur. `StreamHandler` nur anlegen, wenn `sys.stdout` existiert — in der EXE ist es `None`
- **Startbefehle gehören in `main()`:** Seiteneffekte beim Import (Threads, Tray, Config) machen die Datei untestbar
- **Bei gehaltenem Hotkey kommt `Strg+V` im Zielfenster nicht an (direktes Unicode-Tippen dagegen schon, siehe unten).** Gemessen am 06.10.2026 (Notepad, durch Claude am PC): Bei gehaltenem Alt fügt `Strg+V` nichts ein (Windows sieht `Strg+Alt+V`), und `Alt+Rücktaste` ist „Rückgängig" — drei Rücktasten leerten das Dokument. Die Live-Happen wurden deshalb geschnitten, aber nie eingefügt; der Abschluss löschte trotzdem so viele Zeichen, als wären sie da. Auswege (Zusatztasten per Software freigeben, `eigene_eingabe`-Sperre) halfen nicht. ~~Regel: Live nur im Umschalt-Modus~~ — **abgelöst am 06.10.2026 abends** durch einen Test mit echtem Finger auf AltGr+Ä (Notepad): `Strg+V` kam beim Halten nicht an, auch nach der Freigabe nicht; **direkt getippter Text per Unicode (`SendInput` + `KEYEVENTF_UNICODE`) kam an, sogar ohne Freigabe.** Seitdem tippt `_live_text_einfuegen` über `unicode_tippen` (ein `SendInput`-Aufruf je Happen, keine Zwischenablage), und `live_erlaubt` lässt Live in beiden Hotkey-Modi zu. Eine Ersetzung am Ende gibt es seit dem Glätten pro Block nicht mehr. Ungetestet: Rücktaste bei gehaltenem Hotkey — die braucht erst der Wort-für-Wort-Stream
- **Blockgrenzen im Live-Modus — kein Punkt mitten im Satz (06.10.2026):** Die Block-Glättung hielt jeden Block für einen fertigen Satz („…schlecht erkannt." | „worden oder…"). Jetzt hält `block_aufteilen` das Satzzeichen am Blockende zurück (`live_ausstehend`), und **der rohe Anfang des nächsten Blocks entscheidet** (`geht_weiter`): mai schreibt Fortsetzungen klein, neue Sätze groß. `fuge_bestimmen` setzt dann „ " (weiter, Zeichen fällt weg) oder Zeichen + „ " (neuer Satz); `anfang_angleichen` passt die Groß-/Kleinschreibung der Glättung an (Nomen bleiben groß, der erste Block bleibt unangetastet). Am Ende tippt `_live_abschluss` das zurückgehaltene Zeichen. **Gemessen an 6 echten Grenzfällen: diese Regel 6/6, das Lite-Modell per Markierung „~/|" 4/6, mit Zusatzhinweis 2/6** — deshalb entscheidet nicht das Modell. Schwachstelle: eine Fortsetzung, die mit einem Nomen beginnt, gilt als neuer Satz
- **Im Live-Modus heißt eine leere Antwort Stille, nicht Fehler** (`leer_ist_stille`, `_live_transkribieren`): In Sprechpausen lieferte `mai` leer, die Kette rückte auf `voxtral` (Audio-Chat) vor, und der **erfand Sätze** — „Vielen Dank.", „Okay.", „.", „I'm sorry, but I don't have the necessary context …" (06.10.2026). Jetzt endet die Kette bei leerer Antwort mit `('', anbieter)`; nur echte Fehler (Netz, 429, 5xx) lassen das nächste Glied ran. Das normale Diktat („alles auf einmal") behält das alte Verhalten
- **Tests dürfen nie echt tippen:** `tests/conftest.py` sperrt per autouse-Fixture `unicode_tippen` und die Tastatur-Funktionen von `pyautogui`. Anlass: Ein Test tippte am 06.10.2026 zweimal „hallo welt " in Sebastians aktives Fenster, weil die neue Funktion nicht abgefangen war
- **`config.json` in `%ProgramFiles%` muss dem Benutzer gehören.** Der Installer legt sie mit Admin-Rechten an (`Benutzer:(RX)`) — dann kann der Tray-Schalter seine Wahl nicht speichern (nur im Arbeitsspeicher, nach dem Neustart weg) und `patch`/`write_file` scheitern mit „Permission denied". Einmalig beheben: `icacls "%ZIEL%" /grant "%USERNAME%:(OI)(CI)(M)" /T`.
- **Totes Mikrofon erkennt man an exakter digitaler Null**, nicht an leiser Lautstärke — ein echtes Gerät liefert immer Grundrauschen
- **Dateien nie ohne `encoding=` öffnen** — sonst Encoding-Fehler auf nicht-englischen Systemen
- **Strukturierte Logging-Parameter statt f-Strings** — `log.warning('msg %s', var)` statt `log.warning(f'msg {var}')`
- **Quellcode ändern reicht nicht — es muss gebaut UND installiert werden.** Die Quelle wurde am 14.08. auf ein neueres Glättungsmodell umgestellt, die installierte EXE blieb der Build vom 02.08. Das Modell wurde später abgekündigt, jede Glättung endete im 404 — und weil nur die Logdatei davon wusste, lief die App wochenlang ohne Filter. Nach jeder Änderung an `windows/typefree.py`: `py -3.12 -m PyInstaller typeFREE.spec`, dann `windows/update_exe.cmd` (Admin-Rechte, tauscht die EXE und startet neu). **Seit 14.10.2026 trägt jede EXE Version und Commit** (`windows/version.py`; die Spec schreibt bei jedem Build `windows/_version_build.py` frisch, nicht versioniert, und nur die EXE liest es): Startzeile „typeFREE gestartet — Version … (Commit) — …“ und Tray-Zeile unter „typeFREE“. „dev (lokal)“ heißt: Start aus dem Quellcode.
- **Ein abgekündigtes Modell ist ein stiller Ausfall.** Fremde Modelle verschwinden ohne Ankündigung an uns. Deshalb: Anbieter- und Modellketten statt Einzelnamen, und ein Ausfall, der länger als einen Versuch anhält, wird gemeldet (Glättung: Windows-Hinweis nach drei Ausfällen in Folge) — nicht nur geloggt.
- **Fehlgeschlagener Upload lässt den Dateizeiger am Ende.** Der Ausweichversuch schickte sonst eine leere Datei; `transcribe_audio` setzt den Puffer vor jedem Anbieter mit `seek(0)` zurück.
- **Der EXE-Tausch beendet die Anlage hart.** `update_exe.cmd` killt typeFREE, kopiert die neue EXE und startet neu. Der Einzelinstanz-Mutex wird erst mit dem Prozessende frei — am 25.09.2026 kam der einzelne `start`-Versuch nicht durch, die Anlage lag danach still (das Skript versucht es jetzt fünfmal und prüft das Ergebnis). Während des Einspielens **kein Diktat** laufen lassen: das Beenden mitten in der Aufnahme kostet es.
- **`schtasks /run /tn typeFREE` startet die Anlage ohne UAC** — der Weg, wenn sie nach einem Update oder Absturz still liegt. `schtasks /end` beendet sie dagegen nicht zuverlässig.
- **Neue Anbieternamen brauchen drei Einträge.** Ein Glied der `KETTEN` wird in `_kette_durchlaufen` still übersprungen, wenn `transkriptions_clients()` keinen Eintrag für den Namen hat (`clients.get(name)` ist dann `None`) — dazu gehören `SCHLUESSEL_JE_ANBIETER` und `PREISE_JE_MINUTE`, sonst fehlen Schlüssel bzw. Kostenzeile. `sprachmessung.eigene_clients()` muss denselben Satz bauen, sonst misst das Werkzeug den Weg nicht.

## Erledigt (Stand 25.09.2026)

### Durchgang 1 — „Stabilität und Mikrofon" ✅
- `main()`-Umbau: Import sicher, Tray im Hauptthread, Seiteneffekte in `main()`
- Hotkey-Logik: Loslassen beendet IMMER, Modifier-Tracking über Scancodes
- Mikrofon-Wächter: totes Gerät erkennen, Zeitgrenze 10 Min
- `.env`-Leser (eigener, kein python-dotenv)
- Logdatei + Fehler-Abfänger + rotes Icon bei Fehler
- tkinter entfernt, Hotkey-Auswahl im Tray-Menü
- Registry-Autostart entfernt
- Mikrofon nur während der Aufnahme geöffnet
- **Einzelinstanz-Sperre** ✅ Benannter Windows-Mutex `Local\typeFREE_einzelinstanz`

### Durchgang 2 — „Autostart, Installer und DSGVO" ✅
- **Kosten anzeigen** ✅ Whisper-Kosten im Tray-Menü
- **Prompt verbessert** ✅ Füllwörter-Filter (01.08.2026): alle Schreibweisen, neue Füllwörter, Fachbegriff-Ausnahme
- **Tests gefixt** ✅ 73/73 Prüfungen grün (Referenz `client` → `openrouter_client`)
- **Windows-Aufgabenplanung** ✅ Autostart bei Anmeldung + Aufwachen (`build/autostart_admin.cmd`)
- **`einrichten_exe.cmd`** ✅ automatische UAC-Erhöhung eingebaut
- **Installer-Paket** ✅ `installer/setup.cmd` mit API-Key-Abfrage, Desktop-Verknüpfung, Startmenü, Deinstallations-Skript
- **DSGVO-Anleitung** ✅ Schritt 6 in `ANLEITUNG-API-KEY.html`: Zero Data Retention + Data Training deaktivieren
- **Installer-Tests** ✅ 11 neue Prüfungen in `test_installer.py` (84 insgesamt)
- **`installer/installer_lib.py`** ✅ Installations-Logik als testbare Python-Funktionen

### Durchgang 3 — „Betriebsreparatur und Tempo" ✅ (25.09.2026)

Anlass: Sebastian meldet, die Transkription brauche lange und der Filter „funktioniere komplett schlecht". Zwei Befunde aus `typefree.log` und Messungen:

- **Der Filter lief gar nicht** — 226 von 226 Diktaten im aktuellen Log mit „Glättung fehlgeschlagen — Rohtext wird verwendet", Fehler `404 No endpoints found for google/gemini-2.0-flash-001`. Ursache war nicht der Code, sondern ein veralteter Build: Quelle am 14.08. auf `gemini-2.5-flash` umgestellt, installierte EXE vom 02.08., OpenRouter hatte das alte Modell abgekündigt.
- **Die Transkription lief über einen toten Umweg** — der OpenAI-Schlüssel gehört zu einem Konto ohne aktives Guthaben (`billing_not_active`), jeder Aufruf scheiterte, jedes Diktat ging über OpenRouter. Median im Log: 4 s, p90 10 s, Maximum 27 s.

Umgesetzt:
- **Anbieterkette** `TRANSCRIPTION_KETTE` (Groq → OpenRouter → OpenAI) mit `transcribe_audio`, Puffer-Reset je Versuch, Zeitmessung je Stufe
- **Modellkette** `POLISH_MODELLE` für die Glättung mit automatischem Nachrücken
- **Ausfallmeldung** statt stillem Log-Eintrag: drei Glättungs-Ausfälle in Folge → einmaliger Windows-Hinweis (`ausfall_zaehlen`, `ausfall_melden`)
- **Preise je Anbieter** (`PREISE_JE_MINUTE`, `kosten_fuer`), Tray zeigt Minuten, Betrag und Anbieter
- **`groq`-Paket entfernt** — Groq läuft über das OpenAI-SDK (OpenAI-kompatibler Endpunkt), eine Abhängigkeit weniger
- **25 neue Prüfungen** (`test_transkription.py`), 109 insgesamt grün
- **Gemessen** (24,5 s deutsches Audio, 16 kHz mono): Groq median 0,72 s · OpenRouter median 1,83 s (Ausreißer 6,79 s) · OpenAI antwortet nicht

## Transkriptionswege — Messstand 25.09.2026

Alle Zahlen an 24,5 s deutschem Audio (16 kHz mono), mehrfach gemessen.

| Weg | Zeit | Vollständig | Kosten/h | Daten gehen an |
|-----|------|-------------|----------|----------------|
| **Groq direkt** `whisper-large-v3` | 0,72–1,9 s | 16 von 16 ✅ | 0,111 $ | Groq (US) |
| **OpenRouter** `whisper-large-v3` (Transkriptions-Endpunkt) | 1,0–3,7 s | **5 von 16** ❌ | 0,09–0,11 $ | DeepInfra/Together/Groq (US) |
| **OpenRouter** `whisper-large-v3-turbo` | 3,7 s | ja, sichtbar schlechtere Qualität | 0,012 $ | DeepInfra (US) |
| **OpenRouter** `voxtral-mini-transcribe` | – | Fehler: Konto-ZDR schließt Endpunkt aus | 0,18 $ | Mistral (EU) |
| **OpenRouter** `nova-3` | 1,3 s | leeres Ergebnis | 0,258 $ | Deepgram (US) |
| **OpenRouter** `voxtral-small-24b-2507` (Audio-Chat-Weg) | 1,8–2,8 s | 3 von 3 ✅ | 0,36 $ | **Mistral (EU)** |

**Befund: der Transkriptions-Endpunkt von OpenRouter ist für Diktate unbrauchbar.**
Er liefert in rund der Hälfte der Läufe nur das letzte Drittel des Audios — reproduziert
über 16 Läufe, mit und ohne `provider.zdr`, mit wav/flac/mp3, mit festgenageltem
Anbieter und im Wechsel zwischen DeepInfra, Together und Groq. Der **Chat-Weg mit
Audio** (`input_audio`) ist davon nicht betroffen.

**Datenschutz-Einstellungen von OpenRouter** (Stand 25.09.2026, dieses Konto):
- Das Konto erzwingt ZDR bereits — nicht konforme Endpunkte fallen mit 404 raus (`ZDR violation (account settings)`).
- Zusätzlich pro Anfrage: `provider.zdr = true` (nur Endpunkte ohne Speicherung).
- `allowed_data_regions: ['global']` — EU-In-Region-Routing ist Enterprise-only.
- Guthaben: 178 $ aufgeladen, 161,08 $ verbraucht → rund 17 $ übrig.

**Werkzeug:** `windows/stimmvergleich.py` schickt eine Aufnahme durch alle Kandidaten
und stellt die Transkripte nebeneinander (`-s 30` für 30 s Mikrofon, `-d datei.wav`
für eine vorhandene Datei). Die Aufnahme liegt nur temporär und wird danach gelöscht.

### Die drei Transkriptionswege (config.json → „transkription")

| Wahl | Weg | Anbieter | Tempo | Kosten/h | Schlüssel |
|------|-----|----------|-------|----------|-----------|
| `eu` (Standard) | **Reine OpenRouter-Kette**: `mai-transcribe-1.5` → `whisper-large-v3-turbo` | Modelle von Microsoft und OpenAI, beide über OpenRouter; ZDR des Kontos greift für beide | mai-1.5 2,2–3,4 s bei 70 s Audio (14.10.) | ~0,36 $ (mai-1.5) | `OPENROUTER_API_KEY` |
| `beste` | ElevenLabs Scribe v2 + Keyterms | ElevenLabs (US) | noch nicht gemessen | 0,264 $ | `ELEVENLABS_API_KEY` |
| `schnell` | Groq whisper-large-v3, STT-Endpunkt | Groq (US) | 0,7–1,9 s | 0,111 $ | `GROQ_API_KEY` |

**Kostenzählung seit 25.09.2026 anbietergenau:** Der Betrag wird beim Diktat mit dem
Preis des Anbieters gebucht, der geliefert hat (`verbrauch_buchen(..., anbieter)`), und
in `verbrauch.json` als `monat_betrag`/`gesamt_betrag` festgehalten. Vorher rechnete die
Anzeige die Monatssumme mit dem Preis des gerade gewählten Wegs um — aus 0,33 $ wurden
so 1,04 $, ohne Ausgabe. Laufen im Monat mehrere Wege, nennt die Anzeige den ersten mit
„+" („(Groq +)"). Alte Stände ohne Beträge werden einmalig mit dem Groq-Preis geschätzt
(Groq war bis dahin der Regelfall).

Fehlt der Schlüssel für den gewählten Weg, nimmt typeFREE automatisch den anderen und
schreibt es ins Log. Umgestellt wird im Tray-Menü unter **„Transkription wählen"** (wirkt
sofort, ohne Neustart; fehlt für einen Weg der Schlüssel, steht „(kein Schlüssel)" dabei)
oder in der `config.json` neben der EXE (bzw. in `windows/config.json` beim Quellcode-Start):
`"transkription": "eu" | "beste" | "schnell"`.

**Warum Scribe als „beste":** Laut Anbieter 3,1 % Wortfehlerquote für Deutsch gegen
4,5 % bei Whisper large v3; `keyterms` ist dieselbe Idee wie der Whisper-Vokabelhinweis,
nur gezielter (bis zu 100 Begriffe). Preis 0,22 $/Stunde, Keyterms kosten 20 % Aufschlag.
Laut ElevenLabs-Agreements darf kein Drittanbieter mit Kundendaten trainieren; echtes
Zero-Retention ist allerdings Enterprise-Kunden vorbehalten.

### Modellwahl nach Benchmark und Messung — 25.09.2026 abends

Sebastians Vorgabe: „nur über OpenRouter und das beste Modell, das meinem
ZDR-Datenschutz entspricht." Entschieden wurde nicht nach Gefühl, sondern nach
veröffentlichten Benchmarks **und** eigener Messung am Referenzaudio.

**Veröffentlichte Werte** (Artificial Analysis „Speech-to-Text", Wortfehlerquote;
Fleurs multilingual über 43 Sprachen — jeweils der veröffentlichte Stand):

| Modell | AA-WER | Fleurs (43 Spr.) | über OpenRouter? |
|---|---|---|---|
| ElevenLabs Scribe v2 | 2,2 % | 5,53 % | nein |
| **Microsoft MAI-Transcribe-1.5** | 2,4 % | **4,86 %** (Bestwert) | **ja** |
| Google Gemini 3.5 Transcribe | 2,6 % | – | nein |
| AssemblyAI Universal-3.5 Pro | 3,0 % | – | nein |
| OpenAI Whisper large-v3 (gehostet) | 4,1 % | – | ja |
| Mistral Voxtral Small (offenes Modell) | – | 5,65 % | ja |
| Google Gemini 2.5 Flash / Lite | 5,1 / 5,2 % | 5,63 % (Lite) | ja |

Quellen: Artificial Analysis (Speech-to-Text), Open-ASR-Leaderboard, Modellkarten
von Microsoft und Mistral. Zu Gemini passt der Befund mehrerer Tests, dass es
keinen reinen Transkriptionsmodus hat (Antworten und Kommentare statt Text) —
hier deckt sich das mit dem Auftragstext-Vorfall.

**Eigene Messung am selben Audio** (69,7 s Deutsch, Wortlaut bekannt):

| Weg über OpenRouter | Wortfehler | Ende | Zeit |
|---|---|---|---|
| `microsoft/mai-transcribe-1.5` | **1,1 %** | vollständig | 4,8 s |
| `openai/whisper-large-v3` | 3,4 % | vollständig | 3,4 s |

**Eigene Messung an 140 s natürlichem Deutsch** (fortlaufender Text, 325 Wörter,
per TTS gesprochen — nicht wiederholt, sonst lassen Modelle Wiederholungen weg
und die Zahlen werden ungültig):

| Weg über OpenRouter | Wortfehler | Wörter | Zeit | Deutsch? |
|---|---|---|---|---|
| **`microsoft/mai-transcribe-2`** | **0,3 %** | 325 / 325 | **3,8 s** | ja |
| `microsoft/mai-transcribe-1.5` | 0,3 % | 325 / 325 | 11,8 s | ja |
| `mistralai/voxtral-small-24b-2507-stt` | 0,3 % | 325 / 325 | 18,9 s | ja (nur mit `language="de"` — ohne übersetzt er ins Englische) |
| `openai/whisper-large-v3` | 1,2 % | 324 / 325 | 4,5 s | ja |
| `google/gemini-3.5-flash` (Chat) | 0,3 % | 325 / 325 | 12,6 s | ja |
| `mistralai/voxtral-small-24b-2507` (Chat) | – | – | 27,5 s | **429** |

Daraus die Reihenfolge der `eu`-Kette (25.09.): `mai-transcribe-2` (schnell, genau, billig)
→ `mai-transcribe-1.5` → `voxtral-…-stt` → `voxtral-…` (Chat, letzter Weg).
`google/gemini-3.5-transcribe` fällt aus: „0 endpoints out of 1 requested" —
für dieses Modell bietet OpenRouter **keinen ZDR-Endpunkt** an, das Konto lehnt es
damit ab (derselbe Mechanismus, der die ZDR-Vorgabe durchsetzt).

**Entscheidung (25.09.2026 früh, später abgelöst durch `mai-transcribe-2` an erster
Stelle, siehe Reihenfolge oben):** `microsoft/mai-transcribe-1.5` stand an erster Stelle der
`eu`-Kette — über OpenRouter erreichbar, ZDR-konform (das Konto lehnt nicht
konforme Endpunkte mit 404 ab; dieser liefert), und nach Benchmark wie eigener
Messung das beste erreichbare Modell für Deutsch. Scribe v2 wäre laut Benchmark
gleichauf, erfüllt die ZDR-Vorgabe aber nicht: laut ElevenLabs-Agreements ist
echtes Zero-Retention Enterprise-Kunden vorbehalten, und über OpenRouter ist es
gar nicht erreichbar. Es bleibt deshalb nur als ausdrücklich wählbarer Weg
bestehen, nicht als Standard.

### mai-1.5 vorn, nur zwei Glieder — Entscheidung 14.10.2026

**Seit 14.10.2026 nur noch zwei Glieder: `microsoft/mai-transcribe-1.5` vorn, `openai/whisper-large-v3-turbo` als Ausweich.** turbo erfand im Betrieb in Sprechpausen „Vielen Dank" (3 von 7 Diktaten am 14.10.) und brauchte 2,1–12,4 s; Sebastian: „Qualität ist sehr schlecht geworden". Messung am 14.10. (70 s Referenzaudio, je 3 Läufe): mai-1.5 2,2–3,4 s bei 1,1 % Wortfehler (leise mit zwei Pausen 1,7 %), turbo 3,0–3,8 s bei 3,4–5,1 %, mai-2 1,4–20,1 s bei 2,8 %. Weitere Glieder kosten nur im Störfall Zeit, dann aber je Glied bis zu 90 s — deshalb entfallen mai-2 (unstet), voxtral-stt (19 s) und der Audio-Chat-Weg (erfindet Sätze, drosselt). Die Glättung lässt Inhalte bewusst stehen; was das Transkriptionsmodell erfindet, kommt also durch.

Umsetzung: `KETTEN['eu']` = `mai-1.5`, `turbo`; Tests in `test_transkription.py` (`test_eu_weg_bleibt_bei_openrouter`, `test_eu_weg_hat_genau_einen_ausweich_und_keinen_chat_weg`). Das Vorwärmen (nur Live) trifft jetzt mai-1.5.

### Turbo vorn — Entscheidung 13.10.2026 (abgelöst am 14.10.)

Sebastian: Geschwindigkeit hat Vorrang („das schnellste Modell … large-v3 turbo").
Anlass: `mai-transcribe-2` antwortete bis 07.10. im Median in 1,3–1,8 s, am 12.10. in
11,3 s (max 57,7 s). Vergleich 12.10. (70 s Referenzaudio, OpenRouter, Konto erzwingt ZDR):

| Modell | Median | Wortfehler | Preis |
|---|---|---|---|
| `openai/whisper-large-v3-turbo` | 1,8 s (max 3,1), 5/5 vollständig | 5,1 % | ~0,012 $/h |
| `microsoft/mai-transcribe-1.5` | 2,4 s | 1,1 % | 0,36 $/h |
| `microsoft/mai-transcribe-2` | 11,3 s (max 57,7) | 2,8 % | 0,10 $/h |
| `openai/whisper-large-v3` | 6,6 s, 10/10 vollständig | 5,1 % | ~0,10 $/h |

Nicht erreichbar: `gpt-4o(-mini)-transcribe` (404), Qwen-Omni und gpt-audio-mini (kein
ZDR). Das Abschneiden von Whisper über OpenRouter (September: 11 von 16) trat nicht mehr auf.

Umsetzung: neues erstes Glied `turbo` in `KETTEN['eu']`, Client in
`transkriptions_clients()` und `sprachmessung.eigene_clients()` (ein Test prüft, dass
jedes EU-Glied dort, in `SCHLUESSEL_JE_ANBIETER` und `PREISE_JE_MINUTE` steht),
`PREISE_JE_MINUTE['turbo'] = 0.0002`, Tray-Text; `VORWAERM_MODELL` ist das erste EU-Glied
(`KETTEN['eu'][0][1]`), wandert also mit. Die
Zweitanfrage geht an dasselbe Modell. Echter Lauf über `transcribe_audio` am 13.10.:
2,2–3,0 s warm, der erste Aufruf eines Prozesses 4,2–4,9 s (auch mit vorgebautem
SSL-Kontext — Verbindungsaufbau und Kaltstart bei OpenRouter), immer 5,1 % Wortfehler.

**Offen:** Whisper erfindet in Stille gelegentlich Sätze („Vielen Dank.") — betrifft vor
allem Live-Happen (Live ist Standard aus); ein Filter fehlt noch. Die Live-Wortgrenzen-
Logik wurde an mai beobachtet (Fortsetzungen klein) und ist mit turbo ungemessen.
Wortfehler nach der Glättung (turbo vs. mai) noch nicht gemessen. Den Erstaufruf (4,2–4,9 s)
nimmt nur der Live-Modus per Vorwärmen vorweg; Vorwärmen auch für „Alles auf einmal“ ist
noch offen. **Rückweg:** Glied `turbo` aus `KETTEN['eu']` entfernen (Vorwärmmodell folgt
von selbst) und die Reihenfolgetests in `test_transkription.py` zurückstellen
(`test_regelweg_ist_der_eu_weg`, `test_eu_weg_bleibt_bei_openrouter`,
`test_verfuegbare_anbieter_haelt_die_kettenreihenfolge`).

### Grenzen des EU-Wegs — Messung 25.09.2026 (Historie: betraf den Voxtral-Chat-Weg, seit 14.10.2026 nicht mehr in der Kette)

Der EU-Weg läuft im **geteilten Anbieter-Pool** von OpenRouter. Mistral drosselt ihn
je nach Audiolänge:

| Audio | Ergebnis über den EU-Weg |
|-------|--------------------------|
| 3 s (94 KB) | 0,69–2,86 s, vollständig (ein 429 wurde per Wiederholung abgefangen) |
| 24,5 s (764 KB) | 1,41–1,45 s, vollständig |
| 60 s (2,3 MB) | **429 bei jedem Versuch** (3 Wiederholungen reichen nicht) |

Deshalb drei Sicherungen im Code:

1. **Wiederholung** (`CHAT_WIEDERHOLUNGEN = 3`, 1 s / 2 s Wartezeit) — **nur der
   Audio-Chat-Weg** (`voxtral-chat`); fängt kurze Drosselungen ab. Nur bei 429 und
   5xx; ein Aufruffehler wird nicht wiederholt. Die Transkriptions-Endpunkt-Wege
   sichert stattdessen die Zweitanfrage (Punkt 3).
2. **Rückfall** (`RUECKFALL = True`) — fällt der gewählte Weg komplett aus, läuft der
   nächste verfügbare Weg, damit kein Diktat verloren geht. Der Anbieter steht danach
   im Log und in der Kostenzeile („(groq)"). Auf `False` setzen, wenn strikt nur der
   gewählte Weg laufen darf. Bei eigener `kette` (Stimmvergleich, Tests) gibt es
   **keinen** Rückfall. Unabhängig davon wechselt `aktive_kette()` schon **vor** dem Diktat den Weg, wenn für den gewählten gar kein Schlüssel da ist: `eu` → `schnell`, `schnell` → `eu`, `beste` → `eu` (Log: „Kein Schlüssel für Weg …“) — das schaltet `RUECKFALL = False` nicht ab.
3. **Zweitanfrage** (12.10.2026, `_stt_anfrage`) — **nur die Transkriptions-
   Endpunkt-Wege** (`weg == 'stt'`: turbo, mai, mai-1.5, voxtral-stt, groq); Audio-Chat
   und ElevenLabs Scribe laufen ohne sie. Dieselbe Anfrage geht parallel ein
   zweites Mal los, wenn
   - nach `zweitanfrage_nach()` (4 s + 0,03 s je Audiosekunde, bei 70 s also
     6,1 s) keine Antwort da ist, oder
   - die erste mit 429/5xx scheitert — das ersetzt die stillen SDK-Wiederholungen
     (`max_retries=0`). Andere Fehler (z. B. 400) werden nicht wiederholt.

   Höchstens zwei Anfragen. Es gewinnt die erste **brauchbare** Antwort; eine
   leere zählt nur, wenn keine andere mehr läuft oder die Frist abläuft — dann
   kommt sie als Stille zurück (Live). **Harte Gesamtfrist `STT_HOECHSTDAUER`
   (90 s):** Jede Anfrage bekommt eine eigene Verbindung (`httpx.Client`), deren
   Zeitlimit die Restzeit bis zum Fristende ist. Beim Verlassen — Gewinner, Fehler
   oder Fristende — werden alle Verbindungen geschlossen; eine hängende Anfrage
   bricht damit nach rund 1 s ab (gemessen gegen einen lokalen Server). Nur die
   Restzeit allein reichte nicht: das httpx-Zeitlimit gilt je Phase (Verbinden,
   Lesen …), nicht insgesamt. Antworten, die erst nach dem Fristende eintrafen,
   zählen nicht. Danach `TimeoutError` mit den vorher gemeldeten Fehlern (z. B.
   429), die Kette rückt weiter. Vorher wartete das SDK bis zu 10 min.

   **Gemeinsamer SSL-Kontext** (`gemeinsamer_ssl_kontext()`, 13.10.2026): Ein
   neuer `httpx.Client` baute je Anfrage die Zertifikatsprüfung neu auf
   (0,8–1,4 s gemessen) und fraß so die Frist. Jetzt wird der Kontext einmal, faul
   und fadensicher, erzeugt und an jede Verbindung gegeben; `main()` baut ihn beim
   Start im Hintergrund vor. Die Verbindung baut der **Anfragefaden selbst** auf und
   misst **danach** die Restzeit — ist die Frist um oder die Entscheidung schon
   gefallen, schließt er sie und fragt nicht an. Die wartende Schleife kehrt dadurch
   auch bei langsamem Aufbau pünktlich zum Fristende zurück. Die Eingangszeit einer
   Antwort wird direkt bei der Rückkehr von `create()` gestempelt.

   **Kosten:** Jede Zweitanfrage wird gebucht, sobald sie zum Versand freigegeben
   ist — nicht schon beim Anstoßen (ist ihr Aufbau erst nach Fristende oder nach dem
   Sieg der ersten fertig, wird nichts gebucht). Fällt das Schließen genau zwischen
   Freigabe und Versand, ist sie gebucht, ohne gesendet zu sein
   (`verbrauch_buchen(..., diktat=False)`: Betrag plus `monat_zweitanfragen`,
   ohne Diktat und Sekunden doppelt zu zählen) — je Anfrage dieselbe Audiolänge
   zum Preis des Anbieters, bei mai 0,17 ct/min. Gebucht wird **nur aus der App**
   (`zweitanfrage_buchen=_zweitanfrage_buchen` beim Diktat und im Live-Modus);
   Werkzeuge wie `sprachmessung.py` übergeben nichts und lassen `verbrauch.json`
   unberührt. Die Buchung nutzt eine eigene Sperre (`_verbrauch_lock`), nicht
   `lock` — den hält auch der Audio-Callback — und läuft in einem eigenen Faden
   (`stt-buchung`), damit Sperre und Dateispeichern weder die Antwort noch das
   Schließen am Fristende aufhalten. Ob der Anbieter eine abgebrochene
   Anfrage berechnet, ist unbekannt; die Anzeige zeigt eher zu viel.

   Anlass: mai antwortete bis 07.10. im Median in 1,3–1,8 s, am 12.10. in 12,5 s,
   einzelne Anfragen hingen 56/90/181 s, unabhängig von der Diktatlänge. Echter
   Lauf mit 70 s Referenzaudio: viermal Zweitanfrage nötig, einmal war sie
   schneller; bei Überlastung des ganzen Dienstes hilft sie nur begrenzt (22 s /
   29 s trotz zweier Anfragen). Nachgeschärft nach drei Runden Codex-Ergebnisprüfung
   (12./13.10.2026).

**Entschärft am 25.09.2026 abends (Historie — seit 14.10.2026 ist der Chat-Weg ganz raus, die Kette ist `mai-1.5` → `turbo`):** In der `eu`-Kette stehen die beiden
Transkriptions-Endpunkt-Wege jetzt **vorn** (damals `mai-transcribe-1.5`, dann
`voxtral-small-24b-2507-stt`; heute steht `mai-transcribe-2` davor). Sie kennen die Drosselung des Chat-Wegs nicht:
69,7 s liefen in 4,8 s durch, 139 s im Test ebenfalls. Der gedrosselte Chat-Weg
ist nur noch das dritte Glied — er ist der einzige, der die Fachbegriffe
mitgeben kann, soll aber nicht mehr den Ausschlag geben. Lange Diktate enden
dadurch nicht mehr im roten Symbol (Sebastians Beobachtung: „bei längeren
Aufgaben vor allem rot").

**Belastbarer EU-Betrieb über Voxtral** bräuchte einen eigenen Mistral-Schlüssel bei
OpenRouter (BYOK, „Integrations" in den OpenRouter-Einstellungen) — dann gälten eigene
Limits statt des geteilten Pools. Seit 14.10.2026 ist Voxtral nicht mehr in der Kette;
der Hinweis gilt nur, falls es zurückkommt. Eine Fehlermeldung mit diesem Ausweg gibt
es im Code nicht.

**Zweiter Befund:** Voxtral gab im Betrieb einmal den **Auftragstext selbst** zurück
(„Transkribiere diese deutsche Sprachaufnahme …") statt zu transkribieren; der Text
landete danach im Dokument. Seitdem verwerfen `_ist_auftragstext()` und die Kette
solche Antworten.

## Offene Arbeit

### Transkriptionsweg — Stand 25.09.2026

Entschieden sind **drei wählbare Wege** (Tabelle oben), umschaltbar im Tray und in
der `config.json`. Offen sind zwei Punkte:

- ~~Der EU-Weg ist im Betrieb nicht belastbar (geteilter Mistral-Pool, 429 ab ~60 s)~~ —
  erledigt: Die Kette läuft seit 25.09. abends über Transkriptions-Endpunkte und
  besteht seit 14.10.2026 nur aus `mai-1.5` → `turbo`, ohne Mistral. Betrieb: Auswahl `eu`.
- **`beste` ist noch nicht einsatzbereit**, weil kein `ELEVENLABS_API_KEY` gesetzt
  ist — das Tray-Menü zeigt „(kein Schlüssel)" und die Kette überspringt den Weg.

Entschieden wird an einer **echten** Aufnahme — nicht durch Vermutung:
`windows/stimmvergleich.py` (alle Kandidaten auf demselben Audio) und
`windows/sprachmessung.py` (Wortfehlerquote gegen bekannten Text).

### Schnelles Sprechen ist nicht die Fehlerquelle (Messung 25.09.2026)

Sebastian testete bewusst schnelles Diktieren. Messung mit `sprachmessung.py`
gegen bekannten deutschen Text (Referenzaudio im Repo):

| Aufnahme | Wortfehler |
|---|---|
| 69,7 s am Stück | 4,0 % |
| dieselbe Aufnahme in 25-s-Happen | 3,4 % |
| derselbe Satz wie ein echtes Diktat, normale Sprechweise | 0,0 % |
| +30 % schneller | 1,2 % |
| +30 % schneller und −35 % leiser | 0,0 % |

Auch seine eigenen Diktate bestätigen das: das schnellste im Log (3,07 Wörter/s)
war fehlerfrei, die Stellen mit sinnlosen Wörtern („Brother 1", „Context-Hensers")
lagen bei 1,70–2,48 Wörtern/s. **Länge und Sprechtempo sind damit widerlegt**; ein
Umbau auf Happen wurde gemessen und **verworfen** (0,6 Prozentpunkte, im Rauschen).
Die Ursache liegt in der Aufnahme an der jeweiligen Stelle selbst — deshalb steht
der Pegel jetzt im Log (`Aussteuerung: Spitze … · RMS …`).

### Bugreport an OpenRouter (offen)

Über `POST /api/v1/audio/transcriptions` kommen in rund der Hälfte der Läufe nur
die letzten Sekunden des Audios zurück (16 Läufe, mehrere Formate, mehrere
Anbieter, mit und ohne ZDR). Der Chat-Weg mit `input_audio` ist nicht betroffen.

### ⚠️ Critic-Gegenprobe für Slice A (Prompt-Änderungen)
Nach Phase 7 einen `/critic`-Lauf auf die geänderten Stellen:
```bash
cd "C:\Users\sebas\Desktop\workspace agentic engineering"
node .claude/skills/critic/pruefe.mjs "02_Softwareentwicklung_IT\typeFREE\windows\typefree.py"
```

### Durchgang 2 Fortsetzung — „Feinschliff"

- **Unsichtbarer Start** `einrichten.cmd` — typeFREE mit `pythonw` starten (kein Terminal-Fenster)
- **Fehlstart-Erkennung** — nach 3 Fehlstarts in Folge aufgeben und einmalig melden
- **Guthaben-Prüfung** — leeres Guthaben an fehlgeschlagener API-Anfrage erkennen → rotes Icon, weiterlaufen
- **README-Abschnitt** „Warum nicht Win+H"
- **`setup.cmd` auf `installer_lib.py` umstellen** — damit der Installer nicht doppelte Logik im Batch hält
- **Inno-Setup-Installer** — falls gewünscht, kann der Batch-Installer später durch ein `setup.iss` ersetzt werden

### Textqualität — offene Punkte

Die Glättung läuft über die Modellkette (seit 14.10.2026 `google/gemini-2.5-flash-lite` vorn, gemessen 1,3 s Median; Ausweich `google/gemini-2.5-flash` und `google/gemini-3.5-flash-lite`). Die Beobachtungen unten stammen noch aus der Zeit mit `gemini-2.5-flash` vorn:
- Füllwörter werden zuverlässig entfernt (auch als „A H M" verschriftete) — im Testdurchlauf blieben keine stehen
- „glaube → denke" und „gucken → wissen" müssen nochmal gemessen werden
- Englische Fachbegriffe in deutschen Sätzen werden nicht geschont
- Verhörer werden unterschiedlich gut repariert: „Zweittest" → „zweite Test" gelang, „Swayt-Test" → „Suite-Test" daneben

### Installer — offener Punkt

Der Installer fragt nur OpenRouter und optional OpenAI ab. Der Standardweg `eu` braucht nur OpenRouter; den OpenAI-Schlüssel nutzt keine Kette. Groq (Weg `schnell`) und ElevenLabs (Weg `beste`) fehlen im Assistenten — wer sie will, trägt sie von Hand in die `.env` ein. Aufräumen: die OpenAI-Abfrage aus `setup.cmd`/`installer_lib.py` entfernen.

### Weitere Ideen

- **Live-Diktat, satzweise am Cursor** (Sebastians Wunsch 25.09.2026): Text soll
  schon während des Sprechens erscheinen, „satzweise, mit ein bisschen
  Verzögerung", statt alles erst beim Loslassen. Machbar: während der Aufnahme
  alle ~10 s an der letzten stillen Stelle schneiden (`stillste_stelle` gibt es
  aus der Happen-Messung), den Happen sofort transkribieren und den fertigen Satz
  einfügen. Gemessen kostet der Schnitt keine Qualität (25-s-Happen 3,4 % gegen
  4,0 % am Stück). Als **Schalter im Tray**: „Alles auf einmal" / „Live satzweise".
  Grenze: echtes Wort-für-Wort-Streaming geht über OpenRouter nicht — der
  Transkriptions-Endpunkt nimmt fertige Dateien, und Realtime-STT (Mistral
  Realtime, Nemotron-Streaming) ist dort nicht buchbar. Also satzweise mit 1–2 s
  Verzögerung. Risiko: Zwischenstücke werden ohne Fortsetzung geglättet und
  können nicht mehr korrigiert werden, weil sie schon im Dokument stehen.
- **Umschalt-Modus** („einmal drücken zum Starten/Beenden") mit Auswahl im Tray-Menü
- **Lokale Transkription** mit `faster-whisper`
- **EU-Anbieter** prüfen (deutsches Whisper-Hosting, Azure OpenAI Westeuropa)
- **Datenschutz auf dem Arbeitgeber-PC** klären
- **`AltGr + Ä` als eigener Eintrag**
- **Android-APK** via EAS Build
- **Sprachwahl im Tray-Menü** (Deutsch / Englisch / automatisch)

## Arbeitsweise mit Claude

- Sprache: **Deutsch**
- Erklärungen: immer WARUM, nicht nur WAS
- **Vor jeder Dateiänderung / jedem Befehl:** Sicherheitsinfo aus CLAUDE.md ausgeben
- **Vor Build:** Tests ausführen (`pytest windows/tests/`)
- **Vor Weitergabe:** Critic-Lauf (`node .claude/skills/critic/pruefe.mjs windows/typefree.py`)
- Jeden Schritt erst erklären, dann auf Bestätigung warten
