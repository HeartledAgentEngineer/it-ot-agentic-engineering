# Kabellose Übergabe ans Handy über pCloud (10.10.2026)

## Anlass

Die Ergebnisübergabe an das Handy lief bislang **nur über das Kabel**: Der PC
legte die Dateien in den freigegebenen Download-Ordner (`/sdcard/Download`), das
Widget-Skript holte sie beim Start mit `tools/handy/uebergabe_uebernehmen.py`.
Ohne Kabel — also im Alltag unterwegs — blieb das Handy damit auf dem alten
Stand. Sebastians Auftrag vom 10.10.2026: dieselbe Übergabe **kabellos über
pCloud**, ausgelöst beim Start (App-Knopf bzw. `termux/start-vorbereiten.sh`).

## Entscheidung

- Der Weg läuft über den **pCloud-Ordner `/Agent/uebergabe`** (fester Zielordner).
- **Ausdrücklich freigegeben sind auch die Gesichts-Vektoren und der
  Gesichtskatalog.** Das widerspricht der bisherigen Projektregel („Biometrie
  bleibt lokal — verlässt den PC nie") und ist deshalb in der Projekt-`CLAUDE.md`
  richtiggestellt: Sie gehen **weiterhin nicht ins Repository und nicht an einen
  fremden KI-Anbieter**, dürfen aber über die **eigene pCloud auf das eigene
  Gerät**.

## Was neu ist

**Rechner-Seite — `tools/pcloud/uebergabe_hochladen.py`**
- Nimmt eine Liste von Dateien (`--dateien`) oder einen Ordner (`--ordner`,
  eine Ebene, nicht rekursiv).
- Lädt nach `/Agent/uebergabe` hoch (`createfolderifnotexists` für den Ordner,
  `uploadfile` je Datei; Schreiben nur unter `/Agent/`).
- **Idempotent:** gleiche Größe **und** gleiche Prüfsumme wie beim letzten Lauf
  (steht im Manifest) heißt überspringen. `--alles` erzwingt einen Neu-Upload.
- Schreibt je übertragener Datei eine Manifest-Zeile (Zeit, Quelle, Ziel,
  Größe, Prüfsumme, fileid) **außerhalb des Repos** —
  Standard `~/foto_sortierung/uebergabe_manifest.jsonl`
  (`PCLOUD_UEBERGABE_MANIFEST` überschreibbar; ein Repo-Pfad wird abgewiesen).
- **Trockenlauf ist Standard**; `--schreiben` schaltet scharf. **Kein Löschen**,
  Token wird nie ausgegeben.

**Handy-Seite — `termux/pcloud-uebernehmen.sh`** (Muster
`termux/wissensdatei-uebernehmen.sh`)
- Ruft den Netz-Teil `tools/handy/pcloud_dateien_holen.py` auf (der auf dem Handy
  läuft): `listfolder` + `getfilelink`, Download ins Staging
  `$HOME/.cache/pcloud_uebergabe`, Liste der geholten Namen.
- Übernimmt je Datei an ihren Platz: **gleiche sha256 → nichts** (idempotent);
  sonst **zuerst** die vorhandene Fassung als `<ziel>.vor_<datum>` sichern (bei
  Kollision `_2`, `_3`, …), **dann** über `.teil` + Prüfsummenvergleich kopieren.
- Klare Protokollzeile (Zeit, Name, Größe, sha256, kopiert/übersprungen) nach
  `hermes_diag/pcloud_uebernahme.log` im freigegebenen Download-Ordner.
- **Exit immer 0**, fehlertolerant (kein Token / kein Netz / leerer Ordner →
  klare Zeile, Start läuft weiter), **nichts gelöscht**.

**Einbindung**
- Neuer Schritt **6b** in `termux/start-vorbereiten.sh` (der EINEN gemeinsamen
  Ablaufdatei für App-Knopf und Widget), direkt nach der Wissensdatei und vor
  dem Weckruf, mit `|| true` — der Start wird nie verhindert.

**Datenschutz-Regel (`CLAUDE.md`)**
- Abschnitt „Sicherheit: Fotos, Gesichter, Menschenmengen", Punkt „Biometrie":
  Gesichts-Vektoren und Katalog gehen **nicht** ins Repo und **nicht** an einen
  fremden KI-Anbieter; erlaubt ist seit dem 10.10.2026 die Übergabe an das
  **eigene Gerät** über die **eigene pCloud** (eigenes Konto). Grund und Datum
  stehen dabei.

## Prüfung

Offline, erfundene Daten in `tmp_path`, kein Netz, keine Zugangsdaten.

- Neu `backend/tests/test_pcloud_uebergabe.py` — **23 Tests**, alle grün:
  - Hochladen: Trockenlauf sendet nichts; Schreiben ruft `uploadfile` und bucht
    eine Manifest-Zeile; gleiche Prüfsumme → ohne Aufruf übersprungen; Netzfehler
    → klare Meldung ohne Absturz; Ziel außerhalb `/Agent/` und Manifest im Repo
    werden abgewiesen; ohne Token kein Netzaufruf; Token steht in keiner Ausgabe.
  - Holen: Dateien + Liste, leerer Ordner, fehlender Token, abweichende Größe.
  - Übernehmen (echter Git-Bash-Sandkasten): neue Datei kopiert; gleiche
    Prüfsumme → nichts; abweichend → erst Sicherung, dann Kopie (Reihenfolge im
    Protokoll geprüft), Kollision → `_2`; fehlende Quelle → Exit 0 mit Meldung;
    `bash -n` und reine LF.
- Angepasst: `backend/tests/test_ein_startweg.py` — der Sandkasten stubbten den
  neuen Schritt 6b und prüft seine Stelle in der Reihenfolge.
- Prüfbefehl des Projekts: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **3729 passed, 2 skipped, Exit 0** (231,17 s).
- `bash -n termux/pcloud-uebernehmen.sh` → Exit 0; reine LF (kein CR).

## Einmal am Handy nötig

Ein Schritt von Sebastian: beim nächsten Start des Handys läuft Schritt 6b
automatisch mit. Voraussetzung ist, dass der pCloud-Schlüssel auf dem Handy in
`backend/.env` steht (das macht der bestehende Schritt 3 im Startweg). Sobald der
PC einmal etwas nach `/Agent/uebergabe` hochgeladen hat, holt das Handy es beim
nächsten App-Knopf-/Widget-Start von selbst.

## Rückweg

Jede hochgeladene Datei steht als Manifest-Zeile (Quelle → Ziel, Größe,
Prüfsumme) in `~/foto_sortierung/uebergabe_manifest.jsonl`. Zurücknehmen heißt:
die Datei im pCloud-Ordner von Hand entfernen (Löschen ist bewusst nicht Teil der
Werkzeuge). Am Handy bleibt von jeder ersetzten Datei die Sicherung
`<ziel>.vor_<datum>` neben der Datei liegen — es wird nie etwas gelöscht.

## Vollzug: der erste echte kabellose Lauf (Nachtlauf 10./11.10.2026)

Der Weg ist nicht nur gebaut, er ist gelaufen — und dabei fiel eine Lücke auf.

- Um 17:12 legte der PC die ersten Ergebnisdateien nach `/Agent/uebergabe`:
  `bild_index.db` (104.251.392 B), `orte.jsonl`, `bild_orte.csv`,
  `ordner_ereignisse.jsonl`, `bild_beschreibungen_reich.jsonl`,
  `bild_beschreibungen_papa_reich.jsonl`. Je Datei eine Manifest-Zeile in
  `~/foto_sortierung/uebergabe_manifest.jsonl`.
- **Gefundene Lücke, geschlossen:** `--ordner ~/foto_sortierung` liest nur EINE
  Ebene — die um Papas Gruppen erweiterten Dateien in `personen_gruppen/` fielen
  dadurch durch. Sie wurden um 17:2x einzeln nachgeschoben:
  `gesicht_zuordnung.jsonl` (8.741.862 B) und `personen_beispiele.json`
  (1.595.146 B). `kennungen.json` gehört NICHT aufs Handy — kein Dienst liest es.
- **Nachweis (per API, `listfolder` + `getfilelink`):** der Ordner enthält jetzt
  8 Dateien; die sha256 der beiden nachgeschobenen stimmt mit dem Manifest überein
  (`gesicht_zuordnung.jsonl` c4381b60…, `personen_beispiele.json` abda14a4…),
  Größen gleich.
- **Flach ist richtig:** `gruppen_quiz._lesepfad` liest erst
  `~/foto_sortierung/personen_gruppen/<name>`, dann `~/foto_sortierung/<name>` —
  am Handy greift die flache Übergabe (dort gibt es keinen Unterordner).
- Am Handy ist nichts weiter zu tun: beim nächsten App-Knopf-/Widget-Start läuft
  Schritt 6b und holt die acht Dateien.
