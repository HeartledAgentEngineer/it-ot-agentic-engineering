# `bild_orte.csv` kannte Papas Fotos gar nicht — Ursache war die Standardliste (13.10.2026)

## Ausgangslage (gemessen, nur lesend)

Nach dem Ortsnamen-Nachtrag (Changelog `changelog-2026-10-13-papas-orte-nachgetragen.md`) fiel beim
Gegenprüfen der zweiten Orts-Stufe auf: in `bild_orte.csv` (OSM-Detail je Bild) kam **keine einzige**
Papa-Kennung vor.

```
alt:   18.840 Zeilen — Papa-Zeilen darin: 0        (Sammlung: 7.530 + 11.310 = 18.840)
```

Die Datei war also exakt die Summe der beiden Sammel-Vektordateien; Papas 6.336 Fotos (729 mit GPS)
fehlten vollständig.

## Ursache (belegt, keine Vermutung)

`tools/foto_sortierung/orte_aus_karte.py` führt eine Standardliste `STANDARD_VEKTOREN`. Die beiden
Startskripte `osm_csv_lauf.sh` und `osm_abschluss.sh` rufen das Werkzeug **ohne** `--vektoren` — es
entscheidet also diese Liste, welche Fotos vorkommen. In ihr standen nur die zwei Sammel-Dateien
(`personen_vektoren_n0929_bildervideos.jsonl`, `..._voll.jsonl`); `personen_vektoren_papa.jsonl`
entstand erst am 10.10. 15:15, also **nach** dem Bau der Liste. Folge: Papas Fotos fehlten still —
in `bild_orte.csv` **und** im Umkreis der Kartenauswertung (was rund um ihre Standorte lag, konnte
verworfen werden).

Dieselbe Zahl von beiden Seiten geprüft: 18.840 Zeilen = 7.530 + 11.310 (die zwei Listendateien),
Zusammentreffen der GPS-Kennungen mit der Datei = **0 von 729**.

## Vorgehen

1. **Zuerst gemessen, nicht gleich geschrieben:** Probelauf mit ausdrücklich allen vier Vektordateien
   in eine **eigene** Zieldatei (`--bild-orte bild_orte_probe_papa.csv`): 25.177 Zeilen, 9.259 mit
   GPS. Prüfsumme der Probedatei: `131a77995bb03009…` (16 Stellen).
2. **Der Standard wurde berichtigt** (`STANDARD_VEKTOREN`): `personen_vektoren_papa.jsonl` und
   `personen_vektoren_gedreht_neu.jsonl` sind jetzt dabei, mit Begründung im Code („zweite Wahrheit:
   entsteht eine neue Vektordatei, gehört sie hier hinein, sonst fehlen ihre Bilder still").
   `personen_vektoren_fotobuch.jsonl` bleibt bewusst draußen: 839 Scans ohne GPS brächten nur leere
   Zeilen. Der Modulkopf erklärt das jetzt.
3. **Neu erzeugt** (Sicherung **zuerst als Kopie**: `bild_orte.csv.vorher_papa-20261013`, 3.274.756 B,
   unverändert erhalten) — Aufruf **ohne** `--vektoren`, also genau über den neuen Standard:
   „Bilder: 25177 | mit GPS: 9259 | während des Flugs: 5", „geschrieben: … (25177 Zeilen)".

## Belege

* **Obermenge, nichts verschwunden** (Zeile für Zeile verglichen): von den alten 18.840 Zeilen fehlen
  **0**, inhaltlich geändert **0**; dazu **6.337** neue Zeilen.
* **Papa ist jetzt drin:** 729 Papa-Zeilen mit GPS, davon 582 mit Ortsname, 578 mit Landmarke.
* Die Probe-Zieldatei ist **byte-gleich** zur neuen echten Datei (Prüfsumme `131a77995bb03009…`).
* **Der Nachweis liest die neue Datei** (`bestand_pruefen.py`, Exit 0):
  „Orte (OSM): bild_orte.csv: **25.177 Zeilen** (eine je Bild) = 9.258 mit GPS + 15.914 ohne GPS + 5 im
  Flug; Ortsname 8.650, Landmarke 8.788, Strasse 2.790" (vorher 18.840 / 8.529 / Ortsname 8.068).
* **Test (Regressionshaken):** `test_orte_aus_karte.py` **24 → 25** Testfunktionen, Lauf **25 passed**
  (1,22 s). Der neue Test lädt ein **frisches** Modul (die Test-Vorrichtung ersetzt den Standard
  bewusst durch einen leeren Pfad) und hält fest, dass genau die vier GPS-Dateien im Standard stehen
  und die Fotobuch-Scans nicht.

## Ehrlich: was dieser Schritt NICHT gelöst hat

* **Papas Treffer sind dünner als bei der Sammlung** — gemessen an derselben Datei: Papa 80 % Ortsname
  / 79 % Landmarke / 9 % Straße gegen Sammlung 95 % / 96 % / 32 %. Zwei Gründe, beide offen:
  (a) die Kartenauswertung behält nur Orte **im Umkreis der Fotos der Standardliste** — rund um Papas
  Standorte wurde also damals nichts behalten, weil seine Datei noch fehlte; ein **Neubau der
  Gebietstabellen** (15 Gebiete, grob 3–10 h, lokal und kostenfrei) würde das beheben.
  (b) Für einen Teil von Papas Aufnahmen gibt es **keine** Karte: Baden-Württemberg 28, Italien 8,
  Schweiz 5, Festland-Spanien 1 (Standorte aus `orte.jsonl`, nur Länder/Regionen gezählt).
* **Keine Adressen** für Papas Regionen: Schleswig-Holstein hat seit der Entscheidung vom 07.10.
  („Brauche nicht alle Adressen") keine Adresstabelle — Papas 9 % Straßen sind die wenigen Orte, für
  die es eine gibt. Das ist Sebastians Entscheidung, nicht ein Fehler.
* **Beide Punkte sind Entscheidungen**, nicht Nachtarbeit: der Tabellen-Neubau kostet Stunden
  Rechenzeit, die fehlenden Karten sind Downloads. Gestartet wurde nichts davon.
* Die neue `bild_orte.csv` liegt **am PC**; das Handy bekommt sie erst mit der nächsten Übergabe
  (Kettenschritt 9). Die Sicherung von vorher liegt daneben, gelöscht wurde nichts.

## Was unverändert bleibt

Kein Netz (die Karten liegen lokal), keine Bilder geöffnet oder gesendet, kein fremdes Modell, keine
pCloud-Schreibzugriffe, keine Geräteeingriffe, keine Kosten. Geändert wurden zwei Dateien des Repos
(Werkzeug + Test) und die Datendatei außerhalb des Repos; die Probe- und die Sicherungsdatei bleiben
liegen.
