# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Der Schalter zeigt außerdem den
aktiven Master, ordnet die Lage der Kaskaden-Matrix zu und legt beim Wechsel ein
technisches Übergabepaket bereit.

Stand: **v0.5.1** (Entwicklungsstand; Linksklick öffnet das Übersichtsfenster, das Symbol zeigt keinen globalen Master mehr): Codex-Kontingent wird aktiv gemessen (Abschnitt „Woher die Zahlen kommen“, `masterwechsel codex-messen`). Darunter **v0.5.0** (veröffentlicht): Wechselassistent samt Fenster und Automatik-Weg (Abschnitte „Bedienung (v0.5.0)“ und „Zwei Wege für den Versand“). Noch offen: neue Sitzungen starten, Hermes-Empfang, Kontingent-Wächter. v0.4.1: Claude-Katalog findet das native `claude.exe` (npm-Paket ab 2.1.3xx ohne `cli.js`). Darunter v0.4.0: Rollen und Ausführermodelle je Thema (Profil v2): Master, Ausführer und Ausführermodell getrennt wählbar, dynamische Modellkataloge von Claude Code und Codex, neue CLI (profil/master-setzen/worker-setzen/modell-setzen/modelle). Hermes-Worker bleibt DeepSeek V4.1 Flash über OpenRouter (kostenpflichtig). Enthält die v0.3.5-Reparatur: bestätigter Menüwechsel läuft außerhalb des Traycallbacks; die native Ja/Nein-Bedienung auf dem Desktop ist weiterhin nicht nachgewiesen.

## Bedienung

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile „Lage 1 · Claude 62 % · Codex 1 % verbraucht" (5-Stunden-Fenster; unbekannt = „?“, zurückgesetzt = „neu“) |
| Linksklick | öffnet die **Übersicht** (eigener Prozess, siehe „Übersichtsfenster“); er löst den Menüeintrag „Übersicht …“ aus. Die frühere Windows-Benachrichtigung entfällt |
| Rechtsklick | Menü (seit v0.5.0 nach Plan E9): Stand-Zeilen (Themenzahl je Masterart, Lage, Kontingente), „Übersicht …", „Anmelden bei Claude …", „Übergabe starten …", Zeilen offener Wechsel, „Aktualisieren", „Einstellungen ▸" und „Beenden". Die bisherigen Einstellpunkte liegen unter „Einstellungen ▸" (siehe „Bedienung (v0.5.0)“) |

Das Symbol besteht aus zwei Balken (links Claude, rechts Codex). Die Füllhöhe zeigt den
5-Stunden-Verbrauch: Grundfarbe bis 79 %, gelb ab 80 %, rot ab der Schwelle (Standard 97 %).
Einen globalen Master zeigt das Symbol nicht mehr (früher ein weißer Punkt über dem Balken); der Menükopf
nennt stattdessen die Zahl der Themen je Masterart („Themen: 3 fest · 2 nach Kontingent“, „fest“ = Master Claude,
Codex oder Hermes, sonst „nach Kontingent“). `masterwechsel status`/`master` und `master.json` bleiben unverändert.
Die Anzeige wird standardmäßig jede Minute aktualisiert. Die Claude-Messung läuft beim
Start, nach „Aktualisieren" und anschließend im eingestellten Takt; dabei werden offene Übergaben
abgehakt (auch wenn die Automatik aus ist). Codex wird im selben Messtakt aktiv gemessen (höchstens alle
5 Minuten, kein Tokenverbrauch; siehe „Woher die Zahlen kommen“).

