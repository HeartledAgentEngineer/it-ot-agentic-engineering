# Feinauftrag N27 Schritt 1 — Ereignis-Knoten je Anlass (Verknuepfungsschicht)

**Datum:** 28.09.2026 · **Planer:** Hauptagent · **Ausfuehrer:** Hermes-Subagent
(`deepseek-v4.1-flash`) · **Pruefer:** `openai/gpt-5.6-luna` (andere Modellfamilie)

## Warum dieser Schritt

Der Nutzer hat am 28.09. die **Verknuepfungsschicht** beauftragt: thematisch
zwischen Chats, Bildern und Menschen verbinden, damit man "ueber alles mit dem
reden kann". N27 zerlegt das in fuenf Schritte; **Schritt 1 ist der
Ereignis-Knoten**: je Anlass ein Datensatz mit Datum, Thema/Kategorie, Anzahl
Dateien und den Datei-Kennungen — **ohne** Personen, ausschliesslich aus dem,
was schon da ist (`sortierplan.json` aus N7). Erst danach kommen
Chat-Andockung (2), Kalender (3), Personen (4) und die Ableitung "wer war mit
wem wo" (5).

Der Schritt ist bewusst **rein lokal**: kein Netz, kein pCloud, kein Bild, kein
LLM. Er legt nur das Datenfundament.

## Eingefrorene Schnittstelle (bindend)

Datei: `tools/foto_sortierung/ereignisse_bauen.py` (Nachbarmodul von
`foto_dateien.py`; deren Konventionen gelten: `REPO`-Konstante,
`_pruefe_ziel_ausserhalb_repo`, atomares Schreiben, `--trocken` als Standard).

**Eingabe (nur lesend):** `~/foto_sortierung/sortierplan.json` (N7-Plan,
`stand: 2026-09-27T13:49:46`). Genutzt werden genau die Schluessel
`anlaesse` (Liste) und `zuege` (Liste) sowie `stand`. Unbekannte Schluessel
werden ignoriert.

**Ausgabe:** `~/foto_sortierung/ereignisse.jsonl` — **JSONL**, je Zeile genau
ein Ereignis-Knoten, kodiert mit `ensure_ascii=True` (ASCII, keine Umlaute) und
`sort_keys=True`:

```json
{"anlass_id": "2014-03-30_Beispiel-01", "anzahl_dateien": 1,
 "art": "ereignis", "datei_kennungen": [12345678901],
 "datum": "2014-03-30", "event": "2014-03-30 Beispielthema",
 "event_quelle": "neu", "event_stufe": null, "jahr": 2014,
 "kategorie": "Beispielkategorie", "kennung": "E-2014-03-30_Beispiel-01",
 "quellen": {"datum": "sortierplan.json:anlaesse",
             "dateien": "sortierplan.json:zuege",
             "ziel_ordner": "sortierplan.json:zuege"},
 "stand": "<ISO-Zeit des Laufs>", "thema": "Beispielthema",
 "ziel_ordner": "Agent/Fotos/2014/Beispielkategorie/2014-03-30 Beispielthema"}
```

Regeln zur Ausgabe:

1. `kennung` = `"E-" + anlass_id`; `anlass_id` ist `thema_quelle` aus dem Plan
   (im Bestand eindeutig, erfundenes Beispiel: `2014-03-30_Beispiel-01`).
   Damit ist die Kennung **stabil** und haengt nicht an der Reihenfolge.
2. Sortierung **fest**: nach `datum` aufsteigend, bei Gleichstand `anlass_id`
   aufsteigend. Der Inhalt ist damit reproduzierbar (bei vorgegebenem `stand`
   auch byte-gleich; zu verschiedenen Zeitpunkten unterscheiden sich zwei
   Läufe ausschließlich im Feld `stand`).
3. `datei_kennungen`: die `fileid` der Zuege dieses Anlasses, als ganze Zahlen,
   aufsteigend sortiert; Zuege ohne brauchbare Kennung werden gezaehlt
   (`zahlen.zuege_ohne_kennung`), nicht aufgenommen.
