# N11 Teil B — Fotos-Übersicht am Handy (Endpunkt, Chat-Anschluss, Selbsttest)

> **Stand:** 27.09.2026 · **Nachtlauf-Schritt N11, Teil B** (Planer: Hauptagent,
> Ausführer: Hermes-Subagent, Prüfer: andere Modellfamilie)
> **Anlass:** Der Nutzer möchte am Handy fragen können: „wie viele Events gab's?"
> und „zeig mir die Urlaube 2021". Die Sortierdaten
> (`sortierschluessel*.csv`, `themen.jsonl`, `kategorien.json`) liegen aber nur
> auf dem PC.
> **Schnittstelle (eingefroren):** Teil A erzeugt
> `~/foto_sortierung/fotos_uebersicht.json` (nur Zahlen und Event-Namen, keine
> Bilder), Teil B liest sie. Das Schema steht wortgleich im Feinauftrag
> `docs/auftrag-n11-foto-uebersicht.md`.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `backend/app/services/foto_uebersicht.py` (389 Zeilen, neu) | Dienst: Pfad (`FOTO_UEBERSICHT_PFAD` übersteuert `~/foto_sortierung/fotos_uebersicht.json`), `uebersicht_laden` (**wirft nie**), `status_block` (immer derselbe Schlüsselsatz), `events_finden` (Jahr/Kategorie/Suche), `text_antwort` (Chat-Anhängung, leer ohne Datei) |
| `backend/app/router/fotos.py` (103 Zeilen, neu) | `GET /api/fotos/uebersicht` mit `jahr`, `kategorie`, `suche`, `limit`; immer HTTP 200, immer alle Felder |
| `backend/app/main.py` (+7 Zeilen) | Registrierung `app.include_router(fotos.router, dependencies=[Depends(auth.require_api_key)])` mit Kommentarzeile im Stil der Nachbarn |
| `backend/app/router/chat.py` (+55 Zeilen) | `_fotos_uebersicht_tool(frage)` nach dem Gesichts-Werkzeug; in **beiden** Ketten eingehängt (`/api/chat` und `/api/chat/stream` — das Frontend nutzt `/stream`) |
| `backend/app/router/selbsttest.py` (+30 Zeilen) | Block `_fotos_info()` unter `"fotos"` und in der Bauer-Schleife; Modulkopf ergänzt |
| `frontend/app.js` (+22 Zeilen) | Zeile im Selbsttest-Blatt: `✓/⚠/✗ Fotos: …` |
| `frontend/tests/test_selbsttest.js` (238 Zeilen) | 12 neue Prüfungen (vorhanden/fehlend/Teilangaben/Fehler/Quelle); Standardpfad wird jetzt relativ zur Testdatei aufgelöst, damit `node frontend/tests/test_selbsttest.js` aus der Repo-Wurzel läuft |
| `frontend/index.html` | **Cache-Bump `app.js?v=20260927A` → `?v=20260927B` (Planer, nach dem Bau).** Der Ausführer hatte den Wert für „bereits vorhanden“ gehalten — er stammt aber aus Commit `6b08e67` und war damit **älter als die Änderung**; ohne Bump hätte der Browser die alte `app.js` behalten (Regel §5). Die Token-Prüfung in `frontend/tests/test_selbsttest.js` wurde mitgezogen (sie war auf `20260927A` festgenagelt und wurde durch den Bump rot) |
| `backend/tests/test_foto_uebersicht_endpunkt.py` (791 Zeilen, neu) | **83 Testfunktionen**, alles offline (`tmp_path`, erfundene Namen) |
| `backend/tests/test_selbsttest.py` (1 Zeile) | `PFLICHT_FELDER` um `"fotos"` ergänzt (der Test vergleicht die SchlüsselMENGE exakt) |

## Verhalten in einem Satz

* **Datei da:** Endpunkt `ok: true` mit Zahlen und Listen; Chat hängt eine
  deutsche Notiz mit Gesamtzahl und Treffern an; Selbsttest zeigt
  `✓ Fotos: 2127 Anlässe · 2098 Events · 9430 Dateien · 11 Jahre
  (Stand …, Quelle fotos_uebersicht.json)`.
* **Datei fehlt** (Normalfall auf einem frisch eingerichteten Handy): Endpunkt
  `ok: false` + deutscher `error`, Listen leer, **HTTP 200**; Chat bleibt still
  (leerer String) statt zu raten; Selbsttest zeigt `✗ Fotos: <error>`.
