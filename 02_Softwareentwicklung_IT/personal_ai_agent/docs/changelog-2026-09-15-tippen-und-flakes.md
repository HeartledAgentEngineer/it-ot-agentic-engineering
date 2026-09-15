# Änderung 15.09.2026 — Serielles Tippen, 4-Zeilen-Blöcke, Test-Flakes gehärtet

## 1. Serielles Tippen statt zwei paralleler Blasen (Frontend)

**Wunsch Sebastian:** „Ein Block wird geschrieben — wenn der Block fertig ist,
erscheint erst der nächste. Nicht zwei tippende Blasen parallel." Außerdem soll
das Tempo über den Regler (Zahnrad) im Chat einstellbar sein.

**Befund:** Die Gedanken-Blasen tippten zwar schon in einer Kette
(`_gedankenTippWartend`), aber die **Antwort** blendete **gleichzeitig** daneben
ein (`_zeigeEingeblendet`, 8 Zeichen je Frame). Das ergab den Eindruck zweier
parallel tippender Blasen.

**Fix (`frontend/app.js`):**
- `_zeigeEingeblendet()` bricht ab, solange eine Zwischenmeldung tippt
  (`if (_gedankenTippWartend > 0) return;`) — der Puffer wartet, es tippt immer
  nur **eine** Blase.
- Das Tipp-Tempo der Zwischenmeldungen folgt jetzt dem Regler:
  `_tempoFaktor = clamp(state.streamMs / 120, 0.25, 3)`.
- Cache-Bump `?v=20260915B` → **`?v=20260915C`**.

## 2. Vier Zeilen pro Block (Daemon)

`FLUSH_MAX_ZEILEN` **2 → 4** (Wunsch Sebastian: „vier Zeilen, wenn es inhaltlich
zusammenpasst"). Rohausgabe bleibt bei 4 Zeilen je Block
(`ROH_BLOCK_ZEILEN = 4`), Blöcke tragen weiter den Zeitstempel.

## 3. Test-Flakes gehärtet — **und ein Datenrisiko geschlossen**

**Befund (beim Commit blockierte der neue Hook):** Zwei volle Läufe brachten
jeweils einen **anderen** roten Test in der Gesichter-Familie
(`test_person_speichern_und_lesen`, `test_proaktiver_kontext_wuerde_gemeldet`,
im Sammellauf mal `test_kontext_block_enthaelt_namen`).

**Ursache:** Diese Tests schrieben direkt in `gesichter_service.KATALOG_DATEI`
— den **echten Katalog** (`backend/app/gesichter_katalog.json`) — und **leerten
ihn** (`open(..., "w")`). Zwei Folgen:
1. **Quer-Interferenz** zwischen Testdateien → flakiges Gate.
2. **Datenrisiko:** Auf einem Gerät mit echter Personen-Merkliste hätte ein
   Testlauf diese geleert. Auf dem PC war kein Schaden (der Katalog liegt nur
   auf dem Handy), das Risiko ist jetzt aber ausgeschlossen.

**Fix:** Autouse-Fixture in `tests/test_gesichter_service.py` und
`tests/test_gesichter_chat.py`, die `KATALOG_DATEI` auf `tmp_path` umbiegt —
jeder Test bekommt seinen eigenen Katalog.

## Verifikation

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q     # 3× hintereinander: 224 passed
cd frontend && node --check app.js                          # Exit 0
cd frontend && node tests/test_serielles_tippen.js app.js   # alle Prüfungen grün
```

**Neuer JS-Test** `frontend/tests/test_serielles_tippen.js` (5 Prüfungen):
Antwort wartet auf tippenden Block · weiterhin 8-Zeichen-Blöcke · Tempo nutzt
`state.streamMs` · Gedanken tippen in einer Kette.

## Noch offen

- Live prüfen (Handy): Fühlt sich das Tippen jetzt seriell an? Passt die
  Blockgröße von 4 Zeilen? Tempo über das Zahnrad testen.
- Der Regler skaliert das Tippen der Zwischenmeldungen; ob der Wertebereich
  (0,25×–3×) reicht, zeigt der Praxistest.