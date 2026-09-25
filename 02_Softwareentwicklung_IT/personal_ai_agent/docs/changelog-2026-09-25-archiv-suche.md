# Changelog 25.09.2026 — Wissensspeicher durchsuchbar + Bewusstsein „was mein Agent weiß"

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Auftrag (Sebastian, sinngemäß):** *„Ich habe meinen Agenten gefragt: ‚Was habe ich zu
Beginn der Aufzeichnungen mit ChatGPT besprochen?' — und dann benutzt er die Web-Suche und
hat keinen Zugriff darauf, obwohl ich die gefüllte Wissensdatenbank habe. Es müssten
semantische Suche UND Hybridsuche funktionieren."* — *„Er weiß, er hat eine
Wissensdatenbank."* — *„Dann könnte man über Vektorvergleiche nochmal ins Original gehen und
dann nochmal nachlesen."* — *„Wenn der Agent nicht sicher ist … dann möchte ich das als
Rückfrage nach meiner menschlichen Erinnerung gefragt werden."*

**Keine Archivinhalte in diesem Dokument** — nur Zahlen, Daten, Pfade, Feldnamen und
Themen-Stichworte.

---

## 1. Befund: Was war schon da?

Es gab bereits einen vollständigen Aufbereitungs-Anlauf im Schwesterprojekt
`Chats von GPT, GEMINI, Claude`. Geprüft wurde **nur lesend** (`mode=ro`), nichts verändert.

| Baustein | Befund | Urteil |
|---|---|---|
| `db/memory.db` (123,6 MB) | SQLite: `messages` 40.627 · `chunks` 30.891 · `chunks_fts` (FTS5) · `index_meta` | vorhanden, **brauchbar** |
| `db/memory.vektoren.f32` (126,5 MB) | 30.891 × 1024 float32, `mistral-embed` | vorhanden, **veraltet** (Modellwechsel) |
| `normalized/messages.jsonl` (49,1 MB) | 40.627 Zeilen; Zeilennummer = `messages.id` | vorhanden, **brauchbar** |
| `distilled/startbestand.jsonl` (58 KB) | 64 destillierte Aussagen | vorhanden, nicht nötig |
| `src/` (41 Dateien, u. a. `build_db.py`, `chunker.py`, `embed.py`, `speicher.py`) | volle Pipeline + 6 Adapter | vorhanden, **Vorarbeit übernommen** |
| `backend/app/services/archiv_service.py` + `router/archiv.py` | FTS + Vektorsuche, in `main.py` eingehängt | vorhanden, **nicht angefasst** |
| `backend/.env` | fehlt (nur `.env.example`) | **fehlt** |

**Zeitraum:** 1940-09-04 … 2026-12-28 (früh = Kalender/Geburtstage). Chats beginnen
2022-12-26 (chatgpt), 2024-10-20 (gemini), 2025-11-01 (claude-ai), 2026-05-29 (claude-code).

### Warum der Agent bisher nichts fand

`archiv_service` liest `settings.archiv_db_path`; `config.py` lädt nur
`personal_ai_agent/.env` und `personal_ai_agent/backend/.env` — **beide fehlen** → Pfad leer →
`is_available == False` → der Agent meldet „Wissensspeicher nicht erreichbar" und geht ins Web.
Zusätzlich passte die alte Vektordatei (1024 Dimensionen, Mistral) nicht mehr zur
Projekt-Entscheidung vom 25.09.2026 (**OpenRouter**, `openai/text-embedding-3-small`, 1536
Dimensionen — siehe `docs/konzept-gedaechtnis.md` §E1).

---

## 2. Was gebaut wurde

**Alles neu, nichts Bestehendes angefasst** (insbesondere nicht `router/chat.py` und nicht
`frontend/app.js` — die gehören parallelen Strängen; die Verdrahtung ins Chat-Prompt macht
der Haupt-Agent).

