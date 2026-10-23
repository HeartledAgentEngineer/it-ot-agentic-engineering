# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

## [0.5.0] – unveröffentlicht

Wechselassistent, Bausteine P4 (Ablauf und Zustellung) und P3a (Claude-Empfang per Hook). Gebaut auf Branch
`v0.5.0-wechselassistent`.

### Neu
- **`assistent.py`:** `uebergeben(thema, ziel, von_chat, nach_chat)` legt den Vorgang an
  (Write-ahead mit Vorzustand), schickt dem alten Chat den Abgabe-Auftrag und ruft einmal
  `fortsetzen` auf. `fortsetzen(vorgang)` ist der idempotente Takt: 10-Minuten-Frist
  (`ABGABE_FRIST`) mit Info an den alten Chat (nur der Gewinner des Überspringens sendet), Rolle
  setzen unter der Themensperre (Marke ≠ Vorzustand → `verworfen`, „Stand geändert“), danach die
  Nachricht an den neuen Chat (`sende` vor dem Transport). Zustellung an Codex über `codex.exe
  queue`, an Claude/Hermes über das Postfach; Transporte laufen nie unter Themen- oder Dateisperre.
  Doppelklick-Schutz (belegte Sperre, laufender Vorgang); eine übersprungene Abgabe ergibt einen
  Zusatzsatz im Text an den neuen Master.
- **Chat-Referenzen:** `ChatRef(werkzeug, kennung)`; `Vorgang` bekommt die optionalen Felder
  `von_chat` und `nach_chat` (alte Dateien ohne diese Felder lesen weiter). Kennungen stehen nur in
  `assistent.json`.
- **`protokoll.py`:** `protokoll.jsonl` (G10) mit den Entscheidungen des Ablaufs, ohne Kennungen,
  Titel oder Inhalte; `lesen(limit)` für das spätere Fenster.
- **CLI:** `uebergeben THEMA ZIEL [--von WERKZEUG:KENNUNG] [--nach WERKZEUG:KENNUNG]` und
  `fortsetzen [VORGANG]`; beide geben nur Vorgangs-ID, Thema und Phase aus.
- **Claude-Empfang per Hook (P3a):** `claude_hook.py`, aufrufbar als `python -m master_schalter.claude_hook`.
  `UserPromptSubmit` und `PostToolUse` melden `arbeitet` und merken mit `postfach.vormerken("claude",
  session_id)` Nachrichten vor; gibt es welche, steht genau ein JSON `hookSpecificOutput` mit
  `additionalContext` (feste Einleitung plus feste Postfachtexte) auf stdout, sonst keine Ausgabe. `Stop`
  setzt nur `ruht` und blockiert nie (kein `decision: block`). Jeder Fehler (kaputtes JSON, unzulässige
  Sitzungskennung, belegte Sperre, `OSError`, Importfehler) endet mit Exit 0 ohne Ausgabe; auf Modulebene
  steht nur die Standardbibliothek, stdin wird auf 1 MB begrenzt, nur `hook_event_name` und `session_id`
  werden ausgewertet. **Der Hook ist noch nicht in eine `settings.json` eingetragen.**
- **Ausgabe vor Zustellung (Postfach):** `postfach.abholen` besteht jetzt aus `vormerken` (prüft wie bisher,
  verschiebt nichts, liefert `Vorgemerkt`) und `bestaetigen` (liest unter der Themensperre erneut, übergeht
  geänderte Dateien und trifft mit `_entscheiden` wieder dieselbe Entscheidung wie früher `abholen`:
  zustellen, verwerfen mit Grund oder liegen lassen – wechselt der Master dazwischen, wird der Vorgang
  nicht `im_chat`; wurde die Nachricht schon ausgegeben, steht sie im Chat und die Quittung scheitert, der
  Text sagt dazu „beginne keinen Schritt“). Der Hook bestätigt erst nach erfolgreicher Ausgabe; scheitert sie, bleibt die
  Nachricht liegen und kommt beim nächsten Ereignis erneut (lieber doppelt als verloren, gültig nur über die
  Quittung, G5). `abholen` verhält sich unverändert. Das Prozessende des Hooks ist hart (`os._exit(0)` nach
  letztem `flush`), damit geschlossenes stdout nicht mit stderr-Meldung und Exit 120 endet.
