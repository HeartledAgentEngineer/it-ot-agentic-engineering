# Changelog 2026-09-28 — N13b: Bilder im Chat, Anzeige (Galerie + Diashow)

> **Auftrag:** `docs/auftrag-n13b-bilder-anzeige.md` (Schritt **N13b** des
> Plans `docs/plan-nachtlauf-2026-09-26.md`).
> **Vorgänger:** N13a — liefert `GET /api/fotos/bilder` mit den Datei-Kennungen
> je Event. **Ausführer:** Hermes-Subagent (Codex-Kontingent erschöpft).
> **Kein git-Befehl ausgeführt, kein pCloud-Aufruf, keine Datei gelöscht.**

## Warum

Am Handy sollen Bilder **im Chat** sichtbar sein: Frage → Trefferliste →
Kacheln → Antippen = groß → Diashow. Die Daten liegen seit N13a bereit, die
Anzeige fehlte. Die Bilder werden **gestreamt**: `fetch` → Blob →
Objekt-URL; nach dem Ansehen bzw. beim Schließen wird die Objekt-URL wieder
freigegeben.

## Was gebaut wurde

### `frontend/app.js` — 8772 → **9195** Zeilen (+423; davon +5 aus dem Nachtrag des Planers)

**Teil A — vier REINE Funktionen** (ohne DOM, ohne Netz, ohne `API_BASE`; der
JS-Test schneidet sie wörtlich aus dieser Datei und führt sie in Node aus):

| Funktion | Regel |
| --- | --- |
| `fotoFrageErkennen(text)` | Trifft nur bei **Bild-Wort** (`foto/fotos/bild/bilder`) **und Zeige-Wort** (`zeig/zeige/zeig mir/anschauen/galerie/welche`). Kein Treffer bei `wie viele`, `wieviel`, `anzahl` (Zählfragen bleiben beim Text-Werkzeug aus N11) und nicht bei `upload`, `hochladen`, `löschen`. `jahr` = erste `20\d{2}`-Zahl, sonst `null`. `event` = erstes zutreffendes Wort der festen Liste `urlaub, konzert, geburtstag, hochzeit, festival, party` (Listenreihenfolge), sonst `null`. Nicht-String (leer, `null`, Zahl, `true`, Objekt) → `null`, kein Wurf. |
| `fotoKacheln(daten, maxKacheln)` | Nicht-Objekt, `ok !== true`, fehlende/ungültige `events` → `[]`. Nur ganzzahlige `datei_id > 0` (`true` ist **keine** Kennung). `name` fehlt → `""`. `thumb_klein` mit `groesse=120x120`, `thumb_gross` mit `groesse=480x480`. Reihung: Events und Dateien in der Reihenfolge der Antwort; Länge höchstens `maxKacheln` (fehlend/0/negativ/nicht-Zahl → `40`). |
| `fotoGalerieZeilen(daten)` | Kopfzeile `Treffer: <anzahl> Events, <n> Bilder` (n = Zahl **aller gültigen** `datei_id`s aus `daten.events`), je Event `· <event> (<jahr>) — <anzahl> Bilder`, höchstens 4 Event-Zeilen (also höchstens 5 Zeilen). Leere Antwort → genau eine Zeile `Keine Bilder gefunden`. |
| `fotoDiashowNaechster(index, anzahl, richtung)` | `richtung` `1` = vor, `-1` = zurück, alles andere = `1`; über die Enden **umlaufend**. `anzahl <= 0` → `0`. |

**Teil B — Anzeige:**

* Zweig in `sendMessage` **nach** den vorhandenen Befehlszweigen, **vor** dem
  Abbruch-Guard: `const fotowunsch = fotoFrageErkennen(text);` →
  `zeigeFotoGalerie(fotowunsch); return;`
* `zeigeFotoGalerie(wunsch)` — EINE Assistenten-Blase (`addMessage('', 'assistant')`
  + `zeigeBlaseMitText(...)`) mit `data-foto-galerie="1"`, Überschrift
  `🖼️ Bilder`, die Zeilen aus `fotoGalerieZeilen(daten)`, darunter ein Raster
  `<div data-foto-kacheln="1">` aus `fotoKacheln(daten)`.
  Lädt `GET /api/fotos/bilder` mit `limit=5`, `pro_event=40` und — nur wenn
  vorhanden — `jahr` und `event`; fehlende Werte werden **nicht**
  mitgeschickt. Fehlerfall (`ok !== true`, Netzfehler, HTTP ≠ 200): **eine**
  ehrliche Zeile mit dem `error`-Text des Endpunkts bzw.
  `Bilder nicht abrufbar (<Ursache>)` — kein Absturz, keine leere Blase.
  Ladefehler eines **einzelnen** Bildes: diese Kachel zeigt
  `Vorschau nicht verfügbar`, die übrigen bleiben.
