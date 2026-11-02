# Changelog 02.11.2026 — Bildbeschreibung: finden, zuerst lesen, bearbeiten, neu beschreiben (Plan G2)

Plan: `.hermes/plans/2026-11-02_geschichte-sprachmodell.md`, Schritt G2 (Fassung 6).

## Anlass
Der Knopf „📝 Beschreibung“ im Vollbild-Editor öffnete sofort eine fokussierte Textarea. War zu dem Bild
nichts geladen, stand dort ein leeres Feld ohne Erklärung. Außerdem galt eine von Hand gespeicherte
Beschreibung nicht, sobald es für das Bild einen Text in einer `*_reich`-Datei gab: Der Leser wendete die
`*_reich`-Dateien nach `bild_beschreibungen.jsonl` an und überschrieb damit die Handänderung.

## Änderung

### Backend
- `backend/app/services/erzaehl_service.py`
  - Zeilen, die die App schreibt, tragen `quelle`: `hand` (`beschreibung_speichern`) oder `einzel_ki`
    (neu `beschreibung_uebernehmen_ki`, ein leerer Text wird nicht gespeichert). Beide Funktionen teilen
    sich `_beschreibung_schreiben` (JSONL-Zeile plus SQLite wie bisher).
  - Vorrang: neu `_beschreibungen_mit_herkunft() -> {fileid: (text, herkunft)}`. Reihenfolge: SQLite, dann
    alle JSONL-Dateien, ZULETZT die App-Zeilen. Die neueste App-Zeile gewinnt gegen SQLite und alle
    `*_reich`-Dateien. Eine spätere Werkzeugzeile derselben Datei überschreibt eine App-Zeile nicht.
    `herkunft` ist `ki` (SQLite, `*_reich`, Zeilen ohne `quelle`), `hand` oder `einzel_ki`
    (= die der zuletzt angewendeten Zeile). Ein leerer Hand-Text löscht nichts, er wird beim Lesen
    übersprungen (wie bisher).
  - `_beschreibungen_lesen` liefert jetzt `(text, herkunft)` je fileid; `_beschreibungen_gesamt_lesen()` bleibt
    als dünne Hülle `{fileid: text}` für die bisherigen Aufrufer (`beschreibung_holen`, `bilder_info`,
    Anlass-Geschichte).
  - Neu `beschreibung_mit_herkunft_holen(fileid)`.
  - `ki_geschichte_generieren` meldet `daten.beschreibung_gefunden: bool` (übergebene oder gefundene
    Beschreibung vorhanden).
- `backend/app/router/erzaehlen.py`
  - `GET /api/erzaehlen/bild-beschreibung` liefert zusätzlich `gefunden: bool` und
    `quelle: "ki"|"hand"|"einzel_ki"|null`; `beschreibung` bleibt ein String (die alte Form gilt weiter).
  - Neu `POST /api/erzaehlen/bild-beschreibung/vorschlag {fileid}` und
    `POST /api/erzaehlen/bild-beschreibung/uebernehmen {fileid, beschreibung}` (speichert genau eine Zeile
    `einzel_ki`).
- Neu `backend/app/services/bild_beschreibung_vorschlag.py` (eigenes kleines Modul):
  - Vorschaubild über den vorhandenen pCloud-Dienst (`pcloud_service.thumb`, Größe `480x480`).
  - EIN Vision-Aufruf an `modell_router.MODELL_VISION` über den vorhandenen `OpenRouterZDRClient`
    (ZDR erzwungen). `data_collection: deny` steht zusätzlich im Aufruf selbst. Zeitgrenze 30 s,
    `max_tokens` 400, Prompt „Beschreibe sachlich auf Deutsch in 2–4 Sätzen, was auf dem Bild zu sehen ist;
    erfinde keine Namen.“
  - Antwort `{ok, vorschlag, modell, kosten_usd}`. `kosten_usd` kommt aus `usage.cost` der Antwort, sonst aus
    den Token mal den Preisen in `PREISE_USD_PRO_MIO`, sonst `null`. Es wird NICHTS gespeichert.
  - Fehler als `{ok: false, grund}` (HTTP 200), ehrlich und ohne Schlüssel, URL oder den Text der Ausnahme
    (Zeitgrenze, HTTP-Status, Verbindung, leere Antwort, kein Bild, kein Schlüssel).
  - Log (eigene Zeilen): nur Modell, Dauer, Zeichenzahl, Kosten bzw. Fehlerart — nie der Text, nie die fileid.
    (Die Bibliothek `httpx` protokolliert ihre Anfrage-URL selbst; sie enthält weder Schlüssel noch Inhalt.)
  - Client und Bildabruf sind einspielbar (`client=`, `bild_holer=`).

