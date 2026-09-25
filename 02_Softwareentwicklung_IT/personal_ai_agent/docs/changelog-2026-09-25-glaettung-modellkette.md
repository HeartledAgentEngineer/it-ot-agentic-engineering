# Changelog 25.09.2026 — Glättung: Modellkette statt eines einzigen Modells

## Befund

Die Sprachglättung (`glätte`) im Backend lief über **ein** fest verdrahtetes Modell:
`google/gemini-2.0-flash-001`. OpenRouter hat dieses Modell **abgekündigt** — jeder
Aufruf endete im `404`. Weil der Fehler nur im Log stand und der Aufrufer bei einem
Fehlschlag den Rohtext weiterverwendet, lief die **Spracheingabe wochenlang
ungeglättet** durch, ohne dass es auffiel. Bemerkt am 25.09.2026 — **dieselbe
Ursache** wie beim Projekt `typeFREE`.

## Änderung

**Datei:** `backend/app/services/llm_service.py`

1. **`POLISH_MODELS`** — Kette statt Einzelmodell. Der Reihe nach:
   - `google/gemini-2.5-flash` — 0,8 s und gründlich (Messung 25.09.2026)
   - `google/gemini-3.5-flash-lite` — Ausweichweg, ähnlich schnell
   - `google/gemini-2.5-flash-lite` — letzter Ausweichweg, günstigstes Modell
2. **Jeder Fehlschlag wird geloggt**; gelingt die Glättung über ein Ausweichmodell,
   steht das als `INFO` im Protokoll. Erst wenn **alle** Modelle scheitern, gibt die
   Funktion `None` zurück — der Aufrufer verwendet dann den Rohtext.
3. **`POLISH_ANWEISUNG` erweitert** um Regel 5–8 (die Glättung darf den Sinn nicht
   verbiegen):
   - **5.** Anrede und Blickwinkel bleiben (`ich` bleibt `ich`, `du` bleibt `du`).
   - **6.** Sprechakt bleibt: Aussage bleibt Aussage, Frage bleibt Frage — auch das
     Satzzeichen am Ende.
   - **7.** Kein Erzähl- oder Fragestil — so knapp und direkt, wie gesprochen.
   - **8.** Fachbegriffe und Denglisch bleiben (`deployen`, `der Commit`);
     ähnlich klingende Fachwörter nach dem Zusammenhang trennen
     (`Comet` = Browser, `Commit` = Git-Aktion).

## Prüfung

```
cd 02_Softwareentwicklung_IT/personal_ai_agent/backend
.venv/Scripts/python -m pytest tests/ -q
→ 358 passed, 3 warnings in 131.62s (Exit 0)
```

Ausgeführt am 25.09.2026, vollständig, mit dem Projekt-venv.

## Folge-Regel (gilt für jedes Modell im Projekt)

Ein abgekündigtes Modell darf die Funktion **nie still** abschalten. Deshalb:
Modell-Listen statt Einzelnamen, und jeder Ausfall muss **sichtbar** geloggt werden —
sonst fällt es wochenlang niemandem auf.
