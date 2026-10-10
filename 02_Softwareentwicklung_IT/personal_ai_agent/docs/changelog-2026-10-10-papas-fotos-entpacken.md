# Änderungsprotokoll 10.10.2026: Papas Amazon-Fotos auf dem Server entpacken

Anlass: Sebastians Papa hat 32 ZIP-Dateien mit **16,1 GB** Amazon-Fotos in die pCloud gelegt
(`/AmazonPhotosvonPapa`). Sie sollen in den normalen Bestand einsortiert werden — mit
derselben Kette wie die eigenen Bilder (Gesichter, Orte, Anlässe, Beschreibungen).

Freigabe Sebastian (10.10.2026, 04:30): entpacken nach
`Bilder & Videos/Papa (Amazon)/<Name des Archivs>`.

## Warum auf dem Server und nicht am PC

Ein Herunterladen und erneutes Hochladen wären 32 GB über die Leitung — Stunden und
Datenverkehr für nichts. pCloud kann Archive **auf seinem eigenen Server** entpacken
(`extractarchive`). Dabei geht kein Byte über die Leitung. Gemessen am kleinsten Archiv
(`AmazonPhotos (35).zip`, 180 MB): API-Aufruf **4,7 s**, danach arbeitet pCloud im
Hintergrund — nach **20 s** lagen **139 Dateien / 180 MB** im Zielordner.

## Schon gemessen, bevor etwas geschrieben wurde

- Die ZIPs sind **flach** (keine Unterordner). Geprüft wurde das ohne Download, nur über
  das Inhaltsverzeichnis am Dateiende (`Range`-Anfrage über `getfilelink`, dann EOCD und
  Central Directory gelesen).
- Rund **200 Bilder je Archiv**, Dateitypen `jpg`/`jpeg`, die Dateinamen tragen das
  Aufnahmedatum (`YYYYMMDD_HHMMSS…`) — für die spätere Sortierung ohne Bild-Lesen nutzbar.
- Zeitrechnung: 32 Archive × ~30 s ≈ **15–20 Minuten** für den ganzen Bestand.

## Was gebaut wurde

**Keine zweite Schreiblogik.** Erweitert wurde das bestehende Sicherheitsnetz
`tools/pcloud/pcloud_bewegungen.py`:

- `archiv_entpacken(fileid, ziel_id)` → `extractarchive`. Trockenlauf ist Standard.
- Der Zielordner wird **vor** dem Entpacken gelesen. Liegt dort schon etwas, wird nicht
  entpackt (`uebersprungen: True`, `grund: "ziel_nicht_leer"`). Damit ist der Aufruf
  **idempotent** und es kann kein vorhandenes Bild ersetzt werden.
- `ERLAUBTE_METHODEN` und `ERLAUBTE_ARTEN` um `extractarchive` erweitert — die Positivliste
  bleibt die einzige Stelle, an der ein Schreibweg entsteht.
- Neu `ordner_per_pfad(pfad)`: Ordner über den Pfad finden (nur lesend). Ein unbekannter Pfad
  ergibt einen Klartextfehler statt einer stillen 0 — sonst könnte ein Tippfehler in den
  Wurzelordner schreiben.
- Längeres Zeitlimit fürs Entpacken (`ENTPACKEN_TIMEOUT_SEKUNDEN = 300`).

Dazu der Durchlauf `tools/pcloud/pcloud_entpacken.py`:

- geht die Archive des Quellordners durch, legt je Archiv einen Zielordner an
  (`zielordner_finden_oder_bauen` — nie doppelt) und entpackt hinein.
- `--nur <text>` lässt **ein** Archiv laufen: erst messen, dann alle.
- `--schreiben` schaltet scharf; ohne den Schalter passiert nichts.
- Ausgabe in **Zahlen** (entpackt / übersprungen / Ordner neu / Fehler), keine Dateinamen.

## Rückholbarkeit

Jeder Entpackvorgang steht als Manifest-Zeile mit `fileid` (das Archiv) und `nach_folderid`
(der angelegte Ordner) — plus `taskid`, wenn pCloud eine Hintergrundaufgabe meldet. Das
Archiv selbst bleibt **unberührt**; zurückzunehmen wäre nur der entstandene Ordner. Das
Manifest liegt außerhalb des Repos (`~/foto_sortierung/manifest.jsonl`).

## Prüfung

- Neu `backend/tests/test_pcloud_entpacken.py` (7 Tests, offline) und 6 neue Tests in
  `test_pcloud_bewegungen.py` (34 insgesamt): Trockenlauf sendet nichts, leerer Ordner
  entpackt und bucht **eine** Zeile, gefüllter Ordner wird übersprungen, fehlender Token
  ergibt Klartext ohne Netz, der Token steht in keiner Buchung.
- Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **3599 passed, 2 skipped**, Exit 0 (vor dieser Änderung 3592 passed).
- **Echter Probelauf** an `AmazonPhotos (35).zip`: 1 Archiv entpackt, 0 übersprungen,
  0 Fehler; danach 139 Dateien im Zielordner gezählt (Zahl über die API, nicht geraten).
- Am Handy/Termux war nichts zu tun; der Schritt läuft rein in der Cloud.

## Nachtrag 10.10.2026, ca. 05:10: Schwall-Fehler und die Pause

Der erste Massenlauf meldete 16 Erfolge — **nachgezählt hatten aber nur 2 Archive wirklich
Inhalt.** 15 Aufrufe kamen mit pCloud-Fehler **3006** („Extracting of the archive failed“)
zurück, 15 meldeten Erfolg und lieferten (noch) nichts. Kein Größenmuster: das kleinste
(180 MB) und ein großes (696 MB) waren durch, alles andere nicht.

**Ursache:** nicht der Code, sondern der Schwall — 32 Aufträge in zweieinhalb Minuten. Nach
25 Minuten Pause lief dasselbe Archiv (`AmazonPhotos (33).zip`) ohne jede Änderung durch.

**Lehre für das Werkzeug:** Fortschritt niemals aus der Erfolgsmeldung ableiten, sondern per
`listfolder` nachzählen (macht das Werkzeug jetzt selbst, und `werkzeuge/fortschritt/` zählt
für die Anzeige mit). Und: `--pause <sekunden>` legt zwischen zwei Archiven eine Wartezeit
ein — Standard bleibt 0, der Massenlauf fährt mit 45 s. Zwei Tests halten das fest
(Wartezeit zwischen den Archiven, aber nicht nach dem letzten).

## Offen (bewusst nicht in diesem Schritt)

- Die 31 übrigen Archive. Sie laufen erst nach dem Probelauf — auf Sebastians Wort
  („alles nacheinander").
- Gesichter auf Papas Fotos, Orte, Anlässe und Beschreibungen: das ist die Kette danach.
- Beschreibungen erst an 50 Bildern messen (Kosten), dann entscheiden.
