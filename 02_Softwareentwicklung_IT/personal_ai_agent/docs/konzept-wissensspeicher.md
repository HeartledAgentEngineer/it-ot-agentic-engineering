# Konzept: Wissensspeicher (Chat-Archiv) — durchsuchbar machen + Bewusstsein

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT)
**Stand:** 25.09.2026
**Auslöser (Sebastian, sinngemäß):** *„Ich habe meinen Agenten gefragt: ‚Was habe ich zu
Beginn der Aufzeichnungen mit ChatGPT besprochen?' — und dann benutzt er die Web-Suche und
hat keinen Zugriff darauf, obwohl ich die gefüllte Wissensdatenbank habe. Es müssten
semantische Suche UND Hybridsuche funktionieren."*
Weiter: *„Er weiß, er hat eine Wissensdatenbank — eigentlich müsste er es wissen, dass er die
ganzen Daten aus Extrakten bekommen hat."*
Und: *„Man hat Punkte gefunden durch die Indizierung und die Vektorsuche. Dann könnte man
über Vektorvergleiche nochmal ins Original gehen und dann nochmal nachlesen."*

**Keine Archivinhalte in diesem Dokument.** Es stehen nur Zahlen, Feldnamen, Pfade und
Strukturen darin — keine Zitate, keine Themen im Klartext, keine Namen. Alle Tests laufen in
`tmp_path` gegen künstliche Daten, nie gegen den echten Bestand.

**Prüfbefehle (in dieser Arbeit ausgeführt):**

| Was | Befehl | Ergebnis |
|---|---|---|
| Backend-Tests | `cd backend && .venv/Scripts/python -m pytest tests/ -q` | **333 passed**, Exit 0 |
| Neue Tests einzeln | `… -m pytest tests/test_archiv_suche.py -q` | **28 passed**, Exit 0 |
| Doku-Vorgabe des Auftrags | Baseline war 272 — **nicht gesunken**, gestiegen | ✓ |

---

## §1 Bestand — was war schon da (vor dem Bauen geprüft)

Geprüft wurden die Dateien **nur lesend** (`mode=ro`), die echten `db/`-Dateien wurden nicht
verändert. Ergebnis:

| Baustein | Befund | Urteil |
|---|---|---|
| `db/memory.db` (123,6 MB) | SQLite. Tabellen: `messages` (40.627 Zeilen), `chunks` (30.891), `chunks_fts` (**FTS5**, `unicode61 remove_diacritics 2`), `index_meta` (8 Schlüssel). Indizes auf Zeit/Gespräch. | **vorhanden, brauchbar** |
| `db/memory.vektoren.f32` (126,5 MB) | Rohe float32-Matrix, 30.891 × 1024, Modell `mistral-embed` (steht in `index_meta`). | **vorhanden, aber veraltet** |
| `normalized/messages.jsonl` (49,1 MB) | 40.627 JSONL-Zeilen, Felder `conversation_id`, `source`, `timestamp`, `role`, `text`, `title`, `project`. Zeilennummer = `messages.id`. | **vorhanden, brauchbar** |
| `distilled/startbestand.jsonl` (58 KB) | 64 destillierte Aussagen (Fremdbestand, `geprueft: false`). | vorhanden, für die Suche nicht nötig |
| `src/` (41 Dateien) | Volle Pipeline des Schwesterprojekts: `build_db.py`, `chunker.py`, `embed.py`, `speicher.py`, `suchen.py`, 6 Adapter, `filter.py`, `verify.py`. | **vorhanden — Vorarbeit wird übernommen** |
| `tests/` (30 Dateien), `docs/`, `tools/` | Tests und Werkzeuge des Schwesterprojekts. | vorhanden, nicht angefasst |
| `backend/app/services/archiv_service.py` | **Existiert schon**: FTS + Vektorsuche + `hybrid()`, liest `chunks`/`chunks_fts`, Vektordatei als `memmap`. | vorhanden, **nicht angefasst** |
| `backend/app/router/archiv.py` | **Existiert schon**, in `main.py` eingehängt: `GET /api/archiv/status`, `GET /api/archiv/suche`. | vorhanden, **nicht angefasst** |
| `backend/.env` | **fehlt** (nur `.env.example`). | **fehlt — Ursache siehe §1.1** |

