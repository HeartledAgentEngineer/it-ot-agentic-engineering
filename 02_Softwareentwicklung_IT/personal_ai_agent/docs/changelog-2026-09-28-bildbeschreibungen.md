# Changelog 28.09.2026 — Bildbeschreibungen je Einzelbild + Bildindex (N15)

Plan-Schritt **N15**: „Einzelbild-Stufe: eine Inhaltsbeschreibung JE BILD ->
`bild_beschreibungen.jsonl`", dazu die Einbettung in eine Bild-Vektordatenbank,
mit **Kostenbremse 1,00 USD** und **Messung an 3 Bögen vorab**.

Neu in diesem Schritt:

| Artefakt | Pfad | Was |
|---|---|---|
| Werkzeug Beschreiben | `tools/foto_sortierung/bild_beschreiben.py` | Kontaktbögen aus Vorschaubildern **im Arbeitsspeicher**, ein Vision-Aufruf je Bogen, je Kachel eine Beschreibungszeile |
| Werkzeug Einbetten | `tools/foto_sortierung/bild_index_einbetten.py` | Beschreibungstexte -> Vektoren -> `bild_index.db` (Tabelle `bilder`) |
| Ausgabe (außerhalb Repo) | `~/foto_sortierung/bild_beschreibungen.jsonl` | eine Zeile je Bild, **keine Bilddaten** |
| Vektordatenbank (außerhalb Repo) | `~/foto_sortierung/bild_index.db` | `bilder` (fileid, datum, ordner, beschreibung, vektor) + `meta` |
| Prüfungen | `backend/tests/test_bild_beschreiben.py` | 38 Prüfungen, alles offline (Vision/pCloud als Attrappen) |

## 1. Wie die Beschreibung je Bild entsteht (bestehender Weg, wiederverwendet)

Kein neuer Weg: `bild_beschreiben.py` lädt die Nachbarwerkzeuge per Pfad und
benutzt sie unverändert.

* aus `foto_themen.py`: CSV lesen (`zeilen_lesen`), Dateizeit aus dem Namen
  (`zeit_aus_name`), fileid-Auflösung über `listfolder` (`dateien_im_ordner`,
  ein Aufruf je Ordner, mit Zwischenspeicher), Vorschaubilder in Stapeln
  (`vorschau_stapel`, `getthumbs`), **`bogen_bauen`** — dieselbe Bogen-Geometrie
  wie im bestandenen N5-Bogen: 8 Spalten, 160 px je Kachel, **1382 × 872 px bei
  36 Kacheln** (im Test als Zahl festgenagelt).
* aus `foto_themen_vision.py`: Transport mit Wiederholung (`sende_aufruf`),
  Antwort-Zerlegung (`antwort_zerlegen`), Schlüssel-Suche (`schluessel_finden`),
  Kostenrechnung (`kosten_berechnen`), Geheimnis-Entschärfung
  (`geheimnis_entfernen`).
* aus `backend/scripts/archiv_index_bauen.py` (Einbetten): `EinbetterOpenRouter`,
  `_vektor_blob` (float16), `PREIS_JE_MIO_TOKEN = 0,02 USD`, `_schluessel_holen`
  — wörtlich übernommen, kein zweiter Einbettungsweg.

Ablauf je Bogen: Vorschaubilder holen -> Kacheln **ohne** Vorschau fallen aus dem
Bogen (die Datei bleibt offen und kommt im nächsten Lauf wieder) -> Bogen im
Speicher bauen -> **ein** Aufruf an OpenRouter -> Antwort zerlegen -> je gültiger
Kachel eine Zeile anhängen. Der Bogen existiert nur als Bytes im
Arbeitsspeicher; es wird **kein Bild auf die Platte geschrieben oder kopiert**
(im Test geprüft: nach einem Lauf liegt keine einzige Bilddatei im Zielordner).

## 2. Ausgabeformat `bild_beschreibungen.jsonl`

Genau die vereinbarten Felder — **keine Bilddaten, kein base64**:

```json
{"fileid": 0000000000, "datei": "…", "jahr": 2025, "monat": 6, "tag": 14,
 "ordner": "…", "beschreibung": "…", "bogen_id": "bogen-<fileid der ersten Kachel>",
 "modell": "…", "kosten_usd": 0.00012345, "zeit": "2026-09-28T…"}
```

* `beschreibung`: eine Zeile, höchstens 14 Wörter, gegenständlich (Personen ohne
  Namen, Ort, Situation, Gegenstände) — gedacht für die Textsuche.
* `kosten_usd` je Zeile = Aufruf-Kosten des Bogens geteilt durch die Zahl der
  geschriebenen Zeilen; **Summe über alle Zeilen = tatsächliche Aufruf-Kosten**.
* Absichtlich **nicht** enthalten: `unbrauchbar` als Feld. Kacheln, die nichts
  Erkennbares zeigen, nennt das Modell im Beschreibungstext selbst — im
  Bericht werden sie gesondert gezählt.

## 3. Kostenbremse (harte Grenze) und Messung

* `--budget` (Standard **1,00 USD**) — geprüft **vor** jedem Aufruf:
  bereits ausgegeben + Durchschnitt der bisherigen Aufrufe > Budget ⇒ Stopp mit
  Bericht; kein Aufruf wird begonnen, der die Grenze reißen würde.
* Nach den ersten **3 Bögen** (Messung) druckt das Werkzeug Dauer und Kosten je
  Bogen und rechnet auf den Rest hoch; danach Fortschritt je Stapel
  (`--stapel`, Standard 25). Preise: **0,30 USD/1M Eingabe-Tokens,
  2,50 USD/1M Ausgabe-Tokens** (Parameter `--preis-ein`/`--preis-aus`).
