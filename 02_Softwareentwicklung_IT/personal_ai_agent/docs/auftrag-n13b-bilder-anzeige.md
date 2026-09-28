# Feinauftrag N13b — Bilder im Chat, Anzeige (Galerie + Diashow)

> **Übergeordneter Plan:** `docs/plan-nachtlauf-2026-09-26.md`, Schritt **N13b**
> **Vorgänger:** N13a (`docs/changelog-2026-09-28-n13a-bilderdaten.md`) — liefert
> `GET /api/fotos/bilder` mit den Datei-Kennungen je Event.
> **Ausführer:** Hermes-Subagent (Codex-Kontingent ist erschöpft).
> **Prüfer:** `openai/gpt-5.6-luna` (fremde Modellfamilie), führt den Prüfbefehl selbst aus.
> **Kein git-Befehl. Kein pCloud-Schreibzugriff. Keine `.env`. Keine Bilder im Repo.**

## Warum dieser Schritt

Am Handy soll man Bilder **im Chat** sehen: Frage → Trefferliste → Kacheln →
Antippen = groß → Diashow. Die Daten liegen seit N13a bereit; die Anzeige fehlt.
Die Bilder werden **gestreamt**: über `GET /api/cloud/thumb` als Blob in den
Arbeitsspeicher, als Objekt-URL angezeigt und **nach dem Ansehen freigegeben** —
es wird **kein** Bild auf Platte, in `localStorage`, in `IndexedDB` oder im
Service-Worker-Cache abgelegt.

## Vorhandene Bausteine (nur benutzen, nichts davon ändern)

| Baustein | Wo | Was |
| --- | --- | --- |
| `GET /api/fotos/bilder` | `backend/app/router/fotos.py` | Parameter `jahr`, `kategorie`, `event`, `limit` (Standard 5, 1…50), `pro_event` (Standard 40, 1…200). Antwort **immer** 200 mit `ok`, `quelle`, `stand`, `zahlen`, `events`, `anzahl`, `error`; je Event `{jahr, kategorie, event, anzahl, dateien:[{datei_id, name}]}` |
| `GET /api/cloud/thumb` | `backend/app/router/cloud.py` | `?fileid=<int>&groesse=120x120\|480x480` → JPEG, Header `Cache-Control: no-store`. **Unbekannte Größen sind 422** — nur `32x32`, `120x120`, `480x480`, `800x800` sind erlaubt |
| Muster „reine Funktion aus `app.js` schneiden" | `frontend/tests/test_selbsttest.js` | `extractFn(name)` + `eval` + `pruefe(...)`; Aufruf aus dem Ordner `frontend`: `node tests/test_x.js app.js` |
| Muster „Befehl oben in `sendMessage`" | `frontend/app.js`, Zweig `zeigeReferenzen()` (~Zeile 5860) | Befehl wird **vor** dem Abbruch-Guard erkannt, eigene Anzeige, `return` |

## Teil A — Reine Funktionen in `frontend/app.js` (in Node prüfbar)

Alle vier Funktionen sind **ohne DOM, ohne Netz, ohne `API_BASE`** und werden vom
JS-Test wörtlich aus dem echten `app.js` geschnitten und ausgeführt.

1. **`fotoFrageErkennen(text)`** → `null` oder `{ jahr: <int\|null>, event: <string\|null> }`
   * Trifft nur, wenn **beides** vorkommt: ein **Bild-Wort** (`foto`, `fotos`,
     `bild`, `bilder`) **und** ein **Zeige-Wort** (`zeig`, `zeige`, `zeig mir`,
     `anschauen`, `galerie`, `welche`).
   * Trifft **nicht** bei reinen Zählfragen (`wie viele`, `wieviel`, `anzahl`) —
     die bleiben beim Text-Werkzeug aus N11.
   * Trifft **nicht** bei `upload`, `hochladen`, `löschen`.
   * `jahr`: erste vierstellige `20\d{2}`-Zahl, sonst `null`.
   * `event`: erstes zutreffendes Suchwort aus der festen Liste
     `["urlaub", "konzert", "geburtstag", "hochzeit", "festival", "party"]`
     (klein geschrieben, sonst `null`).
   * Leere Eingabe, `null`, Zahl → `null` (kein Wurf).
