# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Der Schalter zeigt außerdem den
aktiven Master, ordnet die Lage der Kaskaden-Matrix zu und legt beim Wechsel ein
technisches Übergabepaket bereit.

Stand: **v0.4.1** (veröffentlicht); in Arbeit ist **v0.5.0** mit dem Wechselassistenten samt Fenster (Abschnitt „Bedienung (v0.5.0)“) — Claude-Katalog findet das native `claude.exe` (npm-Paket ab 2.1.3xx ohne `cli.js`). Darunter v0.4.0: Rollen und Ausführermodelle je Thema (Profil v2): Master, Ausführer und Ausführermodell getrennt wählbar, dynamische Modellkataloge von Claude Code und Codex, neue CLI (profil/master-setzen/worker-setzen/modell-setzen/modelle). Hermes-Worker bleibt DeepSeek V4.1 Flash über OpenRouter (kostenpflichtig). Enthält die v0.3.5-Reparatur: bestätigter Menüwechsel läuft außerhalb des Traycallbacks; die native Ja/Nein-Bedienung auf dem Desktop ist weiterhin nicht nachgewiesen.

## Bedienung

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile mit Master, Lage und Kontingenten |
| Linksklick | Windows-Benachrichtigung mit beiden Mastern und Stand-Zeit |
| Rechtsklick | Menü (seit v0.5.0 nach Plan E9): Stand-Zeilen (Master, Lage, Kontingente), „Übergabe starten …", Zeilen offener Wechsel, „Aktualisieren", „Einstellungen ▸" und „Beenden". Die bisherigen Einstellpunkte liegen unter „Einstellungen ▸" (siehe „Bedienung (v0.5.0)“) |

Das Symbol besteht aus zwei Balken (links Claude, rechts Codex). Die Füllhöhe zeigt den
5-Stunden-Verbrauch: Grundfarbe bis 79 %, gelb ab 80 %, rot ab der Schwelle (Standard 97 %).
Die Anzeige wird standardmäßig jede Minute aktualisiert. Die Claude-Messung läuft beim
Start, nach „Aktualisieren" und anschließend im eingestellten Takt; dabei werden offene Übergaben
abgehakt (auch wenn die Automatik aus ist).

Im Menü „Einstellungen ▸ Standard-Master (übrige Themen)" (bis v0.4.1: „Master wechseln") kann Claude, Codex oder Hermes ausgewählt werden (Hermes = Lage 3 der
Kaskaden-Matrix; kein eigenes Abo-Kontingent, deshalb kein Balken und kein weißer Punkt). Jeder Wechsel
fragt vorher nach (Ja/Nein, Standard **Nein**); beim Ziel **Codex** werden danach zusätzlich alle aktiven
Themen an ihre Codex-Chats zurückgegeben (siehe „Rückgabe an Codex"). Der Wechsel legt ein Markdown-Paket
unter .hermes/uebergabe/ ab und zeigt den Paketnamen an. Themen mit Hermes-Schutz bleiben beim globalen Standardwechsel unberührt. Die Schwelle lässt sich im Menü „Einstellungen ▸ Wechsel-Schwelle"
auf 80, 90, 95, 97 oder 100 % setzen; sie steuert Lage und rote Anzeige. Die unbemannte Automatik
(Claude im Limit → Übergabe) läuft nur, wenn sie ausdrücklich eingeschaltet ist — per
`masterwechsel automatik an` (der frühere Menühaken ist in v0.3.2 entfallen).

## Bedienung (v0.5.0)

Der Wechsel „Thema X: alter Chat → neuer Chat" läuft über **ein Menü, ein Fenster und einen Takt in der Leiste**.
Alles Folgende gilt für den Entwicklungsstand auf Branch `v0.5.0-wechselassistent` (noch nicht veröffentlicht).

**Menü (Rechtsklick, Plan E9).** Oben die Stand-Zeilen wie bisher (Master, Lage, Kontingente). Darunter:
„Übergabe starten …" öffnet das Wechselfenster als eigenen Prozess; je offenem Wechsel steht eine
deaktivierte Zeile „Wechsel <thema>: <Phase>" (z. B. „wartet auf Abgabe", „liegt im Postfach"); dann
„Aktualisieren", „Einstellungen ▸" und „Beenden". Unter **Einstellungen ▸** liegen, in dieser Reihenfolge:
„Wechsel-Schwelle", „Modelle aktualisieren" (mit den Katalogzeilen), „Automatik je Thema" (bisher „Chats
übergeben", gleiche Funktion: Paar je Thema für die Automatik ein-/ausschalten), „Automatik-Weg" (zwei
Auswahlpunkte: „Alter Weg (direkt an Codex)" und „Über Wechselassistent", Standard alt; siehe „Automatische Übergabe"),
„Arbeitsmodus je Thema" und
„Standard-Master (übrige Themen)" (bisher „Master wechseln", gleiche Funktion samt Rückfrage). Das Menü liest
nur Momentaufnahmen; der Fensterstart läuft in einem eigenen Faden (`pythonw.exe` neben dem laufenden Python,
sonst dieses Python; `PYTHONPATH` zeigt auf das Paket).

**Fenster** (`python -m master_schalter.fenster`, `pythonw.exe -m master_schalter.fenster` oder
`masterwechsel fenster`). Es läuft **nur einmal**: eine zweite Instanz (Sperrdatei `fenster.lock` im Datenordner)
beendet sich still mit Exit 0 und holt das erste nicht nach vorn. Es liest alle 3 Sekunden im Hintergrund-Thread
neu (die Oberfläche bleibt im Tk-Thread; Tk ist in der Standardbibliothek). Vier Bereiche:

1. **Themen:** Thema · Ist-Master (Besitzer der Marke) · Kopfzeile `ja`/`nein` mit Alter · Automatik an/aus.
2. **Übergabe starten:** Thema, Ziel (Claude/Codex/Hermes), **Von-Chat** (Chats des aktuellen Masters) und
   **Nach-Chat** (Chats des Ziels), je als `Titel · zuletzt hh:mm · arbeitet/ruht/unbekannt`, zuletzt aktive
   zuerst; dazu die Einträge „ohne alten Chat (Abgabe überspringen)" und „ohne (nur Rolle setzen)". Vorbelegt wird
   der jüngste Chat, dessen Vorschlag (`chat_zuordnung`) auf das Thema lautet. **Ohne Vorschlag bleibt das Feld
   bewusst leer**: der Knopf „Übergeben" verlangt dann eine ausdrückliche Wahl (auch für „ohne …"), damit die
   Abgabe nicht versehentlich übersprungen wird. Eine bewusste Wahl bleibt beim Aktualisieren erhalten. „Übergeben"
   zeigt die Zusammenfassung in einer Zeile und fragt per Ja/Nein-Dialog (Standard **Nein**); erst nach dem Ja läuft
   `assistent.uebergeben` im Hintergrund, Fehler erscheinen bereinigt im Fenster. Wird ein **Codex-Chat** gewählt,
   der vom Vorschlag abweicht, wird er nach dem Anlegen als Paar des Themas gemerkt
   (`chat_zuordnung.bestaetigen`; so lernt der Vorschlag; Claude-/Hermes-Chats werden nicht gemerkt).
