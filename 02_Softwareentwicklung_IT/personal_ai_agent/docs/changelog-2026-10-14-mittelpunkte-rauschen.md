# Änderungsprotokoll 14.10.2026: Verrauschen unsichere oder verpixelte Gesichter die Gruppenmittelpunkte?

## Anlass

Sebastians Frage vom 14.10.2026 (Wunschliste, Punkt 3 „Wisch-Sortierer, Stufe 1“):

> „Verrauschen verpixelte Ausschnitte die Mittelwerte, also die Gruppenmittelpunkte und die
> Lebensphasen? Vermutung: ja.“

Die Wunschliste sagt ausdrücklich: „Antwort und Messung gehören in den Plan.“ Diese Datei ist die
**Messung** dazu — kein Neuberechnen, kein Ändern einer Schwelle.

## Neu

`tools/foto_sortierung/mittelpunkt_rauschen_messen.py` — ein reines **Messwerkzeug**:

- **Liest nur:** die Vektorzeilen (Format `gesicht_erkennen.py` / `video_gesichter.py`) und
  `~/foto_sortierung/personen_gruppen/gesicht_zuordnung.jsonl`. Verbunden wird über
  `(bild_id, index)`; bei doppelter Kennung gewinnt die erste Datei (wie `personen_gruppieren`).
- **Schreibt nichts** — der Bericht geht nur auf die Konsole. Kein Bild wird geöffnet, kein Netz,
  kein fremdes Modell, keine Kosten.
- **Mittelpunkt** = normierter Mittelwert der normierten Gesichtsvektoren (Richtung, nicht Länge);
  Maß ist die **Cosinus-Distanz** (`1 − Kosinus`) — dieselbe Cosinus-Welt wie `personen_cluster`
  (Gruppierungsschwelle dort: `CLUSTER_SCHWELLE = 0,45`).
- **„Unsicher“** = `score` unter 0,90 (Voreinstellung, `--min-score`).
  **„Grob aufgelöst“** = Ausschnittbreite unter 64 px (`--min-breite`) — dort wäre die Nahansicht
  verpixelt. Beide Maße werden **einzeln und zusammen** gemessen.
- Drei Fragen: (1) Verschiebung des Mittelpunkts ohne unsichere/grobe Gesichter, (2) wie viele
  saubere Gesichter unter den sauberen Mittelpunkten die Gruppe wechseln würden, (3) dasselbe je
  Aufnahmejahr (Lebensphase).
- Ausgabe: nur Zahlen und Gruppen-Kennungen (`Person_0123`) — **keine Namen, keine Bild-IDs, keine
  Koordinaten** (ein Test hält das fest).

Tests: `backend/tests/test_mittelpunkt_rauschen.py`, **14 Offline-Tests** auf erfundenen Vektoren
(Zeilen ohne Kennung, doppelte Kennung/erste Datei gewinnt, abweichende Vektorlänge, defektes JSON,
fehlende Datei, Mittelpunkt/Winkel, die drei Weglass-Varianten, Neuordnung, Jahresphasen, keine
Bild-ID und kein Pfad im Bericht, beide Abbruchwege).

## Der Lauf am echten Bestand (14.10.2026, 21:1x, nur lesend)

Aufruf (aus `personal_ai_agent`):

    backend\.venv\Scripts\python.exe tools\foto_sortierung\mittelpunkt_rauschen_messen.py