| Datei | Art | Was |
|---|---|---|
| `backend/app/services/archiv_suche.py` | **neu** | Hybridsuche (FTS5 + OpenRouter-Vektoren), Zeiger ins Original, Original nachlesen, Statistik, Chronik, Bewusstseins-Baustein. Inkl. Schema des Index (`SCHEMA_SQL`). |
| `backend/scripts/archiv_index_bauen.py` | **neu** | Baut den übertragbaren Index (eine Datei) aus `db/memory.db`; ermittelt die Quelldatei je Gespräch; rechnet die Vektoren über OpenRouter; weist geschätzte **und** gezählte Kosten aus. Einbetter injizierbar (Tests ohne Netz). |
| `backend/scripts/__init__.py` | **neu** | Namensraum, damit Tests den Indexierer importieren können. |
| `backend/app/router/archiv_wissen.py` | **neu** | 5 Endpunkte wie unten. Bewusst **eigene** Datei, damit sie nicht mit `router/archiv.py` / `router/chat.py` kollidiert. Einbau in `main.py`: zwei Zeilen (stehen im Kopf der Datei). |
| `backend/tests/test_archiv_suche.py` | **neu** | 26 Tests gegen kleine künstliche Daten im `tmp_path` — das echte Archiv wird **nie** geladen. |
| `docs/konzept-wissensspeicher.md` | **neu** | Bestandstabelle, Bauweise, Hybridsuche, Zwei-Stufen-Suche, Schwellwerte, Endpunkte, Einbauort des Bewusstseins-Bausteins, Kosten, USB-Übertragung, offene Punkte. |

### 2.1 Der Index — eine Datei

`Chats von GPT, GEMINI, Claude/db/archiv_index.db`, Tabellen `nachrichten`, `chunks`,
`chunks_fts` (FTS5), `vektoren` (float16), `gespraeche`, `meta`.

**Aufgesetzt auf den Bestand, nicht neu extrahiert:** die Normalisierung der sechs
Quellformate steckt in 41 Dateien und 30 Tests des Schwesterprojekts und hat nachweislich
funktioniert. Übernommen wurden `messages` (Originaltexte, Ordinale) und `chunks`
(Fundstellen); neu gerechnet wurden nur die **Vektoren** (Modellwechsel) und der
**Volltextindex** neu aufgebaut.

**Einbetter:** `POST {openrouter_base_url}/embeddings`, `openai/text-embedding-3-small`.
Es geht nur der Chunk-Text hinaus, einmalig beim Bauen.

**Nachträglich nur die Zeiger:** `--nur-quelldatei` trägt fehlende Quelldateien in einem
bestehenden Index nach, **ohne** neu einzubetten. Gebraucht wurde das einmal: Der
Google-Takeout-Ordner heißt `Google Notizen` (nicht `Notizen`), dadurch blieben zunächst 15
Gespräche ohne Quelldatei. Statt 8,5 Minuten Rechenzeit und 0,19 $ noch einmal zu bezahlen,
wurden nur die 15 Zeiger ergänzt — danach 1.109 von 1.109. Bei Google-Notizen ist die
Gesprächskennung der Dateiname, deshalb wird dort die *einzelne* Notizdatei aufgelöst, nicht
nur der Bereich.

**Warum float16:** 30.891 × 1536 Dimensionen wären float32 ≈ 190 MB, als float16 ≈ 95 MB.
Für eine Rangfolge reicht das (Fehler ~1e-3); gerechnet wird in float32, blockweise — das
spart auf dem Handy rund 100 MB Spitzenlast.

### 2.2 Zwei-Stufen-Suche: Treffer → Original

Sebastians Kernwunsch, in dieser Reihenfolge umgesetzt:

1. **Mathematischer Treffer** (Vektorvergleich bzw. Volltext). Jeder Treffer trägt einen
   **Zeiger ins Original**: `quelldatei`, `chat_kennung`, `ordinal` (Nachrichten-Ordinal),
   `ordinale`, `titel`, `datum`. Ein Treffer ohne Zeiger wird **verworfen und protokolliert** —
   er ist wertlos. Der Rückweg über `normalized/messages.jsonl` + Ordinal ist immer vorhanden,
   auch wenn die Originaldatei in einem Takeout-Zip liegt.
