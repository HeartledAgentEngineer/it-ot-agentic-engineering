# Changelog / Änderungsprotokoll

Alle sichtbaren Änderungen am personal_ai_agent, dokumentiert nach dem
Prinzip „Doku folgt dem Code“. Neuere Einträge oben.

## 2026-08-30 — Bild-Vorschau (Dateisuche) überlebt Reload

**Problem:** Bilder, die der Agent über die Dateisuche im Chat angezeigt hat
(z. B. „der letzte Screenshot“), waren nur flüchtig (RAM-Cache, 10 min).
Nach einem Reload/einer neuen Sitzung waren sie weg, weil der Verlauf pro
Nachricht nur `role`/`content`/`zeit` speicherte.

**Fix:**
- `chat_verlauf.finish_exchange(..., bild_pfad=None)` speichert den Pfad des
  per Dateisuche gezeigten Bildes am Assistant-Eintrag mit. Es wird bewusst
  NUR der Pfad gespeichert, nie die Bilddatei (Original unantastbar).
- `chat.py` reicht den Bildpfad der Dateisuche an beide Verlauf-Pfade durch
  (`/api/chat` und `/api/chat/stream`).
- Frontend `zeigeGespraech` lädt Nachrichten mit `bild_pfad` über
  `GET /api/dateien/daten?pfad=` frisch nach und zeigt sie wieder an.

**Verifikation:** `python -m pytest tests/test_chat_verlauf.py -q` grün;
`GET /api/conversations/conv_main` liefert den restaurierten Verlauf.