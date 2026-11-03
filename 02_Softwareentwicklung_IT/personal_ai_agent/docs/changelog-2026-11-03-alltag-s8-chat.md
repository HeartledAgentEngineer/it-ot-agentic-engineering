# Changelog 03.11.2026 — Alltagsprotokoll S8: Protokoll im Chat abfragen

Baut auf S1 bis S7 auf. Zum Schlaf gab es schon `schlaf_abfragen`. Jetzt kann der Chat auch
die Stundeneinträge lesen und beides verknüpfen.

## Neu

Das Chat-Werkzeug `alltag_abfragen` nimmt `datum` (heute, gestern, JJJJ-MM-TT) oder `tage`
(1–90, Standard 7).

- **Ein Tag:** Es zeigt die Nacht davor (Uhr) und jeden Eintrag mit Zeit, Tätigkeit, Stimmung
  (Wort und Zahl), Anspannung und Gefühlen.
- **Zeitraum:** Je Tag kommen die Zahl der Einträge, der Schnitt von Stimmung und Anspannung und
  die häufigsten Grundgefühle. Dazu gibt es die **Verknüpfung Schlaf ↔ Stimmung**:
  - Gegenübergestellt werden Stimmung und Anspannung nach den kürzeren und nach den längeren
    Nächten.
  - Getrennt wird am Median der eigenen Nächte, die Nacht zählt zum Tag des Aufwachens.
  - Nickerchen zählen nicht mit.
  - Ab 4 Tagen mit beidem gibt es den Vergleich, sonst einen ehrlichen Hinweis.
  - Der Text endet mit „kein Beweis".
- Fragen wie: „Wie war meine Stimmung gestern?", „Was habe ich heute gemacht?", „Hängt meine
  Stimmung am Schlaf?"

Die neue Datei `backend/app/services/alltag_auswertung.py` rechnet rein, ohne Modellaufruf.

## Datenschutz

Werkzeug-Ergebnisse gehen als Text an das Sprachmodell (OpenRouter ZDR, `data_collection: deny`).
Der Chat maskiert sie nicht. Deshalb gilt im Werkzeug selbst:

- `originalworte` (der eigene Satz) geht **nie** hinaus.
- Freitexte (Tätigkeit, eigene Gefühlsworte) gehen nur geschwärzt hinaus. Jeder Name aus
  `namen_fuer_maskierung` wird über den `PIIShield` zu „[Name]", Telefon und Mail werden zu
  „[Kontakt]". Das wird **nicht** zurückübersetzt.
- Ohne lesbare Namensliste fallen die Freitexte ganz weg (fail-closed). Der Text sagt das dann.
- Stimmung, Anspannung, Zeiten und Gefühle aus der festen Liste gehen unverändert hinaus.

## Prüfung

- Neue Tests, vorher rot (Modul fehlte):
  - `test_alltag_auswertung.py` (14, mit Nachtrag)
  - `test_werkzeug_alltag.py` (7)
- Die Werkzeugzahl in `test_werkzeuge.py` und `test_daten_aendern_werkzeuge.py` steigt auf 17.
- `test_werkzeug_schlaf.py` ist unverändert grün.
- Nachtrag: `test_kaputte_eintraege_brechen_nichts`, vorher rot. Kamen Gefühle als Text statt
  als Liste, wurden sie Buchstabe für Buchstabe ausgegeben. Jetzt zählen nur Listen.

## Nachtrag nach Hermes (Runde 1: EINWAND)

`pii_shield.schild_aus_namen` trennte Namensteile nur an Leerzeichen. Daraus folgten zwei
Fehler, die auch die Glättung (#19) und die Struktur (S3) betreffen:

- **Bindestrich-Namen:** „Anna-Lena Meier" ergab keinen Teil „Anna". Ein allein genannter
  Vorname ging so unmaskiert hinaus. Jetzt wird zusätzlich am Bindestrich getrennt.
- **Namenszusätze:** „von der Heide" machte „von" und „der" zu Namen, und jedes „der" im Text
  wurde maskiert. Zusätze wie von, der, zu oder van sind jetzt ausgenommen (`NAMENSZUSAETZE`).
- Auf diesem PC betrifft das 9 der 742 Namen (Bindestrich) und 2 (Zusatz). Gezählt wurde nur,
  kein Name wurde ausgegeben.
- Neue Datei `test_schild_namensteile.py` (5 Tests, vorher 3 rot).

## Nachtrag nach Hermes (Runde 2: EINWAND)

- Die Ausnahmeliste verglich ohne Rücksicht auf Groß- und Kleinschreibung. „Della" oder „Ten",
  die auch Vornamen sind, wurden deshalb allein nicht mehr maskiert. Diesen Weg hatte die
  Reparatur aus Runde 1 erst geöffnet. Jetzt fallen nur **kleingeschriebene** Zusätze weg.
- Namen werden auch am Apostroph getrennt („O'Brien" ergibt den Teil „Brien").
- Teile unter 3 Zeichen („Jo") werden weiterhin bewusst nicht einzeln registriert, sonst würde
  jedes gleiche Kurzwort maskiert. Das steht jetzt im Docstring.
- 2 Tests mehr in `test_schild_namensteile.py` (vorher rot).
- Die volle Suite auf dem Stand von Runde 1 ergab 6420 grün und 3 übersprungen.
