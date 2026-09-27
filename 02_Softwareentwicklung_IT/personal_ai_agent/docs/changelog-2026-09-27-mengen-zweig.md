# Changelog 27.09.2026 — Mengen-Zweig erreichbar + Gesichtsausschnitt-Kachel (N9c)

Auftrag: `docs/auftrag-n9c-mengen-zweig.md` (Teile 1–4). Ausführer: Hermes-Subagent
(Codex gesperrt). **Keine** git-Befehle ausgeführt — committet wird vom Planer.

## Ergebnis in drei Zeilen

1. `ANTEIL_MIN` ist von `0,0005` auf `0,00001` gesenkt; **keine** andere Schwelle angefasst.
2. Der Zweig `menge` ist am echten Bestand **erreicht**: 1 von 30 Bildern (`56226986656`,
   13 kleine Gesichter). Vorher: 0 von 30. Nicht schöngeredet — es ist **ein** Bild.
3. `kachel_quelle` kann jetzt in-memory einen **Gesichtsausschnitt** liefern (nur PIL,
   `ausschnitt=True`, Rand `0,45`, Ziel 200×200); 7 Referenzseiten mit 54 echten
   Ausschnitten gebaut, zweiter Lauf **0** Dateien.

## Prüfbefehl (selbst gefahren)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

* Baseline vor dem Schritt: **1175 passed**
* Nach dem Schritt: **1196 passed, Exit-Code 0** (72 s, nur die drei bekannten
  Pydantic-/starlette-Warnungen)

## Teil 1 — `ANTEIL_MIN` (`tools/foto_sortierung/personen_cluster.py`)

* `ANTEIL_MIN`: `0,0005` → **`0,00001`**. Kommentar/Docstring ehrlich umgeschrieben:
  das Flächen-Tor ist **kein Rausch-Tor** (das ist `MIN_SCORE = 0,6`), es verwirft nur
  noch **entartete Boxen** (Breite/Höhe ~ 0). Herleitung als Kommentar mit den
  Beleg-Zahlen **0,000145** (kleinste echte Detektion der Vormessung, 13 kleine
  Gesichter) und **0,000022** (kleinste echte Detektion des Nachtlaufs N9b, 16×22 px),
  beide lagen unter dem alten Tor.
* 0,00001 der Fläche sind bei 4032×3024 = 12,2 MP rund 122 px ≈ 11×11 px — praktisch
  YuNets eigene Mindest-Box (10×10 px).
* Wertgleich geblieben (Test `test_nur_das_flaechen_tor_wurde_gesenkt` nagelt das fest):
  `MIN_SCORE 0.6`, `ANTEIL_ERKENNBAR 0.005`, `MENGE_ANZAHL 6`, `KATALOG_SCHWELLE 0.363`,
  `CLUSTER_SCHWELLE 0.45`, `CLUSTER_MIN_NACHBAR 3`, `ALT_SCHWELLE = KATALOG_SCHWELLE`.
  `MENGEN_PARAMS` zieht den neuen Wert automatisch nach (`anteil_min = 1e-05`).

## Teil 2 — Gesichtsausschnitt (`tools/foto_sortierung/gesicht_erkennen.py`)

* Neu `AUSSCHNITT_RAND = 0.45`, `AUSSCHNITT_GROESSE = (200, 200)`.
* Neu **`ausschnitt_rechnen(bbox, breite, hoehe, rand=0.45)`** → `(x0, y0, x1, y1)|None`.
  Rein rechnend: kein PIL, kein cv2, kein I/O. Rand = `rand` × bbox-Maß je Seite
  (Breite links/rechts, Höhe oben/unten), dann Klemmung an die Bildgrenzen.
  `None` bei unbrauchbarer `bbox`, Bildmaßen ≤ 0, Box-Breite/-Höhe ≤ 0 und entartetem
  Ausschnitt (nach dem Klemmen kein Pixel übrig); unbrauchbares `rand` fällt still auf
  `AUSSCHNITT_RAND` zurück.
* `kachel_quelle(service, max_bytes=…, groesse=None, ausschnitt=False, rand=0.45)`:
  bei `ausschnitt=True` und brauchbarer `bbox` im Eintrag wird **in-memory** geschnitten
  und auf `groesse` bzw. `AUSSCHNITT_GROESSE` skaliert (JPEG, Qualität 85). **Nur PIL**,
  kein `cv2`, kein Netz, **kein** Schreiben auf die Platte.
* **Rückfall statt Abbruch:** fehlender/krummer `bbox`, unlesbare Bytes, entarteter
  Ausschnitt oder fehlendes PIL → **ganzes Foto** wie bisher; es dringt nie eine Ausnahme
  nach außen (Test mit `b"kein bild"`).
* CLI: Schalter **`--ausschnitt`** in `main()`; die Ausgabe nennt in Klartext
  „Gesichtsausschnitt je Gesicht — Ziel 200x200 px, Rand 0.45 x bbox, nur PIL, in-memory
  (Rueckfall ohne bbox/bei Fehlern: ganzes Foto)" bzw. „ganzes Foto (in-memory
  verkleinert)". Standard bleibt **ganzes Foto** (Trockenlauf unverändert).
