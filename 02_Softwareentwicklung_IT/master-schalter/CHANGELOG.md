# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

## [0.4.0] – 2026-10-16

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