4. `ziel_ordner` = `ziel_pfad` der Zuege des Anlasses (im Bestand fuer alle
   Zuege eines Anlasses gleich); fehlt er, `"ziel_pfad": null`-Fall ehrlich als
   `ziel_ordner: null` ausgeben.
5. Vor jeder Zeile steht die Kopfzeile **nicht** als Sonderfall — die Datei ist
   reine JSONL. Ein `zahlen`-Block gehoert **nicht** in die Datei (er wird auf
   der Konsole berichtet und im Rueckgabewert gefuehrt).

**Rueckgabe von `ereignisse_bauen(plan, *, stand=None) -> dict`:**

```python
{"art": "ereignisse", "version": 1, "stand": "<ISO>",
 "plan_stand": "<ISO>|null",
 "zahlen": {"anlaesse", "dateien", "zuege", "zuege_ohne_anlass",
            "zuege_ohne_kennung", "ohne_datum", "ohne_thema",
            "kollisionen", "events_wiederverwendet", "event_quellen",
            "kategorien", "jahre", "themen"},
 "ereignisse": [...]}
```

**Zaehlregeln (Invarianten, im Code als Zusicherung + Test):**

* `zahlen.anlaesse == len(ereignisse)`
* `zahlen.dateien == sum(k["anzahl_dateien"])`
* `zahlen.dateien + zahlen.zuege_ohne_anlass + zahlen.zuege_ohne_kennung == zahlen.zuege`
  (jede Zug-Zeile ist genau einmal zugeordnet — keine Zeile verschwindet
  unbemerkt)
* `ohne_datum` zaehlt Anlaesse ohne lesbares `datum` (sie werden **trotzdem**
  als Knoten gefuehrt, mit `datum: null`, damit nichts verloren geht)
* `kollisionen` wird aus den Anlässen gezählt (`kollision`).
* `events_wiederverwendet` zählt jeden Anlass, dessen `event_quelle`
  **nicht** `"neu"` ist — im echten Plan der Wert `"vorschlag"` (Event-Name
  kommt aus einem vorhandenen Ordner, N6e). Die **volle** Verteilung steht
  zusätzlich in `zahlen.event_quellen`.
  **Korrektur 28.09. (Planer):** dieser Auftrag nannte zuerst den Wert
  `"ordner"` — den gibt es im echten Plan nicht. Am echten Plan gemessen:
  **2.088 × `neu`, 39 × `vorschlag`**. Der Ausführer hatte den Auftrag
  wortgetreu umgesetzt (Zähler also 0); die Zählregel wurde deshalb vom
  Planer auf „jeder Wert außer `neu`" geändert und der Zähler
  `event_quellen` ergänzt — damit wird kein Wert stillschweigend verbucht.

**Funktionsnamen (eingefroren, damit die Tests und spaetere Schritte sie
benutzen koennen):**

```python
plan_laden(pfad: str) -> dict
ereignisse_bauen(plan: dict, *, stand: str | None = None) -> dict
ereignisse_schreiben(pfad: str, daten: dict) -> str          # atomar, JSONL
knoten_zeile(knoten: dict) -> str                            # reine Funktion
zahlen_text(daten: dict) -> str                              # Konsolenbericht
_pruefe_ziel_ausserhalb_repo(pfad: str) -> str
haupt(argv=None) -> int
```

**Kommandozeile:** `--plan` (Standard `~/foto_sortierung/sortierplan.json`),
`--ausgabe` (Standard `~/foto_sortierung/ereignisse.jsonl`), `--trocken`
(Standard, schreibt nichts), `--schreiben` (schreibt atomar), `--limit N`
(zeigt nur die ersten N Knoten auf der Konsole).

## Was das Werkzeug NICHT tut (verbindlich, mit Test belegt)

* **Kein Netz**: kein `pcloud`, kein `httpx`/`requests`, kein LLM — Quelltext-
  Suchtest.
* **Keine Bilder**: keine Bilddatei geoeffnet, kopiert oder gespeichert.
* **Kein Loeschen**: keine Loeschfunktion, kein `shutil.rmtree`, kein
  `os.remove` ausser der **eigenen** temp-Datei beim atomaren Schreiben.
  (Vorbild `foto_dateien.py`; der Quelltext-Suchtest prueft das.)