* Modul-Docstring ergänzt (der Ausschnitt ist in-memory/PIL, kein Zwischenbild).

**Verdrahtungshinweis (offen für den Nachtlauf):** `kachel_quelle` liest das Feld
`fileid`; die Kachel-Einträge aus N9a tragen die fileid als **`bild_id`**. Beim Verdrahten
muss also gemappt werden (im Beleg unten außerhalb des Repos so gemacht, das Modul wurde
dafür **nicht** angefasst).

## Teil 3 — Echte Messung (nur lesend, nichts im Repo)

Alle Belege liegen **außerhalb** des Repos unter `C:/Users/sebas/foto_sortierung/`
(`n9c_lauf_neu.txt`, `n9c_belege.txt`, `n9c_ausschnitt.txt`, Hilfsskripte
`n9c_belege.py`, `n9c_ausschnitt_seiten.py`).

### 3a) Vormessung des Planers wiederholt (`n9c_probe.py`, dieselben 30 Bilder)

30 Bilder aus den fünf bilderstärksten Mengen-Anlässen (zwei Themen-Buckets),
**95,9 s, 0 Fehler**:

| ANTEIL_MIN | Bild-Art über 30 Bilder |
|---|---|
| **0,0005 (alt)** | `gruppe 12 · leer 9 · unklar 9 · menge 0` |
| 0,0001 | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| 0,00005 | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| 0,00002 | `gruppe 12 · leer 6 · unklar 11 · menge 1` |
| **0,00001 (neu)** | `gruppe 12 · leer 6 · unklar 11 · menge 1` |

Das **deckt sich Zeile für Zeile** mit der Vormessung des Planers (Sollwerte erreicht,
keine Abweichung). `gruppe` bleibt über alle Kandidaten **12** → keine Regression.

### 3b) Vorher/Nachher am selben Bestand (`n9c_belege.py`, dieselben 30 Bilder, 86,8 s, 0 Fehler)

* **Vorher** (`params={"anteil_min": 0.0005}`, reine Rechnung, kein zweiter Download):
  `{'gruppe': 12, 'leer': 9, 'unklar': 9}` — `menge 0`.
* **Nachher** (`ANTEIL_MIN = 1e-05`): `{'gruppe': 12, 'leer': 6, 'menge': 1, 'unklar': 11}`.
* Genau **4 Bilder** ändern ihre Art:
  * `56226986656` `unklar → menge` — **das menge-Bild**: 4032×3024, **13 Gesichter**,
    13 nutzbar / 0 erkennbar, kleinster Flächenanteil **0,000145**, größter 0,001911
    (alle < `ANTEIL_ERKENNBAR` 0,005) → `clustern=False`,
    `grund=menge_ohne_bekannte_person`.
  * `56226031437` `leer → unklar` (3 nutzbar, 0 erkennbar)
  * `56226986963` `leer → unklar` (1 nutzbar)
  * `56226987597` `leer → unklar` (5 nutzbar)
* Die 12 `gruppe`-Bilder sind identisch vorher/nachher; nur die Zahl **nutzbarer** kleiner
  Gesichter steigt (z. B. `56227009840` 8 → 11 nutzbar), die Art kippt dort **nicht**.

### 3c) Referenzseiten mit `--ausschnitt` (`~/foto_sortierung/personen_echt_ausschnitt/`)

Gerechnet mit den vorhandenen 24 Vektorzeilen aus N9b (`je_art = leer 5 · gruppe 12 ·
unklar 7 · menge 0`), Gruppen `[14, 40]` Kacheln:

| Seite | Bytes |
|---|---|
| `Person_001_seite_01.jpg` | 71.883 |
| `Person_001_seite_02.jpg` | 35.453 |
| `Person_002_seite_01.jpg` | 99.772 |
| `Person_002_seite_02.jpg` | 96.057 |
| `Person_002_seite_03.jpg` | 98.013 |
| `Person_002_seite_04.jpg` | 80.820 |
| `Person_002_seite_05.jpg` | 70.445 |

* **Anzahl Seiten: 7**, Gesamtbytes **552.443**, Lauf 1: 101,5 s.
* **54 Kacheln** — alle als **Ausschnitt 200×200** geliefert, 0 leer, 0 andere Größe.
* **Zweiter Lauf: 0 neue Dateien** (Idempotenz belegt), 0,0 s.
* Gegenprobe auf Pixel: erster Kachel-Eintrag `bild_id 93174879840`,
  `bbox [1308.9, 1265.0, 520.6, 603.2]`, Original 4096×3072, gerechnete Grenzen
  `(1074, 993, 2064, 2140)`; gelieferter Ausschnitt und unabhängig nachgerechneter
  Ausschnitt stimmen in der Form überein, `max_pixel_diff = 33` (JPEG-Qualität 85 im
  Zwischenschritt — kein Abbildungsfehler, aber ehrlich: der Vergleich ist nicht bitgenau).
  **Ohne** `--ausschnitt` kommt für dasselbe Bild eine andere Kachel (7.984 Bytes,
  ungleich dem Ausschnitt).
