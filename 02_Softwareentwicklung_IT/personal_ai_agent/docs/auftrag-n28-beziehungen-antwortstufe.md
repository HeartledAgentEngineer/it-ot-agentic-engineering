# Auftrag N28 — Antwortstufe: der Chat beantwortet „wer war mit wem wo" aus `beziehungen.jsonl`

> **Planer:** Hauptagent (Hermes) · **Ausführer:** ein Subagent · **Prüfer:**
> frischer Kontext, **andere Modellfamilie** als der Ausführer.
> **Stand:** 29.09.2026. Vorgänger: N27e (`beziehungen_ableiten.py`,
> abgenommen) — dieser Schritt baut **nur auf** dessen Ausgabedatei auf und
> ändert daran nichts.

## Warum (1 Absatz)

N27 ist mit allen fünf Teilen fertig: je Anlass existieren belegbare Aussagen
„wer war mit wem wo" mit Datum und Quelle in
`~/foto_sortierung/beziehungen.jsonl` (**15.051** Aussagen, **645** Tage,
2016-05-04 bis 2025-08-16, 12 Personen-Kennungen, **0** bestätigte Namen,
253 benannte Kontakte). Diese Datei liegt aber **nur auf dem PC**, und niemand
liest sie: die Datenbank ist voll, die App kann nichts davon zeigen. Dieser
Schritt macht sie **abfragbar** — als Dienst + Endpunkt (wie
`/api/fotos/uebersicht` in N11) und als **Chat-Werkzeug**, damit die Frage
„was war am 27.12.2019?" in der App eine **belegte** Antwort bekommt.

## Vorbedingung (vom Planer bereits erledigt, nicht nachbauen)

Die kanonische Ausgabedatei ist mit dem vorhandenen Werkzeug geschrieben
(`--schreiben`, Standardpfad, außerhalb des Repos, idempotent):

* `C:/Users/sebas/foto_sortierung/beziehungen.jsonl` — **12.601.994 B**
* `C:/Users/sebas/foto_sortierung/beziehungen.json` — **715 B**
* Lauf-Protokoll: `C:/Users/sebas/foto_sortierung/n28_kanonisch.log`
* Zahlen wie in N27e: **15.051** Aussagen (fotos 23 · gemeinsam_im_chat 14.902 ·
  fotos_und_chat 126), 5 zu lesende Vektorzeilen, 0 defekte Zeilen.

## Datenschema (bindend, nicht ändern)

Zeile (JSONL, je Zeile eine Aussage) — Schlüssel:
`anlass_id`, `art` (immer `"beziehung"`), `beleg`, `datum` (`JJJJ-MM-TT`),
`ereignis_kennung`, `hinweis`, `kategorie`, `personen`, `quellen`, `stand`,
`thema`, `unterart`, `ziel_ordner`.

* `unterart` ∈ `fotos` | `gemeinsam_im_chat` | `fotos_und_chat`
* `personen` = Liste von `{bestaetigt, bilder, gesichter, kennung, name}`;
  `kennung` ist `null` bei Kontakten aus dem Chat, `name` ist `null`, wenn
  keine Bestätigung vorliegt.
* `beleg` ist je Unterart verschieden (z. B. `{chat_art, chat_name,
  nachrichten}` bei `gemeinsam_im_chat`) — **nicht** auswerten, nur mitgeben.
* Übersicht (`beziehungen.json`): `anzahl` (je Unterart), `anzahl_kontakte`,
  `anzahl_namen_bestaetigt`, `anzahl_personen_kennungen`, `art`, `datum_bis`,
  `datum_von`, `hinweis`, `quellen`, `stand`.

## Zu bauen

### 1. Dienst `backend/app/services/beziehungen_service.py` (neu)

Rein **lesend**, kein Netz, keine Bilder, keine Schreibfunktion. Deutsche
Docstrings im Stil von `foto_uebersicht.py`/`foto_bilder.py`.

* `STANDARD_PFAD` = `~/foto_sortierung/beziehungen.jsonl`, `STANDARD_UEBERSICHT`
  = `~/foto_sortierung/beziehungen.json`; beides über `os.path.expanduser`.
