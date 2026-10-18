# Kein „ewiges Warten" mehr ohne Hermes (S7)

**Datum:** 18.10.2026 · **Schritt:** S7 der Dauerlauf-Liste (To-do Punkt 8 „Hermes wurde
benachrichtigt — wartet auf Bearbeitung") · **Betroffen:**
`backend/app/services/chat_routing.py`, `backend/app/router/chat.py`, zwei neue Testdateien,
zwei nachgezogene Testdateien · **Kein Frontend, kein Cache-Bump nötig**

## Ausgangslage (Sebastians Befund)

„Die Oberfläche zeigt einen grünen Live-Status, der ewig auf den lokalen Hermes wartet." Auf dem
Gerät lief aber **kein** Hermes (Termux-Paket defekt), und der PC war aus.

Nachgemessen im Code: Ist weder der PC-Hermes noch der lokale Hermes erreichbar, läuft die
Auftrags-Weiche in den **Track B** (Warteliste). Dort standen zwei unwahre Sätze:

```
🧩 **Hermes-Aufgabe erkannt – wird übernommen.**
➡️ **Weitergeleitet an:** Hermes
Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, erscheint es hier.
```

Dazu schrieb der Nicht-Stream-Weg die Statuszeile
`⏳ **Hermes wurde benachrichtigt** – wartet auf Bearbeitung...` in den Auftrag. Der grüne Balken
der Oberfläche lebte von genau dieser Zeile und zeigte „⏳ wartet" — obwohl **nichts** lief: der
Auftrag lag nur in der Liste und wartete auf einen Hermes, den es nicht gab. Der Nutzer wartete
damit auf ein Ergebnis, das nie kam.

## Jetzt

- **Der Grund steht sofort im Chat.** Neue reine Funktionen in
  `backend/app/services/chat_routing.py`:
  - `kein_helfer_text(pc_grund, lokal_verfuegbar)` → Klartext, warum die Aufgabe niemanden hat
    („auf diesem Gerät ist der lokale Hermes nicht einsatzbereit; der PC-Hermes ist nicht
    erreichbar (…)").
  - `bereit_reply_text(message, wartegrund)` → die Antwort, **eine** Quelle für beide Wege.
  - `statusmeldung_bereit(eintrag_id, grund)` → ehrliche Statuszeile („⚠️ **Liegt bereit — gerade
    arbeitet niemand daran.** …") statt der alten Behauptung.
- **Beide Wege, eine Meldung.** Der Stream-Weg (`backend/app/router/chat.py`) war eine **zweite,
  nicht ausgelagerte Kopie** derselben Weiche und trug die unwahre Meldung ebenfalls. Er holt Text
  und Statuszeile jetzt aus `chat_routing` — zwei Kopien derselben Meldung waren hier schon einmal
  auseinandergelaufen.
- **Der Ausweg steht dabei:** „Sofort weiter kommst du ohne Werkzeug: stell dieselbe Frage direkt
  („antworte ohne Werkzeuge") — dann beantworte ich sie hier selbst."
- **Nichts geht verloren:** Die Aufgabe wird weiterhin vorgemerkt und abgearbeitet, sobald wieder
  ein Hermes erreichbar ist (der PC-Hermes holt sie über `/api/auftraege/naechster` ab, der lokale
  Hermes über sein Postfach). Die Aussage ist damit gedeckt, nicht behauptet.
- **`pc_grund` wird nicht mehr erfunden:** Wird Track A übersprungen (Umlenk-Ziel „handy"), bleibt
  der Grund leer und der Text behauptet den PC **nicht**.

## Belege

- **Neuer Test** `backend/tests/test_kein_lokaler_hermes_klare_meldung.py` (7 Prüfungen): fährt den
  **echten** `route_auftrag` (nur Gateway und lokale Verfügbarkeit sind gefakt) und prüft die
  ehrliche Antwort, den Klartext-Grund, die ehrliche Statuszeile — plus **Gegenprobe**: mit
  verfügbarem lokalem Hermes wird **nicht** gebucht und **keine** Warnung geschrieben. Dazu ein
  Quelltext-Wächter, dass die alte Statuszeile aus dem Code verschwunden ist.
- **Neuer Test** `backend/tests/test_chat_stream_kein_hermes_klare_meldung.py`: fährt den echten
  Endpunkt `/api/chat/stream` (conv_code, kein Hermes), sammelt die Server-Sent-Events und prüft,
  dass die Meldung ehrlich ist und die Statuszeile geschrieben wird; dazu ein Quelltext-Wächter
  gegen die zweite Kopie des Textes.
- **Nachgezogen (nicht gelöscht, nicht abgeschwächt):** `backend/tests/test_chat_routing.py` (die
  alte Zusicherung „wird übernommen" **war** die Beanstandung), `backend/tests/test_chat_endpoint.py`
  (zwei Stellen), `backend/tests/test_kontext_delegation.py`, `backend/tests/test_route_ziel.py`
  (Mock auf den umbenannten Status-Helfer).
- **Prüfbefehl** `cd backend && .venv/Scripts/python -m pytest tests/ -q` → siehe Tor-Protokoll im
  Commit-Log (pre-commit-Haken).

## Ehrliche Grenzen

- **Die Anzeige im Frontend ist in diesem Schritt NICHT angefasst.** Der grüne Balken zeigt weiter
  „⏳ wartet", wenn ein Auftrag offen ist — er zeigt jetzt aber die **ehrliche** Statuszeile darin
  („⚠️ Liegt bereit — gerade arbeitet niemand daran.") und verschwindet nach seiner
  Frischegrenze (30 Minuten ohne neue Meldung) von selbst. Das Umbenennen der Balken-Beschriftung
  („⏳ liegt bereit" statt „⏳ wartet") bleibt als eigener Teilschritt offen: `frontend/app.js` ist
  in diesem Durchlauf von einem **zweiten Lauf** belegt (Schritt C, Mehrfachbearbeitung) — zwei
  Schreiber in derselben Datei sind unzulässig. Grund steht im Journal des Dauerlaufs.
- **Der Weg „selbst antworten" ist nicht gebaut.** Die To-do-Liste ließ beides zu („selbst
  antworten **oder** klare Meldung"); gewählt wurde die klare Meldung, weil sie deterministisch,
  sofort und kostenfrei belegbar ist. Der Hinweis im Text nennt den Ausweg (Frage ohne Werkzeuge).
- **Keine Prüfung am Gerät:** nachgestellt ist der Mechanismus (kein PC-Hermes, kein lokaler
  Hermes). Ob Sebastians Handy genau diesen Weg nimmt, ist damit nicht bewiesen — der Weg ist aber
  der einzige, der bei „kein Hermes erreichbar" übrig bleibt.