* `fotoBildLaden(url)` — `fetch` → Blob → **Objekt-URL**; Fehlschlag → `null`.
  Jede erzeugte Objekt-URL wird in `_fotoObjekte` (ein `Set`) vermerkt.
* `fotoObjekteFreigeben()` — ruft `URL.revokeObjectURL` für alle vermerkten
  URLs, leert die Buchführung und liefert die Anzahl zurück.
* **Großansicht + Diashow**: Antippen einer Kachel öffnet
  `<div data-foto-gross="1">` mit dem Bild in `480x480`, Beschriftung (`name`),
  Zähler und den Knöpfen `‹ Zurück`, `Weiter ›`, `▶ Diashow` / `⏸ Stopp`, `✕`.
  `fotoDiashowNaechster` bestimmt den nächsten Index (umlaufend); die Diashow
  schaltet alle 3000 ms selbsttätig weiter und **gibt bei jedem Wechsel das
  vorherige Bild frei**. Schließen über `✕`, Hintergrund-Klick oder `Escape`
  ruft **immer** `fotoObjekteFreigeben()`; danach ist die Buchführung leer.
  Kacheln, deren Objekt-URLs dabei freigegeben wurden, sagen das ehrlich
  (`Vorschau freigegeben – erneut fragen`) statt ein kaputtes Bild zu zeigen.

### `frontend/style.css` — 1463 → **1586** Zeilen (+123)

Neuer Abschnitt „N13b — Bilder im Chat (Galerie + Diashow)" im vorhandenen
dunklen Look (vorhandene CSS-Variablen `--assistant-msg-bg`, `--border`,
`--accent`, `--bg-secondary`): `.foto-zeilen`, `.foto-kacheln` (Raster),
`.foto-kachel`, `.foto-kachel-bild`, `.foto-platzhalter`, `.foto-gross`,
`.foto-gross-panel`, `.foto-gross-bild`, `.foto-gross-kopf`,
`.foto-gross-knoepfe`, `.foto-knopf`.

### `frontend/index.html` — 273 Zeilen (unverändert), **Cache-Bump**

`app.js` von `?v=20260927B` → **`?v=20260928A`**,
`style.css` von `?v=20260925F` → **`?v=20260928A`**.

### `frontend/tests/test_foto_galerie.js` — **neu, 328 Zeilen, 145 Prüfungen**

Bauart wie `frontend/tests/test_selbsttest.js`: `extractFn(name)` schneidet die
vier reinen Funktionen wörtlich aus dem echten `app.js`, `eval` führt sie aus,
`pruefe(...)` zählt, Exit-Code 1 bei Fehlern. Zusätzlich Quelltext-Prüfungen
für Teil B: Zweig in `sendMessage` (und dass er **vor** dem Abbruch-Guard
steht), `data-foto-galerie`, `data-foto-kacheln`, `data-foto-gross`,
`revokeObjectURL`, kein direktes `/api/cloud/thumb` in `img.src`, keine
Speicher-APIs im Galerie-Bereich, `sw.js` cached im `/api/`-Zweig nichts, sowie
der Cache-Bump (`?v=` höher als vorher).

## Harte Regel: es wird NICHTS gespeichert

* Im Galerie-Bereich kommt **kein** `localStorage`, `sessionStorage`,
  `indexedDB`, `caches.`, `CacheStorage` und `serviceWorker.register` vor —
  im Test über den ausgeschnittenen Quelltext-Abschnitt belegt.
* Bilder laufen **nur** über `fotoBildLaden` (Blob → Objekt-URL). Es gibt
  keine Zuweisung eines `/api/cloud/thumb`-Pfades an ein `img.src`.
* `sw.js` wurde **nicht** angefasst: der `/api/`-Zweig ist
  netzwerk-zuerst (`fetch(request)`) und legt nichts in den Cache; die
  Anzeige ist im Test darauf geprüft.