- **Laufzeit-Obergrenze:** `vormerken`, `bestaetigen` und `abholen` haben die optionalen Parameter `frist`
  (Sperrfrist für Themensperre und `aendern`) und `bis` (Zeitbudget als `time.monotonic()`-Zeitpunkt; danach
  wird keine weitere Datei angefasst); eine belegte Sperre lässt die Datei liegen. Der Hook nutzt 0,3 s
  Sperrfrist, 0,6 s Budget zum Vormerken und 0,4 s zum Bestätigen.
- **Statusregister (K2):** `status.py` mit `status/<werkzeug>-<kennung>.json` (`zustand`, `zeit`,
  `ereignis`), atomar geschrieben; `arbeitet` höchstens einmal je 60 s, solange der Zustand gleich bleibt;
  `lesen(werkzeug, kennung)` liefert `(zustand, zeit)` oder `None` (= unbekannt) für den späteren
  Ruhenachweis.
- `assistent_vorgaenge.phase_gewinnen` meldet zusätzlich, ob der aufrufende Prozess den Phasenwechsel
  gemacht hat; `postfach.text()` baut die festen Nachrichtentexte (auch für die Codex-Queue).

### Geändert
- `abgabe_ueberspringen` gilt jetzt auch aus `abgabe_fehler` (Frist nach nicht gestartetem Transport).
- **Blockade neuer Wechsel:** nur noch in den Phasen `av.WECHSEL_BLOCKIEREND` (Rolle noch nicht gesetzt
  oder `sende`); ab `rolle_gesetzt` blockiert ein Vorgang nicht mehr.
- **Überholt:** nach erfolgreichem Rollensetzen werden die anderen Vorgänge desselben Themas in den
  Phasen `av.UEBERHOLBAR` (`rolle_gesetzt`, `gesendet`, `im_postfach`, `im_chat`, `unklar`, `fehler`)
  mit einem `av.aendern`-Schritt auf `verworfen` / „überholt“ gesetzt, mit Protokolleintrag.
- **Protokoll ohne Fremdtexte:** Fehler beim Fortsetzen, Rollensetzen und Markenprüfen nennen nur die
  Fehlerklasse (Ursache an `__cause__`); der Verwerfungsgrund bei überholter Marke ist ein fester Text.
- `wiederaufnehmen`: `abgabe_fehler` erscheint als Status `abgabe_offen` mit Fristhinweis.
- **Zustellung unter der Themensperre (Ergebnisprüfung R1):** Markenprüfung und `rolle_gesetzt → sende`
  laufen gemeinsam unter `thema_sperre` (blockierend, kurze Frist; belegt = nichts tun, nächster Takt);
  der Transport bleibt außerhalb jeder Sperre. `_rolle_setzen` wartet, solange ein anderer Vorgang
  desselben Themas in `sende` steht.
- **Abgabe-Info erst nach dem Rollenwechsel:** die Frist setzt nur noch `abgabe_uebersprungen`; die Info
  an den alten Chat geht erst raus, wenn `_rolle_setzen` den Wechsel nach `rolle_gesetzt` gewonnen hat
  (nur bei übersprungener Abgabe mit `von_chat`; Codex außerhalb jeder Sperre). Bei Absturz dazwischen
  geht sie verloren, nie nachgesendet.
- **Restfenster vor dem Transport (R2):** `_zustellen` prüft die Marke direkt vor dem Senden (außerhalb der
  Sperre) noch einmal; passt sie nicht, `sende → verworfen` (Protokoll `neu_entfallen`), nichts gesendet
  (nicht lesbar: `fehler`). Ein Restfenster bleibt grundsätzlich – die Gültigkeit erzwingt die Quittung (G5).
  `postfach.TEXT_NEU` ergänzt: „Schlägt die Quittung fehl, beginne keinen Schritt – die Nachricht gilt dann
  nicht mehr.“
- **Abgabe-Info nach Rückwechsel (R2):** vor dem Senden wird geprüft, dass der Vorgang nicht `verworfen` ist
  und die Marke noch genau diesen Wechsel trägt; sonst Protokoll `info_entfallen`. `TEXT_ABGABE_INFO`
  ergänzt: „Maßgeblich ist die Besitzmarke; prüfe im Zweifel `masterwechsel profil {thema}`.“
- **Bereinigte Ausnahmen (R2):** Jede Ausnahme, die `uebergeben` oder `fortsetzen` verlässt, ist ein
  bereinigter `AssistentFehler` (auch aus `abgabe_ergebnis` und den Aufrufen nach dem Anlegen); bleibt dabei
  `abgabe_sende` stehen, macht `wiederaufnehmen` daraus `abgabe_unklar`.
