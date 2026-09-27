# Duplikate per Prüfsumme: Upload-Baum gegen Sebastians Sammlung

> **Datum:** 27.09.2026 · **Auftrag:** Sebastian: „doppelte Dateien in der pCloud
> über **Prüfsummen** finden — Vergleich zwischen dem Upload-Stapel und meiner
> eigenen Ordnerstruktur. Belastbare Liste, damit ich entscheiden kann, was
> gelöscht wird." Rahmen: **nur lesend** — kein Download, kein Löschen, keine
> Schreibzugriffe auf die pCloud, keine git-Befehle.

| Datei | Inhalt |
|---|---|
| `tools/pcloud/pcloud_duplikate.py` | Das Werkzeug: liest beide Bäume per `listfolder` (nur Metadaten), gruppiert nach `(size, hash)`, schreibt den Bericht |
| `backend/tests/test_pcloud_duplikate.py` | **24 Prüfungen** — komplett offline (Attrappen für `listfolder`, kein Netz) |
| `docs/changelog-2026-09-27-duplikate-hashes.md` | Diese Doku |

## Warum Prüfsummen statt Namen

Datei**namen** sind als Beweis untauglich: Handy-Namen wie
`059956_2024-08-09_17-14-43_96.jpg`, WhatsApp-Empfang (`IMG-…-WA0001.jpg`),
Umbenennungen und Zusätze wie `(1)`/`(2)`/`- Kopie`. Zwei gleiche Namen können
verschiedene Inhalte tragen, zwei verschiedene Namen denselben Inhalt. Deshalb:

* `listfolder` liefert je Datei ein Feld **`hash`** — pClouds eigene Prüfsumme,
  live geprüft: 19-stellige Zahl (z. B. `6906308981406561991`) — und `size`.
* **Rechenweg:** Vergleichsschlüssel ist das Paar **`(size, hash)`**. Gleiche
  Größe **und** gleicher Hash = gleicher Inhalt. Gruppen mit mehr als einem
  Eintrag sind Duplikatgruppen.
* Nur Dateien mit **beiden** Werten werden verglichen. Fehlt die Prüfsumme, gibt
  es keinen Inhaltsbeweis — solche Dateien werden gezählt (im Live-Lauf: 0),
  nicht geraten. Kaputte/fremde Felder in der API-Antwort werden gezählt
  (`kaputte_eintraege`), nie zum Absturz.
* Der Hash ist konto-eigen: beide Bäume liegen in **derselben** pCloud, deshalb
  sind die Hashes untereinander vergleichbar. Es wird **nicht** behauptet, dass
  er einem bestimmten Verfahren (SHA, CRC) entspricht.

## Was das Werkzeug tut — und wo es anhält

1. **Wurzel genau EINMAL** lesen (`listfolder` auf `folderid 0`), um die
   Kennungen von `Automatic Upload` und `Bilder & Videos` zu finden. Danach
   wird die Wurzel **nicht** weiter durchsucht — kein rekursiver Lauf über sie.
