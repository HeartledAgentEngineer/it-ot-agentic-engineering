# Auftrag E8a — Erzähl-Diashow (Schritt 1)

> Planer/Prüfer: Claude Code (Opus) · Ausführer: Subagent (Sonnet) · Abnahme mit Echtdaten: Hermes
> Plan: Erinnerungs-Agent, Schritt E8 (privater Plan). Stand 28.09.2026.

## Ziel
Sebastian wählt in seiner App ein **Ereignis**, klickt sich durch die **Diashow** der Bilder und
**erzählt zu jedem Bild** (tippen oder Mikrofon). Jede Geschichte wird **an Bild + Ereignis**
gespeichert. Sprachbefehle „weiter" / „zurück" / „speichern". Läuft im PC-Browser (groß, Maus,
Tastatur) und am Handy (Touch).

## Datengrenze (bindend)
- **Keine echten Daten lesen oder ausführen.** Nicht `~/foto_sortierung/` öffnen, keine Skripte gegen
  echte Dateien laufen lassen. Tests nur mit **synthetischen** Daten in `tmp_path`.
- Ausgabedateien liegen **außerhalb des Repos**; Pfade über Umgebungsvariablen übersteuerbar.
- Nicht anfassen: `frontend/app.js` (Quiz-Code, 28 Stellen — Umbau riskant), Hermes-Dateien,
  `tools/`, die Kosten-/Kontextleiste in Hermes.
- **Kein git commit**, kein push. Der Planer committet nach Prüfung.

## Eingabe (nur lesend): `ereignisse.jsonl`
Standard `~/foto_sortierung/ereignisse.jsonl`, übersteuerbar mit `ERZAEHL_EREIGNISSE_PFAD`.
JSONL, je Zeile ein Knoten (eingefrorenes Schema aus `tools/foto_sortierung/ereignisse_bauen.py`):
`anlass_id, anzahl_dateien, art, datei_kennungen (int, aufsteigend), datum (ISO oder null),
event, event_quelle, event_stufe, jahr, kategorie, kennung ("E-"+anlass_id, stabil), quellen,
stand, thema, ziel_ordner`. Defekte Zeilen **zählen, nicht abstürzen**.