- **Fehlermeldungen ohne Pfade:** Hilfsfunktion für alle `AssistentFehler` aus fremden Ausnahmen; mit
  `OSError` in der Kette steht nur ein fester Text mit Fehlerklasse (`SperrFehler`: „Sperre gerade
  belegt“). Fremde Ausnahmetexte werden nie übernommen (nur Fehlerklasse); „Thema unbekannt“ prüft `uebergeben` selbst (Prüfung R3/R4); ungeprüfte Eingaben (Thema, Vorgangs-ID)
  und `OSError`-Texte werden in Meldungen und CLI nie wiederholt (R6).
  `uebergeben ZIEL` und `quittieren ART` ohne argparse-`choices` (kein Echo der Eingabe); `quittieren` meldet
  Vorgangs-ID-Fehler, veraltete Marke und Datei-/Sperrfehler nur mit festem Text bzw. Fehlerklasse (R7).
  `modi.py` unverändert.

### Noch nicht gebaut
- Ruhenachweis (G8b, liest das Statusregister, P7a), Hook-Eintrag in `settings.json`, Empfang im
  Hermes-Chat (P6), Fenster und Takt in der Leiste (P5).

## [0.4.1] – 2026-10-21

### Behoben
- **Claude-Modellkatalog nach Claude-Code-Update:** Das npm-Paket ab 2.1.3xx enthält kein `cli.js`
  mehr, sondern das native `bin/claude.exe`. `claude_programm()` liefert jetzt das Aufrufpräfix
  `(node, cli.js)` **oder** `(claude.exe,)` (Suche zusätzlich in `%APPDATA%/npm/node_modules/@anthropic-ai/claude-code/bin/`
  und `~/.local/bin/`); vorher meldete der Katalog „Programm nicht gefunden". Echter Abruf am 21.10.
  mit 2.1.304: 5 Modelle.
  Liegt noch ein altes `cli.js` herum, aber kein Node, geht die Suche zum nativen Programm weiter.
- **Tests unabhängig von der Installation:** Die Fixture `daten` setzt feste Attrappenpfade für
  `MASTER_SCHALTER_CLAUDE_CLI`/`MASTER_SCHALTER_NODE`; 8 Tests hingen zuvor davon ab, dass auf dem
  Rechner ein `cli.js` liegt. Zwei neue Tests für das native Programm.

### Geändert
- Version 0.4.1 (`__init__.py`, `pyproject.toml`).

## [0.4.0] – 2026-10-20

Gebaut 16.10. auf Branch `v0.4.0-rollen-modelle`, am 20.10. mit 0.3.5 zusammengeführt;
die 0.3.5-Reparatur (Wechselsperre außerhalb des Traycallbacks) bleibt vollständig erhalten.

### Neu
- **Rollen und Ausführermodelle je Thema (Profil v2):** `themenmodi.json` speichert je Thema
  `master` (`kontingent|claude|codex|hermes`), `worker` (`workflow|claude|codex|hermes`) und
  `modell` (Kennung oder `null`; „Nach Workflow“ nur ohne festes Modell, Hermes genau
  `deepseek/deepseek-v4.1-flash`). Alle neun ausdrücklich gewählten Master-/Ausführer-Kombinationen
  sind setzbar; Version-1-Dateien werden **nur lesend** migriert (Migration beim ersten
  ausdrücklichen Schreibvorgang), kaputte Dateien werden strikt abgelehnt statt auf Automatik
  zurückzufallen. Neue öffentliche API `profil`, `master_setzen`, `worker_setzen`,
  `modell_setzen`; Worker-/Modellwechsel lassen Masterfeld und `.master`-Marke bytegleich,
  Modellwahlen werden gegen den erfolgreich ermittelten Katalog geprüft.
- **Dynamische Modellkataloge (`modelle.py`):** Codex meldet `models` über den reinen
  App-CLI-Metadatenaufruf `debug models` (nur `visibility=list`); Claude Code über die lokale
  Control-Initialisierung ohne Anmeldung und ohne Benutzerprompt (nur `value`/`displayName` der
  eigenen passenden `control_response`). Lokaler Metadatencache (`modelle.json`), TTL 24 h,
  Fristen 30 s je Abfrage und 65 s gesamt, feste Byte-/Zeilen-/Modellgrenzen, Single-Flight je
  Anbieter, verlustfreies Mergen unter kurzer globaler Sperre; bei Fehlern bleibt das letzte gute
  Ergebnis mit sichtbarem Fehlerstatus stehen. Keine Inferenz, keine API-/Fremdprovider-Schlüssel
  im Kindprozess, Bereinigung ausschließlich des eigenen Prozessbaums
  (`taskkill /PID <eigene PID> /T /F`, keine Namenssuche). Herkunft/Grenzen offiziell dokumentiert:
  https://learn.chatgpt.com/docs/cli/reference und https://learn.chatgpt.com/docs/app-server ;
  kein Kontokatalog-Versprechen.
