# Features 2026-08 (Ein-Chat, Datei-Tool, Chat-Suche, Modell-Kategorien)

Dokumentation der jüngsten Agent-Fähigkeiten — codegenau zum Stand.

## 1. Ein-Chat-Architektur (Rolling-Summary, Option C)

- Es gibt **GENAU EINE fortlaufende Conversation** (kein `+`-Button, kein
  Chat-Switcher; `neuesGespraech` ist ein No-op).
- **Rolling-Summary** (`app/services/kontext_service.py`): Ab >60 Nachrichten
  werden die älteren Teile zu einem kompakten Summary gerollt (Rate-Limit:
  frühestens alle 50 neuen Nachrichten neu).
- **Kontext pro Anfrage**: [Summary der Vergangenheit] + [letzte 15 Nachrichten]
  + [5 relevante Erinnerungen aus ChromaDB], grobes Token-Budget ~2000.
- **Antwort-Relevanz (Kontext-Management)**: Als **primäre Kontextquelle** pro
  Anfrage bekommt der LLM nur die letzte sichtbare Nutzerfrage + deren Antwort
  (`app/services/llm_service.py::_kontext_aufteilen`). Jüngere/frühere Fragen
  (frühere, themenfremde Fragen verdrängten die aktuelle) werden dabei nicht
  gelöscht — der Verlauf bleibt streng append-only —, sondern als **gedimmter
  Hintergrund-Kontext** mitgegeben (gekürzt, mit Hinweis „nur als Hintergrund“).
  Ein deutscher System-Prompt-Block (`KONTEXT_FOKUS_ANWEISUNG`) weist den
  Agenten an, sich auf die letzte Frage zu konzentrieren und ältere Kontext-
  Fragen zu ignorieren, wenn die neue Frage in einem neuen Themenbereich liegt.
- Persistenz: Summaries liegen in `chat_verlauf.summarys`, gespeichert in
  `conversations.json` (Feld `summarys`).
- **Hermes-Spiegel-Chat persistiert** (`/api/hermes/chat`): Jede Runde
  (Nutzer-Frage + Hermes-Antwort) wird append-only in `conv_main` geschrieben
  (`hermes_steuerung.py::_persistiere_hermes_runde`). Damit landet auch der
  Dialog über den bidirektionalen Spiegel (Terminal <-> Frontend) im
  persistenten Verlauf und ist nach Reload/Neustart wieder ansehbar.
- Test: `tests/test_kontext_service.py`, `tests/test_chat_verlauf_service.py`,
  `tests/test_hermes_spiegel_persistenz.py`.

## 2. Handy-Dateisuche + Datei-Inhalt (über Sprache, ohne UI)

- **Stufe A** — Suche: `GET /api/dateien?suche=<wort>` durchsucht
  `~/storage/shared` (alle freigegebenen Android-Ordner) nach Dateinamen;
  nur erlaubte Erweiterungen, nur lesend, keine Systempfade/privaten Dateien.
- **Stufe B** — Inhalt lesen: `lese_datei_info(pfad)` extrahiert PDF-Text
  (pdfminer), TXT/MD direkt, Bilder als Vision-`data_url`.
- **Über Sprache**: `_datei_tool(frage)` erkennt Datei-Suchs-/Lese-Signale
  ("suche/finde/lies/was steht in/zeig mir den inhalt von …") und hängt die
  Treffer bzw. den Inhalt an die user_message — der LLM nennt/fasst zusammen.
- **Screenshot-Erkennung**: "screenshot" ist ein eigenes Such-Signal (in
  `signale`), aktiviert die Bild-Anzeige (`will_erklaeren`) und priorisiert
  den Screenshots-Ordner (`ordner_hinweis="screenshot"`). So liefert
  "Was ist auf dem letzten Screenshot?" das neueste Bild aus
  `Pictures/Screenshots` als Vision-`data_url` (nicht nur den Dateinamen).
  `GET /api/dateien?ordner=screenshot` reicht die Ordner-Priorisierung ebenso
  durch (Default bleibt "kamera" bei leerem Suchbegriff).
- **Agentische Intent-Erkennung (LLM statt Heuristik)**: `_datei_tool` ruft
  jetzt zuerst `llm_service.extrahiere_datei_such_intent(frage)` auf — ein
  günstiger LLM-Aufruf extrahiert strukturiert {suchbegriff, jahr, neueste,
  ordner, nur_bilder, nur_dokumente, erklaeren}. So versteht der Agent freie
  Formulierungen wie "das letzte Foto aus 2025" (Jahresfilter), Synonyme und
  Satzbau — ohne dass jede Variante als Wortliste gepflegt werden muss. Ein
  schnelles Vor-Gate (Datei-Signalwort oder Jahreszahl) verhindert, dass jede
  normale Frage einen LLM-Call auslöst. Die deterministische Heuristik bleibt
  als Fallback, falls der LLM-Aufruf fehlschlägt.
- **Jahresfilter in der Suche**: `suche_dateien(..., jahr=N)` behält nur
  Dateien dieses Aufnahmejahres (EXIF, Fallback mtime). "Letztes Foto aus
  2025" liefert so exakt ein 2025er-Bild.
  Keine Lupen-UI nötig; alles läuft über den Sprach-/Chat-Weg.
