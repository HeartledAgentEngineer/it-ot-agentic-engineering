# N6e — Event-Abgleich (Vorschlag statt Neubau)

> **Stand:** 27.09.2026 · **Nachtlauf-Schritt N6e**, **Runde 2** (Planer: Hauptagent,
> Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, Prüfer: `openai/gpt-5.6-luna`)
> **Auftrag:** `docs/auftrag-n6e-event-abgleich.md` · **Vorgänger:** N6d
> (`docs/changelog-2026-09-27-zielkategorien.md`)
>
> **Runde 2** korrigiert drei Befunde aus der Prüfung: (1) die in den Dateien
> stehenden **echten Ordnernamen** (der Prüfer nannte vier, tatsächlich waren es
> **acht** Namen aus Sebastians Ablage) sind durch erfundene Platzhalter ersetzt,
> (2) die Zahl „109 von 113“ ist auf **112** richtiggestellt (Herleitung unten),
> (3) die **Vorschlagsregel ist verschärft**: nur `tag`/`monat` ergeben einen
> Vorschlag, `jahr`/`spanne` sind nur noch ein **schwacher Hinweis** (erst mit
> `--auch-schwach` ein Vorschlag, dann `sicher: false`). Alle Zahlen unten sind
> **nach** diesen Korrekturen neu gemessen.

## Das Problem, das N6e löst

Nach N6d steht fest, **wohin** sortiert wird: `Agent/Fotos/<Jahr>/<Kategorie>/<Event>`.
Der Event-Name kam bisher aus dem Datums-Block (`2025-01-06_Anlass-01`). Sebastian
hat in seiner eigenen Ablage aber **schon** Event-Ordner, teils seit 2013. Ein
Sortieren auf neue Datums-Namen würde seinen Bestand **verdoppeln** statt ergänzen.