## Gefahrene Befehle mit echter Ausgabe

### 1. Backend (unverändert) — Regressionstest

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

```
1876 passed, 3 warnings in 91.47s (0:01:31)
PYTEST_EXIT=0
```

### 2. Syntaxprüfung

```
node --check frontend/app.js
```

```
NODECHECK_EXIT=0
```

```
node --check frontend/tests/test_foto_galerie.js
```

```
TESTCHECK_EXIT=0
```

### 3. Der neue Test

```
cd frontend && node tests/test_foto_galerie.js app.js
```

```
… (145 OK-Zeilen) …
ERGEBNIS: alle Prüfungen grün
EXIT=0
```

Auszug der Gruppen (jede Zeile im Test ist eine Prüfung):

```
1) fotoFrageErkennen — Bild-Wort UND Zeige-Wort nötig        (29 Prüfungen)
1b) Zählfragen, Upload und Löschen bleiben ausgenommen        (7)
2) fotoKacheln — Kennungen, Reihenfolge, Klemmung            (25)
3) fotoGalerieZeilen — Kopfzeile, Event-Zeilen, Grenzen      (15)
4) fotoDiashowNaechster — Umlauf und Richtung                (14)
5) Verdrahtung im Quelltext (Teil B)                         (18)
6) Nichts wird gespeichert (harte Regel)                     (22)
7) Service Worker legt für /api/ nichts ab                     (5)
8) Cache-Bump, Styling und Datenschutz                       (10)
                                                     Summe  = 145
ERGEBNIS: alle Prüfungen grün
```

### 4. Alle JS-Tests

```
cd frontend && for f in tests/*.js; do if node "$f" >/dev/null 2>&1; then echo "OK   $f"; else echo "ROT  $f"; fi; done
```

```
OK   tests/test_chat_konsistenz.js
ROT  tests/test_conv_code_live_stream.js
ROT  tests/test_diff_darstellung.js
OK   tests/test_foto_galerie.js
ROT  tests/test_gedaechtnis_ui.js
OK   tests/test_gedanken_blasen.js
ROT  tests/test_options_assistent.js
ROT  tests/test_quiz_ende.js
ROT  tests/test_quiz_geo.js
ROT  tests/test_quiz_rahmen_quelle.js
ROT  tests/test_quiz_suche_vollstaendig.js
ROT  tests/test_ref_loeschen_ui.js
ROT  tests/test_selbsttest.js
OK   tests/test_serielles_tippen.js
ROT  tests/test_sprachaufnahme.js
ROT  tests/test_tastatur_und_textauswahl.js
```

Elf dieser Tests waren **schon vor dieser Änderung rot** — sie verlangen den
Pfad `app.js` als Argument (`process.argv[2]`), und ohne Argument bricht
`readFileSync` mit `ERR_INVALID_ARG_TYPE` ab. Mit dem Argument laufen sie
durch:

```
cd frontend && for f in tests/*.js; do if node "$f" app.js >/dev/null 2>&1; then echo "OK   $f"; else echo "ROT  $f"; fi; done
```

```
OK   tests/test_chat_konsistenz.js
OK   tests/test_conv_code_live_stream.js
OK   tests/test_diff_darstellung.js
OK   tests/test_foto_galerie.js
OK   tests/test_gedaechtnis_ui.js
OK   tests/test_gedanken_blasen.js
OK   tests/test_options_assistent.js
OK   tests/test_quiz_ende.js
OK   tests/test_quiz_geo.js
OK   tests/test_quiz_rahmen_quelle.js
OK   tests/test_quiz_suche_vollstaendig.js
OK   tests/test_ref_loeschen_ui.js
ROT  tests/test_selbsttest.js
OK   tests/test_serielles_tippen.js
ROT  tests/test_sprachaufnahme.js
ROT  tests/test_tastatur_und_textauswahl.js
```

### 5. Wegwerf-Rauchtest (nicht im Repo)

Der Galerie-Bereich wurde zusätzlich gegen eine Mini-DOM-Attrappe **wirklich
ausgeführt** (`fetch` → Blob → Objekt-URL, Raster, Großansicht, Weiter/Zurück,
Diashow-Knopf, Schließen). Der Prüfling lag außerhalb des Repos in einem
Zwischenspeicher-Ordner und wird nicht eingecheckt:

```
A) Galerie bauen (echter Durchlauf über fetch -> Blob -> Objekt-URL)
  OK   Anfrage enthält jahr, event, limit=5, pro_event=40
  OK   Raster vorhanden
  OK   3 Kacheln
  OK   3 Bild-Elemente per Objekt-URL
  OK   kein Bild trägt /api/cloud/thumb im src
  OK   alle Bilder tragen blob:-Objekt-URLs
  OK   Buchführung hat 3 Objekt-URLs
  OK   Blase trägt data-foto-galerie
  OK   Zeilenblock stimmt
B) Großansicht + Weiterschalten + Diashow
  OK   Overlay data-foto-gross vorhanden
  OK   Zähler zeigt 1 / 2
  OK   Name A steht in der Beschriftung
  OK   Großbild per Objekt-URL
  OK   vier Knöpfe vorhanden
  OK   Knopftexte ‹ Zurück / Weiter › / ▶ Diashow / ✕
  OK   Weiter springt auf Index 1
  OK   vorheriges Bild wurde freigegeben
  OK   neues Bild hat eine andere Objekt-URL
  OK   Zurück läuft um (1 -> 0)
  OK   Diashow-Knopf zeigt ⏸ Stopp
  OK   Stopp setzt den Knopf zurück
C) Schließen gibt ALLES frei
  OK   Buchführung ist leer
  OK   Overlay ist aus dem Baum
  OK   es wurden weitere URLs freigegeben
D) Fehlerfall: eine ehrliche Zeile statt Absturz
  OK   nur limit/pro_event ohne jahr/event
  OK   Blase ist NICHT leer
  OK   nennt „Bilder nicht abrufbar (HTTP 500)"
E) Netzfehler wirft nicht
  OK   kein Wurf bei Netzfehler
  OK   Bildabruf liefert null bei Fehler
RAUCHTEST: alle grün
SMOKE_EXIT=0
```

## Bedienung (Beispiele)

* `zeig mir die fotos` → Galerie ohne Filter.
* `welche bilder habe ich von 2023` → `jahr=2023`.
* `zeig mir die fotos vom urlaub 2022` → `jahr=2022` und `event=urlaub`.
* Zählfragen wie `wie viele fotos habe ich` laufen weiter über das
  Text-Werkzeug aus N11.
* Beispielfall für eine Datei-Kennung in Test und Doku (erfunden):
  `47110000001`.

## Nachtrag des Planers (28.09.2026, nach dem Bau)

Der Planer hat den Stand nachgesehen, drei Dinge nachgezogen und den ganzen Weg
**in einem echten Browser gegen den echten Bestand** gemessen.

### A. Cache-Bump-Prüfungen dynamisch gemacht (Auflösung von offenem Punkt 1)

Die drei JS-Tests, die die `?v=`-Nummer **fest verdrahtet** prüften, sind
umgestellt: sie lesen die Version jetzt aus `index.html` und verlangen nur noch
*Nummer vorhanden, Muster `JJJJMMTT`+Buchstabe, nicht älter als die letzte
bekannte Pflicht-Nummer (`20260925`)*. Geändert:
`frontend/tests/test_selbsttest.js`, `frontend/tests/test_sprachaufnahme.js`,
`frontend/tests/test_tastatur_und_textauswahl.js` (je 2 Prüfungen, Zahl der
Prüfungen unverändert).

Damit ist auch ein **Altbestand** weg: `test_sprachaufnahme.js` und
`test_tastatur_und_textauswahl.js` waren **schon vor dieser Änderung rot** — sie
verlangten `20260927A`, während `index.html` längst `20260927B` lud. Eine
Prüfung, die bei korrektem Verhalten rot wird, prüft nicht das Verhalten.

### B. Deutsche Einzahl in der Trefferliste

`fotoGalerieZeilen` schreibt jetzt `1 Event, 1 Bild` statt `1 Events, 1 Bilder`
(Kopfzeile und Event-Zeilen). Kein neues Verhalten, nur die Schreibweise der
geforderten Zeilen.

### C. Messung im echten Browser (gegen den echten Bestand, nur lesend)

Aufbau: Backend am PC (`uvicorn app.main:app --host 127.0.0.1 --port 8099`,
Interpreter des Projekt-venv, **kein** API-Key gesetzt — der Endpunkt bleibt
ungeschützt wie im Heimnetz), dazu ein **eigener, wegwerfbarer Edge** mit
`--headless=new --remote-debugging-port=9222 --user-data-dir=<Temp>` (nicht das
Browserprofil des Nutzers), Seite `http://127.0.0.1:8099/`.

