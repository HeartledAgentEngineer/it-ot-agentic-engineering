# Handy-Hermes-Routing (Track C) — Programmierauftrag direkt auf dem Geraet (automatisch)

**Zweck:** Wird ein Coding-Auftrag erkannt und der PC-Hermes (Track A) ist nicht
erreichbar, startet das Backend den Auftrag **automatisch auf dem lokalen
Hermes-CLI (Termux)** — ohne manuelles Widget/„weiter". Der lokale Agent arbeitet
als Coding-Agent im Projektordner und seine **Gedanken und Werkzeug-Schritte
erscheinen live** als Chat-Blasen (Status-Meldungen) im Frontend. Erst wenn auch
der lokale Hermes fehlt/scheitert, faellt der Auftrag ins Buch (Track B).

## Reihenfolge (voller Durchlauf)
1. **Track A** — PC-Hermes (im WLAN erreichbar) → Antwort direkt.
2. **Track C** — lokaler Hermes-CLI auf dem Handy (va. unterwegs ohne PC) →
   startet die Aufgabe im Hintergrund, strahlt Gedanken + Ergebnis live aus.
3. **Track B** — Auftragsbuch (wenn beides nicht verfuegbar ist).

## Wie Track C arbeitet (Laufzeit)
- Der Chat-Endpoint (`chat.py`) prueft: PC-Hermes erreichbar? Wenn nicht:
  ist `hermes`+`tmux` auf dem Handy installiert?
- `_starte_lokale_hermes()` legt den Auftrag direkt als `laeuft` an
  (`anlegen_als_arbeitender`) — wichtig, damit der Watcher ihn **nicht** parallel
  claimt — und startet den Stream in einem **Daemon-Thread**.
- `hermes_local.stream_auftrag()` startet `hermes chat` **interaktiv** (ohne
  Einzel-Query) in einer **tmux-Pane** (TTY). Der CLI rendert seine
  Zwischengedanken (Hermes-Boxen) und Werkzeug-Schritte (`💻 $ ls …`) **live**
  in die Pane.
- Das Backend pollt die Pane, dedupliziert die Inhalte und schreibt jeden Schritt
  als **Status-Meldung** ins Auftragsbuch — der Kanal, den das Frontend ohnehin
  alle 3 s pollt und als Chat-Blase anzeigt.
- Am Ende wird die letzte Hermes-Box (die Antwort) gelesen und per
  `ergebnis_eintragen(…, erfolg=True)` als `fertig` geschlossen.

## Live-Blase bleibt im Verlauf (nicht nur fluechtig)
- Die Live-Meldungen waren bisher **nur** im Client-Speicher (`state.messages`)
  und im Auftragsbuch — nach einem Neuladen fehlten die von Hermes gekommenen
  Nachrichten im Gespraechsverlauf.
- Jetzt wird jeder Coding-Auftrag, der aus einem Gespraech entsteht, an dessen
  `conversation_id` gebunden (`setze_chat_verknuepfung()`). Jede Hermes-Meldung
  (Status-Meldung + Ergebnis) wird danach **zusätzlich** in den persistenten
  Verlauf (`conversations.json`) geschrieben (`_in_verlauf_anhaengen()` →
  `verlauf_nachricht_anhaengen()` in `chat.py`).
- Ergebnispunkte: (1) Der Verlauf ist ein Merkmal des Servers und ueberlebt
  Neuladen/Neustart. (2) Die Uebernahme ist eingeschlossen gegen Fehler und
  greift nur, wenn der Auftrag mit einem Gespraech verknuepft ist — Auftraege,
  die direkt aus dem Auftragsbuch stammen, beruehren den Verlauf nicht.
- Die Sperre `_verlauf_sperre` verhindert, dass das gleichzeitige Schreiben
  des Chat- und des Auftrags-Hintergrund-Threads die JSON-Datei zerhackt.

