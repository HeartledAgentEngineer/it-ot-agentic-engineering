# Changelog 27.09.2026 — N9a: Personen-Verfahren (Mengen-Filter, Clustering, Referenzseiten)

Auftrag: `docs/auftrag-n9-personen-verfahren.md` (Feinauftrag N9a).
Ausfuehrer: Hermes-Subagent. Rolle der Datei: Beleg mit Zahlen zum Abnahmepunkt.

## Was entstanden ist (genau drei Dateien)

| Datei | Zeilen | Inhalt |
|---|---|---|
| `tools/foto_sortierung/personen_cluster.py` | **1510** | das Werkzeug (10 Vorgabefunktionen + Helfer) |
| `backend/tests/test_personen_cluster.py` | **1590** | **216** Testfunktionen, vollstaendig offline |
| `docs/changelog-2026-09-27-personen-verfahren.md` | diese Datei | Zahlen und Abweichungen |

Keine andere Datei wurde inhaltlich geaendert. Keine `git`-Befehle ausgefuehrt
(das macht der Planer).

## Pruefbefehl (selbst gefahren, Ausgabe ungekuerzt)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

| | |
|---|---|
| Baseline vorher | **879 passed**, Exit 0 (vor dem Bau separat gemessen) |
| Nachher | **1095 passed**, 3 warnings, 72,75 s, **Exit 0** |
| Zuwachs | **+216** — genau die Zahl der neuen Testfunktionen (`grep -c "^def test_"` = 216) |
| Nur die neue Datei | 216 passed, Exit 0 |

Es sind **keine** Tests aus dem Bestand angefasst, umgeschrieben oder uebersprungen
worden; die drei Warnungen sind dieselben wie in der Baseline (Pydantic-Deprecation).

## Pflichtfaelle aus dem Auftrag — wo sie geprueft werden

* **Massenfoto clustert nicht**: 4032×3024 mit 40 kleinen Gesichtern (100×100 px)
  → `bild_art == "menge"`, `clustern is False`, `grund == "menge_ohne_bekannte_person"`.
* **Massenfoto mit bekannter Person**: dasselbe Bild plus ein grosses Gesicht mit
  Katalog-Treffer → `clustern is True`, `personen == ["Person_007"]`.
* **Grenzfaelle der Art**: 0 Gesichter, 1 Grossgesicht, 3 kleine → `unklar`,
  5 kleine + 1 grosses → `gruppe`, `score` unter `MIN_SCORE`, `bbox`-Breite 0,
  `bildbreite`/`hoehe` 0 (kein `ZeroDivisionError`), Staub unter `ANTEIL_MIN`.
* **Clustern**: 3 klar getrennte Gruppen + Rauschen → genau 3 Gruppen, Rauschen
  **nicht** enthalten; identische Vektoren → eine Gruppe; leerer Eingang → `[]`;
  zweimal derselbe Aufruf → gleich.
* **Kennungen**: zweiter Lauf mit gleichem Altbestand → gleiche Kennungen; neue
  Gruppe → naechste freie Nummer; verschwundene Kennung wird nicht neu vergeben.
* **Referenzseiten**: Datei entsteht, Groesse > 0, Kachelraster und Beschriftung
  ueber Bildmasse belegt; zweiter Lauf schreibt 0, mit `erneut=True` wieder;
  `kachel_holen` → `None` (und: wirft, und: liefert unlesbare Bytes) → Platzhalter,
  kein Absturz.
* **Verbote im Quelltext**: keine Loeschfunktion (`deletefile|deletefolder|
  shutil.rmtree|os.remove|os.unlink`), kein pCloud-Aufruf (`requests|httpx|e.pcloud`),
  kein Manifest, keine Vektor-/Mittelpunkt-Ausgabe in einer `print`-Zeile.
* **Nebenwirkungsfrei**: `bild_entscheidung` und `bericht_bauen` laufen mit
  stillgelegtem `open` durch (Test) — kein Dateizugriff.
* **Repo-Schutz**: Ausgabe im Repo → deutsche Meldung + `SystemExit(2)`, es wird
  nichts geschrieben (Test fuer Ordnergrenze und fuer die Kennungsdatei).

## Live-Stichprobe am Werkzeug (SYNTHETISCH — die echte Messung ist N9b)

