# Changelog 2026-09-25 — Spracheingabe: Kette, Rückfallweg und Regeln aus typeFREE

Anlass (Nutzer-Auftrag, diktiert): „die Verbesserung, die wir jetzt hier gebaut
haben, natürlich auch in meinen Personal AI Agent einbauen, im Chat Interface“ —
das Diktat landete bisher unverändert über die Eingabezeile im Chat, die
Erkennung war aber die alte.

Beim Nachsehen kam der eigentliche Befund: Die Glättung des Agents lief seit
Wochen **ins Leere**. Das Modell `google/gemini-2.0-flash-001` ist bei
OpenRouter abgekündigt (404) — derselbe stille Ausfall wie in typeFREE, nur
hier ohne Warnung, ohne Log-Zeile und ohne einen einzigen Test. Der Rohtext
wurde kommentarlos durchgereicht.

## 1. Glättung: Modellkette statt eines toten Modells
`backend/app/services/llm_service.py`:

- `POLISH_MODELS` = `google/gemini-2.5-flash` → `google/gemini-3.5-flash-lite`
  → `google/gemini-2.5-flash-lite` (alle drei per `/models` als lebend geprüft).
- `polish_text()` läuft die Kette durch. Scheitert ein Modell (404, Drosselung,
  leere oder unplausible Antwort), kommt das nächste dran; erst wenn alle
  scheitern, gibt es `None` und der Rohtext wird verwendet.
- Jeder Fehlschlag steht jetzt als `WARNING` im Log, der Totalausfall als
  `ERROR` — der stille Ausfall von vorher kann so nicht wieder passieren.
- Ausweichmodelle werden beim Erfolg gemeldet (`Glättung über Ausweichmodell …`).

## 2. Glättungs-Regeln wie in typeFREE (Regeln 5–8)
`POLISH_ANWEISUNG` ist jetzt deckungsgleich mit typeFREE:

- **5. ANREDE UND BLICKWINKEL BLEIBEN** — 'ich'/'du'/'Sie' werden nie getauscht.
- **6. SPRECHAKT BLEIBT** — Aussage bleibt Aussage, Frage bleibt Frage.
- **7. KEIN ERZÄHL- ODER FRAGESTIL** — nichts wird nach-erzählt oder ausformuliert.
- **8. FACHBEGRIFFE UND DENGLISCH BLEIBEN** — 'deployen' bleibt 'deployen';
  'Comet' (Browser) und 'Commit' (Git) werden auseinandergehalten.
- Verbot ergänzt: „Die Anredeform oder den Sprechakt ändern.“

## 3. Erkennung: zweiter Weg und Vokabular
`transcribe()` und `_audio_puffer()`:

- `TRANSCRIBE_MODELS` = `microsoft/mai-transcribe-1.5` (zuerst) →
  `openai/whisper-large-v3` (Rückfall). Vorher gab es **einen** Versuch: fiel
  der aus, war das Diktat weg.
- Der Rückfallweg bekommt `language="de"` und `prompt=WHISPER_VOKABULAR`
  (Fachwörter, Denglisch, Azure-Kurs) — `mai-transcribe` kennt beides nicht,
  dort wird nichts erfunden.
- `_audio_puffer()` liefert **pro Versuch einen frischen Puffer**: der Client
  liest den alten leer, ein zweiter Versuch hätte 0 Bytes geschickt.
- Log nennt jetzt den liefernden Weg („Erkannt über …"), nicht mehr „Whisper".

## Messwerte (Referenzaudio, 69,7 s deutsch, 176 Wörter, 25.09.2026)

| Weg (OpenRouter `/audio/transcriptions`) | Wortfehler | Ende vollständig |
|---|---|---|
| `microsoft/mai-transcribe-1.5` (Erstweg) | **1,1 %** | ja |
| `openai/whisper-large-v3` (Rückfallweg) | 3,4 % | ja |

Gemessen mit `typeFREE/windows/sprachmessung.py` gegen bekannten Text.

## Datenschutz-Entscheidung
Beide Wege liegen **innerhalb von OpenRouter** — es kommt kein weiterer Anbieter
hinzu. Die Aufnahme verlässt das Gerät nur dorthin, wohin der Text-Chat auch
geht. Die Architektur-Zeile „Kein externer STT" im Projekt-CLAUDE.md behauptete
das Gegenteil und ist korrigiert.

## Verifikation
- Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **376 passed**, Exit 0 (vorher 358; die 18 neuen stehen in
  `tests/test_spracheingabe.py`).
- Neue Tests decken ab: Kette, Rückfallweg je Parameter, frischer Puffer,
  WebM/WAV-Erkennung, leere Antwort, unplausible Antwort, Totalausfall,
  Anweisungs-Regeln 5–8, Vokabular-Inhalt und -Länge.

## Folge-Regel (für jedes Modell im Projekt)

Ein abgekündigtes Modell darf eine Funktion **nie still** abschalten. Deshalb:
Modell-Listen statt Einzelnamen, und jeder Ausfall wird **sichtbar** geloggt —
sonst fällt es wochenlang niemandem auf.

## Offen
- Die Erkennung selbst (1,1 %) ist besser als der Glättungs-Zugewinn; ob der
  Agent später denselben Wegwahl-Schalter bekommt wie typeFREE (EU/Groq),
  entscheidet Sebastian — im Agent gilt weiter „nur OpenRouter".

## Hinweis zur Dokumentenlage

Eine Parallel-Session hatte dieselbe Ursache unabhängig beschrieben
(`changelog-2026-09-25-glaettung-modellkette.md`, Prüflauf mit 358 Tests). Zwei
Changelogs für eine Änderung sind Doku-Drift — der Inhalt (Folge-Regel oben,
Messwerte unten 376 statt 358) ist hier aufgegangen, die Doppeldatei entfernt.