2. **Original nachlesen:** `original(chat_kennung, ordinal, kontext=1)` liefert den
   **unveränderten** Originaltext **plus Kontextfenster** (Nachricht davor/danach,
   einstellbar 0–10). Kein Kürzen, kein Umschreiben, kein Zusammenfassen — das ist im Test
   Zeichen für Zeichen nachgeprüft.

### 2.3 Nie erfinden: Unsicherheit → Rückfrage

Jedes Ergebnis trägt `sicher`, `grund` und bei Unsicherheit eine **fertige `rueckfrage`**.
Bei `sicher: false` gibt es bewusst **kein** Feld `antwort` — nur Kandidaten mit Zeigern.

Schwellwerte als Zahlen (Konstanten in `archiv_suche.py`, dokumentiert in
`docs/konzept-wissensspeicher.md` §5):

| Konstante | Wert |
|---|---|
| `AEHNLICH_STARK` | 0,45 |
| `AEHNLICH_SCHWACH` | 0,30 |
| `WETTBEWERB_ABSTAND` | 0,03 |

`grund` ∈ {`eindeutig`, `keine_treffer`, `nur_schwache_aehnlichkeit`,
`widerspruechliche_fundstellen`, `kein_index`}.

### 2.4 Bewusstsein (Prompt-Baustein, **kein** Eingriff in `chat.py`)

`archiv_suche.prompt_baustein()` liefert Kennzahlen (Quellen, Zeitraum, Anzahl, Themenbereiche)
plus die Regel *„bei Fragen nach früheren Gesprächen ZUERST hier suchen, NICHT im Web"* und
*„bei sicher=false fragen, nicht behaupten"*.

**Einbauort (für den Haupt-Agenten):** `backend/app/services/llm_service.py`, Methode
`_build_messages` (ab Zeile 527), direkt **nach** `system_prompt += KONTEXT_FOKUS_ANWEISUNG`
(Zeile 547). Der vorhandene `_build_archiv_context` (Zeile 499) hängt nur **Treffer** an — die
entstehen erst nach einer Suche. Der Agent muss aber **auch ohne Suche** wissen, dass er ein
Archiv hat. Genau daran ist Sebastians Frage gescheitert.

### 2.5 Endpunkte (neuer Router)

| Endpunkt | Zweck |
|---|---|
| `GET /api/archiv/wissen/statistik` | Gespräche/Nachrichten je Quelle, Zeitraum, Jahre, Themen-Häufigkeit |
| `GET /api/archiv/wissen/chronik?richtung=alt\|neu&limit=N` | älteste/neueste Gespräche mit Datum + Quelle + Thema + Zeiger |
| `GET /api/archiv/wissen/frage?q=…&modus=…` | Hybridsuche, **zeitlich sortiert**, mit `sicher`/`grund`/`rueckfrage` |
| `GET /api/archiv/wissen/original?chat_kennung=…&ordinal=…` | Original nachlesen, unverändert, mit Kontext |
| `GET /api/archiv/wissen/ueberblick` | Bewusstseins-Baustein als JSON |

---

## 3. Probe am echten Archiv (Zahlen)

Gefahren am 25.09.2026 gegen den echten Index. Ausgegeben wurden nur Zahlen, Datumsangaben,
Quellen und Themen-Stichworte.

**Index:** 40.627 Nachrichten · 30.891 Fundstellen · **1.109 Gespräche** ·
30.891 Vektoren × 1536 · Zeitraum 1940-09-04 … 2026-12-28 ·
**Token gezählt 9.613.866 → Kosten 0,192277 $** · Baudauer 509,8 s · **Dateigröße 239,7 MB** ·
**Quelldatei für 1.109 von 1.109 Gesprächen und 30.891 von 30.891 Chunks aufgelöst**.

