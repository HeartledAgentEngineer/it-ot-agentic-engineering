# Changelog N9d — Verdrahtung der N9a-Kennung und ehrliche `--ausschnitt`-Ausgabe

Datum: 27.09.2026
Schritt: N9d (Verdrahtung) zu `tools/foto_sortierung/gesicht_erkennen.py`
Status: umgesetzt und geprueft (pytest Exit 0)

## Wozu

Der Befund aus N9c: die echte Kachelquelle las nur das Feld `fileid`, die
N9a-Eintraege (`personen_cluster.py`) tragen ihre Kennung aber als `bild_id`
(und die Gesichtsbox als `bbox`). Deshalb musste ein Beleg-Skript ausserhalb des
Repos das Feld `bild_id` -> `fileid` umkopieren. Ausserdem behauptete die
Ausgabe von `main()` bei `--ausschnitt`, es wuerde je Gesicht geschnitten —
obwohl im Vektorzeilen-Lauf nur die Kennung uebergeben wird.

## Aenderungen (nur `tools/foto_sortierung/gesicht_erkennen.py` + Tests + diese Doku)

1. **`_fileid_von(eintrag)` erweitert.** Vorrang `fileid`, sonst `bild_id`
   (Text oder Zahl, kein `bool`, kein `None`). Ein blanker Eintrag
   (`kachel_holen("1234567")`) gilt weiter. Damit arbeiten die N9a-Eintraege
   **direkt** — kein Um-Mappen mehr.
2. **Docstrings korrigiert** (Modulkopf und `kachel_quelle`): die N9a-Eintraege
   tragen `bild_id` + `bbox`, die Kachelquelle arbeitet damit direkt; ohne
   brauchbare `bbox` faellt `ausschnitt=True` aufs ganze Foto zurueck. Auch der
   `--ausschnitt`-Hilfetext sagt das jetzt.
3. **Ehrliche Ausgabe.** Neue reine Funktion
   `kachelquelle_hinweis(ausschnitt: bool) -> str` baut die Ausgabezeile; sie
   ersetzt in `main()` die bisherige Behauptung. `kachelquelle_hinweis(True)`
   sagt klar: im **Vektorzeilen-Lauf** ist vor dem Download **keine** `bbox`
   bekannt, `--ausschnitt` wirkt dort **nicht**; wirklich je Gesicht geschnitten
   wird im **Referenzseiten-Weg von `personen_cluster`**, wo die Eintraege
   `bild_id` und `bbox` tragen. `kachelquelle_hinweis(False)` beschreibt den
   Download des ganzen Fotos.

## Wo `--ausschnitt` wirkt (und wo nicht)

* **Wirkt nicht:** Vektorzeilen-Lauf von `gesicht_erkennen.main()` — dort wird
  vor dem Download nur die Kennung uebergeben, eine `bbox` entstuende erst
  **nach** dem Download aus der Detektion.
* **Wirkt:** Referenzseiten-Weg von `personen_cluster.referenzseiten_bauen` —
  dort ruft `kachel_holen` je Kachel auf, und die Eintraege tragen `bild_id`
  und `bbox`; die Kachelquelle schneidet dann in-memory (nur PIL).

## Tests

Neu in `backend/tests/test_gesicht_erkennen.py` (Abschnitt 7c, offline, kein
Netz, kein `cv2`, Bilder mit PIL in-memory):

* `test_fileid_von_liest_bild_id_als_text_und_zahl`
* `test_fileid_von_lehnt_bool_und_none_ab`
* `test_fileid_von_fileid_hat_vorrang`
* `test_kachel_quelle_reicht_bild_id_als_kennung_durch`
* `test_kachel_quelle_ausschnitt_schneidet_n9a_eintrag_wirklich`
* `test_kachel_quelle_bild_id_ohne_bbox_ganzes_foto`
* `test_kachelquelle_hinweis_ausschnitt_nennt_vektorzeilen_lauf`
* `test_kachelquelle_hinweis_ohne_ausschnitt_ganzes_foto`
* `test_kachelquelle_hinweis_ist_rein`

