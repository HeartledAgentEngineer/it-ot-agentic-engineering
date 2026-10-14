# 14.10.2026 – Standbilder der Video-Gesichter (Video-Gesichter im Quiz, Schritt V1)

## Anlass

Ein großer Teil der Gesichter in `gesicht_zuordnung.jsonl` stammt aus Videos (Felder
`video_id`, `zeit_s`, `bbox` im Frame). Diese Frames gibt es nirgends als Bild. Deshalb
überspringt das Quiz sie (`gruppen_quiz._gesichter_laden`). Reine Video-Vorschläge
blieben leer.

Plan: `.hermes/plans/2026-10-14_video-gesichter-im-quiz.md` (Fassung 3, Codex FREI).

## Neu

`tools/foto_sortierung/video_standbilder.py` – Werkzeug am PC:

- **Auswahl:** je Gruppe die besten Video-Gesichter (`anteil × score`, `--max-je-gruppe`,
  Standard 8), je Frame höchstens eines.
  - `--umfang nur_video` (Standard): nur Gruppen ohne Foto-Gesicht.
  - `--umfang alle`: alle Gruppen.
- **Jedes Video nur einmal:** Das Video wird über `PCloudService.datei_bytes` geladen
  (`--max-mb`, Standard 300) und liegt nur als flüchtige Temp-Datei vor. Diese wird immer
  entfernt.
- **Standbild je Zeitpunkt:** cv2 springt wie beim Erzeugen per `CAP_PROP_POS_MSEC`.
  - **Maß-Gegenprobe:** Weicht das Frame-Maß von `breite`/`hoehe` der Gesichtszeile ab,
    wird nichts eingetragen (Zähler `mass_abweichend`). Ein falscher Rahmen erscheint so nie.
  - Das Bild wird auf höchstens 1600 px verkleinert (`--max-seite`) und als JPEG 85
    gespeichert.
- **Hochladen** nur über `tools/pcloud/uebergabe_hochladen.py`
  (`createfolderifnotexists` + `uploadfile`) nach `/Agent/video_standbilder/`.
  Nichts wird gelöscht oder umbenannt.
- **Idempotent:**
  - fester Name `<video_id>_t<zeit>.jpg`;
  - vor dem Lauf wird der Zielordner gelesen, ein vorhandenes Standbild wird wiederverwendet
    statt erneut hochgeladen (Abbruch zwischen Hochladen und Eintrag);
  - schon eingetragene `bild_id`s und fertige Videos werden übersprungen.
- **Ergebnisdatei** `~/foto_sortierung/personen_gruppen/video_standbilder.jsonl`:
  - jede Zeile wird sofort geschrieben (flush + fsync);
  - Felder `bild_id`, `video_id`, `zeit_s`, `standbild_fileid`, `breite`/`hoehe` (Maß des
    Standbilds), `skala`, `stand`;
  - der Gesichtsrahmen im Standbild ist `bbox × skala`.
- Der Dateiname ist eine gemeinsame Konstante mit dem Quiz:
  `gruppen_quiz.VIDEO_STANDBILDER_DATEINAME`.
- **Regeln:**
  - Trockenlauf ist Standard (nur Zählung, kein Netz). `--groessen` fragt zusätzlich nur
    lesend die Download-Menge ab.
  - `--schreiben` schaltet scharf.
  - Liegt das Ergebnis im Repo, endet der Lauf mit Exit 2.
  - Die Konsole zeigt nur Zahlen.
  - `--uebergeben` reicht die Ergebnisdatei danach über
    `uebergabe_hochladen.main([... "--schreiben"])` kabellos ans Handy.

**Rückweg:** den Ordner `/Agent/video_standbilder/` in pCloud und die Ergebnisdatei von
Hand entfernen. Das Werkzeug löscht nie.

## Tests

Neu: `backend/tests/test_video_standbilder.py`, 24 Tests, offline, mit erfundenen
Kennungen und Attrappen für pCloud, Hochladen und Frame-Entnahme.

Geprüft werden:
- Auswahl und Umfang;
- ein Ladevorgang je Video;
- Wiederverwendung vorhandener Standbilder;
- Maß-Gegenprobe;
- zu großes Video;
- Hochladefehler ohne Abbruch des Videos;
- nicht lesbare Frames;
- Trockenlauf ohne Netz;
- zweiter Lauf ohne Arbeit;
- `--uebergeben`;
- Repo-Ziel mit Exit 2;
- gemeinsamer Dateiname.

Ein Test baut ein künstliches Video und läuft echt durch cv2. Im Backend-venv fehlt cv2,
dort wird er übersprungen. Im Gesichter-venv (OpenCV 5.0.0) wurde derselbe Ablauf von Hand
nachgefahren:
- AVI und MP4 werden gelesen;
- ein Zeitpunkt hinter dem Videoende fällt weg;
- 320×200 wird bei `max_seite=160` zu 160×100, Skala 0,5, gültiges JPEG.

## Offen

- **V2:** Das Quiz liest die Ergebnisdatei.
- **V3:** Marke „🎬“ im Frontend.
- **V4:** Übergabe.
- Echter Trockenlauf und Schreiblauf (Sebastian, Gesichter-venv).