```json
{"appSrc":["api/konfig","app.js?v=20260928A"],"cssSrc":["manifest.json","style.css?v=20260928A"],
 "hatFrage":"function","hatKacheln":"function","hatGalerie":"function","hatGross":"function",
 "apiKeyLeer":true,"blobsOffen":0}
```

**1. Die Galerie läuft wirklich (echte Vorschaubilder über pCloud):**

```json
{"ok":true,"events":5,"kacheln":23,"bilderGeladen":23,"platzhalter":0,"blaseDa":true,
 "zeilen":["🖼️ Bilder","Treffer: 5 Events, 23 Bilder","· 2026-01-02 … (2026) — 1 Bild"],
 "blobsOffen":23,"storageUsageVorher":0,"cachesVorher":0,"lsLaenge":4,"ssLaenge":0}
```

(Zusatzwert derselben Messung, hier in Worten statt als lange Ziffernfolge: die
vom Browser gemeldete Speicher-Obergrenze lag bei **10 GiB**.)

23 von 23 Kacheln sind als echte Bilder erschienen (0 Platzhalter), die
Trefferliste steht in der Blase. Der echte Event-Name wird hier **nicht**
wiedergegeben.

**2. 100 angesehene Bilder** (dieselbe Funktion, die die Bedienung nutzt —
`oeffneFotoGross` + 100 × `_fotoGrossZeigen` über alle Kacheln):

```json
{"angesehen":100,"bildGeladen":100,"bildFehl":0,"dauerS":35.1,
 "blobsWaehrend":25,"maxBlobsGleichzeitig":25,"geschlossen":true,"blobsNachSchliessen":0,
 "storageUsageNachher":0,"storageUsageVorher":0,
 "cachesNachher":0,"cachesVorher":0,
 "lsNachher":4,"lsVorher":4,"ssNachher":0,"ssVorher":0,
 "kachelBilderNachSchliessen":0,"kachelPlatzhalterNachSchliessen":23}
```

Heißt: **100 Bilder angesehen, 100 geladen, 0 Fehler**; der Speicher des
Browsers ist **vorher wie nachher 0** (`navigator.storage.estimate()`), die
Cache-Speicher-Liste ist **vorher wie nachher leer** (`caches.keys()`), und
`localStorage`/`sessionStorage` haben sich **nicht** verändert. Die Zahl offener
Objekt-URLs läuft **nicht** hoch (25 gleichzeitig statt 125) und ist nach dem
Schließen **0**.

**3. Der Zusatzbeleg, dass nichts zwischengespeichert wird** — dieselbe
Bild-Adresse zweimal hintereinander abgerufen:

```json
{"http1":200,"bytes1":4581,"http2":200,"bytes2":4581,
 "cacheHeader":"no-store","typ":"image/jpeg",
 "zweiAbrufe":[{"transfer":4881,"encoded":4581,"duration":203},
               {"transfer":4881,"encoded":4581,"duration":231}]}
```

Beide Abrufe gingen mit **4881 Byte Übertragung** über die Leitung
(`transferSize > 0` = **kein** Treffer im Browser-Cache); der Kopf
`Cache-Control: no-store` kommt vom Endpunkt.

**4. Der echte Bedienweg** — die Frage wurde durch `sendMessage` geschickt, wie
ein Tippen im Chat:

```json
{"blaseDa":true,"zeilen":["🖼️ Bilder","Keine Bilder gefunden"],
 "kacheln":0,"kachelBilderGeladen":0,"platzhalter":0,"blobsOffen":0,
 "keineZaehlfrage":null,"keinUpload":null,
 "erkannterWunsch":{"jahr":2021,"event":"urlaub"}}
```

Die Blase entsteht, die Zählfrage (`wie viele fotos gibt es?`) und die
Upload-Frage (`lade die Bilder hoch`) lösen die Galerie **nicht** aus. Der
Grund für „Keine Bilder gefunden" ist echt und liegt an den Daten, nicht am
Code: ein Treffer-Suchwort `urlaub` **und** das Jahr 2021 zusammen ergeben
`anzahl: 0`; ohne Jahr findet derselbe Filter 5 Events (2, 3, 6, 25, 8 Dateien
je Event). Steht unter „Offene Punkte".

