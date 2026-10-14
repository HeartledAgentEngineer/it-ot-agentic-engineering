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

- ~~V2~~ erledigt, siehe Nachtrag unten.
- ~~V3~~ erledigt, siehe Nachtrag unten.
- ~~V4~~ erledigt, siehe Nachtrag unten.
- Echter Trockenlauf und Schreiblauf (Sebastian, Gesichter-venv).

## Nachtrag V2: Das Quiz zeigt Video-Gesichter (`backend/app/services/gruppen_quiz.py`)

- **Neue Leser:**
  - `_standbilder_laden` liest die Karte über `_lesepfad`, also am PC unter `personen_gruppen/`
    und am Handy im Basisordner.
  - `_video_zeilen_laden` liest die Video-Zeilen der Gesichtsdatei.
  - Beide werden über `_gemerkt` **getrennt** gemerkt, jeder an seine eigene Datei gebunden.
    Zusammengeführt wird erst beim Aufruf (`_video_teil`). Kommt nur die Karte neu, sieht
    das Quiz sie sofort.
  - Fehlt die Karte oder ist sie unlesbar, ist das Ergebnis `{}`. Das Quiz läuft dann wie
    bisher, bei Lesefehlern mit einer Warnung im Log. Kaputte Zeilen fallen einzeln weg.
- **Gesichterliste** (`gesichter`) und **Personenansicht** (`gesichter_person`):
  - Eine Video-Zeile mit Standbild wird ein Gesicht mit `fileid` = Standbild,
    `bbox × skala`, `breite`/`hoehe` des Standbilds, `gid` = `<standbild>:<index>`,
    `video: true` und `zeit_s`.
  - `videos` zählt jetzt nur noch die Video-Gesichter **ohne** Standbild, also die nicht
    gezeigten. Nicht darstellbare Zeilen (ohne `zeit_s` oder Rahmen) zählen dort mit.
  - Ordnung `zeit`: Video-Gesichter ohne Datum landen hinten, wie bisher.
- **`naechste()`:**
  - Hat eine Gruppe weniger als 8 Foto-Beispiele, wird mit den besten Video-Gesichtern
    aufgefüllt (`anteil × score`, je Standbild höchstens eines).
  - Zwillinge und verbundene Vorschläge ohne Foto-Beispiel bekommen das beste Video-Gesicht
    als Vergleichsbild.
  - Reine Video-Gruppen zeigen damit erstmals Bilder.
- **Einzelaktionen gesperrt:** `ausschliessen`, `ausschliessen_person` und `zuordnen` lehnen
  Video-Gesichter mit einer klaren Meldung ab und schreiben nichts. Die Regeln brauchen eine
  Foto-`bild_id`; die Gruppierung kennt Standbilder nicht.
  - Benennen, „gleiche Person“ und „kenne ich nicht“ wirken weiter auf die ganze Gruppe.
- Entfernt: `_video_gesichter_zaehlen`. Das Zählen übernimmt `_video_teil`.
- **Unverändert** bleiben `gesichter_auf_bild`, `personen_auf_bildern`, `bilder_mit` und
  `personen_gruppieren.py` (dort arbeitet Issue #5).
- **Tests:** neu `backend/tests/test_gruppen_quiz_video.py`, 18 Tests, erfundene Dateien.
  Geprüft werden:
  - ohne Karte, mit Karte, Teilkarte;
  - Karte nachträglich;
  - kaputte Karte;
  - Karte als Ordner;
  - Karte am Handy im Basisordner;
  - Ordnung `zeit`;
  - Beispiele für Video-, Misch- und Fotogruppen;
  - Zwilling nur aus Videos;
  - Sperre der drei Einzelaktionen;
  - Personenansicht;
  - Foto-Aktionen laufen weiter.

  `test_gruppen_quiz.py` bleibt unverändert grün.

## Nachtrag V3: Oberfläche (`frontend/gruppen_quiz.js`, `style.css`)

- **Marke an Video-Kacheln:** neue reine Funktion `gruppenVideoMarke` erzeugt aus `zeit_s`
  die Marke „🎬 0:04“, ab einer Stunde „🎬 1:02:05“. Sie liegt unten rechts auf der Kachel
  (`.gruppen-video-marke`, nur per `textContent`). Der Kacheltitel lautet „Standbild aus
  einem Video · 0:04“.
- **Gesamtansicht:** Video-Gesichter lassen sich nicht markieren, weil das Backend
  Ausschließen und Zuordnen für sie sperrt. Antippen zeigt das ganze Standbild mit
  Gesichtsrahmen. Die Infozeile sagt dazu „🎬 Video-Gesichter nur ansehen, nicht einzeln
  ändern“.
- **Meldungen:**
  - „+ N aus Videos (nicht gezeigt)“ zählt seit V2 nur noch die Gesichter ohne Standbild.
  - Für reine Video-Vorschläge ohne Standbild heißt der Grund jetzt „für sie gibt es noch
    keine Standbilder“.
- **Cache-Kennungen:** `gruppen_quiz.js?v=20261014A`, `style.css?v=20261014A`. Die feste
  Versionsprüfung in `frontend/tests/test_foto_galerie.js` ist mitgezogen.
- **Tests:** 12 neue Prüfungen in `frontend/tests/test_gruppen_quiz.js`. Alle 31
  Frontend-Tests sind über `backend/tests/test_frontend_node.py` grün.
- **Nicht im Browser geprüft:** Das Quiz braucht das Backend mit pCloud-Vorschaubildern, und
  das Backend am PC läuft nicht mit echten Daten. Die Sichtprüfung folgt am Handy nach dem
  Schreiblauf.

## Nachtrag V4: Übergabe ans Handy

- Gebaut ist das schon in V1: `--uebergeben` ruft genau den Kommandozeilen-Einstieg des
  Hochladers auf, `uebergabe_hochladen.main(["--dateien", <ergebnis>, "--schreiben"])`.
  Ohne `--uebergeben` gibt das Werkzeug nur diesen Befehl aus.
- Das Handy übernimmt jede Datei aus `/Agent/uebergabe` beim Start nach `~/foto_sortierung/`
  (`termux/pcloud-uebernehmen.sh`). Dort findet `gruppen_quiz._lesepfad` die Karte im
  Basisordner.
- **Neu:** `backend/tests/test_video_standbilder_uebergabe.py`, 2 Tests, offline:
  1. **Echte Kette:** `video_standbilder.main(--schreiben --uebergeben)` läuft über das echte
     `uebergabe_hochladen` (`planen` → `hochladen_lauf`); nur `httpx` ist eine Attrappe.
     Belegt ist:
     - erst wird der Standbild-Ordner angelegt, dann der Übergabeordner;
     - das Standbild und danach die Ergebnisdatei (Byte für Byte) werden hochgeladen;
     - die Manifestzeile ist gebucht, ohne Token.
  2. **Sandkasten:** `termux/pcloud-uebernehmen.sh` läuft mit dem echten Standardziel
     `$HOME/foto_sortierung` (ohne Umleitung). Die Karte liegt danach dort, und
     `gruppen_quiz._lesepfad` sowie `_video_karte` lesen sie.

## Stand nach V1–V4

- Code und Tests sind fertig.
- **Offen:**
  1. Echter Trockenlauf am PC (Gesichter-venv, nur Zählung):
     `~/foto_sortierung/venv_gesicht/Scripts/python.exe tools/foto_sortierung/video_standbilder.py --groessen`
  2. Schreiblauf mit `--schreiben --uebergeben`.
  3. App-Start am Handy und Sichtprüfung im Quiz.
