# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Der Schalter zeigt außerdem den
aktiven Master, ordnet die Lage der Kaskaden-Matrix zu und legt beim Wechsel ein
technisches Übergabepaket bereit.

Stand: **v0.3.0** — Automatische Übergabe Claude → Codex für eingeschaltete Paare (die Automatik ist standardmäßig aus).

## Bedienung

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile mit Master, Lage und Kontingenten |
| Linksklick | Windows-Benachrichtigung mit beiden Mastern und Stand-Zeit |
| Rechtsklick | Menü mit Master, Lage, Besetzung, Wechsel, Schwelle, Automatik, Übergabe-Chats, Kontingenten, Aktualisieren und Beenden |

Das Symbol besteht aus zwei Balken (links Claude, rechts Codex). Die Füllhöhe zeigt den
5-Stunden-Verbrauch: Grundfarbe bis 79 %, gelb ab 80 %, rot ab der Schwelle (Standard 97 %).
Die Anzeige wird standardmäßig jede Minute aktualisiert. Die Claude-Messung läuft beim
Start, nach „Aktualisieren" und anschließend im eingestellten Takt.

Im Menü „Master wechseln" kann Claude, Codex oder Hermes ausgewählt werden (Hermes = Lage 3 der
Kaskaden-Matrix; kein eigenes Abo-Kontingent, deshalb kein Balken und kein weißer Punkt). Der Wechsel legt
ein Markdown-Paket unter .hermes/uebergabe/ ab und zeigt den Paketnamen an. Der neue
Master liest es, wenn Sebastian ihn darauf hinweist. v0.2 startet keinen Chat und schreibt
in keinen Chat. Die Schwelle lässt sich im Menü „Wechsel-Schwelle" auf 80, 90, 95, 97
oder 100 % setzen. Sie steuert die Lage und die rote Anzeige; automatisch gewechselt
wird nur, wenn die Automatik ausdrücklich eingeschaltet ist (siehe unten).

## Automatische Übergabe Claude → Codex (v0.3.0)

Die Automatik ist **standardmäßig aus** (`einstellungen.json`, Feld `automatik`). Eingeschaltet
wird sie im Menüpunkt „Automatik Claude → Codex" (Häkchen) oder in der Datei selbst. Sie greift
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
  ändern. Bei abgelaufener Anmeldung bleibt der bisherige Messwert mit Stand erhalten; Claude Code
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

v0.3.0 ergänzt die automatische Übergabe; die Automatik bleibt standardmäßig aus, bis sie im Menü eingeschaltet wird.

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
| v0.1.1 | Kontingentwerte nach Reset, Messalter und Anzeigegrenzen korrigieren |
| v0.1.0 | Kontingent-Anzeige beider Master |
| **v0.3.0** | Automatische Übergabe Claude → Codex: Paare, sicherer Übergabepunkt, Handschlag, Sperren, ACK, Datenschutz-Paket (Sebastians Freigabe 15.10.; Abschnitt „v0.3.0 im Detail" des Plans) — **dieser Stand**. Standardmäßig aus. |
| v0.2.1 | Hermes als dritter Master wählbar (Zustand, Menü, CLI; ohne Balken) |
| v0.2.0 | Masteranzeige, Lage und Besetzung, Wechsel per Klick, technisches Übergabepaket, Menüschwelle |
| v0.3.1 | Hermes-Prüfsitzungen benennen, registrieren und nach Abschluss archivieren; Übergabepaket um Issues und Prüfrunden ergänzen |
| v0.4.0 | Automatischer Rückweg Codex → Claude und weitere Ausbaustufen |