### D. Prüfbefehle des Planers (frisch, echte Ausgabe)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
1876 passed, 3 warnings in 103.15s (0:01:43)          Exit 0
```

Derselbe Befehl, später am selben Morgen erneut gefahren:

```
1897 passed, 3 warnings in 151.34s (0:02:31)          Exit 0
```

Die Zahl **wächst**, weil ein **zweiter Agent** in diesem Arbeitsbaum parallel
schreibt: `backend/tests/test_whatsapp_zuordnung.py` (samt `tools/whatsapp/` und
`docs/changelog-2026-09-28-whatsapp-zuordnung.md`) ist **neu** und gehört
**nicht** zu N13b. Zwischen den Läufen war einer rot:

```
1 failed, 1896 passed, 3 warnings in 159.44s         (test_chat_endpoint.py::test_conv_code_ohne_bild_delegiert_weiterhin_an_hermes)
```

Dieser eine Test läuft **einzeln sofort grün** (`1 passed in 12.55s`) und lief im
nächsten vollen Lauf mit — er ist **flakig** (bekannt; der Repo-Hook
`.githooks/pre-commit` hängt daran). Für `backend/` wurde in diesem Schritt
**nichts** geändert.

```
cd frontend && for f in tests/*.js; do node "$f" app.js >/dev/null 2>&1 || echo "ROT: $f"; done
rote: 0        (16 von 16 Dateien grün)
node --check app.js  -> syntax ok
node tests/test_foto_galerie.js  -> ERGEBNIS: alle Prüfungen grün, Exit 0
```

## Prüfer-Befund (fremde Modellfamilie: `openai/gpt-5.6-luna`)

* **Runde 1: NICHT BESTANDEN, 4 Punkte — 2 davon echt, 2 „Bestand".** Bestätigt
  hat der Prüfer: `node --check` Exit 0, **145 OK-Zeilen** im neuen Test
  („alle Prüfungen grün", Exit 0), **16 von 16** JS-Dateien grün, im
  Galerie-Abschnitt **je 0 Treffer** für `localStorage`, `sessionStorage`,
  `indexedDB`, `caches.`, `CacheStorage`, `serviceWorker.register`, kein
  `img.src` mit `/api/cloud/thumb`, `URL.revokeObjectURL` vorhanden, `sw.js`
  `git diff --stat` leer und der `/api/`-Zweig kehrt vor dem Cache-Zweig zurück,
  Zeilen **9195 / 1586 / 273 / 328**, beide `?v=20260928A`,
  `docs/plan-nachtlauf-2026-09-26.md` unverändert, Messwerte widerspruchsfrei.
  **Berechtigt:** (1) im Changelog stand der **Vorname des Eigners** (ein Wort,
  hier nicht wiederholt) — ersetzt durch „das Browserprofil des Nutzers";
  (2) die 11-stellige Suche fand neben der erfundenen Beispielkennung die
  **Speicher-Obergrenze des Browsers** (als lange Ziffernfolge im Messblock) —
  die Zahl steht jetzt in Worten („10 GiB"). **Nicht berechtigt (Bestand):** die
  Testzahl (1876 vs. 1897 — der zweite Agent schreibt parallel, oben belegt)
  und die fremden Dateien im Arbeitsbaum (gehören zu `whatsapp`, nicht zu
  N13b).
* **Runde 2 (auf den korrigierten Dateien): „NICHT BESTANDEN" mit genau einer
  Abweichung — und die ist fremd.** Bestätigt: Eigner-Name **0 Treffer**,
  11-stellig nur die erfundene Kennung (3 Treffer), Changelog nennt **1876 und
  1897** samt Grund und dem flakigen Einzelfall, Volltest **1897 passed, Exit
  0**, `node --check` Exit 0, **145** OK-Zeilen, alle JS-Dateien ohne `ROT`,
  `sw.js` gegenüber `HEAD` unverändert, Galerie-Abschnitt ohne Speicher-API.
  Bemängelt wurde allein `CLAUDE.md` („steht nicht in der Whitelist") — dort
  liegt eine **offene Protokollzeile des zweiten Agenten** (WhatsApp). Sie
  gehört **nicht** zu N13b und wurde **bewusst nicht angefasst**
  (Kollisionsschutz). Deshalb als Bestand eingeordnet, nicht als Schritt-Fehler.
* **Runde 3 (Schlussabnahme auf den Commits `3f5bd43` und `7a7dd39`):** alle
  Punkte des Schritts bestätigt — `git show --stat` = genau **9** Dateien bzw.
  **1** Plandatei, **keine** fremde, `0 0`, Prüfbefehl **1922 passed, Exit 0**
  (die Zahl wächst durch fremde Parallelarbeit), 145 OK-Zeilen, 16/16
  JS-Dateien grün, 0 Eigner-Treffer, 11-stellig nur die erfundene Kennung,
  Planzeile/Journal vollständig und ohne falsche Handy-Behauptung, `CLAUDE.md`
  **nicht** in den Commits und weiterhin uncommittet. Rest-Abweisung des
  Prüfers: unsauberer Arbeitsbaum wegen der fremden Änderungen — von ihm selbst
  als „keine Abweichung der beiden N13b-Commits" eingeordnet.

## Offene Punkte und Grenzen

1. ~~**Eine bestehende Testdatei ist durch den geforderten Cache-Bump rot
   geworden.**~~ **Erledigt im Nachtrag des Planers (Abschnitt A):** die drei
   fest verdrahteten `?v=`-Prüfungen lesen die Version jetzt aus `index.html`.
   Die Punkte 2–6 sind unverändert.
2. Der `/api/cloud/thumb`-Endpunkt erlaubt nur `32x32`, `120x120`, `480x480`,
   `800x800`. Verwendet werden ausschließlich `120x120` (Kachel) und `480x480`
   (Großansicht); eine andere Größe wäre ein 422.
3. Die Galerie lädt höchstens `limit=5` Events mit `pro_event=40` Dateien
   (maximal 40 Kacheln). Für mehr Bilder ist ein Nachladen im Raster noch
   **nicht** eingebaut.
4. Die Kennungen der Vorschaubilder stehen als vollständige
   `/api/cloud/thumb?fileid=…`-Angaben in der reinen Funktion — sie werden
   aber **nie** direkt in ein `img.src` geschrieben, sondern immer erst über
   `fotoBildLaden` in eine Objekt-URL gewandelt.
5. Kein Bild und keine Kennung aus dem echten Bestand liegen im Repo; alle
   Beispiele in Test und Doku benutzen `47110000001` bzw. verwandte erfundene
   Werte.
6. `sw.js`, `backend/**`, `tools/**` und fremde uncommittete Dateien wurden
   nicht angefasst. Es wurde **kein** git-Befehl ausgeführt und **keine**
   Datei gelöscht.
7. **Leerer Treffer bei Suchwort *und* Jahr ist echt — und noch nicht
   abgefangen.** Gemessen: `zeig mir die Bilder vom Urlaub 2021` →
   `anzahl: 0` → die Blase sagt ehrlich „Keine Bilder gefunden". Ohne Jahr
   findet derselbe Filter Events (5 gezeigt). Ein Rückfall („kein Treffer für
   »urlaub 2021« — hier stattdessen …") ist **bewusst nicht** gebaut: er stand
   nicht im Auftrag („was nicht im Auftrag steht, wird nicht gebaut") und
   ändert die Bedeutung der Frage. Entscheidung des Nutzers nötig.
8. **Nachladen im Raster fehlt** (siehe Punkt 3): `limit=5`,
   `pro_event=40` — bei einem Event mit mehr Dateien zeigt die Kopfzeile die
   echte Gesamtzahl, das Raster aber nur 40 Kacheln.
9. **Die Kachel-Vorschauen werden beim Schließen der Großansicht mit
   freigegeben** (harte Regel „nach dem Ansehen freigegeben"). Die Kacheln
   sagen das dann ehrlich („Vorschau freigegeben – erneut fragen"). Wer die
   Kacheln länger behalten will, braucht eine andere Freigabe-Regel — bewusst
   **nicht** eigenmächtig geändert.
10. **JS-Tests brauchen den Pfad als Argument.** Zwölf von 16 Testdateien
    lesen `process.argv[2]` ohne Rückfall und brechen ohne Argument mit
    `ERR_INVALID_ARG_TYPE` ab (Altbestand, nicht aus dieser Änderung). Der
    Aufruf lautet `cd frontend && node tests/<datei>.js app.js`. Einzeilige
    Härtung wäre `process.argv[2] || path.join(__dirname, '..', 'app.js')` wie
    in `test_selbsttest.js`.