## Ausgabe (nur anhängend): `geschichten.jsonl` — Schicht „mensch"
Standard `~/foto_sortierung/geschichten.jsonl`, übersteuerbar mit `ERZAEHL_GESCHICHTEN_PFAD`.
Je Zeile:
```json
{"id": "<uuid4>", "zeit": "<ISO lokal>", "schicht": "mensch", "version": 1,
 "ereignis_kennung": "E-…", "ereignis_datum": "…|null", "ereignis_titel": "<Schnappschuss>",
 "datei_kennung": 123 | null, "text": "…", "quelle": "tippen" | "sprache" | "import", "ersetzt": "<id>" | null}
```
Regeln (Hermes' Einwand: *alles Menschliche hängt an Beobachtungen*):
1. **Nur anhängen**, nie neu schreiben, nie löschen (`open(..., "a")` + `flush` + `os.fsync`).
2. Anker ist die **Bildkennung** plus Schnappschuss von Datum/Titel — damit überlebt die Geschichte
   jede Neuberechnung der Ereignisse.
3. **Korrektur** = neue Zeile mit `ersetzt: <alte id>`; Listen liefern nur die jeweils neueste Fassung.
4. Validierung: `text` nicht leer, ≤ 20.000 Zeichen; Ereignis muss existieren; `datei_kennung`
   (falls gesetzt) muss in dessen `datei_kennungen` stehen; `quelle` ∈ {tippen, sprache, import}
   (`import` für die spätere Übernahme von Hermes-Erzählungen; die Oberfläche setzt nur tippen/sprache);
   `ersetzt` (falls gesetzt) muss existieren.

## Backend
- `backend/app/services/erzaehl_service.py` (rein, testbar, Type Hints, try/except mit Logging):
  `ereignisse_liste(jahr=None, suche=None, min_bilder=1, limit=200, offset=0)` → je Eintrag
  `kennung, datum, jahr, titel (event, sonst thema, sonst "Ohne Titel"), kategorie, anzahl_dateien,
  vorschau_kennungen (erste 4), anzahl_geschichten`; plus `gesamt`, `defekte_zeilen`.
  `ereignis_detail(kennung)` → zusätzlich alle `datei_kennungen` und die Geschichten.
  `geschichte_speichern(...)`, `geschichten(ereignis_kennung=None, datei_kennung=None)`.
- `backend/app/router/erzaehlen.py`, Präfix `/api/erzaehlen`:
  `GET /ereignisse`, `GET /ereignisse/{kennung}`, `POST /geschichten`, `GET /geschichten`.
  GET antworten **immer 200** mit `ok`, `error` (deutscher Text, z. B. „Ereignisdatei noch nicht
  vorhanden — sie liegt auf dem PC") — Stil wie `router/fotos.py`. POST: 400 mit deutschem Text bei
  Validierungsfehler. In `backend/app/main.py` mit `dependencies=[Depends(auth.require_api_key)]`
  registrieren (wie `fotos.router`).
- `backend/tests/test_erzaehlen.py`: nur `tmp_path` + Umgebungsvariablen, **kein Netz**. Mindestens:
  Liste/Filter (Jahr, Suche, min_bilder), Titel-Rückfall, Detail, unbekannte Kennung, Speichern ok,
  Bild nicht im Ereignis → Fehler, leerer/zu langer Text, **nur anhängend** (alte Bytes unverändert,
  Datei wächst), Ersetzen (Liste zeigt nur neueste), defekte Zeilen gezählt, fehlende Datei →
  `ok: false` mit deutschem Text, Router über `TestClient` inkl. API-Key-Schutz wie bestehende Tests.

## Frontend
- **Neue Datei** `frontend/erzaehlen.js` (kein Umbau von `app.js`). In `index.html` nach `app.js`
  einbinden mit `?v=20260928B`; Kopfzeilen-Knopf `#erzaehlen-btn` („📖 Erzählen").
  `app.js` patcht `fetch` global mit dem API-Key — Bilder deshalb per `fetch` → Blob → Objekt-URL
  laden (wie die Galerie, `/api/cloud/thumb?fileid=…&groesse=…`; erlaubte Größen in
  `backend/app/router/cloud.py` nachsehen) und Objekt-URLs **wieder freigeben** (kein Speicherwachstum).
- Ansicht als Vollbild-Blatt (Stil wie das Selbsttest-Blatt; Schließen über ×/Esc):
  links **Ereignisliste** (Jahr-Filter, Suche, Anzahl Bilder, Anzahl Geschichten, ✎-Marker),
  rechts **Diashow** (großes Bild, ◀ ▶, Pfeiltasten, Wischen, Zähler „3 / 148"), darunter die
  **Geschichten** zum Bild und zum Ereignis, Eingabefeld + **🎤** + **Speichern**.
  Handy (< 768 px): Liste und Diashow als zwei Stufen statt nebeneinander.
- Mikrofon: dieselbe Aufnahme-/Transkriptionsweise wie `app.js` (`POST /api/sprache/transkript`,
  multipart Feld `file`) — **bewusst ohne MediaRecorder** (WebM/Opus → HTTP 400). Vorhandene globale
  Hilfsfunktionen aus `app.js` wiederverwenden, falls vorhanden; sonst die Aufnahme dort nachlesen und
  gleichwertig in `erzaehlen.js` umsetzen.
- **Sprachbefehle**: Ist das Transkript (normalisiert) genau „weiter"/„nächstes", „zurück"/„vorheriges"
  oder „speichern", wird die Aktion ausgeführt statt Text eingefügt.
- Reine, testbare Funktionen (ohne DOM): `erzaehlSprachbefehl(text)` → `'weiter'|'zurueck'|'speichern'|null`,
  `erzaehlTitel(ereignis)`, `erzaehlIndex(i, n, richtung)` (Grenzen, kein Überlauf).
- Design nach Bereichsregeln: Dark Mode, dezente Akzente, runde Schrift wie bestehend, Mikro-Animationen,
  eindeutige IDs, semantisches HTML, `textContent` statt `innerHTML` für Nutzertexte.
- `frontend/tests/test_erzaehlen.js` (Stil wie `test_selbsttest.js`: Funktionen aus der echten Datei
  ausschneiden, in Stub-Umgebung ausführen) + Prüfung, dass `index.html` die Datei mit `?v=` lädt und
  `#erzaehlen-btn` existiert.

## Doku (code + docs, gleicher Stand)
- `docs/changelog-2026-09-28-e8a-erzaehl-diashow.md` (was, warum, Datengrenze, Testzahlen).
- Zeile im Änderungsprotokoll von `personal_ai_agent/CLAUDE.md` (Tabelle, Stil der bestehenden Zeilen).
- README: Funktionsliste um „Erzähl-Diashow" ergänzen.

## Prüfkriterium (fertig heißt verifiziert)
1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0** (Baseline notieren: vorher/nachher).
2. `node --check frontend/erzaehlen.js` und `node frontend/tests/test_erzaehlen.js` → Exit 0;
   alle übrigen `frontend/tests/*.js` weiter Exit 0.
3. Bericht: geänderte/neue Dateien, Testzahlen vorher/nachher, offene Punkte.
