# Ortsfragen im Antwortweg — gemessen statt geraten (14.10.2026, Nachtlauf)

**Anlass:** Plan `2026-10-10_personen-orte-erzaehlungen.md`, Abschnitt 1: „Orte wirken nicht:
‚Österreich-Urlaub' wird nicht erkannt, stattdessen eine statistische Aufzählung." Der Plan stellt
dort drei Prüffragen. Dieses Dokument beantwortet sie **mit Code-Belegen (Datei:Zeile) und
gemessenen Zahlen** — es ändert **nichts** am Verhalten. Kein Bild geöffnet, kein Modell aufgerufen,
kein Netz, keine Kosten.

## Die drei Fragen des Plans, je mit Beleg

### 1. „Kennt der Antwortweg `orte.jsonl` / `bild_orte.csv` überhaupt?"

**Geteiltes Ergebnis — eine der beiden Dateien kennt er, die andere nicht:**

| Datei | Inhalt | Wird vom Antwortweg gelesen? |
|---|---|---|
| `bild_orte.csv` | OSM: `ort_osm`, `landmarke`, `landmarke_art`, `adresse`, `abstand_m` | **Ja** — `backend/app/services/erzaehl_service.py:528–595` (`BILD_ORTE_DATEINAME`, `_bild_orte_lesen`), benutzt in `bilder_info()` (`:610`) |
| `orte.jsonl` | GeoNames: `land`, `land_code`, `region`, `ort`, `aufnahme` | **Nein** — 0 Treffer in `backend/app/**`; einziger Leser ist das PC-Werkzeug `tools/foto_sortierung/anlass_namen.py:99` |

Bestätigung aus zweiter, unabhängiger Quelle: der Nachweis (`bestand_pruefen.py`) führt
`orte.jsonl` selbst unter **„Übergeben, aber von keinem Dienst gelesen (4)"**.

**Der harte Punkt:** `bild_orte.csv` trägt **keine Landesspalte**. Gemessene Kopfzeile (25.178
Zeilen, eine je Bild):

```
fileid,aufnahme,adresse,hausnummer,ort_osm,landmarke,landmarke_art,hinweise,abstand_m
```

Und `_bild_orte_lesen()` übernimmt genau drei Felder: `landmarke`, `art`, `ort_osm`
(`erzaehl_service.py:588–594`). Damit hat der Antwortweg **kein Land und keine Region** — nur
Ortsnamen, Landmarken und Adressen. Die einzige Datei mit der Ortsangabe, die Sebastian benutzt
(„Österreich", „Korfu"), ist die, die niemand liest.

### 2. „Warum fehlten Österreich und Korfu? Sind sie in `orte.jsonl`?"

**Ja, beide sind drin — gemessen, nur anders benannt als in der Frage.**

`orte.jsonl`: **9.259 Zeilen**, jede mit Region, 9.257 mit Aufnahmedatum. Länder (Code: Bilder):

| Code | Bilder | | Code | Bilder |
|---|---|---|---|---|
| DE | 6.854 | | DK | 147 |
| GR | 830 | | FR | 146 |
| AT | 412 | | IT | 73 |
| EG | 351 | | LU | 15 |
| HR | 221 | | AL | 11 |
| ES | 177 | | TR | 6 |
| (CZ 5, CH 5, BE 4, US 2) | | | | |

Regionen: **AT: Tyrol 409, Upper Austria 2, Salzburg 1**; **GR: Ionian Islands 799, Crete 31**.

**Der eigentliche Grund für „Korfu fehlt":** der Name kommt in keiner Ortsdatei vor. Die häufigsten
Orte der GR-Bilder sind *Agios Georgis* (278), *Kontokali* (216), *Acharavi* (163), *Kerkyra* (114)
— **0 Bilder mit „Korfu" im Ortsnamen**. Die Insel steckt als **englische GeoNames-Region
„Ionian Islands"** (799 Bilder) in der Datei, nicht als „Korfu". Dasselbe Muster bei Österreich:
„Österreich" heißt dort `AT` / *Tyrol*.

**Doppelt belegt:** Dieselbe Ursache zeigt sich in der Übersicht, die der Chat heute benutzt
(`fotos_uebersicht.json`: 2.098 Events, 2.168 Titel) — **kein einziger Titel enthält „österreich",
„korfu", „griechenland" oder „ägypten"**; 107 Titel enthalten das Suchwort „urlaub".

### 3. „Gibt es einen Weg ‚Urlaub = Ort + zusammenhängender Zeitraum'?"

**Nein — es gibt nur Einzelanlässe, keine Reise-Stufe.**

