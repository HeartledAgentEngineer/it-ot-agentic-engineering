# Papas Ortsnamen: 7 Bilder fehlten still — nachgetragen (13.10.2026)

## Ausgangslage (gemessen, nur lesend)

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`, Exit 0) meldete:

```
Orte (GeoNames): orte.jsonl: 9.252 Zeilen, 9.252 Bilder
  Deckung: 9.252 von 23.916 Plan-Fotos haben einen Ortsnamen (38,7 %)
```

Die Zeile nennt nur **eine** Zahl. Ob **alle** Bilder mit GPS-Daten auch einen Ortsnamen
haben, sagte sie nicht — und der Nachtrag der Ortsnamen (Kettenschritt 3b im Plan
`.hermes/plans/2026-10-10_nachtlauf-papas-fotos-und-chat.md`) war am 10.10. um 07:43
gefahren worden, **bevor** Papas Gesichtslauf fertig war (dessen Vektordatei wurde erst
10.10. 15:15 geschrieben; `orte.jsonl` stammt von 14:57). Der Verdacht war also:
Papa-Bilder mit GPS, die nie einen Ortsnamen bekamen.

## Befund (gemessen)

Gezählt wurde je Vektordatei, wie viele Bilder GPS tragen (`metadaten.gps`) und wie viele
davon eine Zeile in `orte.jsonl` haben:

| Vektordatei | Zeilen | mit GPS | in `orte.jsonl` | fehlten |
|---|---|---|---|---|
| `personen_vektoren_papa.jsonl` | 6.336 | 729 | 722 | **7** |
| `personen_vektoren_n0929_voll.jsonl` | 7.530 | 3.982 | 3.982 | 0 |
| `personen_vektoren_gedreht_neu.jsonl` | 2.373 | 1.710 | 1.710 | 0 |
| `personen_vektoren_n0929_bildervideos.jsonl` | 11.310 | 4.548 | 4.548 | 0 |
| `personen_vektoren_fotobuch.jsonl` | 839 | 0 | 0 | 0 |

**7 Papa-Fotos mit GPS ohne Ortsnamen** — genau der vermutete Zeitversatz. Die anderen vier
Quellen sind vollständig. Die Lücke war lautlos: keine Zeile des Nachweises nannte sie.

## Vorgehen (idempotent, nichts gelöscht)

1. **Sicherung zuerst, als Kopie:** `orte.jsonl` → `orte.jsonl.vorher_papa-20261013`
   (gleiche Größe, gleiche md5 `f90ae54c…`). Die Originaldatei wurde vorher nicht angefasst.
2. Trockenlauf `orte_zuordnen.py --eingabe personen_vektoren_papa.jsonl`:
   „mit GPS: 729, bereits vorhanden: 722, **neu zu berechnen: 7**".
3. Schreiben mit `--schreiben`: „**zugeordnet: 7**", Länder: Deutschland 7 (offline
   GeoNames, kein Netzdienst, keine Bilder, keine Kosten).

## Belege

* `orte.jsonl` jetzt **9.259 Zeilen / 9.259 verschiedene `bild_id` / 0 doppelt** (gezählt).
* Papa: **729 von 729** GPS-Bildern haben einen Ortsnamen (vorher 722).
* **Idempotenz belegt:** zweiter Trockenlauf „bereits vorhanden: **729**, neu zu berechnen: **0**".
* Nachweis frisch, Exit 0: „Orte (GeoNames): orte.jsonl: **9.259** Zeilen, 9.259 Bilder …
  Deckung: 9.259 von 23.916 Plan-Fotos haben einen Ortsnamen (38,7 %)".

## Ehrliche Grenzen

* Die Ortsnamen entstehen nur für Bilder **mit** GPS; 5.607 der 6.336 Papa-Fotos tragen
  keins — für sie bleibt es bei null Ortsnamen (kein Fehler).
* Der Nachweis **kann die Lücke weiterhin nicht selbst erkennen**: er zählt Zeilen, nicht
  GPS-Bilder gegen Ortszeilen. Eine Prüfzeile dafür gehört in `bestand_pruefen.py` — die
  Datei ist derzeit **fremd im Arbeitsbaum geändert** (uncommittete Arbeit des Master-Chats
  zur Frontend-Dateiliste). Sie wurde deshalb **nicht** angefasst; der Wächter bleibt als
  nächster freier Punkt notiert.
* Der Nachtrag ändert **nur** `orte.jsonl` (außerhalb des Repos, anhangend, nie löschend);
  die Daten am Handy kommen erst mit der nächsten Übergabe auf denselben Stand.

## Was unverändert bleibt

Zwei Ausgabedateien des Repos, kein Bild- oder Gesichtsdienst, kein Vision-Aufruf, kein Bild
an ein fremdes Modell, keine pCloud-Schreibzugriffe, keine Geräteeingriffe, keine
kostenpflichtigen Läufe. Die Sicherungskopie liegt daneben; gelöscht wurde nichts.
