# 15.10.2026 – Video-Gesichter im Quiz: „nicht gezeigt“ belegt und geradegezogen

Anlass: Sebastians Screenshot vom 15.10.2026 (Ansicht „Alle Gesichter“):
`136 Gesichter · 48 geladen · + 42 aus Videos (nicht gezeigt)`. Die Video-Gesichter
werden gezählt, aber nicht angezeigt – er kann sie deshalb nicht ansehen.

## Befund (gemessen an den echten Dateien am PC, nur lesend)

1. **Die Zahl stammt aus dem Quiz selbst und ist korrekt gezählt.**
   `gruppen_quiz._video_gesichter` (`backend/app/services/gruppen_quiz.py:768-783`)
   macht aus einer Video-Zeile nur dann ein sichtbares Gesicht, wenn ihr Frame
   einen Eintrag in der Standbild-Karte `video_standbilder.jsonl` hat; sonst
   zählt sie als „ohne Standbild“. `gesichter()` (`:891-913`) gibt diesen Zähler
   als `videos` zurück – die Oberfläche schreibt ihn seit V3 als
   „+ N aus Videos (nicht gezeigt)“ (`frontend/gruppen_quiz.js:180`).
   Die Video-Gesichter **mit** Standbild erscheinen als normale Kacheln (Marke
   „🎬“) – an der Anzeige selbst ist nichts kaputt.

2. **Die Gruppe des Screenshots ist eindeutig bestimmbar.** Auf den echten
   Daten passt genau **eine** Gruppe auf „136 gesamt / 42 ohne Standbild“:
   `Person_1159` = 109 Fotos + 69 Video-Gesichter; davon 27 mit Standbild (werden
   angezeigt) und 42 ohne (nur gezählt). Eine Gruppe mit 136 Fotos und 42 Video-
   Gesichtern (das wäre der Fall „Handy ohne Karte“) gibt es nicht – das Handy
   liest die Karte also richtig; die Übergabe der Karte funktioniert.

3. **Ursache: Der Lauf vom 14.10.2026 hat die gemischten Gruppen nie erfasst.**
   Der Schreiblauf lief im Standard-Umfang `--umfang nur_video`
   (`tools/foto_sortierung/video_standbilder.py:417`); `auswaehlen()`
   überspringt dabei jede Gruppe, die auch Foto-Gesichter hat (`:148-150`).
   Gemessen: **alle 1133 Karten-Zeilen liegen in der `nur_video`-Auswahl,
   keine außerhalb**; für `Person_1159` (gemischte Gruppe) wurden nie eigene
   Frames gewählt – ihre 27 Treffer sind Zufallstreffer, weil ein Frame
   gleichzeitig zu einer Video-only-Gruppe gehört. Zusätzlich deckt selbst
   `--umfang alle` nur die besten 8 Gesichter je Gruppe ab
   (`STANDARD_MAX_JE_GRUPPE`, `:63`, angewendet in `auswaehlen`, `:154`) –
   für eine Gruppe mit 69 Video-Gesichtern blieben also auch dann Lücken.

4. **Mengen (Trockenlauf mit dem echten Werkzeug, 15.10.2026, kein Netz):**
   - Standard `nur_video`: 359 Gruppen · 1787 Gesichter · 348 Videos;
     schon erledigt 1133; offen: 15 Videos, 95 Standbilder.
   - `--umfang alle`: 749 Gruppen · 3620 Gesichter · 645 Videos;
     offen: 493 Videos, 1130 Standbilder.
   - Volle Abdeckung (`--umfang alle --max-je-gruppe 0`): 749 Gruppen ·
     **8120 Gesichter · 823 Videos**; offen: **748 Videos, 2828 Standbilder**.
   Von 749 Gruppen haben 496 noch Lücken (größte: 432, 193, 164, 142, 142).

## Änderungen

