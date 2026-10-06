# Änderungsprotokoll 07.10.2026 — Orte aus den Karten (Adressen und Landmarken)

## Was
- Neu: `tools/foto_sortierung/orte_aus_karte.py` mit drei Betriebsarten.
  - **Karten auswerten** (`--karte <datei>`, mehrfach möglich): liest die Geofabrik-Kartenausschnitte (`.osm.pbf`, auch `.osm`) über `osmium` und schreibt je Gebiet zwei Tabellen: `osm_adressen.csv` (Straße, Hausnummer, Ort) und `osm_orte.csv` (Art, Name). Adressen werden an Einzelpunkten **und** an Wegen (Mittelpunkt) gelesen — deutsche Hausnummern hängen in OpenStreetMap meist am Gebäude.
  - **Zusammenfassen** (`--zusammenfassen`): verbindet die Gebiets-Tabellen zu einer Gesamttabelle; wiederholbar, baut immer neu aus den Einzeldateien.
  - **Bilder zuordnen** (`--zuordnen`): sucht zu jedem Bild mit GPS die nächste Adresse und die nächste Landmarke **je Art** (Restaurant, Berg, Wasser, Fluss, Wald, Schutzgebiet, Sehenswürdigkeit, Historisches, Kirche, Sport, Laden, Bahnhof, Flughafen, Haltestelle, Ort) und schreibt `bild_orte.csv` — **eine Zeile je Bild**, mit Aufnahmedatum; Bilder ohne GPS stehen als `ohne GPS` darin.
- Die Landmarken-Arten liegen in einer Tabelle aus `(Art, Schlüssel, Werte)`. Mehrere Zeilen je Art sind Absicht: „Wald" steht unter `natural` **und** `landuse` — als Wörterbuch würde eine der beiden Zeilen stillschweigend verschwinden (genau dieser Fehler war im ersten Entwurf und ist jetzt als Test festgehalten).
- Rein lokal: kein Netz, keine Bilder, keine Koordinaten auf dem Bildschirm. Zieldateien im Repo werden verweigert (Exit 2); ohne `--schreiben` wird nur gezählt.
- Neu: `backend/tests/test_orte_aus_karte.py` — 14 Prüfungen mit einer winzigen erfundenen `.osm`-Karte (Adresse am Punkt, Adresse am Weg, Restaurant, Dorf, Berg, Wald), Umkreisgrenze, GPS-Lesen, Zuordnungslauf, Trockenlauf, Repo-Sperre, Zusammenfassen (wiederholbar).
- Neu (außerhalb des Repos): `~/foto_sortierung/werkzeuge/osm_csv_lauf.sh` — wertet alle geladenen Gebiete aus (kleinste zuerst), fasst zusammen und ordnet die Bilder zu. Fertige Gebiete werden übersprungen, der Lauf ist also wiederaufnahmefähig.

## Warum
- Die bisherige Ortsstufe (`orte_zuordnen.py`, GeoNames) liefert nur Land, Region und Stadt. Für „wo bin ich hingefahren" fehlten **Straße mit Hausnummer** und die Landmarken (Naturschutzgebiet, Restaurant, Fluss, Berg, Wald).
- Sebastian hat die Karten ausdrücklich lokal bestellt („OpenStreetMap runterladen und dann lokal machen") und Tabellen statt XML („XML mal nicht, CSV").
- Mit Adresse und Landmarken kann die Erzählschicht später Sätze bilden wie „bei Thorsten und Thorsten in Zarrentin" oder „Nationalpark Plitvicer Seen" statt nur „Kroatien".

## Messung (Probe Schleswig-Holstein, echte Karte)
- Index: **769.685 Punkte** in 33.502 Rasterzellen.
  - Adressen 719.557 · Haltestelle 17.789 · Fluss 8.938 · Restaurant 7.106 · Ort 4.467 · Laden 2.925 · Sehenswürdigkeit 1.988 · Historisch 1.858 · Sport 1.545 · Wasser 1.144 · Kirche 1.074 · Schutzgebiet 771 · Bahnhof 238 · Berg 158 · Wald 127.
- Probe an sechs echten Bildpunkten, Beispiele:
  - 03.10.2015: **Elbstraße 52** (5 m) · Künstlerhaus Lauenburg (23 m) · Historische Altstadt Lauenburg/Elbe (35 m) · Restaurant „von Herzen" (16 m) — GeoNames sagt dazu nur „Schleswig-Holstein/Lauenburg".
  - Geesthacht: **Grenzstraße 1** (30 m) · Holsteiner Hof (249 m) · GeesthachtMuseum (564 m).
  - Basedow: **Am See 5** · Gasthaus Lanzer See (1.484 m) · Elbe-Lübeck-Kanal (131 m).

## Prüfung
- `cd backend && .venv/Scripts/python -m pytest tests/test_orte_aus_karte.py -q`: **14 passed**, Exit 0.
- Voller Prüfbefehl vor dem Commit: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **3449 passed, 1 skipped, Exit 0** (Grundstand 3435 + 14 neue), 210 s.
- Erster echter Gebietslauf (Hamburg, 4 Minuten): **293.330 Adressen, 22.253 Landmarken** — davon Restaurant 5.341, Historisch 5.150, Haltestelle 4.661, Kirche 411, Ort 413, Wald 75.

## Grenzen
- Die Entfernung ist Luftlinie, nicht Wegstrecke; bei Flüssen und Straßen kann der nächste Karteneintrag weiter weg liegen als der Ort, an dem das Bild entstand.
- Adressen gibt es nur, wo sie in OpenStreetMap eingetragen sind; in dünn besiedelten Gebieten bleibt die Spalte leer (ehrlich leer statt geraten).
- Wege werden über ihren Mittelpunkt verortet — bei sehr großen Gebäuden kann der Mittelpunkt einige Meter vom Hauseingang entfernt sein.
- Gebiete ohne heruntergeladene Karte bleiben ohne Adresse; die Bilder behalten dann die GeoNames-Orte aus `orte.jsonl`.
- Städtenamen aus der Karte (`ort_osm`) sind der jeweils **nächste** Eintrag — in Randlagen kann das der Nachbarort sein.
