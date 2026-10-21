# 21.10.2026 – Bildfragen im Chat wieder möglich (Vision-Modell)

## Befund
Am Handy endete jede Frage mit Bild in „Dieses Modell ist mit deinen
Datenschutz-Einstellungen nicht nutzbar“.

## Ursache (belegt)
`backend/app/router/chat.py` schickte Bilder fest an `google/gemini-2.5-flash`
(in `/chat` und in `/chat/stream`), sofern kein bildfähiges Modell gewählt war.
Der öffentliche OpenRouter-Katalog (`GET /api/v1/models/<id>/endpoints`,
abgefragt am 21.10.2026) führt dieses Modell nur noch bei **Google AI Studio**.
Die Provider-Whitelist des Kontos enthält **Google Vertex**, nicht AI Studio.
OpenRouter fand deshalb keinen erlaubten Anbieter.

## Änderung
Beide Chat-Wege nutzen jetzt `MODELL_VISION` aus
`backend/app/services/modell_router.py` (`google/gemini-3.7-flash`). Dieses
Modell nimmt Bilder an und wird laut Katalog auch über Google Vertex angeboten.
Damit gibt es nur noch eine Stelle für das Bildmodell.

Preis laut Katalog (21.10.2026, je 1 Mio. Tokens): 0,75 $ Eingabe / 3,75 $
Ausgabe, statt 0,30 $ / 2,50 $ bei `gemini-2.5-flash`. Eine Bildfrage bleibt
im Bereich von Bruchteilen eines Cents.

## Belege
- Neu `backend/tests/test_vision_modell_einheitlich.py` (3 Prüfungen). Vor der
  Änderung waren 2 davon rot.
- Zusammen mit `test_modell_router.py` und `test_chat_endpoint.py`: 59 passed.
- Voller Prüfbefehl im Commit-Haken.

## Grenzen
- Ob Vertex das Modell für dieses Konto wirklich ausliefert, zeigt erst eine
  Bildfrage am Handy. Am PC fehlt der Schlüssel für `/models/user`.
- Nicht in diesem Commit: `gemini-2.5-flash` steht noch als erstes Modell der
  Glättungskette (`llm_service.POLISH_MODELS`, die Kette weicht auf
  `gemini-3.5-flash-lite` aus) und als Standard einiger PC-Werkzeuge unter
  `tools/foto_sortierung/`. Das steht als To-do auf der Liste.