* `beziehungen_laden()` → dict mit **immer** denselben Feldern:
  `pfad`, `existiert`, `stand`, `anzahl` (dict je Unterart), `anzahl_gesamt`,
  `datum_von`, `datum_bis`, `anzahl_personen_kennungen`,
  `anzahl_namen_bestaetigt`, `anzahl_kontakte`, `error`.
  Liest die **Übersicht** (`beziehungen.json`) für die Kennzahlen; die
  Aussagen selbst werden **nicht** in dieses dict geladen.
  Fehlt die Datei → `existiert: False` und deutscher `error`-Text (kein Wurf).
  Defekte Zeilen sind eine Zählung, kein Abbruch.
* `aussagen_fuer_datum(datum, limit=50)` → dict:
  `datum` (normalisiert `JJJJ-MM-TT`), `gueltig` (bool), `anzahl` (Gesamtzahl
  des Tages, **vor** dem Limit), `anzahl_je_unterart`, `aussagen` (Liste,
  **höchstens** `limit`, sortiert nach `UNTERART_REIHENFOLGE` wie im Werkzeug:
  fotos → gemeinsam_im_chat → fotos_und_chat, dann nach `anlass_id`),
  `gekuerzt` (bool), `error`.
  Ungültiges Datum → `gueltig: False`, deutscher `error`, **kein Wurf**.
  Ein Tag **ohne** Aussagen ist **kein** Fehler: `gueltig: True`, `anzahl: 0`.
* `datum_erkennen(text)` → `"JJJJ-MM-TT"` oder `None`. Erkennt **nur**
  eindeutige Datumsangaben: `27.12.2019`, `27.12.19`, `2019-12-27`,
  `27. Dezember 2019`, `am 3.1.2022`. Deutsche Monatsnamen (Januar…Dezember)
  ausschreiben, `märz` **und** `maerz` akzeptieren (auch kleingeschrieben).
  Zweistellige Jahre: `20xx`, also `19` → `2019`. Plausibilitätsprüfung über
  `datetime.date` (z. B. `31.02.2020` → `None`).
* `text_antwort(datum)` → deutscher Text (mehrzeilig) für den Chat:
  Kopfzeile mit dem Datum, dann die Zahl der belegbaren Aussagen je Unterart,
  die ersten Aussagen (**höchstens 10**) als Zeilen mit Uhrzeit-freiem Datum,
  Thema/Kategorie, Personen (Kennung `Person_00x`, `name` nur wenn **nicht**
  `null`) und **den `hinweis` der Zeile wörtlich** (einmal, nicht je Zeile
  wiederholt — der Hinweis ist je Unterart gleich). Kein Datum ohne Aussagen:
  ehrlicher Satz, dass an diesem Tag **keine** Andockung vorliegt.
  Am Ende **immer** der Hinweis, dass Chat-Mitgliedschaft keine Anwesenheit
  und Foto-Nähe keine Beziehung belegt. Fehlt die Datei → deutscher Text
  „liegt noch auf dem PC". Länge begrenzen (≤ ~2.000 Zeichen).
* `status_block()` → kleine Zusammenfassung für den Selbsttest:
  `quelle` (Dateiname), `pfad`, `existiert`, `stand`, `aussagen`,
  `personen_kennungen`, `namen_bestaetigt`, `kontakte`, `datum_von`,
  `datum_bis`, `error`. Wirft nie.

### 2. Router `backend/app/router/beziehungen.py` (neu)

`APIRouter(prefix="/api/beziehungen", tags=["beziehungen"])` mit genau zwei
Routen, **immer HTTP 200** und **immer denselben Feldern** (Vorbild
`router/fotos.py`):

* `GET /api/beziehungen/uebersicht` → `beziehungen_laden()` plus `ok` und
  deutscher `error`.
* `GET /api/beziehungen/tag?datum=JJJJ-MM-TT&limit=50` → `ok`, `quelle`,
  `stand`, `datum`, `gueltig`, `anzahl`, `anzahl_je_unterart`, `aussagen`,
  `gekuerzt`, `error`. `limit` geklemmt auf 1…200.

