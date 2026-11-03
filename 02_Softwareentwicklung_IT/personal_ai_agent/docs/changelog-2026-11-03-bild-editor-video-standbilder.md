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

## Nachtrag — zweite Ursache im Frontend

- **Ursache 2:** `gesichtBearbeitbar` (`gruppen_quiz.js`) sperrte jedes Gesicht mit
  `video: true` für den Editor. Ein Standbild öffnete deshalb nur die Ansicht, ohne fileid.
  Der Backend-Fix oben kam am Handy so nie an.
- **Behoben:** Entscheidend ist nur noch die Kennung. Eine rein numerische Kennung (Foto oder
  fileid eines Standbilds) öffnet den Editor. `12#t=3` (Video ohne Standbild) bleibt Ansicht.
- **Prüfung:** `test_bild_editor_b4.js` erwartet jetzt den Editor mit `{fileid: "222"}`
  für das Standbild. Vorher 3 rot, jetzt 142 grün.
- Cache: `gruppen_quiz.js?v=20261103B`.