- **Menü „Arbeitsmodus je Thema“:** je Thema getrennte Untermenüs **Master** (`Nach Kontingent`,
  `Claude Code`, `Codex`, `Hermes`), **Ausführer** (`Nach Workflow`, `Claude Code`, `Codex`,
  `Hermes`) und **Ausführermodell** (gemeldete Modelle des gewählten Ausführers; bei „Nach
  Workflow“ deaktivierter Hinweis; bei Hermes genau `DeepSeek V4.1 Flash`). Providerherkunft immer
  sichtbar (Codex-Modelle aus dem ChatGPT-Abo, Hermes über OpenRouter kostenpflichtig), neuer
  Menüpunkt **Modelle aktualisieren**; Menü und Häkchen ausschließlich aus dem Snapshot, Aktionen
  im Hintergrund mit nichtblockierender Themensperre, Katalogabgleich mit Single-Flight und
  Drossel (30 min). Gespeicherte, nicht bestätigte Modelle bleiben sichtbar und werden nie still
  ersetzt; veraltete/fehlerhafte Kataloge werden im Menü benannt, blockieren aber nichts.
- **CLI (bestehende Befehle unverändert):** `profil THEMA [--json]`, `master-setzen THEMA MASTER`,
  `worker-setzen THEMA WORKER`, `modell-setzen THEMA MODELL|standard`,
  `modelle [PROVIDER] [--aktualisieren] [--json]`. Die JSON-Ausgabe ist maschinenlesbar; Fehler
  liefern Exit 1 und eine klare Diagnose ohne rohe Werkzeugantworten. `profil THEMA --json` ist
  vor jedem **neuen** Workerauftrag die verbindliche Provider-/Modellvorgabe (README/AGENTS).

### Geändert
- Persönliches Themenprofil: Alter `hermes-codex`-Modus wird als `hermes/codex/gpt-6-luna`
  gedeutet; die bisherigen Befehle `modus` und `setzen` bleiben kompatibel. Feste Masterrollen
  bleiben vor Automatik, manueller Sammelrückgabe und alten ACKs geschützt (Paket B).
- Version 0.4.0 (`__init__.py`, `pyproject.toml`); README auf den neuen Stand (Bedienung,
  Rollenprofil, Katalogquellen und -grenzen, verbindliche Profilabfrage, Fahrplan).