**Zeitraum des Bestands:** 1940-09-04 bis 2026-12-28 (der frühe Teil sind Geburtstage und
Kalendereinträge). Die **Chat**-Kanäle beginnen 2022-12-26 (chatgpt), 2024-10-20 (gemini),
2025-11-01 (claude-ai), 2026-05-29 (claude-code).

**Mengen je Quelle (aus `memory.db`):** chatgpt 19.057 Nachrichten / 19.443 Chunks · claude-code
13.328 / 3.185 · gemini 4.734 / 4.537 · claude-ai 3.088 / 3.280 · google-kalender 405 / 403 ·
google-notizen 15 / 43.

### §1.1 Warum der Agent nichts fand

Die Kette war: `archiv_service.py` liest seinen Pfad aus `settings.archiv_db_path` →
`settings.env_file` sind nur `personal_ai_agent/.env` und `personal_ai_agent/backend/.env` →
**beide Dateien existieren nicht** → `archiv_db_path` bleibt leer → `is_available` ist `False` →
der Agent meldet „Wissensspeicher nicht erreichbar" und fällt auf die Web-Suche zurück.

Der OpenRouter-Schlüssel liegt ausserdem **nur** in `…/workspace agentic engineering/.env` —
diese Datei liest `config.py` nicht. Das ist ein Verdrahtungspunkt für den Haupt-Agenten
(§9, Punkt 1).

**Zweiter Grund:** Selbst mit Pfad liefe die semantische Suche ins Leere. Die vorhandene
Vektordatei ist `mistral-embed` (1024 Dimensionen); das Projekt hat sich am 25.09.2026 aber auf
**OpenRouter** festgelegt (`openai/text-embedding-3-small`, 1536 Dimensionen, siehe
`docs/konzept-gedaechtnis.md` §E1). Ein 1536er-Fragevektor passt nicht auf eine 1024er-Matrix.

---

## §2 Der neue Index — eine Datei, alles drin

Gebaut von `backend/scripts/archiv_index_bauen.py`. **Aufgesetzt auf den Bestand, nicht neu
extrahiert:** `messages` und `chunks` werden aus `db/memory.db` übernommen (samt
Nachrichten-Ordinalen), die FTS5-Tabelle wird neu aufgebaut, und die Vektoren werden **neu
gerechnet** — mit OpenRouter, weil das die Entscheidung des Projekts ist.

**Begründung, warum aufgesetzt statt neu extrahiert:** Die Normalisierung der sechs
Quellformate (ChatGPT-Export, Gemini-HTML, Claude-Exports, Takeout) steckt in 41 Dateien und
30 Tests des Schwesterprojekts und hat nachweislich funktioniert (40.627 Nachrichten mit
Zeitstempeln, Rollen und Ordnungszahlen). Sie ein zweites Mal zu schreiben wäre Risiko ohne
Gewinn. Was fehlte, waren nur zwei Dinge: Vektoren im richtigen Modell und **alles in einer
Datei**.

**Eine Datei** (`archiv_index.db`), Tabellen:

| Tabelle | Inhalt | Zweck |
|---|---|---|
| `nachrichten` | 40.627 Originalnachrichten + Ordinal (`id` = Zeile in `messages.jsonl`) | **Original nachlesen** (§4) |
| `chunks` | 30.891 Fundstellen, `beginn`/`ende`, `title`, `quelldatei`, `nachricht_ids` | Suchtreffer |
| `chunks_fts` | FTS5-Volltextindex (external content) | Wortlaut-Suche |
| `vektoren` | `chunk_id`, `dimension`, `modell`, `vektor` (float16-BLOB) | Bedeutungs-Suche |
| `gespraeche` | je Gespräch: Quelle, Titel, `quelldatei`, von/bis, Zählungen | Chronik, Statistik |
| `meta` | Modell, Dimension, Zahlen, Zeitraum, Token, Kosten, Bauzeitpunkt | Nachweisbarkeit |

