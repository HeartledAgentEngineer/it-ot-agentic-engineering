# Hermes-Integration: Zustand & Deployment (2026-08-14)

## Ziel
Hermes (in der Hermes-Android-App) ist das "Brain" des persönlichen AI-Agenten
(grillAnAgent). Die Oberfläche/der Chat leitet Coding-Aufträge automatisch ans
Auftragsbuch, Hermes holt sie sich im eigenen Takt ab und arbeitet sie ab.

## Komponenten & Zustand

### 1. Auftragsbuch (Backend, live in Termux)
- `POST   /api/auftraege`                 Auftrag anlegen (Oberfläche)
- `GET    /api/auftraege`                 Liste mit Stand (Oberfläche)
- `GET    /api/auftraege/naechster`       nächsten offenen abholen (Hermes)
- `GET    /api/auftraege/{id}`            einzelner Stand
- `POST   /api/auftraege/{id}/ergebnis`   Rückmeldung (Hermes)
- Auftrag: `offen -> laeuft -> fertig/fehler`, 30-min-Timeout für verwaiste.
- Ablage: `personal_ai_agent/auftraege.json` (gitignored).

### 2. Chat-Weiche (Backend, NEU im lokalen Klon-Commit af47dbc5ab, NOCH NICHT deployed)
- Dateien:
  - `backend/app/services/auftrags_erkennung.py` (neu) — Heuristik
  - `backend/app/router/chat.py` (geändert) — Weiche in `/chat` + `/chat/stream`
- Verhalten: erkennt Coding-Auftrag über Signalwörter + Code-/System-Bezug.
  Erkannt -> Eintrag ins Auftragsbuch, Antwort mit Auftrags-ID.
  Normale Frage -> unverändert durch lokalen LLM.
- Verifiziert: Syntax OK, 10 Erkennungs-Testfälle alle korrekt, config lädt.

### 3. Hermes-Poller (Cron-Job, eingerichtet)
- Job-ID `098fc30755ad` "Auftragsbuch-Poller (Hermes als Brain)"
- Monitor-Modus: alle 1 Min, Skript `~/.hermes/scripts/auftraege_poller.py`.
  Leerlauf = leere Ausgabe -> kein LLM-Lauf (0 Token). Auftrag vorhanden ->
  Ausgabe ändert sich -> Hermes aktiviert, arbeitet ab, POSTet Ergebnisse.
- WICHTIG Status: hat noch keinen Tick gemacht (last_run_at: null) — prüfen!

## Deployment (NOCH OFFEN)
Die Chat-Weiche ist NUR im Klon unter
`~/agent_project/it-ot-agentic-engineering/`, Commit `af47dbc5ab`.
Der laufende Termux-Server hat sie NICHT. Zum Aktivieren:

1. Push/Übertragen des Commits nach Termux (Repo-Update dort).
2. Server in Termux neu starten (uvicorn), damit neue Routen sicher aktiv sind.
3. Test: Coding-Auftrag über Oberfläche senden -> Auftrag im Buch,
   Hermes-Cron holt ihn ab, Ergebnis kommt zurück.

## Push offen (Token fehlt)
Der lokale Commit `af47dbc5ab` ist nicht gepusht (`HTTPUnauthorized`, kein
Token in Sandbox). Push läuft über den Nutzer/CI in Termux. Inhalt des
Commits: nur die 2 Dateien oben; KEINE `.env`, keine Keys, keine persönlichen
Daten (verifiziert).

## Sicherheitshinweis
- `.env` mit echten API-Keys wurde VORHER angelegt (OPENROUTER + MISTRAL) und
  ist NICHT getrackt (gitignore). Keys waren zeitweise im Chat -> rotieren!
- `auftraege.json` ist gitignored (enthält Diktiertes).