Jede Route in `try/except Exception` → `ok: false`, deutscher `error`-Text,
Log über `logger.error`. Registrierung in `backend/app/main.py` mit
`dependencies=[Depends(auth.require_api_key)]` und einem deutschen
Kommentarblock wie bei `fotos.router`.

### 3. Chat-Werkzeug `_beziehungen_tool(frage)` in `backend/app/router/chat.py`

Vorbild: `_fotos_uebersicht_tool` (Zeile ~1184). **Enge Auslöseregel:**

* Auslösen **nur**, wenn `beziehungen_service.datum_erkennen(frage)` ein Datum
  liefert **und** die Frage einen Zeit-/Beleg-Bezug hat: eines der Wörter
  `was war`, `wer war`, `was passierte`, `was war los`, `damals`, `an dem tag`,
  `an diesem tag`, `ereignis`, `termin`, `foto`, `fotos`, `bild`, `bilder`,
  `chat`, `zusammen`, `mit wem`, `dabei` — **oder** die Frage ist kürzer als
  60 Zeichen und besteht überwiegend aus dem Datum.
* Sonst `""` zurück (der Chat bleibt unverändert; **kein** LLM-Aufruf, kein Netz).
* Der Aufruf wird an **beiden** Stellen eingehängt, an denen
  `_fotos_uebersicht_tool` steht (Zeile ~384 und ~1868), **nach** ihm
  (`if not werkzeug_notiz:`) — die Reihenfolge bleibt sonst unangetastet.
* Ein Fehler im Werkzeug darf den Chat **nie** reißen (`try/except`, leerer
  Rückgabewert, `logger.warning`).

### 4. Selbsttest: Block „beziehungen"

In `backend/app/router/selbsttest.py` einen Block nach dem Muster von
`_fotos_info()` ergänzen (`status_block()` des Dienstes, eigener try/except),
Feld in der Antwortstruktur **und** in der Textausgabe des Frontends nur, wenn
das ohne Frontend-Umbau geht — **kein** Umbau von `app.js`, **kein**
Cache-Bump nötig. Wenn die Frontend-Zeile nicht ohne JS-Änderung geht:
**weglassen** und im Changelog als offen benennen (die Chat-Antwort ist der
Zweck dieses Schritts, der Selbsttest ist Beiwerk).

### 5. Tests `backend/tests/test_beziehungen_service.py` (neu)

**Alles offline**, `tmp_path`, erfundene Beispieldaten — **keine** echten
Namen, keine echten Kennungen, kein Netz, keine echte Datei aus
`~/foto_sortierung`. Deckung mindestens:

* `datum_erkennen`: alle Formate oben, `märz`/`maerz`, zweistelliges Jahr,
  ungültige Tage (`31.02.2020`, `99.99.9999`), Text **ohne** Datum → `None`,
  „2019" allein → `None` (kein Tag erfunden).
* `beziehungen_laden`: fehlende Datei → `existiert: False` + deutscher
  `error`; vorhandene Übersicht → Kennzahlen wie in der Datei; kaputte
  JSON-Zeile zählt als defekt statt zu werfen.
* `aussagen_fuer_datum`: Filter trifft genau einen Tag; `anzahl` ist die
  Gesamtzahl, `aussagen` ist gekürzt und `gekuerzt: True`; Sortierung nach
  Unterart-Reihenfolge; Tag ohne Aussagen → `anzahl: 0`, `gueltig: True`.
* `text_antwort`: enthält das Datum, die Zahlen, den `hinweis` **wörtlich**,
  den Schlusssatz zur Abgrenzung; enthält **keinen** Namen, wenn `name: null`;
  nennt ehrlich „keine Andockung", wenn der Tag leer ist; ≤ 2.000 Zeichen.
* Router (mit `fastapi.testclient.TestClient` wie in den Nachbartestdateien,
  Pfade über `monkeypatch` auf `tmp_path`): beide Routen **HTTP 200**; fehlende
  Datei → `ok: false` + deutscher `error`; ungültiges `datum` → 200 mit
  `gueltig: false`; `limit` geklemmt.
