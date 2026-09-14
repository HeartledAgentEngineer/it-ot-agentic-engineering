# Changelog 2026-09-14 — Quiz lässt sich wieder beenden + Modell auf V4.1-Flash

## 1. „Ich kann das Quiz nicht beenden" — Ursachen und Fix

**Symptom:** Die Quiz-Karte bleibt stehen. Der ✕-Knopf tut nichts, „quiz
beenden" antwortet „Es läuft gerade keine Quiz-Sitzung.", und es kann sogar
sein, dass 1,5 s später doch wieder eine neue Frage aufklappt.

**Ursache A — `_quizAktiv` war nach Reload/Fortsetzen `false`:**
Der ✕-Knopf ruft `beendeQuizAktiv()`, und die Funktion war komplett in
`if (_quizAktiv) { … }` gekapselt. `_quizAktiv` wird aber **nur** in
`quizStart()` auf `true` gesetzt. Wird eine Quiz-Karte aus dem Verlauf
wiederhergestellt (Reload) oder per „quiz fortsetzen" aufgebaut, blieb
`_quizAktiv` `false` → der ✕-Knopf war ein **No-Op**, und der Textbefehl
meldete fälschlich „keine Quiz-Sitzung".

**Ursache B — Auto-Weiter-Timer lief nach dem Beenden weiter:**
Nach jeder Antwort/Überspringen (auch im 0-Gesichter-Zweig) planen drei
`setTimeout(naechsteQuizRunde, 1500/1600)` die nächste Frage.
`naechsteQuizRunde()` hatte bewusst **keinen** `_quizAktiv`-Guard. Wer
innerhalb dieser 1,5 s beendete, bekam die nächste Frage trotzdem — das Quiz
ließ sich nicht beenden.

**Fix (`frontend/app.js`):**
- `beendeQuizAktiv()` ist nicht mehr an `if (_quizAktiv)` gekoppelt (der
  Funktion hängt nur der ✕-Knopf der Quiz-Karte an).
- Beim Beenden wird die laufende Kette abgeräumt: `_quizWeiterAbbrechen()`
  (Timer), `_rundeToken++` (bereits angestoßene Runden entwerten sich) und
  `_analyseAbort.abort()` (laufende Gesichts-Analyse abbrechen).
- `_quizWeiterPlanen(ms)` ersetzt die drei losen `setTimeout`-Aufrufe: genau
  ein Timer, jederzeit abbrechbar, und er blättert nur weiter, wenn die
  Sitzung noch läuft.
- `naechsteQuizRunde()` baut ohne laufende Sitzung (`!_quizAktiv`) keine Runde
  mehr auf.
- `_quizAktiv = true` beim Wiederherstellen (`_baueOffeneQuizKarte`) und beim
  „quiz fortsetzen" — eine sichtbare Quiz-Karte IST eine laufende Sitzung.
- Textbefehl „quiz beenden"/„quiz stoppen"/„stopp" ruft jetzt
  `beendeQuizAktiv()` (Karten + Bedienung weg) statt nur ein Flag zu setzen;
  als laufend gilt auch eine sichtbare Quiz-Karte.
- Cache-Bust `app.js?v=20260914bY`.

**Test:** `frontend/tests/test_quiz_ende.js` (Node, ohne Browser) schneidet die
echten Funktionen aus `app.js` heraus und prüft in einer Stub-Umgebung:
Timer feuert in laufender Sitzung · nach dem Beenden kommt **keine** neue Runde
· Karte wird geleert · Meldung erscheint · Token/Analyse entwertet ·
doppeltes Beenden harmlos. Aufruf: `node tests/test_quiz_ende.js app.js`
(aus `frontend/`). 8/8 grün.

**Bedienung (fertig):** ✕ oben rechts in der Quiz-Kopfzeile — oder in den Chat
tippen: `quiz beenden` (auch `quiz stoppen`, `quiz aus`, `stopp`).

## 2. Standardmodell der App → DeepSeek V4.1 Flash

Sebastian-Wunsch: das neueste Modell aufrufen.

- OpenRouter-ID geprüft: **`deepseek/deepseek-v4.1-flash`** existiert (mit
  Punkt; `deepseek-v4-flash` war der alte Stand).
- `backend/.env`: `LLM_MODEL=deepseek/deepseek-v4.1-flash` (nicht versioniert).
- `backend/app/config.py`: `llm_model`-Default + `allowed_models_fallback` +
  `favorite_models` auf das neue Modell gesetzt.
- `backend/app/modelle_de.py`: deutsche Katalog-Beschreibung ergänzt.
- Hermes selbst (`~/.hermes/config.yaml`) lief **bereits** auf
  `deepseek/deepseek-v4.1-flash` — dort war nichts zu tun.

**Verifikation (live):** Server-Neustart, dann
- `/api/health` → `{"status":"ok", …}`,
- `/api/models` → `"aktuell": "deepseek/deepseek-v4.1-flash"`, Modell im
  Katalog samt deutscher Beschreibung,
- Startup-Log: `LLM configured: model=deepseek/deepseek-v4.1-flash`.

**Hinweis Anzeige:** Die Modellwahl in der Oberfläche merkt sich das zuletzt
gewählte Modell. Wer dort vorher explizit ein anderes Modell gewählt hat,
sieht weiterhin dieses — dann im Picker auf „DeepSeek V4.1 Flash" umstellen.