**Warum float16:** 30.891 × 1536 Dimensionen sind als float32 rund 190 MB, als float16 rund
**95 MB**. Für eine Rangfolge reicht float16 (Fehler ~1e-3); gerechnet wird trotzdem in
float32, blockweise — das spart auf dem Handy ca. 100 MB Spitzenlast. Vektoren liegen **im
Index**, nicht daneben (der alte Bestand hatte genau das als Schwäche: eine rohe
`.f32`-Neben-Datei, die zum Index passen muss).

**Kosten (OpenRouter, `openai/text-embedding-3-small`, 0,02 $/1 Mio Token):** Es geht **nur
der Chunk-Text** hinaus, und nur einmalig beim Bauen. Die tatsächlich gezählten Werte stehen in
§8.

---

## §3 Hybridsuche — Wortlaut + Bedeutung

`backend/app/services/archiv_suche.py`. Zwei Wege, ein Ergebnis:

* **Volltext (FTS5)** — findet Wörter: Eigennamen, Fachbegriffe, Produktnamen. Kein Netz,
  kein Schlüssel, keine Kosten, Millisekunden.
* **Vektor (OpenRouter)** — findet Bedeutung: „Wo bin ich damals hingezogen?" steht so in
  keinem Gespräch, hat aber dutzende Fundstellen. Dafür verlässt **nur die Suchfrage** das
  Gerät — ein kurzer Satz, kein Archivinhalt.

**Zusammenführung:** Beide Wege bekommen ein festes Kontingent (mindestens die Hälfte an den
Vektorweg, der Rest an den Volltext). Ohne das füllt die Vektorsuche alle Plätze und der
Volltext kommt nie zum Zug — dann fehlen genau die Eigennamen, für die er da ist. Findet ein
Treffer über beide Wege, steht das im Feld `gefunden_ueber` als `"vektor+volltext"`.

**Zeitliche Sortierung:** Die Trefferliste kommt **aufsteigend nach Datum** zurück
(`sortierung: "zeit"`). Die Frage lautet „was war damals" — also ist die Chronologie die
richtige Achse, nicht die Ähnlichkeit. Die Ähnlichkeitswerte bleiben je Treffer erhalten.

**Ehrlicher Rückfall:** Fehlt der Vektorweg (keine Vektoren im Index / kein Schlüssel /
Einbettung schlug fehl), steht im Ergebnis `wege.vektor: false` **plus** `wege.vektor_status`
mit dem genauen Grund **plus** ein `hinweis` im Klartext. Die Suche ist dann schlechter, aber
nie stumm leer — und der Nutzer sieht, warum.

**Belastbarkeit im Volltext (nachgeschärft am echten Bestand):** FTS5 verknüpft die Suchwörter
mit **OR**. Ein Chunk, der von fünf Suchwörtern nur *eines* enthält, war damit zunächst ein
vollwertiger Treffer — auf 30.891 Chunks findet jedes beliebige Wort irgendetwas, also wirkte
sogar eine sinnfreie Anfrage „belastbar". Deshalb zählt der Dienst jetzt die **wirklich
passenden Begriffe** (`passende_begriffe` steht im Treffer) und verlangt mindestens **zwei**
davon — bei einer Ein-Wort-Anfrage naturgemäß einen. Die Rangfolge im Volltext richtet sich
nach dieser Zahl, bei Gleichstand nach bm25. Beleg und Vorher/Nachher-Zahlen in §8.

---

## §4 Zwei-Stufen-Suche: Treffer → Original (Sebastians Kernwunsch)

Die Reihenfolge ist **festgelegt und absichtlich so**:

