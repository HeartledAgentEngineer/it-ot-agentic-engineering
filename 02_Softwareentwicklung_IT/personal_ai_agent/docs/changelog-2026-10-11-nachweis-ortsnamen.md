# Nachweis kennt jetzt die Ortsnamen (orte.jsonl) — 11.10.2026

## Warum

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) zaehlt Plaene,
Gesichter, Beschreibungen, Gruppen, den Karten-Zweig (OSM), den Bildindex, die
Neuausrichtung und seit heute frueh die Anlaesse nach. Die **Ortsnamen-Stufe**
(Ketten-Schritt 3b, `orte.jsonl`) stand aber weiter in KEINEM Nachweis: je Bild
Land, Region und der naechste Ort aus den offline GeoNames-Daten, dazu das
Aufnahmedatum (`orte_zuordnen.py`, anhaengend und idempotent).

Diese Stufe ist nicht Beiwerk: sie traegt die Auskunft **„wo war das?"** und die
Ortsnamen fuer die **Erzaehlung** (und `anlass_namen.py` liest sie). Fehlt oder
halbiert sie, merkt es heute niemand — **dieselbe Luecke wie bei OSM
(Journal 8), beim Bildindex (Journal 12) und bei den Anlaessen (Journal 19)**:
eine gebaute Stufe ohne Zahl.

## Was jetzt geprueft wird

Neuer Abschnitt **„Orte (GeoNames)"**:

* **Zeilen** und **Bilder** (verschiedene `bild_id`); dazu **doppelte Zeilen**
  (der Zuordner soll anhaengen und vorhandene Kennungen ueberspringen — mehr
  Zeilen als Kennungen zeigen, dass ein Lauf nicht idempotent war) und
  **kaputte Zeilen** (werden gezaehlt, nie geworfen).
* **Land/Region/Ort** als **Anzahl verschiedener Werte** — nie ein Name,
  nie eine Koordinate.
* **Aufnahme:** wie viele Zeilen ein Datum tragen und wie viele verschiedene
  Tage es gibt (die Zeitschicht, an der Anlass- und Konzertkette haengen).
* **Deckung:** wie viele Plan-Fotos einen Ortsnamen haben — die einzige Zahl,
  die „ist der ganze Bestand verortet?" in einer Zeile beantwortet.
* Fehlt die Datei, steht das als **Luecke** in der Ergebnisliste
  („Ortsnamen nicht zugeordnet"), nicht als stiller Nullwert. Abschaltbar mit
  `pruefen(..., orte_namen=None)`.

Wie der ganze Nachweis: **nur Zahlen und Dateinamen** — das ist in den Tests
festgehalten (Fantasie-Laender/-Regionen/-Orte duerfen im Bericht nicht
auftauchen).

## Messung am echten Bestand (11.10.2026, Exit 0)

```
Orte (GeoNames): orte.jsonl: 9.252 Zeilen, 9.252 Bilder
  Namen: 16 Laender, 38 Regionen, 267 Orte; ohne Ortsnamen 0
  Aufnahme: 9.250 von 9.252 Zeilen tragen ein Datum (958 verschiedene Tage)
  Deckung: 9.252 von 23.916 Plan-Fotos haben einen Ortsnamen (38,7 %)
```

Deutung, ehrlich: 9.252 Zeilen = 9.252 Bilder, **keine Dublette** (der
anhaengende Lauf war sauber) und **0 kaputte Zeilen**. Die Deckung von 38,7 %
ist erwartet — `orte_zuordnen.py` schreibt nur Zeilen fuer Bilder **mit GPS**
(Fotobuch-Scans und Bilder ohne Geodaten haben keins); die 9.252 liegen
vollstaendig innerhalb der Plaene (keine Zeile ausserhalb).

Ergebnisliste des Laufs unveraendert: **4 Luecken** (3 + 5 Fotos und 25 Videos
ohne Beschreibung bzw. Gesichtszeile im Einzelplan, 8 Fotos im Gesamtplan) —
alle kosten- bzw. geraetegebunden.

## Belege

* Tests: `backend/tests/test_bestand_und_handy_uebergabe.py` **39 passed**
  (4 neue: Zaehlung/Uebersicht, keine Ortsnamen im Text + Dubletten und kaputte
  Zeilen, ehrliche Meldung bei fehlender Datei + Abschaltbarkeit,
  `ortsnamen_lesen` wirft bei kaputter Datei nicht; die bestehenden
  unveraendert).
* Pruefbefehl frisch und vollstaendig: **3792 passed, 2 skipped, Exit 0**
  (197,4 s) — vorher 3788, also genau die vier neuen Tests, keine Nebenwirkung.
* Lauf am echten Bestand: Exit 0, Ausgabe oben.

## Dateien

* `tools/foto_sortierung/bestand_pruefen.py` — `STANDARD_ORTE_NAMEN`,
  `ortsnamen_lesen`, Abschnitt „Orte (GeoNames)", Parameter `orte_namen`
  (Standard `orte.jsonl`), Modul-Docstring nachgezogen.
* `backend/tests/test_bestand_und_handy_uebergabe.py` — 4 neue Tests.

## Ehrlich offen

* Am Handy nicht gegengeprueft (kein Geraet am Kabel in dieser Runde).
* Kein Bild-/Gesichtsdienst aufgerufen, nichts geloescht, keine Handy-Eingriffe.
* Fremde Aenderungen im Arbeitsbaum blieben unangetastet (nie `git add -A`).