* **Datei kaputt / fremde Schema-Version:** derselbe Weg — Fehlertext statt
  Absturz, **nie 500**.

## Prüfbefehle (frisch gefahren, 27.09.2026)

| Befehl | Ergebnis |
|---|---|
| `cd backend && .venv/Scripts/python -m pytest tests/ -q` | **1687 passed**, Exit **0** (Baseline 1503; +83 aus dieser Datei, der Rest aus parallel entstandenen Dateien) |
| `node --check frontend/app.js` | Exit **0**, keine Ausgabe |
| `node frontend/tests/test_selbsttest.js` | „alle Prüfungen grün", Exit **0**, 73 Zeilen Ausgabe |

## Beispielaufrufe (erfundene Testdaten, kein echter Bestand)

Testdatei in `tmp_path`, `FOTO_UEBERSICHT_PFAD` darauf gesetzt.

1. `GET /api/fotos/uebersicht?limit=2` → **200**
   `{"ok": true, "quelle": "fotos_uebersicht.json",
   "stand": "2026-09-27T22:30:00+02:00", "zahlen": {…}, "jahre": […],
   "themen": […], "kategorien": […], "events": [ … 2 … ], "error": null}`
2. `GET /api/fotos/uebersicht?jahr=2021&suche=urlaub` → **200**, genau ein
   Treffer: `{"jahr": 2021, "kategorie": "Reisen",
   "name": "2021-07-01 Urlaub Beispiel", "dateien": 12, "quelle": "neu"}`
   (Suchwort klein geschrieben, Event-Name groß — die Suche ist
   groß/klein-unabhängig; „pruefung" findet „Prüfung".)
3. Ohne Datei → **200**:
   `{"ok": false, "quelle": "gibtsnicht.json", "stand": null, "zahlen": {},
   "jahre": [], "themen": [], "kategorien": [], "events": [],
   "error": "Fotos-Übersicht nicht gefunden (die Zahlen entstehen auf dem PC,
   Werkzeug foto_uebersicht.py)"}`
4. Chat-Werkzeug `frage="wie viele Events gab's?"` →
   `[Fotos-Übersicht (Quelle: fotos_uebersicht.json, Stand …): 2127 Anlässe,
   2088 Events, 9430 Dateien, 2 Jahre. Zeige 4 von 2088 Events: … ]`
