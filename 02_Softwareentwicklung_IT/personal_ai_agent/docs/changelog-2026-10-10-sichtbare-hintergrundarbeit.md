# Changelog 2026-10-10 — Sichtbare Hintergrundarbeit + ehrliches Werkzeug-Angebot

Quelle: drei Beschwerden von Sebastian (10.10.2026, aus echter Nutzung):

1. „Jetzt wollte mein Personal Agent Hermes, was gar nicht aktiviert ist" —
   im Chat erschien etwas mit einem Werkzeug „Hermes" bzw. einer Meldung, es sei
   nicht aktiviert; unklar, ob etwas passiert ist.
2. „Muss jederzeit ersichtlich sein, welche Hintergrundprozesse laufen" — ein
   Bildanalyse-Lauf lief 20–30 Minuten, im Chat war nichts davon zu sehen.
3. „Das muss auf jeden Fall konkreter sein, was er gerade macht" — vage Zeilen
   („liest") sind unbrauchbar.

## 1. Befund und Entscheidung: das „Werkzeug Hermes"

**Befund (belegt im Code):** `backend/app/services/faehigkeiten.py`
(`faehigkeits_block()`, geht in JEDEN System-Prompt) sagte dem Modell wörtlich:
„Du hast auch ein benutzbares Werkzeug: **Hermes** …". Ein aufrufbares Werkzeug
„hermes" gibt es aber nirgends: `werkzeuge.REGISTER` führt 10 Werkzeuge, keins
heißt hermes; `werkzeuge.schemata()` (die dem Modell angebotene Liste) enthält
es ebenfalls nicht. Wollte das Modell „Hermes" trotzdem aufrufen, bekam es nur
„Unbekanntes Werkzeug …" — und erzählte dem Nutzer dann von einem Werkzeug, das
es „nicht gibt"/„nicht aktiviert" sei. Die echte Übergabe an Hermes macht die
Weiche VOR dem Modell (`router/chat.py`, `services/chat_routing.py`) — das
Modell ist daran nie beteiligt (so entschieden; kein zweiter Weg = keine neue
Parallelität).

**Entscheidung (Variante „aus der angebotenen Liste entfernen"):**

- `faehigkeits_block()` sagt jetzt klar: Hermes ist **kein Werkzeug in deiner
  Werkzeugliste**; du kannst ihn nicht aufrufen; erfinde keinen Werkzeugaufruf,
  keine Übergabe und kein Ergebnis für ihn. Die Übergabe passiert automatisch
  im Backend, BEVOR du eine Nachricht zu sehen bekommst.
- Die alte Aufforderung „sage: ‚Das übernimmt Hermes.'" ist entfernt: sie ließ
  das Modell eine Übergabe behaupten — obwohl es solche Nachrichten (die
  delegiert werden) gerade NICHT mehr erreichen.
- Sicherheitsnetz in `werkzeuge.ausfuehren`: ein Aufruf `hermes` /
  `hermes_aufgabe` / … liefert eine klare, ehrliche Antwort („Es gibt KEIN
  aufrufbares Werkzeug „Hermes" …") statt des Standardsatzes.
- **Invariante mit Test:** `werkzeuge.pruefe_register()` prüft, dass JEDES
  angebotene Werkzeug (= jeder Eintrag aus `schemata()`) im Register steht und
  einen aufrufbaren Ausführer hat (und umgekehrt). Tests:
  `test_jedes_angebotene_werkzeug_hat_einen_ausfuehrer` plus Gegenprobe
  `test_pruefe_register_findet_fehlenden_ausfuehrer`.

## 2. Endpunkt `GET /api/laeuft` (Daten der Statusleiste)

Neu `backend/app/services/laufende_arbeiten.py` + `backend/app/router/laeuft.py`.
Drei Quellen, rein lesend, fehlertolerant (fehlende Ordner/Dateien stören nie):

1. **Angemeldete Backend-Arbeiten** — `merke_start` / `beende` / `setze`;
   asyncio-Tasks über `merke_task` (meldet sich beim Ende selbst ab).
   Angemeldet wird u. a. jede Werkzeug-Ausführung der Schleife
   (`werkzeug_schleife.laufe`): eine lange Suche steht damit in der Leiste,
   WÄHREND sie läuft. Bewusst KEINE rohe `asyncio.all_tasks()`-Liste — dort
   stünden immer die uvicorn-Server-/Verbindungs-Tasks, „Keine
   Hintergrundarbeit" wäre nie wahr.
2. **Laufende Aufträge** aus dem Auftragsbuch (Status `laeuft`, Track C):
   Name „Hermes: <Aufgabe>", letzte Statusmeldung (ohne `[ISO]`-Präfix),
   erkannter Fortschritt. `offen` (Warteschlange) zählt bewusst NICHT.
3. **Protokolldateien** `*.log` in `~/storage/downloads/hermes_diag/` und
   `…/termux-sicherung/` (Fallback `/sdcard/Download/...`; per
   `LAEUFT_LOG_BASIS` umlenkbar): je Datei Zustand (laeuft = mtime höchstens
   180 s alt, sonst steht, leer), letzte Zeile (nur das Dateiende wird gelesen)
   und Fortschritt („N von M", „N/M", „X %" — sonst leer; es wird nichts
   geraten).

Je Eintrag: `name`, `art`, `zustand`, `seit` (ISO), `dauer_sekunden`,
`letzte_zeile`, `fortschritt`. Sortierung: laufende zuerst, darin die am
längsten laufenden oben. Die Route hängt am X-API-Key-Schutz wie alle anderen.

## 3. Oberfläche: die Hintergrund-Leiste

`frontend/index.html` (direkt unter dem Kopf) + `style.css` + `app.js`:

- Dauerhafte Statuszeile: „Es läuft: <Name> seit <Dauer>"; ohne Arbeit
  „Keine Hintergrundarbeit"; mehrere Arbeiten: „Es laufen N Arbeiten: <Name>
  seit …".
- Antippen zeigt Einzelheiten (Zustand, Startzeit, Dauer, Fortschritt, letzte
  Zeile).
- Erneuert sich selbst alle 15 s und sofort beim Zurückkommen in die App
  (`visibilitychange`); ist der Server kurz weg, steht ehrlich
  „Hintergrund-Status gerade nicht abrufbar".
- Deutsch, ohne Haken-/Statussymbole, keine Emojis (als Testwache im
  Frontend-Test enthalten).
- Bleibt auch im VERLAUF sichtbar — das Element liegt außerhalb der
  Nachrichtenliste und wird vom Verlauf nicht überschrieben.
- Cache-Kennungen hochgezogen: `app.js?v=20261010C`, `style.css?v=20261010B`;
  die Versionstests (`test_foto_galerie.js`, `test_gruppen_quiz.js`) sind
  mitgezogen.

## 4. Konkrete Statuszeilen im Chat

- **Befund:** Die Status-Ereignisse des Backends (`{"status": …}` aus
  `werkzeug_schleife`) kamen im Browser an, wurden in `app.js` aber VERWORFEN —
  es blieb „🔍 Agent liest deine Nachricht…" stehen, obwohl z. B. eine
  Fotos-Suche lief. Jetzt zeigt die Arbeits-Bubble den echten Schritt
  (`setzeTutZeile(daten.status)`).
- **Konkreter Inhalt:** `werkzeuge.status_text(name, argumente)` nennt die
  Argumente des Aufrufs, z. B. „🔧 sucht Fotos mit einer Person (Person „Anna") …"
  statt nur „🔧 sucht Fotos mit einer Person …". Für die Leiste liefert
  `werkzeuge.laufender_name(...)` dieselbe Konkretion ohne Symbole.
- **Lange Arbeit starten (Track C):** Die Übernahme-Meldung im Chat nennt jetzt
  konkret: „Gestartet HH:MM Uhr · Womit: lokaler Hermes im Termux-CLI, Modell X ·
  Zeitbudget bis zu N Minuten." (`hermes_local.arbeits_start_zeile()`, genutzt in
  `router/chat.py` und `services/chat_routing.py`) und sagt, dass der
  Fortschritt oben in der Leiste sichtbar bleibt.

## 5. Tests

- `backend/tests/test_laeuft.py` (neu, 14 Tests): leer; eine laufende Arbeit
  (frisches Protokoll mit Fortschritt); fehlende Ordner/Dateien; leere Datei;
  altes Protokoll „steht"; Sicherungs-Ordner; Sortierung; Buch-Auftrag
  (Track C) inkl. `[ISO]`-Präfix und Fortschritt; offene Aufträge zählen nicht;
  Register an/ab; asyncio-Task meldet sich selbst ab; Fortschritts- und
  Zeilen-Erkennung; Key-Schutz der Route.
- `backend/tests/test_werkzeuge.py` (+6): jedes angebotene Werkzeug hat einen
  Ausführer; `pruefe_register()` sauber + Gegenprobe; `hermes` ist kein
  Werkzeug; konkrete Statuszeilen; Leisten-Name ohne Symbole.
- `backend/tests/test_faehigkeiten_prompt.py` (+1): Der Fähigkeiten-Block
  verspricht kein Hermes-Werkzeug mehr.
- `frontend/tests/test_hintergrund_leiste.js` (neu, 37 Prüfungen): Kopfzeile
  (leer/eine/mehrere/kaputt; nur echt laufende zählen), Dauer- und Zeit-Texte,
  Einzelheiten (laufende zuerst, stehende bleiben sichtbar), Symbolwache,
  Verdrahtung (Element, Abruf, 15-s-Takt, Status-Ereignisse, Fehlerzeile).

Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
**3694 passed, 2 skipped, Exit 0** (629 s).
Frontend: 27 von 27 Tests grün.

## Was Sebastian am Handy tun muss

1. **App-Knopf tippen** (oder App öffnen): Der Startweg zieht den neuen Stand
   (`git pull --ff-only`) — das läuft bei JEDEM Start, auch wenn der Server
   schon antwortet. Das Backend lädt die Änderungen selbst nach (uvicorn
   `--reload`).
2. **App neu laden** (schließen und wieder öffnen): erst dann lädt die
   Oberfläche die neue `app.js`/`style.css` (Cache-Kennungen hochgezogen) und
   die Leiste erscheint.
3. Danach gilt: Oben steht dauerhaft entweder „Keine Hintergrundarbeit" oder
   „Es läuft: … seit …" — antippen für Einzelheiten. Während einer laufenden
   Werkzeug-Ausführung oder eines Hermes-Auftrags wird die Leiste von selbst
   aktuell (alle 15 Sekunden).
