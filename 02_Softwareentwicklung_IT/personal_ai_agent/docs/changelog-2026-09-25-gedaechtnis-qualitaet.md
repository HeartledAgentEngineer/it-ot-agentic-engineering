# Changelog: Gedächtnis-Qualität — Korrekturen, Relevanz, Zeitbezug

**Projekt:** `personal_ai_agent` (02_Softwareentwicklung_IT) · **Datum:** 25.09.2026
**Auslöser:** Sebastians Entscheidungen vom 25.09.2026 (vier Punkte, unten zitierter
Abschnitt in `docs/konzept-gedaechtnis.md`) und sein Zeit-Bezug-Wunsch: *„Es gibt Fakten,
die sich nie ändern … es gibt Termine … es gibt veränderliche Details … und ich will
verstehen, wie mein Agent sich etwas merkt."*
**Umfang:** NUR Backend (`backend/app/**`, `backend/tests/**`, `backend/.env.example`) + diese
Doku. **`frontend/app.js` wurde von dieser Arbeit nicht angefasst** (ein paralleler Strang
arbeitet dort; die Datei wurde innerhalb derselben Stunde von jenem Strang geändert).
**Grundlage (belegt):** die Diagnose `docs/konzept-gedaechtnis.md` (§1 Ist-Zustand, §2 Schwächen).

**Prüfbefehl (Stand dieses Dokuments, frisch ausgeführt):**

```
cd backend && .venv/Scripts/python -m pytest tests/ -q      →  304 passed, 3 warnings, Exit 0
```

Baseline vor dieser Arbeit: **272 passed** (Exit 0, gleicher Befehl). Gesunken ist nichts;
**+32 Tests** (25 in `test_gedaechtnis_qualitaet.py`, 7 in `test_gedaechtnis_erklaeren.py`).

**Keine echten Erinnerungsinhalte angefasst.** Alle Tests laufen in `tmp_path`; der echte
Speicher (`chroma_data/memory_store.json` bzw. der Handy-Bestand) wurde nur gelesen, nie
geschrieben, gelöscht oder überschrieben. Es gab **keine** Migration gegen echte Daten —
die Migration existiert als Route mit Trockenlauf und muss von Sebastian/Backend ausgelöst
werden (siehe §4).

---

## 1. Ursachen (belegt am alten Code, mit Datei:Zeile)

### 1.1 Korrekturen wurden still verworfen (Kern-Fehler)

| Stelle (alter Stand) | Was dort stand | Wirkung |
|---|---|---|
| `app/services/memory_service.py:49` | `AEHNLICHKEIT_SCHWELLE = 0.90` | Zeichen-Ähnlichkeit (difflib) entschied über „schon bekannt" |
| `memory_service.py:98-104` | `_ist_wiederholung(a, b)` → `ratio() >= 0.90` | **ein einziger Wert** über der Schwelle galt als derselbe Fakt |
| `memory_service.py:155-165` | `_finde_wiederholung(content)` → ID des ähnlichsten Eintrags | lieferte den alten Eintrag |
| `memory_service.py:125-128` | `store_memory()`: `vorhanden = ...` → **`return vorhanden`** | die **neue** Fassung wurde nicht gespeichert |

Gemessen mit genau der Funktion aus dem alten Dienst
(`SequenceMatcher(None, _normalisiert(a), _normalisiert(b)).ratio()`).

**(A) Die Paare, die die Tests benutzen** (exakt diese Zeichenketten, frisch nachgemessen):

| Paar | Ähnlichkeit | Folge im alten Code |
|---|---|---|
| „Ich arbeite seit **zehn** Jahren in der Automatisierung." vs. „… seit **elf** Jahren …" | **0,950** | Korrektur **verworfen**, alte Fassung blieb aktiv |
| „Ich habe einen Hund namens **Rex**." vs. „… namens **Max**." | **0,933** | dito |
| „Testfakt: Geburtstag am **3.** Mai **1984**." vs. „… am **5.** Mai **1985**." | **0,939** | dito |