- **`tools/foto_sortierung/video_standbilder.py`:** `--max-je-gruppe 0` (oder
  kleiner) bedeutet jetzt **alle** Gesichter der Gruppe; der Standard bleibt 8.
  Ohne diese Möglichkeit war die volle Abdeckung nur über einen willkürlichen
  großen Wert erreichbar. Test:
  `test_null_je_gruppe_nimmt_alle_frames_der_gruppe` (`backend/tests/test_video_standbilder.py`).
- **`frontend/gruppen_quiz.js`:** Die Zeile sagt jetzt den Grund –
  „+ 42 aus Videos **(noch ohne Standbild)**“ statt „(nicht gezeigt)“.
  Cache-Kennung `gruppen_quiz.js?v=20261015A` (`frontend/index.html`).
  Frontend-Test in `frontend/tests/test_gruppen_quiz.js` mitgezogen.
- **`backend/app/services/gruppen_quiz.py`:** Docstring von `gesichter()`
  berichtigt (`videos` = Video-Gesichter **ohne** Standbild, die die Ansicht
  nicht zeigen kann).
- **Enthalten außerdem:** die dokumentierte Fortschritts-/Begrenzungsänderung
  des Werkzeugs aus dem 15.10.-Stand (`fortschritt_zeile`, `melden`; Nachtrag
  „Fortschritt und Begrenzung sichtbar“ in
  `docs/changelog-2026-10-14-video-standbilder.md`). Sie lag uncommittet im
  Arbeitsbaum und wird mit diesem Commit unverändert übernommen.

## Was das Handy danach zeigt

Nach dem Nachhol-Lauf erscheint **jedes** Video-Gesicht als Kachel (Marke „🎬“,
antippen zeigt das Standbild mit Gesichtsrahmen); die Zeile „+ N aus Videos“
verschwindet, weil der Zähler dann 0 ist. Die Kacheln lädt das Handy live aus
pCloud (`/api/cloud/thumb?fileid=…`); übergeben werden muss nur die Karte
`video_standbilder.jsonl` – das erledigt `--uebergeben` (pCloud-Ordner
`/Agent/uebergabe`, das Handy übernimmt beim App-Start,
`termux/pcloud-uebernehmen.sh`).

## Was noch offen ist (Sebastian, PC)

Der Nachhol-Lauf ist ein großer Lauf (748 Videos). Empfohlener Befehl im
Projektordner (Gesichter-venv, wie beim Lauf am 14.10.):

```
~/foto_sortierung/venv_gesicht/Scripts/python.exe tools/foto_sortierung/video_standbilder.py \
    --umfang alle --max-je-gruppe 0 --schreiben --uebergeben
```

- Abbruch jederzeit möglich – der nächste Lauf macht weiter (idempotent,
  Ergebniszeile je Standbild mit fsync). In Scheiben mit `--max-videos N`.
- Danach am Handy die App starten (übernimmt die Karte) und im Quiz nachsehen.
- Bis dahin erklärt die Zeile den Rest ehrlich: „noch ohne Standbild“.

## Belege des Schritts

- Messungen: eigene Wegwerf-Skripte im Tempordner gegen
  `~/foto_sortierung/personen_gruppen/gesicht_zuordnung.jsonl` (8120 Video-
  Gesichter, 3961 eindeutige Frames, 823 Videos) und `video_standbilder.jsonl`
  (1133 gültige Zeilen, 0 unbrauchbar); Trockenläufe des Werkzeugs (kein Netz).
- Prüfbefehl vor der Änderung (eigener Lauf): `4589 passed, 3 skipped, Exit 0`.
  Der Commit lässt den geänderten Stand über das Tor prüfen
  (`tools/gate/tor.py`, Befehl `python -m pytest tests/ -q`).

Rolle: Auftrag und Befund vom Thinker (Hermes-Master, Screenshot 15.10.2026);
Umsetzung durch Hermes-Ausführer (Subagent) mit Messbelegen oben.
