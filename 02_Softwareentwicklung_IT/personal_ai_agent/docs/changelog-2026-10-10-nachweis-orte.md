# Nachweis kennt jetzt den Karten-Zweig (Orte/OSM) — 10.10.2026

## Warum

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) zaehlte Plaene,
Gesichter, Beschreibungen und Gruppen nach — **den Karten-Zweig aber gar
nicht.** `bild_orte.csv` (eine Zeile je Bild, aus den OpenStreetMap-Karten)
tauchte in keiner Pruefzeile auf. Genau die Stufe der Papas-Kette, die bis
zuletzt am laengsten offen war, war damit die einzige ohne Nachweis — und
„fertig ist, was verifiziert ist" verlangt fuer jede Stufe eine Zahl, die sich
wiederholen laesst.

Anlass im Nachtlauf: Der Kartenstapel ist in der Nacht durchgelaufen (alle
Gebiete fertig, `bild_orte.csv` geschrieben). Damit war die Frage „existiert die
Datei ueberhaupt, und was steht wirklich drin?" erstmals messbar.

## Was jetzt geprueft wird

Neuer Abschnitt **„Orte (OSM)"** in der Ausgabe:

* `bild_orte.csv`: Zeilen insgesamt (eine je Bild), davon **mit GPS**, **ohne
  GPS** (ehrliche Leerzeile) und **im Flug** (Fensterblick, keine Bodenverortung).
* Bilder mit **Ortsname**, **Landmarke**, **Strasse**, **Hausnummer**.
* Zahl der **Kartengebiete** mit beiden Tabellen
  (`osm/csv/<gebiet>/osm_orte.csv` UND `osm_adressen.csv`) — ein halb
  ausgewertetes Gebiet zaehlt nicht als fertig — dazu die Groesse der
  Gesamttabellen (`osm/csv/osm_orte.csv`, `osm/csv/osm_adressen.csv`).
* Fehlt `bild_orte.csv`, steht das als Luecke in der Ergebnisliste
  („Kartenauswertung nicht zugeordnet"), nicht als stiller Nullwert.

Wie der ganze Nachweis: **nur Zahlen.** Keine Ortsnamen, keine Strassen, keine
Koordinaten, kein Schreiben — das ist in den Tests festgehalten. Abschaltbar mit
`pruefen(..., bild_orte=None)`, wie die uebrigen Abschnitte.

## Messung am echten Bestand (10.10.2026, Exit 0)

```
Orte (OSM): bild_orte.csv: 18.840 Zeilen (eine je Bild) = 8.529 mit GPS
            + 10.306 ohne GPS + 5 im Flug
  Ortsname 8.068, Landmarke 8.210, Strasse 2.724, Hausnummer 2.724
  Karten: 15 Gebiete mit beiden Tabellen (osm/csv)
  Gesamttabellen: 183.805 Orte, 1.331.046 Adressen
```

Vollstaendige Ergebnisliste des Laufs (unveraendert ausser dem neuen
Abschnitt): 4 Luecken — `sortierplan.json` 3 Fotos ohne Beschreibung,
`sortierplan_bildervideos.json` 25 Videos ohne Gesichter-Lauf und 5 Fotos ohne
Beschreibung, Gesamtplan 8 Fotos ohne Beschreibung (Kennung und Grund benannt).

## Belege

* Tests: `backend/tests/test_bestand_und_handy_uebergabe.py` **23 passed**
  (3 neue: Zaehlung, ehrliche Meldung bei fehlender Datei, keine Namen im Text
  und nur fertige Gebiete).
* Lauf am echten Bestand: Exit 0, Ausgabe oben.

## Dateien

* `tools/foto_sortierung/bestand_pruefen.py` — `orte_lesen`, `karten_gebiete`,
  `tabellen_zeilen`, Abschnitt „Orte (OSM)".
* `backend/tests/test_bestand_und_handy_uebergabe.py` — 3 neue Tests.
