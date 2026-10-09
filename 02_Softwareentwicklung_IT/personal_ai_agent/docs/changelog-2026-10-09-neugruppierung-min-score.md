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

## Nachtrag: Sicherung auch beim vollen Neugruppieren (09.10.2026, ~23:45)

Befund vor dem ersten echten Schreiblauf: Nur `--nachtragen` sicherte die drei Gruppendateien
als `*.vorher`. Ein **voller** Lauf mit `--schreiben` ersetzte `gesicht_zuordnung.jsonl`,
`personen_beispiele.json` und `kennungen.json` ohne Rückweg. Außerdem überschreibt
`*.vorher` nie, weil es den Stand vor dem ersten Nachtragen festhält. Für einen zweiten
Rückweg reicht es deshalb nicht.

**Behoben:**
- Neu `_stempel_sichern`. Vor jedem vollen Schreiblauf werden die drei Dateien als
  `*.vorher_<JJJJMMTT_hhmmss>` kopiert.
- Die Konsole meldet jede Sicherung mit „gesichert: …“.
- Eine vorhandene Sicherung wird nie überschrieben.
- Die Repo-Prüfung läuft vor der Sicherung.

Tests: +2 in `test_personen_gruppieren.py`.
- Der zweite Schreiblauf sichert genau die drei vorherigen Fassungen, byte-gleich.
- Eine vorhandene Sicherung bleibt unangetastet.
- Zusammen mit `test_personen_gruppieren_nachtragen.py`: 40 passed.

**Messung Nachtlauf 09.10.:**
- 2.281 gedrehte Fotos neu erkannt, 51 lieferte pCloud nicht, 0 Fehler, 2 h 19 min.
- Trockenlauf mit neuer Datei vorn: 644 Gruppen und 1.003 ähnliche Paare.
- Je Name bleiben 90–100 % beim Namen, bei einer Person 66 %.
  - Deren fehlende Gesichter liegen zu 248 in einer überwiegend gleichen, unbenannten Gruppe
    (Benennen im Quiz genügt).
  - 64 liegen in einer Mischgruppe mit Kinderfotos zweier Personen.
- Aus gedrehten Fotos stammt davon nur 1 Gesicht.

## Nachtrag: Das Widget übernimmt jetzt auch (10.10.2026, ~00:30)

Befund am Handy: Nach dem Schreiben und `gruppen_aufs_handy.py --senden` zeigte das Quiz
weiter die alten Mischgruppen. Die zwei Dateien lagen unverändert in `/sdcard/Download`.

Ursache:
- Das Widget `termux/agent-start` rief `uebergabe_uebernehmen.py` **nie** auf.
- Die Übernahme stand nur in `start-termux.sh` und in `termux/agent-ensure.sh`, und dort nur,
  wenn das Backend gerade **nicht** lief.
- Der Hinweis „Widget antippen“ in `gruppen_aufs_handy.py` stimmte deshalb nicht.

**Behoben:**
- `agent-start` übernimmt nach `git pull` und vor dem Serverstart dieselbe Dateiliste wie
  `agent-ensure.sh`. Die Übernahme ist hart über sha256 geprüft, die alte Fassung wird als
  `*.vorher` gesichert.
- Der Aufruf endet mit `|| true` und kann den Start nie verhindern.

Tests: +3 Wächter in `test_uebergabe_uebernehmen.py`.
- Die Dateiliste ist vollständig.
- Die Reihenfolge stimmt: Pull, dann Übernahme, dann Server.
- Die Übernahme ist abgefangen.
- Widget und App führen dieselbe Liste.

**Wichtig beim ersten Mal:** bash liest ein laufendes Skript aus der Datei, die beim Start
offen war. `git pull` ersetzt `agent-start` durch eine neue Datei, der laufende Widget-Start
arbeitet aber noch die **alte** Fassung ab. Eine Änderung an `agent-start` selbst wirkt
deshalb erst beim **zweiten** Widget-Tipp. Python-Werkzeuge, die nach dem Pull aufgerufen
werden, sind dagegen sofort neu.
