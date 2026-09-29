# Änderungsprotokoll 29.09.2026: Agentenbus-Wache meldet nur noch (0 Tokens)

## Befund
Sebastians OpenRouter-Guthaben (rund 6 € an einem Tag) wurde fast vollständig von Hintergrund-Weckrufen verbraucht. Laut Hermes' `usage_audit.jsonl` stammten 310 von 347 Aufrufen vom Handoff-Wächter und 37 vom Nachtlauf-Cron, je ~837k Tokens. Hinzu kamen die Zustellungen der Bus-Wache. Jede Zustellung weckte die Hermes-Sitzung mit ihrem **ganzen Verlauf**. Hermes hat Wächter und Nachtlauf-Cron pausiert (gesichert, nicht gelöscht) und die Windows-Aufgabe `HermesAgentenbusWache` deaktiviert.

## Änderung
- `tools/agentbus/wache.py` hat einen neuen **Standardmodus `melden`**. Er zeigt nur eine Windows-Benachrichtigung (Toast) mit Anzahl und Kurztext, **ohne Modellaufruf**. Die Nachrichten bleiben ungelesen, und jede wird nur einmal gemeldet (`.hermes/bus/wache-gemeldet.txt`).
- Der alte Weg bleibt als **`--zustellen`** / `WACHE_MODUS=zustellen` erhalten. Er ist ausdrücklich als teuer dokumentiert.
- `docs/agentbus-protokoll.md` wurde nachgezogen.

## Prüfung
- Neu: `backend/tests/test_wache_melden.py` mit 5 Tests: `melden` ist Standard, kein Zustellaufruf, Nachrichten bleiben ungelesen, jede wird nur einmal gemeldet, `zustellen` nur ausdrücklich.
- Ein echter Test-Toast wurde am PC gezeigt.

## Nicht geändert
Die Windows-Aufgabe bleibt deaktiviert, bis Sebastian sie wieder einschaltet (`schtasks /Change /TN HermesAgentenbusWache /ENABLE`).

## Nachtrag: Modus `auftrag` (Hermes als „Subagent", frische Sitzung je Auftrag)
- **Aufruf:** `wache.py --auftrag` bzw. `WACHE_MODUS=auftrag`.
- **Auslöser:** Nur Bus-Nachrichten vom Typ `task` starten einen Lauf. `info`, `tip` und `frage` bleiben ungelesen und werden nur gemeldet.
- **Ablauf:** Je Wache-Lauf wird höchstens **ein** Auftrag gestartet, mit Sperrdatei; ein Lock älter als `--max-minuten` gilt als verwaist. Die Wache ruft `hermes -z "<kurzer Auftrag>" --usage-file .hermes/bus/kosten/<zeit>_<id>.json --in <Repo>` auf. Das öffnet eine **frische Sitzung** und schleppt keinen alten Verlauf mit.
- **Kosten:** Nach dem Lauf schreibt die Wache eine Zeile nach `.hermes/bus/kosten.jsonl` (Kosten, Tokens, Modell, Dauer, Exit) und zeigt einen Toast „Hermes-Auftrag <step> fertig (x.xx $)".
- **Tagesbremse:** `WACHE_TAGESLIMIT_USD`, Standard 1,00 $. Ist das Limit erreicht, startet kein neuer Lauf.
- **Rückmeldung:** Meldet Hermes kein `erledigt`/`blockiert` zum Step, schreibt die Wache selbst ein `blockiert` mit Exit-Code auf den Bus.
- **Prüfung:** `backend/tests/test_wache_auftrag.py` mit 20 Tests, alle mit Attrappen. `hermes` wurde nie echt gestartet. Voller Prüfbefehl 3186 passed, 1 skipped, Exit 0 (Lauf durch den Ausführer).
- **Offen:** Die Feldnamen im Kostenbericht der Hermes-CLI sind noch unbekannt. Nach dem ersten echten Probelauf muss `kosten.jsonl` geprüft werden.