2. **`fotoKacheln(daten, maxKacheln)`** → Liste `{ datei_id, name, thumb_klein, thumb_gross }`
   * `daten` ist die Endpunkt-Antwort. Nicht-Objekt, `ok !== true`, fehlende
     `events` → leere Liste (kein Wurf).
   * Nur Einträge mit ganzzahliger `datei_id > 0` (bool ist **keine** Kennung)
     werden übernommen; `name` fehlt → `""`.
   * `thumb_klein = "/api/cloud/thumb?fileid=<id>&groesse=120x120"`,
     `thumb_gross = "/api/cloud/thumb?fileid=<id>&groesse=480x480"`.
   * Reihung: Events in der Reihenfolge der Antwort, Dateien in deren
     Reihenfolge; Gesamtlänge höchstens `maxKacheln` (fehlend/0/negativ → `40`).
3. **`fotoGalerieZeilen(daten)`** → Liste deutscher Zeilen (höchstens 5)
   * Kopfzeile `Treffer: <anzahl> Events, <n> Bilder` (n = Zahl aller
     `datei_id`s aus `daten.events`), je Event eine Zeile
     `· <event> (<jahr>) — <anzahl> Bilder` (höchstens 4 Event-Zeilen).
   * Leere Antwort → genau **eine** Zeile `Keine Bilder gefunden`.
4. **`fotoDiashowNaechster(index, anzahl, richtung)`** → nächster Index
   * `richtung` `1` = vor, `-1` = zurück, alles andere = `1`; über die Enden
     wird **umlaufend** weitergeschaltet.
   * `anzahl <= 0` → `0`.

## Teil B — Anzeige (Verdrahtung in `app.js` + `style.css`)

5. **Zweig in `sendMessage`** (nach den vorhandenen Befehlszweigen, **vor** dem
   Abbruch-Guard): `const fotowunsch = fotoFrageErkennen(text);` → wenn nicht
   `null`: `zeigeFotoGalerie(fotowunsch); return;`
6. **`zeigeFotoGalerie(wunsch)`** (asynchron):
   * Legt **eine** Assistenten-Blase an (`addMessage('', 'assistant')` +
     `zeigeBlaseMitText(...)` wie im vorhandenen Muster) mit
     `data-foto-galerie="1"`.
   * Überschrift `🖼️ Bilder` + die Zeilen aus `fotoGalerieZeilen(daten)`, dann
     ein Raster (`<div data-foto-kacheln="1">`) aus den Kacheln von
     `fotoKacheln(daten)`.
   * Lädt `GET /api/fotos/bilder` mit den Parametern aus `wunsch`
     (`jahr`, `event` als `event`, `limit=5`, `pro_event=40`); fehlende Werte
     werden **nicht** mitgeschickt.
   * Fehlerfall (`ok !== true`, Netzfehler, HTTP ungleich 200): **eine** ehrliche
     Zeile mit dem `error`-Text des Endpunkts bzw.
     `Bilder nicht abrufbar (<Ursache>)` — kein Absturz, keine leere Blase.
   * Ladefehler eines **einzelnen** Bildes: diese Kachel zeigt
     `Vorschau nicht verfügbar` — die übrigen bleiben.
7. **`fotoBildLaden(url)`** — holt das Bild per `fetch`, gibt eine
   **Objekt-URL** aus dem Blob zurück; schlägt es fehl → `null`.
   * **Jede** erzeugte Objekt-URL wird in einer Buchführung vermerkt
     (`_fotoObjekte`, `Set`), damit sie später freigegeben wird.
   * **`fotoObjekteFreigeben()`** ruft `URL.revokeObjectURL` für alle
     vermerkten URLs, leert die Buchführung und liefert die Anzahl der
     freigegebenen URLs zurück.
8. **Großansicht + Diashow**:
   * Antippen einer Kachel öffnet die Großansicht (`<div data-foto-gross="1">`)
     mit dem Bild in `480x480`, Beschriftung (`name`) und den Knöpfen
     `‹ Zurück`, `Weiter ›`, `▶ Diashow` / `⏸ Stopp`, `✕`.
   * `fotoDiashowNaechster` bestimmt den nächsten Index (umlaufend).
   * Diashow = selbsttätiges Weiterschalten alle 3 Sekunden; jeder Wechsel
     **gibt das vorherige Bild frei** (Freigabe der Objekt-URL).
   * Schließen (× / Hintergrund / `Escape`) ruft **immer**
     `fotoObjekteFreigeben()`; danach ist die Buchführung leer.