**(B) Weitere Paare aus der Diagnose** (§2.5 in `konzept-gedaechtnis.md`), hier unabhängig
nachgerechnet — die Zahlen der Diagnose stimmen:

| Paar | Ähnlichkeit | Regel heute | Regel vorher |
|---|---|---|---|
| „Der Nutzer trinkt morgens **Kaffee**." vs. „… **Tee**." | 0,918 | Korrektur | verworfen |
| „Meine Schwester heißt **Anna**." vs. „… **Maria**." | 0,906 | Korrektur | verworfen |
| „Geburtstag: **3.** Mai **1984**" vs. „Geburtstag: **5.** Mai **1985**" | 0,905 | Korrektur | verworfen |
| „Mein Lieblingsessen ist **Pizza**." vs. „… **Pasta**." | 0,897 | **keine** Regel greift → zwei Einträge (unverändert) | blieb gespeichert |

Der Test `test_memory_api.py::test_gleicher_anfang_gilt_schon_als_wiederholung` hielt diesen
Ist-Zustand fest. Er ist jetzt zu
`test_gleicher_anfang_ist_jetzt_eine_korrektur` umgestellt (Name + Erwartung), damit die
belegte Ursache nicht in Vergessenheit gerät.

### 1.2 Der ganze Bestand wanderte in jede Frage

| Stelle | Was dort stand | Wirkung |
|---|---|---|
| `memory_service.py:54` | `ALLES_MITGEBEN_BIS = 300` | Grenze, ab der überhaupt ausgewählt wurde |
| `memory_service.py:226-227` | `if anzahl <= ALLES_MITGEBEN_BIS: return get_all_memories(...)` | bei 175 Einträgen (Handy-Bestand) ging der **komplette** Bestand in den Prompt |
| `memory_service.py:51-54` (Kommentar) | „… bei heutigen Kontextfenstern belanglos" | `top_k` war wirkungslos; der Bezug zur Frage fehlte |

Nachgemessen an der Diagnose: ~11.000 Zeichen ≈ 2.500 Token **je Frage**, unabhängig vom
Thema. Der Test, der das festhielt
(`test_kleiner_speicher_wandert_vollstaendig_in_den_prompt`), heißt jetzt
`test_top_k_wirkt_auch_bei_kleinem_speicher`.

### 1.3 `category` und `importance` waren tote Felder

| Stelle | Was dort stand | Wirkung |
|---|---|---|
| `memory_service.py:262-269` | `store_memory(content=fact, category="fact", importance=3)` | jeder Eintrag fest `fact` + `3` |
| `app/models.py:97-98` | Muster `^(fact|preference|context|project)$`, `importance` 1–5 | vier Kategorien und vier von fünf Stufen wurden nie erzeugt |
| `chroma_client.py:66,107` | Feld nur durchgereicht | `importance` wurde **nirgends gelesen** |

Im echten Altbestand (Sicherung 13.08.2026, 70 Einträge): Kategorien **nur `fact`**,
`importance` **nur 3**.

### 1.4 Kein Zeitbezug, keine Erklärung, keine Einbettung ohne Schlüssel

- **Kein Datumsfeld.** Ein Eintrag war ein freier String (`chroma_client.py:62-72`) — ein
  Termin konnte nach dem Termin nicht „zurücktreten" und war auch nicht als Termin erkennbar.
- **Kein Weg zu erklären.** `app/router/memory.py` hatte Liste (`:16`), Anlegen (`:38`),
  Zähler (`:54`), Vektoren (`:64`), Wiederholungen (`:78`), Löschen (`:98`, `:115`) — aber
  nichts, was „was weißt du über X?" beantwortet.
- **Einbettungen fehlten auf beiden Geräten.** `memory_service.py:22-32` lud
  `sentence-transformers` in einem `try/except` (nicht installiert);
  `mistral_vektor()` (`:57-88`) brauchte `MISTRAL_API_KEY`. Ohne beides blieb
  `embedding = null` und die Auswahl fiel auf „die neuesten" zurück.