### Zählwerkzeug
- Neu `tools/foto_sortierung/beschreibung_abdeckung.py` (nur lesend, nur Zahlen): Zeilen je Quelle, Bilder mit
  Beschreibung gesamt (nach Herkunft), fileids im Fotobuch und in `ereignisse.jsonl` und wie viele davon eine
  Beschreibung haben. Die Pfade kommen aus `erzaehl_service` (`fotobuch_pfad()`, `ereignisse_pfad()`,
  `beschreibungen_alle_pfade()`; `ERZAEHL_*_PFAD` werden respektiert). Die Ausgabe enthält keine fileid und keinen
  Beschreibungstext. Ausführen auf den echten Daten lässt Hermes in der G2-Ergebnisprüfung (`--sensibel`).

### Frontend
- Neu `frontend/bild_beschreibung.js` (eigene Datei, schlank und modular; klassisches Skript, in `index.html` VOR
  `app.js` geladen): `baueBeschreibungKasten` (testbar mit Schein-Oberfläche), `beschreibungKostenText`,
  `bildBeschreibungVorlesen` (der Vorlese-Weg der oberen Beschreibungsbox ist dieselbe Funktion) und die Konstanten
  `BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD` und `BESCHREIBUNG_HERKUNFT_TEXT`.
- `frontend/app.js`: nutzt sie nur noch. In `zeigeBildVollbild` ersetzt der Kasten die alte, sofort fokussierte
  Textarea.
  - „📝 Beschreibung“ öffnet zuerst die LESE-Ansicht: Text, Herkunft („KI-Beschreibung“ / „von dir
    bearbeitet“ / „KI, von dir übernommen“), „🔊 Vorlesen“, „✏️ Bearbeiten“, „✨ Neu beschreiben lassen“.
  - „✏️ Bearbeiten“ öffnet die Textarea MIT Text; „💾 Speichern“ schickt den Hand-Weg.
  - „✨ Neu beschreiben lassen“ zeigt zuerst „Kostet ca. 0,001 $ – fortfahren?“ im Kasten (eigene
    Bestätigung statt `window.confirm`, damit nichts blockiert und die Abfolge testbar ist). Erst
    „Fortfahren“ ruft den Vorschlag ab; er erscheint lesend mit „Übernehmen“ (speichert über
    `/uebernehmen`) und „Verwerfen“ (verändert nichts).
  - Leerer Zustand: „Für dieses Bild gibt es noch keine KI-Beschreibung.“ mit „✨ Neu beschreiben lassen“ und
    „✏️ Selbst schreiben“. Beim Öffnen gibt es keine Textarea und keinen Fokus.
  - Scheitert das Laden der Beschreibung, steht „Die Beschreibung konnte nicht geladen werden.“ (kein
    Editor, damit ein vorhandener Text nicht blind überschrieben wird).
- `frontend/erzaehlen.js`: neue reine Funktion `erzaehlBeschreibungFehltHinweis`; `geschichteErzeugen` schreibt bei
  `daten.beschreibung_gefunden === false` „Für dieses Bild gibt es noch keine Bildbeschreibung“ in
  `#erzaehl-bild-beschreibung` (dort, wo sonst die Beschreibung steht).
- `frontend/index.html`: neues `<script src="bild_beschreibung.js?v=20261102A">` vor `app.js`; Cache-Bump
  `app.js?v=20261102E`, `erzaehlen.js?v=20261102D`.
- `backend/app/sicherheit.py`: `bild_beschreibung.js` in der Positivliste `FRONTEND_DATEIEN` (sonst 404);
  `sw.js` bleibt unverändert (seine `STATIC_ASSETS` führen weder `erzaehlen.js` noch `gruppen_quiz.js`, die Dateien
  kommen über den Fetch-Zweig in den Cache).
- `backend/tests/test_datenschutz_waechter.py`: `API_BASE_LESER` um die neue Datei erweitert.
- `backend/tests/test_frontend_node.py`: `ZUORDNUNG` für `test_bild_beschreibung_lesen.js` -> `bild_beschreibung.js`.
  Die drei Tests, die `erzaehlen.js?v=20261102B` festgehalten hatten, sind mitgezogen
  (`test_erzaehlen.js`, `test_erzaehlen_geschichte_getrennt.js`, `test_erzaehlen_hand_gesichter.js`);
  `test_erzaehlen_geschichte_getrennt.js` bekommt außerdem die neue Hilfsfunktion in seine Schein-Umgebung.

## Herleitung der Kostenschätzung (`BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD = 0.001`)
**Schätzwert, ungemessen.** Es gab bisher keinen Messlauf für diesen Aufruf.
- Preise von `google/gemini-3.7-flash` (OpenRouter, live abgefragt am 27.09.2026, `docs/plan-nachtlauf-2026-09-26.md`):
  0,75 USD je 1 Mio Eingabe-Token, 3,75 USD je 1 Mio Ausgabe-Token.
- Eingabe: Vorschaubild 480×480 plus Prompt. Die Zahl der Bild-Token ist NICHT gemessen; angenommen werden
  einige hundert bis etwa 1.000 Token.
