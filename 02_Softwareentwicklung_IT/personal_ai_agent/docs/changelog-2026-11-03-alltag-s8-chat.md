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

## Nachtrag nach Hermes (Runde 3: EINWAND)

- Großgeschriebene Füllwörter in gespeicherten Namen (Kontakt „Die Oma") wurden wieder zu
  Namensteilen. Dann wurde jedes „die" im Text maskiert. Ein Leck war das nicht, der Text wurde
  aber verstümmelt. Betroffen ist 1 der 742 Namen (nur gezählt).
- Jetzt gibt es zwei Listen:
  - `FUELLWOERTER` (von, der, die, das, zu, und …) fallen in jeder Schreibweise weg.
  - `NAMENSZUSAETZE` (van, della, ten …) fallen nur kleingeschrieben weg, weil sie auch
    Vornamen sein können.
- 1 Test mehr in `test_schild_namensteile.py`.

## Nachtrag nach Hermes (Runde 4: EINWAND, zwei ältere Lecks)

Beide Lecks steckten schon vor S8 im Namensschutz. Sie betrafen deshalb auch die
Diktat-Glättung (#19) und die Struktur (S3):

- **Beugung:** „mit Annas Hund" ging im Klartext hinaus, weil nur das genaue Wort maskiert wurde.
  - Jetzt bekommt jede Schreibweise ab 4 Zeichen auch die Form mit **-s**.
  - Die Form mit **-n** kommt nur nach Vokal dazu („Wiebken").
- **Umschrift rückwärts:** Bei gespeichertem „Juergen" blieb „Jürgen" im Text stehen. Jetzt
  entstehen auch Umlaut- und ß-Formen. Unechte Formen schaden nicht, weil sie nie im Text
  vorkommen.
- Jede Form hat ihr eigenes Kürzel. Die Rückübersetzung bleibt exakt.
- **Laufzeit:** Aus 742 Namen werden 2905 Formen. Einzeln ersetzt hätte das 180 ms je Text
  gekostet. `PIIShield.encode` ersetzt jetzt in einem Durchgang mit einem gemeinsamen Muster
  (die längste Form zuerst) und braucht 20 ms je Text auf dem PC. Gemessen wurde mit einem
  erfundenen Satz, ausgegeben wurden nur Zahlen.
- **Bleibt offen:** Spitznamen, Tippfehler und Namensteile unter 3 Zeichen erkennt keine
  Wortliste. Für einen Schutz ohne diesen Rest wäre Variante B nötig (Freitexte bleiben auf dem
  Gerät). Die entscheidet Sebastian.
- 4 Tests mehr in `test_schild_namensteile.py`, 2 davon vorher rot.

## Abschluss

- Hermes Runde 5: FREI.
- Volle Suite auf `9f89b61`: 6427 grün, 3 übersprungen.
