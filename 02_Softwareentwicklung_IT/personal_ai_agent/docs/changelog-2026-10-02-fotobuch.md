# Änderungsprotokoll 02.10.2026 — Digitales Fotobuch in der Erzähl-Diashow

Wunsch Sebastian: das erste Fotobuch (`Bilder & Videos/___Photobücher_Buddy_Jule`) Seite für Seite
durchgehen und Erinnerungen dazu erzählen; prüfen, was an den Daten lesbar ist.

## Befund (nur Zahlen, Inhalte nicht gelesen)

- 2.187 Dateien in 12 Unterordnern, 3,7 GB: 2.175 JPEG, je wenige TIFF/PSD/PNG, **eine CEWE-
  Projektdatei `.mcf`** (+ Sicherung `.mcf~`).
- `.mcf` (XML, 1,3 MB): 159 Seiten (154 Inhalt, 2 Umschlag, 2 leer, 1 Rücken), 860 Bildplätze mit
  Position, **alle 852 verwiesenen Dateien liegen im Ordner**, 130 Textfelder (HTML).
- Stichprobe 200 Fotos: 195 mit EXIF-Datum (2003–2010, auffällig 86× 2013 = vermutlich
  Scan-/Bearbeitungsdatum, 116 ohne Kameraangabe), nur 7 mit GPS, meist ~2.000 px.
- Folgerung: Das Buch nicht neu clustern — **die Buchseiten sind die Ordnung** (Momente in der
  damals gewählten Reihenfolge, mit den eigenen Texten).

## Was neu ist

- **`tools/foto_sortierung/fotobuch_lesen.py`**: liest die `.mcf` (nur lesend): je Inhaltsseite
  und Umschlag die Bilder in Lesereihenfolge (oben→unten, links→rechts) und die Texte (HTML →
  Klartext); pCloud-`fileid` über die vorhandene Ordner-Abfrage (`foto_themen.dateien_im_ordner`,
  ein `listfolder` je Unterordner). Schreibt `~/foto_sortierung/fotobuch_ereignisse.jsonl` im
  Format der Erzähl-Diashow (`kennung` eindeutig je Stelle im Buch, `event`/`titel` „Fotobuch
  Buddy Jule · S. 12 – <Textanfang>", `datei_kennungen`, `kategorie: Fotobuch`, `seite`,
  `texte`). Konsole nur Zahlen; Trockenlauf Standard, `--schreiben`, `--senden` (adb push +
  Größenprobe); Ziel im Repo → Exit 2, keine `.mcf` → Exit 3.
- **`erzaehl_service`**: liest zusätzlich `fotobuch_ereignisse.jsonl` (im Ordner der
  Ereignisdatei, `ERZAEHL_FOTOBUCH_PFAD`) und zeigt die Buchseiten **oben** in 📖 Erzählen;
  Geschichten je Bild wie gehabt (`geschichten.jsonl`).
- Übergabe: `fotobuch_ereignisse.jsonl` in den Listen von `start-termux.sh` und
  `termux/agent-ensure.sh`; Wächter jetzt 9 Dateien (Name aus `FOTOBUCH_DATEINAME`).

## Prüfung

- Neu `backend/tests/test_fotobuch.py` (6, erfundenes Mini-Buch): Buchreihenfolge, Bildreihenfolge
  nach Position, Pfad mit Unterordner, HTML→Text, zwei Umschläge mit eindeutiger Kennung, Seiten
  ohne gefundenes Bild und ohne Text fallen weg, Trockenlauf ohne Texte/Dateinamen, Schreiben,
  Schutz Repo-Ziel/fehlende `.mcf`, Diashow zeigt Buchseiten zuerst und liefert die Kennungen.
- `test_uebergabe_uebernehmen.py`: 9 Dateien; die Gegenprobe entfernt nur das alleinstehende
  `ereignisse.jsonl` (sonst traf sie auch `fotobuch_ereignisse.jsonl`).

## Lauf (Sebastian, Handy am Kabel)

    backend\.venv\Scripts\python.exe tools\foto_sortierung\fotobuch_lesen.py --senden

Dann am Handy Widget „agent" → Hey Agent → 📖 Erzählen: die Buchseiten stehen oben.