> **Diese Stichprobe ist synthetisch.** Sie bestand aus **keiner** Bilddatei,
> **keinem** pCloud-Aufruf und **keinem** echten Bestand: erzeugt wurde nur eine
> Vektordatei aus einem Seed (`numpy.random.default_rng(20260927)`), mit
> eingebauter Wahrheit. Die echte Messung an den Fotos des Nutzers ist Schritt N9b
> (Modelle holen, `cv2`/`onnxruntime` in eigenem venv).

*Eingabe:* `C:/Users/sebas/foto_sortierung/personen_probe/vektoren_probe.jsonl`
(ausserhalb des Repos) — 83 Bilder, 221 Gesichter.

*Aufruf:* `personen_cluster.py --vektoren … --ausgabe …/seiten` (Trockenlauf) und
danach mit `--schreiben` bzw. `--schreiben --erneut`.

**Eingebaut vs. gefunden**

| | |
|---|---|
| eingebaute Personen-Cluster | **12** |
| Fotos darin | 76, Groessen `5,5,6,6,5,7,5,5,9,6,9,8` |
| gefundene Gruppen | **12** |
| Groessen der Gruppen | `5,5,6,6,5,7,5,5,9,6,9,8` — **identisch mit der Wahrheit** |
| **Trefferquote** | **12/12 = 100 %** |
| falsch zusammengelegt (mehr als eine Person in einer Gruppe) | **0** |
| uebersehen (eingebaute Person ohne Gruppe) | **0** |
| Rausch-Gesichter in einer Gruppe | **0** von 4 (5,3 %) — das Rauschen wurde verworfen |

Der Vergleich lief ueber die Zuordnung Gruppe → eingebaute Person; jede der 12
Gruppen enthielt ausschliesslich Fotos **einer** eingebauten Person, und keine
Gruppe enthielt ein Fremd-/Rausch-Gesicht.

**Mengen-Filter (die Pflichtpruefung des Plans)**

* 3 Massen-Bilder mit zusammen **141 kleinen Gesichtern** (100×100 px, kein
  erkennbares) → Art `menge`, `clustern: False`, Grund
  `menge_ohne_bekannte_person`. Aus diesen 141 Gesichtern entstand **keine**
  Gruppe und **keine** Referenzseite.

**Zahlen des Laufs (Bericht des Werkzeugs, Trockenlauf)**

```
Bilder gelesen: 83   Zeilen gesamt: 83   ungueltige Zeilen: 0
Je Bild-Art: leer: 0   gruppe: 80   menge: 3   unklar: 0
Geclusterte Bilder: 80   mit bekannter Person: 0   Gruppen: 12
Kennungen neu: 12   Kennungen wiederverwendet: 0   Kacheln geschrieben: 0
Gruende: gruppe: 80   menge_ohne_bekannte_person: 3
```

**Schreiben und Idempotenz**

* 1. Lauf mit `--schreiben`: 14 Referenzseiten geschrieben
  (`Person_001_seite_01.jpg` … `Person_012_seite_01.jpg`; `Person_009` und
  `Person_011` haben wegen 9 Kacheln eine zweite Seite), dazu `kennungen.json`
  mit 12 Kennungen. Groessen der Seiten 6.680–34.999 Bytes.
* 2. Lauf mit `--schreiben`: **0** Referenzseiten geschrieben, `kennungen.json`
  hatte 12 Kennungen, im Bericht `Kennungen neu: 0` /
  `Kennungen wiederverwendet: 12`, dieselben 12 Kennungen wie im ersten Lauf —
  die Idempotenz haelt also auch ueber die CLI (nicht nur im Test).
* `--schreiben --erneut`: 14 Seiten neu geschrieben.
* Trockenlauf schreibt nichts: der Ausgabeordner existierte danach nicht.

**Bildkontrolle** (Sichtpruefung einer erzeugten Seite ueber die Bildanalyse):
`Person_009_seite_01.jpg` zeigt ein 4×2-Raster mit 8 Kacheln, jede Kachel mit
`keine Kachel` (es gab keine Bildquelle — siehe unten) und darunter die
Beschriftung `1. Person_009` … `8. Person_009`.

**Warum Platzhalter statt Kachelbilder:** das Werkzeug fasst keine Bilddateien an.
Die Kachelquelle ist die eingesteckte Funktion `kachel_holen(eintrag) -> bytes|None`;
in der CLI ist sie standardmaessig leer, also entstehen beschriftete Platzhalter.
Den echten Weg (pCloud-Download bzw. Handy-Crop) steckt N9b an — dann steht in
jeder Kachel ein Gesicht, ohne dass am Verfahren etwas geaendert werden muss.