* Platzhalter-Gegenprobe: die Kachel (0,0) der Seite hat `std = 50,5` (echter Bildinhalt),
  ein Platzhalter wäre flächig grau (200, 200, 200).
* **Kein Original auf Platte:** außerhalb des Ausgabeordners entstand **keine** neue
  Bilddatei, im Repo **keine** (per `find -newermt` geprüft);
  `manifest.jsonl` existiert weiterhin **nicht** → **0 Einträge**. Keine schreibende
  pCloud-Operation, keine Löschfunktion berührt.

## Teil 4 — Tests

`backend/tests/test_personen_cluster.py`:
* `test_bild_art_staub_zaehlt_nicht_als_gesicht` (nagelte 20×20-Boxen als „Staub" fest)
  ist **ersetzt, nicht gelöscht** durch **drei** Tests, die die **Regel** prüfen:
  `test_bild_art_entartete_boxen_zaehlen_nicht_als_gesicht` (Kantenlänge aus
  `ANTEIL_MIN` und Bildfläche gerechnet, also relativ zur Konstante),
  `test_bild_art_sieht_nur_noch_entartete_boxen_als_zu_klein` (alte 0,0005 über `params`
  gegengerechnet: damals `leer`, heute `menge` — das ist die Vorher/Nachher-Probe),
  `test_anteil_min_verwirft_keinen_echten_fund_mehr` (`0 < ANTEIL_MIN ≤ 0,000022` und
  `≤ 0,000145` — die Beleg-Zahlen als Zusage).
* Neu `test_nur_das_flaechen_tor_wurde_gesenkt` (alle übrigen Schwellen wertgleich,
  `ANTEIL_MIN = 0.00001`, `MENGEN_PARAMS` zieht nach).

`backend/tests/test_gesicht_erkennen.py` (Abschnitt 7b, alles offline, `tmp_path`, kein
Netz, kein `cv2`, keine echten Namen):
* Geometrie: Rand je Seite, `rand=0` = die Box selbst, Klemmung an beide Bildgrenzen,
  `None` bei entarteter Box (außerhalb/Nullbreite/negative Höhe) und unbrauchbarer Eingabe
  (None, falsche Länge, Nicht-Zahl, `bool`, Bildmaß ≤ 0), unbrauchbares `rand` → Vorgabe.
* `ausschnitt_rechnen` ist **rein** (AST-Prüfung: kein `cv2`/`Image`/`open`/`read`/`write`),
  der Ausschnitt-Weg läuft **ohne `cv2`** (AST beider Funktionen ohne Docstring).
* `kachel_quelle(ausschnitt=True)`: quadratische 200×200-Ausgabe, **inhaltlich** der
  Gesichtsausschnitt (zweifarbiges Testbild: der rote Block liegt im Ausschnitt, das Blau
  nicht mehr), Rückfall aufs ganze Foto ohne/krummen `bbox` und bei kaputten Bytes
  (keine Ausnahme dringt nach außen), `None` ohne Dienst, **kein** Schreiben ins Repo
  (Ordnerinhalt vor/nach gleich), Zusammenspiel mit `referenzseiten_bauen`.
* CLI: `--ausschnitt` im Trockenlauf (Exit 0, nichts geschrieben); Quelltext nennt den
  Modus in Klartext.

## Offen / nicht behauptet

1. **Der Zweig `menge` ist an 1 von 30 Bildern erreicht** (13 kleine Gesichter). Das ist
   das Prüfkriterium („1 von 30 ist in Ordnung"), aber es ist **ein** Bild — kein Beleg
   dafür, dass Mengen-Bilder generell greifen. `MENGE_ANZAHL = 6` ist unverändert und
   braucht weiterhin eine eigene Messung.
2. Die Referenzseiten (3c) sind mit den **24 Vektorzeilen aus N9b** gerechnet — die tragen
   noch den alten Stand. Für den echten Mengen-Nachweis muss der Vektorlauf (N9b) mit dem
   neuen `ANTEIL_MIN` wiederholt werden; in dieser kleinen Stichprobe entsteht dabei
   ohnehin kein `menge`-Bild (`je_art = leer 5 · gruppe 12 · unklar 7 · menge 0`), es
   werden nur mehr kleine Boxen nutzbar.
3. `--ausschnitt` in `gesicht_erkennen.main` wirkt nur, wenn der Eintrag eine `bbox` trägt;
   im Vektorzeilen-Lauf wird nur `fileid` übergeben, dort bleibt es also beim **ganzen
   Foto** (bewusst, sonst würde vor der Detektion beschnitten). Der Nutzen liegt bei den
   Referenzseiten (N9a) — siehe Verdrahtungshinweis in Teil 2.
4. Pixel-Gegenprobe ist nicht bitgenau (JPEG 85 im Zwischenschritt, `max_pixel_diff 33`).
5. Kein Commit, kein `git add`, kein Push — das macht der Planer nach der Abnahme.
