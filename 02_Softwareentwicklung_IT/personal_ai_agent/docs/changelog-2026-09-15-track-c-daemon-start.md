# Änderung 15.09.2026 — Track C: Inbox-Daemon wird jetzt mitgestartet

## Problem (Live-Beobachtung Sebastian)

Erste Übergabe „an lokalen Hermes übergeben" am Handy lief ins Leere:

```
Hermes übernimmt die Nachricht
bearbeitet die Nachricht mit Modell DeepSeek V4.1 Flash
Hermes denkt nach, internes Reasoning
Hermes hat geantwortet — aber keine Antwort geschickt
```

Am Ende kam keine brauchbare Antwort, nur ein Rest mit Trennlinie.

## Ursache

Track C (lokaler Hermes) antwortet **nicht direkt aus dem Request**, sondern über
die **Datei-Inbox**: `~/hermes_inbox/`

| Datei | Rolle |
|---|---|
| `auftraege.jsonl` | Der Server legt den Auftrag hier ab |
| `status.jsonl` | Der Daemon meldet Zwischenschritte (→ „Hermes denkt nach …") |
| `antworten.jsonl` | Der Daemon schreibt die **fertige Antwort** hierher |

Verarbeitet wird die Inbox von **`backend/hermes_inbox_daemon.py`** (Endlosschleife,
3-s-Takt, optional `--einmal` für einen Durchgang).

**`start-termux.sh` hat diesen Daemon nie gestartet.** Der Auftrag wurde also
abgelegt und nie bearbeitet — genau das Bild „denkt nach … und dann nichts".
Das Skript endet außerdem mit `exec python -m uvicorn …`; alles nach dieser Zeile
wird nie ausgeführt, der Daemon-Start musste deshalb **davor**.

## Fix

`start-termux.sh` startet den Daemon jetzt **idempotent** direkt vor dem
`exec uvicorn`:

```bash
DAEMON="hermes_inbox_daemon.py"
if pgrep -f "$DAEMON" >/dev/null 2>&1; then
    echo "Inbox-Daemon läuft bereits — Track C bereit."
else
    mkdir -p "$HOME/hermes_inbox"
    nohup python "$DAEMON" >> "$HOME/hermes_inbox/daemon.log" 2>&1 &
    ...
fi
```

- **Idempotent:** Läuft er schon, wird nichts gestartet — sonst würden zwei
  Daemons dieselben Aufträge doppelt abarbeiten.
- **Log:** `~/hermes_inbox/daemon.log`
- **Hinweis bei Fehlschlag:** Prüfbefehl `python backend/hermes_inbox_daemon.py --einmal`

## Verifikation

```bash
bash -n start-termux.sh          # Syntax: Exit 0
```

Auf dem Handy nach dem Widget-Start:

```bash
pgrep -af hermes_inbox_daemon    # muss den Prozess zeigen
tail -5 ~/hermes_inbox/daemon.log
```

Dann eine Coding-Aufgabe senden und „↪️ An lokalen Hermes übergeben" drücken:
erwartet sind laufende Zwischenmeldungen **und** eine Antwort in
`~/hermes_inbox/antworten.jsonl`, die im Chat erscheint.

## Zusätzlich (Frontend, gleicher Tag)

Die **leere Antwort-Bubble** direkt nach dem Senden ist weg: Die Blase wird
verborgen angelegt und erst beim ersten echten Inhalt eingeblendet
(`finishReply` prüft den tatsächlich gerenderten Text). Der Fortschritt gehört
in die untere `#loading`-Bubble. Cache-Bump `?v=20260915B`.

## Noch offen (nächster Schritt)

- **Antwort-Sichtbarkeit doppelt absichern:** Wenn der Daemon fertig ist, aber
  kein Text im Antwort-Kasten stand, soll eine **klare Fehlermeldung** kommen
  statt Stille (Teil des Track-B-/Fehlermeldungs-Umbaus).
- **Track B (Auftragsbuch)** soll laut Sebastian **nicht mehr in der UI**
  erscheinen (keine Nummern) — nur noch intern fürs Logging.