- Die Anlässe entstehen durch Bündelung mit Zeitlücke:
  `tools/foto_sortierung/ereignisse_ordner_bauen.py:360` (`anlaesse_bilden(..., luecke_stunden)`,
  neuer Anlass nach der Pause) → 2.268 bzw. 2.098 Anlässe, **kein Elternteil, keine Reise**.
- Der Chat beantwortet „Urlaube 2021" über eine **enge Auslöseregel**:
  `backend/app/router/chat.py:1323` (`_fotos_uebersicht_tool`) verlangt **ein Foto-Wort** *und*
  **ein Frage-/Listen-Wort** (`:1341–1351`) und filtert dann nach Jahreszahl und dem Suchwort
  „urlaub"/„konzert" (`:1352–1361`) — die Quelle ist `fotos_uebersicht.json`
  (`services/foto_uebersicht.py`). Es ist eine **Zähl-/Listenschicht über Anlass-Titeln**, keine
  Ortsauswertung.
- Eine Frage wie „erzähl mir vom Österreich-Urlaub" enthält **kein** Listen-Wort und **keine**
  Jahreszahl → das Werkzeug **feuert nicht**; „Österreich" steht in keiner gelesenen Datei. Was
  übrig bleibt, ist genau das, was Sebastian gesehen hat: eine statistische Aufzählung ohne Ort.
- Die große Ausnahme mit Ortsbezug ist der Beziehungsweg
  (`services/beziehungen_service.py`, `beziehungen.jsonl`, „wer war mit wem wo") — der hängt an
  **Datum**, nicht an Land oder Region.

Die Vermutung des Plans („es fehlt die Stufe Reise/Urlaub zwischen Einzelanlass und Person") ist
damit **belegt**, und es kommt ein zweiter, ebenso wichtiger Befund dazu: **die Ortsangabe fehlt
dem Antwortweg als Datenquelle ganz**, nicht nur als Stufe.

## Was das für den nächsten Schritt heißt (Vorschlag, nicht gebaut)

Zwei Dinge, beide klein, beide **ohne** einen neuen bezahlten Lauf:

1. **Die Ortsangabe erreichbar machen:** `orte.jsonl` (land/land_code/region/ort je Bildkennung)
   als **lesende** Quelle in den Antwortweg geben — dieselbe Machart wie `bild_orte.csv` heute
   (`erzaehl_service`), keine Koordinaten, keine Hausnummern.
2. **Wortschatz überbrücken:** der Nutzer sagt „Korfu"/„Österreich", die Daten sagen „Ionian
   Islands"/„Tyrol"/`AT`. Ohne eine kleine Zuordnung (oder eine Suche über Region **und** Land)
   bleibt die Lücke auch mit Quelle bestehen.
3. Die Stufe **Reise** (mehrere Anlässe am selben Ort über zusammenhängende Tage) bleibt der
   größere Baustein des Plans. Erst nach Sebastians Entscheidung — er entscheidet über Umfang und
   ob zuerst die Werkzeuge aus Paket 4 kommen.

**Nichts davon ist in diesem Lauf umgesetzt** — der Plan sieht dafür die Planrunde vor, und ein
Eingriff in den Antwortweg ist eine Verhaltensänderung, keine Nachtarbeit.

## Grenzen dieses Schritts (ehrlich)

- **Nur gelesen und gemessen:** `orte.jsonl` (nur Kopfzeilen geparst), `bild_orte.csv` (nur
  Kopfzeile + Spaltenwerte gezählt), `fotos_uebersicht.json` (nur Zahlen und Wort-Treffer in
  Titeln), Code-Suche im Repo. **Keine Bildinhalte, keine Personennamen, keine Koordinaten, keine
  Adressen** in diesem Dokument.
- Keine Code-Änderung, kein Commit an fremden Pfaden, kein Push fremder Arbeit.
- `bestand_pruefen.py` samt Testdatei liegt weiterhin **fremd und halbfertig** im Arbeitsbaum
  (Arbeit des Master-Chats) — die Prüfzeile „Vektor-Gesichter gegen Zuordnungszeilen" bleibt
  deshalb blockiert und wurde **nicht** angefasst.
- Die Zahlen gelten für den Stand der **PC-Kopien**; die maßgebliche Fassung liegt am Gerät.
- Ob Sebastian genau diese Antwort gesehen hat, ist am PC nicht nachstellbar (sein Verlauf liegt am
  Handy) — belegt ist der Mechanismus, nicht der einzelne Satz.

**Prüfbefehl dieses Laufs** (frisch, vollständig, unabhängig vom Doku-Commit):
`cd backend && .venv/Scripts/python.exe -m pytest tests/ -q` → **4130 passed, 2 skipped, 3
warnings, Exit 0** (542,44 s).
