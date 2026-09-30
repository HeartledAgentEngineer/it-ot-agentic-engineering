# Änderungsprotokoll 01.10.2026 — Werkzeuge immer an (Knopf weg, Rückfall ohne Werkzeuge)

Wunsch Sebastian (30.09. abends): „Werkzeuge brauch ich eigentlich immer. Sonst ist der Agent ja
nur LLM und ein Geschichtenerzähler." Der Web-Knopf bleibt, damit er die Websuche bewusst
abschalten kann. Live-Test am 30.09. ~23:50 mit Werkzeugen: Foto vom Arbeitsblatt gefunden,
angesehen und ausgewertet („richtig top").

## Was sich ändert

- **`backend/app/config.py`:** `tool_use` Standard **True** (vorher False). Am Server abschaltbar
  mit `TOOL_USE=false` in `backend/.env`; je Anfrage weiter über `ChatRequest.werkzeuge`.
  `backend/.env.example` steht jetzt auf `TOOL_USE=true`.
- **Rückfall in `llm_service.chat_stream`:** Scheitert der Werkzeug-Weg, **bevor** Text kam
  (Modell/Anbieter lehnt `tools` ab, Fehler in der Schleife), läuft dieselbe Anfrage ohne
  Werkzeuge; Statuszeile „↩️ Werkzeuge gerade nicht verfügbar – antworte ohne.", Log-Warnung mit
  dem Fehlertyp. Kam schon Text, bleibt es beim bisherigen Fehler (keine doppelte Antwort). Der
  Werkzeug-Weg arbeitet auf **Kopien** der Nachrichten — er hängt den Werkzeug-Hinweis an die
  System-Nachricht, der Rückfall bekommt ihn deshalb nicht. Der Datenschutz-Riegel gilt in beiden
  Wegen.
- **Frontend:** Knopf „Werkzeuge" (`#werkzeug-btn`), `state.werkzeuge`, `setWerkzeuge()` entfernt;
  die Stream-Anfrage schickt **kein** `werkzeuge`-Feld mehr — sonst hätte ein früher gespeichertes
  „aus" (`localStorage`) den Server-Standard überstimmt.
- **Stichwort-Abfang aus:** „zeig … Foto" wird nicht mehr vor dem Senden abgefangen und an die
  feste pCloud-Galerie gegeben (die am Handy ohne `fotos_dateien.json` ohnehin mit „Datei-Kennungen
  nicht gefunden" endete). Das Modell entscheidet. `fotoFrageErkennen`/`zeigeFotoGalerie` bleiben
  für das geplante Stream-Ereignis `galerie` (Plan Foto-Gedächtnis Schritt 4).
- `app.js?v=20261001A`.

## Unverändert

- `/api/chat` (Rückfallweg ohne Stream) nutzt weiter die Vorab-Weiche.
- Hermes-Delegation, Aufträge, Quiz laufen vor der Werkzeug-Stelle — nicht betroffen.
- Hermes' Sprechknopf `wecken.js` unberührt.

## Prüfung

- Backend: `tests/test_tool_use_stream.py` — `test_standard_ist_an` (ersetzt `…_ist_aus`), neu
  `test_rueckfall_ohne_werkzeuge_wenn_werkzeug_weg_vor_dem_text_scheitert` (2 Aufrufe: erst mit,
  dann ohne `tools`; Statuszeile; Text kommt an; kein Werkzeug-Hinweis im Rückfall; Riegel bleibt)
  und `test_kein_rueckfall_wenn_schon_text_kam` (ein Aufruf, Fehler bleibt). Tool-Use-Dateien
  zusammen 42 passed; voller Prüfbefehl siehe Commit.
- Frontend: `tests/test_werkzeuge_schalter.js` auf den neuen Soll-Zustand umgestellt (Knopf weg,
  kein Feld, kein Abfang, Riegel bleibt, Cache-Stand); `test_foto_galerie.js` Teil 5 ebenso.
  `node --check app.js` OK, **alle 23 Frontend-Tests Exit 0** (`test_wecken.js` braucht
  `wecken.js` als Argument, `test_erzaehlen.js` `erzaehlen.js`).
- **Offen:** Steht in der `backend/.env` am Handy `TOOL_USE=false`, gilt der neue Standard dort
  nicht (Datei wird bewusst nicht gelesen — sie enthält Schlüssel). Erkennbar daran, dass bei einer
  Werkzeug-Frage keine 🔧-Statuszeile erscheint.