## Was bewusst anders gemacht wurde als im Feinauftrag (mit Begruendung)

1. **`--schreiben` ergaenzt, Trockenlauf bleibt Standard.** Der Auftrag nennt nur
   `--trocken` und sagt gleichzeitig „Standard ist trocken". Mit einem einzigen
   `--trocken`-Schalter waere Schreiben nie erreichbar. Umgesetzt wie in
   `foto_sortieren.py`: ohne `--schreiben` passiert nichts, `--trocken` hat
   Vorrang vor `--schreiben`. Ein Werkzeug, das beim Weglassen eines Flags
   Dateien anlegt, waere die falsche Voreinstellung.
2. **`--altbestand` und `kennungen.json` ergaenzt.** Ohne gespeicherten
   Altbestand waeren die Kennungen nach jedem Lauf neu — die Auftragsforderung
   „Kennung bleibt stabil" waere auf der Kommandozeile nicht erfuellbar. Der
   Lauf liest `kennungen.json` aus dem Ausgabeordner (wenn vorhanden), schreibt
   ihn beim Schreiben fort und nimmt alternativ `--altbestand <pfad>`.
3. **`bild_entscheidung` prueft bei `art == "menge"` den Katalog gegen *alle
   nutzbaren* Gesichter, nicht nur gegen die erkennbaren.** Sonst waere der vom
   Auftrag verlangte Zweig `menge_mit_bekannter_person` **tote Kode**: nach
   `bild_art` ist ein Bild mit auch nur einem erkennbaren Gesicht immer
   `gruppe`, nie `menge`. So ist die Vordergrund-Pruefung genau dort wirksam, wo
   der Plan sie verlangt (bekannte Person erkannt → normales Foto), und fuer die
   Pflichtpruefung des Plans (bekanntes Grossgesicht) greift weiter der
   `gruppe`-Zweig.
