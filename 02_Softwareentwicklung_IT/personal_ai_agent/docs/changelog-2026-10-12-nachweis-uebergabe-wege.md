# Nachtrag: Die Deckung der Übergabe wird jetzt JE WEG gemessen (12.10.2026)

Werkzeug: `tools/foto_sortierung/bestand_pruefen.py`, Abschnitt
„Übergabe-Listen (Deckung)". Test:
`backend/tests/test_bestand_und_handy_uebergabe.py` (75 → **79** Testfunktionen).
Code, Test und dieses Dokument liegen in einem Commit.

## Warum (gemessen, nicht angenommen)

Der Abschnitt aus Journal 29 stellte die Kabel-Listen gegen die Dateinamen, die
`backend/app` wirklich liest — und meldete „0 ohne Liste", also **kein Befund**.
Genau das war die Lücke: die Prüfung nahm die **Vereinigung** aller Listen und
sah deshalb nicht, dass seit dem 10.10. **zwei Wege** existieren:

- **Kabel** — die `--dateien`-Listen in `termux/start-vorbereiten.sh` (12 Namen)
  und `start-termux.sh` (12 Namen), abgeholt von
  `tools/handy/uebergabe_uebernehmen.py` aus dem Download-Ordner;
- **kabellos** — der pCloud-Ordner `/Agent/uebergabe`, gefüllt vom PC mit
  `tools/pcloud/uebergabe_hochladen.py`, geholt vom Gerät mit
  `termux/pcloud-uebernehmen.sh`. Dieser Weg hat im Baum **gar keine Liste**:
  was er liefert, steht nur in den Buchungen des Übergabe-Manifests.

Eine Datei, die ein Dienst liest und die nur auf EINEM Weg steht, kommt auf dem
anderen Weg nicht ans Gerät. Das war der Neben-Befund aus Journal 27 („zwei
Wege, zwei Listen") — bisher nur im Journal, in keiner Prüfzeile.

## Was jetzt gemessen wird

`uebergabe_deckung_pruefen(...)` nimmt die kabellosen Namen aus dem Manifest
(der Aufrufer liest es ohnehin schon) und liefert zusätzlich:

- `kabellos` — die Namen des kabellosen Weges,
- `nur_kabel` — gelesene Dateien, die nur auf der Kabel-Liste stehen,
- `nur_kabellos` — gelesene Dateien, die nur kabellos übergeben wurden.

Ehrlich statt still: wird das Manifest **nicht** gelesen (`uebergebene is None`),
bleiben `kabellos`/`nur_kabel`/`nur_kabellos` **`None`** und der Bericht sagt
„Kabelloser Weg nicht gemessen … bleibt offen" — kein geratener Nullwert.

Semantik nachgeschärft: „kommt nie ans Gerät" heißt jetzt **auf keinem der
beiden Wege** (keine Kabel-Liste, nicht kabellos übergeben). Eine Datei, die
kabellos übergeben wurde, ist nicht mehr „auf keiner Liste" — sie kommt eben nur
ohne Kabel an. Die Meldung wurde entsprechend umformuliert.

Ein Weg-Unterschied ist eine **Zeile, keine Lücke**: welcher Weg benutzt wird,
entscheidet Sebastian; eine Lücke wäre hier ein Dauer-Fehlalarm. „Auf keinem
Weg" bleibt dagegen eine Lücke (wie bisher).

Nur Zahlen und Dateinamen — kein Pfad, kein Inhalt (im Test mit dem Fantasiepfad
`C:/geheim` und `str(tmp_path) not in text` festgehalten).

## Messung am echten Bestand (12.10.2026, Exit 0, nur lesend)

```
Uebergabe-Listen (Deckung): termux/start-vorbereiten.sh: 12 Namen, 2 Stellen (gleich);
                            start-termux.sh: 12 Namen, 2 Stellen (gleich)
  Dienst liest 31 Datendateinamen; auf einer Liste 12, geraeteseitig 19, ohne Liste 0
  Kabelloser Weg: 8 Dateien im Manifest (Uebergabe-Liste des Kabels: 12);
                  nur kabelseitig 8, nur kabellos 0
  Nur ueber das KABEL ans Geraet - ohne Kabel fehlt sie dem Dienst (8): beziehungen.json,
    beziehungen.jsonl, bild_beschreibungen.jsonl, ereignisse.jsonl, fotobuch_ereignisse.jsonl,
    fotos_dateien.json, fotos_uebersicht.json, kontakte.json
  Uebergeben, aber von keinem Dienst gelesen (4): bild_beschreibungen_papa_reich.jsonl,
    bild_beschreibungen_reich.jsonl, bild_index.db, orte.jsonl
```

Gegenprobe des kabellosen Weges **per pCloud-API** (nur `listfolder`, nur lesend):
der Ordner `/Agent/uebergabe` führt genau **8 Einträge** — dieselben acht Namen
wie das Manifest. Die Manifest-Namen sind damit keine Behauptung, sondern
nachgezählt.

**Der Befund:** acht Dateien, die ein Dienst liest, kommen auf dem kabellosen Weg
**nicht** ans Gerät (sie stehen nur auf der Kabel-Liste). Ohne Kabel fehlen dem
Gerät also die Beziehungen (`beziehungen.jsonl`, `beziehungen.json`), die
Ereignis- und Fotobuch-Anlässe (`ereignisse.jsonl`, `fotobuch_ereignisse.jsonl`),
die Foto-Übersicht/-Dateiliste (`fotos_uebersicht.json`, `fotos_dateien.json`),
die Kontakte (`kontakte.json`) und die knappen Bildbeschreibungen
(`bild_beschreibungen.jsonl`). **Nichts geändert** — was kabellos mitgehen soll,
ist Sebastians Entscheidung (ein Lauf
`tools/pcloud/uebergabe_hochladen.py --dateien … --schreiben` würde es
nachholen).

Ergebnisliste unverändert **5 Lücken** (vier kosten-/gerätebunden, die fünfte =
2 Kennungen ohne Gruppe). Der Weg-Unterschied zählt bewusst nicht dazu.

## Nebenbei gemessen (nicht von mir geändert)

`orte.jsonl` (GeoNames-Namen) hat jetzt **9.252 Zeilen** (Journal 29 nannte
8.530) — eine fremde Sitzung hat dort nachgetragen; kein Befund, die Deckung
steht bei 9.252 von 23.916 Plan-Fotos.