* Werkzeug `_beziehungen_tool`: löst bei „was war am 27.12.2019?" aus, bei
  „wie geht's dir?" **nicht**, bei einem Datum ohne Zeitbezug wie
  „27.12.2019" nur in der kurzen Form; Ausgabe leer, wenn die Datei fehlt.

## Beweisregeln (bindend)

* **Prüfbefehl aus dem Projektverzeichnis:**
  `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → muss **Exit 0** liefern; die Zahl vorher (**2.789 passed**) und nachher im
  Changelog nennen.
* **Live-Beleg am echten Bestand** (nur lesend, echte Datei) mit den Zahlen
  aus diesem Auftrag: `15.051` Aussagen, `645` Tage, 2016-05-04 bis
  2025-08-16, 12 Kennungen, 0 Namen, 253 Kontakte;
  `GET /api/beziehungen/tag?datum=2022-08-21` → **61** (fotos 10 · chat 6 ·
  kreuz 45); `datum=2019-12-27` → **0** (ehrlich, kein Fehler);
  `datum=2025-06-06` → **685**; `datum=31.02.2020` → `gueltig: false`.
  Die Belegausgabe als Datei außerhalb des Repos ablegen, z. B.
  `C:/Users/sebas/foto_sortierung/n28_belege.txt`, und die Zahlen im
  Changelog nennen.
* **Zahlen selbst zählen, nicht schätzen** (Zeilen der neuen Dateien,
  Testfunktionen, Prüfbefehlszahlen).
* **Kein Schreiben** nach `~/foto_sortierung/beziehungen.jsonl` und
  `beziehungen.json` — diese Dateien werden **nur gelesen**; ein Test prüft
  das (mtime/sha256 vor und nach dem Lauf).
* **Keine pCloud-Aufrufe, kein Netz, keine Bilder, keine Löschfunktion.**
  Das Werkzeug darf **kein** `deletefile`/`deletefolder`/`rmtree` enthalten.

## Datenschutz (hart)

* In **Code, Tests, Auftrag und Doku** stehen **keine** echten Personen-,
  Chat- oder Ortsnamen und keine echten Datei-/Kontaktkennungen — nur
  erfundene Beispiele (`Person_001`, „Musterchat") und **Zahlen**.
  Kalenderjahre (`2019`) sind erlaubt.
* Der Dienst gibt nur aus, was in der Datei steht (Kennung + `name`, wobei
  `name` in der kanonischen Datei durchweg `null` ist) — er **erfindet nie**
  einen Namen und liest **keine** Kandidatenlisten.
* Keine Schlüssel/Token in Ausgaben oder Dateien.

## Abgabe

* `backend/app/services/beziehungen_service.py`
* `backend/app/router/beziehungen.py`
* `backend/tests/test_beziehungen_service.py`
* Änderungen in `backend/app/router/chat.py`, `backend/app/router/selbsttest.py`,
  `backend/app/main.py`
* `docs/changelog-2026-09-29-n28-beziehungen-antwortstufe.md` (mit allen
  Zahlen, dem Prüfbefehl-Ergebnis und den ehrlichen Grenzen)
* **keine** git-Befehle (Commits macht der Planer), **keine** Änderung an
  `docs/plan-nachtlauf-2026-09-26.md` und **keine** an `CLAUDE.md`

## Ehrliche Grenzen, die im Changelog stehen müssen

1. Die kanonische Datei liegt **auf dem PC**; am Handy fehlt sie (Übergabe ist
   ein eigener Schritt wie N13c).
2. `name` ist in der echten Datei durchweg `null` (0 bestätigte Namen) — die
  Antwort nennt deshalb `Person_00x`-Kennungen; die **Namen** warten weiter auf
  den Eintrag des Nutzers in `personen_bestaetigt.json`.
3. Der plan-interne Testtag `2019-12-27` trägt **keine** Andockung → 0
  Aussagen; das ist kein Fehler, sondern der Befund aus N27e.
4. Der Massenlauf der Gesichter über alle 9.430 Fotos (~15 h) ist **nicht**
   Teil dieses Schritts.
