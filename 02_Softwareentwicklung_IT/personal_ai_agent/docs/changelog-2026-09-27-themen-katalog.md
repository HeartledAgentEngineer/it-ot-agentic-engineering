# N6c: Fester Themen-Katalog für das Foto-Themen-Werkzeug

> **Datum:** 27.09.2026 · **Schritt:** N6c aus `docs/plan-nachtlauf-2026-09-26.md`
> (Entscheidung aus N6b, `docs/changelog-2026-09-27-themen-stapel1.md`) ·
> **Geänderte Dateien:** `tools/foto_sortierung/themen_katalog.py` (neu),
> `tools/foto_sortierung/foto_themen_vision.py`,
> `backend/tests/test_foto_themen_vision.py`,
> `docs/changelog-2026-09-27-themen-katalog.md` (diese Datei) — sonst nichts.

## Zweck: der Befund aus N6b, in Zahlen

Der Massenlauf N6b Stapel 1 hat 161 Anlässe angesehen und dafür **155
verschiedene Themen** vergeben = **96 % Einzelstücke** (155/161 = 96,27 %).
Beispiele aus dem echten Lauf: „Haus Garten" **und** „Haus und Garten";
„Sonnenuntergang Stadtansicht", „Sonnenuntergang Meer",
„Sonnenuntergang am See". Als Ordnerbaum `Agent/Fotos/<Jahr>/<Thema>/` ist das
untauglich: faktisch bekäme jedes Foto einen eigenen Ordner, dasselbe Motiv
läge zerstreut.

Die Ursache lag **im Prompt, nicht im Modell**: `prompt_bauen()` verlangte
„2 bis 4 deutsche Wörter, die den Anlass benennen" — **ohne Wortschatz**. Ohne
feste Liste erfindet jedes Modell bei jedem Aufruf neue Wörter.

**N6c dreht das um:** Das Modell darf sein Thema nur noch aus einem festen
Katalog wählen; alles, was nicht **WORT FUER WORT** passt, fällt auf
`Sonstiges`. Der Ordnerbaum `Agent/Fotos/<Jahr>/` ist damit auf **44 Themen
je Jahr** beschränkt (harte Obergrenze statt offener Wortliste).

## Der vollständige Katalog (44 Einträge, `KATALOG_VERSION = 2`)

Reihenfolge wie in `THEMEN_KATALOG` (und so steht er im Prompt):

| # | Eintrag | Bereich |
|---|---|---|
| 1 | Familienfeier Zuhause | Personen & Familie |
| 2 | Kindergeburtstag Zuhause | Personen & Familie |
| 3 | Babybauch Fotoshooting | Personen & Familie |
| 4 | Familienausflug Wochenende | Personen & Familie |
| 5 | Haus und Garten | Haus & Garten |
| 6 | Gartenarbeit im Freien | Haus & Garten |
| 7 | Balkon und Terrasse | Haus & Garten |
| 8 | Blumen im Garten | Haus & Garten |
| 9 | Wandern im Schnee | Natur & Landschaft |
| 10 | Wanderung im Wald | Natur & Landschaft |
| 11 | See und Fluss | Natur & Landschaft |
| 12 | Berg und Tal | Natur & Landschaft |
| 13 | Strand und Meer | Natur & Landschaft |
| 14 | Hund im Freien | Tiere |
| 15 | Katze Zuhause | Tiere |
| 16 | Tiere im Zoo | Tiere |
| 17 | Stadtbummel Altstadt | Stadt & Reisen |
| 18 | Reise und Urlaub | Stadt & Reisen |
| 19 | Ausflug ins Umland | Stadt & Reisen |
| 20 | Museum und Ausstellung | Stadt & Reisen |
| 21 | Fest und Feier | Veranstaltungen & Feste |
| 22 | Weihnachtsmarkt Besuch | Veranstaltungen & Feste |
| 23 | Konzert und Buehne | Veranstaltungen & Feste |
| 24 | Geburtstag mit Gaesten | Veranstaltungen & Feste |
| 25 | Arbeit am Schreibtisch | Arbeit & Technik |
| 26 | Technik und Geraete | Arbeit & Technik |
| 27 | Computer und Bildschirm | Arbeit & Technik |
| 28 | Essen und Trinken | Essen & Trinken |
| 29 | Kochen in der Kueche | Essen & Trinken |
| 30 | Restaurant Besuch | Essen & Trinken |
| 31 | Kuchen und Gebaeck | Essen & Trinken |
| 32 | Sport und Fitness | Sport & Bewegung |
| 33 | Laufen und Joggen | Sport & Bewegung |
| 34 | Spiel und Bewegung | Sport & Bewegung |
| 35 | Auto und Strasse | Fahrzeuge |
| 36 | Fahrrad und Radweg | Fahrzeuge |
| 37 | Zug und Bahnhof | Fahrzeuge |
| 38 | Wohnung und Einrichtung | Innenraum & Alltag |
| 39 | Aufraeumen Zuhause | Innenraum & Alltag |
| 40 | Fenster und Licht | Innenraum & Alltag |
| 41 | Bauen und Renovieren | Bauen & Handwerk |
| 42 | Handwerk und Werkzeug | Bauen & Handwerk |
| 43 | Baustelle und Geruest | Bauen & Handwerk |
| 44 | **Sonstiges** | Rückfall (MUSS der letzte Eintrag sein) |

