# Änderungsprotokoll 29.09.2026: Gesichter-Durchlauf fortsetzbar

## Was
- `tools/foto_sortierung/gesicht_erkennen.py` bekommt `--fortsetzen`: Es liest die vorhandene `--vektoren`-Datei, überspringt schon berechnete `bild_id`s und hängt an. `--max-bilder` gilt erst nach dem Filtern, also als Stapelgröße der noch offenen Bilder.
- `main` schreibt jede Zeile sofort und flusht dabei. Vorher wurde alles erst gesammelt, und ein Abbruch verlor den ganzen Lauf.
- Neue reine Funktionen `vorhandene_ids_lesen` (tolerant, zählt kaputte Zeilen) und `offene_eintraege`. `vektoren_schreiben(..., anhaengen=False)` setzt vor dem Anhängen ein Zeilenende, falls die letzte Zeile abgeschnitten ist.
- Eine nach einem Abbruch halbe Zeile bleibt als einzelne ungültige Zeile stehen, nichts wird abgeschnitten („nie löschen"). Ihr Bild gilt als offen und wird neu berechnet. `personen_cluster.py` und `orte_zuordnen.py` zählen solche Zeilen als ungültig und überspringen sie.

## Warum
Der Nachtlauf N-0929 hing an der Hermes-Sitzung und lief nach der Stichprobe nicht weiter: rund 5 Stunden Leerlauf. Bei 7.755 Bildern zu 2,4 s muss ein Abbruch ohne Verlust fortsetzbar sein.

## Prüfung
- `pytest tests/test_gesicht_erkennen.py`: 143 passed (vorher 133).
- Den vollen Prüfbefehl führt der Pre-commit-Hook aus.

## Nachtrag: Wächter gegen stumme Leerzeilen (29.09.2026, später am Vormittag)
- Befund: Im Nachtlauf lief `gesicht_erkennen.py` mit `backend/.venv`, das kein cv2 und kein onnxruntime hat. Jedes Bild wurde mit leerer Gesichtsliste geschrieben. Das Feld `fehler` landet nicht in der Ausgabezeile, deshalb fiel es nicht auf. 96 und 21 Zeilen enthielten nur Metadaten, **es wurden keine Gesichter berechnet**.
- Neu: `main` lädt mit `--schreiben` das Modell **vor** dem ersten Bild. Ist es nicht ladbar, bricht es mit einer deutschen Meldung und Exit 2 ab. Es wird nichts geholt und nichts geschrieben.
- Test: `test_main_bricht_ab_wenn_modell_nicht_ladbar`. `test_gesicht_erkennen.py` hat jetzt 144 passed.
