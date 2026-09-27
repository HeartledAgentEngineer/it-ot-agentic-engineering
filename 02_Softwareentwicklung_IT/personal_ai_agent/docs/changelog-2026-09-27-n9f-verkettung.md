# N9f — Personen-Ergebnisse mit korrigierten Vektoren + Verkettung beziffert

**Datum:** 27.09.2026 · **Schritt:** N9f (Nachtlauf)
**Planer:** Hauptagent (`deepseek-v4.1-flash`) · **Ausführer:** Hermes-Subagent
(`deepseek-v4.1-flash`, 0,026 USD) für das neue Werkzeug, Messläufe vom Planer ·
**Prüfer:** `openai/gpt-5.6-luna` (andere Modellfamilie)

## Warum dieser Schritt

N9e hat einen Fehler in der Merkmalberechnung gefunden und behoben: `cv2…alignCrop`
bekam an drei Stellen nur die 5×2-Landmarken statt der vollen 15-Werte-Detektionszeile
→ **jedes Gesicht eines Bildes hatte denselben Vektor**. Damit waren die
Personen-Ergebnisse aus N9b/N9d ungültig. N9f rechnet sie auf der korrigierten
Vektordatei neu **und** beziffert die danach noch messbare Verkettung.

## Neu gebaut (Ausführer)

| Datei | Umfang |
|---|---|
| `tools/foto_sortierung/personen_verkettung.py` | 878 Zeilen |
| `backend/tests/test_personen_verkettung.py` | 939 Zeilen, **117 Testfunktionen** |

Drei Gruppierverfahren, alle rein (nur `numpy`, offline, kein Bild, kein Netz):

* **`dichte`** — der Bestandsweg (`personen_cluster.vektoren_clustern`, DBSCAN-artig,
  Kernpunkt + Expansion). Verkettet transitiv: A nah an B, B nah an C → A und C in
  **einer** Gruppe, obwohl ihre Distanz groß ist.
* **`vollstaendig`** — agglomerative **Complete-Linkage**: verschmolzen wird nur, wenn
  das *weiteste* Punktpaar beider Gruppen ≤ Schwelle ist. Der Durchmesser jeder Gruppe
  ist damit **garantiert** ≤ Schwelle (per Test über Saatgüter und Schwellen belegt).
* **`mittelpunkt`** — Zuordnung zum nächsten normierten Mittelpunkt, Verschmelzen bis
  stabil. Hat die Garantie **nicht** (gemessen 0,4862 > 0,45 im Ketten-Test).

Dazu `verfahren_messen` (je Schwelle Gruppen, größte Gruppe, Gesichter, verworfen,
Durchmesser max/mittel, mit Beschriftungen zusätzlich die Bodenwahrheit),
`vergleich_bericht`/`bericht_text` und eine Kommandozeile (`--vektoren`, `--verfahren`,
`--schwellen`, `--min-groesse`, `--ausgabe` **nur außerhalb des Repos**, `--schreiben`;
Standard ist der Trockenlauf). Wiederverwendet statt nachgebaut: `vektoren_clustern`,
`cosinus_distanz`, `zeilen_lesen`, `bild_entscheidung`, `geclusterte_eintraege`
(N9a) und `bild_paare`, `verschmelzungsquote`, `gruppendurchmesser` (N9e).

## Messung 1 — Verkettung, Produktionseinstellungen

Vektordatei `personen_vektoren_n9e.jsonl` (92 Bildzeilen, **189 nutzbare Gesichter**),
Schwelle **0,45**, Mindestgröße **3** (wie `CLUSTER_MIN_NACHBAR`):

| Verfahren | Gruppen | größte | Gesichter | verworfen | Durchmesser max | ≤ Schwelle? |
|---|---|---|---|---|---|---|
| dichte (Bestand) | 12 | **22** | 74 | 115 | **0,9032** | nein |
| vollständig | 11 | 11 | 63 | 126 | **0,4417** | ja |
| mittelpunkt | 10 | **27** | 75 | 114 | **0,9040** | nein |

**Die Verkettung ist damit beziffert:** der Bestandsweg bildet bei Schwelle 0,45 eine
Gruppe mit 22 Gesichtern und einem Durchmesser von **0,9032 — das Doppelte der
Schwelle**. Die vollständige Verknüpfung bleibt mit **0,4417** unter der Schwelle.

## Messung 2 — alle acht Schwellen, gleiche Mindestgröße (2) für alle drei

`personen_verkettung.py --vektoren personen_vektoren_n9e.jsonl` (189 Gesichter):

| Schwelle | dichte: Gruppen / größte / Durchm. max | vollständig: Gruppen / größte / Durchm. max | mittelpunkt: Gruppen / größte / Durchm. max |
|---|---|---|---|
| 0,45 | 20 / 22 / **0,9032** | 23 / 11 / **0,4491** | 18 / 27 / **0,9040** |
| 0,40 | 17 / 20 / **0,7387** | 21 / 9 / **0,3781** | 17 / 20 / **0,7387** |
| 0,35 | 17 / 20 / **0,7387** | 22 / 9 / **0,3410** | 17 / 20 / **0,7387** |
| 0,30 | 17 / 18 / **0,7213** | 24 / 8 / **0,2818** | 16 / 18 / **0,6534** |
| 0,25 | 16 / 16 / **0,6534** | 23 / 6 / **0,2380** | 17 / 14 / **0,4544** |
| 0,20 | 16 / 14 / **0,6193** | 21 / 5 / **0,1979** | 15 / 13 / **0,4544** |
| 0,15 | 15 / 6 / **0,2748** | 16 / 3 / **0,1497** | 14 / 6 / **0,2748** |
| 0,10 | 11 / 3 / **0,1553** | 11 / 2 / **0,0960** | 11 / 3 / **0,1380** |

