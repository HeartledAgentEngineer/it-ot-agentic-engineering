# Master-Schalter

Zeigt in der Windows-Taskleiste, wie viel vom Nutzungskontingent **Claude Code** und
**Codex** noch übrig ist — beide auf einen Blick. Später soll das Werkzeug auch die Arbeit
von einem „Master"-Agenten an den anderen übergeben, wenn einer ins Limit läuft
(Plan: Releases v0.2–v0.4, siehe unten).

Stand: **v0.1.0** — nur Anzeige, kein Wechsel.

## Was v0.1 kann

| Bedienung | Ergebnis |
|---|---|
| Mauszeiger auf das Symbol | eine Zeile: `Claude 5h 90% · Wo 70% \| Codex 5h 0% · Wo 32%` |
| Linksklick | Windows-Benachrichtigung mit beiden Mastern und Stand-Zeit |
| Rechtsklick | Menü: je Master 5-h- und Wochenwert, Rücksetzzeit, Stand; „Aktualisieren", „Beenden" |

Das Symbol besteht aus zwei Balken (links Claude, rechts Codex). Die Füllhöhe zeigt den
5-Stunden-Verbrauch: Grundfarbe bis 79 %, gelb ab 80 %, rot ab der Schwelle (Standard 97 %).
Die Werte werden alle 60 Sekunden neu gelesen.

## Woher die Zahlen kommen

Beide Quellen sind **lokale Dateien** — kein Netzzugriff, keine Zugangsdaten.

- **Codex** schreibt seine Kontingente in die eigenen Sitzungsdateien
  `~/.codex/sessions/**/rollout-*.jsonl` (Ereignis `token_count`, `limit_id: "codex"`).
  Gelesen werden nur Zeilen mit `"rate_limits"`; übernommen werden nur Zahlen. Neue Werte
  entstehen nur, wenn Codex arbeitet — deshalb steht immer „Stand" dabei. Ein Fenster, dessen
  Rücksetzzeit vorbei ist, erscheint als „zurückgesetzt".
- **Claude Code** gibt die Kontingente an seine Statuszeile weiter
  (`rate_limits.five_hour` / `seven_day`). `masterwechsel statuszeile` speichert nur diese
  Werte in `%LOCALAPPDATA%\master-schalter\kontingent-claude.json`.
  **Einschränkung:** Die Claude-Desktop-App hat die Statuszeile im Test (14.10.2026) nicht
  ausgeführt; das klappt nur in Claude Code im Terminal. Ersatzweg: Werte von Hand eintragen
  (`masterwechsel claude-kontingent …`, siehe unten).

## Einrichten

```powershell
cd "02_Softwareentwicklung_IT\master-schalter"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[leiste,dev]"
```

Statuszeile in Claude Code (z. B. `.claude/settings.local.json`):

```json
"statusLine": { "type": "command", "command": "\"<Pfad>/.venv/Scripts/masterwechsel.exe\" statuszeile" }
```

## Benutzen

```powershell
# Taskleisten-Symbol ohne Konsolenfenster starten
.\.venv\Scripts\pythonw.exe -m master_schalter.leiste

# beide Kontingente in der Konsole
.\.venv\Scripts\masterwechsel.exe status

# Claude-Werte von Hand eintragen (Ersatzweg ohne Statuszeile)
.\.venv\Scripts\masterwechsel.exe claude-kontingent --fuenf 90 --woche 70 --reset-fuenf 2026-10-14T18:40:00Z --reset-woche 2026-10-18T21:00:00Z
```

Einstellungen: `%LOCALAPPDATA%\master-schalter\einstellungen.json`, z. B. `{"schwelle": 90}`
(1–100, sonst gilt 97). Für Tests lassen sich die Ordner per Umgebungsvariable umlenken:
`MASTER_SCHALTER_DATEN`, `MASTER_SCHALTER_CODEX_SESSIONS`.

## Aufbau

```
src/master_schalter/
  signale.py   Kontingente lesen (Codex: Sitzungsdateien, Claude: Statuszeilen-Datei)
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
| **v0.1.0** | Kontingent-Anzeige beider Master (dieser Stand) |
| v0.2.0 | Hermes-Sitzungen benennen, registrieren, nach Abschluss archivieren |
| v0.3.0 | Übergabepaket bauen, Wechsel per Klick |
| v0.4.0 | automatischer Wechsel ab Schwelle (erst nach Anpassung der Workspace-Regeln) |
