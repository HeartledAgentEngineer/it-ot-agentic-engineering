# Änderungsprotokoll 20.10.2026: Checks-Fenster, Serverzustand im Roboter-Symbol

## Anlass
Sebastian: „alles unter Checks im Menü verstecken", „Server läuft ins Symbol
integrieren", „Rest wegmachen". Vier Bereiche standen dauerhaft unter dem Kopf
der App und schoben am Handy den Chat aus dem Bild: `#hintergrund-leiste`,
`#server-zustand` (mit den Knöpfen „Protokoll“ und „Datenstand“), `#datenstand`
und `#server-protokoll`.

## Änderung
- `frontend/index.html`: Die vier Blöcke (IDs und Kinder unverändert) liegen jetzt
  im Fenster `#selbsttest-sheet`, in dessen `.sheet-list`, vor `#selbsttest-text`.
  Reihenfolge: `server-zustand`, `hintergrund-leiste`, `datenstand`,
  `server-protokoll`. Unter dem Kopf bleibt nur `#system-update-status`.
- Umbenennung nur in den Texten (IDs unverändert): Überschrift „Selbsttest“ →
  „Checks“; `#selbsttest-btn`: title „Checks – Zustand des Systems“, aria-label
  „Checks anzeigen“; aria-label des Fensters „Checks“.
- `frontend/app.js`: Das Roboter-Symbol `#agent-face` zeigt den Serverzustand
  mit den drei Werten aus `serverZustandPunkt(daten)`:
  - `ok`: Roboter ohne Filter, title „Server läuft · Modell bereit“
  - `kein-modell`: Roboter mit orangem Ton (CSS-Klasse `agent-face-kein-modell`),
    title „Server läuft · Modell nicht geladen“
  - `weg`: Schlafgesicht, grau (`agent-face-weg`), title „Server nicht erreichbar“
  Neue reine Funktionen `agentGesichtFuer(zustand)` → `{zeichen, klasse, titel}`
  und `agentZustandFuerOnline(online, letzterDetail)`; kleine Zeichenfunktion
  `zeichneAgentGesicht(zustand)`.
- Zwei Quellen schreiben ins Symbol: der 5-Sekunden-Takt auf `/api/health`
  (läuft unverändert weiter, auch wenn das Fenster zu ist) und `setOnline()`.
  Damit sie sich nicht widersprechen, merkt der Takt den letzten Detailzustand
  (`letzterServerDetail`): `setOnline(true)` zeigt `kein-modell`, wenn das der
  letzte Detailzustand war, sonst `ok`; `setOnline(false)` zeigt `weg`.
  `state.isOnline` bleibt wie vorher.
- Antippen des Roboter-Symbols (Klick, Enter, Leertaste) ruft
  `oeffneSelbsttestBlatt()` auf, dieselbe Funktion wie der Haken-Knopf.
  `role="button"`, `tabindex="0"`, `cursor: pointer`.
- `frontend/style.css`: Abschnitt „Checks-Fenster“: die vier Blöcke mit voller
  Breite, Rahmen und Abstand im Fenster; `#datenstand-liste` und
  `#server-protokoll-zeilen` mit `max-height: 40vh` und eigenem Scrollen;
  Klassen für das Roboter-Symbol. Dazu die Regel
  `.datenstand[hidden], .server-protokoll[hidden] { display: none; }`: Bisher
  überstimmte `display: flex` der Klassen das `hidden`-Attribut, die beiden
  Bereiche waren also nicht wirklich zugeklappt (siehe „Grenzen“).
- Kommentare in `index.html`, `app.js`, `style.css` und den betroffenen Tests, die
  „dauerhaft sichtbar am oberen Rand“ behaupteten, nennen jetzt den neuen Ort.
- Funktion der Knöpfe (Protokoll/Datenstand auf- und zuklappen, Neu messen,
  Aktualisieren, Neu starten) und die Abruftakte sind unverändert.
- Cache-Kennung: `app.js?v=20261020A` (vorher `20261018O`), `style.css?v=20261020A`
  (vorher `20261018E`).

## Prüfung
- `frontend/tests/test_server_zustand.js` (erweitert): die vier Blöcke liegen in
  `#selbsttest-sheet`, vor `#selbsttest-text`, in der Reihenfolge, nur einmal und
  nicht vor dem Chat; Überschrift und Beschriftungen „Checks“;
  `agentGesichtFuer` liefert für alle drei Zustände das Richtige;
  `agentZustandFuerOnline`; `setOnline` selbst (aus dem echten `app.js`
  ausgeschnitten, mit Attrappen für `state`/`dom`/`document`): `setOnline(true)`
  nach `kein-modell` bleibt `kein-modell`; Verdrahtung von Takt, Klick und
  Tastatur; Stil (Rollbereich 40vh, volle Breite, `[hidden]`).
- Angepasst: `test_selbsttest.js` (Blöcke im Blatt), Kommentare in
  `test_hintergrund_leiste.js`, `test_datenstand.js`, `test_server_protokoll.js`.
- Lauf über `backend/tests/test_frontend_node.py` und einzeln mit `node`.

## Bewusste Grenzen
- Die Anzeige des Serverzustands am Handy und das Aussehen des Fensters sind nicht
  im echten Browser/auf dem Handy gesehen worden; geprüft ist der Quelltext
  (Tests) und die Reihenfolge im HTML. Der orange Ton ist ein CSS-Filter auf dem
  Roboter-Emoji (`sepia`/`saturate`/`hue-rotate`) und sieht je nach Emoji-Schrift
  des Geräts etwas anders aus.
- Ohne geöffnetes Fenster sieht man nur noch den Roboter, nicht mehr den Text
  („Modell bereit · 42 Erinnerungen · Stand …“) und nicht mehr „Es läuft …“ der
  Hintergrundarbeit; beides steht erst im Fenster „Checks“. So gewünscht.
- Der Fehler mit `hidden` bei Datenstand/Protokoll bestand vorher schon (der
  Bereich war trotz `hidden` sichtbar). Er ist hier mit behoben, weil beide im
  Fenster sonst ständig offen stünden.
- Das Fenster „Checks“ lädt den Selbsttest-Text weiterhin nur beim Öffnen und auf
  „Aktualisieren“ (kein Auto-Polling); die Takte von Serverzustand und
  Hintergrund-Leiste laufen dagegen immer, weil sie das Symbol speisen.
- IDs und Funktionsnamen mit „selbsttest“ blieben bewusst unverändert, damit
  nichts bricht; nur Texte und Beschriftungen heißen jetzt „Checks“.
