# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Der Schalter zeigt außerdem den
aktiven Master, ordnet die Lage der Kaskaden-Matrix zu und legt beim Wechsel ein
technisches Übergabepaket bereit.

Stand: **v0.4.1** — Claude-Katalog findet das native `claude.exe` (npm-Paket ab 2.1.3xx ohne `cli.js`). Darunter v0.4.0: Rollen und Ausführermodelle je Thema (Profil v2): Master, Ausführer und Ausführermodell getrennt wählbar, dynamische Modellkataloge von Claude Code und Codex, neue CLI (profil/master-setzen/worker-setzen/modell-setzen/modelle). Hermes-Worker bleibt DeepSeek V4.1 Flash über OpenRouter (kostenpflichtig). Enthält die v0.3.5-Reparatur: bestätigter Menüwechsel läuft außerhalb des Traycallbacks; die native Ja/Nein-Bedienung auf dem Desktop ist weiterhin nicht nachgewiesen.

## Bedienung

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile mit Master, Lage und Kontingenten |
| Linksklick | Windows-Benachrichtigung mit beiden Mastern und Stand-Zeit |
| Rechtsklick | Menü mit Master, Lage, Besetzung, „Master wechseln" (mit Rückfrage), Wechsel-Schwelle, „Arbeitsmodus je Thema" (je Thema Master, Ausführer, Ausführermodell), „Modelle aktualisieren", „Chats übergeben", Aktualisieren und Beenden |

Das Symbol besteht aus zwei Balken (links Claude, rechts Codex). Die Füllhöhe zeigt den
5-Stunden-Verbrauch: Grundfarbe bis 79 %, gelb ab 80 %, rot ab der Schwelle (Standard 97 %).
Die Anzeige wird standardmäßig jede Minute aktualisiert. Die Claude-Messung läuft beim
Start, nach „Aktualisieren" und anschließend im eingestellten Takt; dabei werden offene Übergaben
abgehakt (auch wenn die Automatik aus ist).