---

## 2. Neue Regeln (mit Ort im neuen Code)

### 2.1 Korrektur ersetzt — nichts wird gelöscht

- `memory_service.py:220-247` `_tragende_unterschiede()`: vergleicht die **Wörter**, die sich
  unterscheiden (difflib-Opcodes auf Token-Ebene). Unterschiede nur in Füllwörtern zählen
  nicht; Namen, Zahlen, Daten, Orte zählen.
- `memory_service.py:241-250` `_ist_doppelung()` — wortgleich bzw. nur Füllwörter verschieden.
- `memory_service.py:253-266` `_ist_korrektur()` — über der Schwelle **und** ein tragendes
  Wort anders ⇒ derselbe Gegenstand, neue Aussage.
- `memory_service.py:505-558` `store_memory()`:
  echte Doppelung → nichts angelegt (ID des vorhandenen Eintrags zurück, wie bisher);
  Korrektur → `_loese_ab()`.
- `memory_service.py:582-641` `_loese_ab()`: die **neue** Fassung wird aktiv (Inhalt, Art,
  Datum, Wichtigkeit, Zeitstempel, neuer Vektor), die **alte** wandert in
  `history` mit `{inhalt, abgeloest_am, geschrieben_am, art}` — Inhalt, Zeitpunkt der
  Ablösung, der ursprüngliche Schreibzeitpunkt der alten Fassung und ihre Art.
  Der Eintrag behält seine ID; es wird nichts
  gelöscht, auch nicht bei mehrfachen Korrekturen (`history` wächst).
- `chroma_client.py:169-187` `aktualisiere_memory()` — setzt nur die übergebenen Felder.
- `memory_service.py:637-682` `entferne_wiederholungen()` nutzt jetzt `_ist_doppelung()`:
  eine Korrektur ist **keine** Doppelung und wird vom Aufräumen nicht angefasst.

### 2.2 Relevanz statt Vollbestand

- `memory_service.py:168-206` `openrouter_vektor()`: Einbettung über OpenRouter
  (`POST {base}/embeddings`, Modell aus `settings.openrouter_embed_model`,
  Standard `openai/text-embedding-3-small`). **Mistral entfällt**, das lokale Modell entfällt.
- `config.py:90-100` neue Einstellung `openrouter_embed_model`; die alte
  `embedding_model`-Einstellung ist entfernt (sie hatte nur diesen einen Nutzer).
- `memory_service.py:684-773` `retrieve_relevant_memories(query, top_k=8)` — **immer** Auswahl:
  - Vektoren vorhanden → Kosinus-Ähnlichkeit (`chroma_client.py:94-130` `vektor_score()`,
    überspringt Vektoren anderer Länge, statt sie falsch zu rechnen).
  - keine Vektoren/welche ohne Vektor → Wortgleichheit (`memory_service.py:469-486`).
  - **kein** Worttreffer und keine Vektoren → „die neuesten" als sichtbarer Notbehelf.
  - `MEMORY_TOP_K = 8` (`:91`) ist der Standard; die Chat-Wege rufen weiter mit
    `top_k=5`/`top_k=3` auf (`chat.py:345`, `chat.py:977`, `chat.py:1785` — dort nichts geändert).