9. **Nichts wird gespeichert (harte Regel, im Test belegt):**
   * kein `localStorage`, `sessionStorage`, `indexedDB`, `caches.`,
     `CacheStorage`, `serviceWorker.register` im Galerie-Code,
   * Bilder **nur** über `fotoBildLaden` (Blob + Objekt-URL), **nicht** als
     `img.src = "/api/cloud/thumb…"` direkt,
   * `sw.js` bleibt unverändert: der `/api/`-Zweig ist netzwerk-zuerst und legt
     **nichts** in den Cache (im Test aus dem Quelltext belegt).

## Teil C — Tests und Doku

10. **`frontend/tests/test_foto_galerie.js`**, Bauart wie
    `frontend/tests/test_selbsttest.js` (Funktionen aus dem echten `app.js`
    schneiden und ausführen, `pruefe(...)`, Exit-Code 1 bei Fehlern):
    * **mindestens 40 Prüfungen**,
    * alle Regeln aus Teil A (Grenzfälle: leere Eingabe, `null`, `true` als
      Kennung, `ok:false`, fehlende Felder, Klemmung von `maxKacheln`,
      Umlauf der Diashow, Richtung `0`/`"x"`),
    * Quelltext-Prüfungen aus Teil B: Zweig in `sendMessage` vorhanden,
      `data-foto-galerie`, `data-foto-kacheln`, `data-foto-gross`,
      `revokeObjectURL` kommt vor, **keine** Speicher-APIs im Galerie-Bereich,
      `sw.js` unverändert (der `/api/`-Zweig cached nicht),
    * `?v=` in `index.html` höher als vorher.
11. **Cache-Bump:** in `frontend/index.html` für **jede** geänderte Datei die
    `?v=`-Nummer auf `20260928A` setzen (`app.js`, `style.css`).
12. **`docs/changelog-2026-09-28-n13b-bilder-anzeige.md`** mit: Warum, was
    gebaut wurde (Dateien mit Zeilenzahlen), gefahrene Befehle **mit echter
    Ausgabe**, offene Punkte, Grenzen. Sprache Deutsch, **kein** Eigner-Name
    („der Nutzer"), **keine** echten Event-/Ortsnamen, **keine** 11-stellige
    echte Kennung (erfundene Beispiele benutzen `47110000001`).

## Prüfbefehl (selbst ausführen, Ausgabe in den Changelog)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q      # muss 1876 passed, Exit 0 bleiben
node --check frontend/app.js
cd frontend && node tests/test_foto_galerie.js app.js
cd frontend && for f in tests/*.js; do node "$f"; done      # alle JS-Tests, Exit 0
```

## Grenzen

* Kein git-Befehl, kein pCloud-Schreibzugriff, kein Löschen.
* Keine Bilddatei im Repo; keine Kennung aus dem echten Bestand in Doku/Test.
* Nur die genannten Dateien ändern (`frontend/app.js`, `frontend/style.css`,
  `frontend/index.html`, `frontend/tests/test_foto_galerie.js`,
  `docs/changelog-2026-09-28-n13b-bilder-anzeige.md`). **Nicht** anfassen:
  `sw.js`, `backend/**`, `tools/**`, `docs/plan-nachtlauf-2026-09-26.md`,
  fremde uncommittete Dateien im Arbeitsbaum.

## Nachtrag des Planers (nach dem Bau, 28.09.2026)

Der Planer hat den Stand nachgesehen und drei Dinge **selbst** nachgezogen
(Whitelist damit ausdrücklich erweitert): die drei JS-Tests
`frontend/tests/test_selbsttest.js`, `frontend/tests/test_sprachaufnahme.js`
und `frontend/tests/test_tastatur_und_textauswahl.js` prüfen die
`?v=`-Nummer nicht mehr **fest verdrahtet**, sondern lesen sie aus
`index.html` (Muster `JJJJMMTT`+Buchstabe, nicht älter als `20260925`) — sonst
wird jede Cache-Bump-Prüfung nach jedem legitimen Bump rot. Außerdem steht
`fotoGalerieZeilen` in deutscher Einzahl (`1 Event, 1 Bild`). Der echte
Browser-Beleg (23 von 23 Kacheln geladen, 100 angesehene Bilder ohne
Speicher-Änderung, `no-store` doppelt belegt) steht im Changelog-Abschnitt
„Nachtrag des Planers".
