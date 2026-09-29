# Änderungsprotokoll 29.09.2026: Video-Gesichter (E14b) und Personen-Register (E17)

## Was
- **Neu: `tools/foto_sortierung/video_gesichter.py`.** Findet Gesichter in pCloud-Videos.
  - **Auswahl:** nur die Video-Einträge des Plans (mp4, mov, 3gp, mkv, avi, m4v).
  - **Einzelbilder:** alle `--abstand-s` Sekunden ein Bild (Standard 2), höchstens `--max-frames` pro Video (Standard 60), bei langen Videos gleichmäßig verteilt.
  - **Ausgabe:** im Vektorzeilen-Format von `gesicht_erkennen.py`, mit `bild_id` = `<fileid>#t=<s>` und `video_id`. `personen_cluster.py` liest das direkt. Einzelbilder ohne Gesicht werden nur gezählt.
  - **Fortsetzen:** mit `--fortsetzen` über `video_id`s und die Fortschrittsdatei `<vektoren>.videos_fertig`. Videos ohne Gesicht gelten dort ebenfalls als erledigt.
  - **Wächter:** Ist das Modell nicht ladbar, endet das Werkzeug mit Exit 2, ebenso bei einem Repo-Pfad.
  - **Temporäre Datei:** Das Video liegt nur kurz im System-Temp (cv2 braucht einen Pfad) und wird im `finally` immer entfernt.
- **Neu: `tools/foto_sortierung/personen_register.py`.** Hält fest, wer auf welchem Bild ist.
  - **`bild_person.jsonl`:** ein Eintrag je Gesicht mit Person (Name aus `personen_bestaetigt.json`/Katalog oder Kennung), bbox, Gesichtsanteil, score und `zaehlt_mit`. `zaehlt_mit` gilt ab Anteil 0,004 und score 0,8, damit Hintergrundgesichter nicht mitzählen.
  - **`personen_uebersicht.json`:** je Person Anzahl der Bilder, erstes und letztes Datum sowie die häufigsten Begleiter.
  - **Abfrage `bilder_mit(..., "genau"|"mindestens")`:** „genau" liefert „nur David und ich". Unbenannte Gruppen zählen dabei als fremd.
  - **Wiederverwendung:** nutzt `lauf_rechnen`/`vektoren_lesen` aus `personen_cluster` und `bestaetigung_lesen` aus `personen_andocken`, ohne eigenen Parser.

## Warum
Sebastian will alle Bilder **und** Videos nach Personen sortiert haben. Außerdem soll es Diashows wie „nur mein Bruder und ich, von klein bis heute" geben (Plan E14b/E17).

## Prüfung
- `test_video_gesichter.py`: 15 passed, 1 skipped. Der echte cv2-Einzelbild-Test läuft nur im Gesichter-venv und steht dort noch aus.
- `test_personen_register.py`: 15 passed.
- Voller Prüfbefehl: 2979 passed, 1 skipped (Lauf durch den Ausführer). Der Pre-commit-Hook prüft erneut.

## Grenzen
- Videos haben kein Aufnahmedatum in `metadaten`, weil cv2 es nicht liest.
- Ein echter Lauf gegen die Daten folgt über Hermes.
