# Änderungsprotokoll 30.09.2026 — Tool Use v1 (Schalter, Standard aus) + Riegel im Stream

Auftrag Sebastian (20:25): „Tool Use integrieren, damit der Agent schlauer wird und nicht so in
Fehler reinläuft." Entwurf mit Entscheidungen: `docs/spec-tool-use-v1.md`. Plan und Journal:
`.hermes/plans/2026-09-30_abend-dauerlauf-claude.md` (gitignored).

## Was neu ist

- **`backend/app/services/werkzeuge.py`** — Register mit 8 nur lesenden Werkzeugen als dünne
  Hüllen um bestehende Dienste: `dateien_suchen`, `datei_ansehen`, `archiv_suchen`,
  `erinnerungen_suchen`, `fotos_uebersicht`, `fotos_mit_person`, `personen_liste`,
  `wer_war_wann`. OpenAI-Funktionsschemata, Ergebnis ≤ 6.000 Zeichen, Fehler als Text (nie ein
  Absturz, nur der Fehlertyp), Bilder getrennt vom Text.
- **Pfad-Schutz in `datei_ansehen`:** nur erlaubte Endungen (`datei_suche._ERLAUBTE_EXT`) und nur
  innerhalb der freigegebenen Speicherwurzeln (`realpath` + `commonpath`). Befund beim Bau: Die
  vorhandene `datei_suche.lese_datei_info()` prüft **weder Pfad noch Endung** — ein verleitetes
  Modell hätte z. B. `backend/.env` lesen können. Die alte Vorab-Weiche übergab nur Pfade aus der
  eigenen Suche, deshalb fiel das bisher nicht auf; mit Tool Use schlägt das Modell Pfade selbst
  vor. `lese_datei_info` selbst ist unverändert.
- **`backend/app/services/werkzeug_schleife.py`** — die Schleife: gestreamter Modellaufruf,
  `tool_calls` stückweise einsammeln (id/Name/Argumente), ausführen, `role=tool` zurück, höchstens
  5 Runden (danach `tool_choice="none"`), 4 Aufrufe je Runde (jeder Aufruf bekommt eine Antwort),
  Bilder als eigene Nutzernachricht mit `image_url`, `reasoning_details` werden mitgegeben.
- **`llm_service.chat_stream(..., werkzeuge=True)`** → `_chat_stream_mit_werkzeugen`: Schemata und
  Websuche (`openrouter:web_search`) in **einer** `tools`-Liste über `extra_body`, Datenschutz-Riegel
  bleibt, System-Prompt bekommt `werkzeuge.SYSTEM_HINWEIS`.
- **`router/chat.py` (Stream-Weg):** `_werkzeuge_an(request)` — Anfrage-Feld `werkzeuge` vor
  `settings.tool_use` (Standard **aus**). Mit Werkzeugen entfällt die Vorab-Weiche
  (Archiv/Datei/Verlauf/Gesicht/Fotos/Beziehungen); Statuszeilen gehen als SSE `status` raus, ein
  angesehenes Bild wird wie ein Dateisuche-Bild behandelt (Vorschau, `bild_pfad` im Verlauf).
  `/api/chat` (Rückfallweg) bleibt bei der Vorab-Weiche.
- **Konfiguration:** `settings.tool_use = False` (`.env`: `TOOL_USE=true`), `ChatRequest.werkzeuge`.
- **Frontend:** Knopf „Werkzeuge" (`#werkzeug-btn`) in der Leiste an der Eingabe, Standard aus,
  Wunsch in `localStorage`; die Stream-Anfrage schickt `werkzeuge` mit. `app.js?v=20260930A`.

## Befund nebenbei: Datenschutz-Riegel fehlte im Stream-Weg (behoben)

`frontend/app.js` schickte `no_retention` nur im Rückfallweg `/api/chat` mit, **nicht** im
Stream-Weg `/api/chat/stream`, den die Oberfläche normal nutzt. `state.noRetention` steht fest auf
`true` („Riegel fest an"), im Backend kam aber der Standard `false` an — also ohne
`provider.data_collection = "deny"`. Jetzt schickt der Stream-Weg den Riegel mit. Vorher geprüft
(öffentliche OpenRouter-Liste `/api/v1/endpoints/zdr`, 30.09.2026): `deepseek/deepseek-v4.1-flash`
27 Anbieter ohne Datenspeicherung, `google/gemini-2.5-flash` (Bild-Umweg) 4 — Anfragen werden also
nicht mangels Anbieter abgelehnt.

## Prüfung

- Prüfbefehl `backend/.venv/Scripts/python.exe -m pytest tests/ -q` → **3243 passed, 1 skipped,
  Exit 0** (Baseline 3203; +40: `test_werkzeuge.py` 24, `test_werkzeug_schleife.py` 11,
  `test_tool_use_stream.py` 5).
- Frontend: `node --check app.js` OK; neu `tests/test_werkzeuge_schalter.js`; alle 21
  Frontend-Tests Exit 0 (Aufruf mit `app.js` bzw. `erzaehlen.js` als Argument, wie die Tests es
  erwarten); `test_foto_galerie.js` auf den neuen Cache-Stand nachgezogen (reiner Versionsabgleich).
- Fremdprüfung des Entwurfs (`node .claude/skills/critic/pruefe.mjs`, `google/gemini-3.7-flash`):
  keine Befunde.
- **Nicht live belegt:** ein echter Modelllauf mit Werkzeugen am Handy. Die API des Handy-Backends
  verlangt den Schlüssel, den Claude bewusst nicht benutzt — der Live-Test läuft über die
  Oberfläche (Knopf „Werkzeuge" an).

## Live-Test (für Sebastian)

1. Hey Agent öffnen (lädt den neuen Stand), Knopf **„Werkzeuge"** antippen → „Werkzeuge an".
2. Fragen wie am 30.09. morgens: „Schau dir mein letztes Foto an und such im Archiv Beispiele dazu."
   Erwartet: Statuszeilen „🔧 durchsucht Handy-Dateien …", „🔧 öffnet eine Datei …",
   „🔧 durchsucht das Gesprächsarchiv …", dann eine Antwort, die Bild **und** Archiv verbindet.
3. Plauderfrage ohne Werkzeug („Wie geht's dir?") → keine 🔧-Zeile.
4. Zurück: Knopf wieder aus = alter Weg.

## Nachtrag 30.09.2026 ~23:45 — Stichwort-Abfang nur ohne Werkzeuge

Erster Test am Handy (Werkzeuge an): „Zeige mir jetzt das Foto, das ich heute aufgenommen habe.
Such dafür auf meinem Handy." → Antwort „Datei-Kennungen nicht gefunden (die Kennungen entstehen
auf dem PC …)". Ursache: `frontend/app.js` `fotoFrageErkennen` fängt jede Nachricht mit
„zeig" + „Foto" **vor** dem Senden ab und öffnet die feste pCloud-Galerie
(`/api/fotos/bilder`, `foto_bilder.py:205`); die braucht `fotos_dateien.json`, die am Handy
fehlt (Übergabe läuft nur in `start-termux.sh`, nicht im echten Startweg — Plan Schritt 2).
Die Frage erreichte das Modell nie. Jetzt: `const fotowunsch = state.werkzeuge ? null :
fotoFrageErkennen(text);` — mit Werkzeugen entscheidet das Modell. `app.js?v=20260930B`;
`test_werkzeuge_schalter.js` und `test_foto_galerie.js` nachgezogen, alle 21 Frontend-Tests grün.
