# Changelog 16.10.2026 — Schritt B: einzelner Rahmen, Cosinus-Distanz im Protokoll

Bezug: Plan `.hermes/plans/2026-10-16_rahmeneditor-detailbild.md`, Fassung 13,
Abschnitt 4, **Schritt B** (Reihenfolge A0 → A → A2 → A3 → **B**). Vorgänger:
`changelog-2026-10-16-gesendeter-rahmen.md` (A3).

## Was Schritt B verlangt

„Dienst ruft `embed_crop` für den (verschobenen) Rahmen, speichert den Vektor als
Referenz über den Gesichter-Weg, **protokolliert die Cosinus-Distanz**."

## Was schon stand (A3, Commit `dc45517`) — nicht doppelt gebaut

- `gesicht_quiz.beantworte_runde` rechnet den Vektor für **genau den gesendeten
  Ausschnitt** (`face_service.embedding_fuer_bbox` → `op: embed_crop`) und speichert
  **numerisch die gesendeten Koordinaten**; der Detektor-Rahmen bleibt benannter
  Rückfall. `ergaenze_person_mit_bbox` (selbst gezeichneter Rahmen) tat dasselbe.
- Die 0,05-Schwelle im Quiz-Weg (`zu_alt > 0.05`) und der Frühausstieg bei bereits
  bestätigter Region (`_ist_bestaetigt`) waren vorhanden und getestet.

## Was dieser Schritt geändert hat (Code)

`backend/app/services/gesicht_quiz.py`:

- **Neu: die Cosinus-Distanz steht im Antwort-Protokoll.** Beide Schreibwege melden
  jetzt das Feld `cosinus_distanz` (gerundet auf 4 Stellen) — die Distanz des neuen
  Vektors zur **nächsten** vorhandenen Referenz derselben Person. Ehrliche Fälle:
  - erste Referenz einer Person → `None` (es gibt nichts zu vergleichen),
  - Frühausstieg „Region bereits bestätigt" → `None` (der Vergleich wird bewusst
    **nicht** gerechnet; die Erkennung wird dadurch eingespart),
  - jeder Fehlerausgang → `None`.
- Damit ist die 0,05-Entscheidung **nachprüfbar**: `referenz_geschrieben: false`
  geht immer mit einer gemeldeten Zahl **unter** 0,05 einher, `true` mit einer Zahl
  **über** 0,05 oder `None`.

Kein neuer Netz-, Modell- oder Geräteweg. Keine Änderung am Frontend; die Anzeige
der Distanz ist **nicht** Teil von Schritt B und bleibt offen.

## Belege (in diesem Lauf selbst ausgeführt)

- Neue Testdatei `backend/tests/test_gesicht_quiz_rahmen_distanz.py` (5 Tests) —
  fährt den **echten** Weg (`beantworte_runde` / `ergaenze_person_mit_bbox` →
  `face_service.embedding_fuer_bbox` → `face_service._infer`), gefakt ist nur der
  Debian-Subprozess, der je Rahmen einen erfundenen Vektor liefert:
  1. **über 0,05** (Vektor `[0.5, 0.866, 0]` → Distanz 0,5): neue Referenz,
     `cosinus_distanz` = 0,5;
  2. **unter 0,05** (Vektor `[1, 0.005, 0]` → Distanz ≈1,25e-05): **keine** neue
     Referenz, Bestand unverändert, Distanz wird trotzdem gemeldet;
  3. **Idempotenz:** derselbe Rahmen ein zweites Mal → `uebersprungen`, Bestand
     unverändert, **kein** zweiter Engine-Aufruf (Zähler 0);
  4. **Fremdaufruf-Nachweis scharf:** `socket.socket.connect` /
     `socket.create_connection` sind im Test verboten und werden gezählt —
     **0** Netzaufrufe; der Engine-/Subprozess-Aufruf (`op: embed_crop`) zählt
     **≥ 1** (der gewollte Aufruf);
  5. beide Schreibwege melden dieselben Felder.
  Ergebnis: **5 passed**.
- Nachbarprüfung: `pytest tests/ -q -k "gesicht or gesichter or quiz"` →
  **515 passed, 1 skipped, Exit 0**.
- Volles Tor über den Commit-Haken (`tools/gate/tor.py`, also genau der Prüfbefehl
  `cd backend && .venv/Scripts/python -m pytest tests/ -q`): siehe Journal des
  Nachtlaufs (Zahlen und Exit 0 dort).

## Grenzen (ehrlich)

- Der Test beweist die **gemeldeten Daten**, nicht die Anzeige am Handy — die
  Wirkung bleibt Sebastians Abnahme.
- **Variante 2** („jedes Speichern erzeugt eine neue Referenz", Abschnitt 3/4 des
  Plans) ist weiterhin **nicht** gebaut; sie wartet auf Sebastians Wort und hat die
  Auflagen (a)–(f) im Plan.
- Die Schritte **C–I** des Plans sind offen.
