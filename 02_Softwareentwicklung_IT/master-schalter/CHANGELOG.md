# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[SemVer](https://semver.org/lang/de/).

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