3. **Vorgänge:** alle offenen und die letzten 10 abgeschlossenen, mit Phase in Klartext und einem **ehrlichen
   Zustellhinweis (E8)** – nie „zugestellt" ohne Beleg:
   Codex + `gesendet` → „Codex: zugestellt (Queue)"; Claude + `im_postfach` → „liegt im Postfach, kommt mit der
   nächsten Eingabe/dem nächsten Werkzeugschritt in diesem Chat"; Hermes + `im_postfach` → „noch kein automatischer
   Empfang – Text unten kopieren und im Hermes-Chat einfügen" (Knopf **Text kopieren**, der Text steht im Feld
   darunter); offene Abgabe → „wartet auf Abgabe des alten Chats (Frist läuft noch m:ss)", ist Hermes der alte Chat,
   mit dem Zusatz zum manuellen Kopieren des Abgabe-Auftrags; `im_chat` → „Quittung offen"; `bestaetigt` →
   „übernommen ✓"; `verworfen`/`fehler`/`unklar` → der Grund. Knöpfe: **Jetzt weiter** (ein Takt für diesen Vorgang,
   `assistent.fortsetzen`) und **Abbrechen** (nur **vor** `rolle_gesetzt`, mit Rückfrage; setzt den Vorgang auf
   `verworfen` / „von Hand abgebrochen", Vergleich-und-Setzen unter der Themensperre, mit Protokolleintrag;
   Rolle und Marke bleiben unberührt, liegende Postfachdateien werden nach G5 ungültig).
4. **Protokoll:** die letzten 50 Einträge, neueste oben, aus einer Tabelle in Klartext übersetzt – ohne Vorgangs-ID,
   Kennung, Titel oder freien Text.

Chat-Titel, Ordner und Kennungen erscheinen **nur in diesem lokalen Fenster** (G9), nie in Nachrichten, im
Protokoll, in Logs oder Windows-Hinweisen.

**Takt in der Leiste.** Ein eigener leichter Faden (alle 10 Sekunden, `leiste.ASSISTENT_TAKT_SEKUNDEN`), unabhängig
vom 60-Sekunden-Messtakt, ruft `assistent.fortsetzen` für jeden nicht endgültigen Vorgang (Frist, Rolle setzen,
zustellen; mehrfaches Aufrufen sendet nie doppelt). Fehler stehen nur mit ihrer Klasse im Log und beenden nichts.
Ändert sich eine Phase (auch durch ein anderes Programm), wird das Menü neu gebaut. Beim Start der Leiste ordnet
`assistent_vorgaenge.wiederaufnehmen()` Absturzreste einmal ein; im Log stehen nur Zähler je Status.

**Windows-Hinweise** (je Vorgang und Ereignis genau einmal; der Merker liegt nur im Speicher, nach einem Neustart
der Leiste kann ein Hinweis also noch einmal kommen – Vorgänge, deren letzte Änderung länger als 15 Minuten
zurückliegt, melden nichts mehr): „<thema>: alter Chat hat noch nicht abgegeben – bitte kurz anstoßen (Frist bis
hh:mm)" (Abgabe länger als 2 Minuten offen), „<thema>: Rolle jetzt bei <Ziel>", „<thema>: <Ziel> hat übernommen ✓"
und „<thema>: Wechsel braucht Blick ins Fenster" bei `fehler`, `unklar` oder `verworfen` (ein von Hand
abgebrochener Vorgang meldet nichts). Ein „übernommen" macht das „Rolle jetzt bei …" desselben Vorgangs überflüssig.

