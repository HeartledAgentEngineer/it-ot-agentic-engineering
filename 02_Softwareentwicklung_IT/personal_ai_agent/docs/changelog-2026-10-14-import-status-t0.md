# T0 — datensparsamer Quellenstatus der Fotokette (14.10.2026)

Auftrag: `.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md`, Abschnitt **T0**
(„Fotoquellen wirklich bis zum Handy nachweisen"). Dort steht als Ergebnis für den Nutzer eine
Statuszeile je Quelle — `entpackt → Bildindex → Gesichtserkennung → Gruppenbestand → auf diesem
Handy` — und ausdrücklich als **Hermes-Punkt** geführt („T0 läuft nebenher bei Hermes").

Angelegt wurde der dafür vorgesehene Dienst `backend/app/services/import_status.py` samt Tests
`backend/tests/test_import_status.py`. **Es wurde kein Bild geöffnet oder gesendet, kein
Vision-Aufruf, kein Netzaufruf, keine Modellkosten, kein Geräteeingriff, kein pCloud-Zugriff,
nichts gelöscht.** Alle Zahlen sind am echten Bestand auf dem PC gezählt (nur lesend), und im
Bericht stehen ausschließlich Summen: kein Pfad, kein Name, kein Ortswert, keine Bild-ID, kein
Vektor. Der Dienst liest nur; geschrieben wird nichts.

## 1. Die zwei harten Regeln des Auftrags — und wie sie festgehalten sind

1. **Nur Summen.** `plan_kennungen()`, `vektoren_zaehlen()`, `index_kennungen()` und
   `gruppen_zeilen()` geben nie die gelesenen Kennungen zurück, sondern nur ihre Anzahl. Der
   Test `test_bericht_traegt_keinen_pfad_und_keine_kennung` prüft das am **fertigen Bericht**:
   weder die Kennung, noch der Pfad, noch `/`, `\`, `.json`, `.jsonl` oder `.db` dürfen darin
   vorkommen.
2. **Fehlender Messwert ist `null`, nicht `0`.** Jede Station gibt `None` zurück, wenn die Datei
   fehlt oder nicht lesbar ist; welche Werte offen sind, steht namentlich in `fehlende_werte`.
   Ein **leerer** Plan (`[]`) ist dagegen gemessen (0 Bilder) und wird von einer fremden Form
   unterschieden — beides durch eigene Tests festgehalten.

Zusätzlich: die Stationen werden über **dieselben technischen Medienkennungen** (`fileid`)
abgeglichen, und die Gruppen gelten als **Bestand, kein Zuwachs** — `offene_gruppen` und
`spaeter_gruppen` tragen den Stand des ganzen Bestands in jeder Zeile und dürfen über die
Quellen nicht addiert werden (so im Bericht ausgewiesen).

## 2. Der Bericht am echten Bestand (14.10.2026, 13,6 s Laufzeit)

Je Quelle genau die zehn Felder des Berichtsvertrags:

| `quelle_typ` | `bilder_im_plan` | `bilder_im_index` | `bilder_mit_gesichtslauf` | `erkannte_gesichter` | `gesichter_im_gruppenbestand` |
|---|---|---|---|---|---|
| `fotos` | 7.616 | 7.613 | 7.530 | 20.060 | 6.522 |
| `bilder_und_videos` | 11.630 | 10.766 | 11.310 | 29.439 | 9.974 |
| `papas_album` | 6.336 | 6.336 | 6.336 | 23.246 | 13.048 |
| `neuausrichtung` | 2.373 | 2.373 | 2.373 | 4.526 | 1.020 |
| `fotobuch` | 842 | 840 | 839 | 2.606 | 1.286 |

Gruppenbestand (ganzer Bestand, gilt für jede Zeile): **1.367 Gruppen, 18 benannt, 1.349 offen,
0 „später", 30.830 Gesichter.** `offene_gruppen`/`spaeter_gruppen` stehen in jeder Zeile gleich
und sind **keine** Zahl neuer Personen.

Drei Quellen sind vollständig durchgezogen (Papas Album 6.336/6.336/6.336, Neuausrichtung
2.373/2.373/2.373, Fotobuch 842/840/839 = 99,6 %). Bei den zwei Sammlungsquellen fehlen noch
Bilder im Bildindex (7.616 → 7.613 und 11.630 → 10.766; die 8 bekannten Fotos ohne Beschreibung
und die Aufteilungen der Einzelpläne). Genau das ist der Zweck der Zeile: die fehlende Station
ist sofort sichtbar, statt in einer Gesamtzahl zu verschwinden.

## 3. Die fünfte Station ist heute ehrlich offen

`handy_stand_geprueft` ist **`null`** und steht in `fehlende_werte` — die Prüfung am Zielgerät
ist am PC nicht messbar, und `adb devices` ist in diesem Lauf leer (kein Gerät). Der Dienst
nimmt eine echte Messung als Wert entgegen (`handy_geprueft=True/False`, dann tragen alle Zeilen
sie); erfunden wird sie nicht. Der Test `test_geraetestation_ist_null_ohne_messung` hält beides
fest: ohne Messung `null` — nicht `False`, was „geprüft und abwesend" heißen würde.

## 4. Belege

- **Tests:** `backend/tests/test_import_status.py` — **19 Tests**, alle grün; sie decken den
  Berichtsvertrag, die vier Stationen, fehlende/kaputte/leere Dateien, Video-Standbilder
  (`#t=` zählt nicht als Bild), doppelte Kennungen, Plan als Liste und mit `bild_id`,
  Gruppen je Quelle, den Stand ohne Dateien, die Datensparsamkeit des Berichts, die
  Gerätestation, Wiederholbarkeit und Schreibfreiheit (Dateizeiten und Dateiliste unverändert)
  ab. Vorrichtungen sind synthetisch (erfundene Kennungen, erfundener Name).
- **Echter Lauf:** `import_status.status()` gegen `~/foto_sortierung` — 13,6 s, Zahlen der
  Tabelle oben, `fehlende_werte` nennt genau die fünf `handy_stand_geprueft`-Felder.
- **Kein Schreiben:** der Dienst öffnet den Bildindex mit `mode=ro` und schreibt nie; der
  Wiederholbarkeitstest vergleicht Dateizeiten vorher/nachher.
- **Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` — siehe Commit
  (Zahl und Exit-Code im Bericht).

## 5. Grenzen dieses Schritts (ehrlich)

- **Die Anzeige in der App fehlt noch.** T0 nennt den Dienst ausdrücklich „für die spätere
  Appanzeige"; die Oberfläche (Statuszeile unter „Datenstand") ist ein eigener Schritt und hängt
  am neuen Tor **P0 Sicherheit** (`.hermes/plans/2026-10-12_p0-sicherheit-app.md`), das vor
  allem liegt, was Vektoren aufs Handy bringt.
- **Die Gerätestation bleibt offen**, bis ein Gerät am Kabel hängt (oder der kabellose Stand
  ausgewertet wird). Sie wird nicht geschätzt.
- **`gesichter_im_gruppenbestand`** zählt Zeilen der Zuordnungsdatei mit gesetzter Gruppe, deren
  Medienkennung zum Plan der Quelle gehört. Gesichter **ohne** Gruppe zählen dort nicht mit —
  sie stehen in der Differenz zur Größe des Gesichts-Laufs.
- Die Zahlen der Sammlungsquellen sind eine **Momentaufnahme** (14.10.2026): laufende Nachträge
  verschieben sie, der Dienst misst bei jedem Aufruf neu.