2. Je Baum ein Lauf per Warteschlange: **jeder Ordner wird genau EINMAL
   gelesen** („gesehen"-Menge), keine Wiederholung, keine Retry-Schleife,
   keine Stapel-Downloads.
3. Grenzen und Ehrlichkeit: `--tiefe` (Standard 8) und `--ordner-max`
   (Standard 2000 Leseaufrufe je Baum). Was nicht gelesen wurde, steht als
   `uebersprungen_tiefe`, `abgebrochen` und `offen_gelassen` im Bericht.
   Erreichte **Tiefe** und **Knotenzahl** werden je Baum protokolliert.
4. Gruppieren nach `(size, hash)`, Kandidaten wählen, Bericht schreiben,
   Konsole zeigen.

**Schalter:** `--tiefe N` · `--quelle PFAD` (JSON-Ausgabe, Standard
`~/foto_sortierung/duplikate.json`) · `--ohne-sammlung` (nur Upload-Baum) ·
`--trocken` (Standard und **einziger** Modus: nur zählen und die Datei
schreiben) · `--ordner-max N` · `--beispiele N` (Standard 5).
Rückgabewerte: **0** = Bericht geschrieben, **2** = Bedien-/Konfigurationsfehler
(fehlender Token, fehlende Zielordner, Ausgabepfad im Repo, pCloud-Fehler).

## Was der Lauf NICHT tut (ausdrücklich)

* **Kein Löschen, nirgends.** Es gibt in der Datei keinen Entfernungs-Befehl,
  keinen Papierkorb-Weg und keinen Schalter dafür — ein Suchtest prüft, dass die
  verbotenen Befehlsnamen im Quelltext nicht vorkommen. Gelöscht wird später
  allein Sebastian, nach Sicht auf die Liste.
* **Kein Download:** gelesen werden nur Metadaten (Name, Größe, Hash,
  Zeitstempel). Kein Datei-Inhalt, keine Vorschaubilder (ein zweiter Suchtest
  prüft genau das).
* **Kein Schreiben in die pCloud:** die Positivliste `ERLAUBTE_METHODEN`
  enthält **genau einen** Eintrag: `listfolder`. Jede andere Methode wird
  abgewiesen, BEVOR etwas gesendet wird (per Test belegt).
* **Keine Ausgabe im Repo:** der Bericht enthält eigene Dateinamen und Pfade;
  ein Ausgabepfad im Repo wird mit Klartextmeldung und `SystemExit(2)`
  abgelehnt. `~` wird ausgeschrieben (Fund unten).
* **Kein Geheimnis in der Ausgabe:** der Token kommt aus der Umgebung oder
  `backend/.env`, wird nie ausgegeben und steht in keiner Zeile des Berichts
  (per Test belegt).

## Lösch-Regel (Kandidat = Upload-Kopie)

* **Über die Bäume hinweg:** jede Kopie im Baum **`upload`** ist Kandidat — das
  Sammlungs-Original bleibt unberührt.
* **Innerhalb `upload`:** EINE Kopie bleibt stehen (sonst wäre die Datei ganz
  weg), die weiteren sind Kandidaten.
* **Innerhalb `sammlung`:** **gar keine** Kandidaten — die Sammlung ist tabu,
  dort entscheidet Sebastian selbst.

## Ausgabeformat (`~/foto_sortierung/duplikate.json`, nie im Repo)

```json
{
  "stand": "2026-09-27T22:15:30+02:00", "trocken": true, "tiefe_grenze": 8,
  "regel_kandidat": "Loesch-Kandidat ist immer die Kopie im Baum 'upload' …",
  "baeume": { "upload": { "ordner_gelesen": 20, "dateien": 12080, "knoten": 12100,
              "tiefe_erreicht": 7, "tiefe_grenze": 8, "aufrufe": 20,
              "abgebrochen": false, "offen_gelassen": 0, "uebersprungen_tiefe": 0,
              "ohne_hash": 0, "ohne_groesse": 0, "ohne_kennung": 0,
              "kaputte_eintraege": 0, "wiederholte_ordner": 0 },
              "sammlung": { "…": "gleiche Felder" } },
  "gruppen": [ { "size": 500, "hash": 1234567890123456789, "hash_text": "…",
                 "anzahl": 2, "art": "ueber_baeume",
                 "mitglieder": [ { "fileid": 7, "name": "IMG_1.jpg",
                                   "pfad": "Automatic Upload/…", "baum": "upload",
                                   "created": "…", "modified": "…" } ],
                 "loesch_kandidaten": [ { "fileid": 7, "name": "IMG_1.jpg",
                                          "pfad": "…", "baum": "upload" } ] } ],
  "loesch_kandidaten": { "dateien": 2133, "mb": 17465.7, "liste": [ … ] },
  "zusammenfassung": { "gescannte_dateien": 23715, "vergleichbare_dateien": 23715,
                       "duplikatgruppen": 2606, "betroffene_dateien": 6467,
                       "mb_alle_kopien": 45393.1, "mb_freigabe_kandidaten": 17465.7,
                       "ueber_baeume": { "gruppen": 1299, "dateien": 3808, "mb_alle_kopien": 31051.5 },
                       "innerhalb": { "upload": { … }, "sammlung": { … } },
                       "loesch_kandidaten": { "dateien": 2133, "mb": 17465.7 } } }
```

`art` ist eines von `ueber_baeume` (Upload-Kopie vs. Sammlung-Original),
`innerhalb_upload`, `innerhalb_sammlung`. Auf der **Konsole** erscheinen nur
Zahlen, die ersten `--beispiele` Gruppen mit Namen und die Lösch-Kandidaten
ausdrücklich als `LOESCH-KANDIDAT (Upload-Kopie)` — die vollständige Liste
steht in der JSON-Datei.

## Live-Lauf 27.09.2026 (nur gelesen, eapi.pcloud.com)

* **192 `listfolder`-Aufrufe** (1 Wurzel + 20 + 171), Laufzeit **~55 s**.
* `Automatic Upload`: **20 Ordner, 12.080 Dateien** (12.100 Knoten), Tiefe
  erreicht **7** (Grenze 8).
* `Bilder & Videos`: **171 Ordner, 11.635 Dateien** (11.806 Knoten), Tiefe
  erreicht **4**.
* Vollständig gelesen: `uebersprungen_tiefe 0`, `abgebrochen false`,
  `ohne_hash 0`, `kaputte_eintraege 0` — **alle 23.715 Dateien vergleichbar**.
* **2.606 Duplikatgruppen, 6.467 betroffene Dateien**, Summe aller Kopien
  **45.393,1 MB**; mögliche Freigabe (nur Kandidaten) **17.465,7 MB**.
  * über die Bäume hinweg: **1.299** Gruppen / 3.808 Dateien / 31.051,5 MB
  * innerhalb `upload`: **329** Gruppen / 660 Dateien / 7.202,7 MB
  * innerhalb `sammlung`: **978** Gruppen / 1.999 Dateien / 7.138,8 MB
* **Lösch-Kandidaten (nur Baum `upload`): 2.133 Dateien / 17.465,7 MB.**
* Beispiele aus der Liste: 1.035,4 MB großes Video (6 Fassungen: 2 Upload-Kopien
  + 4 Sammlungs-Dateien), 298,9 MB `VID20230804143540.mp4` (Upload ↔ „Wacken
  2023"), 207,3 MB `MOV_0989 - Kopie.mp4` vs. `MOV_0989.mp4` — Letzteres
  **innerhalb** der Sammlung, deshalb **kein** Kandidat.
* Bericht: **3,42 MB** JSON in `~/foto_sortierung/duplikate.json`. Der Token
  steht nicht darin (nachgeprüft).

**Live-Fund (behoben):** pCloud liefert `hash` als **Zahl**, nicht als Text —
der Vergleich normalisiert deshalb auf Text. Und: der Standardpfad
`~/foto_sortierung/duplikate.json` wurde beim ersten Lauf als „im Repo"
abgelehnt, weil `~` ohne Ausschreiben wie ein Unterordner des
Arbeitsverzeichnisses aussah; jetzt wird `~` vor der Repo-Prüfung
ausgeschrieben (eigener Test dafür).

## Beleg und Neustart (Prüfbefehl)

```bash
cd backend
# Prüfbefehl (Exit-Code 0): 24 neue Prüfungen + gesamter Bestand
.venv/Scripts/python -m pytest tests/ -q
# -> 1473 passed, Exit 0 (27.09.2026)

# Live-Lauf, nur lesend (schreibt ~/foto_sortierung/duplikate.json):
.venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py --beispiele 5
# Nur der Upload-Baum, eigene Ausgabedatei:
.venv/Scripts/python ../tools/pcloud/pcloud_duplikate.py --ohne-sammlung --quelle ~/foto_sortierung/duplikate_upload.json
```

Der Lauf ist beliebig oft wiederholbar (idempotent: er liest nur und
überschreibt die Ausgabedatei atomar über `.tmp` + `os.replace`); ein zweiter
Lauf liefert dieselben Gruppen, solange sich die pCloud nicht ändert.