* **Kein Schreiben ohne `--schreiben`**, und **kein** Ziel im Repo
  (`_pruefe_ziel_ausserhalb_repo` → deutsche Meldung auf `stderr`, **Exit 2**).
* Ausgaben und Dateien tragen **keine Schluesselwerte**.

## Tests (offline, Pflicht)

`backend/tests/test_ereignisse_bauen.py` — alles offline, `tmp_path`,
**kein** Netz, **keine** echte Datei, **keine** echten Orts-/Personennamen
(erfundene Beispieldaten wie `Beispielort`, `Beispielthema`).

Abzudecken (mindestens 45 Pruefungen):

1. Zaehl-Invarianten (alle vier oben) an einem erfundenen Plan.
2. `kennung`/`anlass_id` stabil; zweiter Aufruf ergibt **denselben** Text
   (Idempotenz auf `daten`-Ebene).
3. Sortierung fest (datum, dann anlass_id) — auch bei gleichem Datum.
4. Anlass ohne Datum: Knoten entsteht, `datum: null`, `ohne_datum` zaehlt.
5. Zug ohne `fileid` → `zuege_ohne_kennung`, nicht aufgenommen.
6. Zug mit unbekannter `thema_quelle` → `zuege_ohne_anlass`.
7. `ziel_ordner` aus den Zuegen; `null`-Fall ehrlich.
8. `--trocken` schreibt **nichts** (Datei existiert danach nicht) — Beleg ueber
   `haupt([...])`.
9. `--schreiben` in `tmp_path` schreibt JSONL, Zeilenzahl == Anlaesse, jede
   Zeile mit `json.loads` lesbar, ASCII (`ensure_ascii`), `sort_keys`.
10. Ziel **im Repo** → Exit 2, nichts geschrieben, deutsche Meldung.
11. Quelltext-Suchtest: keine Netz-/Loeschfunktion im Modul.
12. `knoten_zeile` ist rein (kein Dateizugriff): gleiche Eingabe, gleiche
    Ausgabe.
13. `zahlen_text` nennt alle Zahlen und **nicht** "geloescht" o. Ae.

## Pruefkriterium des Schritts (Pruefbefehl + Live)

1. `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **Exit 0**
   (Baseline vor dem Schritt: **2070 passed**).
2. Live-Trockenlauf gegen den **echten** Plan: erwartet **2.127 Ereignisse**
   und **7.616 Datei-Kennungen**, `zuege_ohne_anlass 0`, `zuege_ohne_kennung 0`,
   `ohne_datum 0` — Zahl wird am echten Plan gemessen, nicht behauptet.
3. `--schreiben` in einen **frischen** Ordner ausserhalb des Repos; zweiter
   Lauf mit demselben Ziel → der Inhalt ist **inhaltlich identisch**.
   **Praezisiert (28.09., am echten Lauf gemessen):** zwei Läufe zu
   verschiedenen Zeitpunkten unterscheiden sich **ausschließlich** im Feld
   `stand` (Lauf-Zeitstempel in jeder Zeile); ohne `stand` sind die Dateien
   byte-gleich (`sha256`-Auszug `cfbbe6f68961b142` über beide Läufe). Die
   Zusage „byte-gleich" gilt nur bei **vorgegebenem** `stand` — so wie die
   Tests ihn setzen. Das ursprüngliche Kriterium war zu absolut formuliert.
4. Ziel im Repo → **Exit 2**.

## Grenzen (unveraendert)

Nur lesen und anlegen; **nichts loeschen**; pCloud wird **nicht** beruehrt
(kein Aufruf); Bilder bleiben, wo sie sind (kein Download); Biometrie und
Kennungen bleiben lokal; Ausgaben ausserhalb des Repos; Dateien ASCII.
Fremde, unfertige Dateien im Arbeitsbaum (`tools/whatsapp/`,
`backend/scripts/whatsapp_db_import.py`, `backend/scripts/archiv_index_ergaenzen.py`,
`README.md`, `CLAUDE.md`, `docs/experimente/*`) werden **nicht** angefasst.