Im Menü „Einstellungen ▸ Standard-Master (übrige Themen)" (bis v0.4.1: „Master wechseln") kann Claude, Codex oder Hermes ausgewählt werden (Hermes = Lage 3 der
Kaskaden-Matrix; kein eigenes Abo-Kontingent, deshalb kein Balken). Jeder Wechsel
fragt vorher nach (Ja/Nein, Standard **Nein**); beim Ziel **Codex** werden danach zusätzlich alle aktiven
Themen an ihre Codex-Chats zurückgegeben (siehe „Rückgabe an Codex"). Der Wechsel legt ein Markdown-Paket
unter .hermes/uebergabe/ ab und zeigt den Paketnamen an. Themen mit Hermes-Schutz bleiben beim globalen Standardwechsel unberührt. Die Schwelle lässt sich im Menü „Einstellungen ▸ Wechsel-Schwelle"
auf 80, 90, 95, 97 oder 100 % setzen; sie steuert Lage und rote Anzeige. Die unbemannte Automatik
(Claude im Limit → Übergabe) läuft nur, wenn sie ausdrücklich eingeschaltet ist — per
`masterwechsel automatik an` (der frühere Menühaken ist in v0.3.2 entfallen).

## Übersichtsfenster (Linksklick)

Ein Linksklick auf das Symbol öffnet `uebersicht.py` als eigenen Prozess (`pythonw.exe -m master_schalter.uebersicht`;
auch von Hand startbar). Es läuft **nur einmal** (Sperre `uebersicht.lock`); eine zweite Instanz beendet sich still mit
Exit 0. Es liest alle 5 Sekunden im Hintergrund-Thread (`uebersicht_modell.aufnehmen`, dieselben Bausteine wie
`masterwechsel status`; nie Dateizugriff im Tk-Thread) und misst selbst nichts. Inhalt:

- **Kopf:** Uhrzeit, Lage und der Hauptschalter **Automatik** (an/aus) als Umschaltknopf; vor dem Umschalten fragt ein
  Ja/Nein-Dialog (Standard **Nein**).
- **Kontingent:** je Abo und Fenster (5h, Woche) ein Fortschrittsbalken „n % verbraucht“ (0–100), Reset-Zeit und
  Messzeit. Farbe wie im Symbol (aus dem ungerundeten Messwert): Grundfarbe, gelb ab 80 %, rot ab der Schwelle. Eine scheiternde Messung steht mit
  Grund darunter („Claude-Messung scheitert seit HH:MM (letzter Versuch HH:MM): …“, aus `messfehler.json`).
- **Themen:** Tabelle Thema · Master · Besitz · Prüfer · Ausführer · Arbeitsweise · Auto. Thema wählen, dann im
  Aufklappmenü „Master“ (Nach Kontingent / Claude Code / Codex / Hermes) die Rolle wählen; nach der Ja/Nein-Rückfrage
  setzt `modi.master_setzen` sie (nur die Rollenvorgabe, keine Sitzung). Das Menü „Arbeitsweise“ (Protokoll / Vibe)
  schaltet nach Rückfrage `modi.vibe_setzen`; Vibe wird vorab abgelehnt, wenn der Ausführer nicht Claude ist.
- **Knöpfe:** „Alle nach Kontingent“ und „Alle wie vorher“ (`alle.auf_kontingent` / `alle.zurueck`, mit Rückfrage,
  der Bericht erscheint in einem Textfeld), „Übergabe starten …“ (öffnet das Wechselfenster) und „Aktualisieren“
  (sofort neu lesen).
- **Unten:** „Wartet worauf“ und die jüngsten Sitzungen (wie im Master-Status: Kennung gekürzt, keine Chat-Titel, keine Pfade).
- **Lesefehler:** scheitert eine Aktualisierung, zeigt das Fenster keine alten Werte weiter: alle Balken „unbekannt“,
  darunter „keine aktuellen Messdaten (Aktualisierung fehlgeschlagen)“, „Automatik: unbekannt“; Automatik- und
  Schreibknöpfe sind gesperrt, bis eine Aufnahme wieder gelingt.

**Ein Repo-Ort für Lesen und Schreiben:** Je Aktualisierung wird genau einmal
`uebergabe.haupt_wurzel(uebergabe.repo_wurzel())` bestimmt; mit genau diesem `repo` werden Besitz gelesen und alle
Änderungen geschrieben (`modi.master_setzen(..., repo=repo)`, `alle.auf_kontingent(repo=repo)`, `alle.zurueck(repo=repo)`).
Aus einem Git-Worktree gestartet, treffen Anzeige und Änderung also den Hauptarbeitsbaum. Geschrieben wird nur, wenn
`repo/.git` ein **Ordner** ist (die Prüfung läuft bei der Aufnahme und unmittelbar vor dem Schreiben). Ist das Repo
nicht bestimmbar oder die Auflösung über `commondir` gescheitert (dann ist `.git` eine Datei), sind die Schreibknöpfe
gesperrt und es steht „Hauptarbeitsbaum nicht gefunden – nur Anzeige“ da. Der Automatik-Schalter schreibt nur
`einstellungen.json` im Datenordner und ist davon nicht betroffen.

## Bedienung (v0.5.0)

Der Wechsel „Thema X: alter Chat → neuer Chat" läuft über **ein Menü, ein Fenster und einen Takt in der Leiste**.
Alles Folgende gilt für den Entwicklungsstand auf Branch `v0.5.0-wechselassistent` (noch nicht veröffentlicht).

**Menü (Rechtsklick, Plan E9).** Oben die Stand-Zeilen (Themenzahl je Masterart, Lage, Kontingente). Darunter:
„Übersicht …“ (= Linksklick) öffnet das Übersichtsfenster; „Übergabe starten …" öffnet das Wechselfenster als eigenen Prozess; je offenem Wechsel steht eine
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
- Der Claude-Hook ist nur auf Sebastians PC in `.claude/settings.local.json` des Workspaces eingetragen (gitignored,
  siehe „Claude-Empfang"); andere Rechner und Claude-Chats außerhalb des Workspaces holen das Postfach nicht ab.
  Ein echter Empfang Ende-zu-Ende ist noch nicht nachgewiesen.
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
.\.venv\Scripts\masterwechsel.exe vibe THEMA an|aus
.\.venv\Scripts\masterwechsel.exe thema-anlegen THEMA [--master claude|codex|hermes|kontingent]
.\.venv\Scripts\masterwechsel.exe modelle [claude|codex] [--aktualisieren] [--json]
```

`profil` (Textform) und `master-setzen` zeigen zusätzlich den **Prüfer** nach der Regel von `pruefkreis.py`
(siehe Master-Status): „Jetzt: Prüfer …“ aus dem Besitz (`<thema>.master` im Hauptarbeitsbaum). Ein fester Master
schreibt die Marke mit, der Prüfer wechselt also sofort (Master Codex ⇒ „Prüfer Hermes (Master Codex)“). Bei
„Nach Kontingent“ folgt der Prüfer dem jeweiligen Besitzer; weicht eine feste Vorgabe vom Besitz ab, nennt eine
zweite Zeile den Prüfer nach der Übergabe. `profil --json` behält alle bisherigen Felder unverändert; neu kommen die
Felder der Arbeitsweise dazu (siehe unten). **Grenze:** Der Sofortwechsel gilt
für Aufrufe aus dem Hauptarbeitsbaum (so läuft die Leiste). Aus einem Git-Worktree schreibt `master-setzen` bei
Themen **mit** Codex-Paar die Marke in den Worktree, die Vorschau und `pruefkreis` lesen aber den Hauptbaum – die Ausgabe
sagt das dann mit „Hinweis: Aufruf aus einem Git-Worktree …“. Themen **ohne** Paar schreiben immer im Hauptbaum (siehe
`thema-anlegen`); dort entfällt der Hinweis.

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

### Arbeitsweise je Thema: `protokoll` oder `vibe` (unveröffentlicht)

Jedes Thema hat eine Arbeitsweise. Standard ist `protokoll` (der bisherige Ablauf mit Gegenprüfung). `vibe` schaltet
Sebastian für ein Thema **von Hand** ein; die Regel dazu gehört in den Schalter, nicht in `AGENTS.md`.

- **Datei:** `<datenordner>/arbeitsweise.json` = `{"version": 1, "themen": {"<thema>": "vibe"}}`. Ein fehlendes Thema (oder
  eine fehlende Datei) heißt `protokoll`. Die Datei gehört bewusst **nicht** zum strengen Profilformat `themenmodi.json`;
  Profil-Leser und -Sperren bleiben unberührt. Gelesen wird streng: kaputtes JSON, unbekannte Version, Schlüssel oder
  Werte ergeben einen Fehler beim Setzen und die Anzeige „?“ (nie ein Absturz); eine ungültige Datei wird nie
  überschrieben. Schreiben ist atomar unter der kurzen globalen Sperre. `aus` entfernt den Eintrag.
- **Nur von Hand:** `masterwechsel vibe THEMA an|aus` (und die Spalte „Arbeitsweise“ im Übersichtsfenster, mit
  Ja/Nein-Rückfrage). Kein Automatikpfad (`automatik`, `alle`, Wechselassistent) schreibt die Datei. Das Thema muss
  existieren (Profil oder Paar); jeder Fehler lässt die Datei unverändert; wiederholtes Setzen ist idempotent.
- **Regel (`vibe_regel`):** Claude-Subagent baut (Modell laut Profil; bei `modell_standard` wählt der Master Sonnet oder
  Haiku); der Master gibt den Auftrag und nimmt per Kurzprüfung ab (Diff lesen, Prüfbefehl selbst ausführen); keine
  Codex-/Hermes-Gegenprüfung; Prüfbefehl Pflicht vor Commit und Push; Sensibles nur Hermes; kein OT/SPS-Code; kein
  force-push, kein Löschen. Ein festes Claude-Modell im Profil gilt; die Regel schreibt kein Modell vor. `vibe an` gibt
  die Regel aus.
- **Prüferangabe bei Vibe:** Master-Status, Übersichtsfenster, `profil` und `master-setzen` nennen dann „Prüfer
  Master-Kurzprüfung (Vibe, keine Codex-/Hermes-Gegenprüfung)“ statt des pruefkreis-Prüfers.
- **`profil THEMA --json`:** bekommt zusätzlich `"arbeitsweise": "protokoll"|"vibe"` (bei ungültiger Datei `"?"`) und bei
  `vibe` `"vibe_regel"`; die bisherigen Felder bleiben unverändert und stehen vorn. `profil THEMA` (Text) zeigt
  „Arbeitsweise: …“ und bei Vibe die Regel. Vor jedem Workerauftrag gilt: `arbeitsweise` aus dem Profil beachten.
- **Vorrang Vibe vor der Workerwahl:** Vibe gibt es nur mit `worker=claude`, damit Profil und Regel nie widersprechen.
  `vibe THEMA an` bei anderem Ausführer ⇒ Fehler „Vibe braucht Ausführer Claude – erst `worker-setzen THEMA claude`“.
  Umgekehrt lehnt jedes Schreiben eines Profils mit anderem Ausführer bei `vibe` ab („erst `vibe THEMA aus`“), ohne
  Profil oder Besitzdatei zu ändern. Die Prüfung sitzt zentral im einzigen Profilschreiber `modi._speichern` und – vor
  der ersten Besitzmarke – in `modi._umschalten_gesperrt`; damit gilt sie für `worker-setzen`, `modell-setzen`,
  `master-setzen`, `modus THEMA hermes-codex|kontingent` (Legacy-Profil mit Ausführer codex/workflow), `alle` und den
  Wechselassistenten. `vibe` selbst läuft unter der Themensperre und liest das Profil dazu frisch. **Grenze
  (fail-closed):** Ist `arbeitsweise.json` nicht lesbar, ist unbekannt, ob Vibe gilt – dann werden Profile mit anderem
  Ausführer als Claude nicht geschrieben (die Meldung nennt den Grund), bis die Datei repariert ist.
- **Anzeige:** Die Themenzeile im Master-Status endet bei Vibe auf „· VIBE“ (bei Protokoll nichts, bei ungültiger Datei
  „· Arbeitsweise ?“ plus Hinweis). Das Übersichtsfenster hat die Spalte „Arbeitsweise“ und neben dem Master-Menü einen
  Umschalter (Protokoll/Vibe, mit Rückfrage; gesperrt in „nur Anzeige“).

### Thema ohne Codex-Paar (`thema-anlegen`, unveröffentlicht)

Nicht jedes Thema braucht einen Codex-Chat. `masterwechsel thema-anlegen THEMA [--master claude|codex|hermes|kontingent]`
(Standard `claude`) legt ein Thema **ohne Paar** an: das Profil (`themenmodi.json`, Master = `--master`, Ausführer
Workflow) und die Besitzdatei `.hermes/uebergabe/laufend/<THEMA>.master` im **Hauptarbeitsbaum** (gleicher Ort wie bei
`pruefkreis`, auch aus einem Git-Worktree heraus). Der Besitz steht bei der Anlage immer auf `claude <ISO-Zeit> modus
<THEMA>` (der anlegende Master); die Vorgabe `--master` steht im Profil. Alles läuft unter der Themensperre:

- Profil und Besitzdatei fehlen ⇒ erst das Profil, dann die Besitzdatei **exklusiv** (`O_EXCL`, nie überschrieben) ⇒
  „angelegt“. Zwei gleichzeitige Anlagen ergeben genau eine Besitzdatei; die andere meldet „existiert schon“.
- Profil da, Besitzdatei fehlt, kein Paar (halbe Anlage nach einem Abbruch, auch ältere Themen wie `weiterbildung`) ⇒ die
  Besitzdatei wird ergänzt („Besitzdatei ergänzt“); weicht `--master` vom gespeicherten Master ab, Fehler und nichts geändert.
- Besitzdatei da (auch leer) ohne Profil und ohne Paar ⇒ Fehler „existiert ohne Profil“; fremder oder alter Stand wird nie
  überschrieben. Profil **und** Besitzdatei da, oder ein Paar vorhanden ⇒ Fehler „existiert schon“.
- Ist der Hauptarbeitsbaum nicht auffindbar (`.git` ist eine Datei und die `commondir`-Auflösung scheitert), lehnt der
  Befehl vor jeder Nebenwirkung ab („Hauptarbeitsbaum nicht gefunden“).

**Themen ohne Paar in den Schreibwegen:** `modi._paar_pruefen(..., ohne_paar=True)` lässt ein Thema ohne Paar gelten, wenn es
ein Profil hat (frisch gelesen); der Besitzpfad ist dann immer der im Hauptarbeitsbaum, nie eine Worktree-Kopie. Das gilt
für `master-setzen` (auch über `master_setzen_wenn`, also `alle`), `worker-setzen`, `modell-setzen` sowie die
Schutzprüfung (`fuehrt`/`geschuetzt`) und `snapshot`. `worker-setzen` und `modell-setzen` prüfen nur den Besitzpfad und
lassen alle Besitzdateien bytegleich. Ohne Profil und ohne Paar bleibt es bei „Thema unbekannt“ (Tippfehlerschutz). **Weiter
ein Paar verlangen:** Wechselassistent, Postfach, Automatik, `master_uebergeben_gesperrt` und der Legacy-Setter
`modus THEMA …`. Themen **mit** Paar behalten Verhalten und Besitzpfad (bewusst unverändert, eigener Schritt). Der
Master-Status zeigt solche Themen mit „· ohne Codex-Paar“ (statt früher „kein Paar“) und liest ihren Besitz im Hauptbaum.

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
(v0.5.0)“). Der Empfang im Hermes-Chat (P6) ist noch nicht gebaut; der im Claude-Chat läuft als Hook (Eintrag siehe
„Claude-Empfang“).

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
  Postfach über den Hook abholen (siehe „Claude-Empfang“; eingetragen nur auf Sebastians PC); für
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
JSON auf stdin; das Modul liest höchstens 1 MB und wertet nur `hook_event_name`, `session_id` und
`stop_hook_active` aus.

- **`UserPromptSubmit` und `PostToolUse`:** meldet den Status `arbeitet` und holt mit
  `postfach.vormerken("claude", session_id)` die Nachrichten dieser Sitzung vor (Übernahme-Auftrag `neu`,
  Abgabe-Auftrag, Abgabe-Info – mit den Gültigkeitsregeln aus dem Abschnitt Wechselassistent). Gibt es
  Nachrichten, schreibt der Hook genau ein JSON auf stdout:
  `{"hookSpecificOutput": {"hookEventName": "<Ereignis>", "additionalContext": "<Text>"}}`. Der Text besteht
  aus der festen Einleitung „Nachricht des Master-Schalters:“ und den festen Postfachtexten, je Zeile einer.
  Er enthält nur Thema, Vorgangs-ID und den repo-relativen Pfad der laufenden Übergabe – nie die
  Sitzungskennung oder einen absoluten Pfad. Ohne Nachricht gibt es **keine** Ausgabe.
- **`Stop`:** setzt den Status `ruht`; Wechselnachrichten des Postfachs werden bei `Stop` nie zugestellt.
  Ausnahme seit v0.5.1: Liegt ein **Auftrag** vor (Abschnitt „Aufträge an Claude“) und ist `stop_hook_active`
  nicht `true`, gibt der Hook `{"decision": "block", "reason": "<Text>"}` aus – Claude arbeitet dann sofort
  weiter, statt bis zur nächsten Nutzernachricht zu ruhen; der Status bleibt `arbeitet`.
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

**Stand des Eintrags (ehrlich):** Seit 25.10.2026 ist der Hook nach Sebastians OK auf seinem PC in
`.claude/settings.local.json` des Workspaces eingetragen (gitignored, gilt nur dort). Ohne Eintrag holt kein
Claude-Chat das Postfach ab, und es wird kein Status geschrieben. Ein echter Empfang Ende-zu-Ende ist noch nicht
nachgewiesen. Beispiel (Pfad des venv-Pythons anpassen):

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

## Aufträge an Claude (v0.5.1, unveröffentlicht)

Ein Master (Codex oder Hermes) beauftragt eine laufende Claude-Code-Sitzung, z. B. als Prüfer. Das Postfach des
Wechselassistenten kennt nur feste Wechselnachrichten; Aufträge laufen deshalb getrennt über `auftraege.py` und
ändern weder Besitz noch Profil.

```text
masterwechsel claude-sitzungen
masterwechsel claude-auftrag --sitzung <kennung> --thema <thema> --datei .hermes/<…>.md [--von codex|hermes]
```

- **Auftrag als Datei:** Der Inhalt steht in einer Markdown-Datei unter `.hermes/` (repo-relativ, muss existieren,
  kein `..`, kein absoluter Pfad; auch nach dem Auflösen von Verknüpfungen innerhalb von `.hermes/` und des Repos). Ins Postfach `<datenordner>/auftraege/claude/<kennung>/<id>.json` kommt nur
  `{auftrag, thema, von, datei, zeit}` (höchstens 4 KB, atomar, idempotent je ID).
- **Gemeinsame Dateibasis:** Pfade gelten im Hauptarbeitsbaum des Repos: `MASTER_SCHALTER_REPO`, sonst der
  Elternordner von `git rev-parse --git-common-dir`. Ein Aufruf aus einem Worktree findet so dasselbe `.hermes/`.
  `claude-auftrag` nennt den absoluten Pfad der Ergebnisdatei.
- **Zustellung:** über den Claude-Hook bei `UserPromptSubmit`/`PostToolUse` (Zusatzkontext) und bei `Stop`
  (`decision: block`, außer `stop_hook_active` ist `true`). Erst ausgeben, dann nach `erledigt/` verschieben;
  ungültige Dateien wandern mit Grund nach `verworfen/`. Ein Fehler bei den Aufträgen verhindert die
  Postfachzustellung nicht.
- **Ergebnis:** `<auftrag ohne .md>-ergebnis-<auftrag-id>.md` neben dem Auftrag, je Auftrag eine eigene Datei. Claude legt sie als **ersten** Schritt mit
  `ERGEBNIS: LÄUFT (Auftrag <id>)` an; die letzte Zeile am Ende ist `ERGEBNIS: FERTIG` oder `ERGEBNIS: BLOCKIERT`.
- **Schutz vor doppelter Ausführung:** Existiert die Ergebnisdatei dieses Auftrags schon, wird der Auftrag nicht erneut zugestellt,
  sondern mit Vermerk „Ergebnis vorhanden – bereits angenommen“ nach `erledigt/` verschoben.
- **Nachweis (27.10.2026):** Echter Auftrag per `claude-auftrag` an eine laufende Claude-Sitzung, Zustellung beim
  nächsten `PostToolUse`, Ergebnisdatei mit `ERGEBNIS: FERTIG`, Auftrag danach unter `erledigt/`. Die Zustellung bei
  `Stop` ist nur durch Tests belegt, noch nicht live. Der Hook-Eintrag zeigt seit 27.10. auf den Hauptstand.
- **Grenze:** Ruht die Sitzung zwischen zwei Antworten, kommt der Auftrag erst beim nächsten Ereignis an (z. B. der
  nächsten Nachricht von Sebastian). Ruhende Desktop-Sitzungen kann der Hook nicht wecken; dafür bleibt ein frischer
  `claude -p`-Lauf.

## Master-Status für den Chat (unveröffentlicht)

`masterwechsel status` (Chat-Befehl `/master-status`) gibt in wenigen Zeilen ohne Tabellen aus, was man beim Steuern über eine
Remote-Sitzung sehen will. Die Kopfzeile lautet „Master-Status · HH:MM · Lage … · Hauptschalter Automatik an|aus“. Der frühere Befehl `kurz`
bleibt als **stiller Alias** mit gleicher Ausgabe (in der Hilfe nicht mehr aufgeführt); die bisherige Zwei-Zeilen-Ausgabe von `status`
(beide Kontingente) entfällt, sie steckt in der Übersicht. Der Agent führt den Befehl aus und reicht die Ausgabe wörtlich in den Chat weiter.
Der Befehl liest nur: Er misst nicht, schreibt nichts und startet nichts.

- **Kontingent verbraucht:** je Abo und Fenster der *Verbrauch* („… % verbraucht“, auf 0–100 begrenzt), die Zeit bis zum Reset
  („Reset in 3 h 33 min, 01:39“) und die Messzeit. Ein Fenster nach Reset
  ohne neue Messung heißt „neu, nicht gemessen“, ein Messfehler „unbekannt (…)“.
- **Matrix:** Lage und Besetzung aus `rollen.BESETZUNG` (Planer/Prüfer/Ausführer), nur bei bekannter Lage.
- **Themen:** Master-Vorgabe, Besitzer aus `<thema>.master` (fehlend = claude, Lesefehler = unbekannt),
  **Prüfer** nach derselben Regel wie `pruefkreis.py`: Master laut `<name>.master` (Thema oder längster Anfang vor
  einem Bindestrich, leere Datei = claude) – Codex ⇒ „Prüfer Hermes (Master Codex)“, Claude/Hermes ⇒ „Prüfer
  Codex“. **Fehlt** die Datei oder ist sie unlesbar/unbekannt ⇒ „Prüfer ? (pruefkreis braucht --master)“, denn
  pruefkreis bricht dann ab – auch wenn die Besitzanzeige davor beim Rückfall „fehlend = claude“ bleibt.
  Aus einem Git-Worktree heraus liest der Master-Status Besitzdateien im **Hauptarbeitsbaum** (`uebergabe.haupt_wurzel`,
  `.git` → `gitdir` → `commondir`, wie `pruefkreis`); die schreibenden Teile behalten `repo_wurzel`.
  Ausführer mit Modell und ob die Automatik das Thema wirklich anfasst. „Auto an“ gilt nur bei aktivem Paar,
  Master-Vorgabe „nach Kontingent“ und eingeschalteter globaler Automatik, wie in `automatik.py`.
- **Sitzungen:** die drei jüngsten Einträge des Statusregisters, Kennung auf 8 Zeichen gekürzt, mit Thema aus
  einer von Sebastian bestätigten Zuordnung (`zuordnung.json`, siehe Chatliste), sonst „Thema nicht zugeordnet“. Ein
  „arbeitet“, das älter als 30 Minuten ist, erscheint als „arbeitet? (veraltet)“.
- **Als Nächstes:** zuerst „neu messen“, wenn ein Fenster zurückgesetzt ist, sonst der früheste Reset
  eines Fensters im Limit mit Uhrzeit und Restzeit („22:36 (in 24 min)“). Ein Reset ist keine Zusage, dass dann weitergearbeitet wird.
- **Wartet worauf:** je Thema die Meldung aus `masterwechsel warte THEMA TEXT…` (älteste zuerst, mit „seit“;
  älter als 24 h ⇒ „(veraltet?)“), sonst „Wartet worauf: nichts gemeldet“. Ablage `<datenordner>/wartet/<thema>.json`,
  eine Zeile, höchstens 120 Zeichen (Steuerzeichen und Zeilenumbrüche werden Leerzeichen); kaputte oder zu große
  Dateien werden übersprungen, nie geraten. `warte THEMA --fertig` entfernt die Meldung (idempotent). **Nur eine
  technische Kurzangabe** („Freigabe Vibe-Modus“, „Codex-Prüfung R2“) – keine Inhalte, Namen oder Pfade; der Code
  begrenzt nur Form und Länge.
  **Verwaiste Meldung:** Die Meldung von `pruefkreis` („Prüfung R<n> läuft“) enthält zusätzlich `"pid"` (Prozess der
  Prüfung; `warte` schreibt keine pid, alte Dateien ohne pid bleiben gültig, eine kaputte pid – Text, negativ, 0, zu groß –
  wird ignoriert). Ist der Prozess beendet, hängt die Zeile in Master-Status und Übersicht
  „(verwaist – Prozess beendet; `warte THEMA --fertig` räumt auf)“ an. `wartet.lebt(pid)`: Windows über
  `OpenProcess`/`GetExitCodeProcess` (Fehler 87 ⇒ beendet, Zugriff verweigert oder anderer Fehler ⇒ unbekannt,
  Exit-Code ≠ 259 ⇒ beendet), sonst `os.kill(pid, 0)`; „unbekannt“ zeigt die Zeile normal. Unter Windows gilt die Meldung
  auch als verwaist, wenn der Prozess **nach** der Meldung gestartet wurde (`GetProcessTimes`, 5 s Toleranz; die pid wurde
  dann wiederverwendet); unbekannte Startzeit zählt nur als „lebt“. Es wird **nie automatisch gelöscht** – das bleibt
  `warte THEMA --fertig` bzw. `pruefkreis` selbst.
- **Gemerkt:** steht eine Merkdatei des Sammelbefehls `alle` (siehe unten), zusätzlich
  „Gemerkt für „alle zurueck“: <thema> <rolle>, …“; eine ungültige Merkdatei nur als Hinweis.
- **Messfehler:** scheitert die Claude- oder Codex-Messung, steht direkt unter den Limitzeilen
  „Claude-Messung scheitert seit HH:MM (letzter Versuch HH:MM): <fester Text>“. Quelle ist `<datenordner>/messfehler.json`
  (`{"claude"|"codex": {"kategorie", "text", "seit", "zuletzt"}}`). Geschrieben wird in den zentralen Messfunktionen
  `claude_messen.messen` und `codex_messen.messen` selbst – also für jeden Messweg (Leiste, `claude-messen`,
  `codex-messen`, Automatik): Fehler ⇒ Eintrag der Quelle (`seit` bleibt beim ersten Fehler der Serie, `zuletzt` = jetzt),
  Erfolg ⇒ Eintrag derselben Quelle weg. Der Text ist der feste Fehlertext, nie Rohdaten oder Token. Es gibt **keine
  Verfallsgrenze**: ein Eintrag gilt, bis eine Messung derselben Quelle gelingt. Kann die Statusdatei nicht
  geschrieben werden, bleiben Messergebnis und Ausnahme unverändert; eine kaputte Datei zeigt einfach nichts an.
  Lesen-Ändern-Schreiben läuft unter der Sperre `messfehler.json.lock`, damit zwei Messwege (z. B. Leiste und CLI)
  sich nicht gegenseitig einen alten Stand zurückschreiben; bleibt sie 5 s belegt, entfällt dieses eine Update.

### Alle Themen auf einmal (`masterwechsel alle`, unveröffentlicht)

- `alle kontingent` stellt jedes Thema auf „Master nach Kontingent“. Vorher merkt es sich jede feste Rolle
  (`claude`/`codex`) in `<datenordner>/alle-vorher.json` – unter der Themensperre und für genau den Zustand, der
  umgeschaltet wird (`modi.master_setzen_wenn`). Ein Eintrag wird nur durch eine feste Rolle ersetzt, nie durch
  „kontingent“; ein zweiter Aufruf verliert nichts.
- `alle zurueck` stellt die gemerkten Rollen wieder her, solange das Thema noch auf Kontingent oder schon auf der
  gemerkten Rolle steht (halbfertige Wechsel werden abgeschlossen). Eine inzwischen von Hand gesetzte andere Rolle
  bleibt. Sind alle Einträge erledigt, wird die Merkdatei nach `alle-vorher.<zeitstempel>.json` **verschoben**, nie
  gelöscht; offene Einträge bleiben für einen erneuten Aufruf stehen.
- **Hermes bleibt immer unberührt:** Hermes-Master, Hermes-Besitz und ein abgebrochener Wechsel zu Hermes (eigene
  Zwischenmarke mit Ziel Hermes). Eine Zwischenmarke mit fremdem Ziel wird nie fortgesetzt („offen“).
- Beide Richtungen laufen unter der Sperre `alle` (zweiter gleichzeitiger Aufruf ⇒ „läuft schon“, nichts geändert).
  Exit 0 = alles erledigt, 1 = ein Thema offen oder Sperre belegt, 2 = Merkdatei ungültig (nichts geändert).
- Der globale Hauptschalter `automatik an|aus` ist davon getrennt. Wie `master-setzen` schreibt der Befehl den
  Besitz im Repo, in dem er läuft – echte Läufe aus dem Hauptarbeitsbaum, nicht aus einem Git-Worktree.

Codex-Chat-Kennungen, Chattitel und Pfade erscheinen nicht. Über Pipes schreiben `status` (und `kurz`) und alle
anderen Befehle (stdout und stderr, schon vor dem Einlesen der Argumente, also auch `--help`) UTF-8, damit Umlaute in Remote-Sitzungen und über `/master-status`
lesbar ankommen; einzige Ausnahme ist `statuszeile` (Anzeige der Claude-Code-Statuszeile, bewusst unverändert).

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
  Protokolle: `leiste.log` (Fehler, u. a. Messfehler mit Zeitstempel; bei Claude mit Fehlerart `http`/`netz`/`antwort`/`speichern` bzw. `anmeldung_fehlt`/`anmeldung_defekt`/`anmeldung_abgelaufen`/`anmeldung_abgelehnt` und ggf. HTTP-Code) und `leiste-ausgabe.log`.
- Autostart: Verknüpfung im Startmenü-Startup-Ordner (`Master-Schalter-Leiste.lnk`) startet genau
  eine Leiste bei jeder Anmeldung.
- Nach tiefem Energiesparen kann das Taskleisten-Symbol verschwinden — Doppelklick auf den Starter
  genügt; die Erholung per Aufwach-Aufgabe ist als nächster Schritt vorgesehen.

## Woher die Zahlen kommen

Codex wird aus lokalen Sitzungsdateien gelesen und (seit v0.5.1) zusätzlich aktiv gemessen. Claude wird
über den OAuth-Usage-Endpunkt gemessen und das Ergebnis lokal zwischengespeichert.

- **Codex** schreibt seine Kontingente in die eigenen Sitzungsdateien
  `~/.codex/sessions/**/rollout-*.jsonl` (Ereignis `token_count`, `limit_id: "codex"`).
  Gelesen werden nur Zeilen mit `"rate_limits"`; übernommen werden nur Zahlen — für den
  Verbrauch ausschließlich Werte von 0 bis 100 (negativ, über 100, nicht endlich oder fehlend
  heißt „unbekannt" und löst nie einen Versand aus). Neue Werte
  entstehen nur, wenn Codex arbeitet — deshalb steht immer „Stand" dabei. Ein Fenster, dessen
  Rücksetzzeit vorbei ist, wird im Kontingentmenü als „zurückgesetzt" angezeigt. Bis ein
  neuer Messwert vorliegt, zeigen Tooltip und Balken weiterhin 0 %; das ist ein bekannter
  Fehler. Die Lage wertet das Fenster als unbekannt und nennt den Grund.
- **Codex, aktive Messung (v0.5.1)**: Sitzungsdateien sind nur frisch, solange Codex arbeitet. Arbeitet
  Claude und Codex ruht, wäre die Messung veraltet und die Automatik (verlangt eine Codex-Messung
  von höchstens 10 Minuten) würde nie auslösen. Deshalb startet `masterwechsel codex-messen` (und der
  Takt der Taskleiste) `codex.exe app-server` (Argumentliste ohne Shell, ohne Konsolenfenster, stderr
  verworfen, Umgebung ohne API-/Token-Schlüssel, Arbeitsordner ein leerer Ordner), schickt `initialize`,
  die Benachrichtigung `initialized` und `account/rateLimits/read` (Zeile je Nachricht, Frist 20 s) und
  beendet den Prozess samt allen Nachkommen **immer** wieder: unter Windows über ein Jobobjekt (greift auch, wenn der
  Elternprozess zuerst endet; `taskkill /T` fände die Kinder dann nicht mehr), sonst `taskkill /PID <eigene PID> /T /F`
  bzw. die eigene Prozessgruppe. Die Bereinigung ist hart zeitbegrenzt (Gnadenfrist 0,5 s + 5 s Kill-Wartezeit + 3 s
  Einsammeln des Lesefadens); `stdout` wird nie geschlossen, solange der Lesefaden liest (das würde unbegrenzt blockieren) —
  scheitert die Bereinigung, meldet die Messung „Bereinigung fehlgeschlagen“, statt zu hängen. Das kostet keine Tokens.
  Die beiden Fenster werden nach `windowDurationMins` zugeordnet (300 → „5h“, 10080 → „Woche“), nicht nach
  Position; Fenster mit anderer Dauer werden ignoriert (ein Ausweichdatensatz `rateLimitsByLimitId["codex"]` muss selbst
  zu `codex` gehören), fehlt eines der beiden oder liegt `usedPercent`
  außerhalb 0–100, ist die Messung ein Fehler und die vorhandene Datei bleibt unverändert. Gespeichert
  werden **nur** Prozent, Rücksetzzeit und Messzeit in `~/.master-schalter/codex-kontingent.json`
  — keine Kontofelder (Plan, Credits, Namen); Fehlertexte sind feste Texte mit Fehlerklasse
  („Codex-Messung fehlgeschlagen (Zeitüberschreitung)“), nie Text aus der Antwort. Der Takt misst höchstens
  alle 300 s und zusätzlich vor der Automatikprüfung, wenn die frische Claude-Messung die Schwelle
  erreicht und der Codex-Stand älter als 120 s ist; die Messung läuft im Messfaden, nie im Menüfaden.
  `signale.codex_lesen` nimmt den **neueren** Stand aus Sitzungsdateien und aktiver Messung (eine Messzeit
  mehr als eine Minute in der Zukunft wird ignoriert).
  **Bekannte Grenze:** Das Protokoll von `codex.exe app-server` ist eine Schnittstelle der Codex-App und kann
  sich ändern; ein Fehlschlag zeigt sich nur im Log (`leiste.log`) und dadurch, dass der Codex-Stand nicht
  frisch wird.
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
  ungültig). Bei abgelaufener Anmeldung bleibt der bisherige Messwert mit Stand erhalten. Werte lassen
  sich weiterhin mit `masterwechsel claude-kontingent …` von Hand eintragen.
  **Selbsterneuerung bei abgelaufenem Zugang (Entwicklungsstand):** Endet eine Messung mit
  `anmeldung_abgelaufen`, startet `claude_messen.messen` (also jeder Messweg: Leiste, `claude-messen`,
  Automatik) `claude auth status` (`claude_anmeldung.erneuern`: ohne Konsole, Ein-/Ausgabe nach `DEVNULL`,
  nichts wird gelesen oder protokolliert, nach 30 s wird der Prozessbaum beendet, wirft nie) und liest danach
  genau einmal neu. Das geschieht höchstens **einmal je 30 Minuten über alle Prozesse**: nicht blockierende
  Sperre `<datenordner>/claude-erneuerung.lock` (belegt ⇒ kein Versuch), Zeitstempel
  `<datenordner>/claude-erneuerung.json` (jünger als 30 min ⇒ kein Versuch); der neue Zeitstempel wird **vor**
  dem Start geschrieben, lässt er sich nicht schreiben, gibt es keinen Versuch. Eine kaputte Datei oder ein
  Zeitstempel in der Zukunft gilt als alt. Andere Fehlerarten (fehlt, defekt, abgelehnt, HTTP, Netz) lösen nie
  eine Erneuerung aus. Bleibt der Zugang abgelaufen, steht in `messfehler.json` bzw. im Master-Status „Claude-Messzugang
  abgelaufen – automatische Erneuerung um HH:MM ohne Erfolg; Claude Code auth login --claudeai ausführen“.
  **Nicht belegt:** Ob `claude auth status` den OAuth-Token wirklich erneuert, ist eine Vermutung (am 28.10.2026
  scheiterte die Messung von 00:03 bis 02:40 mit `anmeldung_abgelaufen` und lief nach einem CLI-Aufruf wieder).
  Beim nächsten Ablauf erkennt man die Wirkung so: bleibt `messfehler.json` ohne Claude-Eintrag, hat die
  Erneuerung gewirkt; steht dort „ohne Erfolg“, hilft nur `claude auth login --claudeai` von Hand. Der
  Refresh-Token selbst wird von master-schalter weiterhin nicht gelesen.

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

# Master-Status (Konsole oder Remote-Sitzung): Verbrauch, Lage, Themen, Sitzungen – nur lesend
.\.venv\Scripts\masterwechsel.exe status

# „Wartet worauf“ melden (erscheint im Master-Status) und wieder entfernen
.\.venv\Scripts\masterwechsel.exe warte master-schalter Freigabe Vibe-Modus
.\.venv\Scripts\masterwechsel.exe warte master-schalter --fertig

# alle Themen (außer Hermes) nach Kontingent und wieder zurück auf die gemerkten Rollen
.\.venv\Scripts\masterwechsel.exe alle kontingent
.\.venv\Scripts\masterwechsel.exe alle zurueck

# Claude-Kontingent über die OAuth-API messen
.\.venv\Scripts\masterwechsel.exe claude-messen

# Codex-Kontingent aktiv messen (kein Tokenverbrauch)
.\.venv\Scripts\masterwechsel.exe codex-messen

# aktiven Master, Lage und Rollen anzeigen
.\.venv\Scripts\masterwechsel.exe master

# Master wechseln und technisches Übergabepaket schreiben
.\.venv\Scripts\masterwechsel.exe wechsel codex --hinweis "Nur technische Hinweise"

# Claude-Werte von Hand eintragen (Ersatzweg ohne Statuszeile)
.\.venv\Scripts\masterwechsel.exe claude-kontingent --fuenf 90 --woche 70 --reset-fuenf 2026-10-14T18:40:00Z --reset-woche 2026-10-18T21:00:00Z

# Arbeitsweise Vibe eines Themas ein- oder ausschalten (nur von Hand; braucht Ausführer Claude)
.\.venv\Scripts\masterwechsel.exe vibe engineering an
.\.venv\Scripts\masterwechsel.exe vibe engineering aus

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

Bei abgelaufenem oder vom Server abgelehntem lokalem Claude-Messzugang kann im Taskleistenmenü
**Anmelden bei Claude …** gewählt werden. Unter Windows öffnet das die offizielle Claude-Code-Anmeldung
(`claude auth login --claudeai`) in einem eigenen Konsolenfenster. Nach erfolgreichem Prozessende wird nur
eine neue Messung angefordert; erst deren tatsächlicher Erfolg bestätigt, dass die Kontingentwerte wieder
gelesen werden können. Der lokale Access-Token-Fehler sagt nichts darüber aus, ob Claude Desktop abgemeldet
ist oder das Abo abgelaufen ist. Die Selbsterneuerung (siehe „Claude Code“ oben) ist ein Versuch ohne belegte Wirkung; der
interaktive Login bleibt der sichere Weg. Ist
`CLAUDE_CONFIG_DIR` nicht gesetzt oder leer, gilt der Standardordner `~/.claude`; andernfalls wird dieser
Konfigurationsordner sowohl für Messung als auch CLI-Anmeldung verwendet.

Frische Claude-Werte aus der unabhängigen nativen Statuszeile bleiben bei einem Fehler der OAuth-Messung
nutzbar; zu alte Stände werden im Menü als **veraltet** markiert. Die bestehende Frischeprüfung der Automatik
bleibt maßgeblich. Die Windows-Autostart-Einrichtung ist von diesem Loginweg unabhängig und bleibt ein eigener
offener Punkt.

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
  arbeitsweise.py  Arbeitsweise je Thema (`protokoll`|`vibe`, `arbeitsweise.json`), nur von Hand geschrieben
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
  claude_hook.py  Command-Hook für Claude Code: Postfach und Aufträge abholen, Status melden
  auftraege.py Aufträge eines Masters an eine Claude-Sitzung (Verweis auf eine `.hermes/`-Datei)
  status.py    Statusregister `status/<werkzeug>-<kennung>.json` (`arbeitet` | `ruht`)
  chat_register.py   Zuletzt benutzte Chats (nur Metadaten, nur lesend) aus Claude Code, Codex, Hermes
  chat_zuordnung.py  Projekte, bestätigte Zuordnung und Projekt-Vorschläge je Chat
  vorgaenge.py Vorgänge je Paar und Limitfenster (Phase, Kennung, Lauf-Kennung)
  besitz.py    Besitzmarkierung `<thema>.master` (claude / reserviert / codex); `exklusiv_schreiben` legt sie ohne Überschreiben an
  automatik.py Entscheidung (faellige) und Ablauf der Automatik unter der Themensperre; Weg alt oder assistent
  codex_senden.py  Paket bauen und den Auftrag an `codex.exe queue` übergeben
  ack.py       Bestätigung des Zielchats aus den Rollout-Dateien lesen
  signale.py   Kontingente lesen und Claude-Messwerte sicher lokal speichern; Messfehler-Status `messfehler.json`
  claude_messen.py  Claude OAuth-Usage messen und Werte validieren
  codex_messen.py   Codex aktiv messen (`codex.exe app-server`, Prozent und Rücksetzzeit; Prozess immer beendet)
  kurz.py      Master-Status für den Chat (`masterwechsel status`, Alias `kurz`), nur lesend; Bausteine auch für die Übersicht
  uebersicht.py  Übersichtsfenster (tkinter, nur eine Instanz, Linksklick) – nur Oberfläche
  uebersicht_modell.py  Modell der Übersicht ohne Tk: Aufnahme, Repo-Ort, Aktionen mit Rückfragetext
  wartet.py    „Wartet worauf“ je Thema (`masterwechsel warte`), angezeigt im Master-Status
  alle.py      Sammelbefehl `masterwechsel alle kontingent|zurueck` (Merkdatei, Hermes ausgelassen)
  anzeige.py   Texte für Tooltip („Lage … · Claude n % · Codex n % verbraucht“), Menükopf, Benachrichtigung; Schwelle und Automatikschalter
  symbol.py    Bild des Symbols (zwei Balken, Pillow; Statusfarbe auch für die Übersicht)
  leiste.py    Taskleisten-Symbol (pystray) — nur Oberfläche
  cli.py       Befehlszeile `masterwechsel`
tests/         pytest, nur synthetische Dateien
```

Der Kern (`signale`, `anzeige`, `paare`, `vorgaenge`, `besitz`, `automatik`, `codex_senden`,
`ack`, `cli`, `fenster_modell`) nutzt nur die Standardbibliothek; die Fenster (`fenster`, `uebersicht`) brauchen zusätzlich `tkinter`
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
| v0.5.1 | Codex-Kontingent wird aktiv gemessen (`codex_messen`, CLI `codex-messen`, Takt der Leiste alle 5 Minuten und vor der Automatikprüfung); `codex_lesen` nimmt den neueren Stand aus Sitzungsdateien und Messung — Entwicklungsstand |
| **v0.5.0** | Wechselassistent: Ablauf, Postfach, Claude-Hook, Chatliste, Wechselfenster, Menü nach E9, Takt und Windows-Hinweise, Automatik wahlweise über den Assistenten — **veröffentlichter Stand** |
| v0.4.1 | Claude-Katalog mit nativem `claude.exe`; Tests unabhängig von der installierten Claude-Version |
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