## Live-Ausgabe: durchgehender Stream statt 3s-Polling
- Der Stream-Endpoint `/api/chat/stream` endet bei Track C nicht mehr bei einer
  sofortigen Bestätigung. Der Generator `_strom_auftrag_live()` (`chat.py`)
  haelt die Verbindung **offen**: Er liest das Auftragsbuch periodisch und
  reicht jede neue Hermes-Status-Meldung (Gedanke, Werkzeug-Schritt) als
  weiteres Antwort-Häppchen durch; `fertig`/`fehler` schliesst den Stream mit
  einem `done` (Flag `auftrag_strecke: true`) samt Endergebnis.
- Damit ist die Kette **Frontend → Backend → lokaler Hermes** eine einzige
  durchgehende Verbindung statt „Request schliessen, dann 3s-Polling".
- Der 3s-Poller (`startAuftragTracking`) bleibt als **Rueckversicherung**: Er
  startet nur, wenn der Stream die Strecke nicht selbst bis zum Abschluss
  gefuehrt hat (z. B. Verbindungsabriss) — sonst wuerden die Gedanken doppelt
  angezeigt.
- Gegen Browser-/Proxy-Timeouts sendet der Stream alle ~15 s einen
  SSE-Kommentar (`: keepalive`), den der Client ignoriert.

## Live-Eingabe waerend der Bearbeitung
- Der lokale Hermes bleibt im **interaktiven Modus** offen; eine **Job-Registry**
  (`HermesRegistry` in `hermes_local.py`) haelt die offene tmux-Session pro
  Auftrag.
- Neuer Endpoint `POST /api/auftraege/{id}/eingabe`: Der Nutzer sendet damit
  **waerrend des Laufs** einen Kommentar direkt an den laufenden Agenten
  (`tmux send-keys`).
- Der Kommentar wird als Status-Meldung (`📨 Kommentar an Agent: …`) in den
  Chat-Tracker geschrieben. Ist der Auftrag schon fertig / kein Job mehr da,
  antwortet der Endpoint mit **409** statt zu haengen.
- **Gedaechtnis-Lernen:** Nur Kommentare mit persoenlichem Mehrwert
  (`hat_mehrwert()`, z. B. keine reinen "weiter/ok") werden parallel durch das
  persoenliche ChromaDB-Gedaechtnis gelernt — damit der eigene Assistent
  mitlernt. Der Hermes bekommt jeden Kommentar, das Filter entscheidet nur
  ueber das Lernen.

## Warum tmux + Pane-Lesen statt blockierendem Aufruf
- Ein blockierender `subprocess.run("hermes chat -q …")` liefert erst nach
  Minuten das Endergebnis als einen Textbrocken — ohne jeden Zwischenstand.
- Im tmux rendert der CLI seine Gedanken in Echtzeit in die Pane; das Backend
  liest sie mit `capture-pane`, dedupliziert nach Inhalt (Box-Volltext) und
  meldet sie live weiter.
- Der erste Auftrag wird nach dem Start `send-keys` an die Offen-Session
  geschickt (statt `--query-file`), damit die Session interaktiv bleibt und
  Folge-Eingaben moeglich sind.

## Dateien
- `backend/app/services/hermes_local.py` — interaktiver Live-Job, `stream_auftrag()`
  + `HermesRegistry` (offene tmux-Session pro Auftrag) + `hat_mehrwert()` (neu).
- `backend/app/router/auftraege.py` — neuer Endpoint `POST /{id}/eingabe`
  (L er laufenden Hermes + Gedaechtnis-Lernen).
- `backend/app/router/chat.py` — Weiche: erst PC (Track A), dann lokaler Live
  (Track C), sonst Buch (Track B); helper `_starte_lokale_hermes`.
- `backend/app/models.py` — Modell `EingabeCreate` (neu).
- `backend/app/services/auftrag_service.py` — `anlegen_als_arbeitender()` (neu),
  `setze_chat_verknuepfung()` + `_in_verlauf_anhaengen()` (Verlauf-Uebernahme).

## Voraussetzung
Der **Hermes-CLI muss auf dem Handy (Termux) installiert** und im `PATH` sein
(`hermes`-Befehl); zusaetzlich wird **tmux** benoetigt (verfuegbar in Termux).
Fehlt eines, greift Track C nicht und der Auftrag geht ins Buch zurueck.