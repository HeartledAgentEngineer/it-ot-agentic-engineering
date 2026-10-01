# Übergabe an die Cloud-Sitzung — 01.10.2026, ~11:00 (vom PC-Master-Chat, Claude)

**Für wen:** eine Claude-Code-Sitzung in der Cloud (nur GitHub, Branch `claude/<thema>`, Label
`cloud`), weil Sebastian unterwegs ist und Remote Control am PC nicht startet.
**Repo:** `HeartledAgentEngineer/it-ot-agentic-engineering`, Projekt
`02_Softwareentwicklung_IT/personal_ai_agent/`. Einstieg: `AGENTS.md`, dann
`02_Softwareentwicklung_IT/personal_ai_agent/CLAUDE.md` und `HANDOVER-CLAUDE-CODE.md`.

## Regeln für die Cloud-Sitzung (bindend)

- **Nur Code, Tests, Doku.** Keine persönlichen Daten (Fotos, Gesichter, Namen, Chats) — die
  liegen nur am PC/Handy, nie im Repo. Echte Läufe startet Sebastian (oder Hermes am PC).
- Arbeiten auf eigenem Branch `claude/<thema>`, **nicht** direkt auf `main`; Übergabe zurück als
  Issue-Kommentar. Prüfbefehl muss grün sein: aus `personal_ai_agent/`
  `backend/.venv/Scripts/python.exe -m pytest tests/ -q` (Cloud: `python -m pytest tests/ -q`
  aus `backend/`), Frontend: `node tests/<t>.js app.js` (Ausnahmen: `test_erzaehlen.js` →
  `erzaehlen.js`, `test_wecken.js` → `wecken.js`, `test_gruppen_quiz.js` → `gruppen_quiz.js`).
- „code + docs" in einem Commit; Frontend-Änderung = `?v=`-Cache-Stand in `index.html` hochzählen.
- Nie `git add -A`; nie force-push.

## Prüfstand (main = `02be6d3`, gepusht, lokal = GitHub)

- Prüfbefehl zuletzt **3320 passed, 1 skipped, Exit 0**; **25 Frontend-Tests** Exit 0.
- Branches: `main`; offen auf GitHub nur `claude/compassionate-edison-oy343r` (bereits gemergt,
  253f389). Lokale Altlasten (`archiv/…`, `backup-…`, `sicherung/…`, `claude/determined-…`,
  `claude/open-plan-md-…`) nicht anfassen.

## Was heute fertig wurde (alle Commits auf main, am Handy aufgespielt bis f3f18a5/93bf8a6)

