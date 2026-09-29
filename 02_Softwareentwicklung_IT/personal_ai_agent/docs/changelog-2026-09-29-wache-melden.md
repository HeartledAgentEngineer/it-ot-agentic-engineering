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
