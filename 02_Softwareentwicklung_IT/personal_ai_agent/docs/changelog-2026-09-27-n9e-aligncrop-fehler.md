# Changelog 27.09.2026 — N9e: der Personen-Vektor war ein Bild-Vektor (Fehler in `alignCrop`) + neue Schwelle-Messung

> **Schritt:** N9e (Plan `docs/plan-nachtlauf-2026-09-26.md`) — „Cluster-Schwelle am
> echten Bestand prüfen" (Kandidat aus dem N9d-Nebenbefund).
> **Ergebnis:** Der Befund, der N9e ausgelöst hat, war **kein Clustering-Effekt,
> sondern ein Fehler in der Merkmalberechnung**. Er ist gefunden, behoben, gegen
> einen Wächter abgesichert — und die Schwelle-Messung wurde mit richtigen
> Vektoren wiederholt.

## 1. Der Befund, der den Schritt ausgelöst hat

N9d meldete: „das Clustering bündelt die **189** nutzbaren Gesichter der
`gruppe`-Bilder zu **einer** Gruppe." Das stand als Kandidat N9e im Plan
(Schwellen-Verkettung, Dichte-Verfahren).

## 2. Die Ursache (gemessen, nicht vermutet)

`cv2.FaceRecognizerSF.alignCrop(bild, face_box)` erwartet die **volle
15-Werte-Zeile der Detektion** `[x, y, w, h, 10 Landmarken-Werte, score]`
(60 Byte). An drei Stellen wurde nur das 5×2-Landmarken-Array (40 Byte)
übergeben — OpenCV prüft die Form nicht, liest 20 Byte über den Puffer hinaus,
die Landmarken sind Müll, und **jedes Gesicht EINES Bildes bekommt denselben
Ausschnitt und damit denselben Vektor**.

Belegte Messung (Bild `56226031402`, 1112×2048, 6 Gesichter, nur lesend,
Original nur im Arbeitsspeicher):

| Aufruf | Ausschnitt-Prüfsumme (sha1[:12]) | Ausschnitt-Mittelwert | Merkmal (erste 4 Werte) |
|---|---|---|---|
| `alignCrop(bild, landm)` (5×2, 40 Byte) | **6× dieselbe** `e06d30ef365c` | **0,00 (schwarz)** | 6× `[-0.07192, 0.01178, 0.10788, -0.1486]` |
| `alignCrop(bild, zeile)` (15 Werte, 60 Byte) | 6 **verschiedene** (`6dc1f580d47b`, `e8f9b7cfb09a`, `472f169a79e1`, `1534caa50aa6`, `ae3e96452b09`, `68b954bffc1e`) | 103–158 | 6 verschiedene |

**Mechanik:** die Landmarken sind Müll (meist Nullen) → `alignCrop` liefert ein
**schwarzes** 112×112-Bild → `feature()` darauf ist **konstant** → alle Gesichter
eines Bildes tragen denselben Vektor.

**Harter, wiederholbarer Beleg für den Übergriff** (kontrollierter Puffer, damit
der gelesene Speicher bekannt ist): legt man die 10 Landmarken-Werte als **Sicht**
in einen größeren Puffer und füllt die vier Werte dahinter mit bekannten Zahlen,
so ist der Ausschnitt der alten Aufrufform **bit-identisch** (`e1857be02379`)
mit der Zeile, die man aus genau diesen gemischten Werten nachbaut — OpenCV liest
also nachweislich **vier Werte über das Ende hinaus**. Die korrekte Form liefert
dazu einen anderen Ausschnitt (`6dc1f580d47b`, Mittel 158,21 gegen 0,14).

**Ehrliche Einschränkung (vom Prüfer zurecht beanstandet):** *welcher* Müll
gelesen wird, hängt vom Speicherinhalt ab — in einem Lauf des Prüfers lieferte
die alte Form pro Gesicht **verschiedene** Ausschnitte. Der Übergriff ist damit
**nicht deterministisch in seinen Werten**, aber in seiner Wirkung: die alte
Aufrufform schneidet **nie** das Gesicht (in beiden gespeicherten Messdateien:
100 % der Mehrgesicht-Bilder mit identischen Vektoren).

**Folge (an den gespeicherten Dateien nachgewiesen):**

* `personen_vektoren_n9d.jsonl` (N9d): 465 Gesichter → **72 verschiedene
  Vektorwerte** (= genau die Bilder mit Gesicht); **57 von 57** Bildern mit mehr
  als einem Gesicht hatten nur identische Vektoren.
