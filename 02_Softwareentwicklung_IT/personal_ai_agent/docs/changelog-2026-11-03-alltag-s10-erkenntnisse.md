# Changelog 03.11.2026 — Alltagsprotokoll S10: Erkenntnisse aus Tageszeit und Schlafqualität

Baut auf S9 auf. Sebastians Ziel ist, möglichst viele Daten zu verknüpfen und daraus neue Erkenntnisse zu gewinnen. Bisher verglich `alltag_abfragen` nur die Schlafdauer mit der Stimmung. Jetzt kommen zwei Auswertungen dazu. Beide rechnen nur mit Zahlen, Freitext geht dabei nicht hinaus.

## Neu im Zeitraum-Text von `alltag_abfragen`

- **Tageszeiten** (`tageszeit_text`): Stimmung und Anspannung im Schnitt, getrennt nach Tageszeit.
  - Die Tageszeiten sind morgens (5–12 Uhr), nachmittags (12–17), abends (17–22) und nachts (22–5).
  - Maßgeblich ist der Beginn des Eintrags in der gespeicherten Ortszeit.
  - Die Auswertung erscheint erst ab 4 Einträgen mit Stimmung, verteilt auf mindestens zwei Tageszeiten.
  - Beispiel: „Tageszeiten, Stimmung im Schnitt (Einträge): morgens 2,5 (2) · nachmittags 4,0 (2) · abends 5,0 (2). Anspannung: morgens 55 · …"
- **Schlafqualität** (`schlafqualitaet_text`): nur Nächte, für die die Uhr Schlafphasen geliefert hat.
  - **Tiefschlaf:** Stimmung nach Nächten mit weniger und mit mehr Tiefschlaf. Geteilt wird am Median wie beim Schlafvergleich, ab 4 Tagen.
  - **Aufwachen:** Stimmung nach Nächten ohne und mit nächtlichem Aufwachen (Wachphase mitten in der Nacht), je Gruppe ab 2 Nächten.
  - Der Text endet mit „Nur ein Zusammenhang, kein Beweis."
  - Ohne Phasen oder mit zu wenig Daten schweigt diese Auswertung.
- Die Nacht zählt wie bisher zum Tag des Aufwachens. Nickerchen zählen nicht mit.
- Die Zuordnung von Nacht zu Tag steckt in `_nacht_und_tag` und wird auch vom bisherigen Schlafvergleich genutzt.
- Die Werkzeugbeschreibung nennt jetzt Tiefschlaf, Aufwachen und Tageszeiten. Damit wählt das Modell das Werkzeug auch bei Fragen wie „Wann am Tag geht es mir am besten?".

## Datenschutz

Unverändert. Die neuen Sätze enthalten nur Zahlen, Tageszeit-Namen und feste Wörter. Tätigkeiten, eigene Worte und Namen kommen darin nicht vor.

## Prüfung

- Neue Tests, vorher rot:
  - in `test_alltag_auswertung.py`: Tagesprofil, Mindestmenge, Schlafqualität, Schweigen ohne Phasen.
  - in `test_werkzeug_alltag.py`: Die Beschreibung nennt Tageszeit und Tiefschlaf.
- `test_alltag_auswertung.py`, `test_werkzeug_alltag.py` und `test_werkzeuge.py` sind grün (56).
- Volle Suite auf `26a8d73`: 6437 grün, 3 übersprungen.

## Nachtrag nach Hermes (Runde 1: FREI, ein Hinweis)

- **Hinweis (seit S8):** Fielen zwei Schlafabschnitte auf denselben Tag, zählte nur der spätere.
  Eine unterbrochene Nacht (23–3 Uhr wach, 4–7 Uhr) galt so als 3 statt 7 Stunden. Die Uhr liefert
  solche Nächte oft als zwei Sitzungen.
- **Jetzt:** `_nacht_zusammen` zählt die Abschnitte eines Tages zusammen (Dauer, Schlaf, Wach,
  Leicht-, Tief- und REM-Schlaf). Jede Lücke zwischen zwei Abschnitten zählt als nächtliches
  Aufwachen. Die Phasen gelten nur als bekannt, wenn alle Abschnitte welche haben.
- Neuer Test `test_unterbrochene_nacht_wird_zusammengezaehlt` (vorher rot).

## Abschluss

- Hermes Runde 2: FREI.
- Alle Alltag-Tests auf `da4384c` grün (123).
- **Offen, kein Fehler im Code:**
  - Melden zwei verschiedene Quellen auf dem Handy dieselbe Nacht mit eigener Kennung, würden die Abschnitte doppelt gezählt. Ein Beispiel wären zwei Schlaf-Apps, die beide in Health Connect schreiben. Gleiche Kennungen sind schon ausgeschlossen.
  - Erst prüfen, ob das am Handy überhaupt vorkommt. Dann gegebenenfalls nur eine Quelle übernehmen.