| Quelle | Gespräche | Nachrichten | von … bis |
|---|---|---|---|
| chatgpt | 109 | 19.057 | 2022-12-26 … 2026-08-02 |
| claude-code | 40 | 13.328 | 2026-05-29 … 2026-08-11 |
| gemini | 384 | 4.734 | 2024-10-20 … 2026-08-12 |
| claude-ai | 162 | 3.058 | 2025-11-01 … 2026-08-04 |
| google-kalender | 399 | 405 | 1940-09-04 … 2026-12-28 |
| google-notizen | 15 | 15 | 2020-09-20 … 2025-11-23 |

**Die drei ältesten Gespräche** sind Kalendereinträge (1940-09-04, 1965-08-16, 1968-04-19,
alle `google-kalender`) — Geburtstage aus dem Familienkreis; die betroffenen Personen werden
hier bewusst nicht genannt. **Der älteste echte Chat** ist vom **2022-12-26** (chatgpt), es
folgen Ende 2022 Technik-, Koch- und Sprachthemen.

**Echte Frage „Was habe ich zu Beginn der Aufzeichnungen mit ChatGPT besprochen?"**
(Volltext 5 Treffer, `sicher: true`, aber nur mit späten Stellen ab 2025 · Vektor 5 Treffer,
`widerspruechliche_fundstellen` · Hybrid ebenso): Die Suche liefert dazu **keine** Behauptung,
sondern eine **Rückfrage** — genau wie gewünscht. Der inhaltliche Weg für solche
Rückblicksfragen ist die **Chronik** (älteste Gespräche mit Datum und Titel); der
Bewusstseins-Baustein sagt das jetzt ausdrücklich.

**Zeiger-Rundlauf geprüft:** Der erste Treffer lieferte
`raw/chatgpt/conversations-000.json`, Chat-Kennung und Ordinal; das nachgelesene Original war
Zeichen für Zeichen identisch mit der abgelegten Nachricht, mit je einer Nachricht Kontext
davor und danach.

**Am echten Bestand nachgeschärft:** FTS5 verknüpft die Suchwörter mit OR — ein Chunk mit 1 von
4 Wörtern galt zunächst als „belastbar", und die Anfrage `xyzzy plugh foobar qwertz zxcvb` kam
mit `sicher: true` zurück. Jetzt zählt der Dienst die *wirklich* passenden Begriffe (mindestens
zwei, bei Ein-Wort-Anfragen einer); dieselbe Anfrage ergibt `sicher: false`
(`nur_schwache_aehnlichkeit`) mit Rückfrage. Details in `docs/konzept-wissensspeicher.md`
§3 und §8.5.

---

## 4. Prüfbefehle (echte Ausgaben)

```
$ cd backend && .venv/Scripts/python -m pytest tests/test_archiv_suche.py -q
28 passed, 2 warnings in 3.82s

$ cd backend && .venv/Scripts/python -m pytest tests/ -q
333 passed, 3 warnings in 87.64s        (Exit 0)
```

Baseline des Auftrags war **272 passed** — sie ist **nicht gesunken**. Der Bestand war zum
Zeitpunkt dieser Arbeit bereits auf 304/330 gewachsen, weil parallele Stränge Tests
beigetragen haben; kein Test ist rot.

Abgedeckt (jeweils eigener Test):