* `personen_vektoren.jsonl` (N9b): 72 Gesichter → **8 Werte**; **15 von 15**.
* Zwei verschiedene Personen im selben Bild hatten damit Cosinus-Distanz
  **exakt 0,0000** (131 von 131 Paaren erkennbarer Gesichter im selben Bild).

**Damit sind die Personen-Ergebnisse aus N9b und N9d ungültig** — „2 Gruppen
(6 und 40)", „189 Gesichter → EINE Gruppe", die 6 Referenzseiten: sie messen den
Fehler, nicht das Clustering. Die Plan-Zeilen N9b/N9d sind entsprechend
korrigiert.

## 3. Der Fix

* `tools/foto_sortierung/gesicht_erkennen.py`: `_merkmal` und
  `gesichter_mit_detektor` übergeben die **volle 15-Werte-Zeile**; Zeilen mit
  weniger als 15 Werten werden übersprungen.
* `backend/face_infer.py`: `_align_face` nimmt die Zeile statt der Landmarken;
  die Aufrufer (`_embed_crop_pixels`, `op_embed`) ziehen mit — **auch der
  Produktionsweg war betroffen**.
* **Wächter:** kommen bei einem Bild mit ≥2 Gesichtern **bit-identische**
  Merkmale heraus, ist das ein Fehlersignal — deutsche Meldung im Feld
  `fehler`, leere Gesichtsliste, **kein stiller Durchlauf**. Begründung im
  Docstring: zwei verschiedene Ausschnitte liefern nie bitgleiche Merkmale; der
  stille Durchlauf hat den Fehler zwei Nachtläufe lang verdeckt.

## 4. Belege nach dem Fix

**Ende-zu-Ende auf 6 frischen Bildern** (nicht aus der Stichprobe, Live-Erkennung,
Originale nur im Arbeitsspeicher):

```
93175299625  1280x720   Gesichter= 2  verschiedene Vektoren= 2  kleinste Paar-Distanz=0.6921
93175069498  4656x3492  Gesichter= 3  verschiedene Vektoren= 3  kleinste Paar-Distanz=0.4925
93175135336  4656x3492  Gesichter= 2  verschiedene Vektoren= 2  kleinste Paar-Distanz=0.9137
93175004345  1522x2030  Gesichter= 3  verschiedene Vektoren= 3  kleinste Paar-Distanz=0.8520
93174910608  1600x1200  Gesichter= 7  verschiedene Vektoren= 7  kleinste Paar-Distanz=0.8000
93175010405  1600x1200  Gesichter= 5  verschiedene Vektoren= 5  kleinste Paar-Distanz=0.7688
```

**Dieselben 92 Bilder wie N9d, neu gerechnet** (`personen_vektoren_n9e.jsonl`,
Burst-Serien zusätzlich in `personen_vektoren_n9e_burst.jsonl`):

| | N9d (fehlerhaft) | N9e (gefixt) |
|---|---|---|
| Gesichter | 465 | 465 |
| verschiedene Vektorwerte | **72** | **465** |
| Paare erkennbarer Gesichter im selben Bild | 131 | 131 |
| davon Cosinus-Distanz ≈ 0 | **131** | **0** |
| Paar-Distanzen (min / Median / max) | 0,0000 / 0,0000 / 0,0000 | **0,5312 / 0,8280 / 1,0667** |

## 5. Schwelle-Messung mit richtigen Vektoren

Werkzeug `tools/foto_sortierung/personen_schwelle.py` (**neu in dieser Nacht**)
mit zwei getrennten Kennzahlen — ehrlich getrennt, weil nur die erste
Bodenwahrheit ist:

* **Bodenwahrheit (hart):** zwei **erkennbare** Gesichter (Flächenanteil
  ≥ `ANTEIL_ERKENNBAR` = 0,005) im **selben Bild** sind zwei Personen (eine
  Person ist einmal im Bild; Ausnahmen Spiegelung/Plakat/Zwilling im Docstring).
* **Strukturmaß (weich):** „Anlass-Mix je Cluster" — der Anlass ist **keine**
  Identitätswahrheit (ein Anlass enthält legitim viele Personen, dieselbe Person
  kann in mehreren Anlässen vorkommen). Ein Cluster mit mehreren Anlässen ist
  deshalb **kein** Beweis für eine falsche Zusammenlegung.

Messung über die 189 geclusterten Gesichter (Werkzeug-Standardweg,
`n9e_messung_neu.log`):

