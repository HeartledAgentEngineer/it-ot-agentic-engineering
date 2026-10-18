# Live-Status im Chat: die Beschriftung sagt jetzt den echten Zustand (S7b)

**Datum:** 18.10.2026 · **Schritt:** S7b (To-do-Punkt 8 „Hermes wartet", Frontend-Teil)
**Geänderte Dateien:** `frontend/app.js`, `frontend/index.html`,
`frontend/tests/test_live_status_indikator.js` (neu), dieses Protokoll

## Anlass

Der Backend-Teil von S7 hat die Meldung ehrlich gemacht („Liegt bereit — gerade arbeitet niemand
daran."). Die **Beschriftung des grünen Balkens** im Chat behauptete aber weiter eine Bearbeitung:

```js
indicator.textContent = status === 'laeuft' ? '⚡ arbeitet' : '⏳ wartet';
```

Jeder Zustand außer „laeuft" — auch „offen", also „niemand hat die Aufgabe übernommen" — hieß damit
„wartet". Das liest sich wie „gleich ist jemand dran" und war genau die Zusage, die es nicht gibt
(auf dem Handy läuft kein lokaler Hermes, der PC ist nicht erreichbar).

## Was geändert wurde

- Neue **reine** Funktion `hermesLiveIndikator(status)` in `frontend/app.js` (bei
  `hermesLiveJobWaehlen`, ohne DOM testbar) — eine Quelle für die Beschriftung:

  | Zustand des Auftrags | Beschriftung |
  |---|---|
  | `laeuft` | `⚡ arbeitet` |
  | `fertig` | `✅ fertig` |
  | `fehler` | `❌ fehler` |
  | alles andere (u. a. `offen`, unbekannt) | `⏳ liegt bereit` |

  Die Zustandsnamen sind die des Servers (`backend/app/services/auftrag_service.py`: `offen`,
  `laeuft`, `fertig`, `fehler`).
- **Beide** Stellen, die die Beschriftung setzen (der Poller und der Zweig „fertig/fehler"), rufen
  jetzt diese eine Funktion auf — vorher stand die Zeichenkette zweimal im Code.
- `frontend/index.html`: Cache-Schlüssel `app.js?v=20261016G` → **`?v=20261016H`** (sonst behält
  der Browser die alte Fassung).
- Kein Symbol und keine Farbe wurde hinzugefügt oder entfernt; nur die **Wörter** sind ehrlich.

## Belege

- **Neuer Test** `frontend/tests/test_live_status_indikator.js` (15 Prüfungen, Exit 0): jeder der vier
  Serverzustände einzeln, dazu fünf unbekannte Werte (`undefined`, `null`, `''`, `'unbekannt'`,
  `'WARTET'`) — keiner davon darf „arbeitet" behaupten; drei Quelltext-Wächter (alte Wendung weg,
  genau **zwei** Aufrufe der Funktion, **kein** direkter Text am Indikator).
- **Gegenprobe:** derselbe Test gegen `git show HEAD:…/frontend/app.js` → **12 Prüfungen rot**, Exit 1
  (die alte Fassung kennt die Funktion nicht und trägt die Wendung an Zeile 9389).
- **Alle Frontend-Tests** über den Prüfbefehl: `pytest tests/test_frontend_node.py -q` → **42 passed**.
- **Volles Tor** über den pre-commit-Haken (`cd backend && .venv/Scripts/python -m pytest tests/ -q`)
  → Zahlen und Exit-Code stehen im Tor-Protokoll des Commits.

## Ehrliche Grenzen

- Nachgestellt ist der **Mechanismus**: welcher Text bei welchem Serverzustand erscheint. Eine
  Sichtprüfung am Gerät mit echtem, offenem Auftrag ist **nicht** erfolgt — sie bleibt Sebastians
  Abnahme am Handy.
- Der Balken verschwindet weiterhin nach seiner Frischegrenze (30 Minuten ohne neue Meldung) von
  selbst; daran wurde nichts geändert.
- Der Weg „ohne erreichbaren Hermes selbst antworten" ist weiterhin **nicht** gebaut (Entscheidung
  aus S7: klare Meldung statt Modellaufruf).
- Die Beschriftung nutzt weiterhin die vorhandenen Zeichen (`⚡ ⏳ ✅ ❌`) — die **Hintergrund-Leiste**
  ist bewusst symbolfrei; der Live-Balken war es vorher nicht, und ein reiner Wortwechsel gehört in
  diesen Schritt, kein Umbau der Darstellung.
