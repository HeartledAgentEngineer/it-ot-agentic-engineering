# Änderungsprotokoll 07.10.2026 — Orte aus der Karte nur rund um die Fotos, eigene Orte

Rückmeldung Sebastian zu `orte_aus_karte.py` (Commit `61508d3`, Hermes):

> „Brauche nicht alle Adressen … nicht alle Adressen nach Gebieten. Das ist doch crazy. Wir wollten
> Sehenswürdigkeiten, bestimmte Orte aus den Karten. Bei meinen Großeltern, bei Thorsten in
> Zarrentin, bei meiner Oma oder meinem Nachbarn — das kommt von mir."

Bisher schrieb die Kartenauswertung **alle** Adressen und benannten Orte ganzer Gebiete als
Tabellen. Allein Hamburg ergab 293.330 Adressen und 22.253 Orte.

## Änderung (`tools/foto_sortierung/orte_aus_karte.py`)

**Standard jetzt: nur Orte rund um die Fotos, keine Hausnummern.**

- Die Fotopunkte kommen aus `--vektoren`. Das GPS stammt aus dem Gesichterlauf, eine oder mehrere
  Dateien. Standard sind beide Sammlungen, also „Bilder & Videos" und der Upload-Stapel.
- Ein benannter Ort bleibt nur, wenn ein Foto in Luftlinie nah genug liegt. Der Umkreis hängt von
  der Art ab (`UMKREIS_KM`):

  | Art | Beispiele | Umkreis |
  |---|---|---|
  | Punkt | Restaurant, Sehenswürdigkeit, Museum, Kirche, Sport, Laden, Haltestelle, Bahnhof | 300 m |
  | Fläche (Mittelpunkt oft weit weg) | Berg, See, Fluss, Wald, Schutzgebiet, Flughafen | 2 km |
  | Ortschaft | Stadt, Dorf, Ortsteil | 5 km |

- Weiter entfernte Orte werden nur gezählt („außer Umkreis verworfen").
- Hausnummern nur mit `--mit-adressen`, und auch dann nur 100 m um ein Foto.
- `--alle` stellt die frühere Vollauswertung wieder her (alle Orte und Adressen der Karte).
- Ohne Fotos mit GPS bricht der Lauf ehrlich ab (Exit 2), statt die ganze Karte zu schreiben.
- Die Prüfung `FotoNaehe` nutzt ein Raster je Umkreis und rechnet die Luftlinie genau. Fotos an
  praktisch derselben Stelle (~11 m) zählen einmal, damit die Prüfung am Wohnort mit Tausenden
  Fotos schnell bleibt.

**Eigene Orte kommen von Sebastian, nicht aus der Karte.**

Die Orte stehen in der Datei `~/foto_sortierung/eigene_orte.json`, die außerhalb des Repos liegt:

```json
[{"name": "bei Oma", "lat": 53.7, "lon": 10.7, "radius_m": 100}]
```

- `radius_m` ist optional, Standard 100.
- Beim Zuordnen (`--zuordnen`) gewinnt ein eigener Ort vor der Karte, wenn das Foto in seinem
  Radius liegt. Er steht dann in `bild_orte.csv` als `landmarke` mit `landmarke_art = eigener_ort`.
- Kaputte Einträge werden übersprungen. Fehlt die Datei, gibt es einfach keine eigenen Orte.
- Wie die Einträge entstehen, ist noch offen. Geplant ist, dass Sebastian im Erzählen sagt „das ist
  bei Oma" und das GPS des Fotos übernommen wird. Bis dahin pflegt er die Datei von Hand oder
  diktiert sie Hermes.

`--vektoren` nimmt jetzt mehrere Dateien an (`nargs="+"`). Ein einzelner Pfad funktioniert wie
bisher.

## Lauf (Hermes oder Sebastian, über die echten Karten)

Zuerst je Gebiet neu auswerten. Der Standard braucht keinen weiteren Schalter:

```powershell
& backend\.venv\Scripts\python.exe tools\foto_sortierung\orte_aus_karte.py --karte "$HOME\foto_sortierung\osm\schleswig-holstein-latest.osm.pbf" --ordner "$HOME\foto_sortierung\osm\csv\schleswig-holstein" --schreiben
```

Danach `--zusammenfassen` und `--zuordnen` wie bisher. Die alten Gesamttabellen mit allen Adressen
werden dabei überschrieben. Die Kartendateien selbst bleiben liegen.

## Prüfung

- `backend/tests/test_orte_aus_karte.py`:
  - Die bisherigen 14 Tests prüfen die Vollauswertung jetzt ausdrücklich mit `--alle`.
  - Neu ist eine Schutzvorrichtung: In Tests zeigen die Standardpfade (Fotos, eigene Orte) immer ins
    Leere.
  - 6 neue Tests:
    - Umkreis je Art
    - `sammle_karte` mit Foto-Umkreis und ohne Adressen
    - ohne Fotos ehrlicher Abbruch
    - Standardlauf schreibt nur nahe Orte, keine Adressen
    - `--mit-adressen` nimmt nur die Hausnummer am Foto mit
    - eigene Orte: tolerantes Lesen, Radius, Vorrang beim Zuordnen
  - Ergebnis: 20 grün.
- Prüfbefehl: siehe Commit.

## Hinweis zur Prüfung

Ein erster Testlauf vor dem Schutz rief die Auswertung ohne `--vektoren` auf. Dabei las er die
Standard-Fotodateien am PC. Ausgegeben wurden nur Zählungen, keine Koordinaten oder Namen. Seit der
Schutzvorrichtung kann das nicht mehr passieren.