| Anforderung | Test |
|---|---|
| (a) Volltext findet Begriff | `test_volltext_findet_begriff` |
| (b) sinngemäße Formulierung über Vektoren (Einbetter gemockt) | `test_semantik_findet_umschreibung` |
| (c) Treffer trägt Quelle + Datum + Kennung | `test_treffer_tragen_quelle_datum_kennung` |
| (d) zeitliche Sortierung | `test_treffer_sind_zeitlich_sortiert` |
| (e) „nichts gefunden" ehrlich (mit Zeitraum) | `test_nichts_gefunden_wird_ehrlich_gemeldet` |
| (f) Statistik zählt korrekt | `test_statistik_zaehlt_korrekt` |
| (g) Überblick nennt Quellen+Zeitraum+Anzahl | `test_ueberblick_enthaelt_quellen_zeitraum_anzahl` |
| (h) ohne Vektor-Index → Volltext + Hinweis | `test_ohne_vektorindex_faellt_auf_volltext_zurueck` |
| (i) Zeiger (Datei + Chat-Kennung + Ordinal) | `test_jeder_treffer_traegt_zeiger`, `test_quelldatei_finder_findet_chatgpt_shard` |
| (ii) Original unverändert + Kontext | `test_original_liefert_unveraenderten_text_mit_kontext` |
| (iii) schwach → `sicher: false` + Rückfrage, keine Behauptung | `test_schwache_aehnlichkeit_gibt_rueckfrage_statt_antwort` |
| (iv) widersprüchliche Fundstellen → `sicher: false` | `test_widerspruechliche_fundstellen_sind_unsicher` |
| (v) eindeutig → `sicher: true` | `test_eindeutiger_treffer_ist_sicher` |

Zusätzlich: Index ist **eine** Datei (keine `.f32`/`.npy` daneben)
(`test_index_ist_eine_datei_mit_vektoren_drin`), beide Suchwege werden am selben Treffer
vermerkt (`test_hybrid_vermerkt_beide_wege`), Router-Endpunkte über `TestClient`, leeres
Archiv wird ehrlich gemeldet.

---

## 5. Übertragung aufs Handy

```bash
# PC, aus dem Workspace-Ordner:
adb push "Chats von GPT, GEMINI, Claude/db/archiv_index.db" /sdcard/Download/archiv_index.db
```

```bash
# Handy (Termux):
mv /sdcard/Download/archiv_index.db /data/data/com.termux/files/home/archiv_index.db
```

Der Dienst findet den Index ohne weitere Einstellung (Suchreihenfolge in
`docs/konzept-wissensspeicher.md` §7). **Der Index liegt bewusst im Archivordner**, weil der
per `.gitignore` aus dem Repo ausgeschlossen ist — im Projektordner könnte eine ~200-MB-Datei
mit den vollständigen Gesprächen versehentlich mitcommittet werden.

---

## 6. Offene Punkte

1. **Verdrahtung durch den Haupt-Agenten:** Router in `main.py` einhängen; Bewusstseins-Baustein
   in `llm_service._build_messages` einhängen (§2.4); **`backend/.env` mit
   `OPENROUTER_API_KEY` anlegen** — ohne Schlüssel läuft nur der Volltext.
2. Alte Vektordatei `db/memory.vektoren.f32` ist unbrauchbar, wurde aber **nicht gelöscht**.
3. **WhatsApp** (`raw/whatsapp/`, 2 Dateien) ist im Bestand nicht enthalten — eigene
   Entscheidung Sebastians.
4. Google-Fotos sind bewusst nicht im Textindex.
5. Themen-Häufigkeit = Wortzählung über die Gesprächst*itel*, keine Modell-Deutung.

---

## 7. Datenschutz

* Alle Archivdateien **nur lesend** (`mode=ro`), keine echte Datei geändert oder gelöscht.
  Beim Lesen einer SQLite-Datenbank im WAL-Modus legt SQLite seine üblichen Nebendateien an
  (`memory.db-shm` 32 KB, `memory.db-wal` 0 Byte); **`memory.db` selbst ist unverändert**
  (Änderungszeitpunkt 13.08.2026), es wurde kein Datensatz geschrieben. Die Nebendateien
  wurden bewusst **nicht** gelöscht — Löschen wäre der größere Eingriff.
* Nach außen geht beim **Bauen** der Chunk-Text (Einbettung, einmalig) und beim **Suchen** nur
  die Suchfrage. Sonst verlässt kein Archivinhalt das Gerät.
* Der Index liegt im gitignorierten Archivordner und gehört **nicht** ins Repo.
* Dieses Dokument, die Tests und die Berichte enthalten nur Zahlen und Strukturen.