- Voraussetzung auf dem Handy: `termux-setup-storage` (einmalig), damit
  `~/storage/shared` existiert.
- Tests: `tests/test_datei_suche.py` (12 Tests, 2 gerätebedingte Fehlschläge
  auf Geräten mit echtem `/sdcard`, da die Sandbox-Mocks die `_FALLBACK_WURZELN`
  nicht mitmocken).

## 3. Chat-Volltextsuche im Ein-Chat

- `GET /api/chat/suche?q=<begriff>` durchsucht alle Nachrichten der
  Conversations und liefert bis zu 20 Treffer (neueste zuerst) mit Rolle,
  Textausschnitt und Zeit — "was haben wir zu X gesagt?".
- Funktioniert ohne Handy-Archiv (nutzt `conversations`).
- Tests: `tests/test_chat_suche.py`.

## 4. Modell-Kategorien (Auswahl-UI)

- **Stärke-Kategorien** (klar): `bilder`, `coding`, `reasoning`, `tool_use`,
  `alltag`.
- **`tool_use` neu**: Modelle, die besonders gut Werkzeuge/Agenten nutzen
  (codex, claude-sonnet, grok).
- **`preis_leistung` ist KEIN Stärke-Profil** mehr (es ist ein Sortier-
  Kriterium); sehr günstige Modelle fallen unter `alltag`.
- Entfernt: "EU-fähig"-Chip (doppeldeutig) + "Denkt mit"-Chip.
- Quelle: `app/modelle_use.py` (`MODELL_STAERKEN_DE`) + Backend-Ableitung
  in `llm_service._staerke_ableiten`.

## 5. Bild-/Datei-Anhang über die Büroklammer (Upload)

- **Upload**: `POST /api/upload` (`backend/app/router/upload.py`) nimmt
  Bilder (JPEG/PNG/GIF/WebP) und PDFs entgegen. Bilder werden als
  Vision-`data_url` (Base64), PDFs als extrahierter Text an das Modell
  übergeben.
- **Kein unnötiges Neu-Encoden**: Bilder werden nur dann mit Pillow
  verarbeitet, wenn sie gedreht werden müssen oder breiter/hoher als 2048 px
  sind (Resize auf max. 2048 px). Normale Bilder bleiben unangetastet.
- **EXIF-Orientierung eingebacken**: Die im Foto gespeicherte Dreh-Info
  (`ImageOps.exif_transpose`, z. B. Orientation=6 für hochkant gehaltene
  Handyfotos) wird in die Pixel übernommen und als `data_url` zurückgegeben –
  das Bild erscheint im Chat damit korrekt und auch die Vision-API sieht die
  richtige Seite.
- **Originaldatei bleibt unangetastet**: Die Drehung/Verkleinerung passiert
  **nur in-memory**. Der Upload **überschreibt nie** das Original auf der
  Platte. Genauso backt `lese_datei_info` (`datei_suche.py`) beim Anzeigen
  über `GET /api/dateien/daten?pfad=` die EXIF-Orientierung nur in-memory
  in die Pixel ein – der „🖼️ Bild wieder anzeigen"-Knopf lädt das Bild also
  immer frisch vom Speicher und zeigt es korrekt gedreht, ohne das Original
  zu verändern.
- **Tags**: „Datei-Vorschau oberhalb der Eingabe" + „Bild wieder anzeigen":
  Nach dem Versenden zeigt die Antwort kurz eine flüchtige Bild-Miniatur
  (`BILD_ANZEIGE_MS`, 10 s); danach bleibt ein „🖼️ Bild wieder anzeigen"-
  Knopf, der das Bild frisch lädt (`GET /api/dateien/daten?pfad=`). Beim
  Nachladen wird derselbe Vorschau-Rahmen aktualisiert (kein hängen
  gebliebener „… lädt"-Knopf mehr).

## 6. Nachricht bearbeiten + Abbrechen (Frontend, 2026-08-30)

- **Bearbeiten** (Kontextmenü → „✏️ Nachricht bearbeiten", nur User-Blasen):
  Stoppt einen laufenden Antwort-Stream, entfernt die bearbeitete User-Blase
  samt ihrer Antwort aus DOM + `state.messages`, löscht die Runde serverseitig
  (`DELETE /api/chat/letzte-runde`) und legt den Text zurück in die Eingabe.
  Nach dem erneuten Absenden startet der neue Stream frisch; nach Reload steht
  keine alte Fassung mehr da.
- **Abbrechen-Button**: Der generische „⏹ Abbrechen"-Button an normalen
  LLM-Antwort-Blasen ist entfernt — der Stream-Abbruch läuft über den
  Bearbeiten-Flow bzw. die leere-Eingabe-Abbruchlogik. Ein laufender
  Hermes-Auftrag behält seinen eigenen Abbruch-Knopf (`.gedanke-abbrechen`)
  und den Auftrags-Abbruch (`brichAb` → `POST /api/auftraege/{id}/abbrechen`).
- Backend: `chat_verlauf.verlauf_runde_entfernen()` entfernt die letzte
  User-Nachricht samt Antwort aus dem persistenten Verlauf (conv_main).

## Verifikation

Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest -q` → 57 Tests grün.