# Server-Zustand sichtbar (To-do Punkt 12)

**Datum:** 18.10.2026 · **Schritt:** S12 (To-do-Punkt 12 „Server-Zustand sichtbar machen")
**Geänderte Dateien:** `frontend/index.html`, `frontend/style.css`, `frontend/app.js`,
`frontend/tests/test_server_zustand.js` (neu), dieses Protokoll

## Anlass

Sebastian: „Kann ich gar nicht mehr überprüfen, ob der Server läuft. Im Frontend sehe ich es nicht,
außer wenn irgendwas nicht lädt. Und im Terminal kann ich nicht nachgucken."

Der Server läuft seit dem Umbau **abgekoppelt im Hintergrund** — seine Ausgaben landen nirgends
sichtbar. Damit fehlte jede Möglichkeit, den Zustand zu prüfen, ohne auf einen Fehler zu warten.

## Was geändert wurde

- **Neue kleine Statuszeile** `#server-zustand` in `frontend/index.html`, direkt unter der
  Hintergrund-Leiste und **flach im Fluss** (kein schwebender Kasten über dem Chat — siehe
  Punkt 9). Ein **farbiger Punkt** trägt den Zustand, der davor/daneben stehende Text nennt ihn
  im Klartext (Sebastians Regel: keine Häkchen-/Statussymbole im Chat).
- **Zwei reine Funktionen** in `frontend/app.js`, ohne DOM testbar:

  | Funktion | Aufgabe |
  |---|---|
  | `serverZustandPunkt(daten)` | `ok` (Server läuft, Modell bereit) · `kein-modell` · `weg` (keine brauchbare Antwort) |
  | `serverZustandText(daten)` | eine Zeile: „Server läuft · Modell bereit · 42 Erinnerungen · Stand 0.1.0" bzw. „Server nicht erreichbar" |

- **Quelle:** `GET /api/health` (`backend/app/main.py`) — liefert `status`, `version`,
  `llm_configured`, `memory_count`; die Route ist in `backend/app/router/auth.py` ausdrücklich von
  der Anmeldung ausgenommen (`OPEN_API_PFIXE`), funktioniert also auch ohne Schlüssel.
  **Kein Backend geändert.**
- **Takt 5000 ms** (`SERVER_ZUSTAND_TAKT_MS`) plus Sofort-Abruf beim Zurückkommen in die App
  (`visibilitychange`). Bei nicht erreichbarem Server wechselt die Anzeige damit innerhalb
  weniger Sekunden auf „Server nicht erreichbar" (Prüfkriterium des Punktes 12) — und wieder
  zurück, sobald er antwortet. Alte Angaben bleiben **nicht** stehen.
- **Farben** in `frontend/style.css` (Dunkelmodus): Punkt grün (`ok`), orange (`kein-modell`),
  rot (`weg`); Text bei `weg` in hellerem Rot. Klartext erzählt denselben Zustand, die Farbe ist
  nur die Abkürzung.
- Cache-Schlüssel `app.js?v=20261018J` → **`?v=20261018K`**, `style.css?v=20261016D` →
  **`?v=20261018A`** (sonst behält der Browser die alten Dateien).

## Grenzen (ehrlich)

- Die Anzeige sagt **nur**, was `/api/health` antwortet. Ein hängender (nicht antwortender)
  Server erscheint als „nicht erreichbar" — das ist gewollt.
- **Erinnerungen** = `memory_count` aus `/api/health` (Anzahl der Einträge im Gedächtnis), nicht
  die Zahl der Personen-Erinnerungen.
- Geprüft ist der Mechanismus und die Darstellung im echten Browser; die **Abnahme am Handy**
  (Server anhalten → Anzeige wechselt) bleibt Sebastians Schritt.

## Belege

- **Neuer Test** `frontend/tests/test_server_zustand.js` (läuft automatisch im Prüfbefehl über
  `backend/tests/test_frontend_node.py`): schneidet die **echten** Funktionen aus `app.js` und
  prüft 30 Punkte — vier Zustandsfälle der Ampel (u. a. `undefined`, `{}`, fremder `status`,
  Zeichenkette statt Objekt), sieben Textfälle (Einzahl, fehlende Zahl/Stand, unbrauchbare Zahl,
  keine Symbole, genau eine Zeile), die Verdrahtung (HTML-Elemente, `fetch` auf `/api/health`,
  Takt, `data-zustand`-Setzung) und die Darstellung (eigene Punktfarbe je Zustand, eigener
  Hintergrund). Aufruf: `node tests/test_server_zustand.js` → **Exit 0**.
- **Gegenprobe** (Messskript außerhalb des Repos, `…/cache/scratch/gegenprobe_s12/`): derselbe
  Test gegen `app.js`/`index.html`/`style.css` aus **HEAD** → bricht ab mit
  „Funktion nicht gefunden: serverZustandPunkt", **Exit 1** — die Fähigkeit gab es vorher
  nachweislich nicht.
- **Alle Frontend-Tests:** `pytest tests/test_frontend_node.py -q` → **44 passed** (43 vorher +
  dieser neue).
- **Rendermessung im echten Browser** (Edge, Belegskript außerhalb des Repos
  `…/cache/scratch/server_zustand_messen.js`, echte `index.html` + `style.css`):
  bei **1400 px** liegt die Zeile zwischen Kopf (bis 69 px) und Chat (ab 123 px), Höhe 25 px,
  `data-zustand` folgt der Antwort, Punkt 9 × 9 px, **Überlappung mit dem Chat: 0**,
  Dokument-Überlauf **0**; bei **380 px** dasselbe (Kopf bis 61 px, Zeile 90–115 px, Chat ab
  115 px, Überlauf 0). Ohne Server zeigte die Seite von selbst „Server nicht erreichbar" mit
  rotem Punkt (rgb(224, 85, 85)) — der ehrliche Weg greift live.
  Die drei Zustände durchgespielt: Punkt `ok` rgb(87, 196, 106), `kein-modell` rgb(255, 184, 107),
  `weg` rgb(224, 85, 85); Text auf dem dunklen Grund (`#1a1a2e`) hell und lesbar.
- **Sichtprüfung** der gerenderten Seite bei 1400 px (Standbild im Scratch, angesehen):
  roter Punkt mit „Server nicht erreichbar" unter dem Kopf, flach im Fluss, darüber die
  Hintergrund-Leiste („Hintergrund-Status gerade nicht abrufbar"), darunter der Chat, nichts
  abgeschnitten oder überlappend.
