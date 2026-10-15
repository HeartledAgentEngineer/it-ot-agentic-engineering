# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Der Schalter zeigt außerdem den
aktiven Master, ordnet die Lage der Kaskaden-Matrix zu und legt beim Wechsel ein
technisches Übergabepaket bereit.

Stand: **v0.2.1** — Masteranzeige und Wechsel per Klick (Claude, Codex oder Hermes).

## Bedienung

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile mit Master, Lage und Kontingenten |
| Linksklick | Windows-Benachrichtigung mit beiden Mastern und Stand-Zeit |
| Rechtsklick | Menü mit Master, Lage, Besetzung, Wechsel und Schwelle sowie Kontingenten, Aktualisieren und Beenden |

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
wird erst mit einer späteren Version nach ausdrücklicher Freigabe.

## Woher die Zahlen kommen

Codex wird aus lokalen Sitzungsdateien gelesen. Claude wird über den OAuth-Usage-Endpunkt
gemessen und das Ergebnis lokal zwischengespeichert.

- **Codex** schreibt seine Kontingente in die eigenen Sitzungsdateien
  `~/.codex/sessions/**/rollout-*.jsonl` (Ereignis `token_count`, `limit_id: "codex"`).
  Gelesen werden nur Zeilen mit `"rate_limits"`; übernommen werden nur Zahlen. Neue Werte
  entstehen nur, wenn Codex arbeitet — deshalb steht immer „Stand" dabei. Ein Fenster, dessen
  Rücksetzzeit vorbei ist, wird im Kontingentmenü als „zurückgesetzt" angezeigt. Bis ein
  neuer Messwert vorliegt, zeigen Tooltip und Balken weiterhin 0 %; das ist ein bekannter
  Fehler. Die Lage wertet das Fenster als unbekannt und nennt den Grund.
- **Claude Code**: `masterwechsel claude-messen` fragt
  `https://api.anthropic.com/api/oauth/usage` ab und speichert nur die beiden geprüften
  Prozentwerte und Rücksetzzeiten in `%LOCALAPPDATA%\master-schalter\kontingent-claude.json`.
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

v0.2.1 ändert nur die Master-Auswahl (Hermes dazu); weiterhin keine Chat-Auswahl und kein automatischer Masterwechsel.

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

Einstellungen: `%LOCALAPPDATA%\master-schalter\einstellungen.json`, z. B.
`{"schwelle": 90, "claude_takt_min": 5}`. Die Schwelle liegt bei 1–100 (im Taskleistenmenü
80, 90, 95, 97 oder 100; Standard 97); der Messungstakt liegt bei 1–60 Minuten (Standard 1).
Für Tests lassen sich die Ordner per Umgebungsvariable umlenken:
`MASTER_SCHALTER_DATEN`, `MASTER_SCHALTER_CODEX_SESSIONS`.

## Aufbau

```
src/master_schalter/
  zustand.py   Aktiven Master und letzten Wechsel lokal speichern
  rollen.py    Lage und Besetzung gemäß AGENTS.md bestimmen
  uebergabe.py Technische Metadaten als Übergabepaket schreiben
  wechsel.py   Wechsel unter Sperre ausführen: Paket, dann Zustand
  signale.py   Kontingente lesen und Claude-Messwerte sicher lokal speichern
  claude_messen.py  Claude OAuth-Usage messen und Werte validieren
  anzeige.py   Texte für Tooltip, Menü, Benachrichtigung; Schwelle
  symbol.py    Bild des Symbols (zwei Balken, Pillow)
  leiste.py    Taskleisten-Symbol (pystray) — nur Oberfläche
  cli.py       Befehlszeile `masterwechsel`
tests/         pytest, nur synthetische Dateien
```

Der Kern (`signale`, `anzeige`, `cli`) nutzt nur die Standardbibliothek; `pystray` und
`Pillow` braucht nur die Oberfläche.

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
| **v0.2.1** | Hermes als dritter Master wählbar (Zustand, Menü, CLI; ohne Balken) — dieser Stand |
| v0.2.0 | Masteranzeige, Lage und Besetzung, Wechsel per Klick, technisches Übergabepaket, Menüschwelle |
| v0.3.0 | Automatische Übergabe Claude → Codex (Sebastians Freigabe 15.10.; Abschnitt „v0.3.0 im Detail" des Plans) |
| v0.3.1 | Hermes-Prüfsitzungen benennen, registrieren und nach Abschluss archivieren; Übergabepaket um Issues und Prüfrunden ergänzen |
| v0.4.0 | Automatischer Rückweg Codex → Claude und weitere Ausbaustufen |
