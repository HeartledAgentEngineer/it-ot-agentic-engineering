# Changelog 30.09.2026 — Rückfragen behalten die letzte Runde (Kontext-Fix)

## Befund (Sebastian, 30.09.2026)

Wörtlich: „ich habe jetzt heute versucht gehabt, auf verschiedene Folgefragen zu
stellen, und der vergisst irgendwie, kriegt die letzte Nachricht nicht mehr in
Kontext."

## Ursache (im Code belegt)

`_kontext_aufteilen()` in `backend/app/services/llm_service.py` machte **nur die
letzte Nutzerfrage** zur primären Kontextquelle. Die Antwort davor landete als
„gedimmter Hintergrund" und wurde dort auf `_HINTERGRUND_LAENGE = 400` Zeichen
gekürzt. Eine Rückfrage, die sich auf die letzte Antwort bezieht, hatte diese
also nur noch als Bruchstück.

Zweiter Punkt: `chat.py` schreibt die gerade gestellte Frage sofort in den
Verlauf (offen=True). Sie stand damit **schon in der History** und wurde in
`_build_messages()` ein zweites Mal angehängt — dieselbe Frage ging doppelt in
den Prompt.

Die Regel selbst („beantworte die zuletzt gestellte Frage", ältere Runden als
Hintergrund) bleibt unverändert — sie war nie das Problem. Das Problem war die
**Kürzung der letzten Runde**.

## Änderung

`backend/app/services/llm_service.py`

- `_kontext_aufteilen()`: primär sind jetzt die **letzten zwei Runden**
  (vorherige Frage + Antwort + laufende Frage + Antwort), ungekürzt und in
  Originalreihenfolge. Alles davor bleibt gedimmter Hintergrund mit denselben
  Grenzen (`_HINTERGRUND_MAX = 12`, `_HINTERGRUND_LAENGE = 400`).
- Neu `_ohne_doppelte_frage()`: entfernt die laufende Frage aus den primären
  Turns, wenn sie dort schon steht (Vergleich nach `strip()`), damit sie nicht
  doppelt in den Prompt geht. Aufgerufen in `_build_messages()` direkt nach
  `_kontext_aufteilen()`.

Bewusste Grenze: **zwei** Runden, nicht mehr. Der Nachtrag ist klein (mehrere
Hundert Tokens), die Kostenbremse des Fokus-Konzepts bleibt erhalten.

## Beweis

- Neu: `backend/tests/test_kontext_aufteilen.py` (9 Testfunktionen, offline):
  letzte Runde ungekürzt, zwei Runden primär, Hintergrund weiter gekürzt,
  doppelte/abweichende/fehlende laufende Frage, leere History, History ohne
  Nutzernachricht.
- Prüfbefehl des Projekts, frisch gefahren:
  `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q`
  → **3269 passed, 1 skipped, Exit 0** (4:11 min).

## Abgrenzung

Nicht geändert: die Fokus-Anweisung im System-Prompt
(`KONTEXT_FOKUS_ANWEISUNG`), die Rolling-Summary, die Verlaufsgrenze
`history[-15:]` in `chat.py`, das Speichern der laufenden Frage (append-only).

## Offen (nicht in diesem Schritt)

- `chat.py` zählt in `history[-15:]` **alle** Einträge mit (auch Statuszeilen),
  die Duplikatprüfung sieht nur `history[-8:]` — eigene Aufgabe.
- `kontext_service.py` verklebt Zeilen mit einem literalen `"\n"` — eigener
  Fund, eigene Aufgabe.
- Protokollzeile in der Projekt-`CLAUDE.md` **absichtlich nicht** gesetzt: im
  gleichen Arbeitsbaum liegen fremde, bereits gestagte Änderungen (N24c
  Belegstand von Claude Code). Regel aus `AGENTS.md`: fremde halbfertige Arbeit
  nicht mitschleppen. Die Zeile wird nachgezogen, sobald der Baum frei ist.

Erstellt von Hermes (Ausführer), 30.09.2026.
