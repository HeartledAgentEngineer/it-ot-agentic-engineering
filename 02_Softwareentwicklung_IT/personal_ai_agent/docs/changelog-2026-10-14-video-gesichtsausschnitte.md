# Video-Gesichtsausschnitte im Quiz — Abschnitt 3 belegt beantwortet (14.10.2026)

Anlass: `.hermes/plans/2026-10-10_personen-orte-erzaehlungen.md`, **Abschnitt 3**
(„Gesichtsausschnitte aus VIDEOS sehen"). Dort steht als Vermutung: „Videos sind bisher nur
über `video_vektoren_*.jsonl` erfasst — **offenbar ohne** Gesichtsausschnitte für das Quiz."
Gefordert war zuerst Klärung, dann Bau („Video → Frames ziehen → Gesichter →
Ausschnittbilder erzeugen und dem Quiz zuführen").

**Dieser Lauf hat nur gemessen und gelesen — nichts geändert, kein Bild geöffnet, kein Bild
gesendet, kein Vision-Aufruf, keine Geräteeingriffe.** Alle Zahlen sind an den echten Dateien
auf dem PC gezählt. Personen-Namen kommen nicht vor (nur Zählungen); Bildinhalte ebenso wenig.

## 1. Die Video-Gesichter sind in den Gruppen — vollständig

Gemessen an `~/foto_sortierung/personen_gruppen/gesicht_zuordnung.jsonl` (50.282 Zeilen,
0 kaputte):

| Zahl | Wert |
|---|---|
| Zuordnungszeilen mit `video_id` | **16.966** (= 33,7 % aller Zuordnungen) |
| Zuordnungszeilen aus Fotos | 33.316 |
| verschiedene Videos darin | **971** |
| Gruppen gesamt | 1.368 |
| Gruppen **nur** aus Video-Gesichtern | **359** (darin 2.468 Gesichter) |
| Gruppen gemischt (Foto + Video) | 391 (darin 14.498 Video-Gesichter) |
| Gruppen nur aus Fotos | 618 |

Die **359 reinen Video-Gruppen sind alle unbenannt (0 von 359)** — also genau die Gruppen, die
ein Mensch am Handy ansehen und benennen müsste. Größe: kleinstes 3, Median 4, größtes 113
Gesichter; **103 Gruppen haben höchstens 3 Gesichter**. Die 359 Gruppen stammen aus **363
verschiedenen Videos** (Videos werden von mehreren Gruppen geteilt).

## 2. Was eine Video-Zeile trägt — und was fehlt

Gemessen an einer echten Zeile (Werte gerundet, keine Inhalte):

`anteil 0.003333 · bbox [1468,1 | 404,8 | 77,2 | 89,5] · breite 1920.0 · hoehe 1080.0 ·
index 0 · score 0.8808 · video_id 53634205041 · zeit_s 4.0 · bild_id 53634205041#t=4.0 ·
aufnahme (leer)`

- **Vorhanden:** Video-Kennung, **Zeitpunkt im Video** (`zeit_s`), Gesichtsrahmen **im
  Frame-Koordinatensystem**, Framemaße (`breite`/`hoehe`, gemessen u. a. 1920×1080 in 7.324
  Zeilen, 1080×1920 in 4.303, kleinere Auflösungen in den übrigen), Erkennungssicherheit.
- **`bild_id` ist kein Datei-Kennwert**, sondern eine Frame-Kennzeichnung
  `"<fileid>#t=<sekunden>"` (`tools/foto_sortierung/video_gesichter.py:263–265`,
  `frame_kennung`).
- **`aufnahme` ist in 0 von 16.966 Video-Zeilen gefüllt.** In der Zeitansicht
  (`ordnung=zeit`) landen sie deshalb hinten (Ersatzwert `9999`).
- Der **Frame selbst existiert nirgends als Bild:** `video_gesichter.py:38` sagt ausdrücklich
  „Keine Bilder speichern"; die Frames sind in-memory-JPEG-Bytes (`frames_entnehmen`,
  `:215–240`).

## 3. Warum das Quiz sie nicht zeigt — und es ehrlich sagt

- **Backend filtert sie weg:** `backend/app/services/gruppen_quiz.py:642` (`_gesichter_laden`)
  und `:690` (`_gesichter_je_bild_laden`) überspringen jede Zeile mit `video_id`
  („nur Fotos"). `gesichter()` liefert stattdessen die **Zahl** `videos`.
- **Frontend sagt es an:** `frontend/gruppen_quiz.js:104` zeigt „N Videos" an der Gruppenkarte,
  `:160–170` „Dieser Vorschlag besteht nur aus N Videos (nicht gezeigt)" bzw.
  „+ N aus Videos (nicht gezeigt)". Das ist genau der Befund vom 10.10. (89 Vorschläge, die
  nur aus Video-Standbildern bestanden) — inzwischen sauber erklärt statt leer.
- **Es ist nicht nur eine Anzeigelücke:** die Kachel lädt ihr Bild über
  `/api/cloud/thumb?fileid=<Kennung>` (`gruppen_quiz.js:371`, Kennungswahl `:48–53`). Bei einer
  Video-Zeile wäre die Kennung `… #t=…` und damit kein gültiger Datei-Kennwert.
- **Auch das Backend kann kein Video-Standbild schneiden:** 0 Treffer für `ffmpeg` oder
  `zeit_s` in `backend/app/**`. Der PC hat dagegen alles dafür —
  `tools/foto_sortierung/gesicht_erkennen.py` `AUSSCHNITT_RAND = 0.45` (`:156`),
  `ausschnitt_rechnen` (`:886`), `_ausschnitt_bytes` (`:929`, in-memory),
  `kachel_quelle(..., ausschnitt=True)` (`:21–30`) — und `cv2` im Videowerkzeug.

## 4. Der billige Scheinweg ist gemessen und reicht nicht

pCloud liefert über `getthumbs` auch für ein **Video**-Kennwert ein Standbild (gemessen über
den Dienst des Projekts, `PCloudService.thumb`, 120×120: **JPEG, 3.860 Bytes**; Gegenprobe Foto:
JPEG, 6.967 Bytes — beides HTTP 200, keine Fehlermeldung). Das ist aber das Standbild des
Videos, **nicht der erkannte Frame**.

Wie wenig das trägt, ist an den 2.468 Gesichtern der reinen Video-Gruppen gemessen:

| Zeitpunkt im Video | Gesichter | Anteil |
|---|---|---|
| ≤ 0,5 s | 90 | 3,6 % |
| ≤ 1,0 s | 90 | 3,6 % |
| ≤ 3,0 s | 197 | 8,0 % |
| ≤ 10,0 s | 575 | 23,3 % |
| größter gemessener Zeitpunkt | 936,6 s | — |

Selbst wenn das Standbild den ersten Moment zeigt, wäre nur rund **jedes zwanzigste** Gesicht
zu sehen. Der Weg „Standbild statt Frame" ist damit widerlegt.

## 5. Was ein echter Nachbau kostet (gerechnet, nicht geschätzt)

Einen Frame wiederherstellen heißt: **das Video erneut laden**, an die Stelle springen,
Rahmen schneiden (in-memory, nichts speichern).

- Größen der betroffenen Videos: aus `sortierplan_bildervideos.json` für **484 von 971**
  bekannt; größtes **2,4 GB**, 18 über 300 MB, 113 über 100 MB. Die übrigen 487 gehören zur
  Upload-Sammlung und stehen nicht in dieser Plan-Datei — **die genaue Downloadsume ist ehrlich
  nicht belegt** (die Bytes der Plan-Datei sind teils 0).
- Billigster Weg für den Zweck: nur die **359 reinen Video-Gruppen** brauchen Anschauung, und
  je Gruppe wenige Gesichter. Über die **363 betroffenen Videos** entdoppelt wird jedes Video
  **einmal** geladen — statt 16.966-mal.
- Kachelseiten wie beim Bestand (Gesichtsausschnitt 200×200 px, Rand 0,45 × Rahmen; gemessene
  Seite: 54 Kacheln, rund 55–100 KB je Seite) wären für 16.966 Gesichter grob 314 Seiten und
  rund 25 MB — das ist der kleine Teil der Rechnung.

## 6. Ergebnis und Entscheidung

**Beantwortet:** Ja, die Video-Gesichter sind erkannt, gezählt und in den Gruppen — seit dem
13.10. Auch die Zuordnung selbst (welches Gesicht in welcher Gruppe) steht. Was fehlt, ist
**allein das Anschauen**; die Daten dafür (Video-Kennung, Zeitpunkt, Rahmen, Framemaß) sind
vollständig vorhanden.

**Offen und Sebastians Entscheidung** (nichts davon gebaut):

1. **Weg A — PC baut Kachelseiten** aus den Frames und übergibt sie wie die anderen Dateien
   (kabellos über `/Agent`). Er sieht dann am Handy Ausschnitte auch aus Videos. Preis: lokale
   Rechenzeit + erneutes Laden der 363 Videos; kein Vision-Aufruf, keine Modellkosten.
2. **Weg B — Backend kann einen einzelnen Frame auf Zuruf** (Kennung + Zeitpunkt) — braucht
   `ffmpeg` bzw. `cv2` im Backend und einen Netzweg zum Video; der Speicher am Handy ist dafür
   der schwächste Teil.
3. Die 359 unbenannten Video-Gruppen sind der erste sinnvolle Anlass für Weg A — kleine Gruppen,
   Median 4 Gesichter, alle bisher unsichtbar.

Das **Prüfkriterium des Plans** („Im Quiz erscheinen Gesichtsausschnitte aus Videos") ist damit
ein Bau-Schritt, kein Diagnose-Schritt: er gehört in den Plan/Umsetzungsweg (Master + Prüfung),
nicht in den Nachtlauf.
