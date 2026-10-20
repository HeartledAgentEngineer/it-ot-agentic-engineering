# Änderungsprotokoll 20.10.2026: Schnellprüfung mit Prüfstempel beim App-Start

## Anlass
Gemessen am 20.10.2026: Jedes Öffnen der Handy-App stößt `termux/start-vorbereiten.sh` an.
Darin rechneten `termux/wissensdatei-uebernehmen.sh` (memory.db, 230 MB) und
`termux/pcloud-uebernehmen.sh` (mehrere Dateien) bei **jedem** Lauf volle sha256 über Quelle
**und** Ziel, auch wenn nichts geändert war (Protokoll: jedes Mal „uebersprungen
(Pruefsumme gleich)“). Das lastete das Handy aus; die App zeigte „wird geladen …“ bzw.
„Server nicht erreichbar“.

## Änderung
- **Neu `termux/pruefstempel.sh`** (nur Funktionen, wird von beiden Skripten per `.` eingebunden):
  `stempel_zeile`, `stempel_passt`, `stempel_ziel_sha`, `stempel_schreiben`.
  Stempeldatei `<ziel>.pruefstempel`, drei Zeilen: (1) Quellpfad | Quellgröße + Quell-mtime |
  Zielgröße + Ziel-mtime, (2) geprüfte sha256, (3) Zielgröße + Ziel-mtime.
  `stempel_passt` ist nur wahr, wenn die Stempeldatei lesbar und vollständig ist, Zeile 1
  **exakt** der aktuellen Zeile entspricht und der Stempel jünger ist als
  `PRUEFSTEMPEL_MAX_ALTER_S` (Standard 86400 s = 1 Tag; ungültige Werte → Standard; ein Stempel
  aus der Zukunft gilt nicht). Jede Unklarheit (Stempel fehlt/leer/kaputt, `stat` scheitert,
  Ziel fehlt) heißt: volle Prüfung wie bisher. `stempel_schreiben` schreibt atomar
  (`.teil`, dann `mv`) und bricht nie ab. `PRUEFSTEMPEL_AUS=1` erzwingt immer die volle Prüfung.
- **`wissensdatei-uebernehmen.sh`:** Passt der Stempel, steht die Protokollzeile „WISSENSDATEI
  uebersprungen (Groesse und Zeit unveraendert seit letzter Pruefung, keine Pruefsumme)“ und das
  Skript endet mit Exit 0 – ohne eine einzige Prüfsumme. Der Stempel wird nach „gleich“ und nach
  erfolgreicher Übernahme (mit den Werten nach dem Kopieren) geschrieben. Sicherung vor Kopie,
  `.teil` + Prüfsumme, nie löschen und Exit immer 0 sind unverändert.
- **`pcloud-uebernehmen.sh`:** dasselbe je Datei (Protokollzeile „PCLOUD-Uebergabe <NAME>
  uebersprungen (Groesse und Zeit unveraendert seit letzter Pruefung, keine Pruefsumme)“).
  Zusatz, weil der Netz-Teil (`tools/handy/pcloud_dateien_holen.py`) die Staging-Dateien bei
  **jedem** Lauf neu schreibt (neue Quell-mtime, der volle Stempel passt dann nie): Ist das
  **Ziel** laut Stempel unverändert (Größe + mtime + Alter), wird dessen gestempelte sha256
  wiederverwendet (`stempel_ziel_sha`); nur die Quelle wird gerechnet. In diesem Fall wird der
  Stempel nicht erneuert, damit seine Altersgrenze die volle Prüfung nach spätestens einem Tag
  erzwingt.
- Fehlt `pruefstempel.sh`, laufen beide Skripte mit Ersatzfunktionen wie bisher (immer volle
  Prüfung).

## Grenzen (ehrlich)
- Gleiche Größe **und** gleiche mtime-Sekunde bei anderem Inhalt (oder eine von außen
  zurückgesetzte mtime) fällt bis zur Tagesgrenze nicht auf; danach prüft der Lauf wieder voll.
  Für sofortige volle Prüfung: `PRUEFSTEMPEL_AUS=1`.
- Zwischen Hashen und Stempelschreiben wird die Quelle nicht erneut gelesen; ändert sie sich in
  diesem Fenster, bleibt der Stempel einen Lauf lang unscharf (wird beim nächsten Wechsel von
  Größe/mtime ohnehin ungültig).
- Die pCloud-Übernahme lädt weiterhin bei jedem Lauf alle Dateien neu ins Staging (Netz und
  Quell-Prüfsumme); das ist ein eigener Befund und hier **nicht** geändert.
- Am Handy nicht gelaufen (Tests am PC in Git Bash; GNU `stat -c` in Termux und Git Bash).

## Prüfung
- Neu `backend/tests/test_pruefstempel.py` (29 Tests, echte Läufe in `tmp_path`, `sha256sum`-
  Zähler im PATH): erster Lauf + Stempel, zweiter Lauf ohne Prüfsumme, Quelle geändert, gleiche
  Größe/andere mtime, Stempel zu alt/aus der Zukunft, kaputter/leerer Stempel, `PRUEFSTEMPEL_AUS`,
  Ziel von außen verändert/gelöscht, pCloud-Grundform und Ziel-Prüfsummen-Wiederverwendung,
  Syntax (`bash -n`) und reine LF.
- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pruefstempel.py -q` → 29 passed.