| Schwelle | Gruppen | größte | verschmolzene Bild-Paare | Quote | Ketten-Paare | Durchmesser |
|---|---|---|---|---|---|---|
| **0,45 (heute)** | 12 | 22 | 0 / 131 | 0,0 % | 0 | 0,9032 |
| 0,40 | 10 | 20 | 0 / 131 | 0,0 % | 0 | 0,7387 |
| 0,35 | 9 | 20 | 0 / 131 | 0,0 % | 0 | 0,7387 |
| 0,30 | 9 | 18 | 0 / 131 | 0,0 % | 0 | 0,7213 |
| 0,20 | 8 | 14 | 0 / 131 | 0,0 % | 0 | 0,6193 |
| 0,15 | 7 | 6 | 0 / 131 | 0,0 % | 0 | 0,2748 |
| 0,10 | 2 | 3 | 0 / 131 | 0,0 % | 0 | 0,1553 |

**Gegenprobe mit denselben Werkzeug auf der alten Datei:** bei 0,45 eine Gruppe
mit 189 Gesichtern, **131 von 131** Bild-Paaren verschmolzen (100 %),
Durchmesser 0,4241 — der Fehler ist damit im Werkzeug sichtbar, nicht nur im
Text.

**Über alle 465 Gesichter gerechnet** (unabhängige Nachrechnung des Planers)
bleibt die Verkettung sichtbar: bei 0,45 **19 Gruppen, größte 85 Gesichter,
Durchmesser 1,0755** — der Durchmesser liegt **über** der Schwelle, also
existiert transitives Verketten weiterhin; es trifft nur **keine** Bild-Paare
mehr (0 von 131 bei jeder Schwelle). Bei 0,15: 11 Gruppen, größte 8,
Durchmesser 0,3226.

**Burst-Serien** (59 Dateien in 6 Familien, dieselbe Szene in
Sekundenabstand): 36 Gesichter, 36 verschiedene Vektoren, 0 Fehler. Im
geclusterten Bestand bleiben 3 Familien (2 mit mehreren Gesichtern, 42 Paare):
**0 von 42** Paaren in derselben Gruppe bei allen acht Schwellen,
Distanz-Median **0,7777**. Ehrliche Folge: die Burst-Serie ist hier **kein**
Identitätsbeleg (Szenenaufnahmen mit fremden Personen) — das Maß steht deshalb
ausdrücklich weich im Docstring, nicht als Bodenwahrheit.

## 6. Entscheidungen (statt Fragen)

1. **Keine Schwellenänderung.** `CLUSTER_SCHWELLE` (0,45), `ANTEIL_MIN`
   (0,00001), `MENGE_ANZAHL` (6), `CLUSTER_MIN_NACHBAR` (3) bleiben wertgleich.
   Eine Absenkung ist **nicht belegt**: die verschmelzenden Bild-Paare sind bei
   allen acht Schwellen 0 — es gibt kein falsch zusammengelegtes Paar, das eine
   niedrigere Schwelle retten müsste.
2. **Wächter lieber streng als still:** ein auffälliges Bild fällt bewusst
   komplett heraus (leere Liste + `fehler`), statt unbrauchbare Vektoren zu
   liefern.
3. **Der Anlass wird umbenannt, nicht gelöscht:** er bleibt als Strukturmaß
   erhalten, wird aber nicht mehr als Bodenwahrheit bezeichnet.

## 7. Was offen bleibt (ehrlich)

1. **Die Personen-Ergebnisse aus N9b und N9d müssen neu gerechnet werden** (mit
   `personen_vektoren_n9e.jsonl`): Gruppen-Anzahl, Referenzseiten,
   Kennungs-Altbestand. Im Plan als **N9f** aufgenommen.
2. **Die Verkettung ist weiterhin da** (Durchmesser 1,0755 bei Schwelle 0,45).
   Sie ist jetzt ohne den Fehler messbar — zu messen/zu ersetzen ist sie als
   eigener Schritt, **bevor** die Schwelle neu begründet wird.
3. `CLUSTER_MIN_NACHBAR = 3` und `MENGE_ANZAHL = 6` bleiben N9a-Beschlüsse
   (eigene Messung nötig).

## 8. Schutz

Kein Löschen im gesamten Schritt (der Wächter verwirft nur, er löscht nichts);
pCloud ausschließlich **lesend**; Originale nur im Arbeitsspeicher, **keine**
Bilddatei auf Platte; Ausgaben ausschließlich außerhalb des Repos unter
`C:/Users/sebas/foto_sortierung/`; keine Schlüsselwerte in Ausgaben oder
Dateien; keine echten Personennamen in Code, Tests oder Doku.

**Prüfbefehl (selbst gefahren):** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
→ **1316 passed, Exit 0** (Baseline vor diesem Schritt 1205; +75 aus dem neuen
Mess-Werkzeug, +36 aus Fix, Wächter und den neuen Tests).