- Ausgabe: höchstens 400 Token (`MAX_TOKENS`); 2–4 deutsche Sätze liegen wahrscheinlich bei 100–200 Token.
- Rechnung: realistisch 600 ein + 150 aus ≈ 0,00045 + 0,00056 ≈ 0,001 USD; Obergrenze 1.000 ein + 400 aus
  ≈ 0,00075 + 0,0015 ≈ 0,0023 USD.
- Die Antwort der API meldet die echten Kosten (`kosten_usd`); die Oberfläche zeigt sie nach dem Aufruf
  an. Mit den ersten echten Aufrufen lässt sich die Konstante nachmessen und anpassen.

## Tests (alle offline, erfundene Daten)
- Neu `backend/tests/test_bild_beschreibung_herkunft.py` (17): Vorrang (Hand schlägt `*_reich`/SQLite, neueste
  App-Zeile gewinnt, Werkzeugzeile danach überschreibt nicht, leerer Text löscht nicht), Herkunft, GET
  `gefunden`/`quelle`, Übernehmen genau eine Zeile `einzel_ki`, `beschreibung_gefunden`.
- Neu `backend/tests/test_bild_beschreibung_vorschlag.py` (23): `data_collection: deny` im wirklich gesendeten
  Rumpf (echter ZDR-Client auf `httpx.MockTransport`) und im Aufruf, Zeitgrenze/HTTP-/Verbindungsfehler ehrlich
  ohne Schlüssel/URL, nichts gespeichert, Log ohne Text/Schlüssel/fileid, Bildabruf (480×480), Router.
- Neu `backend/tests/test_beschreibung_abdeckung.py` (7): Zahlen, SQLite, fehlende Dateien, Ausgabe ohne fileid und
  Text, schreibt nichts.
- Neu `frontend/tests/test_bild_beschreibung_lesen.js` (64 Prüfungen, läuft über `test_frontend_node.py`): (a), (b),
  (c), (e), (g2) und die Verdrahtung (eigene Datei vor `app.js`, Positionen, Cache-Bump), gegen die wörtlich aus
  `bild_beschreibung.js` geschnittene Funktion.

## Beleg Rot vor Grün
- `test_bild_beschreibung_herkunft.py` gegen den Stand vor der Änderung: 16 failed, 1 passed (der eine grüne
  Fall prüft die dünne Hülle, die schon galt); „Hand-Text schlägt `*_reich`“ rot mit
  `'Maschinenbeschreibung eins' == 'Mein eigener Text'`.
- `test_bild_beschreibung_vorschlag.py` und `test_beschreibung_abdeckung.py`: rot beim Sammeln bzw. Laden (Modul und
  Werkzeug existierten nicht).
- `test_bild_beschreibung_lesen.js`: rot, Absturz beim Laden („Funktion nicht gefunden“).
- Danach grün: 47 passed (die drei neuen Backend-Dateien), `test_frontend_node.py` 61 passed.

## Messung Abdeckung (02.11.2026, Echtdaten, nur Zahlen)
`tools/foto_sortierung/beschreibung_abdeckung.py` auf `~/foto_sortierung/` — rein lesend, Ausgabe nur Zahlen
(keine fileid, kein Text, kein Netz). Direkt am PC gezählt (nicht über Hermes): Das Werkzeug gibt ausschließlich
Aggregatzahlen aus, deshalb verlässt kein privater Inhalt den Rechner.
- Quellen: `bild_beschreibungen.jsonl` 19.065 Zeilen, `…_reich` 17.428, `…_papa_reich` 6.336, `…_rest_reich` 984,
  `…_altbestand_reich` 604; `life_archive.db` 19.065 Zeilen (alle mit Text).
- Bilder mit Beschreibung gesamt: **26.241** (KI 26.241, von Hand 0, KI-Einzelvorschlag 0 — erwartet, der Hand-
  und der Einzel-KI-Weg sind erst mit G2 neu und noch ungenutzt).
- **Fotobuch: 78 Einträge, 842 verschiedene Bilder, davon 840 mit Beschreibung (99,8 %), 2 ohne.**
- **Ereignisse: 2.127 Einträge, 7.616 verschiedene Bilder, davon 7.613 mit Beschreibung (100,0 %), 3 ohne.**

Befund: Die Anlass-Vermutung (Fotobuch-Seiten ohne Beschreibung) bestätigt sich **nicht** — die Abdeckung ist
praktisch vollständig. Ein eigener Nachbeschreib-Lauf wäre nur für die 2 Fotobuch- und 3 Ereignis-Bilder nötig.

## Offen
- ~~Messung der Abdeckung auf den echten Daten und Messwert ins Journal.~~ **Erledigt** — siehe „Messung Abdeckung" oben.
- Nachbeschreiben der Fotobuch-Beschreibungen entfällt praktisch (nur 2 + 3 Bilder ohne); bei Bedarf eigener
  Kleinlauf mit vorheriger Kostenmessung (nicht Teil von G2).
- Sichtprüfung am Handy (Lese-Ansicht, Kostenfrage, Vorschlag) — offen (von Sebastian am Handy).
