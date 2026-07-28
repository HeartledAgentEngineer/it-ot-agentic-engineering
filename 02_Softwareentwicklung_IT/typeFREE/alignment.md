# Alignment: typeFREE — „Immer einsatzbereit"

**Datum:** 2026-07-28 · **Projekt:** `02_Softwareentwicklung_IT/typeFREE` · **Phase:** 2 von 8

---

## Ausgangslage (belegt, nicht vermutet)

Diagnose vom 2026-07-28, jeder Punkt durch Code oder Windows-Protokoll nachgewiesen:

| Befund | Beleg |
|---|---|
| Mikrofon dauerhaft belegt | `typefree.py:463` — Stream wird beim Start geöffnet und erst beim Beenden geschlossen |
| Speicherleck | Windows Error Reporting, 21.07.2026 15:39: `RADAR_PRE_LEAK_64` für `typeFREE.exe` |
| Ursache des Lecks | `audio_frames` (`typefree.py:327`) wächst unbegrenzt, solange `is_recording` wahr ist — ~230 MB/h |
| Verpasstes Loslassen | `typefree.py:445-447` verwirft KEY_UP, wenn ein Modifier vorher losgelassen wurde |
| Windows tötet die App | Winsrv 10001, 20.07.2026 21:55 (+2 weitere): „Von der folgenden Anwendung wurde versucht, das Herunterfahren zu unterbinden: typeFREE.exe." |
| Autostart kaputt | Registry-Wert ohne Anführungszeichen bei einem Pfad mit Leerzeichen (`typefree.py:223`) |
| Schlüssel fehlen beim Autostart | Weder `OPENAI_API_KEY` noch `GROQ_API_KEY` als dauerhafte Umgebungsvariable gesetzt; `python-dotenv` nicht installiert → `.env` wird nie gelesen |
| Gerätefehler unsichtbar | `audio_callback` (`typefree.py:324`) ignoriert den `status`-Parameter |
| Abstürze spurlos | `console=False` (`typeFREE.spec:32`), kein Logging, kein `sys.excepthook`, alle Threads sind Daemon-Threads |
| Laufende EXE veraltet | `dist/typeFREE.exe` vom 22.05.2026, Quellcode vom 14.07.2026 |

## Ziel

typeFREE ist ohne Zutun verfügbar: Es startet bei der Anmeldung mit Admin-Rechten, kommt nach Schlaf- und Ruhezustand von selbst zurück, startet sich nach einem Absturz selbst neu und belegt das Mikrofon nur während einer Aufnahme. Geht etwas schief, sieht Sebastian es sofort im Klartext — **ein Diktat darf nie mehr stillschweigend verloren gehen.**

## Nicht-Ziele

