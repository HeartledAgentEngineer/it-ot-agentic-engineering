# Änderung 15.09.2026 — Verlauf ist jetzt vollständig (nichts geht mehr verloren)

## Problem (Live-Beobachtung Sebastian)

Nach einem Browser-Neustart war **die letzte eigene Nachricht verschwunden**.
Während einer Hermes-Übergabe waren Zwischenmeldungen kurz zu sehen, aber nach
dem Neuladen nicht mehr im Chat.

## Ursache

Die **User-Nachricht** wurde erst von `finish_exchange()` geschrieben — und zwar
**am Ende** des Austauschs. Brach der Stream vorher ab (Browser-Neustart,
Hänger, Timeout, `exec`-Uvicorn-Neustart), lief `finish_exchange` nie:
die Nachricht war spurlos weg.

Zweiter Befund: `verlauf_nachricht_anhaengen()` existierte zwar, wurde aber
**nirgends aufgerufen** — es gab also gar keinen frühen Schreibpfad.

## Fix (Backend)

1. **`chat_stream` sichert die User-Nachricht SOFORT** beim Eintreffen
   (`app/router/chat.py`):
   ```python
   verlauf_nachricht_anhaengen(
       _get_or_create_conversation(request.conversation_id), "user", request.message)
   ```
   Damit überlebt die Eingabe jeden Abbruch. Fehler dabei werden geloggt, aber
   nie als Stream-Abbruch behandelt.

2. **`finish_exchange` ist idempotent** (`app/services/chat_verlauf.py`):
   Ist der letzte Eintrag schon genau diese User-Nachricht, wird sie **nicht
   doppelt** angehängt — ein inzwischen bekannter Upload-Bildpfad wird
   stattdessen nachgetragen.
   Ohne Sofort-Sicherung bleibt das Verhalten wie vorher (abwärtskompatibel).

## Warum die Zwischenmeldungen schon sicher waren

Hermes-Zwischenmeldungen laufen über `_reite_an_verlauf(auftrag_id, …)` und
brauchen eine **Verknüpfung Auftrag → Gespräch**. Die setzt `_starte_lokale_hermes`
vor dem Worker-Start (`setze_chat_verknuepfung`). Diese Kette war intakt —
deshalb war die Lücke allein die User-Nachricht.

## Verifikation

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q    # 212 passed, Exit 0
```

Neue Tests in `backend/tests/test_verlauf_vollstaendig.py` (4):
1. Nachricht steht im Verlauf, auch wenn der Stream abbricht.
2. Sofort-Sicherung + `finish_exchange` = genau **2** Einträge (kein Duplikat).
3. Ohne Sofort-Sicherung unverändertes Verhalten (Abwärtskompatibilität).
4. Nachgereichter Upload-Bildpfad wird am bestehenden User-Eintrag ergänzt.

Die Tests biegen `_verlauf_datei`/`_persist_dir` auf `tmp_path` um — die echten
Chat-Daten werden nie berührt.

## Noch offen

- **Reload-Anzeige prüfen:** Nach dem Pull testen, ob ein Neustart mitten in
  einer Hermes-Übergabe den Verlauf vollständig zeigt (inkl. Zwischenmeldungen).
- **Track B** soll laut Sebastian nicht mehr in der UI erscheinen (nur intern).
