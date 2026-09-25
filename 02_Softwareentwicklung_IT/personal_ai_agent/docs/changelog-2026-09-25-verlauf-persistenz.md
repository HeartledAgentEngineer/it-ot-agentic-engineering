# Changelog 2026-09-25 — Daemon-Antwort überlebt das Neuladen der App

**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`
**Art:** Bugfix (Persistenz), Backend + Tests + Doku

## Befund (Live-Test Sebastian, 25.09.2026)

Fragt Sebastian im Chat auf dem Handy etwas, das an den **lokalen Hermes**
geht (Track C = Inbox-Kanal/Daemon), sieht er **live** alles: die
Gedanken-Blasen und die Antwort. **Sobald er die App neu öffnet, ist beides
weg** — der Verlauf zeigt die Runde nicht mehr.

## Ursache (mit Datei:Zeile)

Der lokale Weg speicherte nur den **Platzhalter**, nie die echte Antwort:

- `backend/app/router/chat.py:1631` — Wahl-Runde: `_finish_exchange(…, "⏳ **Wohin mit dieser Aufgabe?**")`
- `backend/app/router/chat.py:1725` — lokaler Weg Track C:
  `"➡️ **Weitergeleitet an:** Hermes (Handy)"`, dann
  `backend/app/router/chat.py:1730` `_finish_exchange(conversation_id, request.message, reply_text)`

Die **echte** Antwort entsteht erst später: Der Inbox-Daemon
(`backend/hermes_inbox_daemon.py`) schreibt sie nach
`~/hermes_inbox/antworten.jsonl` (`_schreibe_antwort`, Zeile 185ff). Bisher
wurde sie nur **live** ausgeliefert (`hermes_local.stream_auftrag_aktiv`,
`backend/app/services/hermes_local.py:928`, `yield {"art": "ergebnis", …}`)
und vom Frontend über den
Poll-Endpunkt `GET /api/auftraege/{id}/chat`
(`backend/app/router/auftraege.py:140`) bzw. `GET /api/hermes/status/{id}`
angezeigt — **in den gespeicherten Verlauf geschrieben wurde sie nie.**
Nach einem Reload blieb dadurch nur der Platzhalter stehen.

## Änderung

1. **Neuer Leser** — `backend/app/services/hermes_local.py:194`
   `lese_daemon_antwort(auftrag_id, inbox_dir=None) -> Optional[str]`
   liest die letzte passende Zeile aus `antworten.jsonl`.
   Vertrag: `None` = **kein** Eintrag (Datei fehlt / Daemon noch nicht fertig),
   `""` = Eintrag vorhanden, Text leer, sonst der Text. Wirft nie —
   fehlende Dateien und kaputte Zeilen werden übersprungen.
   Zusätzlich `daemon_inbox_dir()` (`:182`), über `HERMES_INBOX_DIR`
   umlenkbar (wie im Daemon) — damit Tests ohne echtes HOME laufen.

2. **Einmaliges Anhängen** — `backend/app/services/auftrag_service.py:336`
   `verlauf_antwort_anhaengen(auftrag_id, antwort) -> str`
   hängt die Antwort genau **einmal** über den bestehenden Helfer
   `_in_verlauf_anhaengen` (→ `chat_verlauf.verlauf_nachricht_anhaengen`) an.
   **Dedupe:** Ein Merker `antwort_verlauf_merker` wird im Auftragseintrag
   **vor** dem Anhängen gesetzt — auch zwei gleichzeitige Polls erzeugen kein
   Duplikat. Rückgabe ist ein deutscher Klartext-Grund
   (`geschrieben` / `schon_geschrieben` / `ohne_gespraech` / `leer` /
   `kein_auftrag`).

3. **Verdrahtung am Poll-Endpunkt** — `backend/app/router/auftraege.py:90`
   `_daemon_antwort_in_verlauf(auftrag)` holt die Daemon-Antwort und
   übergibt sie an (2). Aufgerufen in `auftrag_chat_ausgabe`
   (`backend/app/router/auftraege.py:195`, Feld `verlauf_persistenz`).
   Dieser Endpunkt wird vom Frontend mehrfach abgefragt
   (`frontend/app.js:2821`, `startAuftragTracking`) — deshalb der Merker.

**Randfälle** (jeweils klare deutsche Meldung, keine leere Nachricht, kein
Absturz):

| Fall | Verhalten |
|---|---|
| Auftrag ohne Gesprächsverknüpfung | `ohne_gespraech`, Verlauf unverändert |
| fehlende Antwortdatei / noch keine Antwort | `Noch keine Daemon-Antwort vorhanden …`, Platzhalter bleibt stehen (nichts wird erfunden) |
| leere Antwort | Klartext `⚠️ Hermes hat den Auftrag bearbeitet, aber ohne Text geantwortet …` wird einmalig angehängt |
| abgebrochener/fehlgeschlagener Auftrag | Klartext `Auftrag abgebrochen/fehlgeschlagen – keine Daemon-Antwort …`, Verlauf unverändert |
| unbekannte Auftrags-ID | `kein_auftrag` |

**Der LIVE-Weg bleibt unverändert:** Der Stream/`strom_auftrag_live`, die
Gedanken-Blasen und die Live-Anzeige wurden nicht angefasst; lediglich der
Poll-Endpunkt bekommt ein zusätzliches Antwortfeld (`verlauf_persistenz`),
das das Frontend nicht auswertet.

## Tests

Neu: `backend/tests/test_verlauf_persistenz_daemon.py` (10 Tests) —
u. a. Antwort wird angehängt; zweimaliges Abfragen erzeugt **kein** Duplikat;
Auftrag ohne Gespräch kein Fehler; leere Antwort ergibt Klartext;
Reihenfolge Frage→Antwort stimmt (auch bei zwei Aufträgen im selben
Gespräch); ohne Daemon-Antwort bleibt der Platzhalter; fehlende Antwortdatei
harmlos; Leser unterscheidet „kein Eintrag“ / „leer“ und überspringt kaputte
Zeilen. Keine echten Netz-/Daemon-Aufrufe (alles gemockt über tmp-Pfade).

## Prüfbefehl (frisch ausgeführt)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

- **Vor der Änderung (Baseline):** `412 passed, 3 warnings` — Exit 0
- **Nach der Änderung:** `422 passed, 3 warnings` — Exit 0

## Was offen bleibt / unsicher

- **Nicht geprüft:** das echte Live-Verhalten am Handy mit laufendem Daemon
  (kein Netz-/Gerätezugriff in dieser Sitzung). Der Beweis läuft hier über
  gemockte Inbox-Dateien.
- **Bewusst unverändert:** Der bestehende Aktiv-Kanal-Worker
  (`chat.py::_starte_lokale_hermes`) schreibt das Ergebnis weiterhin selbst
  über `ergebnis_eintragen`. Treffen beide Wege auf dieselbe Antwort, greift
  zusätzlich die „letzte Nachricht“-Dedupe in
  `chat_verlauf.verlauf_nachricht_anhaengen`.
- **Gedanken-Blasen:** Sie werden weiterhin **nicht** in den Verlauf
  geschrieben (Wunsch Sebastian 2026-09-11: nur das Endergebnis bleibt)
  — nach einem Reload sind nur noch `Frage + endgültige Antwort` zu sehen.