* Idempotenz: übersprungen wird über `fileid` **und** `(ordner, datei)`;
  ein zweiter Lauf hängt 0 Zeilen an. Nach einem Abbruch macht der nächste
  Aufruf bei den offenen Dateien weiter (nichts wird stillschweigend
  übersprungen, fehlgeschlagene Bögen schreiben nichts).

### Messung (3 Bögen, Zahlen aus dem Lauf)

Der Auftrag verlangt ausdrücklich: „Erst messen, dann weiter". Der Messlauf war
`--limit 3` (also genau drei Bögen), protokolliert in
`~/foto_sortierung/n15_messung_3_boegen.log`:

| Größe | Wert |
|---|---|
| Bögen (Aufrufe) | 3 |
| Bilder | 108 (3 × 36 Kacheln, je Bogen **36/36** beschrieben, lückenlos) |
| Tokens je Bogen | 2.301 Eingabe + 1.499 / 1.527 / 1.595 Ausgabe |
| Kosten | **0,013624 USD** gesamt = 0,004541 USD je Bogen = **0,000126 USD je Bild** |
| Dauer | 8,1 / 8,4 / 8,4 s je Aufruf; **63,9 s** für den Messlauf (davon ~35 s Auflösung der Dateikennungen) |
| Modell | `google/gemini-2.5-flash` (0,30 USD/1M Eingabe, 2,50 USD/1M Ausgabe) |
| ohne Vorschau / unbrauchbar / verworfene Einträge | 0 / 0 / 0 |

Hochrechnung: 8.302 Bilder = 231 Bögen ⇒ **~1,05 USD**. Der ganze Bestand passt
also knapp **nicht** in die Kostengrenze von 1,00 USD — gewolltes Verhalten: der
Lauf fährt bis an die Grenze, stoppt dort mit Bericht, und der Rest bleibt offen
(wiederholbar, nichts geht verloren).

Damit die Gesamtkosten des Auftrags (Beschreiben **und** Einbetten) unter
1,00 USD bleiben, lief der große Beschreibungs-Lauf mit `--budget 0,97`
(Parameter, nicht Standard) — die Einbettung kostet nur den Bruchteil eines
Cents. Ein späterer Lauf mit höherem Budget holt die offenen Bilder nach.

## 4. Einbetten in die Bild-Vektordatenbank

`bild_index_einbetten.py` liest die JSONL, lässt bereits eingebettete `fileid`
aus (Idempotenz), rechnet die Texte über den bestehenden Einbettungsweg
(`openai/text-embedding-3-small`, 1536 Dimensionen, 0,02 USD je 1 Mio Token) und
legt sie in `bild_index.db` ab:

```sql
CREATE TABLE bilder (fileid INTEGER PRIMARY KEY, datum TEXT, ordner TEXT,
                     beschreibung TEXT, vektor BLOB);   -- float16, 3072 Byte
CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);
```

Trockenlauf ist der Standard (legt **keine** Datei an); `--schreiben` bettet ein.
`meta` hält Stand, Anzahl, Dimension, Modell, Token und Kosten (über Läufe
kumuliert). Das Text-Archiv (`Chats von GPT, GEMINI, Claude/db/*`) bleibt
unangetastet — es entsteht nur diese unabhängige Bild-Datenbank.

### Einbettungslauf (Zahlen)

<!-- EINBETTUNG -->

## 5. Prüfungen

`backend/tests/test_bild_beschreiben.py` — 38 Prüfungen, **offline**: Vision,
`listfolder` und `getthumbs` sind Attrappen, `httpx.post`/`httpx.get` sind in der
autouse-Fixture komplett gesperrt, es gibt keine echten Bilder (winzige, im Test
erzeugte JPEGs), alle Ausgaben gehen nach `tmp_path`. Abgedeckt sind u. a.:

* Bogen-Bau: 36 Kacheln/8 Spalten -> **1382 × 872**, JPEG, **kein Bild auf Platte**;
* Antwort-Zerlegung: erfundene/doppelte/leere Kacheln fallen einzeln weg,
  `unbrauchbar` bleibt Information, komplett ungültige Antwort = Fehler;
* Idempotenz: zweiter Lauf sendet nichts und hängt 0 Zeilen an; Fortsetzen nach
  Stopp holt genau den Rest;
* Kostenbremse: Stopp **vor** dem Aufruf (Aufrufzähler!), Messbericht mit
  Hochrechnung, Einbettung stoppt am Budget und behält den Fortschritt;
* Schreiben der JSONL: genau die 11 Felder, kein `base64`/`data:image`, nur
  anhängen, kaputte Zeilen werden ignoriert;
* Schranken: Ausgabe/DB im Repo = Abbruch vor allem anderen (Exit 2), ohne
  Schlüssel wird nichts gesendet, `--trocken`/`--nur-liste` ohne Netzaufruf.

Prüfbefehl (Ergebnis siehe unten):

```
cd 02_Softwareentwicklung_IT/personal_ai_agent/backend
.venv/Scripts/python -m pytest tests/ -q
```

## 6. Aufruf

```bash
cd backend
.venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --nur-liste
.venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --trocken
.venv/Scripts/python ../tools/foto_sortierung/bild_beschreiben.py --budget 1.0   # Lauf mit Kostenbremse
.venv/Scripts/python ../tools/foto_sortierung/bild_index_einbetten.py            # Trockenlauf
.venv/Scripts/python ../tools/foto_sortierung/bild_index_einbetten.py --schreiben
```

<!-- ABSCHLUSS -->
