# Papas Fotos: die EXIF-Orientierung ist jetzt gemessen statt begründet

Datum: 13.10.2026 · Werkzeug: `tools/foto_sortierung/orientierung_pruefen.py` ·
Test: `backend/tests/test_orientierung_pruefen.py`

## Ausgangslage (nicht behauptet, sondern offen)

In der Kette für Papas 6.336 Fotos steht Schritt 2 („Ausrichtung/Drehung") seit
dem 10.10. als **„für Papa NICHT nötig (kein Lauf)"** — begründet, nicht
gemessen: Papas Gesichtserkennung startete am 10.10. mit dem reparierten
Dekoder (Fix `ad4f09c` vom 08.10.), seine Koordinaten wären damit von Anfang an
korrekt, und die Neuerkennungs-Runde des Bestands (2.373 Bilder) entfalle für
ihn. Ein optionaler Kontrolllauf war im Plan beschrieben, aber nie gefahren.

## Was gemessen wurde

Aufruf (nur lesend am Bestand, **kein** Überschreiben vorhandener Dateien — die
Ausgabe geht auf eigene Dateien):

```
backend/.venv/Scripts/python.exe tools/foto_sortierung/orientierung_pruefen.py \
  --vektoren "C:/Users/sebas/foto_sortierung/personen_vektoren_papa.jsonl" \
  --ausgabe "C:/Users/sebas/foto_sortierung/orientierung_papa.jsonl" \
  --plan "C:/Users/sebas/foto_sortierung/gedreht_plan_papa.json" --schreiben
```

Geholt wurden **nur Dateiköpfe** (je höchstens 128 KB über einen
Range-Kopf), keine Bilder, kein Vision-Aufruf, kein fremdes Modell. Der Lauf
selbst ist lesend: `getfilelink` und ein HTTP-`Range`-Kopf je Bild.

**Ergebnis Papa (frisch gemessen, 6.336 Fotos, 0 Fehler, 1.635 s ≈ 4,0/s):**

| Orientierung | Fotos |
|---|---|
| 1 (keine Drehung) | 5.926 |
| 3 | 24 |
| 6 | 264 |
| 8 | 122 |

**Betroffen (Orientierung != 1): 410** – davon mit Gesicht 396, ohne Gesicht 14
(also 6,5 % seiner Fotos). Plan für eine Neuerkennung: 410 Bilder
(`gedreht_plan_papa.json`). Vergleich Altbestand: 19.679 Fotos, 2.373 betroffen.

**Keine Überschneidung:** `orientierung.jsonl` (19.679 Zeilen, Altbestand) und
`orientierung_papa.jsonl` (6.336) haben **0 gemeinsame Kennungen** — Papa war in
den Bestandsplänen nie enthalten. Es wurde also nichts überschrieben, sondern
daneben gemessen.

## Der Befund: „betroffen" heißt nicht „kaputt"

Die 410 Papas gehören genau in die Klasse, die der Fehler vom 08.10. getroffen
hat. Ob ihre Gesichtsrahmen im **richtigen** Koordinatenraum liegen, ist mit
einem Testprüfbar: `bbox` steht laut `backend/face_infer.py` in absoluten Pixeln
im selben (EXIF-orientierten) Raum wie das Bild. Ein Rahmen, der deutlich über
den Bildrand hinausragt, wäre das Muster der doppelten Drehung.

Gemessen (nur Zahlen, keine Kennung):

```
Rand-Ausreisser (ueber 1 % der laengeren Bildkante):
  Orientierung 1   0.13 % (28 von 22292)
  Orientierung != 1 0.31 %  (3 von 954)   - kein Hinweis auf einen anderen Koordinatenraum
```

Gegenprobe mit den Bestandsdaten (19.679 Fotos): Orientierung 1 **0,12 %**
(59 von 50.381), Orientierung != 1 **0,47 %** (14 von 3.010) — ebenfalls ohne
Hinweis. Losgelöst von der Fallzahl bedeutet das: Papas Rahmen sitzen im
Bildrahmen, die Drehung ist für die Erkennung harmlos. Der Plan-Satz „für Papa
nicht nötig" ist damit **gemessen** statt begründet.

## Die Änderung am Werkzeug

Das Werkzeug meldete bisher nur „Betroffen (Orientierung != 1): N" — und das
klingt wie „kaputt", obwohl nach dem Fix nur die Drehung gemeint ist. Neu:

* `rahmen_lesen(pfade)` liest je Bild Bildmaße und die Zahl der Gesichtsrahmen,
  die um mehr als `ANTEIL_GRENZE` (1 % der längeren Bildkante) über den Rand
  hinausragen — nur Zahlen, nie eine Kennung, eine fehlende Datei bricht nichts.
* `rand_zeilen(ids, erledigt, rahmen)` stellt die beiden Gruppen gegenüber. Die
  Zeile erscheint **nur**, wenn beide Gruppen Rahmen haben (ein Prozentwert ohne
  Rahmen sagt nichts), und sie warnt nur, wenn die gedrehten Bilder **über 1 %**
  UND **mehr als doppelt so viele** Ausreißer zeigen. Sonst steht ausdrücklich
  „kein Hinweis auf einen anderen Koordinatenraum (Indiz, kein Beweis)".

Die absolute Schwelle ist bewusst konservativ: auf echten Daten liegt die
gedrehte Gruppe bei beiden Beständen **über** dem doppelten Anteil der übrigen
(0,31 gegen 0,13 / 0,47 gegen 0,12), aber weit **unter** 1 %. Eine Warnung wäre
hier falsch — 1 % Randausreißer sind bei Randgesichtern normal. Ein Fehlalarm
über 20.000 Fotos wäre teurer als eine späte Warnung.

## Belege

* `backend/tests/test_orientierung_pruefen.py`: **12 → 17 Testfunktionen**
  (5 neue: Zählung der Rand-Ausreißer samt fehlender Datei und Video-Kennung;
  Zeile bleibt aus, wenn eine Gruppe keine Rahmen hat; ohne Verdacht bei
  ähnlichen Anteilen; Verdacht bei deutlich mehr; `main` druckt die Zeile und
  nennt keine Kennung). Lauf der Datei: **17 passed**.
* Prüfbefehl (vollständig, frisch): siehe Commit-Haken/Commit-Nachricht.
* Messung am echten Bestand (Exit 0): die Zeile lautet wörtlich
  „Rand-Ausreisser (ueber 1 % der laengeren Bildkante): Orientierung 1 0.13 %
  (28 von 22292), Orientierung != 1 0.31 % (3 von 954) - kein Hinweis auf einen
  anderen Koordinatenraum (Indiz, kein Beweis)".
* Unabhängige Gegenrechnung (eigenes Skript, nur lesend, gegen dieselben
  Dateien): dieselben Werte 28/22.292 und 3/954.

## Ehrliche Grenzen

* Die Zeile ist ein **Indiz, kein Beweis**. Sie sagt nicht, ob ein einzelnes
  Gesicht richtig sitzt — nur, dass eine ganze Gruppe nicht systematisch daneben
  liegt.
* Ob der Altbestand **vor** dem Fix Ausreißer hatte, sagt die Messung nicht: die
  Neuerkennung (2.373 Bilder) hat ihn bereits überdeckt.
* Die Rand-Kontrolle liest die Vektordateien; sie braucht sie also neben der
  Orientierungsdatei. Fehlt sie, bleibt die Zeile weg (kein Fehlalarm).
* Es wurde **nichts gelöscht**: die neuen Dateien liegen daneben
  (`orientierung_papa.jsonl`, `gedreht_plan_papa.json`), die Probe-Kopien des
  Vergleichslaufs heißen `orientierung_probe.jsonl` / `gedreht_plan_probe.json`.
  Kein Bild- oder Gesichtsdienst, kein Vision-Aufruf, kein Bild an ein fremdes
  Modell, **kein pCloud-Schreibzugriff** (nur Link + Range-Kopf, lesend).