Ziel ist deshalb **vorschlagen, nicht neu bauen**: Findet sich für einen
Datums-Block ein bestehender Event-Ordner derselben Kategorie, wird dieser als
Ziel vorgeschlagen — nur wenn es keinen gibt, entsteht ein neuer Name.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/event_abgleich.py` (1.060 Zeilen) | Ordnernamen in Datums-Belege zerlegen, Kandidaten einer Kategorie finden, Vorschlag + Begründung, Trefferquote, Vorschlagsliste schreiben |
| `backend/tests/test_event_abgleich.py` (893 Zeilen) | **51 Prüfungen**, alles ohne Netz, alle Ausgaben nach `tmp_path` |

Öffentliche Schnittstelle: `ordner_datum_lesen`, `datum_stufe`, `kandidaten`,
`vorschlag_fuer(anlass, unterordner, auch_schwach=False)`,
`hinweis_text(anlass, unterordner, auch_schwach=False)`,
`trefferquote(anlaesse, kategorien, zuordnung=None, auch_schwach=False)`,
`vorschlaege_schreiben`, `anlaesse_laden`, `unterordner_von`,
`kategorie_fuer_anlass`, `vorschlaege_bauen`, `bestand_und_zuordnung`,
`anlass_teile`, `anlass_datum`, `anlass_thema`, `STUFEN`, `SICHERE_STUFEN`,
`STUFEN_VORSCHLAG`, `STUFEN_SCHWACH`, `EventFehler`, `KategorienFehler`, `main`.

Das Werkzeug ist ein **Nachbarmodul** von `foto_kategorien.py`: es lädt es über das
vorhandene `_modul_aus_pfad`-Muster und übernimmt `pfad_saeubern`,
`kategorien_laden`, `zuordnung_laden`, `bucket_fuer_thema`, `ziel_kategorie`,
`_pruefe_ziel_ausserhalb_repo` und `_schreibe_atomar` — keine zweite Wahrheit
für Namensbereinigung, Bestand oder Repo-Schutz.

## Die Muster, die der Parser kennt

| Muster | Musterform (erfundene Platzhalter) |
|---|---|
| `Jahr Ort` | `2013 <Ausflugsziel>`, `2020 <Stadt>` |
| `Jahr_Monat[_Tag] Ereignis` | `2018_11_25 <Band>`, `2019_08 <Festival>`, `2018_3 <Party>` |
| `Jahr Person` | `2017 <Vorname>`, `2020+ <Vorname>` |
| Jahresspanne | `2015-2018 …`, `2013_2014 …` |
| offenes Ende | `2019+ …`, `2020+ …` |
| Jahr als Suffix | `Beispiel_2019` |
| Punkt-Datum, auch zweistellig | `… 10.10.21`, `… 10.10.2021` |
| Monatsliste | `2021_08 & 10 …` (nur die angedockte Zahl ist ein Monat) |
| Jahr doppelt im Namen | `2019_2019 …` → **ein** Jahr, aber Spanne |
| ohne jedes Jahr | `<Vorname>`, `<Bandname>`, `Spielkonsole` |

**Fehltreffer-Regel (Test):** eine blanke Zahl 1–12 gilt nur als Monat, wenn sie
**direkt an ein Jahr anschließt** (Trennzeichen `_`, `-` oder `.`). `Spiel A 2`,
`Spiel B 3`, `9.Klasse`, `108` sind **keine** Monate; eine Zahl > 12 ist keiner.
Jahre sind nur vierstellige Zahlen 1900–2100 (`1899`, `2101`, `108` sind keine).

## Die fünf Stufen (`datum_stufe`, absteigend)

| Stufe | Beleg | Vorschlag (Standard) | mit `--auch-schwach` |
|---|---|---|---|
| `tag` | Tag **und** Monat **und** Jahr gleich | ja, `sicher: true` | ja, `sicher: true` |
| `monat` | Monat **und** Jahr gleich | ja, `sicher: true` | ja, `sicher: true` |
| `jahr` | Anlass-Jahr steht im Namen | **nein** — nur schwacher Hinweis | ja, `sicher: false` |
| `spanne` | Jahr liegt in einer Spanne / ab einem offenen Jahr | **nein** — nur schwacher Hinweis | ja, `sicher: false` |
| `ohne_jahr` | kein Jahres-Bezug | **nein** (harte Regel) | **nein** (harte Regel) |

**Harte Regeln (verschärft in Runde 2):**

1. `ohne_jahr` reicht **nie** für einen Vorschlag — ein Ordner ohne Jahr würde
   sonst jeden Anlass dieser Kategorie schlucken.
2. **Nur `tag` und `monat` ergeben einen Vorschlag** (`STUFEN_VORSCHLAG`). Ein
   bloß gleiches Jahr ist **kein** Vorschlag: die Sichtprobe des Planers zeigte,
   dass damit in einer Kategorie mit mehreren Ordnern desselben Jahres reihenweise
   unpassende Ziele entstünden — das ist ein falscher Beleg, kein schwacher.
3. `jahr` und `spanne` werden weiter **gezählt und als Hinweis genannt**
   (`schwacher_hinweis`, siehe `trefferquote`), aber erst mit `auch_schwach=True`
   (CLI: `--auch-schwach`) zum Vorschlag — dann `sicher: false`.

Fehlende Teile am Anlass zählen **nie** als Treffer (ohne Tag/Monat am Anlass gibt
es keine Stufe `tag`/`monat`). `trefferquote` nennt **Vorschlag (tag/monat)** und
**schwachen Hinweis (jahr/spanne)** in getrennten Zeilen — die schwachen Stufen
stehen **nicht** in der Vorschlagszahl.

## Entscheidungen (statt Fragen)

Der Auftrag ließ drei Randfälle offen; sie sind hier festgelegt, im Code
dokumentiert und getestet:

1. **Monat im Namen weicht ab, Jahr passt** → Stufe `jahr` (der Jahres-Beleg
   stimmt), die Abweichung steht in der Begründung. `jahr` ist **kein** Vorschlag,
   sondern ein schwacher Hinweis (erst mit `--auch-schwach` ein unsicherer Vorschlag).
2. **Fremdes Jahr** (weder genannt noch in einer Spanne) → `ohne_jahr`, also kein
   Vorschlag. Eine Stufe außerhalb der fünf genannten wurde **nicht** erfunden.
3. **Zweistelliges Jahr im Punkt-Datum** (`… 10.10.21`) → als `20xx` gelesen und
   in den Jahre-Listen geführt; sonst wäre das Punkt-Datum ohne Jahr.
4. **Sortierung** ist Stufe → Wortüberlappung (absteigend) → alphabetisch, also
   deterministisch; zwei Läufe sortieren gleich (Test).
5. **`kandidaten` liefert alle** Unterordner der Ziel-Kategorie (auch `ohne_jahr`)
   — `vorschlag_fuer` siebt aus: `ohne_jahr` immer, `jahr`/`spanne` ohne
   `auch_schwach`.
6. **Anlass ohne Thema** ergibt im Hinweistext `Ohne-Thema` statt eines Abbruchs
   (Auflage aus N7).
7. **Vorschlagsliste** wird nur bei echter Änderung geschrieben (Vergleich ohne
   das Feld `stand`) — der zweite Lauf lässt die Datei byte-identisch.

## Zahlen (selbst gefahren, nicht behauptet)

> Alle Zahlen sind **nach** den Korrekturen der Runde 2 neu gemessen. Die
> Runde-1-Angaben „639 Anlässe mit Vorschlag (29,9 %)“ und „109 von 113“ sind
> **ersetzt**, nicht ergänzt: der Wert **639** gilt jetzt nur noch **mit
> `--auch-schwach`**, die strenge Vorschlagszahl ist **39**; die Erreichbarkeit
> ist **112** (nicht 109).

* **Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **760 passed, 3 warnings, Exit 0** (74,0 s im letzten Lauf).
  Baseline vor N6e: **709** (N6d) → **+51** eigene Prüfungen (45 aus Runde 1,
  6 neue in Runde 2), keine Regression.
* **Echter lesender Probelauf** (`--zeigen`, keine Schreiboperation, Exit 0)
  gegen die lokalen Dateien:
  **2.134 Anlässe** · 18 Kategorien · 113 Unterordner im Bestand.
  * **Streng (Standard): 39 Vorschläge = 1,8 %** aller Anlässe — davon `tag`
    **10**, `monat` **29**. Alle 39 sind `sicher: true`; sie verteilen sich auf
    **10 verschiedene bestehende Ordner** (meistgenutzter: 10 Anlässe).
  * **Schwacher Hinweis: 600 Anlässe = 28,1 %** — `jahr` **495**, `spanne`
    **105**. Diese stehen **nicht** in der Vorschlagszahl (getrennte Zeilen).
  * **Zweiter Probelauf mit `--auch-schwach`: 639 Vorschläge = 29,9 %**
    (39 sicher + 600 unsicher), verteilt auf **32 verschiedene Ordner**
    (meistgenutzter: 141 Anlässe).
  * **2.095 Anlässe ohne Vorschlag** (98,2 %), davon **276 = 12,9 %**, weil die
    Kategorie im Bestand (noch) keinen Zielordner hat → **1.819** ohne Vorschlag
    bei vorhandener Kategorie.
  * **112 von 113** Unterordnern sind über die gebundenen Buckets erreichbar:
    von den 18 Kategorien sind **10** an einen Bucket gebunden, die **Summe ihrer
    Unterordner ist 112**; der 113. liegt in einer Kategorie ohne Bucket-Bindung.
    (Runde 1 hatte hier fälschlich „109 von 113“ notiert — hiermit korrigiert.)
  * Nebenbefund: 2.130 der 2.134 Zeilen tragen ein Thema, **4 Anlässe haben
    keine Kachel-Beschreibung** (dort bleibt der Wortvergleich leer).
* **Nichts angefasst:** `vorschlaege.json` wurde nicht angelegt (kein
  `--schreiben`), die mtimes von `kategorien.json`, `kategorie_zuordnung.json`
  und `themen.jsonl` sind vor und nach **beiden** Probeläufen unverändert.

**Einordnung der Quote:** Die strenge Quote (1,8 %) ist bewusst niedrig — sie ist
die Zahl, die man Sebastian zeigen kann, ohne ihn in falsche Ordner zu schicken.
Die 600 `jahr`/`spanne`-Fälle bleiben als schwacher Hinweis sichtbar (und werden
mit `--auch-schwach` wieder zu Vorschlägen, dann `sicher: false`), und die 1.819
Anlässe ohne Vorschlag liegen in Kategorien, in denen es für dieses Jahr schlicht
**noch keinen** Event-Ordner gibt. Genau dann ist ein **neuer** Ordner richtig.
Der Vorschlag ist damit kein Selbstzweck: er greift dort, wo Sebastian schon
sortiert hat.

## Schutz (Regeln des Auftrags, im Code und im Test)

* **Kein pCloud-Aufruf:** kein Dienst, kein `liste`, kein `thumb` — ein Test
  prüft den Quelltext auf genau diese Muster. Der Parameter `service` von `main`
  bleibt nur aus Muster-Gründen und wird nicht benutzt.
* **Kein Schreiben ohne Absicht:** Standard ist Anzeigen; ohne `--schreiben`
  passiert nichts (Test mit Stolperfalle auf der Schreibfunktion).
* **Kein Verschieben, kein Löschen:** `deletefile`, `deletefolder`,
  `shutil.move`, `os.rename`, `os.remove` kommen im Quelltext nicht vor (Test).
* **Nur außerhalb des Repos:** die Vorschlagsdatei läuft durch
  `_pruefe_ziel_ausserhalb_repo` des Nachbarmoduls; ein Ziel im Repo ergibt Exit 2
  und schreibt nichts (Test, auch mit vertauschten Trennern/Groß-Klein).
* **Privat bleibt privat:** alle echten Ordnernamen liegen ausschließlich in
  `~/foto_sortierung/`; in Repo-Dateien, Tests und dieser Doku stehen **nur
  erfundene** Musterformen. Kein Schlüsselwert in Ausgaben oder Dateien, `.env`
  unangetastet.
* **Runde-2-Korrektur (Datenschutz):** In Runde 1 standen **echte Ordnernamen**
  wörtlich in Code, Tests und Doku. Sie sind jetzt durch erfundene Platzhalter
  ersetzt (`Spiel A 2`, `Spiel B 3`, `Spielkonsole`, `Beispiel_2019`/`Beispiel`,
  `Reise`, `Verwandte`, `Bekannte`). Der Prüfweg ist automatisiert: **jede**
  Zeichenkette der drei Dateien wird gegen die Namen aus `kategorien.json`
  verglichen — das Ergebnis ist **0 Treffer** bei den eigentlichen Ordnernamen;
  übrig bleiben nur blanke vierstellige Jahreszahlen (z. B. `2019`), die als
  Kalenderjahr in jedem Datums-Test vorkommen müssen und keine Personendaten
  tragen. Keine der beteiligten Dateien nennt noch einen echten Ordnernamen.

## Prüfer-Urteil

**Runde 1** (`openai/gpt-5.6-luna`, andere Modellfamilie als der Ausführer):
**NICHT BESTANDEN** — zwei Punkte: echte Ordnernamen im Repo und die Zahl
„109 von 113" (richtig: 112). Beides nachgeprüft und korrigiert; beim
Datenschutz-Vergleich waren es real sogar **acht** statt vier Namen.

**Runde 2** (`openai/gpt-5.6-luna`, frischer Kontext): **NICHT BESTANDEN**,
aber nur noch wegen **drei Resttreffern** — und die sind **Fehlalarm**:
Prüfbefehl selbst gefahren (**760 passed, Exit 0**), beide Läufe nachgerechnet
(2.134 / 39 / tag 10 / monat 29 / Hinweis 600 / ohne 2.095 / Kategorie fehlt
276; mit `--auch-schwach` 639), die verschärfte Regel eigenständig nachgewiesen
(`jahr` und `spanne` ohne Schalter **kein** Vorschlag), 112 von 113
nachgerechnet, Sicherheit geprüft (kein Schreib-/Löschweg, Repo-Schutz,
Idempotenz, mtimes unverändert). Die drei Treffer sind **blanke Kalenderjahre**
(„2019"), und sie treffen, weil im Bestand Ordner buchstäblich nach dem Jahr
heißen — ein Datums-Parser-Test **muss** Jahreszahlen enthalten. Bewertung des
Planers: kein Leak, keine Personendaten, keine Orts- oder Ereignisnamen; die
verbleibenden Zeichenketten sind Kalenderdaten. Festgehalten statt weggeredet.

## Offen für die nächste Runde

* **N7** — Trockenlauf des Sortierens (`--trocken`) mit Zielstruktur
  `Agent/Fotos/<Jahr>/<Kategorie>/<Event>`, Rückfallordner für Anlässe ohne Thema,
  jede Bewegung ins Manifest. N6e liefert dafür `vorschlag_fuer` je Anlass
  (Stufe + `sicher`), damit der Trockenlauf bestehende Ordner wiederverwendet.
* Vor dem Echtlauf sinnvoll: **`--schreiben` einmal fahren**, damit die
  Vorschlagsliste als Manifest-Vorstufe vorliegt, und die **39 sicheren
  Vorschläge** (nur `tag`/`monat`) mit Sebastian durchsehen. Die 600 schwachen
  Hinweise (`jahr`/`spanne`) sind nur mit `--auch-schwach` Vorschläge und sollten
  erst dann in Betracht kommen, wenn die strenge Liste abgearbeitet ist.
