# Gesprächsfluss aus dem Archiv — Belegstellen werden Rede

Stand: 10.10.2026. Sebastians zweiter Befund aus dem Chat vom 10.10. um 07:00:
„**Kein Gesprächsfluss** — die Verweise wirken wie Striche/Stichpunkte statt
wie Rede." Der erste Teil derselben Rückmeldung (falsche Zeitpunkte und der
sich fälschlich als nicht verfügbar meldende Zustand) wurde im Dokument
`changelog-2026-10-10-archiv-datum-und-status.md` behandelt. Dieses Dokument
schließt den zweiten Teil: den Antwort-Weg, nicht den Index.

## Befund (gemessen im eigenen Code, nicht geraten)

Der Index war in Ordnung — der Fehler steckte in der Anweisung an das Modell.
An **vier** Anzeigewegen stand dieselbe Einladung zur Aufzählung:

1. `router/chat._archiv_tool` (Chat-Notiz): „Zitiere dem Nutzer die relevanten
   Stellen aus der Vergangenheit und nenne dabei die Quelle
   (ChatGPT/Gemini/Claude) und das Datum."
2. `router/chat._verlauf_tool` (lokaler Gesprächsverlauf): „Zitiere dem Nutzer
   die relevanten Stellen aus der Vergangenheit."
3. `services/archiv_suche.erwaehnungs_text` (Personen-Erwähnung):
   „Zitiere dem Nutzer diese Fundstellen mit Quelle und Datum …".
4. `services/werkzeuge._archiv_suchen` (Modell-Werkzeug): lieferte die Stellen
   sogar mit einem wörtlichen **„- "** vor jeder Zeile:
   `f"- [{quelle}{datum}] {text}"`.

Dazu der Kopf im System-Prompt (`llm_service._build_archiv_context`): „nenne
Quelle und Datum, wenn du dich darauf beziehst" — ohne jede Vorgabe, **wie**
erzählt wird. Ergebnis: das Modell schrieb die vorgelegte Liste (Quelle, Datum,
Strich) ab, statt die Vergangenheit als Rede wiederzugeben.

## Was geändert wurde

- **Eine gemeinsame Anweisung** `ARCHIV_FLUSS_ANWEISUNG` in
  `services/archiv_suche.py`: „Erzähle das im Fluss, wie Rede: ganze Sätze,
  keine Strichliste und keine Aufzählung. Nenne die Quelle … und das Datum im
  Satz … Schreibe die Fundstellen nicht wörtlich ab — gib in einer
  zusammenhängenden Darstellung wieder, wer wann was gesagt hat, und nur das,
  was dort steht." Sie steht an **allen vier** Wegen (Verknüpfung über Import),
  damit sie nicht wieder auseinanderläuft.
- **Der Strich ist weg:** das Werkzeug `archiv_suchen` liefert die Stellen jetzt
  ohne `"- "` und trägt die Fluss-Anweisung.
- **Der Prompt selbst** (`backend/system_prompt.md`) hat eine Regel erhalten:
  „Wenn du aus dem Archiv erzählst: im Fluss, wie Rede — ganze Sätze, keine
  Strichliste …".
- **Unverändert** blieben die Beleg-Zeiger `[Quelle, Datum]` (und damit die
  Tag-/Spannen-Regel aus dem ersten Dokument) sowie alle ehrlichen
  Ausfall-Hinweise („erfinde KEINE Fundstellen").

## Belege

- Prüfbefehl des Projekts (`cd backend && .venv/Scripts/python -m pytest tests/ -q`):
  **3745 passed, 2 skipped, Exit 0** (251 s).
- Neue Testdatei `backend/tests/test_archiv_gespraechsfluss.py` (6 Tests): die
  Anweisung selbst, und je ein Test pro Anzeigeweg — inklusive der Prüfung, dass
  im Werkzeug-Weg **kein** `"\n- ["` mehr vorkommt.
- Rückwärts-Beleg: die bestehenden Tests
  (`test_archiv_datum_und_status.py`, `test_archiv_tool.py`,
  `test_erwaehnungssuche.py`, `test_werkzeuge.py`) blieben unverändert grün —
  die Beleg-Zeiger `[Quelle, Datum]` sind also weiterhin wörtlich vorhanden.

## Ehrlich offen

- Ob genau die von Sebastian gesehenen Antworten so aussahen, lässt sich am PC
  nicht nachstellen (sein Verlauf liegt am Handy). Belegt ist der Fehler selbst
  — vier Wege, die wörtlich „Zitiere …" verlangten und einen Weg mit einem
  wörtlichen Strich. Ob die neuen Antworten den gewünschten Fluss zeigen, kann
  nur ein Blick am Handy bestätigen.

## Dateien

- `backend/app/services/archiv_suche.py` — `ARCHIV_FLUSS_ANWEISUNG`, genutzt in
  `erwaehnungs_text`.
- `backend/app/router/chat.py` — `_archiv_tool`, `_verlauf_tool`.
- `backend/app/services/llm_service.py` — `_build_archiv_context`-Kopf.
- `backend/app/services/werkzeuge.py` — `_archiv_suchen` (Strich weg, Anweisung
  dazu).
- `backend/system_prompt.md` — neue Archiv-Erzähl-Regel.
- `backend/tests/test_archiv_gespraechsfluss.py` — neu.
