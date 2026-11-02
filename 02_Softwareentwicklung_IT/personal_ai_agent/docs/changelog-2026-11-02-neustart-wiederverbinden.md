# Changelog 02.11.2026 — Neustart: Wiederverbinden statt Tab-Tod

## Befund (Sebastian, Handy, mit Screenshot)
Nach einem bewussten Neustart (Server-Protokoll → Neustart, `POST /api/system/update`) wird der
Server gekillt, dann laufen `git pull` + Übernahmen (8–30 s), erst danach startet uvicorn wieder.
In dieser Lücke zeigte das Frontend den Schirm „Server nicht erreichbar / Tab jetzt schließen":
- Er **leerte den ganzen Chat** (`document.body.innerHTML = ''`).
- Er zählte **30 s runter** und rief am Ende `window.close()` — das wirkt in einem **normalen Tab
  nicht**. Der Countdown blieb bei 0 stehen, „passiert nix", und es gab **keinen Rückweg** in den
  Chat. Außerdem kein sichtbares Feedback, dass überhaupt etwas läuft.

## Lösung
Ein **nicht-zerstörender Wiederverbinden-Overlay** mit Feedback:
- Legt sich **über** den Chat (der Chat bleibt im Hintergrund erhalten — nichts wird geleert).
- Zeigt einen **Spinner** und eine **Klartext-Meldung** je Grund.
- **Pollt `/api/health` alle ~2 s**. Sobald der Server wieder antwortet, wird **einmal neu geladen**
  → automatisch zurück in den Chat.
- **Kein hängender Countdown, kein `window.close()`-Automatismus** mehr. Erst nach langer Totzeit
  (~60 s) erscheinen **„Erneut versuchen"** und **„Tab schließen"** als manuelle Knöpfe; gepollt
  wird weiter.

## Änderung (nur Frontend)

### `frontend/app.js` (Cache `?v=20261102F` → `20261102G`)
- Neu `wiederverbindenMeldung(grund)` — **reine** Funktion (ohne DOM/Netz, testbar), liefert
  `{titel, text}` je Grund `neustart` / `verloren` / `lange`; unbekannter Grund fällt auf `verloren`
  zurück. Nur Klartext, keine Symbole/Emojis (Screenreader-/Vorlese-freundlich).
- Neu `starteWiederverbinden(grund)` — baut `#reconnect-overlay` (per `createElement`/`textContent`,
  kein `innerHTML` → CSP-konform), pollt `/api/health`, lädt bei Rückkehr einmal neu. Guard
  `_wiederverbindenLaeuft`, damit Neustart-Knopf und Health-Check sich nicht überlagern.
- **Entfernt:** `_tryCloseTab`, `_showCloseOverlay` und das `document.body.innerHTML = ''` samt
  30-s-Countdown.
- `neuStarten()` ruft nach angenommenem `POST /api/system/update` sofort
  `starteWiederverbinden('neustart')` → sichtbares Feedback ab der ersten Sekunde.
- Der Auto-Close-Zweig in `checkHealth()` ruft statt `_tryCloseTab()` jetzt
  `starteWiederverbinden('verloren')` (unerwarteter Verbindungsverlust).

### `frontend/style.css` (Cache `?v=20261101A` → `20261102A`)
- Neu `#reconnect-overlay` (Vollbild, dunkel, zentriert), `.reconnect-spinner` +
  `@keyframes reconnect-spin` (sichtbarer Spinner), `.reconnect-titel`, `.reconnect-text`,
  `.reconnect-knoepfe`, `.reconnect-knopf` (Indigo-Akzent wie im übrigen UI).

## Tests (offline, Node)
- `frontend/tests/test_server_neustart.js` (war bereits als rot-vor-grün angelegt): Meldungstexte je
  Grund inkl. Rückfall und Symbol-Verbot; Verdrahtung (`starteWiederverbinden`, `#reconnect-overlay`,
  Aufrufstellen `neustart`/`verloren`, `/api/health`-Poll + `reload`, ~2-s-Takt); entfernte Sackgasse
  (`_showCloseOverlay`/`_tryCloseTab`/`body.innerHTML`); Darstellung (Overlay + Spinner im CSS);
  Cache (`app.js ≥ 20261102F`, `style.css ≥ 20261102A`).

## Beleg Rot vor Grün
- Vorher: `node tests/test_server_neustart.js` bzw. der pytest-Lauf brach ab
  (`Funktion nicht gefunden: wiederverbindenMeldung`) — belegt im vorangegangenen Prüfstand
  (62 passed, 1 failed: `test_server_neustart.js`).
- Nachher: `node tests/test_server_neustart.js` → „Alle Prüfungen bestanden" (22 Prüfungen).

## Nicht per Browser live geprüft
Das Verhalten ist erst sichtbar, wenn der Server tatsächlich neu startet (Lücke von Sekunden). Das
im laufenden Betrieb auszulösen wäre störend; die Logik ist stattdessen über die Node-Tests
abgesichert (Poll, Reload, Overlay-Aufbau, entfernte Sackgasse).

## Offen / nächste Schritte
- Erzählen-Filter („Ereignis suchen" / „Jahr").
- 50-Pixel-Gesichtsfilter als allgemeine Einstellung + Gesichtszuordnung neu laufen lassen.
- Löschen von Geschichten/Erinnerungen in der Oberfläche sichtbar verdrahten.