### Behoben
- **NT-Pfadpräfix-Härtung:** Die Besitzpfadprüfung vergleicht jetzt komponentenweise und toleriert
  `\\?\`-Präfixe (Windows-Race), während ein echter Pfad außerhalb des Repositorys weiter ein
  Fehler bleibt.
- **Testlast:** Der Test „ungültige Protokollantwort bei laufendem Prozess“ nutzt bewusst
  großzügige, im Docstring begründete Zeitfenster (30 s Abfrage, 20 s Kill-Wartezeit), damit
  unter Rechnerlast deterministisch „Antwort ungültig“ gilt – Kill-Args, Kind-tot und
  Katalog-unverändert bleiben scharf. Der 429-Pausentest zählt ohne Rennen gegen den
  Bestätigungsfaden.
- **Testlast beim Zusammenführen (20.10.):** Zwei Bereinigungstests lasen die PID-Datei des
  hängenden Kindskripts sofort nach dem Lauf; unter Last war das Kind noch nicht gestartet
  (`FileNotFoundError`). Sie warten jetzt bis 20 s auf die Datei (`_pid_lesen`); Budget-, Fehler-
  und Lebendprüfung bleiben unverändert scharf.

## [0.3.5] – 2026-10-20

### Behoben
- Der Menücallback reserviert die Wechselsperre vor dem Start eines Hintergrundfadens, damit ein wartender Bestätigungsdialog den Traycallback nicht festhält. Direkte Wechselaufrufe nutzen dieselbe Sperre; parallele und reentrante Aufrufe werden übersprungen.
- Dialog- und Threadstartfehler melden sich sichtbar und geben die Sperre frei. Ein Dialogabbruch wechselt nichts; nur Ja führt den bisherigen Wechsel und bei Codex die bestehende Rückgabe aus.
- Tests prüfen Dialogflags und Ablauf mit Attrappen. Eine Bedienbarkeit des nativen Dialogs auf dem Desktop ist damit nicht nachgewiesen.

### Geändert
- Version 0.3.5 (`__init__.py`, `pyproject.toml`).

## [0.3.4] – 2026-10-16

### Neu
- **Arbeitsmodus je Thema:** `masterwechsel modus THEMA [kontingent|hermes-codex]` und Taskleisten-Untermenü mit cachierten Radiooptionen. Hermes-Modus bleibt unabhängig von Quoten geschützt; Moduswahl startet keine Sitzung und erzeugt kein ACK.
- **Fail-closed Themenbesitz:** Moduswechsel entwertet offene Vorgänge in definierter Reihenfolge, behandelt Teilschreibfehler idempotent und erhält Schutz über Hermes-Besitz oder gespeicherten Hermes-Modus. Automatik, verspätete ACKs, manuelle Rückgabe und globaler Claude-Rückwechsel respektieren den Schutz.
- **Codex-Code-Worker-Regel:** README und AGENTS dokumentieren den lokal verifizierten nativen Codex-App-CLI-Aufruf mit gpt-6-luna, vorhandener ChatGPT-Anmeldung und bereinigtem technischem Auftrag; keine API-/OpenRouter-Abrechnung.

### Geändert
- Teilfehlermeldungen nennen bereits entwertete Vorgänge und den erreichten Besitz-/Modusstand; ungültige CLI-Modi liefern eine einfache Fehlermeldung mit Exit 1.
- Taskleistenstatus trennt Standard-Master und Hermes-Themen. Menüaktionen sind nicht blockierend; Modus-/Besitz-Häkchen kommen ausschließlich aus dem Aktualisierungssnapshot.
- Version 0.3.4 (`__init__.py`, `pyproject.toml`).

## [0.3.3] – 2026-10-16

### Behoben
- **Claude-Messung versteht die neue API-Form:** Der Usage-Endpunkt liefert ein leeres 5h-Fenster
  seit dem 16.10.2026 als `utilization: 0.0, resets_at: null`. Die Validierung in
  `claude_messen._fenster` und `signale._claude_filtern`/`claude_lesen` akzeptiert die fehlende
  Rücksetzzeit jetzt **nur bei 0 %** (Fenster nicht aktiv) und liest sie als „0 % / kein Reset
  geplant"; fehlende Rücksetzzeit bei Verbrauch > 0 bleibt ungültig (alte Werte bleiben stehen).
  Zuvor verwarf die Prüfung jede Antwort dieser Form und die Anzeige blieb stumm auf dem letzten
  Stand. Anzeige/Tooltip überspringen den Reset-Text, wenn keine Zeit bekannt ist. Die
  Lage-Bewertung (`rollen._bewerten`) zählt ein gemessenes 0 % ohne Rücksetzzeit als **frei**;
  fehlende Rücksetzzeit **mit** Verbrauch bleibt weiter „unbekannt".

### Geändert
- Prüfer-/Subagenten-Rolle: `gpt-6-luna` abgelöst (Input-Preis 5x), `delegation.model` =
  `deepseek/deepseek-v4.1-flash`.

## [0.3.2] – 2026-10-16

### Neu
- **Rückgabe an Codex** (`rueckgabe.py`, `dialog.py`): Bestätigungsdialog vor jedem Wechsel im Menü
  (Standard **Nein**); nach bestätigtem Wechsel auf Codex erhält jedes aktive Paar eine
  Übergabenachricht in seinen Codex-Chat (Verweis auf die laufende Übergabedatei, Grenzen-Kurzliste,
  `ACK <Kennung>`-Bitte). CLI `rueckgabe [THEMA …] [--ja] [--erneut] [--hinweis]`; ohne `--ja` nur
  Trockenlauf (schreibt und sendet nichts).
- **Kennungen** `rueckgabe-<thema>-<yyyymmddHHMMSS>-<4Hex>` (fester Aufbau, präfixfrei — der
  `ACK`-Vergleich bleibt eindeutig); `lauf_id` = Kennung; `--erneut` erzeugt immer eine frische Kennung.
- **Kopfzeilen-Übernahme:** Nur der bestätigte manuelle Weg zieht die Kopfzeile auf `ja · jetzt · HEAD`
  (die Nachricht nennt es); „nein"/fehlend/ungültig bleibt fail-closed und schreibfrei. Der Vorzustand
  steht dauerhaft in der Reservierungszeile (`… vorzustand codex <alte-id>`); die Waisen-Auflösung
  stellt ihn exakt wieder her (mit Tests) — ein spätes ACK bleibt möglich.
- **Abbruch-/Fehlerregeln:** Jeder Abbruch nach der Reservierung und vor dem Transportstart stellt den
  Vorzustand exakt wieder her (nie eine Waise); Fehler nach Prozessstart bleiben `unklar`, die
  Codex-Besitzmarke steht dann weiter. Eine aktive fremde Reservierung wird nie übernommen.
- **Startfestigkeit:** abgekoppelter Starter `leiste_starten.cmd` mit Doppelstart-Schutz und Protokoll,
  Messfehler mit Zeitstempel in `leiste.log`, Autostart-Verknüpfung (siehe README „Start und Autostart").

### Geändert
- **Menü aufgeräumt:** „Automatik Claude → Codex"-Haken entfällt (Modul bleibt, schaltbar per
  `masterwechsel automatik an|aus`); „Jetzt prüfen" ging in „Aktualisieren" auf (frisch messen,
  Zustände lesen und offene Übergaben abhaken — auch bei ausgeschalteter Automatik).
- Version 0.3.2 (`__init__.py`, `pyproject.toml`).

## [0.3.0] – 2026-10-15

### Neu
- **Automatische Übergabe Claude → Codex** (Freigabe 15.10.2026; nur Claude → Codex, nur
  eingeschaltete Paare, nur bei frischer Messung, ein Vorgang je Limitfenster, Rückweg manuell).
  Standardmäßig **aus** (`einstellungen.json`, Feld `automatik`); einschaltbar im Menüpunkt
  „Automatik Claude → Codex". Prüfung nach jeder erfolgreichen Claude-Messung (1-Minuten-Takt)
  und über „Jetzt prüfen" bzw. `masterwechsel automatik-pruefen [--trocken]`.
- **Paare** (`paare.py`, `paare.json`): Thema ↔ Codex-Chat (geprüfte, eindeutige UUID) ↔ laufende
  Übergabedatei. Das Thema wird als `re.fullmatch` geprüft (`^[a-z0-9][a-z0-9-]{0,79}$`, ein
  abschließendes Zeilenende ist damit abgelehnt); der laufende Pfad ist nicht frei, sondern exakt
  `.hermes/uebergabe/laufend/<thema>.md`. CLI `paar-setzen`, `paar-aktiv`, `paare`.
- **Sicherer Übergabepunkt:** Die laufende Übergabedatei führt in der ersten Zeile
  `Übergabebereit: ja|nein · <ISO-Zeit> · <HEAD-Kurzform>`; gelesen wird nur diese Zeile.
  Gesendet wird nur bei `ja`, Zeit ≤ 2 h und einer HEAD-Kurzform (7–12 Hexzeichen), die exakter
  Präfix des aktuellen `git rev-parse HEAD` ist. Der HEAD wird **frisch** ermittelt — vor der
  Reservierung und noch einmal nach der 30-Sekunden-Wartezeit, unmittelbar vor dem Versand; ein
  fremder Commit in dieser Zeitspanne blockiert den Versand (der HEAD-Vergleich ersetzt den
  Sekunden-Zeitvergleich).
- **Handschlag und Sperren:** Besitzdatei `<thema>.master` (`claude …` / `reserviert …` /
  `codex …`); Reservieren → 30 s warten → Kopfzeile und HEAD erneut prüfen → erst dann senden.
  Je Thema eine Betriebssystem-Sperre (`automatik-<thema>.lock`, nicht blockierend); ein belegtes
  Thema wird übersprungen. Der manuelle Rückwechsel nimmt dieselben Themensperren (blockierend,
  höchstens 5 s) in alphabetischer Reihenfolge und entwertet offene Vorgänge
  (`claude <Zeit> entwertet <ID>`); die Besitzmarke jedes Themas geht dabei wieder an Claude zurück
  (bei einem bereits bestätigten Vorgang ohne `entwertet`), damit kein Thema dauerhaft als
  „von Codex übernommen" gesperrt bleibt.
- **Vorgänge** (`vorgaenge.py`, `vorgaenge.json`): Kennung `<thema>@<Rücksetzzeit>` — je Paar und
  Limitfenster genau einer; eine vorhandene Kennung (jeder Phase) wird nie erneut gesendet. Der
  Eintrag steht dauerhaft (Phase `sende`) auf der Platte, **bevor** gesendet wird: ein Absturz
  danach führt zu keinem zweiten Versand.
- **Senden** (`codex_senden.py`): `codex.exe queue --thread <UUID> --message <Prompt>`
  (Argumentliste, keine Shell, Zeitgrenze 60 s; neueste `codex.exe` der Codex-App,
  `MASTER_SCHALTER_CODEX` hat Vorrang). Nur ein belegtes **Nicht-Starten** des Prozesses gibt den
  Besitz zurück (`fehler`); alles nach dem Start gilt konservativ als `unklar` (Codex-Besitz und
  Kennung bleiben erhalten).
- **Bestätigung** (`ack.py`): nur Assistentenantworten des Zielchats nach dem Sendezeitpunkt, die
  mit `ACK <kennung>` beginnen (Rollout-Dateien `rollout-*-<UUID>.jsonl` im Sitzungsordner). Der
  eigene Prompt zählt nie. Bestätigt wird **fail-closed** und atomar: Besitz (`<thema>.master`
  genau `codex <id>`), die frische Phase **und** das Setzen des globalen Masters liegen in **einem**
  gesperrten Abschnitt (Themensperre zuerst, darin kurz die globale Zustandssperre) — ohne
  prüfbares Repo oder bei inzwischen entwertetem Vorgang gibt es keine Bestätigung. Ein Rückwechsel
  läuft damit entweder komplett davor (dann keine Bestätigung) oder komplett danach (dann bleibt er
  der letzte Wille) und wird nie nachträglich auf Codex überschrieben. Reihenfolge im Teilschritt
  bewusst „globaler Master, dann Phase": bricht der Lauf dazwischen ab, bleibt der Vorgang offen
  und der nächste Lauf bestätigt erneut (idempotent) — nichts blockiert. Ohne ACK nach 15 Minuten
  „keine Bestätigung"; ein ACK auf einen entwerteten Vorgang bleibt wirkungslos.
- **Gültige Messwerte:** Der Codex-Verbrauch zählt nur von 0 bis 100. Negative, über 100 liegende,
  nicht endliche oder fehlende Werte gelten als **unbekannt** (`signale._fenster`/`_nur_zahlen`)
  und werden auch in der Entscheidung zurückgewiesen (`automatik._gueltiges_fenster`) — sie lösen
  nie einen Versand aus.
- **Paketoption** (`uebergabe.py`): `paket_bauen(..., *, plaene=True, minimal=False)` —
  rückwärtskompatibel. Der Automatikweg nutzt `plaene=False, minimal=True`: `_plaene` wird nicht
  aufgerufen, und der Abschnitt „Stand" enthält nur Zeitpunkt, HEAD, Anzahl Commits und die
  **Anzahl** uncommitteter Pfade — keine Betreffzeilen, keine Dateinamen. Der Prompt enthält nur
  Pfade, Kennung und Zahlen, keinen Dateiinhalt.
- **Datenordner verschoben:** `%USERPROFILE%\.master-schalter\` statt
  `%LOCALAPPDATA%\master-schalter\`. Claude- und Codex-App sind MSIX-Pakete; ihre Kindprozesse
  wurden je nach Starter in `AppData\Local\Packages\…` umgeleitet, sodass drei getrennte Zustände
  entstanden (Autostart, Codex-Start, Claude-CLI). `MASTER_SCHALTER_DATEN` bleibt Vorrang; alte
  Dateien werden nicht übernommen (Werte werden neu gemessen, Master neu gesetzt).

### Grenzen
- Der **Rückweg Codex → Claude bleibt manuell** (der Claude-Zustellweg ist unbelegt).
- Die Automatik arbeitet mit **beobachteten frischen Momentaufnahmen**; das ersetzt keine
  garantierte Quotenreservierung. Ephemere Codex-Läufe hinterlassen keine Rollouts — das
  Ausbleiben neuer Ereignisse ist deshalb ausdrücklich kein Nutzungsbeleg.
- Live-Abnahme (Probe an genau ein Paar, danach Automatik mit Schwelle) steht noch aus.

## [0.2.1] – 2026-10-15

### Neu
- **Hermes als dritter, manuell wählbarer Master** (Lage 3 der Kaskaden-Matrix: Thinker = Hermes/DeepSeek).
  `master.json` akzeptiert `"hermes"`, das Menü „Master wechseln" und `masterwechsel wechsel hermes` bieten
  ihn an; Tooltip und Statuszeile zeigen dann „M Hermes …“. Hermes hat kein eigenes Kontingent: kein
  Balken, kein weißer Punkt; `wechsel` legt wie gewohnt zuerst das Übergabepaket ab
  (`…_masterwechsel-<von>-hermes.md`).
- README-Fahrplan an die Release-Tabelle des v0.3-Plans angeglichen (Automatik = v0.3.0,
  Hermes-Sitzungen = v0.3.1, Rückweg = v0.4.0).

## [0.2.0] – 2026-10-14

### Neu
- README dokumentiert den optionalen Windows-Benutzer-Autostart über eine eigene
  `shell:startup`-Verknüpfung mit `pythonw.exe`, Startargumenten und Arbeitsordner.
  v0.2 bringt dafür kein eigenes Autostart-Menü oder Einrichtungs-Skript mit.
- Claude-Kontingent über `masterwechsel claude-messen` und im Taskleisten-Worker messen; beim
  Start, nach „Aktualisieren" und standardmäßig jede Minute (einstellbar über
  `claude_takt_min`, 1–60 Minuten). HTTP 429 löst bis zum nächsten Erfolg einen 5-Minuten-Takt aus.
- Der OAuth-Adapter liest den Access-Token zur Laufzeit aus `~/.claude/.credentials.json`, verwendet
  keinen Refresh-Token und speichert/protokolliert/zeigt den Token nicht. Beide Messfenster werden
  vor dem atomaren Schreiben auf vollständige, endliche Prozentwerte und Rücksetzzeiten geprüft.
- Aktiven Master, Wechselzeit, Kaskaden-Lage und Besetzung anzeigen.
- Masterwechsel per CLI oder Taskleistenmenü; das technische Übergabepaket wird vor dem
  Zustandswechsel geschrieben. Fehler beim Sperren oder Paketbau lassen den Zustand unverändert.
- Übergabepakete enthalten nur technische Metadaten und Pläne mit der expliziten Einordnung
  „technisch"; Datei- und Chat-Inhalte werden nicht übernommen.
- Schwelle im Taskleistenmenü auf 80, 90, 95, 97 oder 100 % einstellen.

### Grenzen
- v0.2 startet oder beschreibt keinen Chat. Der neue Master liest das Paket, wenn Sebastian ihn
  darauf hinweist.
- Die Claude-Usage-API ist eine inoffizielle Schnittstelle. Bei HTTP 401 oder abgelaufener
  Anmeldung erscheint eine generische Meldung; der bisherige Messwert bleibt erhalten.
- Nach einem Reset zeigen Tooltip und Balken bis zur nächsten Messung weiterhin 0 %; die Lage
  behandelt den Wert als unbekannt. Die Anzeige wird in v0.1.1 korrigiert.

## [0.1.0] – 2026-10-14

### Neu
- Taskleisten-Symbol (`master_schalter.leiste`) mit zwei Balken für Claude Code und Codex,
  Tooltip, Benachrichtigung per Linksklick und Menü per Rechtsklick.
- Kontingente lesen (`signale.py`): Codex aus den lokalen Sitzungsdateien (nur Zahlen, auch im
  Zwischenspeicher; inkrementell; gekürzte oder neu geschriebene Dateien werden an Größe bzw.
  geändertem Dateianfang (erste 4 KB) erkannt und von vorn gelesen; neuester Eintrag über alle
  Dateien — die Änderungszeit jeder Datei dient als Obergrenze, damit ältere Dateien gar nicht
  erst gelesen werden müssen), Claude aus der Statuszeilen-Datei.
- Befehlszeile `masterwechsel`: `status`, `statuszeile`, `claude-kontingent`.
- Schwelle für Rotfärbung einstellbar (`einstellungen.json`, Standard 97 %).

### Bekannte Grenzen
- Die Claude-Desktop-App führt die Statuszeile nicht aus; Claude-Werte kommen dann nur über
  `masterwechsel claude-kontingent` oder Claude Code im Terminal.
- Codex-Werte sind so frisch wie die letzte Codex-Sitzung (Prüfläufe mit `--ephemeral`
  schreiben keine).
