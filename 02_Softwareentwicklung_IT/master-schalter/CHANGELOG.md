# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

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