Regeln, die das Modul prüfbar einhält: genau **44** Einträge, keine Doppelungen
(auch nicht normalisiert), jeder **2–4 Wörter** (einzige Ausnahme: der
einwortige Rückfall `Sonstiges`), als Ordnername tauglich (kein `/`, kein `\`,
keines der verbotenen Zeichen `: * ? " < > |` und keine Steuerzeichen,
höchstens 60 Zeichen, kein führendes/abschließendes Sonderzeichen, nicht rein
numerisch). Umlaute sind bewusst als `ae/oe/ue/ss` geschrieben, damit der
Ordnername auf jedem Dateisystem und in jeder API-Antwort unverändert
ankommt.

## Was der Code Änderungen unterzieht (codegenau)

**`tools/foto_sortierung/themen_katalog.py` (neu, rein: kein Netz, kein I/O)**

* `KATALOG_VERSION = 2` — Stand des Wortschatzes; **wer `THEMEN_KATALOG`
  ändert, erhöht die Version** (Themen aus verschiedenen Ständen sind nicht
  vergleichbar).
* `THEMEN_KATALOG: list[str]` — die 44 Einträge.
* `SONSTIGES = "Sonstiges"` — der Rückfall.
* `thema_normalisieren_katalog(text) -> str`: Nicht-String/leer → `""`; sonst
  Kleinschreibung, Mehrfach-Leerraum zu einem Leerzeichen, Rand-Leerraum UND
  Rand-Satzzeichen (`. , ; : ! ? " ' \` - _`) abstreifen.
* `thema_zuordnen(antwort) -> str`: nach Normalisierung **exakter** Treffer →
  der Katalog-Eintrag im **Original-Wortlaut**; kein Treffer oder kein String →
  `Sonstiges`.
* `im_katalog(antwort) -> bool`: `True` **nur** bei einem echten Katalogeintrag
  (`Sonstiges` selbst steht im Katalog und ist damit `True`), nicht beim
  Rückfall.
* `katalog_text() -> str`: alle Einträge mit `" | "` verbunden, in
  Katalog-Reihenfolge.

**`tools/foto_sortierung/foto_themen_vision.py`**