**Dichte und Mittelpunkt liegen bei *jeder* der acht Schwellen über der Schwelle;
die vollständige Verknüpfung nie.** Die Zahlen der Tabelle in Messung 1 und die
0,45-Zeile dieser Tabelle unterscheiden sich, weil hier die Mindestgröße **2** als
Kernpunkt-Bedingung durchgereicht wird und dort **3** (Produktionsweg) — dieselbe
Ursache, kein Widerspruch.

## Messung 3 — Bodenwahrheit (hart, ohne Personen-Labels)

Zwei **erkennbare** Gesichter im **selben** Bild sind zwei Personen (Flächenanteil
≥ 0,5 %): **131 solche Paare**. Ihre Cosinus-Distanzen: **min 0,5312**, Median 0,8280,
max 1,0667 — **0 von 131 Paaren liegen unter 0,45**.

Ergebnis über alle drei Verfahren und alle acht Schwellen (0,10–0,45):
**0 von 131 Paaren verschmolzen** (Quote 0,000). Auch der verkettende Bestandsweg
legt also keine zwei erkennbaren Gesichter desselben Bildes zusammen — die Verkettung
verschmilzt hier nur **nicht prüfbare** (kleine/ferne) Gesichter.

## Entscheidung zur Schwelle — unverändert 0,45, mit Zahlen begründet

* Kleinster Abstand zweier **erkennbarer** Gesichter desselben Bildes: **0,5312** →
  Abstand zur Schwelle **0,0812**; unter 0,45 liegen **0 von 131** Paaren.
* Ein Anheben der Schwelle wäre damit durch **keine** Messung gedeckt; es bliebe eine
  unbelegte Änderung. **`CLUSTER_SCHWELLE` bleibt 0,45.**
* **Empfehlung für den Personenschritt** (hier bewusst *nicht* vollzogen, weil ein
  Verfahrenswechsel ein eigener Schritt mit eigener Messung ist): **vollständige
  Verknüpfung**, weil sie den Durchmesser garantiert (0,4417 ≤ 0,45) und in den
  Produktionseinstellungen 11 statt 12 Gruppen mit 63 statt 74 Gesichtern liefert —
  der Preis sind 11 zusätzliche Gesichter im Rauschen, der Gewinn ist das Ende der
  Verkettung (größte Gruppe 11 statt 22, Durchmesser 0,4417 statt 0,9032).
* `CLUSTER_MIN_NACHBAR`, `ANTEIL_MIN`, `ANTEIL_ERKENNBAR`, `KATALOG_SCHWELLE` und
  `MENGE_ANZAHL` sind **unverändert** (nicht angetastet, keine Zahl geändert).

## Neu-Rechnung der Personen-Stufe (korrigierte Vektoren)

`personen_cluster.py --vektoren personen_vektoren_n9e.jsonl` (Produktionseinstellungen
Schwelle 0,45, `min_nachbarn` 3):

* **92 Bilder** gelesen, 0 ungültige Zeilen — Bild-Arten: **leer 20 · gruppe 32 ·
  menge 10 · unklar 30** (identisch zum korrigierten Lauf in N9e, wie erwartet:
  dieselben Vektoren).
* **32 Bilder geclustert**, **12 Gruppen** mit Größen
  **4, 4, 4, 4, 3, 11, 10, 3, 22, 3, 3, 3** (74 Gesichter).
* **12 Kennungen** (`Person_001` … `Person_012`), 0 wiederverwendet — ehrlich dazu:
  der Lauf startete **ohne** Altbestand (die alte Kennungsdatei stammt aus dem
  fehlerhaften N9b-Lauf und beschreibt falsche Vektoren; sie wurde bewusst nicht
  als Altbestand übergeben).
* **16 Referenzseiten** mit echten Gesichtsausschnitten: **74 Kacheln, alle 200×200**
  (0 leer, 0 andere Größe), 17 Dateien, **745.758 Bytes** gesamt,
  `kennungen.json` 40.358 Bytes. **Zweiter Lauf: 0 Seiten** (idempotent).
* **Pixel-Gegenprobe** an drei Kacheln: Abstand zum frisch gerechneten
  Gesichtsausschnitt **2,778 / 2,869 / 3,015** (das ist der JPEG-Verlust bei
  quality 85), zum verkleinerten **ganzen Foto** dagegen **59,425 / 58,783 / 68,712**
  → die Kachel zeigt wirklich den Gesichtsausschnitt.

## Prüfbefehl

`cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q`
→ **1433 passed, 3 warnings, Exit 0** (Baseline vor diesem Schritt: **1316**;
+117 = genau die neuen Testfunktionen). Selbst gefahren.

## Schutz und Grenzen

* pCloud **nur lesend**; Originale waren **nur im Arbeitsspeicher**, **keine**
  Bilddatei auf der Platte außerhalb der Ausgabeordner.
* **Nichts gelöscht**: die Belegskripte verweigern einen nicht leeren Zielordner mit
  deutscher Meldung und **Exit 2**; `~/foto_sortierung/manifest.jsonl` existiert
  weiterhin nicht (0 Buchungen).
* Geschrieben wurde ausschließlich unter `~/foto_sortierung/` (außerhalb des Repos):
  `personen_n9f/` (16 Seiten + `kennungen.json`), `n9f_bodenwahrheit.json`,
  `n9f_referenzseiten.json` und drei Belegskripte.
* Keine Schlüsselwerte, keine Namen Dritter, keine Personen-Labels — die
  Bodenwahrheit ist eine **Bildaussage**, kein Identitätsurteil.
* **Offen für den nächsten Schritt:** der Verfahrenswechsel im Produktionsmodul
  (`vollstaendig`) und die Ausweitung der Stichprobe über die 92 Bilder hinaus.