Angepasst (ehemals auf die alte Ausgabezeile geprueft):
`test_quelle_nennt_die_kachelquelle_in_klartext` prueft jetzt, dass
`main` die Funktion aufruft und die falsche Behauptung
(„Gesichtsausschnitt je Gesicht") **nicht mehr** im Quelltext steht.

## Schutz

Keine Schwellen geaendert (`ANTEIL_MIN`, `MIN_SCORE`, `MENGE_ANZAHL`,
`ANTEIL_ERKENNBAR`, `AUSSCHNITT_RAND`, `AUSSCHNITT_GROESSE` wertgleich). Kein
`cv2`, kein Netz, keine neue Abhaengigkeit, kein Loeschen, kein Schreiben von
Bildern. Keine echten Ordner-/Personen-/Orts-/Ereignisnamen; Testkennungen wie
`1234567` sind erfunden.

## Breite Messung (echte Bilder, nur lesend)

Stichprobe: **92 Bilder** — 80 aus den acht bilderstaerksten Mengen-Anlaessen
(je bis zu 10), dazu **12 Kontrollbilder** aus gewoehnlichen Anlaessen.
Erkennung YuNet+SFace, Originale nur im Arbeitsspeicher: **465 Gesichter,
72 Bilder mit Gesicht, 0 Fehler, 358,9 s**. Kleinster echter Flaechenanteil
**6,8905172548596356e-06**, groesster **0,030437**.

| ANTEIL_MIN | alle 92 Bilder | nur die 80 Mengen-Bilder |
|---|---|---|
| 0,0005 (alt) | gruppe 32 · leer 27 · **menge 4** · unklar 29 | menge **4 von 80 = 5,0 %** |
| 0,00001 (neu) | gruppe 32 · leer 20 · **menge 10** · unklar 30 | menge **10 von 80 = 12,5 %** |

Die **12 Kontrollbilder** ergeben in **beiden** Schwellen **0 × `menge`**
(gruppe 4, leer 7, unklar 1) — das Mengen-Tor greift also nur dort, wo es soll.
`gruppe` bleibt mit **32** in beiden Schwellen gleich (keine Regression).

## Verdrahtung live belegt (N9a-Eintraege direkt)

`kachel_quelle(..., ausschnitt=True)` wird **ohne Um-Mappen** mit den
N9a-Eintraegen aufgerufen (`bild_id` + `bbox`, kein `fileid` im Eintrag):

* **24 Referenzseiten**, **186 Kacheln als 200×200-Ausschnitt**, 3 leere
  Kacheln (Download-Fehler → Platzhalter), 0 anders dimensionierte,
  Gesamtbytes der Seiten **1.749.798**; **2. Lauf 0 neue Dateien** (idempotent).
* Pixel-Gegenprobe an vier Kacheln: Unterschied zum frisch gerechneten
  Ausschnitt **1,755 … 3,116** (das ist der JPEG-Verlust, quality 85), zum auf
  Kachelgroesse verkleinerten **ganzen Foto** dagegen **68,954 … 76,192** —
  die Kachel zeigt also wirklich den Gesichtsausschnitt, nicht das ganze Foto.

## Offener Nebenbefund (nicht Teil dieses Schritts)

Das DBSCAN-artige Clustering (`vektoren_clustern`, Dichte-Verfahren mit
`CLUSTER_SCHWELLE = 0,45`) buendelt die **189** nutzbaren Gesichter der
`gruppe`-Bilder zu **einer einzigen** Gruppe. Fuer ein dichte-basiertes
Verfahren ist Verkettung erwartbar, am echten Bestand ist die Schwelle aber
**nicht** mit Bodenwahrheit geprueft (der synthetische N9a-Test trennte 12
Cluster sauber). Schwellen sind N9a-Beschluesse und wurden hier **nicht**
angefasst → als Kandidat **N9e** notiert.

## Pruefer-Runde 1 (frischer Kontext, andere Modellfamilie) — NICHT BESTANDEN, behoben

Beanstandet wurden drei Punkte:

1. **Belegskript loeschte den eigenen Ausgabeordner** (`shutil.rmtree`).
   Berechtigt nach der Nachtlauf-Regel „NIE loeschen": das Skript legt jetzt
   **nichts mehr an, was es ueberschreiben muesste**, sondern **verweigert**
   einen nicht leeren Zielordner mit deutscher Meldung und **Exit 2**
   (nachgemessen: 24 Dateien vor und nach dem Aufruf, nichts geloescht). Der
   Lauf wurde in einen **frischen** Ordner wiederholt und lieferte dieselben
   Zahlen (24 Seiten, 186 Kacheln 200×200, 3 leer, 1.749.798 Bytes,
   2. Lauf 0 neue Dateien); der alte Ordner blieb unberuehrt.
2. **`manifest.jsonl` fehlte** — die Formulierung „weiterhin 0 Eintraege" war
   falsch: die Datei **existiert nicht**, weil in diesem Schritt **nichts**
   gebucht wurde. Richtig ist: keine Buchung, kein Manifest-Eintrag.
3. **Modulkopf-Docstring geaendert** — lag im Auftrag („Docstrings von
   Modulkopf und `kachel_quelle` korrigieren"), war in der Auftragsbeschreibung
   an den Pruefer aber nicht ausdruecklich genannt. Beide Docstrings sind
   inhaltlich richtig und die Schwellenwerte wertgleich zu HEAD.

Der Pruefer hat unabhaengig bestaetigt (Zahlen aus der JSONL selbst
nachgerechnet): 1205/Exit 0, 92 Zeilen, 465 Gesichter, 72 mit Gesicht,
Minimum `6.8905172548596356e-06`, Bildarten beider Schwellen, 12,5 %,
Kontrollbilder 0 × `menge`, 24 Seiten/186 Kacheln/1.749.798 Bytes, zweiter Lauf
0 neue Dateien, die vier Pixel-Differenzen, `_fileid_von` in sieben Faellen,
keine Schwellenaenderung, kein `or True`, keine Secrets, keine geloeschten
Dateien.

## Pruefer-Runde 2 (frischer Kontext) — NICHT BESTANDEN, zwei Punkte behoben, einer Fehlalarm

1. **`n9c_ausschnitt_seiten.py:39` hatte noch `shutil.rmtree`** (aeltere
   Belegdatei aus N9c, nicht aus diesem Schritt). Berechtigt: behoben wie beim
   N9d-Skript — ein nicht leerer Zielordner wird **verweigert** (deutsche
   Meldung, **Exit 2**), Zielordner per Argument waehlbar. Nachgemessen:
   **7 Dateien vor und nach** dem Aufruf, nichts geloescht, `shutil` ist
   entfernt. Damit gibt es im ganzen Foto-Werkzeugsatz nur noch **eine**
   Loeschoperation: `os.remove(temp)` auf die **eigene temporaere Datei** beim
   atomaren Schreiben (`foto_kategorien.py:641`) — fremde Daten werden nirgends
   geloescht.
2. **„echte personenbezogene Namensnennung" im Plan** — Fehlalarm, mit Zahlen
   belegt: `docs/plan-nachtlauf-2026-09-26.md` enthaelt den Eigner-Namen
   **26 × im HEAD-Stand, 26 × im Arbeitsstand und 0 × in den neu hinzugefuegten
   Zeilen** (`git diff -U0 | grep '^+' | grep -c` = 0). Es ist der Plan, der
   den Auftrag des Eigners im Wortlaut zitiert — kein Name einer fotografierten
   Person, kein Ort, kein Ereignis; derselbe Fall wie in der N9a-Runde. Der
   Bestand wird **nicht** umgeschrieben.
3. **Aufruf mit globalem `python` endet mit Exit 1** (`pydantic_settings`
   fehlt) statt mit der Verweigerung — das ist der in `CLAUDE_EXTENDS.md`
   beschriebene **Aufruf-Fehler** (Pruefbefehle gehoeren ans Projekt-venv),
   kein Fehler des Skripts. Beide Belegskripte nennen im Kopf jetzt den
   vorgesehenen Aufruf mit `venv_gesicht` (dort liegen cv2/onnxruntime).
