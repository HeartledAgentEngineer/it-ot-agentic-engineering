# Changelog 2026-09-15 — Auftragsbuch: verwaiste „läuft"-Einträge + Fehl-Eintrag korrigiert

Anlass: Beim Nachsehen zum Stream-Fix fiel auf, dass der Auftrag des parallelen
Coding-Agenten im Buch als **Fehler** stand, obwohl seine Arbeit erfolgreich
war — und dass insgesamt **45 Einträge dauerhaft auf `laeuft`** hingen.

## Fund 1: 45 „läuft"-Leichen

**Ursache:** Der Worker eines Auftrags läuft in einem Thread **im
Serverprozess**. Startet der Server neu (Widget, `termux/neu-start-nach-lauf.sh`)
oder stirbt er, kann dieser Thread seinen Status nie mehr finalisieren → der
Eintrag bleibt für immer auf `laeuft`. Genauso beim früheren festen
900-s-Deckel: Der Server gab nach 900 s auf, der Agent lief weiter.

**Wirkung:** Das Buch behauptete „es läuft noch" für 45 Aufträge, obwohl kein
`hermes chat`-Lauf und keine tmux-Session existierte — ein Statusbild, das
niemandem hilft.

**Aufgeräumt:** Alle 45 auf `fehler` gesetzt (gleiche Semantik wie der
App-eigene Abbruch-Weg `POST /api/auftraege/<id>/abbrechen`), mit Begründung im
Feld `korrigiert`. Der Chat-Verlauf blieb unangetastet (append-only-Regel).
Backup: `~/auftraege.json.bak-verwaiste-<ts>`.

**Damit es nicht wiederkommt — neue Start-Aufräumung:**
`auftrag_service.verwaiste_auftraege_schliessen()` (in `app/main.py`, lifespan)
schließt beim Serverstart alle zurückgebliebenen `laeuft`-Einträge. Beim Start
kann kein Worker laufen, solche Einträge sind also eindeutig verwaist.
Bewusst **ohne** `ergebnis_eintragen`: dessen Verlauf-Übergabe würde den Chat
mit Aufräum-Notizen fluten — hier wird nur das Buch bereinigt.

## Fund 2: erfolgreicher Lauf als „Fehler" verbucht

Auftrag `2d4fade6` (der Coding-Agent, der den Stream-Fix baute):
- Buch sagte: `fehler` · „Timeout nach 900s: keine Antwort der aktiven Session"
  · **genau 20** Statusmeldungen (= die alte Kappung, deshalb war der Live-Strom
  verstummt).
- Tatsächlich: Der Agent arbeitete weiter, seine Antwort landete in
  `~/hermes_inbox/antworten.jsonl`, seine Arbeit ist Commit `37ef769`.
  Der Server-Deckel schlug 20 Sekunden **vor** seinem Abschluss zu.

**Korrigiert:** Eintrag auf `fertig` mit der echten Daemon-Antwort; die alte
Meldung + Grund stehen unter `korrigiert`. Backup:
`~/auftraege.json.bak-korrektur-<ts>`.

## Verifikation

- `tests/test_verwaiste_auftraege.py` (3 Tests): nur `laeuft` wird geschlossen,
  `fertig`/`offen`/`fehler` und die Gedanken-Spur bleiben unangetastet, leeres
  Buch harmlos. Grün.
- **Live-Beweis der Verdrahtung:** ein Dummy-`laeuft`-Eintrag ins echte Buch
  gesetzt → Server neu gestartet → Eintrag wurde beim Start auf `fehler` mit
  „Abgebrochen/verwaist: Server-Neustart waehrend des Laufs — automatisch
  bereinigt am …" gesetzt. Dummy danach wieder entfernt (216 → 215 Einträge).
- Zustand jetzt: keine `laeuft`-Einträge mehr; genau ein Server, genau ein
  Inbox-Daemon; `/api/health` 200; `app.js?v=20260915bZ` ausgeliefert.