Wörtliche Messzeilen:

    Gesichter in Gruppen: 30830 · mit Vektor: 30830 (100 %) · ohne Vektor: 0 · ohne Kennung (nicht gezaehlt): 19452
    Vektoren: 7 Dateien gelesen (0 fehlten) · 43452 Zeilen · 0 defekt · 129945 Gesichter · uebernommen 30830 · andere Laenge verworfen 0 · Masse 128
    Nicht sicher (score < 0.9): 15186 (49 %) · grob aufgeloest (Breite < 64 px): 7044 (23 %) · unsicher ODER grob: 16802 (54 %)

    Gruppen: 1367 · mit mindestens 30 Gesichtern mit Vektor: 113
    Verschiebung des Gruppenmittelpunkts (Cosinus-Distanz):
      ohne unsichere (score < 0.9)       Median 0.003 · 90 % 0.224 · groesste 0.593
      ohne grobe (Breite < 64 px)        Median 0.002 · 90 % 0.195 · groesste 0.368
      ohne unsichere und grobe           Median 0.005 · 90 % 0.224 · groesste 0.593

    Neuordnung: von 14028 sauberen Gesichtern bekaemen 764 (5 %) unter den sauberen Mittelpunkten eine andere Gruppe (1367 gegen 594 Mittelpunkte)

    Lebensphasen (Gruppe und Aufnahmejahr mit mindestens 20 Gesichtern): 122 Phasen
      Verschiebung je Phase            Median 0.003 · 90 % 0.010 · groesste 0.026

## Befund

1. **Im Mittel verrauscht nichts.** Der Median der Verschiebung liegt bei **0,003**, das 90 %-Maß bei
   0,224. Für die **Lebensphasen** ist die Verschiebung praktisch bedeutungslos: 122 Phasen,
   Median 0,003, 90 % 0,010, größte **0,026**. Die Vermutung „ja“ trifft für die Mittelwerte über die
   Jahre also **nicht** zu.
2. **In dünn besetzten Gruppen kippt der Mittelpunkt trotzdem.** Alle großen Ausreißer (0,36–0,59,
   teils über der Gruppierungsschwelle 0,45) sind Gruppen mit **1–2 sauberen Gesichtern**: dort ist
   der „saubere“ Mittelpunkt fast bedeutungslos, der verrauschte Anteil trägt ihn. Also: **nicht die
   Größe des Rauschens ist das Problem, sondern die Zahl der brauchbaren Gesichter je Gruppe.**
3. **Der harte Nebenfund: 773 der 1.367 Gruppen haben überhaupt kein sauberes Gesicht** (so viele
   Mittelpunkte fallen weg: 1.367 → 594). Diese Gruppen bestehen ganz überwiegend aus unsicheren
   oder grob aufgelösten Funden — 54 % aller zugeordneten Gesichter sind unsicher oder grob
   (49 % unsicher, 23 % grob).
4. **5 % der sauberen Gesichter** (764 von 14.028) bekämen unter den sauberen Mittelpunkten eine
   andere Gruppe. Das ist die Zahl, die für den Wisch-Sortierer zählt: eine Bereinigung der
   Mittelpunkte würde die Zuordnung der guten Gesichter nur am Rand verschieben.

## Was das für den Wisch-Sortierer (Stufe 1) bedeutet

- Ein „Aufräumen nach Erkennungssicherheit/Gesichtsgröße“ **verschiebt die Mittelwerte nicht** —
  es ist also kein Grund, die Gruppenmittelpunkte neu zu rechnen.
- Der Nutzen liegt woanders: die **773 Gruppen ohne ein einziges sauberes Gesicht** sind die
  eigentlichen Kandidaten für den Wisch-Sortierer (dort ist fast alles unbrauchbar), und die
  großen Ausreißer mit 1–2 sauberen Gesichtern sind die unsichersten Gruppen überhaupt.
- Vorschlag für den Plan (nicht umgesetzt, Entscheidung Sebastian): den Wisch-Sortierer nach
  **„Zahl der sauberen Gesichter je Gruppe“** sortieren (schlechteste zuerst), statt nach der
  Gruppengröße.

## Grenzen (ehrlich)

- „Verpixelt“ ist über die **Ausschnittbreite in Pixeln** gemessen, nicht über eine gemessene
  Unschärfe — die vom Wunschzettel genannte spätere „gemessene Unschärfe“ ist damit **nicht**
  abgedeckt.