* `prompt_bauen(anzahl, katalog=None)` — neuer **optionaler** Parameter.
  * Ohne `katalog`: Verhalten **byte-gleich** zu vorher (die Zeile „2 bis 4
    deutsche Woerter …" bleibt stehen) — bestehende Aufrufe bleiben gleich.
  * Mit `katalog`: die Themazeile wird ersetzt durch die Anweisung, dass das
    Thema **GENAU EIN** Eintrag der mitgelieferten Liste sein muss, **WORT FUER
    WORT** übernommen, ohne Abwandlung und ohne eigene Wörter; passt nichts,
    ist `"Sonstiges"` zu nehmen. Die **vollständige Liste** (`katalog_text()`)
    steht ausgeschrieben im Prompt-Teil `Themenliste: …`.
  * Alle übrigen Prompt-Teile (Kachelnummern 1..n, `je_kachel`, `unbrauchbar`,
    `hinweis`, Regeln) bleiben inhaltlich unverändert.
* `anfrage_bauen(modell, daten_uri, anzahl, max_tokens=MAX_TOKENS, katalog=None)`
  — reicht `katalog` an `prompt_bauen` durch.
* `thema_uebernehmen(thema, katalog_aktiv, schluessel="") -> tuple` — gibt
  `(thema_fuer_ordner, thema_roh, katalog_treffer)`:
  * ohne Katalog: `(thema_normalisieren(thema), "", False)` (alter Weg),
  * mit Katalog: Treffer → `(Katalogeintrag, roher Text, True)`;
    kein Treffer → `(Sonstiges, roher Text, False)`.
  * Der rohe Text läuft durch `geheimnis_entfernen` (Schlüssel-Maskierung).
* `anlass_verarbeiten(..., katalog=None)` — gibt im Ergebnis zusätzlich
  `thema_roh` und `katalog_treffer` aus; `thema` bleibt unverändert das
  Ordner-Thema. Eine Modellantwort **ohne brauchbares `thema`** (leer,
  `"///"`) bleibt in **beiden** Modi ein Fehler: ein leerer Text ist kein Thema
  außerhalb des Katalogs, und `Sonstiges` dafür wäre eine Beschönigung.
* **CLI:** neuer Schalter `--ohne-katalog` (Katalog AUS, altes Verhalten).
  Der **Katalog ist Standard AN** (Liste aus `themen_katalog.py`,
  `KATALOG_VERSION 2`). Die Kopfzeile zeigt `Themen-Katalog: 44 Eintraege,
  Version 2 (--ohne-katalog schaltet ihn aus)` bzw. `AUS (--ohne-katalog)`.
  Die **Schlusszeile** nennt zusätzlich:
  `Katalog: <X> Treffer, <Y> Sonstiges (von <Z> angesehenen Anlaessen)`
  (X + Y = Z = angesehene Anlässe dieses Laufs).
* Import: das Nachbarmodul wird wie in `foto_themen.py` über `_modul_aus_pfad`
  geladen — die Datei läuft damit **sowohl als Skript**
  (`python ../tools/foto_sortierung/foto_themen_vision.py …`) **als auch als
  importiertes Modul** in den Tests.

## Neue Felder in den Ausgaben (beide Modi schreiben, Katalog füllt sie)

* `themen/<Jahr>/<Titel>.json`: neu `thema_roh` (Rohtext des Modellthemas,
  entschärft) und `katalog_treffer` (true/false).
* `themen.jsonl`: dieselben zwei Felder je Zeile (vorher: `thema` nur als
  Ordner-Thema).
* `sortierschluessel_themen.csv`: unverändert im Aufbau (Spalten `thema`,
  `thema_quelle`); `thema` trägt jetzt den **Katalogwert** (`Sonstiges` bzw.
  den Eintrag), nicht den Rohtext.

Ohne Katalog ist `thema_roh` bewusst `""` und `katalog_treffer` `false` — dort
gibt es keinen zweiten Wert, der etwas anderes aussagen würde.

## Tests: 28 neue Prüfungen, alle OHNE Netz

`backend/tests/test_foto_themen_vision.py` — **59 → 87** Prüfungen in dieser
Datei (**+28**); es wurde nichts gelöscht. Neu sind u. a.:

* Katalog-Aufbau: 40–60 und genau 44 Einträge, keine Doppelungen (auch
  normalisiert), jeder Eintrag ordnertauglich (verbotene Zeichen, ≤ 60 Zeichen,
  2–4 Wörter ohne `Sonstiges`, kein Rand-Sonderzeichen, nicht numerisch),
  `Sonstiges` als letzter Eintrag, Abdeckung der zwölf Lebensbereiche
  (Stichprobe je zwei Einträge), `katalog_text()` verbindet in Reihenfolge,
  `KATALOG_VERSION == 2`.
* Zuordnung: exakter Eintrag; Groß/Klein + Punkt am Ende + doppelter Leerraum
  treffen trotzdem; `"Drache ueber Hamburg"`/`"Haus Garten"`/
  `"Wintermarkt am See"` → `Sonstiges`; `None`/leer/Zahl/Liste/Dict →
  `Sonstiges`; `im_katalog` true für die drei echten Fälle, false für die
  Rückfälle; Normalisierung im Detail.
* Prompt: `prompt_bauen(12)` ohne Katalog enthält weiterhin „2 bis 4 deutsche
  Woerter" und **keinen** Katalogeintrag; `prompt_bauen(12, katalog=THEMEN_KATALOG)`
  enthält **jeden** der 44 Einträge, den Wortlaut `WORT FUER WORT` und
  `Sonstiges`; Kachelnummern/`je_kachel`/`unbrauchbar`/`hinweis`/Regeln bleiben.
* `thema_uebernehmen`: ohne Katalog der alte Weg, mit Katalog Treffer und
  Rückfall, Rohtext maskiert (`sk_`-Schlüssel wird zu
  `<schluessel-entfernt>`).
* CLI über injizierten Transport (kein Netz): Standardlauf schickt die ganze
  Liste; `--ohne-katalog` schickt sie nicht (Prompt enthält dann wieder „2 bis
  4 deutsche Woerter") und `thema_roh` bleibt leer.
* Simulierter Durchlauf: Thema `"Sonnenuntergang am Meer"` (kein
  Katalogeintrag) → gespeichertes `thema == "Sonstiges"`, `thema_roh ==
  "Sonnenuntergang am Meer"`, `katalog_treffer false`, Fortsetzungspunkt und
  CSV-Kopie ebenso; Gegenprobe mit echtem Eintrag (`"Wandern im Schnee"`) →
  `thema == Eintrag`, `katalog_treffer true`, und eine abweichende Schreibweise
  des Modells (`"  WANDERN IM SCHNEE. "`) wird auf den Original-Wortlaut
  gezogen.
* Schlusszeile: `Katalog: 1 Treffer, 0 Sonstiges (von 1 angesehenen Anlaessen)`
  bzw. `0 Treffer, 1 Sonstiges …`.
* Hygiene: auch der Kataloglauf legt nichts im Repo an
  (`_dateibaum(WERKZEUG.parent)` vorher == nachher), der Schlüssel steht weder
  auf der Konsole noch in irgendeiner Ausgabedatei, die Eingabe-CSV bleibt
  liegen.

**Angepasst, nicht gelöscht:** drei bestehende CLI-Prüfungen
(`test_cli_schreibt_thema_json_jsonl_und_csv`,
`test_fehlgeschlagener_anlass_wird_festgehalten_und_lauf_geht_weiter`,
`test_fehlende_kacheln_werden_gezaehlt_thema_bleibt`) benutzen ein freies Thema
(„Wintermarkt am See", kein Katalogeintrag) und prüfen das Durchreichen. Sie
fahren jetzt mit `--ohne-katalog`; **alle ihre Zusagen und Behauptungen sind
unverändert** (freies Thema kommt roh durch). Das Verhalten mit Katalog deckt
die neuen Prüfungen ab.

## Prüfbefehl und Ergebnis (selbst gefahren)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* Baseline vor der Änderung: **628 passed, Exit 0** (107,6 s).
* Nach der Änderung: **656 passed, Exit 0** (95,6 s) — **+28** Prüfungen.
* Zusätzlich: `python ../tools/foto_sortierung/foto_themen_vision.py --help`
  läuft als Skript (Import über Pfad funktioniert beide Wege).

Kein echter Vision-Aufruf, kein OpenRouter-Zugriff, kein API-Schlüssel
gelesen oder ausgegeben; alle Tests laufen ohne Netz (der Transport ist eine
Attrappe, `httpx.post`/`httpx.get` sind in der autouse-Fixture gesperrt).

## Was ausdrücklich NICHT passiert ist

* **Nichts gelöscht:** kein Katalog-Eintrag, keine Datei, keine Prüfung.
* **Keine Modellwahl-Entscheidung:** `flash-lite` gegen `flash` wird weiterhin
  nicht hier entschieden — der Vergleich gehört an den Katalog (jetzt möglich).
* **Die Original-CSV `~/foto_sortierung/sortierschluessel.csv` wurde nicht
  angefasst** (nur gelesen); geschrieben wird weiterhin ausschließlich die
  Kopie `~/foto_sortierung/sortierschluessel_themen.csv` und nur außerhalb des
  Repos (der Repo-Schutz `_pruefe_ausgabe` und der CSV-Schutz
  `_pruefe_csv_ziel` bleiben unverändert in Kraft).
* **Keine pCloud-Schreibzugriffe**, keine echten Vision-Aufrufe, kein Rücklauf
  über die 161 Anlässe aus N6b (der läuft erst nach diesem Schritt, mit
  `--wiederholen`).
* Keine Änderung an `KATALOG_VERSION`-Konsumenten außerhalb der vier genannten
  Dateien.

## Nachtrag: Katalog erweitert (Version 3)

> **Datum:** 27.09.2026 · **Geänderte Dateien:** `tools/foto_sortierung/themen_katalog.py`,
> `backend/tests/test_foto_themen_vision.py`,
> `docs/changelog-2026-09-27-themen-katalog.md` (diese Datei) — sonst nichts.

### Der Messlauf, der die Lücken zeigte

Der erste Messlauf mit dem Katalog (`google/gemini-2.5-flash`, ein Vision-Aufruf
je Kontaktbogen) über **161 Anlässe** ergab:

* **161 Katalog-Treffer — 100 %** der Anlässe bekamen ein Thema aus dem Katalog
  (kein einziges freies Thema mehr durchgelassen),
* **0 Fehler**,
* aber **43 von 161 Anlässen = 27 %** landeten auf `Sonstiges`.

Ausgewertet wurden dafür die **Kachel-Kurzbeschreibungen** dieser 43 Anlässe.
Sie zeigten neun **fehlende Sachgebiete** — also Motive, für die der Katalog
schlicht kein Wort hatte:

| Fehlendes Sachgebiet | Anlässe | Kachel-Beispiele |
|---|---|---|
| Sonnenuntergang / Abendhimmel | 6 | Sonnenuntergang über Stadt, Hafen, Dachansicht |
| Stadt bei Nacht / Beleuchtung | 2 | Bäume bei Nacht mit bunter Beleuchtung |
| Selfies / Porträts ohne Anlass | 7 | junge Menschen lachen in die Kamera, Zunge herausstrecken, Händeschütteln, Spiegel-Selfie |
| Freunde / Gruppe unterwegs | 3 | Männer auf dem Bürgersteig, drei Männer am Tisch |
| Demonstration / Politik | 3 | Personen mit Fahne und Banner auf der Straße, Bildschirm mit Wahlergebnissen |
| Screenshots / Text / Memes | 6 | Bildschirmfoto mit Formeln, Memes mit Text, Text-Grafiken |
| Zeitungen / Dokumente / Buchseiten | 3 | Zeitungsausschnitte, Buchseite mit Diagramm, Weihnachtskarte |
| Dinge / Stillleben / Nahaufnahmen | 7 | Ferrero und Red Bull, Brettspiel, Schmutz auf Teppich, Schriftzug auf Fahrzeug, Briefkästenfächer |
| Tiere auf dem Land / Hof | 3 | Huhn mit Küken, Schweine im Stall, Igel auf dem Boden |

### Die neun neuen Einträge (Wortlaut wie im Code)

```
Abendhimmel und Sonnenuntergang
Stadt bei Nacht
Selfie und Portraet
Freunde unterwegs
Demonstration und Politik
Text und Screenshot
Zeitungen und Dokumente
Dinge und Stillleben
Tiere auf dem Land
```

Sie stehen **vor `Sonstiges`**; `Sonstiges` bleibt der **letzte** Eintrag. Jeder
Eintrag hält die harten Regeln ein (2–4 Wörter, kein `/`/`\`, keine verbotenen
Zeichen, ≤ 60 Zeichen, keine Doppelung — geprüft, nicht behauptet). Es wurde
**kein** Eintrag weggelassen: keiner der neun stand bereits in gleicher oder
ähnlicher Form im Katalog (nachgeprüft über `len(set(KATALOG))` und den
normalisierten Vergleich).

### Neue Gesamtzahl und Version

* **44 → 53 Einträge** (**+9**). `KATALOG_VERSION`: **2 → 3**
  (`tools/foto_sortierung/themen_katalog.py`). Die Kopfzeile der CLI zeigt damit
  `Themen-Katalog: 53 Eintraege, Version 3 (--ohne-katalog schaltet ihn aus)`
  (das Werkzeug liest die Zahl und die Version aus dem Modul — keine Zweitkopie).
* Der Docstring des Moduls nennt jetzt den Messlauf mit den Zahlen
  (161 Anlässe, 100 % Treffer, 0 Fehler, 43 = 27 % Sonstiges) und die neun
  Gebiete, damit die Herkunft der Einträge im Code steht und nicht nur hier.

### Tests: angepasst und ergänzt

`backend/tests/test_foto_themen_vision.py` — von **87 auf 88** Prüfungen in
dieser Datei (**+1**); es wurde **nichts gelöscht oder abgeschwächt**.

* **Auf den neuen Stand gezogen:** `test_katalog_hat_genau_44_eintraege` →
  `test_katalog_hat_genau_53_eintraege` (53 statt 44, für Katalog und Werkzeug),
  `test_katalog_version_ist_2` → `test_katalog_version_ist_3` (3 statt 2, für
  Katalog und Werkzeug) und die CLI-Prüfung
  `test_cli_standard_schickt_die_ganze_liste` erwartet jetzt
  `53 Eintraege, Version 3` in der Kopfzeile.
* **Neu:** `test_katalog_enthaelt_die_neun_neuen_eintraege` (alle neun im
  Katalog, jeder vor `Sonstiges`, jeder wird wortgleich zugeordnet).
* **Unverändert gültig:** Zielgröße 40–60, keine Doppelungen (auch nicht
  normalisiert), jeder Eintrag ordnertauglich (verbotene Zeichen, ≤ 60 Zeichen,
  kein Rand-Sonderzeichen, nicht numerisch), 2–4 Wörter außer dem einwortigen
  Rückfall, `Sonstiges` zuletzt, `katalog_text()` verbindet in Reihenfolge,
  Prompt mit Katalog enthält **jeden** Eintrag. Alle diese Schleifen laufen über
  den **ganzen** Katalog und decken damit auch die neun neuen Einträge ab.

### Prüfbefehl und Ergebnis (selbst gefahren)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* **657 passed, Exit 0** (149,9 s) — vorher 656 passed (die neue Prüfung ist
  die +1; die beiden umbenannten zählen weiter je einmal).
* Zusätzlich der Skriptlauf:
  `cd backend && .venv/Scripts/python ../tools/foto_sortierung/foto_themen_vision.py --jahr 2014 --limit 1 --nur-liste`
  → Exit 0, Kopfzeile `Themen-Katalog: 53 Eintraege, Version 3`.

Kein echter Vision-Aufruf, kein OpenRouter-Zugriff, kein API-Schlüssel gelesen
oder ausgegeben, keine git-Befehle, keine Datei außerhalb der drei genannten
angefasst.

---

## Messung mit Katalog **Version 3** (echte Vision-Aufrufe, 161 Anlässe)

Dieselben **161 Anlässe** des Stapels 1 (Jahre 2014, 2016, 2017, 2019, 2020,
2021), je **ein** Aufruf pro Anlass und Modell, Katalog Version 3. Preise live
über `/api/v1/models` geholt.

**flash (`google/gemini-2.5-flash`, 0,30 / 2,50 USD je Mio)**

* 161 Anlässe, **0 Fehler**, **161 von 161** Antworten liegen im Katalog (100 %).
* Thema `Sonstiges`: **14 Anlässe (8,7 %)** — alle 14 **selbst** gewählt,
  **0** Antworten außerhalb des Katalogs.
* **37 verschiedene Themen** von 53 (vorher mit Version 2: 155 Einzelstücke).
* 484.279 ein / 25.757 aus Tokens → **0,209693 USD** = **0,001302 USD je Anlass**.

**flash-lite (`google/gemini-2.5-flash-lite`, 0,10 / 0,40 USD je Mio)**

* 161 Anlässe, **0 Fehler**, **160 von 161** Antworten liegen im Katalog
  (99,4 %) — die eine Ausnahme fiel auf `Sonstiges`.
* Thema `Sonstiges`: **18 Anlässe (11,2 %)** = **17 selbst gewählt** + **1** aus
  der außerhalb des Katalogs liegenden Antwort.
* **34 verschiedene Themen** von 53.
* 484.279 ein / 26.348 aus Tokens → **0,058977 USD** = **0,000366 USD je Anlass**.

**Die Erweiterung hat gewirkt:** mit Version 2 (44 Einträge, flash) landeten
**43 von 161 = 27 %** auf `Sonstiges`; mit Version 3 sind es **14 = 8,7 %**.

**Modellvergleich (identische Anlässe, identischer Prompt, nur das Modell
unterschiedlich):**

* Trefferquote: flash 100 % · flash-lite 99,4 %.
* Kosten: flash ist das **3,56-Fache** von flash-lite
  (0,209693 zu 0,058977 USD für dieselben 161 Anlässe).
* Hochrechnung auf die **1.967 noch wartenden** Anlässe: flash **2,56 USD**,
  flash-lite **0,72 USD**.

**Sichtprobe (6 Bögen, in genau den Fällen, in denen sich beide Modelle
widersprechen):** flash trifft **4**, flash-lite **2**. Die Fehler von
flash-lite sind **Fehlzuordnungen in ein falsches Sachgebiet** — „Huhn mit
Küken" → `Hund im Freien`, sommerliche Bergtour → `Wandern im Schnee`, Reise vor
Palmen → `Familienfeier Zuhause`. Wo flash keine passende Kategorie sieht, sagt
es ehrlich `Sonstiges` (bei der Henne korrekt, weil der Katalog keine Hoftiere
kannte). **Entscheidung: flash** für den Massenlauf — 1,84 USD Mehrkosten für
1.967 Anlässe sind gegenüber einem falsch sortierten Ordnerbaum belanglos.

**Restliche 14 `Sonstiges`-Anlässe** (flash) sind überwiegend **Bildschirmfotos,
Memes und Textbilder** (Glühwein-Text, „Finde das Kamel", Wahlergebnisse,
Zeitungsausschnitt, Rezeptseite) plus einzelne Grenzfälle (Teppichfleck, grauer
Boden, Führung vor einer Tafel). Dafür kommt **bewusst kein** Katalogeintrag
dazu — weitere ähnliche Einträge würden überlappende Ordner erzeugen.

**Schutz unverändert:** Original-CSV `~/foto_sortierung/sortierschluessel.csv`
unangetastet (`md5 70642d2988b6e38ff417561ccf870ba8`); alle Ausgaben liegen
außerhalb des Repos. Fortsetzungspunkte: `~/foto_sortierung/themen.jsonl`
(flash) und `~/foto_sortierung/katalogtest_lite/themen.jsonl` (Vergleichslauf).

**Prüfer `openai/gpt-5.6-luna`** hat den Endstand selbst nachgerechnet
(Prüfbefehl, Katalogzählung 53/Version 3, Messzahlen beider Läufe, md5). Eine
Beanstandung: die Angabe „18 gewählte Sonstiges" für flash-lite war unpräzise —
richtig sind **17 selbst gewählte + 1 außerhalb des Katalogs** (Thema ebenfalls
`Sonstiges`, aber `katalog_treffer: false`). Hier korrigiert.
