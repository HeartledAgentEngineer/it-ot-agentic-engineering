# Changelog 03.11.2026 — Alltagsprotokoll S3: Satz → Eintrag

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S3. Neues Modul
`backend/app/services/alltag_struktur.py`; der Endpunkt `POST /api/alltag/eintrag` (S5, Teil 2)
baut darauf auf.

## Was es tut

`strukturieren(text, quelle=, jetzt=, namen=, client=)` schickt einen Satz wie
„Letzte Stunde Wäsche gemacht, Stimmung gut, Anspannung 30, etwas genervt" in **einem** Aufruf
an das Modell und bekommt einen Eintrag nach dem S1-Schema zurück:

| Feld | Regel |
|---|---|
| `stimmung` | ganze Zahl 1–5 (sehr gut = 5 … sehr schlecht = 1), sonst `null` |
| `anspannung` | ganze Zahl 0–100, sonst `null` |
| `gefuehle` | Grundgefühl-Liste bevorzugt, eigene Worte erlaubt (≤ 40 Zeichen, ≤ 8 Stück); das vorherrschende steht vorn |
| `aktivitaet` | Text oder `null` |
| `von`/`bis` | aus „HH:MM" der Antwort; später als jetzt heißt gestern, über Mitternacht wird richtig gerechnet; nur ein Beginn endet spätestens jetzt; ohne Angabe die letzte Stunde |
| Schlaf | `art: schlaf` mit Ereignis aus `SCHLAF_EREIGNISSE` und Zeit (Standard: jetzt) |
| `originalworte`, `quelle` | lokal gesetzt, nie vom Modell |

Unbekannte Felder fallen weg, falsche Werte werden `null` und erscheinen in `fehlt`. Ist die
Antwort gar kein Eintrag (kein JSON, Liste, unbekannte Art), kommt `{"ok": false, "grund"}`.

## Datenschutz

- Nur über OpenRouter mit `provider.data_collection = deny`, Reasoning aus.
- Übergebene Namen gehen nur als Kürzel raus (`PIIShield`, auch Namensteile) und werden in der
  Antwort zurückgesetzt — in der Schreibweise, in der sie im Satz standen (die Namensliste darf
  kleingeschrieben sein). Die Originalworte bleiben unmaskiert und lokal.
- Log: nur Modell, Dauer, Zeichenzahl, erkannt ja/nein, Kosten. Kein Satz, keine Antwort.
- Fehlertexte enthalten nie den Text einer Ausnahme.

## Bewusst offen

- `essen` wird nicht erkannt — Entscheidung D steht aus.
- `GRUNDGEFUEHLE` ist vorläufig und wird mit der Begleitperson abgestimmt.

## Prüfung

- Neu: `test_alltag_struktur.py` (14, mit Attrappe, ohne Netz): Beispielsatz aus den
  Erfolgskriterien, ZDR im Aufruf, Namen maskiert und zurück, Schreibweise aus dem Satz,
  Zeitraum über Mitternacht, nur Beginn nie in der Zukunft,
  Uhrzeit von gestern, Schlaf-Ereignis, strenge Prüfung, unbrauchbare Antwort, Netzfehler ohne
  Ausnahmetext, kein Schlüssel, leerer Text, Log ohne Inhalt. Vorher rot (Modul fehlte).
