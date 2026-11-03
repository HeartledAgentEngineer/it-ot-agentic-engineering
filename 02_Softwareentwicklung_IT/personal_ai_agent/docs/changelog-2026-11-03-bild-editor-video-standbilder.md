# Changelog 03.11.2026 — Bild-Editor auf Video-Standbildern (F3)

## Befund

Auf Ausschnitten aus Videos (Standbildern) ließen sich Gesichter weder umbenennen noch
verschieben noch löschen.

## Ursache

Die gemeinsame Bildsicht `_bild_sicht` (Bild-Editor, „Bilder mit X", Erzählen) bekam ihre
Gesichter aus `_gesichter_je_bild_laden`. Diese Funktion überspringt jede Video-Zeile. Auf einem
Standbild gab es dadurch kein erkanntes Gesicht, und jede Änderung endete in „Dieses Gesicht gibt
es auf dem Bild nicht". Ausschließen und Zuordnen kannten Video-gids schon seit S2 (18.10.2026).

## Behoben

- `_je_bild_mit_standbildern`: Foto-Gesichter plus Video-Gesichter je Standbild
  (gid `<standbild_fileid>:<index>`, Rahmen × Skala, Maße des Standbilds). Ohne Standbild-Karte
  bleibt alles wie vorher.
- Zwischengespeichert, solange Gesichtsdatei und Karte dieselben (gemerkten) Objekte liefern.

## Prüfung

- Neu: `test_bild_editor_video.py` (6). Vorher 4 rot, die zwei Kontrolltests grün.
- Nachbartests Bild-Editor B1/B2, Quiz-Video, Erzählen-Personen: 189 grün.