- **Umschalt-Modus** („einmal drücken zum Starten/Beenden") — gewünscht, aber bewusst auf einen späteren Slice verschoben
- **Lokale Transkription** (`faster-whisper`) — eigener Slice, erst nach Vergleichstest
- **Android-Companion** — bleibt außen vor
- **Modul-Aufteilung** in mehrere Dateien — erst wenn `typefree.py` 800 Zeilen überschreitet
- **Wechsel zu EU-Anbietern** — nur notiert, nicht in diesem Slice
- **Guthaben-Abfrage über die OpenAI-Kosten-Schnittstelle** — verworfen, siehe unten

## Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | Erster Umbau = „immer einsatzbereit": Autostart, Selbstheilung, Absturzschutz, Mikrofon-Überwachung | Der Hauptleidensdruck ist, dass die App unbemerkt weg ist |
| 2 | **Mikrofon nur während der Aufnahme öffnen** | Das blaue Dauersymbol verschwindet, das Gerät wird für andere Programme frei — ~0,2 s Startverzögerung wird akzeptiert |
| 3 | Selbstheilung über die **Windows-Aufgabenplanung** (Anmeldung, Aufwachen, regelmäßige Prüfung) | Bordmittel, kein zweites Programm, „Mit höchsten Privilegien" löst zugleich das Admin-Problem |
| 4 | Nach **3 Fehlstarts in Folge** aufgeben und einmalig im Klartext melden | Verhindert eine stille Endlosschleife bei kaputtem Schlüssel |
| 5 | typeFREE zieht in einen **eigenen Programmordner** unter `%LOCALAPPDATA%` | Entkoppelt vom Desktop-Projektordner — Aufräumen kann den Autostart nicht mehr zerstören |
| 6 | Umzug per **Ordner kopieren + `einrichten.cmd`** | Ein Ordner, ein Doppelklick, kein Python auf dem Zielrechner |
| 7 | API-Schlüssel in einer **`.env` neben der EXE**, nie in die EXE gebacken | Portabel und ohne Schlüssel im Binärartefakt; `.env` ist bereits von Git ausgeschlossen (geprüft) |
| 8 | `.env` wird mit **eigenem Code** gelesen, nicht mit `python-dotenv` | Fünf Zeilen statt einer zusätzlichen Abhängigkeit, EXE bleibt schlank |
| 9 | **Keine Datenpakete oder digitale Null für 3 Sekunden** → Mikrofon automatisch neu verbinden; erst bei Misserfolg roter Alarm | Erkennt das tote Gerät, ohne bei Denkpausen Fehlalarm zu schlagen |
| 10 | Unterscheidungsmerkmal ist **das Gerät, nicht die Lautstärke** | Ein echter Raum liefert immer Grundrauschen; exakte Null bedeutet zuverlässig „abgeklemmt" |
| 11 | **Loslassen beendet die Aufnahme. Immer.** Auch wenn ein Modifier zuerst losgelassen wird | Behebt das „Abrutschen"; Voraussetzung für den Wechsel auf eine Strg-Kombination |
| 12 | Harte Obergrenze **10 Minuten**, Text wird trotzdem gesendet | Stoppt das Speicherleck, ohne ein reales Diktat abzuschneiden |
| 13 | Neuer Standard-Hotkey **Strg + Shift + Ä** | F5 kollidiert mit der Funktionstasten-Belegung des Rechners |
| 14 | Aufnahme-Modus bleibt **Halten** | Umschalt-Modus ist gewünscht, aber ein eigener Slice |
| 15 | **Nur Fehler** werden gemeldet, der Aufnahme-Ballon entfällt | Das grüne Tray-Icon reicht als Rückmeldung für den Normalfall |
| 16 | **Guthaben leer** wird an der fehlgeschlagenen Anfrage erkannt → rotes Icon + Klartext | Zuverlässiges Signal ohne Zusatzabfrage und ohne zweiten Schlüssel |
| 17 | Bei leerem Guthaben **weiterlaufen**, nur rot bleiben | Nach dem Aufladen sofort wieder einsatzbereit, ohne Neustart |
| 18 | **Kosten selbst mitrechnen** und im Tray-Menü anzeigen | Audiolänge ist exakt bekannt, Whisper kostet $0,006/Min sekundengenau; Groq liefert Token mit |
| 19 | **Groq bleibt**, Anweisung wird umgebaut: Füllwörter raus, **Verhörer aus dem Zusammenhang korrigieren**, **Umgangssprache und Slang unangetastet lassen** | Die Verhörer-Korrektur ist der eigentliche Mehrwert; die fehlende Slang-Schonung ist der aktuelle Ärger |
| 20 | **Eine Datei bleibt es**, nur die Startbefehle wandern in `main()` | Das Problem sind die Seiteneffekte beim Einlesen, nicht die Zeilenzahl — Aufteilen bringt für Tests nichts |
| 21 | **Vier Tests**: Hotkey-Logik, Mikrofon-Wächter, Zeitgrenze, Autostart-Befehl | Decken genau die Fehler ab, die im Protokoll nachweisbar sind |
| 22 | Umsetzung in **zwei Durchgängen**, danach `/code-review` (durch Sebastian ausgelöst) | Jeder Teil einzeln testbar; ein unabhängiger Prüfer findet, was der Autor übersieht |
| 23 | **Tray-Icon mit Farbcodierung bleibt unverändert** | Ausdrücklich gewünscht |
| 24 | **README bekommt einen Abschnitt „Warum nicht Win+H"** | Beantwortet die naheliegendste kritische Rückfrage im Bewerbungsgespräch |

## Slice-Zuschnitt

**Durchgang 1 — Stabilität und Mikrofon**
`main()`-Umbau · `.env`-Leser · Mikrofon nur bei Bedarf · 3-Sekunden-Wächter mit Neuverbindung · Loslassen-Fix · 10-Minuten-Grenze · Logdatei und Fehler-Abfänger · Herunterfahren nicht mehr blockieren · nur Fehler-Meldungen · Hotkey-Standard `Strg+Shift+Ä` · vier Tests

**Durchgang 2 — Autostart, Umzug und Feinschliff**
Programmordner unter `%LOCALAPPDATA%` · `einrichten.cmd` · Aufgabenplanung · 3-Fehlstart-Regel · Kosten mitrechnen · Guthaben-Erkennung · neue Groq-Anweisung · README-Abschnitt

## Verworfene Alternativen

| Alternative | Verworfen, weil |
|---|---|
| Registry-`Run`-Schlüssel reparieren | Kann sich nicht selbst erhöhen — ohne Admin-Rechte ist der Tastatur-Hook vor Admin-Fenstern blind |
| UAC-Manifest in die EXE bauen | Fragt bei jedem Start nach und lässt sich per Autostart gar nicht starten |
| UAC abschalten | Sicherheitsloch für das gesamte System |
| Schlüssel als dauerhafte Umgebungsvariable | Weniger portabel — beim PC-Wechsel müsste alles neu gesetzt werden |
| Zweites Wächter-Programm | Zwei laufende Programme statt einem, ohne Vorteil gegenüber der Aufgabenplanung |
| Füllwörter per fester Liste statt Groq | Entfernt „ähm", repariert aber **keine Verhörer** — der eigentliche Mehrwert ginge verloren |
| OpenAI-Kosten-Schnittstelle `/v1/organization/costs` | Braucht einen separaten Admin-Schlüssel und liefert nur Tagessummen statt Kosten pro Diktat |
| Aufteilung in mehrere Python-Dateien | Löst kein Testproblem, das der `main()`-Umbau nicht schon löst; die begründete Ein-Datei-Bauweise ist Portfolio-Substanz |
| Auf Win+H umsteigen | Schickt die Stimme ebenfalls in die Cloud (Microsoft Azure) und kann weder Verhörer korrigieren noch einen eigenen Hotkey belegen |
| Aufnahme bei leerem Guthaben ganz blockieren | Nach dem Aufladen wäre ein Neustart nötig |

## Annahmen (unbestätigt)

- [ ] Sebastian baut die EXE nach dem Umbau selbst neu (`pyinstaller typeFREE.spec`)
- [ ] Der Tastatur-Hook braucht tatsächlich Admin-Rechte — die README behauptet es, gemessen wurde es nie
- [ ] Wie typeFREE **heute** an die API-Schlüssel kommt, ist weiterhin ungeklärt (nicht als Umgebungsvariable, `.env` wird nicht gelesen)
- [ ] Die neue Groq-Anweisung gehört in Durchgang 2, nicht in Durchgang 1
- [ ] Der Programmordner unter `%LOCALAPPDATA%` liegt in keiner Cloud-Synchronisation
- [ ] Ein Diktat dauert im Alltag deutlich unter 10 Minuten

## Offene Punkte

- [ ] **Win+H selbst testen** — denselben Absatz einmal mit Win+H, einmal mit typeFREE diktieren, danach den Lokal-Slice neu bewerten
- [ ] **Umschalt-Modus** („einmal drücken zum Starten/Beenden") mit Auswahl im Tray-Menü
- [ ] **Lokale Transkription** mit `faster-whisper` — `small` läuft ~6× Echtzeit auf CPU, `large-v3` ~3×; spürbar langsamer als die API, dafür kostenlos und ohne Datenabfluss
- [ ] **EU-Anbieter** als Mittelweg prüfen (deutsches Whisper-Hosting, Azure OpenAI Westeuropa)
- [ ] **„Voiceli" von „Everlast AI"** — Produkt konnte nicht verifiziert werden, Link fehlt
- [ ] **Datenschutz auf dem Arbeitgeber-PC** klären, bevor dort diktiert wird
- [ ] Bei über 800 Zeilen `typefree.py` gezielt aufteilen

## Risiken aus der Devil's-Advocate-Runde

| Einwand | Bewertung | Umgang |
|---|---|---|
| Endlose Neustart-Schleife bei kaputtem Schlüssel | zählt nicht (formal), praktisch entschärft | Entscheidung 4: Abbruch nach 3 Fehlstarts mit Meldung |
| Autostart hängt am Desktop-Pfad und bricht beim Aufräumen | zählt nicht (formal), praktisch entschärft | Entscheidung 5: eigener Programmordner unter `%LOCALAPPDATA%` |
| Windows kann Diktat mit Win+H selbst | **zählt** | Trotzdem weiterbauen; Vergleichstest steht aus; README-Abschnitt begründet die Entscheidung |

## Erfolgskriterien für Phase 5

- [ ] Nach einem PC-Neustart ist das Tray-Icon ohne jedes Zutun da
- [ ] Nach Zuklappen und Aufwachen funktioniert `Strg+Shift+Ä` **sofort** beim ersten Versuch
- [ ] typeFREE über den Task-Manager beenden → binnen 5 Minuten ist es von selbst zurück
- [ ] Mikrofon in den Windows-Einstellungen deaktivieren → rotes Icon **und** Klartext-Meldung binnen 3 Sekunden
- [ ] Beim Drücken denkt Sebastian 8 Sekunden nach, ohne zu sprechen → **kein** Fehlalarm
- [ ] `Strg` vor `Ä` loslassen → Aufnahme stoppt trotzdem und der Text wird eingefügt
- [ ] Windows herunterfahren → kein Winsrv-10001-Eintrag „versucht das Herunterfahren zu unterbinden" mehr
- [ ] Das blaue Windows-Mikrofonsymbol erscheint **nur während** einer Aufnahme
- [ ] Das Tray-Menü zeigt die bisher angefallenen Kosten
- [ ] Ordner auf einen USB-Stick kopieren, `einrichten.cmd` auf einem zweiten PC ausführen → typeFREE läuft dort
- [ ] Ein diktierter Satz mit Slang behält seinen Ton, aber „ähm" ist entfernt
- [ ] Alle vier automatischen Tests laufen grün

---

*Erstellt mit dem Skill `grill-me`. Nach Abschluss von Phase 8 löschen (Phasendateien werden aufgeräumt).*
