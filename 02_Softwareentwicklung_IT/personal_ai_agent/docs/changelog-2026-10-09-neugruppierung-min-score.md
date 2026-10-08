# Änderungsprotokoll 09.10.2026: Neugruppierung mit Mindest-Sicherheit, Namen aus der Sicherung

## Anlass

Sebastian hat im Gruppen-Quiz die 20 größten Gruppen benannt. Danach kamen fast nur noch
Mischgruppen mit verschiedenen Personen und Gegenständen. Die Gruppen-Diagnose
(`docs/changelog-2026-10-08-gruppen-diagnose.md`) hat die Hauptursache gemessen:
**unsichere Funde** der Gesichtserkennung. Gruppiert wurde bisher ab `score` 0,6.
Gesichter unter 0,8 machen in Mischgruppen 81 % aus, in echten Gruppen 10 %.

Entscheidung Sebastian (08.10.2026): Die Gruppen werden komplett neu gebildet. Ein Filter
nur im Quiz reicht nicht.

## Neu

**`tools/foto_sortierung/personen_gruppieren.py`: Option `--min-score`**
- Legt die Mindest-Erkennungssicherheit fest, ab der ein Gesicht gruppiert wird.
- `gesichter_lesen(..., min_score=...)` gibt den Wert als `params` an
  `personen_cluster.gesichter_bewerten` weiter. Funde darunter bleiben ohne Gruppe.
- Ohne die Option gilt weiter 0,6, das Verhalten ist also unverändert.
- Für die Neugruppierung empfohlen: `--min-score 0.8`.
- Der Betriebsweg `--nachtragen` ist nicht berührt.
- Für die neu erkannten gedrehten Fotos ist die Reihenfolge der `--vektoren`-Dateien wichtig:
  Bei doppelter `bild_id` gewinnt die **erste** Datei. Deshalb steht die neue Datei vorn.
  Ein Test hält das jetzt fest.

**`tools/handy/namen_aus_sicherung.py`** (läuft am PC)
- Die Neugruppierung braucht die Namen aus dem Quiz, damit sie zwei benannte Personen nie
  zusammenlegt. Diese Namen liegen nur am Handy und in der verschlüsselten Termux-Sicherung.
- Das Werkzeug liest `home.tar.age` als Strom (`age -d`) und holt daraus **nur**
  `personen_bestaetigt.json` und `personen_vorgaben.json`. Sonst wird nichts entpackt.
- Es zeigt je Name die Gruppen und deren Größen. Mit `--ohne-namen` erscheinen nur Nummern.
- `--uebernehmen` schreibt beide Dateien nach `~/foto_sortierung/`:
  - eine vorhandene Datei wird vorher als `*.vorher` gesichert
  - ersetzt wird atomar über `*.neu`
- Exit-Codes: 0 ok, 1 Sicherung, Schlüssel oder `age` fehlt, 3 keine Namen in der Sicherung.

## Prüfung

- `backend/tests/test_personen_gruppieren.py`: zwei neue Tests.
  - Funde unter `--min-score` bleiben ohne Gruppe.
  - Bei doppelter `bild_id` gewinnt die erste Datei.
- Neu `backend/tests/test_namen_aus_sicherung.py`: 8 Tests, offline, erfundene Namen.
  - Es werden nur die zwei Dateien gelesen, auch mit führendem `./`.
  - Ohne `--uebernehmen` wird nichts geschrieben.
  - Die Sortierung folgt der Zahl der Gesichter.
  - `--ohne-namen` verbirgt die Namen.
  - `*.vorher` wird gesichert, es bleibt kein `*.neu` zurück.
  - Exit 1 und Exit 3 sind abgedeckt.
  - Ein Fehler beim Schließen des Stroms bricht nicht ab.
- Diese Dateien zusammen mit `test_personen_gruppieren_nachtragen.py`: **46 passed**.

## Gemessen (Trockenlauf 08.10.2026, nur Zahlen)

Grundlage sind die alten Vektordateien und die 20 benannten Gruppen (7 Namen) aus der
Sicherung. Mit `--min-score 0.8`:
- 627 statt 1.145 Gruppen
- 1.012 statt 29.098 ähnliche Gruppenpaare
- je Name bleiben 85–100 % der sicheren Gesichter in seinen Gruppen
- nur 11 Gesichter landen bei einem anderen Namen

**Noch offen:**
- Neuerkennung der 2.373 gedrehten Fotos: Nachtlauf seit 08./09.10.
- Danach ein Trockenlauf mit der neuen Datei vorn.
- Erst nach gemeinsamer Durchsicht wird mit `--schreiben` geschrieben und ans Handy übergeben.