1. **Stufe 1 — mathematischer Treffer.** Vektorvergleich bzw. Volltextfilter liefert
   Fundstellen. Das ist eine Ähnlichkeitsrechnung, **kein Beweis**. Jeder Treffer trägt
   deshalb einen **Zeiger ins Original**:

   ```
   zeiger = {
     quelldatei:      "raw/chatgpt/conversations-000.json"   # oder normalized/messages.jsonl
     messages_jsonl:  "normalized/messages.jsonl"            # immer: Rückweg über den Ordinal
     chat_kennung:    "<conversation_id>",                   # Chat-Kennung
     ordinal:         1234,                                  # Nachrichten-Ordinal (erste Nachricht)
     ordinale:        [1234, 1235],                          # alle Nachrichten des Chunks
     titel:           "<Gesprächstitle>",
     datum:           "2026-03-12",
   }
   ```

   **Ein Treffer ohne Zeiger ist wertlos.** Deshalb prüft der Dienst das beim Bauen jedes
   Treffers selbst: Fehlt Gesprächskennung oder Ordinal, wird die Fundstelle **verworfen** und
   protokolliert — statt als Volltext ohne Herkunft aufzutauchen. Und weil der Zeiger bei
   Google-Quellen auch in einem Takeout-Zip liegen kann, steht der Rückweg über
   `normalized/messages.jsonl` + Ordinal **immer** zusätzlich bereit: Der Ordinal ist die
   Zeilennummer der Nachricht in dieser Datei, also ein stabiler, prüfbarer Zeiger.

   Die Quelldatei wird beim Bauen **einmal** ermittelt (je Gespräch, nicht je Chunk):
   ChatGPT aus dem Shard, der die Kennung enthält; claude-ai fest; claude-code über den
   Dateinamen; Gemini/Google über das Takeout-Zip samt innerem Pfad. Nicht Ermittelbares
   bleibt ehrlich leer und fällt auf `normalized/messages.jsonl` zurück.

2. **Stufe 2 — Original nachlesen.** `ArchivSuche.original(chat_kennung, ordinal, kontext=1)`
   liefert den **unveränderten Originaltext** der Fundstelle **plus Kontextfenster** (je eine
   Nachricht davor und danach, einstellbar 0–10). Das Original wird **gelesen, nie verändert
   und nie zusammengefasst** — der Rückgabewert trägt `unveraendert: true`, der Text wird
   Zeichen für Zeichen durchgereicht (kein `strip()`, keine Kürzung). Zur Sicherheit ist das
   im Test `test_original_liefert_unveraenderten_text_mit_kontext` Zeichen für Zeichen
   nachgeprüft.

Stufe 1 sagt **wo**, Stufe 2 sagt **was**. Die Kurzfassung im Treffer (`text`, max. 400
Zeichen) ist nur für die Anzeige da und ausdrücklich als `ausschnitt` erkennbar — die Wahrheit
steht im Original.

---

## §5 Nie erfinden: unsicher heißt Rückfrage an Sebastian

Jedes Suchergebnis trägt `sicher: true|false`, einen maschinenlesbaren `grund`, eine
`begruendung` im Klartext und — bei Unsicherheit — eine **fertige `rueckfrage`** an Sebastian.
Bei `sicher: false` liefert der Dienst **keinen behaupteten Inhalt** (es gibt bewusst kein
Feld `antwort`), sondern die gefundenen **Kandidaten mit Zeigern** plus die Rückfrage.

**Sebastians Regel, wörtlich umgesetzt:** *„Wenn der Agent nicht sicher ist … dann möchte ich
das als Rückfrage nach meiner menschlichen Erinnerung gefragt werden."* Seine Erinnerung ist
die Wahrheitsquelle, das Archiv die Stütze.

**Schwellwerte — als Zahlen, damit es nachprüfbar ist** (Konstanten in `archiv_suche.py`):

| Größe | Wert | Bedeutung |
|---|---|---|
| `AEHNLICH_STARK` | **0,45** | Ab dieser Kosinus-Ähnlichkeit gilt ein Vektor-Treffer als belastbar. |
| `AEHNLICH_SCHWACH` | **0,30** | Darunter zählt er gar nicht mehr als Treffer. Dazwischen: schwacher Anklang. |
| `WETTBEWERB_ABSTAND` | **0,03** | Zwei belastbare Vektor-Treffer aus **verschiedenen** Gesprächen, deren Ähnlichkeit weniger als das auseinanderliegt, konkurrieren gleich stark → widersprüchlich. |

**Urteilsregeln:**