| Commit | Inhalt |
|---|---|
| a24d06d | Vollbild-Zoom (zwei Finger, Doppeltipp, Mausrad), Rahmen zoomen mit |
| 338b0f0 | Werkzeuge immer an (Knopf weg), Rückfall ohne Werkzeuge vor dem ersten Text |
| 21cc72d / f3f18a5 | 👥 Personen benennen im Gruppenmodus: Dienst `gruppen_quiz`, `/api/gruppen`, `frontend/gruppen_quiz.js`; Übergabe PC→Handy auch in `termux/agent-ensure.sh` |
| 70c696f | Sprechknopf-Overlay `wecken.js` ausgehängt (Wunsch Sebastian; Datei bleibt für A1c) |
| 8f0dde3 | `tools/foto_sortierung/bestand_pruefen.py` (nur Zahlen) + `tools/handy/gruppen_aufs_handy.py` (adb push) |
| 93bf8a6 | Überlauf-Wächter: misst am Handy, meldet nur Messwerte an Logcat + `/api/diagnose/ueberlauf` |
| 6ae3fcb | `bild_beschreiben.py --plan` (Beschreibungen für „Bilder & Videos", die nur einen Sortierplan hat) |
| 02be6d3 | Profil je Person (Beziehung + Erinnerungen), Wortwahl „Vorschlag/Person" statt „Gruppe" — **noch nicht am Handy** (App-Neustart holt es) |

Doku: `docs/changelog-2026-10-01-*.md`, Plan `C:\Users\sebas\.claude\plans\dapper-roaming-rose.md`
(Foto-Gedächtnis, Schritte 1–5; Schritt 1 + 2 fertig).

## Läuft gerade (am PC, nicht anfassen)

- Beschreibungslauf „Bilder & Videos" seit 10:26, `--plan sortierplan_bildervideos.json --kachel
  640 --kacheln-pro-bogen 12 --budget 2.00` (OpenRouter-Konto 2,50 USD laut Hermes; Reserve für
  den Handy-Chat). Reicht für ~9.000 von 10.771 Fotos; Rest nach Aufladen mit demselben Befehl.

## Offene Aufgaben (Reihenfolge = Vorschlag)

Code (Cloud-geeignet):
1. **`personen_gruppieren.py`**: `video_vektoren_upload.jsonl` in `STANDARD_VEKTOREN` aufnehmen
   (heute 1.106 Gruppen/30.937 Gesichter ohne, Hermes 1.340/38.244 mit Upload-Videos); Test anpassen.
2. **`bestand_pruefen.py`**: Formatierungsfehler — in der Beschreibungszeile ersetzt
   `.replace(".", ",")` auch Punkte in Dateiname und Tausendern („bild_beschreibungen,jsonl:
   8,299 Zeilen"). Nur die Kostenzahl umformatieren; Test ergänzen.
3. **Rückweg Handy → PC** für `personen_bestaetigt.json`, `personen_vorgaben.json`,
   `personen_profile.json` (Handy schreibt sie unter `~/foto_sortierung`; der nächste
   Gruppierlauf am PC braucht sie). Vorschlag: Handy legt Kopien in den kabel-lesbaren
   `hermes_diag`-Ordner (wie `start-termux.sh` die Diagnose), PC-Werkzeug `tools/handy/…holen.py`
   per adb (Muster `diag_holen.py`), Trockenlauf Standard, Sicherung `*.vorher`.
4. **Pfad Beschreibungen → Handy**: `bild_beschreibungen.jsonl` in die Übergabeliste
   (`termux/agent-ensure.sh`, `start-termux.sh`, Wächter in `test_uebergabe_uebernehmen.py` über
   Dienst-Konstanten) — erst wenn ein Handy-Dienst sie liest (Plan Schritt 4/5).
5. **Plan Schritt 3 — Anlass-Quiz** (Anlässe benennen, 4–6 Bilder, Gedanke je Anlass, Ebenen) und
   Erinnerung **je Foto** aus dem Vollbild (Sebastian: „zu dem Original springen, was
   reinsprechen") — `geschichten.jsonl` der Erzähl-Diashow nutzen (`/api/erzaehlen/geschichten`).
6. **Brücke `gesichter_katalog.json`** (benannte Person wird auf neuen Handy-Fotos erkannt) —
   braucht ein Merkmal je Gesicht; eigener Entwurf zuerst.

Nur mit Sebastian / am PC:
7. Gruppen-Dateien sind seit 10:11 am Handy (Übernahme belegt). **pCloud-Schlüssel noch nicht**
   übernommen → Gesichtskacheln leer, bis Sebastian das Termux-Widget „agent" antippt
   (`agent-ensure.sh` übernimmt den Schlüssel nicht — evtl. Aufgabe: dort nachziehen, Muster
   `start-termux.sh` Zeilen ~115–177, nur `PCLOUD_TOKEN`/`PCLOUD_HOST`).
8. Überlauf-Wächter auswerten, sobald der Darstellungsfehler wieder auftritt:
   `adb shell cat /sdcard/Download/hermes_diag/ueberlauf.jsonl` (auch über WLAN-Debugging +
   VPN-Tunnel möglich).
9. Remote Control am PC: „initialization failed" (abgelaufene Anmeldung / Ordnerschlüssel in
   der Claude-Konfiguration) — Sebastian in der App.
10. Repo liegt in einem pCloud-synchronisierten Ordner → Konfliktkopie
    `tools/foto_sortierung/bild_beschreiben [conflicted 2].py` (untracked, nicht löschen ohne OK).
11. Lücken laut `bestand_pruefen.py`: 25 Videos „Bilder & Videos" ohne Gesichter-Lauf, 3 Fotos
    der Upload-Sammlung ohne Beschreibung.
12. Wunsch: tägliche **Tagebuch-Runde** am Handy (neue Fotos/Events des Tages, Erinnerung dazu).

## Bus / Hermes

Hermes kennt den Stand (Agentenbus, 01.10. ~10:00 und ~10:35). Er startet keinen zweiten
Beschreibungslauf parallel. Weckwort (A1c) ist Hermes' Schritt.