4. **Gruppen-Kennungen kommen nicht aus dem Katalog.** Ein Katalog-Treffer sagt
   nur „diese Person ist im Bild" (`personen`); die Gruppe selbst bleibt
   `Person_001` … bis der Nutzer bestaetigt („Unbenannt zuerst"). Ein Name aus dem
   Katalog wird gelesen, aber nie geschrieben und nie ausgegeben — belegt durch
   einen Test, der dieselbe Ausgabe mit und ohne Namen im Katalog vergleicht.
5. **Deutsche Bezeichner und deutsche Docstrings** statt englischer: der
   Feinauftrag gibt die Funktionsnamen deutsch vor (`gesichts_anteil`,
   `bild_art`, …) und die Vorlage `foto_sortieren.py` ist durchgehend deutsch.
   Beides auf einmal ging nicht; eine Mischung innerhalb einer Datei waere
   schlechter lesbar als die Fortsetzung des Bestandsstils. Englisch bleibt nur,
   wo es Fachbegriff ist (`embedding`, `bbox`, `score`, `DBSCAN`).
6. **Dateigroesse 1510 Zeilen** statt der Schaetzung 700–1.100: die zehn
   Vorgabefunktionen plus reine Helfer (`cosinus`, `cosinus_matrix`,
   `gesichter_bewerten`, `katalog_personen`, `zeilen_lesen`, `pruefe_ausserhalb_repo`,
   `seiten_dateiname`, `altbestand_*`) und die ausfuehrlichen deutschen Docstrings
   (jede Konstante mit Herkunft) brauchen den Platz. Gekuerzt wurde nichts
   Fachliches.
7. **Zusaetzliche benannte Konstanten**: `CLUSTER_SCHWELLE` (0.45 als
   Cosinus-**Distanz**) und `CLUSTER_MIN_NACHBAR` (3) — der Auftrag laesst
   „Schwelle und min_nachbarn als Parameter mit dokumentiertem Standard" zu; die
   Standards stehen als Konstanten im Modul, damit kein Aufrufer sie setzen muss.
8. **Deckelung bei 1.0** in `gesichts_anteil` (eine kaputte Box kann nicht mehr
   als das ganze Bild sein) und **Deckelung der Cosinus-Werte** auf [−1, 1]
   (Rundungsrauschen). Beides ist eine Entscheidung und in Tests festgehalten.
9. **`cosinus` und `cosinus_matrix` sind eigene Funktionen** (nicht im Auftrag
   genannt), weil Katalog-Treffer, Clustern und Kennungsvergleich dieselbe
   Rechnung brauchen — einmal tolerant implementiert (ungleiche Laenge,
   Nullvektor, Nicht-Zahlen → `0.0` statt Ausnahme) statt dreimal.


## Prüfer-Runde 1 (fremde Modellfamilie) — Beanstandung und Korrektur

Der Prüfer (`openai/gpt-5.6-luna`) hat den Prüfbefehl selbst gefahren
(**1095 passed, Exit 0**), die Zeilenzahlen und die 216 Testfunktionen
nachgezählt, die zehn Funktionen und die benannten Konstanten bestätigt, die
Verbote am Quelltext geprüft (keine Lösch-, Netz- oder pCloud-Funktion, kein
Vektor-Dump), den Repo-Schutz live nachgestellt und eine **eigene** synthetische
Stichprobe (eigener Seed, 8 Cluster) gerechnet: **8/8 Gruppen gefunden, 0 falsch
zusammengelegt, 0 übersehen, Rauschen verworfen, Massenbild `clustern: False`,
dasselbe Bild mit großem Katalog-Gesicht `clustern: True, personen:
["Person_003"]`, zweiter CLI-Lauf 0 neue Seiten und dieselben Kennungen.**

**Eine Beanstandung, berechtigt:** der Name des Repo-Eigners stand an fünf
Stellen der neuen Dateien (Werkzeug Zeile 7 und 1021, Changelog Zeile 64, 154,
199) — mein Feinauftrag verbietet Personennamen in Code, Tests und Doku
wörtlich. **Korrigiert:** ersetzt durch „der Nutzer"/„die Fotos des Nutzers".
Zum Einordnen, ohne die Beanstandung zu entkräften: betroffen war **nur der
Eigner-Name** (er steht in `AGENTS.md`/`CLAUDE.md` projektweit), **keine
fotografierte Person**; in den Tests kommt kein Name vor.

Gegenstand der verschärften Prüfung in Runde 2: **keine Namen Dritter**,
namentlich keine fotografierte Person, kein Ort, kein Ereignis — und der Zweig
`menge_mit_bekannter_person` ist **erreichbar**, nicht tote Kode (Test
`test_menge_mit_bekannter_kleiner_person_wird_geclustert`, Assertion Zeile 352).

**Prüfer-Runde 2 (frischer Kontext, verschärftes Kriterium): BESTANDEN —
„Abweichungen: keine."** Er hat den Prüfbefehl selbst gefahren (1095 passed,
Exit 0), die Korrektur nachgezählt (`Sebastian` 0 Treffer) und die volle
Namensprüfung gefahren: 50 Vornamen, Städte/Regionen, Veranstaltungsnamen,
Bestandsordner-Muster — **überall 0 Treffer**. Er hat bestätigt, dass der Test
`test_menge_mit_bekannter_kleiner_person_wird_geclustert` (Zeile 343, Assertion
352) die **öffentliche** Funktion `bild_entscheidung` aufruft (Zeile 349) und
der Zweig im Werkzeug in Zeile 625–628 liegt; isolierter Lauf `1 passed,
215 deselected`, Exit 0. Zeilen nachgezählt: Werkzeug 1510, Tests 1590,
Changelog 225. Die synthetische Stichprobe wird an keiner Stelle als echte
Messung ausgegeben.

## Erzeugte Nebendateien (nicht im Repo, keine Inhaltsoaenderung)

* `C:/Users/sebas/foto_sortierung/personen_probe/` — synthetische Vektordatei,
  Wahrheitsdatei, `seiten/` mit 14 Referenzseiten und `kennungen.json`.
  Alles **ausserhalb** des Repos, wie verlangt.
* `backend/.pytest_cache/` — Cache von pytest selbst, beim gefahrenen
  Pruefbefehl neu geschrieben (steht **nicht** in `.gitignore`);
  `__pycache__/` steht in `.gitignore` und ist damit unkritisch.
  Inhalte des Repos wurden nicht angefasst.

## Was offen bleibt (N9b)

* Echte Erkennung: Modelle auf den PC holen bzw. auf dem Handy rechnen,
  `cv2`/`onnxruntime` in **eigenem** venv (das Projekt-venv mit den 1095 gruenen
  Tests bleibt unberuehrt).
* `kachel_holen` an den echten Weg anstecken (pCloud-Download oder Handy-Crop),
  damit die Referenzseiten echte Gesichter zeigen.
* Kennungen bleiben `Person_001` … bis der Nutzer sie benennt; das Umbenennen ist
  noch nicht gebaut (der Altbestand traegt nur die Kennung, keinen Namen).