- Die Cosinus-Distanz zwischen zwei Mittelpunkten ist ein **Maß der Verschiebung**, keine Aussage
  darüber, ob dadurch jemand die Person wechselt; dafür steht die Neuordnungs-Zahl (5 %).
- Nur Gesichter **mit** Zuordnungszeile wurden gemessen (30.830 von 50.282 Gesichtern; 19.452 ohne
  Kennung sind kein Teil einer Gruppe). Vektoren für Video-Gesichter sind über die Form
  `<fileid>#t=…` mitgezählt.
- Die Genauigkeit hängt an `aufnahme` in der Zuordnungsdatei — Video-Gesichter tragen dort `null`
  und zählen damit in keiner Lebensphase mit (das ist gewollt, hält die Phasen sauber).
- Kein Name, keine Bild-ID und kein Koordinatenwert verlässt das Werkzeug; es geht nichts an ein
  fremdes Modell.

## Nachtrag (14.10.2026, 22:1x): Reihenfolge für den Wisch-Sortierer gemessen

Der Vorschlag oben war eine Vermutung („773 Gruppen ohne sauberes Gesicht sind die Kandidaten") —
jetzt ist er eine Zahl. Das Messwerkzeug hat einen vierten Abschnitt bekommen:

**Stufen** (`sauber_je_gruppe`, `sauber_stufen`, `wisch_reihenfolge` in
`mittelpunkt_rauschen_messen.py`): je Gruppe werden die **sauberen** Gesichter gezählt
(`score >= 0,90` UND Ausschnittbreite `>= 64 px`), die Gruppen in Stufen gelegt und
**schlechteste zuerst** sortiert (wenige saubere zuerst, bei Gleichstand die größere Gruppe zuerst,
dann die Kennung). Weiterhin nur lesend, nur Zahlen und Kennungen.

Wörtliche Messzeilen aus dem Lauf am echten Bestand (14.10.2026 22:1x, Exit 0):

    Wisch-Sortierer, Stufe 1 (Vorschlag: nach Zahl der sauberen Gesichter, schlechteste zuerst):
      kein sauberes Gesicht    773 Gruppen
      1 bis 2 saubere          130 Gruppen
      3 bis 9 saubere          330 Gruppen
      10 oder mehr saubere     134 Gruppen
          Person_1160   0 saubere von 239 Gesichtern
          Person_1162   0 saubere von 226 Gesichtern
          Person_092    0 saubere von 182 Gesichtern
          Person_1159   0 saubere von 178 Gesichtern
          Person_1529   0 saubere von 168 Gesichtern

**Der Befund ist deutlicher als erwartet:** die vier Stufen summieren sich auf die 1.367 Gruppen
(keine Gruppe ohne Vektor). **773 Gruppen (56,5 %) haben kein einziges sauberes Gesicht**, und die
Spitze der Sortierliste sind **die größten Gruppen überhaupt** — 239, 226, 182, 178 und 168
Gesichter, alle mit **null** sauberen Funden. Nach der Gruppengröße sortiert wäre die Reihenfolge
zufällig richtig; nach „Zahl der sauberen Gesichter" stehen genau die hoffnungslosen Fälle oben.
Damit ist die Reihenfolge belegt: **Stufe 1 des Wisch-Sortierers muss zuerst die 773 Gruppen ohne
sauberen Fund abarbeiten** (773 + 130 = 903 Gruppen, also zwei Drittel aller Gruppen, mit höchstens
zwei brauchbaren Gesichtern).

Tests: vier neue Fälle in `backend/tests/test_mittelpunkt_rauschen.py` (Zählung nur mit Vektor,
Stufen-Grenzen, Reihenfolge und Gleichstand, der Bericht zeigt die Stufen und bleibt ohne
Bildkennung/Pfad) — Datei **18 passed**.

## Nicht geändert

Keine Schwelle, keine Zuordnung, keine Vektordatei, keine Gruppendatei. `personen_cluster.py`,
`personen_gruppieren.py` und die Gruppendateien wurden **nur gelesen**.