| Fall | `grund` | `sicher` |
|---|---|---|
| Kein Treffer (weder Wortlaut noch Bedeutung) | `keine_treffer` | false — plus Rückfrage, plus **durchsuchter Zeitraum** und Umfang |
| Nur Treffer zwischen 0,30 und 0,45, kein starker | `nur_schwache_aehnlichkeit` | false — plus Rückfrage, plus beste Ähnlichkeit als Zahl |
| Zwei etwa gleich starke Vektor-Treffer aus verschiedenen Gesprächen | `widerspruechliche_fundstellen` | false — plus Rückfrage |
| Sonst (mindestens ein starker Treffer, kein Gleichstand) | `eindeutig` | **true** |
| Index nicht erreichbar | `kein_index` | false — plus Rückfrage, nichts wird behauptet |

Die Ehrlichkeit ist im Ergebnis **selbst beschrieben**: `begruendung` nennt die Zahl
(„beste Ähnlichkeit 0,38, belastbar erst ab 0,45"), `durchsucht` nennt `chunks`/`gespraeche`/
`nachrichten`, `zeitraum` nennt von/bis. Keine Treffer heißt: *„im Archiv nichts gefunden,
Zeitraum X…Y durchsucht"* — nicht ein leeres Schweigen.

---

## §6 Zeitachse und Bewusstsein

Neuer Router `backend/app/router/archiv_wissen.py` (eigene Datei, damit sie nicht mit
`router/archiv.py` oder `router/chat.py` kollidiert):

| Endpunkt | Zweck |
|---|---|
| `GET /api/archiv/wissen/statistik` | Anzahl Gespräche/Nachrichten/Chunks/Vektoren je Quelle, Zeitraum, Zählung je Jahr, **Themen-Häufigkeit aus den Gesprächsttiteln** (keine Deutung) |
| `GET /api/archiv/wissen/chronik?richtung=alt\|neu&limit=N` | die ältesten/neuesten Gespräche mit **Datum + Quelle + Thema + Zeiger** |
| `GET /api/archiv/wissen/frage?q=…&modus=hybrid\|volltext\|vektor` | Hybridsuche, **zeitlich sortiert**, mit `sicher`/`grund`/`rueckfrage` |
| `GET /api/archiv/wissen/original?chat_kennung=…&ordinal=…&kontext=1` | **Original nachlesen**, unverändert, mit Kontextfenster |
| `GET /api/archiv/wissen/ueberblick` | der Bewusstseins-Baustein (§6.1) als JSON |

### §6.1 Der Bewusstseins-Baustein („was mein Agent weiß")

`archiv_suche.prompt_baustein()` (bzw. `archiv_suche.ueberblick()["text"]`) liefert einen
kompakten deutschen Text mit **Kennzahlen statt Inhalten**:

> WISSENSSPEICHER (persönliches Chat-Archiv): N Gespräche, M Nachrichten, Zeitraum von…bis.
> Quellen: … Häufige Themen: … NUTZUNG: Bei Fragen nach früheren Gesprächen … ZUERST hier
> suchen … NICHT im Web. Das Web weiss nichts über dieses Archiv. Ist die Suche unsicher
> (sicher=false), frage Sebastian nach seiner Erinnerung, statt eine Antwort zu behaupten.

Dazu maschinenlesbar `regeln` (`zuerst_archiv`, `dann_original`, `nie_erfinden`,
`nichts_nach_aussen`) und `schwellwerte` (dieselben Zahlen wie §5).

**Einbauort (verbindlich; EINGEBAUT am 25.09.2026):** `backend/app/services/llm_service.py`,
Methode `LlmService._build_messages`. Der Baustein steht **immer** im Prompt, direkt nach
der Fokus-Anweisung:

```python
system_prompt = self.load_system_prompt()
system_prompt += KONTEXT_FOKUS_ANWEISUNG
system_prompt += self._build_wissensspeicher_baustein()   # <- hier (llm_service.py:596)
```

`_build_wissensspeicher_baustein` (llm_service.py:537) holt den Text über
`archiv_suche.prompt_baustein(kurz=True)`; schlägt das fehl, steht statt eines stillen
Weglassens der Not-Baustein `WISSENSSPEICHER_AUSFALL` (llm_service.py:118) im Prompt.

**Kompakte Fassung (das steht im Prompt):** `ArchivSuche.ueberblick_kurz()`
(archiv_suche.py:1133) über `prompt_baustein(kurz=True)` (archiv_suche.py:1304). Ziel und
Grenze: **≤ 600 Zeichen**, ausschließlich Metadaten — Zahlen, Quellen, Zeitraum,
Nutzungsregel; **keine** Inhalte, keine Titel, keine Kennungen. Gemessen am echten Index:
**506 Zeichen** mit Schlüssel, **558 Zeichen** ohne (dann steht zusätzlich „Bedeutungssuche
aus: kein Schlüssel — nur Wortlaut." darin). Die Vektormatrix wird dafür **nicht** geladen
(auf dem Handy 95 MB) — nur die Schlüssel-Frage wird geprüft.

Die **ausführliche** Fassung (`ueberblick()`, 911 Zeichen, mit Themen-Häufigkeit) bleibt
unverändert und wird weiterhin vom Endpunkt `/api/archiv/wissen/ueberblick` geliefert.

**Warum genau dort** und nicht bei den Treffern: Der vorhandene `_build_archiv_context`
(Z. 529) hängt nur die **Treffer** an — die entstehen erst, wenn schon gesucht wurde. Der
Agent muss aber **auch ohne Suche** wissen, dass er ein Archiv hat. Sonst beantwortet er
„was habe ich damals besprochen" mit der Web-Suche, und genau das war Sebastians Befund.

**Reihenfolge im System-Prompt (gegen Doppelung abgesichert):** Fokus-Anweisung →
**Wissensspeicher-Baustein** (Bewusstsein, ohne Treffer) → Zusammenfassung → Gedächtnis →
**Archiv-Fundstellen** (zur aktuellen Frage). Der Baustein trägt nur Metadaten, die
Treffer-Injektion nur Fundstellen; Tests zählen `WISSENSSPEICHER` genau einmal im Prompt
(`tests/test_archiv_verdrahtung.py`).

---

## §7 Aufs Handy übertragen

Der Index ist **eine Datei**. Nach dem Bauen liegt er im Archivordner (der per `.gitignore`
aus dem Repo ausgeschlossen ist — bewusst *nicht* im Projektordner, sonst könnte eine 200-MB-
Datei mit den vollständigen Gesprächen versehentlich mitcommittet werden):

```
…/Chats von GPT, GEMINI, Claude/db/archiv_index.db
```

**Übertragung per USB (`adb`, Kabel):**

```bash
# auf dem PC, aus dem Workspace-Ordner:
adb push "Chats von GPT, GEMINI, Claude/db/archiv_index.db" /sdcard/Download/archiv_index.db
```

```bash
# auf dem Handy (Termux) — in den Termux-Heimordner, damit die App ihn ohne
# Android-Speicherrechte lesen kann:
mv /sdcard/Download/archiv_index.db /data/data/com.termux/files/home/archiv_index.db
```

**Der Dienst findet ihn ohne weitere Einstellung** — er sucht in dieser Reihenfolge:
`settings.archiv_index_path` (falls im Projekt gesetzt) → `$ARCHIV_INDEX_PATH` →
`personal_ai_agent/archiv_index.db` → `personal_ai_agent/backend/archiv_index.db` →
`Chats von GPT, GEMINI, Claude/db/archiv_index.db` → `/sdcard/Download/archiv_index.db` →
`/data/data/com.termux/files/home/archiv_index.db`.

Auf dem Server muss zusätzlich der **Einbettungs-Schlüssel** verfügbar sein
(`OPENROUTER_API_KEY`), sonst läuft nur der Volltext (§3, ehrlicher Rückfall).

**Größe:** siehe §8. Neu bauen kann man den Index jederzeit mit:

```bash
cd backend
.venv/Scripts/python -m scripts.archiv_index_bauen --mit-vektoren
```

---

## §8 Probe am echten Archiv (Zahlen)

Gefahren am 25.09.2026 gegen den echten Index
(`Chats von GPT, GEMINI, Claude/db/archiv_index.db`). Ausgegeben wurden **nur** Zahlen,
Datumsangaben, Quellen und Themen-Stichworte — keine Inhalte, keine Zitate, keine Namen
Dritter.

### §8.1 Der Index selbst

| Größe | Wert |
|---|---|
| Nachrichten | **40.627** |
| Fundstellen (Chunks) | **30.891** |
| Gespräche | **1.109** |
| Vektoren | 30.891 × 1536 (float16) |
| Zeitraum | 1940-09-04 … 2026-12-28 |
| Modell | `openai/text-embedding-3-small` |
| Token geschätzt / **gezählt** | 8.956.277 / **9.613.866** |
| **Kosten** | **0,192277 $** (0,02 $/1 Mio Token) |
| Baudauer / **Dateigröße** | 509,8 s (8,5 min) / **239,7 MB** |
| Quelldatei aufgelöst | **1.109 von 1.109 Gesprächen**, 30.891 von 30.891 Chunks |

### §8.2 Je Quelle

| Quelle | Gespräche | Nachrichten | von … bis | Quelldatei(en) |
|---|---|---|---|---|
| chatgpt | 109 | 19.057 | 2022-12-26 … 2026-08-02 | `raw/chatgpt/conversations-000.json` (100), `-001.json` (9) |
| claude-code | 40 | 13.328 | 2026-05-29 … 2026-08-11 | je Session eine `*.jsonl` |
| gemini | 384 | 4.734 | 2024-10-20 … 2026-08-12 | `…takeout-…-3-001.zip::…/Gemini-Apps/MeineAktivitäten.html` |
| claude-ai | 162 | 3.058 | 2025-11-01 … 2026-08-04 | `raw/claude-ai/conversations.json` |
| google-kalender | 399 | 405 | 1940-09-04 … 2026-12-28 | `…takeout-…-3-001.zip::Takeout/Kalender/…ics` |
| google-notizen | 15 | 15 | 2020-09-20 … 2025-11-23 | je Notiz die eigene Datei im Takeout |

Gegenprobe zur Genauigkeit der Zeiger: Bei den 15 Google-Notizen stimmt die Gesprächskennung
mit dem Dateinamen der Quelldatei überein — 15 verschiedene Dateien, 15 Kennungen, alle
paarweise zugeordnet.

### §8.3 Die drei ältesten Gespräche

| Datum | Quelle | Thema (Stichwort) |
|---|---|---|
| 1940-09-04 | google-kalender | Geburtstagseintrag aus dem Familienkreis |
| 1965-08-16 | google-kalender | Geburtstagseintrag aus dem Familienkreis |
| 1968-04-19 | google-kalender | Geburtstagseintrag aus dem Familienkreis |

(Das sind Kalendereinträge — Personen werden hier bewusst **nicht** genannt. Die drei ältesten
Einträge sind Geburtstage, keine Gespräche.)

**Älteste echte Chats:** der erste überhaupt ist vom **2022-12-26** (chatgpt). Der
Chat-Bestand beginnt also mit einem Schlagabtausch zu einem tagesaktuellen Weltgeschehen-Thema,
danach folgen Ende 2022 Gespräche zu Technik/Cybersecurity, Kochen und Sprachgebrauch. Die
Quellen beginnen in dieser Reihenfolge: chatgpt 2022-12-26 · gemini 2024-10-20 ·
claude-ai 2025-11-01 · claude-code 2026-05-29.

### §8.4 Eine echte Frage

Frage (Sebastians Original): **„Was habe ich zu Beginn der Aufzeichnungen mit ChatGPT
besprochen?"**

| Weg | Treffer | Urteil | Bemerkung |
|---|---|---|---|
| Volltext | 5 | `sicher: true` | findet nur spätere Treffer (2025+) — Wortsuche greift bei Rückblicksfragen daneben |
| Vektor | 5 | `sicher: false`, `widerspruechliche_fundstellen` | ähnlichste Stelle 0,75; fünf Fundstellen liegen dicht beieinander |
| Hybrid | 5 | `sicher: false`, `widerspruechliche_fundstellen` | beide Wege zusammen |

**Ergebnis:** Für diese Frage liefert die Suche **keine** fertige Antwort, sondern **eine
Rückfrage** — genau wie von Sebastian gewünscht (§5). Der inhaltliche Weg für solche
Rückblicksfragen ist die **Chronik** (§6): Sie zeigt den Anfang der Aufzeichnungen mit Datum
und Thema, und von dort geht es über den Zeiger ins Original. Genau das sagt der
Bewusstseins-Baustein jetzt auch (§6.1).

### §8.5 Ehrliche Grenzen (aus derselben Probe)

* **Absolute Schwellen auf großem Bestand:** Für eine sinnfreie Anfrage lag die beste
  Ähnlichkeit bei **0,3962** — über `AEHNLICH_SCHWACH` (0,30). Auf 30.891 Chunks ist
  „keine_treffer" deshalb **selten**. Die Unsicherheitsregeln greifen trotzdem: Der Fall endete
  als `nur_schwache_aehnlichkeit` **mit Rückfrage**, nicht als Behauptung.
* **Vorher/Nachher, belegt:** Die Anfrage `xyzzy plugh foobar qwertz zxcvb` lieferte vor der
  Nachschärfung `sicher: true` (`eindeutig`) — nach der Begriffszählung aus §3
  `sicher: false` (`nur_schwache_aehnlichkeit`) mit Rückfrage. Der Leerlauf-Fall ist damit
  wirklich ehrlich.
* **Rückblicksfragen ≠ Suchfragen:** „Was war am Anfang" ist eine Meta-Frage über das Archiv.
  Kein Ähnlichkeitsmaß beantwortet sie zuverlässig — die Chronik tut es.
* **Themen-Häufigkeit** ist eine Wortzählung über die Gesprächst*itel* (Kandidaten u. a.
  „konzert", „tour", „yoga", „hamburg", „frisör"). Bewusst keine Modell-Deutung, und bewusst
  kein Anspruch auf Vollständigkeit.

---

## §9 Offene Punkte

1. **Verdrahtung durch den Haupt-Agenten** (bewusst nicht in dieser Arbeit gemacht, weil
   `router/chat.py` und `frontend/app.js` parallelen Strängen gehören):
   * `archiv_wissen.router` in `backend/app/main.py` einhängen (zwei Zeilen, siehe Kopf der
     Router-Datei).
   * Bewusstseins-Baustein in `llm_service._build_messages` einhängen (§6.1).
   * **`backend/.env` anlegen** bzw. `OPENROUTER_API_KEY` dorthin übernehmen. Ohne das bleibt
     die semantische Suche aus und `archiv_service` findet die alte Datenbank weiterhin nicht.
   * Entscheiden, ob `archiv_index_path` als echtes Setting in `app/config.py` aufgenommen
     wird (der Dienst liest es schon per `getattr`, ein Nachtragen genügt).
2. **Alte Vektordatei** `db/memory.vektoren.f32` (Mistral, 1024 Dimensionen) ist mit dem neuen
   OpenRouter-Index unbrauchbar. Sie wurde **nicht gelöscht** (Entscheidung Sebastians, keine
   echten Daten werden überschrieben).
3. **WhatsApp** liegt als Rohdaten vor (`raw/whatsapp/`, 2 Dateien) und ist im Bestand
   **nicht** enthalten (`memory.db` kennt keine WhatsApp-Quelle). Ob es hinein soll, ist eine
   eigene Entscheidung Sebastians — der Indexbau könnte es aufnehmen, sobald der Bestand es
   enthält.
4. **Google-Fotos** (Takeout) sind bewusst nicht Teil des Textindex.
5. **Themen-Häufigkeit** ist eine Wortzählung über die Gesprächst*itel* — bewusst keine
   Deutung durch ein Modell.

---

## §10 Datenschutz

* Alle Archivdateien wurden **nur lesend** geöffnet (`mode=ro`); keine echte Datei wurde
  geändert oder gelöscht.
* Nach außen geht beim **Bauen** der Chunk-Text (Einbettung, einmalig) und beim **Suchen** nur
  die Suchfrage. Archivinhalte verlassen das Gerät sonst nicht.
* Der Index liegt im gitignorierten Archivordner. Er enthält die vollständigen Gespräche und
  gehört **nicht** ins Repo.
* In Tests, Doku und Berichten stehen nur Zahlen und Strukturen — keine Inhalte.