Im Menü „Master wechseln" kann Claude, Codex oder Hermes ausgewählt werden (Hermes = Lage 3 der
Kaskaden-Matrix; kein eigenes Abo-Kontingent, deshalb kein Balken und kein weißer Punkt). Jeder Wechsel
fragt vorher nach (Ja/Nein, Standard **Nein**); beim Ziel **Codex** werden danach zusätzlich alle aktiven
Themen an ihre Codex-Chats zurückgegeben (siehe „Rückgabe an Codex"). Der Wechsel legt ein Markdown-Paket
unter .hermes/uebergabe/ ab und zeigt den Paketnamen an. Themen mit Hermes-Schutz bleiben beim globalen Standardwechsel unberührt. Die Schwelle lässt sich im Menü „Wechsel-Schwelle"
auf 80, 90, 95, 97 oder 100 % setzen; sie steuert Lage und rote Anzeige. Die unbemannte Automatik
(Claude im Limit → Übergabe) läuft nur, wenn sie ausdrücklich eingeschaltet ist — per
`masterwechsel automatik an` (der frühere Menühaken ist in v0.3.2 entfallen).

## Automatische Übergabe Claude → Codex (v0.3.0)

Die Automatik ist **standardmäßig aus** (`einstellungen.json`, Feld `automatik`). Eingeschaltet
wird sie per `masterwechsel automatik an` (bis v0.3.0 ein Menühaken; in v0.3.2 entfallen, weil die
Rückgabe das Bedürfnis abdeckt) oder in der Datei selbst. Sie greift
nur für **eingeschaltete Paare** und nur, wenn Claude im Limit **und** Codex frisch gemessen frei
ist.

**Paare anlegen** (Thema ↔ Codex-Chat ↔ laufende Übergabedatei):

```powershell
.\.venv\Scripts\\masterwechsel.exe paar-setzen engineering <UUID-des-Codex-Chats> .hermes/uebergabe/laufend/engineering.md
.\.venv\Scripts\\masterwechsel.exe paar-aktiv engineering an
.\.venv\Scripts\\masterwechsel.exe paare
```

Das **Thema** wird streng geprüft (`^[a-z0-9][a-z0-9-]{0,79}$`, keine Großbuchstaben, kein
Zeilenende). Aus ihm entsteht der laufende Pfad: er muss exakt
`.hermes/uebergabe/laufend/<thema>.md` sein — ein anderer Dateiname wird abgelehnt. Die
Chat-Kennung ist eine geprüfte, eindeutige UUID; je Chat genau ein Paar.

**Sicherer Übergabepunkt:** Die laufende Übergabedatei schreibt der jeweilige Claude-Master-Chat
selbst. Gelesen wird vom Programm **nur die erste Zeile**:

```
Übergabebereit: ja|nein · <ISO-Zeit> · <HEAD-Kurzform>
```

Gesendet wird nur, wenn dort `ja` steht, die Zeit höchstens 2 h alt ist **und** die genannte
HEAD-Kurzform (7–12 Hexzeichen) exakter Präfix des aktuellen `git rev-parse HEAD` ist. Der HEAD
wird dabei **frisch ermittelt** — sowohl vor der Reservierung als auch noch einmal **nach** der
30-Sekunden-Wartezeit, unmittelbar vor dem Versand. Ein fremder Commit in dieser Zeitspanne
blockiert den Versand (der HEAD-Vergleich ersetzt einen Sekunden-Zeitvergleich).

**Handschlag (verhindert gleichzeitiges Arbeiten):** Je Thema gibt es eine Besitzdatei
`.hermes/uebergabe/laufend/<thema>.master`. Der Claude-Chat schreibt vor jedem neuen Schritt
zuerst `Übergabebereit: nein`, die Automatik reserviert mit `reserviert <lauf-id> <Zeit>`, wartet
30 s und prüft **danach** Kopfzeile und HEAD erneut; nur dann wird gesendet. Alle Läufe eines
Themas laufen unter einer Betriebssystem-Sperre je Thema
(`~/.master-schalter/automatik-<thema>.lock`); ein belegtes Thema wird übersprungen.

**Ein Vorgang je Limitfenster:** Die Kennung ist `<thema>@<Rücksetzzeit>`. Eine bereits
vorhandene Kennung — in welcher Phase auch immer — wird nie erneut gesendet. Der Eintrag steht
**dauerhaft auf der Platte** (`vorgaenge.json`, Phase `sende`), bevor irgendetwas gesendet wird;
ein Absturz danach führt zu keinem zweiten Versand. Nur ein belegtes **Nicht-Starten** des
Transportprozesses gibt den Besitz zurück; alles nach dem Start gilt konservativ als **unklar**
(Codex-Besitz und Kennung bleiben, Menü zeigt „Zustellung unklar"), weil der Auftrag schon
zugestellt sein kann.

**Versand und Bestätigung:** Der Transport ruft die neueste `codex.exe` der Codex-App
(`%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`; `MASTER_SCHALTER_CODEX` hat Vorrang) mit
`queue --thread <UUID> --message <Prompt>` auf (Argumentliste, keine Shell, Zeitgrenze 60 s).
Bestätigt wird nur eine **Assistentenantwort des Zielchats** nach dem Sendezeitpunkt, die mit
`ACK <kennung>` beginnt (Rollout-Dateien `rollout-*-<UUID>.jsonl` unter dem Codex-Sitzungsordner).
Vor dem Schreiben prüft der Schalter **unter derselben Themensperre** erneut, dass die Besitzdatei
weiterhin genau `codex <kennung>` enthält und der Vorgang noch `gesendet`/`unklar` ist — auch der
**globale Master** wird in genau diesem gesperrten Abschnitt gesetzt. Ohne prüfbaren Besitz gibt es
keine Bestätigung (fail-closed). Ein Rückwechsel kann eine Bestätigung also weder überholen noch
danach überschrieben werden: er läuft entweder komplett davor oder komplett danach.
Ohne Bestätigung nach 15 Minuten zeigt das Menü „keine Bestätigung"; erneut gesendet wird nicht.
Der **Rückweg bleibt manuell** („Master wechseln → Claude"): er entwertet offene Vorgänge
(`claude <Zeit> entwertet <ID>`), gibt die Besitzmarke jedes Themas wieder an Claude zurück und
stellt den globalen Master um; ein danach eintreffendes ACK ändert nichts mehr.

**Datenschutz:** Das Automatikpaket enthält **keinen** Repo-Freitext — keine Commit-Betreffzeilen,
keine Dateinamen, keine repo-weite Planliste —, sondern nur Zeitpunkt, HEAD, Anzahl Commits, die
**Anzahl** uncommitteter Pfade und den Pfad der laufenden Übergabe. Der Prompt enthält nur Pfade,
Kennung und Zahlen, keinen Dateiinhalt.

```powershell
# Automatik prüfen, ohne etwas zu senden
.\.venv\Scripts\\masterwechsel.exe automatik-pruefen --trocken
```

## Arbeitsmodus je Thema (v0.4.0)

Jedes vorhandene Themenpaar hat ein Rollenprofil (Version 2, `~/.master-schalter/themenmodi.json`):
**Master** (`kontingent`, `claude`, `codex`, `hermes`), **Ausführer** (`workflow`, `claude`,
`codex`, `hermes`) und **Ausführermodell** (Kennung oder `Standard des Werkzeugs`; „Nach
Workflow“ erlaubt kein festes Modell, Hermes genau `deepseek/deepseek-v4.1-flash`). Im
Taskleistenmenü steht dafür unter **Arbeitsmodus je Thema** je Thema ein Untermenü
**Master**, **Ausführer** und **Ausführermodell**; die Optionen sind exakt `Nach Kontingent`/
`Claude Code`/`Codex`/`Hermes` bzw. `Nach Workflow`/`Claude Code`/`Codex`/`Hermes`. Damit sind
alle neun ausdrücklich gewählten Master-/Ausführer-Kombinationen möglich; `kontingent`/`workflow`
ist die Automatik. Alte v1-Dateien werden nur lesend als v2-Profil gedeutet (Migration erst beim
ersten ausdrücklichen Schreibvorgang); eine kaputte Datei fällt **nicht** still auf Automatik zurück.

Die Providerherkunft steht im Menü immer dabei: Claude Code aus dem Claude-Abo, Codex aus dem
ChatGPT-Abo, **Hermes über OpenRouter – kostenpflichtig**. Ein Providerwechsel des Ausführers
setzt das Modell ausdrücklich auf den Standard des Werkzeugs zurück und meldet das; ein
gespeichertes Modell wird nie still ersetzt.

Die Wahl ist eine **Rollen-/Ausführervorgabe**: Sie startet keine Sitzung, versendet keinen
Auftrag und erzeugt kein Empfangs-ACK. Menü und Häkchen kommen ausschließlich aus dem
Aktualisierungs-Snapshot; im Menüklick-/checked-Faden findet keine Datei-, Prozess- oder
Netzabfrage statt. Rollenänderungen laufen im Hintergrund mit nichtblockierender Themensperre;
Fehler werden gemeldet, blockieren aber weder Leiste noch andere Themen.

### Ausführermodell und Modellkataloge

Das Ausführermodell wird aus dem regulären Modellangebot der installierten Werkzeuge ermittelt
(Metadatencache `~/.master-schalter/modelle.json`, TTL 24 h, Hintergrundabgleich bei Leistenstart
und bei abgelaufenem Katalog, zusätzlicher Menüpunkt **Modelle aktualisieren**, Single-Flight):

- **Codex** meldet `models` (`slug`/`display_name`/`visibility`) über den reinen
  App-CLI-Metadatenaufruf `codex … debug models` (ohne Prompt, ohne Inferenz); übernommen werden
  nur Einträge mit `visibility=list`. Offizielle Quellen:
  <https://learn.chatgpt.com/docs/cli/reference> und <https://learn.chatgpt.com/docs/app-server>.
  Codex-Modelle laufen über das vorhandene ChatGPT-Abo.
- **Claude Code** meldet die Modelle über die lokale Control-Initialisierung **ohne Anmeldung und
  ohne Benutzerprompt**; übernommen werden ausschließlich `value`/`displayName` der eigenen
  passenden `control_response` (leerer `CLAUDE_CONFIG_DIR`, keine Sitzungs-, Konto- oder
  Rohantwortdaten im Cache). Aufgerufen wird direkt `node cli.js` (ältere npm-Pakete) oder das native
  `bin/claude.exe` (npm ab 2.1.3xx, auch `~/.local/bin/claude.exe`), nie ein `.cmd`-Wrapper.
  Claude-Modelle laufen über das Claude-Abo.
- **Hermes** nutzt fest `DeepSeek V4.1 Flash` über OpenRouter – **kostenpflichtig** (API-Kosten
  stehen im Prüfprotokoll); es gibt keinen automatischen Modellwechsel.

Grenzen (ehrlich, ohne Kontokatalog-Versprechen): Beide Kataloge sind **Werkzeugkataloge**, keine
Garantie einer freien Quote oder Kontoberechtigung. Der Claude-Katalog ist die begrenzte lokale
Werkzeugliste; die Grenze gegenüber personalisierten Bootstrap-/Cache-Erweiterungen bleibt offen.
Jede Abfrage ist zeitbegrenzt (30 s je Werkzeug, 65 s gesamt) mit festen Byte-/Zeilen-/
Modellgrenzen; eine Überschreitung ist ein Fehler statt einer abgeschnittenen Erfolgsliste.
Kindprozesse laufen ohne API-/Fremdprovider-Schlüssel, und bei Zeitüberschreitung/Abbruch wird nur
der selbst gestartete Prozessbaum beendet (`taskkill /PID <eigene PID> /T /F`, keine Suche nach
Programmnamen).

Fehler blockieren nichts: Ein fehlender, veralteter oder fehlerhafter Katalog wird im Menü
benannt; **neue** Modellwahlen daraus werden abgelehnt (CLI: `Modell nicht gesetzt`, Exit 1), die
gespeicherte Auswahl bleibt als „gespeichert, nicht bestätigt“ sichtbar und unverändert.
`Standard des Werkzeugs` bleibt bewusst wählbar. Nach einem erfolgreichen Abgleich gelingt
dieselbe Auswahl wieder.

### Abfrage vor jedem neuen Workerauftrag (verbindlich)

Vor jedem **neuen** bereinigten Workerauftrag liest der Master die verbindliche Vorgabe exakt so:

```powershell
.\.venv\Scripts\masterwechsel.exe profil <thema> --json
```

und startet den Worker mit dem dort genannten Anbieter samt Modell (Feld `worker` + `modell`;
Beispiel Codex: `-m <modell>`; heißt es `modell_standard: true`, gilt der Standard des
Werkzeugs). Die Profilwahl allein behauptet keinen gestarteten Worker; es gibt keinen
API-/OpenRouter-Fallback für den Codex-Worker.

Die Befehle im Überblick:

```powershell
.\.venv\Scripts\masterwechsel.exe profil THEMA [--json]
.\.venv\Scripts\masterwechsel.exe master-setzen THEMA kontingent|claude|codex|hermes
.\.venv\Scripts\masterwechsel.exe worker-setzen THEMA workflow|claude|codex|hermes
.\.venv\Scripts\masterwechsel.exe modell-setzen THEMA MODELL|standard
.\.venv\Scripts\masterwechsel.exe modelle [claude|codex] [--aktualisieren] [--json]
```

`modelle` zeigt ohne `--aktualisieren` nur den lokalen Cache (Exit 0, Fehlerkategorien stehen
in der Ausgabe); mit `--aktualisieren` wird frisch abgeglichen und ein nicht erfolgreich
ermittelter Katalog liefert Exit 1 mit klarer Diagnose. Alle Fehlertexte sind einfache eigene
Kategorien – niemals rohe Antworten der Werkzeuge.

Der frühere Hermes-Modus ist als Profil enthalten: `master=hermes`, `worker=codex`,
`modell=gpt-6-luna` (Legacy-Migration). Er bleibt eine Rollen- und Schutzregel: Hermes bleibt
Master und liest Sensibles; Codex erhält nur von Hermes bereinigte Code-, Test- und
Architekturaufträge. Status und tatsächliche Zustellung/Bestätigung werden getrennt angezeigt.

Beim Rückstellen auf `kontingent` werden offene alte Vorgänge entwertet. Die Besitzdatei erhält
`claude … modus-reset …` nur als Quelle des bestehenden Kontingentwegs; damit wird kein Claude-Chat
als gestartet behauptet. Der Status lautet **Kontingentbetrieb – Übernahme offen**. Ein Schreibfehler
zwischen den Teilschritten bleibt geschützt und lässt sich durch erneute Moduswahl vervollständigen.

### Bereinigter Codex-Code-Worker

Für das Personal-AI-Thema führt Hermes weiter. Nur ein geprüft bereinigter technischer Auftrag
geht an die installierte Codex-App-CLI mit dem **im Profil gewählten Modell** (Vorgabe:
`gpt-6-luna`) und der vorhandenen ChatGPT-Anmeldung. Hermes prüft vorher lokal `codex login
status`, behält davon nur die Anmeldeart `chatgpt` und gibt niemals die rohe Statusausgabe aus.
Bei fehlender ChatGPT-Anmeldung, Abo-Limit oder Fehler bleibt der Auftrag bei Hermes; es gibt
keinen API-/OpenRouter-Fallback, keine zusätzliche Abrechnung und keinen Masterwechsel.

```powershell
$CodexExe = 'C:\Users\sebas\AppData\Local\OpenAI\Codex\bin\e78bad9887fa50cf\codex.exe'
$WorkerWorktree = '<von Hermes bereitgestellter isolierter technischer Worktree>'
$PromptFile = '<bereinigter technischer Auftrag.md>'
$ResultFile = '<technisches Ergebnis.md>'
# Modell aus `masterwechsel profil <thema> --json` (Feld „modell“; bei modell_standard: true gilt der Werkzeugstandard)
$Modell = 'gpt-6-luna'
Get-Content -Raw -LiteralPath $PromptFile | & $CodexExe exec --json --ignore-user-config `
  -c model_provider=openai -c forced_login_method=chatgpt -m $Modell `
  --sandbox workspace-write -C $WorkerWorktree --output-last-message $ResultFile -
```

Der Auftrag wird per Standardeingabe übergeben, nicht in die Befehlszeile interpoliert. Hermes
entfernt API-Schlüsselvariablen nur aus der Kindprozess-Umgebung, protokolliert die Sitzungskennung
und die technische Ergebnisdatei und hält den Worker-Chat für Fortsetzungen verfügbar. Echte
Aufträge verwenden **kein** `--ephemeral`. Keine Bilder, Screenshots, Originaltexte, Zugangsdaten
oder privaten Originalpfade in Worktree oder Auftrag legen. Der Worker darf nur bereinigten Code,
Tests und technische Dokumente lesen. Kein Sandbox- oder Freigabe-Bypass.

Der Abo-Verbindungsbeleg war ein synthetischer ACK-only-Auftrag in leerem eigenem Verzeichnis mit
`gpt-6-luna`, bestätigter ChatGPT-Anmeldung, 90-Sekunden-Außenfrist und ohne API-Schlüsselfallback;
er belegt die CLI-Verbindung, nicht die erfolgreiche Ausführung eines echten Worker-Auftrags.

## Rückgabe an Codex (v0.3.2)

Der abgebende Master übergibt einzelne Themen an ihren Codex-Chat — manuell und bestätigt:

- **Im Menü:** „Master wechseln" → Codex → Bestätigungsdialog (nennt die aktiven Themen; Standard
  Nein). Nach dem Ja wechselt der Master und jedes aktive Thema bekommt eine Übergabenachricht in
  seinen Codex-Chat (Verweis auf die laufende Übergabedatei, Grenzen-Kurzliste, `ACK`-Bitte).
- **Per CLI:** `masterwechsel rueckgabe` zeigt ohne `--ja` nur, was passieren würde (Trockenlauf);
  mit `--ja` wird gewechselt und gesendet; `--erneut` erzwingt einen neuen Versand, auch wenn
  bereits übergeben wurde.
- **Regeln je Thema (fail-closed):** „Übergabebereit: nein" oder fehlende/ungültige Kopfzeile →
  nichts wird geschrieben oder gesendet. Bei „ja" wird die Kopfzeile beim bestätigten Senden auf
  den aktuellen HEAD und die aktuelle Zeit gezogen (die Nachricht nennt es); die strenge Prüfung
  der Automatik bleibt unverändert.
- **Besitz und ACK:** Die Reservierungszeile merkt den Vorzustand dauerhaft; jeder Abbruch vor dem
  Transportstart stellt ihn exakt wieder her (nie bleibt eine Waise). Eine aktive fremde
  Reservierung wird nie übernommen. Nach dem Versand zeigt das Menü „gesendet"; der Codex-Chat
  bestätigt mit `ACK <Kennung>`; „Aktualisieren" (und jede Messung) hakt das ab → „bestätigt".

## Start und Autostart (Taskleiste)

- Start ohne Konsole: `.venv\Scripts\pythonw.exe -m master_schalter.leiste`
- Abgekoppelter Starter (empfohlen; überlebt Terminal-Sitzungen, mit Protokoll und
  Doppelstart-Schutz): `%USERPROFILE%\.master-schalter\leiste_starten.cmd`.
  Protokolle: `leiste.log` (Fehler, u. a. Messfehler mit Zeitstempel) und `leiste-ausgabe.log`.
- Autostart: Verknüpfung im Startmenü-Startup-Ordner (`Master-Schalter-Leiste.lnk`) startet genau
  eine Leiste bei jeder Anmeldung.
- Nach tiefem Energiesparen kann das Taskleisten-Symbol verschwinden — Doppelklick auf den Starter
  genügt; die Erholung per Aufwach-Aufgabe ist als nächster Schritt vorgesehen.

## Woher die Zahlen kommen

Codex wird aus lokalen Sitzungsdateien gelesen. Claude wird über den OAuth-Usage-Endpunkt
gemessen und das Ergebnis lokal zwischengespeichert.

- **Codex** schreibt seine Kontingente in die eigenen Sitzungsdateien
  `~/.codex/sessions/**/rollout-*.jsonl` (Ereignis `token_count`, `limit_id: "codex"`).
  Gelesen werden nur Zeilen mit `"rate_limits"`; übernommen werden nur Zahlen — für den
  Verbrauch ausschließlich Werte von 0 bis 100 (negativ, über 100, nicht endlich oder fehlend
  heißt „unbekannt" und löst nie einen Versand aus). Neue Werte
  entstehen nur, wenn Codex arbeitet — deshalb steht immer „Stand" dabei. Ein Fenster, dessen
  Rücksetzzeit vorbei ist, wird im Kontingentmenü als „zurückgesetzt" angezeigt. Bis ein
  neuer Messwert vorliegt, zeigen Tooltip und Balken weiterhin 0 %; das ist ein bekannter
  Fehler. Die Lage wertet das Fenster als unbekannt und nennt den Grund.
- **Claude Code**: `masterwechsel claude-messen` fragt
  `https://api.anthropic.com/api/oauth/usage` ab und speichert nur die beiden geprüften
  Prozentwerte und Rücksetzzeiten in `~/.master-schalter/kontingent-claude.json`.
  Beim Start des Taskleistensymbols, nach „Aktualisieren" und standardmäßig jede Minute wird
  gemessen; `claude_takt_min` in `einstellungen.json` kann auf 1–60 Minuten gesetzt werden.
  HTTP 429 verschiebt weitere Versuche bis zum nächsten Erfolg auf fünf Minuten. Der Access-Token
  wird zur Laufzeit aus `~/.claude/.credentials.json` gelesen, nur im Speicher verwendet und nie
  gespeichert, protokolliert oder angezeigt. Der Refresh-Token wird nicht verwendet oder erneuert.
  **Bekannte Grenze:** Der OAuth-Usage-Endpunkt ist eine inoffizielle Schnittstelle und kann sich
  ändern — ab 16.10.2026 liefert er ein leeres Fenster als `utilization: 0.0, resets_at: null`; das
  wird seit v0.3.3 als **0 %** gelesen (mit Verbrauch > 0 bleibt eine fehlende Rücksetzzeit weiter
  ungültig). Bei abgelaufener Anmeldung bleibt der bisherige Messwert mit Stand erhalten; Claude Code
  muss einmal gestartet werden. Werte lassen sich weiterhin mit `masterwechsel claude-kontingent …`
  von Hand eintragen.

## Einrichten

```powershell
cd "02_Softwareentwicklung_IT\master-schalter"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[leiste,dev]"
```

Optionaler Ersatzweg: Die bestehende Statuszeile in Claude Code kann weiterhin Werte
schreiben (z. B. über `.claude/settings.local.json`):

```json
"statusLine": { "type": "command", "command": "\"<Pfad>/.venv/Scripts/masterwechsel.exe\" statuszeile" }
```

### Optional: Start bei der Windows-Anmeldung

Für einen Benutzer-Autostart kann eine eigene Verknüpfung im Windows-Ordner für
Benutzer-Startprogramme angelegt werden. `Win+R` drücken, `shell:startup` eingeben und
im geöffneten Ordner eine Verknüpfung mit diesen Eigenschaften erstellen:

- **Ziel:** `"<Projekt>\.venv\Scripts\pythonw.exe" -m master_schalter.leiste`
- **Ausführen in:** `<Projekt>` (der Ordner mit `pyproject.toml`)

`pythonw.exe` startet das Taskleistensymbol ohne Konsolenfenster. Zum Deaktivieren nur
die eigene Verknüpfung `Master-Schalter.lnk` aus diesem Benutzer-Startordner entfernen.
Das Programm bringt dafür kein eigenes Autostart-Menü und kein Einrichtungs-Skript mit;
die Verknüpfung wird von Windows ausgeführt. Die auf diesem Rechner eingerichtete
Benutzer-Verknüpfung benötigt keine Administratorrechte.

v0.3.0 führte die automatische Übergabe ein; die Automatik bleibt standardmäßig aus, bis sie per `masterwechsel automatik an` eingeschaltet wird (der frühere Menühaken ist in v0.3.2 entfallen).

## Benutzen

```powershell
# Taskleisten-Symbol ohne Konsolenfenster starten
.\.venv\Scripts\pythonw.exe -m master_schalter.leiste

# beide Kontingente in der Konsole
.\.venv\Scripts\masterwechsel.exe status

# Claude-Kontingent über die OAuth-API messen
.\.venv\Scripts\masterwechsel.exe claude-messen

# aktiven Master, Lage und Rollen anzeigen
.\.venv\Scripts\masterwechsel.exe master

# Master wechseln und technisches Übergabepaket schreiben
.\.venv\Scripts\masterwechsel.exe wechsel codex --hinweis "Nur technische Hinweise"

# Claude-Werte von Hand eintragen (Ersatzweg ohne Statuszeile)
.\.venv\Scripts\masterwechsel.exe claude-kontingent --fuenf 90 --woche 70 --reset-fuenf 2026-10-14T18:40:00Z --reset-woche 2026-10-18T21:00:00Z

# Rollenvorgabe eines Themas lesen (verbindlich vor jedem neuen Workerauftrag)
.\.venv\Scripts\masterwechsel.exe profil engineering --json

# Ausführer samt Modell vorgeben
.\.venv\Scripts\masterwechsel.exe worker-setzen engineering codex
.\.venv\Scripts\masterwechsel.exe modell-setzen engineering gpt-6-luna

# Modellkataloge anzeigen und frisch abgleichen
.\.venv\Scripts\masterwechsel.exe modelle
.\.venv\Scripts\masterwechsel.exe modelle codex --aktualisieren
```

Einstellungen: `~/.master-schalter/einstellungen.json`, z. B.
`{"schwelle": 90, "claude_takt_min": 5, "automatik": false}`. Die Schwelle liegt bei 1–100 (im
Taskleistenmenü 80, 90, 95, 97 oder 100; Standard 97), der Messungstakt bei 1–60 Minuten
(Standard 1), die Automatik ist ein Wahrheitswert (Standard aus). Die Paare liegen unter
`~/.master-schalter/paare.json`, die Vorgänge unter `~/.master-schalter/vorgaenge.json`.
Für Tests lassen sich die Ordner per Umgebungsvariable umlenken:
`MASTER_SCHALTER_DATEN`, `MASTER_SCHALTER_CODEX_SESSIONS`, `MASTER_SCHALTER_REPO`,
`MASTER_SCHALTER_CODEX`.

Der Datenordner liegt bewusst unter `%USERPROFILE%` und **nicht** unter `%LOCALAPPDATA%`:
Claude- und Codex-App sind MSIX-Pakete, deren Kindprozesse je Starter in
`AppData\Local\Packages\…` umgeleitet werden — dort läse jeder Starter einen anderen Zustand.

## Aufbau

```
src/master_schalter/
  zustand.py   Aktiven Master und letzten Wechsel lokal speichern; Sperren (global und je Thema)
  modi.py      Rollenprofile v2 je Thema (Master, Ausführer, Modell) und fail-closed Themenbesitz
  modelle.py   Modellkataloge der installierten Werkzeuge lesen/abgleichen (lokaler Metadatencache)
  rollen.py    Lage und Besetzung gemäß AGENTS.md bestimmen
  uebergabe.py Technische Metadaten als Übergabepaket schreiben (auch minimal, ohne Pläne)
  wechsel.py   Wechsel unter Themensperren ausführen: Paket, dann Zustand; Rückwechsel entwertet
  paare.py     Paare aus Thema, Codex-Chat und laufender Übergabedatei
  vorgaenge.py Vorgänge je Paar und Limitfenster (Phase, Kennung, Lauf-Kennung)
  besitz.py    Besitzmarkierung `<thema>.master` (claude / reserviert / codex)
  automatik.py Entscheidung (faellige) und Ablauf der Automatik unter der Themensperre
  codex_senden.py  Paket bauen und den Auftrag an `codex.exe queue` übergeben
  ack.py       Bestätigung des Zielchats aus den Rollout-Dateien lesen
  signale.py   Kontingente lesen und Claude-Messwerte sicher lokal speichern
  claude_messen.py  Claude OAuth-Usage messen und Werte validieren
  anzeige.py   Texte für Tooltip, Menü, Benachrichtigung; Schwelle und Automatikschalter
  symbol.py    Bild des Symbols (zwei Balken, Pillow)
  leiste.py    Taskleisten-Symbol (pystray) — nur Oberfläche
  cli.py       Befehlszeile `masterwechsel`
tests/         pytest, nur synthetische Dateien
```

Der Kern (`signale`, `anzeige`, `paare`, `vorgaenge`, `besitz`, `automatik`, `codex_senden`,
`ack`, `cli`) nutzt nur die Standardbibliothek; `pystray` und `Pillow` braucht nur die Oberfläche.

## Prüfbefehl

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Läuft auch automatisch im Git-Haken `.githooks/pre-commit`, sobald Code dieses Projekts
committet wird.

## Fahrplan

| Version | Inhalt |
|---|---|
| **v0.4.1** | Claude-Katalog mit nativem `claude.exe`; Tests unabhängig von der installierten Claude-Version — **dieser Stand** |
| v0.4.0 | Rollen und Ausführermodelle je Thema (Profil v2), dynamische Modellkataloge von Claude Code und Codex, Menü mit Master-/Ausführer-/Modellwahl und „Modelle aktualisieren", CLI `profil`/`master-setzen`/`worker-setzen`/`modell-setzen`/`modelle`, sichere Prozessbaumbereinigung, NT-Pfadpräfix-Härtung |
| v0.3.5 | Menüwechsel außerhalb des Traycallbacks; parallele und direkte Wechsel werden während Dialog und Wechsel unterdrückt |
| v0.3.4 | Arbeitsmodus je Thema, Hermes-Schutz, natives Codex-gpt-6-luna-Code-Worker-Protokoll |
| v0.3.3 | Claude-Messung versteht die neue API-Form (leeres Fenster `0.0/null` → 0 %); Prüfer-Rolle ohne Luna (Input-Preis 5x) |
| v0.3.2 | Rückgabe an Codex (manuell, mit Bestätigungsdialog), Menü aufgeräumt (Automatik-Haken entfällt, „Jetzt prüfen" in „Aktualisieren"), Startfestigkeit |
| v0.1.1 | Kontingentwerte nach Reset, Messalter und Anzeigegrenzen korrigieren |
| v0.1.0 | Kontingent-Anzeige beider Master |
| v0.3.0 | Automatische Übergabe Claude → Codex: Paare, sicherer Übergabepunkt, Handschlag, Sperren, ACK, Datenschutz-Paket (Sebastians Freigabe 15.10.; Abschnitt „v0.3.0 im Detail" des Plans). Standardmäßig aus. |
| v0.2.1 | Hermes als dritter Master wählbar (Zustand, Menü, CLI; ohne Balken) |
| v0.2.0 | Masteranzeige, Lage und Besetzung, Wechsel per Klick, technisches Übergabepaket, Menüschwelle |
| v0.3.1 | Hermes-Prüfsitzungen benennen, registrieren und nach Abschluss archivieren; Übergabepaket um Issues und Prüfrunden ergänzen |
| danach | Automatischer Rückweg Codex → Claude und weitere Ausbaustufen |