5. Chat-Werkzeug `frage="zeig mir die Urlaube 2021"` → Gegenprobe mit der echten
   Übersichtsdatei: `… Gefiltert (Jahr 2021, Suche „urlaub"): 1 von 2098 Events: …`
   (im Test mit der erfundenen kleinen Datei entsprechend „1 von 4").

**Zahlen in erfundenen Beispielen:** Die Beispiele 1–3 und 5 nutzen eine
Testdatei mit eigenen Zahlen (2.127 Anlässe, 2.088 Events, 9.430 Dateien,
2 Jahre). Die **echte** Datei liefert 2.127 Anlässe, **2.098** Events, 9.430
Zeilen und **11** Jahre — maßgeblich sind die Zahlen im Rauchtest-Abschnitt
unten, nicht die erfundenen Beispiele.

## Auslöseregel des Chat-Werkzeugs (bewusst eng)

Es muss ein **Foto-Wort** (`foto(s)`, `bild(er)`, `event(s)`, `anlass`,
`anlaesse`, `anlässe`, `urlaub`, `konzert`) **und** ein **Frage-/Listen-Wort**
(`wie viele`, `wieviele`, `wie oft`, `anzahl`, `wieviel`, `zeig(e)`, `welche`,
`liste`, `übersicht`/`uebersicht`, `gibts`, `gibt es`, `gab`) vorkommen.
`gab` zählt nur als **eigenes Wort** — „Aufgabe"/„Ausgabe" öffnet das Tor
nicht. Jahreszahl `20\d\d` wird als `jahr`, `urlaub`/`konzert` als `suche`
übergeben. Kein zusätzlicher LLM-Aufruf, kein Netz: Die Notiz ist ein reiner
Datei-Text, der an die Nutzerfrage gehängt wird.

## Sicherheit und Grenzen

* **Kein Netz**: Der Dienst liest ausschließlich die lokale Datei; Tests sperren
  Namensauflösung und Verbindungsaufbau (`socket.getaddrinfo`,
  `socket.socket.connect`) und prüfen den Quelltext per AST auf verbotene Namen
  (`httpx`, `requests`, `urllib`, `socket`, `pcloud_service`, `subprocess`,
  Lösch-Aufrufe). Ein defekter Dienst wird im Chat und im Selbsttest zu einem
  leeren String bzw. Fehlertext, nie zu einem Absturz.
* **Keine Bilder**: Die Übersicht trägt nur Zahlen und Namen; im Dienst kommen
  keine Bild-Endungen vor (Test).
* **Keine Geheimnisse**: Ausgegeben werden Zahlen, Stand, Event-Namen und der
  Dateiname der Quelle (`basename`) — der volle Pfad steht nur im
  Selbsttest-Block, nie ein Schlüssel oder Token.
* **Testdaten erfunden**: `Beispiel-Ordner`-Namen, `Konzert Beispiel`,
  `Urlaub Beispiel`, keine echten Ordnernamen und keine Namen Dritter.

## Bewusst offen gelassen

* **Übertragung der Datei aufs Handy.** Teil B liest nur; wie
  `fotos_uebersicht.json` vom PC auf das Gerät kommt (pCloud/Sync), ist nicht
  Teil dieses Schritts. Fehlt sie, sagen Endpunkt, Chat und Selbsttest das klar.
* **`limit`-Obergrenze 200** ist eine Schutzgrenze der Schnittstelle; mehr als
  200 Events in einem Chat-Anhang wären unlesbar.
* **`jahr` als Query-Parameter ist `int`** (eingefrorene Schnittstelle): Ein
  nicht-numerischer Wert wird von FastAPI mit HTTP 422 abgewiesen, statt in der
  Route selbst behandelt zu werden. Der Fehlerfall „Datei fehlt/kaputt" ist
  davon unberührt und bleibt bei HTTP 200.
* **Die Suchtreffer listen den Event-Namen**, nicht den Ordnerinhalt: Die
  Übersicht führt bewusst keine Dateinamen (Datenschutz, Dateigröße).

## Rauchtest gegen die ECHTE Übersichtsdatei (Planer, 27.09.2026 ~22:43)

Kein Testlauf mit erfundenen Daten, sondern die Datei aus dem Bestand
(`~/foto_sortierung/fotos_uebersicht.json`, 344.615 Bytes, aus dem echten
`sortierplan.json` geschrieben), über `fastapi.testclient` — **ohne Netz**, der
Selbsttest-Endpunkt wurde bewusst **nicht** aufgerufen (er würde den echten
pCloud-Prüfpfad auslösen):

| Aufruf | Ergebnis |
|---|---|
| `GET /api/fotos/uebersicht?limit=3` | **200**, `ok: true`, `quelle: fotos_uebersicht.json`, Stand `2026-09-27T22:40:09+02:00`; Zahlen 2.127 / 2.098 / 9.430 / 7.616 / 1.146; 11 Jahre, 48 Themen, 11 Kategorien; 3 Events geliefert |
| `?jahr=2021&suche=usedom` | **200**, **1** Treffer |
| `?kategorie=urlaub` | **200**, **25** von 2.098 Events |
| `?limit=999` | **200**, auf **200** geklemmt (Schutzgrenze greift) |

Damit ist das Prüfkriterium „Endpunkt antwortet ohne Netz“ am echten Bestand
belegt und nicht nur im Test mit Attrappen.

## Begriffe: zwei verschiedene „Dateien“-Zahlen (bewusst so)

* **Selbsttest-Zeile** (`status_block`, `zahlen.dateien`) = **9.430** — das ist
  `zahlen.zeilen`, also die **Zeilen des Sortierschlüssels** (jede Zeile ist eine
  Datei im Bestand, einschließlich der 1.146 ohne Datum und der 668
  übersprungenen Doppelungen).
* **Werkzeug-Konsole** (`foto_uebersicht.py`) nennt „Dateien: 7.616“ = `zahlen.zuege`,
  also die Dateien, die im **Plan tatsächlich gezogen** werden.

Beide Zahlen sind korrekt und messen Verschiedenes; die JSON-Datei trennt sie
sauber als `zeilen` und `zuege`. Wer die Anzeige später vereinheitlicht, muss
sich für eine der beiden Bedeutungen entscheiden — offen notiert.
