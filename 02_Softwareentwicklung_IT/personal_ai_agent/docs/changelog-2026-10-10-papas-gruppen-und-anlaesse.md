# Papas Gruppen angedockt und Anlässe für den Gesamtbestand gebaut (10.10.2026)

Beide Schritte sind reine Datenläufe (kein Code, alle Dateien außerhalb des Repos) — hier
stehen die Zahlen und der Rückweg.

## Schritt 4 — Papas Gesichter an die bestehenden Gruppen andocken

Voraussetzung war die fertige Vektordatei (`personen_vektoren_papa.jsonl`, 6.336 Zeilen —
siehe `changelog-2026-10-10-kachelgrenze-luecke.md`). Aufruf ohne `--schreiben` zuerst,
dann mit:

```
backend/.venv/Scripts/python.exe tools/foto_sortierung/personen_gruppieren.py \
    --nachtragen "C:/Users/sebas/foto_sortierung/personen_vektoren_papa.jsonl" --schreiben
```

Ergebnis (Trockenlauf und Schreibvorgang identisch):

```
Alte Zuordnung: 18793 Zeilen, 18793 Gesichter, 644 Kennungen (wortgleich uebernommen)
Neue Gesichter: 17773 (schon vorhanden, uebersprungen: 0)
Angedockt an bestehende Gruppen: 9821 Gesichter in 202 Gruppen
Neue Gruppen: 373 (Kennungen Person_1156..Person_1528)
Nicht angedockt (Rauschen): 4725
```

**Prüfkriterium erfüllt:** Der zweite Lauf mit `--schreiben` meldet
„Nichts zu tun: alle Gesichter stehen schon in der Zuordnung (es wurde NICHTS geschrieben)." —
also **0 neu** (idempotent).

`bestand_pruefen.py` (Exit 0) danach:

```
Gruppen (Stand 2026-10-10T15:26:17): 1.017 Gruppen mit 23.932 Gesichtern, benannt 18
  Groesse: 53 Gruppen >= 50 Gesichter, 224 >= 10, 793 unter 10; 673 mit Zwillingsverdacht
  Zuordnung: 36.566 Gesichter, davon 23.932 in einer Gruppe (65,4 %)
```

Vorher: 644 Gruppen, 10.884 Gesichter in Gruppen, 18.793 Gesichter zugeordnet (57,9 %). Die
Lücke „sortierplan_papa.json: 1.870 Fotos ohne Gesichtszeile" ist aus dem Ergebnis
verschwunden.

**Rückweg:** Vor dem Schreiben kopiert das Werkzeug die drei Dateien nach `*.vorher`; eine
vorhandene Sicherung wird bewusst **nicht** überschrieben — sie bleibt der Stand vor dem
ersten Nachtragen (dokumentiertes Verhalten). Es wurde nichts gelöscht.

**Zwillingsverdacht steigt von 382 auf 673 Gruppen.** Die Regel bleibt: Zwillings-Cluster
werden **nie** automatisch zusammengelegt, nur zur Sichtung markiert.

## Schritt 5 — Anlässe (Ereignisse) für den Gesamtbestand

**Entscheidung (im Dauerlauf getroffen, begründet):** Weg (b) aus der Plandatei — **ein**
Anlass-Bestand über den Union-Plan `sortierplan_reich_gesamt.json`, nicht eine zweite Datei
nur für Papa. Gründe: (1) Der Union-Plan enthält Papas 6.336 Fotos bereits (gemessen), eine
zweite Datei wäre eine zweite Wahrheit; (2) `ordner_ereignisse.jsonl` existierte **nicht** —
es wird also nichts überschrieben; (3) die App (`erzaehl_service`) liest genau diesen Namen,
damit wirkt der Bestand sofort.

```
backend/.venv/Scripts/python.exe tools/foto_sortierung/ereignisse_ordner_bauen.py \
    --plan "C:/Users/sebas/foto_sortierung/sortierplan_reich_gesamt.json" \
    --vektoren .../personen_vektoren_n0929_voll.jsonl .../personen_vektoren_n0929_bildervideos.jsonl \
               .../personen_vektoren_papa.jsonl --schreiben
```

Ergebnis:

```
Planzeilen:            28.796 (ohne fileid 0, doppelt 2.372, schon in anderen Anlässen 8.458)
aufgenommen:           17.107 Fotos, 859 Videos
Datum aus:             exif 15.643, dateiname 1.903, geaendert 0, ordnerjahr 42, planjahr 111, ohne 267
Anlässe:               2.268 (mit Datum 2.190, nur Jahr 23, ohne Jahr 55)
Jahre:                 1937–2026
Dateien je Anlass:     1 bis 678, Mitte 2
geschrieben: ordner_ereignisse.jsonl (2.268 Anlässe, außerhalb des Repos)
```

**Prüfkriterien erfüllt:** kein Bild doppelt (8.458 standen schon in `ereignisse.jsonl` /
`fotobuch_ereignisse.jsonl` und wurden übersprungen); zweiter Lauf meldet **„unverändert"**
(idempotent), Datei 2.268 Zeilen / 1,35 MB.

Messung am echten Bestand (nur lesend, nur Zahlen):

- **779 der 2.268 Anlässe enthalten Papa-Fotos** (Kennungen 108… gegen die Papa-Vektordatei).
- Der Dienst `erzaehl_service.anlaesse_zu_kennungen` liefert für 400 Papa-Kennungen
  **10 Anlässe** (Limit 10) — die Verknüpfung Gesicht → Anlass wirkt jetzt auch für Papa.
- 17.966 Datei-Kennungen stehen insgesamt in den Anlässen.

Damit ist der offene Punkt aus Schritt 7 der Plandatei („für Papa keine Anlässe, weil
`ordner_ereignisse.jsonl` fehlt") geschlossen.

## Was bewusst NICHT passiert ist

- **Nichts gelöscht.** Keine fremde Datei angefasst, keine `.vorher`-Sicherung überschrieben.
- **Kein pCloud-Schreibzugriff, keine Übergabe ans Handy** (das ist Schritt 9 und ein
  Geräteeingriff — bleibt Sebastian).
- **Keine Kategorien-/Event-Sortierung** für Papas Fotos (das würde pCloud-Moves bedeuten).