**Was heute noch nicht geht (ehrlich):**
- **Hermes** hat noch **keinen automatischen Empfang** (P6): Nachrichten an Hermes liegen im Postfach und müssen
  über „Text kopieren" von Hand in den Hermes-Chat eingefügt werden; die Quittung (`masterwechsel quittieren`)
  macht der Hermes-Chat selbst.
- **Neue Sitzungen werden nicht gestartet.** Der Assistent übergibt nur an **vorhandene** Chats; das Anlegen neuer
  Claude-/Codex-/Hermes-Sitzungen (S0b/S0c/P5) ist offen.
- Der Claude-Hook ist noch nicht in eine `settings.json` eingetragen (siehe „Claude-Empfang"); bis dahin kommt auch
  eine Postfachnachricht an Claude nicht im Chat an.
- Der Ruhenachweis (G8b) ist noch nicht gebaut: der „Status" der Chats (`arbeitet`/`ruht`/`unbekannt`) ist nur eine
  Anzeige und steuert keine Entscheidung; ohne Statusdatei steht „unbekannt", nie „ruht".

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
Der **Rückweg bleibt manuell** („Einstellungen ▸ Standard-Master → Claude"): er entwertet offene Vorgänge
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

### Zwei Wege für den Versand (v0.5.0, K7)

Entscheidung (`faellige`: Automatik an, Claude frisch im Limit, Codex gemessen frei, Paar aktiv, feste Masterrolle
ausgenommen) und alle Schutzschritte (Modus `kontingent`, Kopfzeile `ja` mit passendem HEAD, Reservierung, 30 s
Wartezeit, erneute Prüfung, Reservierung noch die eigene) sind für beide Wege **gleich**. Nur der letzte Schritt
unterscheidet sich; gewählt wird er mit der Einstellung `automatik_weg` in `einstellungen.json`:

| Weg | Wirkung |
|---|---|
| `alt` (**Standard**; auch bei unbekanntem oder kaputtem Wert) | wie bisher: `codex_senden.senden` schreibt den Vorgang in `vorgaenge.json`, stellt per `codex.exe queue` zu, Bestätigung über `ACK <kennung>` |
| `assistent` | `assistent.uebergeben(thema, "codex", von_chat=None, nach_chat=<Paar-Chat>)`: ein Wechselvorgang in `assistent.json` wie bei einem Klickwechsel (Fenster, Protokoll, Windows-Hinweise, Quittung); den Vorgang führt danach der 10-s-Takt der Leiste weiter |

Beim Weg `assistent` gilt zusätzlich: Die Kennung `<thema>@<Rücksetzzeit>` wird **vor** dem Aufruf dauerhaft in
`~/.master-schalter/automatik_ausgeloest.json` vermerkt – es gibt höchstens einen Versuch je Paar und Limitfenster,
auch wenn der Assistent danach scheitert (`faellige` behandelt vermerkte Kennungen wie bekannte Vorgänge, für beide
Wege). Lässt sich der Vermerk nicht schreiben, wird nichts ausgelöst und die Reservierung zurückgegeben. Die
Reservierung geht vor dem Aufruf zurück auf `claude <Zeit>` (Vorzustand für den Assistenten). Der Aufruf geschieht
**nach** dem Verlassen der Themensperre (der Assistent nimmt sie selbst). Es gibt keinen alten Chat, weil Claude im
Limit nicht antworten kann; der Übergabepunkt ist die geprüfte Kopfzeile. Fehler des Assistenten erscheinen mit
festem Text („Wechsel nicht gestartet (<Fehlerklasse>)"), nie mit fremdem Text; das Protokoll erhält „Automatik
ausgelöst" bzw. „Automatik: Wechsel nicht gestartet" (ohne Kennungen außer der Vorgangs-ID). Menü und Statuszeile
nennen den Weg („bereit · über Wechselassistent"). Offene Vorgänge des alten Weges prüft weiter
`bestaetigungen_pruefen`; neue Wechselvorgänge sind davon nicht betroffen.

```powershell
# Weg anzeigen oder setzen (ohne Argument: anzeigen)
.\.venv\Scripts\masterwechsel.exe automatik-weg
.\.venv\Scripts\masterwechsel.exe automatik-weg assistent
.\.venv\Scripts\masterwechsel.exe automatik-weg alt
```

Im Menü: „Einstellungen ▸ Automatik-Weg". Der Weg wechselt nur per Klick bzw. Befehl.

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

- **Im Menü:** „Einstellungen ▸ Standard-Master (übrige Themen)" → Codex → Bestätigungsdialog (nennt die aktiven Themen; Standard
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

## Wechselassistent (v0.5.0, in Arbeit)

Der Klickwechsel „Thema X: alter Chat → neuer Chat“ läuft ohne Tippen. Es gibt den Ablauf als Code und als
Befehle (`uebergeben`, `fortsetzen`, `quittieren`), das Fenster und den Takt in der Leiste (siehe „Bedienung
(v0.5.0)“). Der Empfang im Hermes-Chat (P6) ist noch nicht gebaut, der im Claude-Chat nur als Hook ohne Eintrag.

- **Reihenfolge (G8):** erst gibt der **alte** Master ab, dann wird die Rolle gesetzt, dann bekommt der
  **neue** Master seine Nachricht. Phasen in `assistent.json` (getrennt von `vorgaenge.json`):
  `vorbereitet` → `abgabe_sende` → `abgabe_angefragt` (`abgabe_unklar` / `abgabe_fehler`) →
  `abgegeben` oder `abgabe_uebersprungen` → `rolle_gesetzt` → `sende` → `gesendet` (Codex) bzw.
  `im_postfach` (Claude/Hermes) bzw. `fehler` / `unklar` → `im_chat` → `bestaetigt`; außerdem
  `verworfen`. Jede Phase, vor der etwas gesendet wird, steht **vorher** auf der Platte
  (Write-ahead); ein Absturz dazwischen gilt als „unklar“, es wird nie automatisch neu gesendet.
- **Chat-Referenz:** `WERKZEUG:KENNUNG` mit Werkzeug `claude`, `codex` oder `hermes` und einer
  Kennung aus `A–Z a–z 0–9 _ -` (1–80 Zeichen). Die Kennungen stehen **nur** in `assistent.json`
  (Felder `von_chat`, `nach_chat`) – nie in Nachrichtentexten, im Protokoll oder in Befehlsausgaben.
  Der alte Chat muss zum aktuellen Besitzer der Marke passen, der neue zur Zielrolle; sonst lehnt
  `uebergeben` ab, ohne etwas zu ändern.
- **Zustellwege:** Codex bekommt die Nachricht über `codex.exe queue --thread <Kennung> --message
  <Text>` (Argumentliste, keine Shell, 60 s). Nur ein belegtes Nicht-Starten (Programm nicht
  gefunden, Startfehler) ist `abgabe_fehler` bzw. `fehler`; Rückgabewert ≠ 0, Zeitüberschreitung oder
  jede andere Ausnahme ist `abgabe_unklar` bzw. `unklar`. Claude und Hermes bekommen eine kleine Datei
  im Postfach (`postfach/<ziel>/<kennung>/<vorgang>_<art>.json`). **Ehrlich:** Ein Claude-Chat kann das
  Postfach über den Hook abholen (siehe „Claude-Empfang“), der aber noch nicht eingetragen ist; für
  Hermes gibt es noch keinen Weg (kommt mit P6) – die Dateien liegen bis dahin bereit. Transporte laufen nie unter der Themen- oder Dateisperre; so kann Codex
  nach `masterwechsel quittieren <id> abgabe` schon quittieren, bevor der Rückgabewert da ist (die
  Phase bleibt dann `abgegeben`).
- **Frist:** Hat der alte Master nach 10 Minuten (`ABGABE_FRIST`, ab `abgabe_sende`) nicht
  quittiert – auch nach `abgabe_fehler` –, wird die Abgabe übersprungen (`abgabe_uebersprungen`,
  Grund „Frist abgelaufen“). Die Frist setzt nur die Phase und sendet nichts. Die Info „Du führst das
  Thema nicht mehr“ geht an den alten Chat erst, nachdem das Rollensetzen den Wechsel nach
  `rolle_gesetzt` **gewonnen** hat, und nur bei übersprungener Abgabe mit gesetztem alten Chat; ein
  Codex-Transport läuft außerhalb jeder Sperre, die Postfach-Info kurz unter der Themensperre.
  Unmittelbar vor dem Senden wird geprüft, dass der Vorgang nicht `verworfen` ist und die Marke noch
  genau diesen Wechsel trägt (`<Ziel> … assistent <Thema> <Vorgang>`); nach einem schnellen Rückwechsel
  entfällt die Info (Protokoll `info_entfallen`, Codex und Postfach). Der Infotext ergänzt: „Maßgeblich ist
  die Besitzmarke; prüfe im Zweifel `masterwechsel profil <Thema>`.“ (`profil` zeigt die gespeicherte
  Masterrolle des Themas, die zusammen mit der Marke gesetzt wird – nicht den Markentext selbst.)
  Scheitert das Rollensetzen oder ist die Sperre belegt, bleibt die Info aus. Stürzt das Programm
  zwischen `rolle_gesetzt` und der Info ab, geht sie verloren (sie wird nie nachgesendet); ein Fehler
  beim Senden steht nur im Protokoll. Ohne alten Chat wird sofort
  übersprungen („kein alter Chat gewählt“). Der neue Master bekommt dann zusätzlich den Satz, dass
  die Abgabe fehlte und er zuerst `git status` und die Kopfzeile der laufenden Übergabe prüfen soll
  (im Postfach wird er beim Abholen aus dem Vorgang abgeleitet, die Datei bekommt kein neues Feld).
  Das Überspringen per Ruhenachweis (G8b) kommt erst mit dem Statusregister (P3/P6).
- **Stand geändert:** Vor dem Rollensetzen muss der Markentext noch dem Vorzustand des Vorgangs
  entsprechen; hat jemand zwischendurch gewechselt, wird der Vorgang `verworfen` („Stand geändert“),
  ohne zuzustellen. Gleiches gilt, wenn nach dem Rollensetzen ein späterer Wechsel die Marke
  überschreibt. Die Marke des Wechsels lautet `<Rolle> <Zeit> assistent <Thema> <Vorgang-ID>`.
  Markenprüfung und der Gewinn von `sende` laufen gemeinsam unter der Themensperre (blockierend, kurze
  Frist; ist sie belegt, tut der Takt nichts und versucht es später erneut), damit ein zweiter Wechsel
  nicht dazwischen seine Marke schreiben kann und kein veralteter Übernahmeauftrag rausgeht. Der Transport
  läuft danach außerhalb jeder Sperre; direkt davor wird die Marke außerhalb der Sperre **noch einmal**
  geprüft – passt sie nicht mehr, wird nichts gesendet und der Vorgang aus `sende` auf `verworfen` gesetzt
  (Protokoll `neu_entfallen`; ist die Marke nicht lesbar, endet er auf `fehler`).
  **Restfenster, ehrlich:** Ein Transport unter der Sperre bleibt verboten (G8d), und auch nach dem Senden
  kann jemand wechseln. Zwischen dieser letzten Prüfung und dem Start des Transports bleibt deshalb ein
  kleines Fenster; die Gültigkeit erzwingt die Quittung (`masterwechsel quittieren <id> neu` prüft die
  Marke, G5) bzw. die Besitzmarke selbst. Darum sagt der Text an den neuen Master: „Schlägt die Quittung
  fehl, beginne keinen Schritt – die Nachricht gilt dann nicht mehr.“ (Codex und Postfach). Solange ein **anderer** Vorgang desselben Themas in `sende` steht,
  setzt `fortsetzen` die Rolle nicht; die Nachricht des alten Vorgangs geht erst vollständig raus (bleibt er
  nach einem Absturz in `sende` hängen, macht `wiederaufnehmen` daraus `unklar`).
- **Doppelklick-Schutz und „überholt“:** `uebergeben` nimmt die Themensperre nicht blockierend; ist sie
  belegt, meldet es „Thema gerade belegt“. Ein neuer Wechsel desselben Themas wird nur abgelehnt
  („Wechsel läuft bereits“), solange ein Vorgang die Rolle noch nicht gesetzt hat oder gerade sendet
  (`av.WECHSEL_BLOCKIEREND`: `vorbereitet`, `abgabe_sende`, `abgabe_angefragt`, `abgabe_unklar`,
  `abgabe_fehler`, `abgegeben`, `abgabe_uebersprungen`, `sende`). Die Abgabephasen lösen sich nach
  spätestens 10 Minuten über die Frist; ein nach Absturz hängendes `sende` macht `wiederaufnehmen`
  zu `unklar`. Ab `rolle_gesetzt` blockiert ein Vorgang nicht mehr: setzt ein späterer Wechsel
  erfolgreich seine Rolle, werden alle anderen Vorgänge des Themas in `rolle_gesetzt`, `gesendet`,
  `im_postfach`, `im_chat`, `unklar` und `fehler` in einem Schritt unter der Themensperre auf
  `verworfen` mit Grund „überholt“ gesetzt (Protokolleintrag je Vorgang); ihre Postfachdateien liefert
  `postfach.abholen` danach nicht mehr aus.
- **Wiederaufnahme:** `assistent_vorgaenge.wiederaufnehmen` zeigt `abgabe_fehler` als `abgabe_offen`
  (Hinweis: Frist läuft, danach wird übersprungen); es sendet nie.
- **Befehle:**
  - `masterwechsel uebergeben THEMA ZIEL [--von WERKZEUG:KENNUNG] [--nach WERKZEUG:KENNUNG]` – legt
    den Vorgang an, schickt den Abgabe-Auftrag und ruft einmal `fortsetzen` auf; gibt nur Vorgangs-ID
    und Phase aus. Ohne `--von` wird die Abgabe übersprungen, ohne `--nach` nur die Rolle gesetzt.
  - `masterwechsel fortsetzen [VORGANG]` – der idempotente Takt (Frist prüfen, Rolle setzen, zustellen);
    ohne ID für alle nicht endgültigen Vorgänge, je Zeile ID, Thema und Phase. Mehrfaches Aufrufen
    sendet nie doppelt (Vergleich-und-Setzen der Phase; wer verliert, sendet nicht). Die Leiste ruft es alle
    10 Sekunden für jeden offenen Vorgang.
  - `masterwechsel quittieren VORGANG neu|abgabe` – Quittung des Zielchats bzw. des alten Chats.
  - `masterwechsel fenster` – das Wechselfenster öffnen (nur eine Instanz).
  - Abbrechen von Hand gibt es als Knopf im Fenster (`assistent_vorgaenge.abbrechen`), nicht als Befehl.
- **Protokoll (G10):** `protokoll.jsonl` im Datenordner, je Entscheidung eine Zeile mit Zeit, Vorgang,
  Thema, Entscheidung und Grund: angelegt, Abgabe-Zustellweg und -Ergebnis, Abgabe übersprungen,
  Info gesendet/fehlgeschlagen, Rolle gesetzt, verworfen, Zustellweg und Ergebnis der Nachricht an
  den neuen Master. Keine Kennungen, Titel oder Inhalte; Schreibfehler werden geschluckt. Auch
  Ausnahmetexte kommen nicht hinein (sie können Pfade enthalten): bei Fehlern im Ablauf steht nur die
  Fehlerklasse, und die `AssistentFehler` aus Rollensetzen und Markenprüfung nennen ebenfalls nur die
  Fehlerklasse (die Ursache hängt an `__cause__`). Der Verwerfungsgrund bei überholter Marke ist ein fester Text.
- **Fehlermeldungen ohne Pfade:** Alle `AssistentFehler` in `assistent.py`, die aus einer fremden Ausnahme
  entstehen, laufen über eine Hilfsfunktion. Steckt ein `OSError` in der Ausnahmekette (`__cause__` /
  `__context__`), lautet der Text fest „Besitz- oder Datendatei nicht lesbar (<Fehlerklasse>)“, bei einem
  `SperrFehler` „Sperre gerade belegt (SperrFehler)“. Ohne `OSError`-Ursache steht nur die Fehlerklasse
  (z. B. „Wechsel nicht gestartet (ModusFehler)“) – fremde Ausnahmetexte werden **nie** übernommen. Lesbare
  Prüftexte wie „Thema unbekannt (kein vorhandenes Paar): <thema>“ erzeugt `uebergeben` selbst, bevor fremder Code läuft.
  Ungeprüfte Eingaben (Thema, Vorgangs-ID) werden nie wiederholt: Meldungen nennen nur das erlaubte Muster,
  `fortsetzen` in der CLI zeigt eine ungültige ID als „ungültige Kennung“; ein `OSError` erscheint in der CLI
  nur mit seiner Klasse. Dasselbe gilt für `quittieren` (dessen Ausgabe im quittierenden Chat landet): die
  Ablehnung einer veralteten Quittung nennt nur „Marke gehört nicht mehr zu diesem Vorgang“. `ZIEL` und `ART`
  prüft das Programm selbst (keine argparse-Auswahlliste, die die Eingabe wiederholen würde).
  `modi.py` ist unverändert, seine Texte (mit Pfad) erreichen weder die CLI noch das Protokoll.
  Das gilt für **jede** Ausnahme, die `uebergeben` oder `fortsetzen` verlässt: nach dem Anlegen ist der ganze
  Ablauf (Abgabe-Transport, `abgabe_ergebnis`, Protokoll- und Vorgangsaufrufe) umschlossen und liefert nur
  einen bereinigten `AssistentFehler`. Scheitert dabei `abgabe_ergebnis`, bleibt die Phase `abgabe_sende`
  stehen – richtig so: `wiederaufnehmen` macht daraus `abgabe_unklar`, es wird nie neu gesendet.

## Claude-Empfang (Hook, v0.5.0)

`python -m master_schalter.claude_hook` ist ein Command-Hook für Claude Code. Claude Code gibt das Ereignis als
JSON auf stdin; das Modul liest höchstens 1 MB und wertet nur `hook_event_name` und `session_id` aus.

- **`UserPromptSubmit` und `PostToolUse`:** meldet den Status `arbeitet` und holt mit
  `postfach.vormerken("claude", session_id)` die Nachrichten dieser Sitzung vor (Übernahme-Auftrag `neu`,
  Abgabe-Auftrag, Abgabe-Info – mit den Gültigkeitsregeln aus dem Abschnitt Wechselassistent). Gibt es
  Nachrichten, schreibt der Hook genau ein JSON auf stdout:
  `{"hookSpecificOutput": {"hookEventName": "<Ereignis>", "additionalContext": "<Text>"}}`. Der Text besteht
  aus der festen Einleitung „Nachricht des Master-Schalters:“ und den festen Postfachtexten, je Zeile einer.
  Er enthält nur Thema, Vorgangs-ID und den repo-relativen Pfad der laufenden Übergabe – nie die
  Sitzungskennung oder einen absoluten Pfad. Ohne Nachricht gibt es **keine** Ausgabe.
- **`Stop`:** setzt nur den Status `ruht`. Der Hook blockiert nie; es gibt kein `decision: block`.
- **Andere Ereignisse:** nichts.
- **Ausgabe vor Zustellung:** Das Postfach kennt zwei Schritte. `postfach.vormerken` prüft wie bisher
  (verwerfen, liegen lassen, zustellen), verschiebt aber nichts. Der Hook schreibt und leert seine Ausgabe
  und ruft **erst danach** `postfach.bestaetigen` auf: Es liest jede Datei unter der Themensperre erneut
  (geänderte oder fehlende Dateien werden übergangen) und trifft dieselbe Entscheidung wie früher `abholen`
  noch einmal: zustellen (nach `erledigt/`, Zustellung vermerken), verwerfen (nach `verworfen/` mit Grund)
  oder liegen lassen. Gültigkeitsprüfung und Zustellung sind so wieder ein Schritt unter der Themensperre
  (G5). **Grenze:** Wird eine Nachricht erst nach der Ausgabe ungültig (Master gewechselt), steht sie schon
  im Chat; der Vorgang wird aber nicht `im_chat`, und die Quittung schlägt fehl – der Text sagt für diesen
  Fall „Schlägt die Quittung fehl, beginne keinen Schritt“. Scheitert die Ausgabe oder stürzt der Hook dazwischen ab, liegt die
  Datei weiter bereit und die Nachricht kommt beim nächsten Ereignis **noch einmal** – gewollt: lieber doppelt
  als verloren. Gültig bleibt sie nur über die Quittung (`masterwechsel quittieren`, G5). Zwei gleichzeitige
  Hooks können dieselbe Datei vormerken (beide geben dann aus); bestätigen kann sie nur einer.
  `postfach.abholen` ist weiterhin `vormerken` + `bestaetigen` in einem Zug.
- **Abholen ist keine Übernahme:** `neu` setzt den Vorgang auf `im_chat`; übernommen ist erst, was der Chat
  mit `masterwechsel quittieren <id> neu` bestätigt.
- **Statusregister (K2):** `<datenordner>/status/claude-<kennung>.json` mit `zustand` (`arbeitet` | `ruht`),
  `zeit` (ISO, UTC) und `ereignis`; atomar geschrieben. `arbeitet` wird nur geschrieben, wenn der Zustand
  vorher ein anderer war oder die gespeicherte Zeit mindestens 60 s zurückliegt (Schutz vor Schreiblast bei
  vielen `PostToolUse`); `ruht` immer. `status.lesen(werkzeug, kennung)` liefert `(zustand, zeit)` oder `None`
  für „unbekannt“ (Datei fehlt oder ist kaputt) – für den späteren Ruhenachweis (G8b), der heute noch nicht
  gebaut ist.
- **Fehlerverhalten (K3):** kaputtes JSON, fehlende oder unzulässige `session_id` (Muster `A–Z a–z 0–9 _ -`,
  1–80 Zeichen), belegte Sperre, `OSError`, Importfehler oder jede andere Ausnahme enden mit Exit 0, ohne
  Ausgabe und ohne Ausgabe auf stderr; der Chat wird nie blockiert. Das Prozessende ist hart
  (`os._exit(0)` nach einem letzten `flush`): scheiterte ein `flush()` an geschlossenem stdout, würde der
  Interpreter beim normalen Beenden erneut leeren und mit Meldung auf stderr und Exit 120 enden. Auf
  Modulebene importiert `claude_hook`
  nur die Standardbibliothek; `modi`, `status` und `postfach` werden innerhalb des Fehlerschutzes geladen
  (`master_schalter/__init__.py` enthält nur Docstring und `__version__`). Fehlt allein das Statusregister,
  wird trotzdem zugestellt. Eine belegte Sperre lässt die Nachricht liegen, sie kommt beim nächsten Ereignis.
  Existiert der Postfachordner der Sitzung nicht, wird nichts weiter gelesen. Das Repo bestimmt wie sonst
  `MASTER_SCHALTER_REPO` bzw. der Ordner, in dem das Paket liegt (das `cwd` des Ereignisses wird nicht benutzt).
- **Laufzeit-Obergrenze:** Der Hook wartet auf Sperren (Themensperre, Dateisperre von `assistent.json`) nur
  `SPERRFRIST` = 0,3 s (ohne diese Angabe gelten die bisherigen 1 s bzw. 5 s). Dazu gibt es Zeitbudgets: das
  Vormerken fasst nach `VORMERK_BUDGET` = 0,6 s keine weitere Datei mehr an, das Bestätigen nach
  `BESTAETIGEN_BUDGET` = 0,4 s ebenfalls nicht (eigenes Budget, damit Ausgegebenes möglichst bestätigt wird).
  Nicht angefasste Dateien bleiben liegen und kommen beim nächsten Ereignis. Eine einzelne Datei kann ein
  Budget um höchstens die Sperrfristen überschreiten. `postfach.vormerken`, `bestaetigen` und `abholen`
  nehmen dafür die optionalen Parameter `frist` (Sekunden je Sperre) und `bis` (Zeitpunkt nach
  `time.monotonic()`); ohne Angabe bleibt das bisherige Verhalten. Ist beim Bestätigen die Dateisperre
  belegt, ist die Ausgabe schon erfolgt, die Datei bleibt aber liegen und die Nachricht kommt noch einmal.
- **Laufzeit:** gemessen etwa 0,8 bis 1,0 s je Aufruf als eigener Prozess (Windows, venv-Python); davon rund
  0,28 s das Importieren des Moduls samt `modi`. Ziel unter 2 s.

**Ehrlich: Der Hook ist noch nicht eingetragen.** Bis jemand ihn in eine `settings.json` einträgt, holt kein
Claude-Chat das Postfach ab, und es wird kein Status geschrieben. Der Eintrag erfolgt bewusst erst nach
ausdrücklichem OK. Beispiel (nur Doku; Pfad des venv-Pythons anpassen):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {"hooks": [{"type": "command",
                  "command": "\"C:/Pfad/zu/master-schalter/.venv/Scripts/python.exe\" -m master_schalter.claude_hook"}]}
    ],
    "PostToolUse": [
      {"matcher": "*",
       "hooks": [{"type": "command",
                  "command": "\"C:/Pfad/zu/master-schalter/.venv/Scripts/python.exe\" -m master_schalter.claude_hook"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command",
                  "command": "\"C:/Pfad/zu/master-schalter/.venv/Scripts/python.exe\" -m master_schalter.claude_hook"}]}
    ]
  }
}
```

## Chatliste (v0.5.0, in Arbeit)

Das Programm kennt die in den letzten 24 Stunden benutzten Chats von Claude Code, Codex und Hermes
und schlägt jedem ein Projekt (Thema) vor. Das Fenster nutzt das Register für die Auswahl von Von- und
Nach-Chat; außerdem gibt es den Befehl `chats`.

- **Quellen** (je einzeln fehlertolerant; Pfade über Umgebungsvariablen umlenkbar):
  `claude-desktop` (`%LOCALAPPDATA%/Claude-Data/*/claude-code-sessions/**/local_*.json`, höchstens
  256 KB je Datei), `claude-cli` (`~/.claude/projects/*/<uuid>.jsonl`, nur direkte Kinder; Zeit =
  Dateiänderung; ergänzt nur Kennungen, die `claude-desktop` nicht liefert), `codex`
  (`~/.codex/state_5.sqlite`, Tabelle `threads`) und `hermes` (`$HERMES_HOME/state.db` bzw.
  `%LOCALAPPDATA%/hermes/state.db`, Tabelle `sessions`; nur Quellen `cli`, `desktop`, `telegram`,
  `api_server`). Bei Codex zählen nur Sebastians Chats (`thread_source = user`), keine automatischen
  Prüf- oder Subagenten-Threads. Eine in Claude Desktop archivierte Sitzung kommt auch über
  `claude-cli` nicht zurück; Desktop-Sitzungen ohne `cliSessionId` erscheinen nicht (sie können
  noch keine Nachricht über den Claude-Hook empfangen). Zeiten mehr als 5 Minuten in der Zukunft
  werden verworfen. Status je Quelle: `ok`, `fehlt`, `gesperrt`, `schema unbekannt`,
  `nicht lesbar: <Fehlerart>` (nie mit Pfad oder Ausnahmetext).
- **Nur Metadaten, nur lesend:** Kennung, Titel, Arbeitsordner und Zeit der letzten Nutzung.
  Nachrichten werden nicht gelesen (bei den `jsonl`-Dateien wird nur geparst, was `"custom-title"`
  oder `"ai-title"` enthält; die Tabelle `messages` wird nie abgefragt). SQLite-Dateien werden
  ausschließlich mit `mode=ro` und ausdrücklicher Spaltenliste geöffnet; passt das Schema nicht,
  meldet die Quelle „schema unbekannt“. Titel, Ordner und Kennungen werden nur lokal gelesen und
  nicht an Modelle weitergegeben; Nachrichten an Chats enthalten sie nicht.
- **Vorschlag:** `projekte.json` (je Thema Ordnerpräfixe und Stichwörter) und `zuordnung.json`
  (von Sebastian bestätigt, nur Claude- und Hermes-Chats) liegen im Datenordner. Rangfolge:
  bestätigt bzw. Paar (Codex), längstes Ordnerpräfix (ganze Pfadsegmente), Stichwort im Titel (nur
  wenn genau ein Projekt passt). Für Codex-Chats ist das Paar die Bestätigung: Bestätigen setzt das
  Paar des Themas (`aktiv` bleibt) und schreibt nichts in `zuordnung.json`.
- **Befehl:** `masterwechsel chats` druckt nur Quellenstatus und Zählwerte (keine Titel, Ordner oder
  Kennungen – auch für Agenten aufrufbar). `masterwechsel chats --liste` zeigt zusätzlich je Chat
  Werkzeug, die ersten 8 Zeichen der Kennung, Zeit, Vorschlag mit Grund und den Titel – nur für
  Sebastian, denn es zeigt persönliche Titel.

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

# Wechselassistent: Thema vom alten an den neuen Chat übergeben, dann weiterführen
.\.venv\Scripts\masterwechsel.exe uebergeben engineering codex --von claude:<Kennung> --nach codex:<Kennung>
.\.venv\Scripts\masterwechsel.exe fortsetzen

# Wechselfenster öffnen (Themen, Übergabe starten, Vorgänge, Protokoll)
.\.venv\Scripts\masterwechsel.exe fenster
```

Einstellungen: `~/.master-schalter/einstellungen.json`, z. B.
`{"schwelle": 90, "claude_takt_min": 5, "automatik": false, "automatik_weg": "alt"}`. Die Schwelle liegt bei 1–100 (im
Taskleistenmenü 80, 90, 95, 97 oder 100; Standard 97), der Messungstakt bei 1–60 Minuten
(Standard 1), die Automatik ist ein Wahrheitswert (Standard aus), der Automatik-Weg ist `alt` oder `assistent`
(Standard `alt`). Die Paare liegen unter
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
  fenster.py   Wechselfenster (tkinter, nur eine Instanz) – nur Oberfläche
  fenster_modell.py  Ansichtsmodell des Fensters: Momentaufnahme, Chat-Auswahl, Zustellhinweise, Klartext, Aktionen
  assistent.py Wechselassistent: übergeben und fortsetzen (Abgabe, Frist, Rolle, Zustellung)
  assistent_vorgaenge.py  Vorgänge des Assistenten (`assistent.json`), Phasen, Quittung, Wiederaufnahme
  postfach.py  Postfach für Claude-/Hermes-Chats und feste Nachrichtentexte
  protokoll.py Entscheidungsprotokoll `protokoll.jsonl` (ohne Kennungen)
  claude_hook.py  Command-Hook für Claude Code: Postfach abholen, Status melden (noch nicht eingetragen)
  status.py    Statusregister `status/<werkzeug>-<kennung>.json` (`arbeitet` | `ruht`)
  chat_register.py   Zuletzt benutzte Chats (nur Metadaten, nur lesend) aus Claude Code, Codex, Hermes
  chat_zuordnung.py  Projekte, bestätigte Zuordnung und Projekt-Vorschläge je Chat
  vorgaenge.py Vorgänge je Paar und Limitfenster (Phase, Kennung, Lauf-Kennung)
  besitz.py    Besitzmarkierung `<thema>.master` (claude / reserviert / codex)
  automatik.py Entscheidung (faellige) und Ablauf der Automatik unter der Themensperre; Weg alt oder assistent
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
`ack`, `cli`, `fenster_modell`) nutzt nur die Standardbibliothek; das Fenster braucht zusätzlich `tkinter`
(Teil der Python-Installation), `pystray` und `Pillow` braucht nur die Taskleiste.

## Prüfbefehl

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Läuft auch automatisch im Git-Haken `.githooks/pre-commit`, sobald Code dieses Projekts
committet wird.

## Fahrplan

| Version | Inhalt |
|---|---|
| v0.5.0 (in Arbeit) | Wechselassistent: Ablauf, Postfach, Claude-Hook, Chatliste, Wechselfenster, Menü nach E9, Takt und Windows-Hinweise (Branch `v0.5.0-wechselassistent`) |
| **v0.4.1** | Claude-Katalog mit nativem `claude.exe`; Tests unabhängig von der installierten Claude-Version — **veröffentlichter Stand** |
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