- `llm_service.py:289` `MEMORY_BLOCK_MAX_ZEICHEN = 1200` und `llm_service.py:327-368`
  `_build_memory_context()`: harte Zeichengrenze für den Prompt-Block; was nicht passt, wird
  gezählt („N weitere Erinnerung(en) ausgelassen"). Die Eintragszeilen halten die Grenze ein,
  nur die eine Schlusszeile darf sie um bis zu ~90 Zeichen überschreiten (sonst wäre das
  Weglassen unsichtbar).
- **Ehrlichkeit im Prompt:** jeder zurückgegebene Eintrag trägt `such_modus`
  (`vektor`/`wort`/`neuheit`) und `such_hinweis`. Ohne Vektoren steht der Hinweis
  („keine Vektoren verfügbar – ausgewählt über Wortgleichheit, nicht über Bedeutung") als
  erste Zeile im Block (`llm_service.py:347-357`).

### 2.3 Zeitbezug (Termine, Fakten, Zustände)

- **Drei Arten** (`memory_service.py:103-119`): `fakt` (unveränderlich), `termin` (mit Datum),
  `zustand` (veränderlich). Alte Werte werden abgebildet
  (`fact`→`fakt`, `preference`/`context`/`project`→`zustand`, `ereignis`→`termin`).
- **Erkennung** (`memory_service.py:335-361` `erkenne_art()`, Reihenfolge = erste Regel gewinnt):
  1. wiederkehrendes Datum („Geburtstag", „jährlich") → `termin`, ohne Enddatum
     (`wiederkehrend: True`; ein Geburtstag darf nie „abgelaufen" sein)
  2. Datum im Text → `termin` mit `ereignis_datum`
  3. veränderliche Formulierung („mag", „Lieblings…", „aktuell", „arbeitet an", „plant" …)
     → `zustand`
  4. sonst → `fakt`
  Das ist bewusst eine **feste Regel, kein Modellaufruf**: Sie muss bei jedem Speichern laufen
  (auch auf dem Handy), und ein Fehlurteil kostet nur die Reihenfolge, keine Daten.
- **Datumsformen** (`memory_service.py:278-316` `_erkenne_datum()`): `2026-11-02`,
  `02.11.2026` (auch `2.11.26`), `2. November 2026`. Ohne Jahreszahl gilt das **nächste**
  Vorkommen („am 2. November" im September → 2026-11-02; „am 3. Januar" im September → 2027-01-03).
  Unmögliche Daten (32.13.2026) liefern `None` — es wird nichts erfunden.
- **Verhalten in der Auswahl** (`memory_service.py:403-427` `_termin_wert()`):
  Termin in ≤ 14 Tagen `+0,30`, ≤ 60 Tage `+0,15`, später `+0,05`, wiederkehrend `+0,05`;
  **vergangener Termin: kein Zuschlag und Lage `vergangen`** → fällt aus dem Prompt, außer die
  Frage zielt auf die Vergangenheit (`memory_service.py:459-467` `_fragt_nach_vergangenheit()`:
  „war/waren/damals/früher/…" oder eine Jahreszahl).
- **Sichtbar im Prompt** (`llm_service.py:300-325` `_erinnerung_zeile()`):
  `- … (Fakt)`, `- … (Termin am 2026-11-02)`, `- … (Termin war am 2026-05-12 – VERGANGEN,
  nur Historie)`, `- … (Zustand, veränderlich)`, `- … (Termin, wiederkehrend)`.
- **`importance` wird jetzt gelesen**: Termine werden als wichtig 4 angelegt, sonst 3;
  in der Rangfolge zählt jede Stufe über 3 mit `+0,05` (`memory_service.py:97`).
- **Sanftes Vergessen** (`memory_service.py:444-457` `_alter_abzug()`): ab 90 Tagen Alter je
  angefangene 30 Tage `−0,01`, gedeckelt bei `−0,10`. Das verschiebt **nur die Reihenfolge** —
  gelöscht oder ausgeblendet wird nichts.

### 2.4 Transparenz: „Was weißt du über X?" (nur lesen)

- `memory_service.py:934-1021` `erklaere_begriff(begriff)` — Wortsuche im Wortlaut **und** in
  den abgelösten Fassungen (`_passt()`, `:488-497`; Teilwort-Treffer: „Zahnarzt" findet
  „Zahnarzttermin").
- Neue Route `GET /api/memory/erklaeren?begriff=…&top_k=…` (`router/memory.py:148-172`).
  Antwort je Treffer: `inhalt`, `aktiv` (true/false), `art` + `art_text`, `zeitbezug`
  (`lage`, `datum`, `tage_bis`), `wichtig`, `seit`, `historie` (Liste der abgelösten Fassungen);
  abgelöste Fassungen erscheinen zusätzlich als eigener Treffer mit
  `aktiv: false`, `historie_von`, `abgeloest_am`. Kopf der Antwort: `anzahl`, `aktiv`,
  `historie`, `suchweise`, `hinweis`.
- **Kein LLM, kein Netzaufruf, keine Änderung am Bestand** — belegt durch
  `test_gedaechtnis_erklaeren.py::test_erklaeren_ohne_netz_und_ohne_llm` (httpx-Aufruf wird
  aufgezeichnet; die Liste bleibt leer) und `::test_erklaeren_aendert_nichts_am_bestand`
  (Bestand vorher/nachher Zeichen für Zeichen gleich).

### 2.5 Migration alten Bestands (Route, Trockenlauf)

- `memory_service.py:862-931` `migriere_bestand(nur_zeigen=True)` und
  `POST /api/memory/migration?ausfuehren=false|true` (`router/memory.py:125-146`).
- Was ergänzt wird: `fact`→`fakt`; `preference`/`context`/`project`→`zustand`; danach
  **einmalig** die inhaltliche Erkennung (Datum → `termin` + `ereignis_datum`, wiederkehrendes
  Datum → `termin`, veränderliche Formulierung → `zustand`); fehlende/kaputte `importance` → 3;
  fehlendes `history`-Feld → `[]`.
- **Garantien:** Inhalt bleibt Zeichen für Zeichen gleich, Anzahl der Einträge ändert sich
  nicht, IDs bleiben, nichts wird gelöscht, Standard ist der Trockenlauf, der zweite Lauf ist
  ein No-Op (idempotent). Getestet mit Vorher/Nachher-Vergleich
  (`test_migration_ergaenzt_art_ohne_inhalt_zu_verlieren`,
  `test_migration_fuellt_fehlende_felder_ohne_zu_loeschen`).
- **Wichtig:** Die Migration ist **noch nicht** gegen Sebastians echten Bestand gelaufen.
  Sie ist von Hand auszulösen (Handy: `git pull`, dann Trockenlauf ansehen, dann ausführen).

---

## 3. Geänderte und neue Dateien

| Datei | Art | Was |
|---|---|---|
| `backend/app/services/memory_service.py` | **umgeschrieben** | Korrektur-Regel, OpenRouter-Einbettung, Auswahl mit `top_k`, Arten/Zeitbezug, Migration, `erklaere_begriff` |
| `backend/app/db/chroma_client.py` | geändert | `add_memory(..., history, ereignis_datum, wiederkehrend)`, `vektor_score()`, `aktualisiere_memory()`, `search_memories()` mit Längen-Schutz |
| `backend/app/services/llm_service.py` | geändert | `_build_memory_context()` mit Zeichengrenze + `_erinnerung_zeile()` (Art/Zeitbezug/VERGANGEN) |
| `backend/app/router/memory.py` | geändert | Liste liefert Art/Zeitbezug/Verlauf; `POST /migration`; `GET /erklaeren` |
| `backend/app/models.py` | geändert | `MemoryItem` (+`art`, `art_text`, `ereignis_datum`, `wiederkehrend`, `history`), `MemoryHistoryEintrag` (`inhalt`, `abgeloest_am`, `geschrieben_am`, `art`), `MemoryCreate` (Art/`importance` optional = „keine Angabe") |
| `backend/app/config.py` | geändert | `openrouter_embed_model` (Mistral-/Lokal-Modell-Einstellung entfällt) |
| `backend/.env.example` | geändert | `EMBEDDING_MODEL` → `OPENROUTER_EMBED_MODEL`; Hinweis, dass `MISTRAL_API_KEY` nur noch für das Archiv gebraucht wird |
| `backend/tests/test_gedaechtnis_qualitaet.py` | **neu** | 25 Tests: Korrekturen (a–c), Doppelung (d), `top_k` + Zeichengrenze (e), vergangener Termin (f), nahender Termin (g), Migration (h), kein automatisches Löschen (i), sanftes Vergessen, Einbettung ohne Schlüssel, Vektor-Längen |
| `backend/tests/test_gedaechtnis_erklaeren.py` | **neu** | 7 Tests: Struktur, Historie, Teilwort, „kein Treffer = keine Erfindung", nur lesen, kein Netz/LLM, Route registriert |
| `backend/tests/test_memory_api.py` | geändert | Fixture ersetzt `openrouter_vektor`; zwei Tests auf die neuen Regeln umgestellt (siehe §1.1/§1.2) |

**Nicht angefasst:** `frontend/**` (auch nicht `app.js`), `backend/app/router/chat.py`,
`backend/app/router/auftraege.py`, `backend/app/services/chat_verlauf.py`, der echte
Erinnerungsbestand.

---

## 4. Bewusst NICHT gebaut

- **Kein Löschen, nirgends automatisch.** Die Wege, die Einträge entfernen, bleiben die
  beiden von Hand ausgelösten: `DELETE /api/memory/{memory_id}` (ein Eintrag) und
  `DELETE /api/memory/clear` (alle) sowie `POST /api/memory/wiederholungen` mit
  `ausfuehren=true` (Trockenlauf als Standard) — und der fasst nur **echte Doppelungen** an.
  Geprüft: `test_loeschen_kommt_nirgends_automatisch_vor` liest den Quelltext von
  `store_memory`, `_loese_ab`, `retrieve_relevant_memories`, `extract_and_store_memories`,
  `migriere_bestand`, `erklaere_begriff` und verlangt, dass darin **kein** Aufruf von
  `delete_memory`/`clear_all`/`clear_memories` steht — plus Verhaltensprüfung.
- **Keine LLM-gestützte Art-Bestimmung.** Das Extraktionsmodell liefert weiterhin nur Sätze
  (`llm_service.py:741-821`, inhaltlich unverändert); die Art erkennt der Dienst deterministisch.
  Begründung: nachprüfbar, kostenlos, auch auf dem Handy.
- **Kein Bedeutungs-Treffer im Erklären-Endpunkt.** Er arbeitet offline über Wortgleichheit.
  Begründung: „nur lesen, kein LLM" — und nutzbar, wenn kein Schlüssel da ist.
- **Keine Anzeige der neuen Felder im Blatt.** `frontend/app.js` gehört dem parallelen Strang
  (siehe §6, offener Punkt).

---

## 5. Echte Testausgaben (in dieser Sitzung ausgeführt)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
    →  304 passed, 3 warnings, Exit 0        (letzte Messung: in 37.03s)

Neu bzw. betroffen, einzeln:
  tests/test_gedaechtnis_qualitaet.py     →  25 passed
  tests/test_gedaechtnis_erklaeren.py     →   7 passed
  tests/test_memory_api.py                →  10 passed

Baseline vorher (gleicher Befehl): 272 passed (Exit 0)
```

Zusätzlich geprüft (Reste der alten Wege müssen weg sein):

```
grep -rn "ALLES_MITGEBEN_BIS\|mistral_vektor\|_embeddings_available\|sentence_transformers\|embedding_model" app/ tests/
  → Treffer NUR noch in Kommentaren/Docstrings (Beschreibung des alten Verhaltens)
    und in .pyc-Cache-Dateien; kein ausführbarer Code mehr.
./.venv/Scripts/python -c "from app.config import settings; print(settings.openrouter_embed_model); print(hasattr(settings,'embedding_model'))"
  → openai/text-embedding-3-small | False      (die alte Einstellung existiert nicht mehr)
```

Arbeitsnachweis am laufenden Code (außerhalb des Repos, Speicher in einem Temp-Ordner,
`openrouter_vektor` ohne Netz ersetzt) — Ausschnitte der echten Ausgabe:

```
1) KORREKTUREN (vorher stillschweigend verworfen)
- aktiv: Ich arbeite seit elf Jahren in der Automatisierung.
    Verlauf (2026-09-25T08:53:42): Ich arbeite seit zehn Jahren in der Automatisierung.
- aktiv: Ich habe einen Hund namens Max.
    Verlauf (…): Ich habe einen Hund namens Rex.
- aktiv: Testfakt: Geburtstag am 5. Mai 1985.
    Verlauf (…): Testfakt: Geburtstag am 3. Mai 1984.
Einträge im Speicher: 3 (drei Korrekturen, kein Datenverlust)

2) Prompt-Block bei 'War ich 2026 beim Zahnarzt?' (Historie-Frage):
## GEMERKTE INFORMATIONEN AUS FRÜHEREN GESPRÄCHEN:
- (Suche: keine Vektoren verfügbar – ausgewählt über Wortgleichheit, nicht über Bedeutung)
- Zahnarzttermin mit Zahnreinigung am 12.05.2026. (Termin war am 2026-05-12 – VERGANGEN, nur Historie)
- Zahnarzttermin mit Zahnreinigung am 2. November. (Termin am 2026-11-02)
- Testfakt: Geburtstag am 5. Mai 1985. (Termin, wiederkehrend)
- Oma Helga ist meine Oma. (Fakt)
   (bei 'Was steht diese Woche an?' fehlt der vergangene Termin – er ist nicht mehr „aktuell")

3) ERKLAEREN: begriff=Zahnarzt anzahl=2 aktiv=2 historie=0
- [Termin] aktiv=True zeitbezug={'lage': 'kommend', 'datum': '2026-11-02', 'tage_bis': 38}
- [Termin] aktiv=True zeitbezug={'lage': 'vergangen', 'datum': '2026-05-12', 'tage_bis': -136}

4) RELEVANZ + GRENZE (60 inhaltlich verschiedene Einträge)
top_k=8  -> 8 Eintraege im Prompt, Block 551 Zeichen (Grenze 1200)
top_k=60 -> 60 ausgewaehlt, Block 1262 Zeichen   (vorher ging IMMER der ganze Bestand hinein)

5) MIGRATION eines Altbestands (category='fact'/'preference')
Trockenlauf: vorher=3 nachher=3 geaendert=3 (nur_gezeigt=True)
Nach der Migration: gleiche Anzahl=3 | Inhalte unveraendert=True
- fakt     datum=None       :: Oma Helga ist meine Oma.
- zustand  datum=None       :: Ich mag Tee statt Kaffee.
- termin   datum=2026-11-02 :: Zahnarzttermin mit Zahnreinigung am 2. November 2026.
```

---

## 6. Grenzen und offene Punkte (ehrlich)

1. **Die Art-Erkennung ist eine Wortliste, kein Verstehen.** Sie erkennt Datumsformen und
   veränderliche Formulierungen; „mein Auto ist ein Golf" wird `fakt`, obwohl es sich ändern
   kann. Folge: kein Beinbruch (Reihenfolge), aber die Trefferquote ist nicht gemessen.
2. **Einträge, die sich nur in Zahlen unterscheiden, gelten als Korrektur.** Nachgemessen
   (Arbeitsnachweis außerhalb des Repos, 60 nummerierte Einträge „Notiz ueber Thema i mit
   eigenen Woertern i*i"): es bleiben **4 aktive Einträge** mit Verlaufslängen 47, 5, 2, 2 —
   also 4 + 56 = 60, **kein Inhalt verloren**, aber die Serie steht nicht mehr nebeneinander.
   Genau so gewollt für „neue Fassung gilt" (`seit zehn/elf Jahren`), beobachtbar als
   Nebenwirkung bei nummerierten Serien.
3. **Zwei verschiedene Formulierungen derselben Sache bleiben zwei Einträge.** Für
   „Mein Lieblingsessen ist Pizza." / „Mein Lieblingsessen ist Pasta." (Ähnlichkeit 0,897,
   nachgemessen) greift keine Regel. Dedup über *Bedeutung* bräuchte
   Vektoren im Schreibpfad — die Einbettung ist da, der Vergleich über Embeddings aber noch
   nicht gebaut. (Aufwand klein, separater Schritt.)
4. **Wiederkehrende Termine haben kein Tagesdatum.** `wiederkehrend: True` verhindert nur das
   „Ablaufen"; „Geburtstag ist in 6 Tagen" kann der Agent noch nicht sagen. Dafür müsste
   Tag/Monat gespeichert und beim Ranking berücksichtigt werden.
5. **`history` wächst unbegrenzt** (so gewollt: nichts löschen). Bei vielen Korrekturen
   wächst der Eintrag; eine kompakte Darstellung (nur die letzten n Fassungen anzeigen) fehlt.
6. **Die Migration ist noch nicht gelaufen** (siehe §2.5). Bis dahin verhalten sich Alteinträge
   zwar schon richtig (die Art wird beim Lesen aus dem Inhalt abgeleitet,
   `memory_service.py:381-401`), aber sie tragen die Felder noch nicht gespeichert.
7. **Vektoren fehlen weiterhin im Bestand, solange niemand `POST /api/memory/vektoren` auslöst.**
   Ohne Vektoren läuft die Suche über Wortgleichheit (sichtbar im Prompt). Mit gesetztem
   OpenRouter-Schlüssel funktioniert der Knopf jetzt ohne Mistral — Auslösen ist Sebastians
   Entscheidung (kostet einen Aufruf je Eintrag, ~0,02 $/1 Mio Token).
8. **Frontend zeigt die neuen Arten als Rohtext.** `frontend/app.js:8109` kennt nur
   `fact/preference/context/project` und fällt sonst auf den Rohwert zurück — es erscheint
   „fakt"/„termin"/„zustand" (klein). Der Backend-Endpunkt listet dafür jetzt `art_text`
   („Fakt"/„Termin"/„Zustand") und `ereignis_datum`/`wiederkehrend`/`history`; die Anzeige
   braucht eine Zeile in `app.js` — die Datei gehört dem parallelen Strang und wurde hier
   **nicht** angefasst.
9. **`CLAUDE.md:31,42` behaupten „Embeddings werden lokal berechnet (sentence-transformers)".**
   Das war schon vorher falsch (nichts installiert) und ist seit dieser Entscheidung auch
   nicht mehr die Absicht. Die Datei wird aus `CLAUDE_EXTENDS.md` erzeugt (`sync-rules.ps1`) —
   Änderung dort, nicht in der generierten Datei. Hier bewusst nicht gemacht, weil der
   Sync-Lauf Dateien außerhalb dieses Projekts neu erzeugt.
10. **`docs/embeddings-auf-termux.md` und `specification.md` nennen alte Zeilennummern** des
    Gedächtnis-Codes bzw. „Embeddings lokal". Historische Dokumente; nur der Hinweis hier.
11. **`chat.py` ruft weiter mit `top_k=5` (Chat) und `top_k=3` (Hermes-Delegation)**. Das ist
    wirkungsvoll (nicht mehr der Bestand) und wurde absichtlich nicht angefasst — die Datei
    arbeitet in einem parallelen Strang. Der Standard des Dienstes ist 8.
12. **Eine vorhandene `.env` kann noch `EMBEDDING_MODEL=…` enthalten.** Das ist harmlos
    (unbekannte Variablen werden ignoriert, `config.py:extra = "ignore"`), sollte aber beim
    nächsten Bearbeiten der `.env` entfernt werden — die Einstellung existiert nicht mehr.
    Die Vorlage `backend/.env.example` ist bereits nachgezogen.
