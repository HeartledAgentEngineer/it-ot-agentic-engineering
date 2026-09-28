# Changelog 28.09.2026 — Auftrag E8a: Erzähl-Diashow

## Was

Neue Funktion „Erzählen": Sebastian wählt in der App ein Ereignis, klickt sich
durch die Diashow der Bilder und erzählt zu jedem Bild (tippen oder Mikrofon).
Jede Geschichte hängt an **Bild + Ereignis** — nicht am Dateisystem, nicht am
Ordner.

Neue/geänderte Dateien:

- `backend/app/services/erzaehl_service.py` — liest `ereignisse.jsonl` (nur
  lesend), hängt `geschichten.jsonl` an (nur anhängend, Schicht „mensch").
- `backend/app/router/erzaehlen.py` — `GET /api/erzaehlen/ereignisse`,
  `GET /api/erzaehlen/ereignisse/{kennung}`, `POST/GET /api/erzaehlen/geschichten`.
- `backend/app/main.py` — Router registriert (Key-Schutz wie alle anderen
  `/api`-Routen).
- `backend/tests/test_erzaehlen.py` — 48 Tests, ausschließlich `tmp_path` +
  Umgebungsvariablen, kein Netz.
- `frontend/erzaehlen.js` — neue, eigenständige Datei (kein Umbau von
  `app.js`): Vollbild-Blatt mit Ereignisliste + Diashow, Bilder per
  fetch→Blob→Objekt-URL (wie die bestehende Galerie), Mikrofon über dieselbe
  AudioWorklet→WAV→`/api/sprache/transkript`-Kette wie `app.js`, Sprachbefehle
  „weiter"/„zurück"/„speichern".
- `frontend/tests/test_erzaehlen.js` — 40 Prüfungen (reine Funktionen aus dem
  echten Quelltext geschnitten, wie `test_selbsttest.js`).
- `frontend/index.html` — Knopf `#erzaehlen-btn`, Blatt `#erzaehlen-sheet`,
  Cache-Bump `app.js` bleibt `?v=20260928A` (unverändert), `style.css`
  → `?v=20260928B`, neu `erzaehlen.js?v=20260928B`.
- `frontend/style.css` — Layout für das neue Blatt (zwei Spalten Desktop,
  zwei Stufen < 768 px).
- `frontend/tests/test_foto_galerie.js` — die dort hart einprogrammierte
  Erwartung `style.css?v=20260928A` auf `20260928B` nachgezogen (reiner
  Versions-Abgleich, keine Verhaltensänderung).
- `README.md` — Feature-Zeile + API-Endpunkte ergänzt.
- `personal_ai_agent/CLAUDE.md` — Zeile im Änderungsprotokoll.

## Warum

Bestehende Fotos landen zwar sortiert nach Ereignis, aber ohne Sebastians
eigene Worte dazu. Die Erzähl-Diashow macht das Nacherzählen zu einer
eigenen, wiederkehrenden Tätigkeit — am PC (groß, Tastatur) wie am Handy
(Touch, Mikrofon).

## Datengrenze (bindend, aus dem Auftrag)

- Keine echten Daten gelesen oder ausgeführt: Tests laufen ausschließlich
  gegen erfundene Beispieldaten in `tmp_path`.
- `ereignisse.jsonl` bleibt **nur lesend** — defekte Zeilen werden gezählt,
  nie geworfen.
- `geschichten.jsonl` ist **nur anhängend** (`open(..., "a")` + `flush` +
  `os.fsync`) — nie neu geschrieben, nie gelöscht. Korrekturen sind neue
  Zeilen mit `ersetzt: <alte id>`; beim Lesen zählt nur die neueste Fassung.
- Beide Pfade liegen außerhalb des Repos (`~/foto_sortierung/…`) und sind
  über `ERZAEHL_EREIGNISSE_PFAD` / `ERZAEHL_GESCHICHTEN_PFAD` übersteuerbar.
- `frontend/app.js` wurde **nicht verändert** (nur gelesen, um Muster für
  Blob-Laden und Mikrofonaufnahme zu übernehmen).

## Nachtrag des Planers (während der Umsetzung)

Das Feld `quelle` in `geschichten.jsonl` darf zusätzlich den Wert `"import"`
tragen (spätere Übernahme von Erzählungen aus Hermes). Erlaubt sind jetzt
`tippen | sprache | import`. Über die Oberfläche werden weiterhin nur
`tippen`/`sprache` gesetzt; die POST-Validierung akzeptiert `import`
zusätzlich. Eigener Test dafür: `test_speichern_erlaubte_quellen` (parametrisiert)
und `test_route_post_geschichte_import_quelle_ok`.

## Testzahlen

- Backend, vorher (Baseline): **2558 passed**, Exit 0 (491 s).
- Backend, nachher: **2606 passed**, Exit 0 (393 s) — `cd backend &&
  .venv/Scripts/python -m pytest tests/ -q` (davon 48 neue Tests in
  `test_erzaehlen.py`).
- Frontend: `node --check frontend/erzaehlen.js` → Exit 0.
  `node frontend/tests/test_erzaehlen.js` → 40 Prüfungen, Exit 0.
  Alle übrigen `frontend/tests/*.js` (14 weitere Dateien) → Exit 0.

## Abweichungen vom Auftrag (mit Begründung)

- `frontend/tests/test_foto_galerie.js` musste um EINE Zeile angepasst werden
  (hartcodierte Erwartung `style.css?v=20260928A`). Der Auftrag verlangt bei
  Frontend-Änderungen zwingend einen Cache-Bump (Bereichsregel
  `02_Softwareentwicklung_IT/CLAUDE.md`, Abschnitt 5); dieser Test prüft
  exakt diese Versionsnummer und wäre bei JEDER weiteren Style-Änderung am
  28.09.2026 ohnehin rot geworden. Die Anpassung ist ein reiner
  Versions-Abgleich, keine Verhaltensänderung — kein bereits vorher roter
  Test wurde "repariert".
- `ereignis_detail`/`ereignisse_liste` liefern `titel` bereits serverseitig
  (Backend-Rückfall `event → thema → "Ohne Titel"`); die REINE Frontend-
  Funktion `erzaehlTitel()` übernimmt ein vorhandenes `titel`-Feld direkt und
  wiederholt den Rückfall nur als Absicherung (z. B. bei künftiger
  Wiederverwendung mit Rohdaten). Das steht so nicht wörtlich im Auftrag,
  wirkt aber nicht dem Schema entgegen.

## Offene Punkte

- Kein Echtdaten-Test möglich (Datengrenze) — Abnahme mit echten Daten liegt
  laut Auftragskopf bei Hermes.
- Die Diashow-Großbilder laden `800x800`-Vorschauen über `/api/cloud/thumb`
  (wie von der Aufgabe vorgeschrieben); ein Sprung auf das Originalbild ist
  nicht Teil dieses Schritts.

## Review durch den Planer (Claude Opus, 28.09.2026)

- **Gefundener Fehler (behoben):** Schnelles Weiterklicken startete mehrere
  Bildanfragen gleichzeitig. Kam eine ältere Antwort zuletzt an, zeigte die
  Diashow ein anderes Bild als der Zähler — eine Geschichte wäre am **falschen
  Foto** gespeichert worden. `erzaehlen.js` merkt sich jetzt Index und Ereignis
  vor dem Laden und verwirft veraltete Antworten (Objekt-URL wird freigegeben).
- Gegengeprüft: `app.js` unverändert; Geschichten nur anhängend
  (`open(..., "a")` + `fsync`); Nutzertexte nur über `textContent`
  (0× `innerHTML`); Objekt-URLs werden vor jedem Bildwechsel und beim
  Schließen freigegeben.
- Prüfbefehl frisch: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **2606 passed, Exit 0**; alle 17 `frontend/tests/*.js` Exit 0.
