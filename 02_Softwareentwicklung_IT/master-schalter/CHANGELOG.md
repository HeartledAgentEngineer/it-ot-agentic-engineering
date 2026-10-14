# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

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
