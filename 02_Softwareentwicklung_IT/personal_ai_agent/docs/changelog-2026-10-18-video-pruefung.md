# Video-Prüfung: Standbilder, Wiederholungen, Brauchbarkeit (To-do Punkt 5)

**Datum:** 18.10.2026 · **Schritt:** To-do Punkt 5 „Video-Prüfung" (Sebastian, 16.10.2026) ·
**Betroffen:** neues Werkzeug `tools/foto_sortierung/video_pruefung.py`, neuer Test
`backend/tests/test_video_pruefung.py` · **Kosten:** 0 USD (nur lesend; die Helligkeitsprobe holt
30 Bilder von pCloud, kein Modellaufruf)

## Auftrag (Sebastians Worte)

„Inwiefern die Videos alle jetzt Bilder haben und wie oft die gleichen Personen erkannt wurden"
— dazu: Sind die Standbilder brauchbar (nicht schwarz, nicht doppelt)?
**Prüfkriterium des Plans:** eine Auswertung mit Zahlen als Beleg, keine Schätzung.

## Ausgangslage (gemessen, bevor gebaut wurde)

Es gab **kein** Werkzeug, das diese drei Fragen beantwortet. Die Zahlen liegen in drei Dateien,
die **nicht** deckungsgleich sind — genau darin lag die Falle:

| Quelle | Inhalt |
|---|---|
| `sortierplan_bildervideos.json` | 11.630 Züge, davon **859** mit `art: "video"` |
| `personen_gruppen/video_standbilder.jsonl` | **3.570** Standbild-Zeilen zu **746** Video-Kennungen |
| `personen_gruppen/gesicht_zuordnung.jsonl` | 50.282 Gesichtszeilen, davon **16.966** aus Videos (971 Video-Kennungen) |

Wer nur eine dieser Mengen „die Videos" nennt, schätzt. Das Werkzeug nennt deshalb **alle drei**
und ihre Schnitte.

## Die Zahlen (in diesem Lauf selbst gemessen)

```
Plan-Videos:                     859
davon mit Standbild:             398
davon ohne Standbild:            461
Videos mit erkannten Gesichtern: 971
davon mit Standbild:             746
davon ohne Standbild:            225
Gesichter in Videos:             16966
davon mit Personen-Kennung:      8120
Standbilder:                     3570 (verschiedene Kennungen: 3570, doppelt: 0)
Standbilder je Video:            1 bis 58
Standbilder ohne Mass:           0
Videos mit Wiederholung:         362 von 971
Personen mehrfach (Summe):       1091
hoechste Wiederholung:           57 Bildstellen
Doppelerkennung je Bildstelle:   0
```

### 1. Haben alle Videos Standbilder? — Nein, und zwar absichtlich

- Von den **971** Videos mit erkannten Gesichtern haben **746** ein Standbild, **225 nicht**.
- **Der Grund ist gemessen, nicht vermutet:** der Erzeuger `video_standbilder.py` wählt je Gruppe
  **höchstens 8 Gesichter** aus (`STANDARD_MAX_JE_GRUPPE = 8`, `auswaehlen()`) und nur Videos ohne
  gleichwertiges Foto. Sein eigener Trockenlauf sagt heute:
  `Gruppen: 359 · Gesichter gewaehlt: 1787 · Videos: 348 · schon erledigt: 3570` →
  `Offen: 12 Videos, 92 Standbilder`. Die Standbilder decken also eine **Auswahl** ab, nicht den
  ganzen Videobestand. Die 225 fehlen nicht durch einen Fehler, sondern weil sie außerhalb dieser
  Auswahl liegen.
- Die **Liste** dieser 225 Kennungen liegt als `~/foto_sortierung/video_ohne_standbild.txt`
  (eine Kennung je Zeile, 225 Zeilen) — für den Fall, dass Sebastian sie vollständig haben will.

### 2. Wie oft wurde dieselbe Person in einem Video erkannt?

- **362 von 971** Videos zeigen mindestens eine Person auf **mehr als einer** Bildstelle;
  zusammen sind das **1.091** solche Personen-Videos.
- Verteilung (Wiederholungen je Video → Videos):
  `0:609 · 1:164 · 2:71 · 3:37 · 4:21 · 5:26 · 6:9 · 7:9 · 8:5 · 9:6 · 10:4 · 11–16:9 · 22/26/29/49:je 1`
- **Höchstwert:** eine Person auf **57** Bildstellen (ein längeres Video), **121** Videos haben
  mehr als 10 Personen. 257 Videos haben nur **eine** Bildstelle mit Gesicht — dort gibt es
  folgerichtig keine Wiederholung.
- **Doppelerkennung im selben Einzelbild: 0.** Dieselbe Person wurde auf keinem Frame zweimal
  gefunden — das ist die saubere Seite des Befunds.
- Ehrliche Grenze: „Wiederholung" heißt **von der Erkennung auf mehreren Frames gesehen**, nicht
  „dieselbe Person mehrfach aufgetreten". Ob eine Person im Video mehrfach vorkommt, sagt diese
  Zahl nicht.

### 3. Sind die Standbilder brauchbar?

- **Doppelt: nein.** 3.570 Standbilder tragen **3.570 verschiedene** Kennungen — kein Standbild ist
  zweimal vergeben; auch auf Bildpunktebene war in der Probe **kein** Bild doppelt (gleicher
  SHA-256: 0).
- **Masse vollständig:** 0 Standbilder ohne Breite/Höhe; die Kantenlängen reichen von 192 bis 1600 px
  (häufigste 1600: 1.048, 900: 768, 480: 360, 640: 309), Skalen 1,0 (1.758) und 0,833 (1.806).
- **Schwarz/leer: nein — an einer Stichprobe von 30 Bildern gemessen** (frisch von pCloud geholt,
  nur im Speicher, **kein** Bild gespeichert und **kein** Modellaufruf):
  `30 geprüft, 0 dunkel (< 12 von 255), 0 gleich aussehend, 0 nicht lesbar`;
  Helligkeit im Mittel **86,1** von 255 (dunkelster 19,1 / hellster 144,2).
  Ehrliche Grenze: das ist eine **Stichprobe von 30 der 3.570** — nicht alle Bilder wurden gemessen.

## Jetzt (was gebaut wurde)

Neues Werkzeug **`tools/foto_sortierung/video_pruefung.py`**, nur lesend, nur Zahlen:

- Trockenlauf ist Standard (zählt und druckt); `--schreiben` legt den Bericht als JSON
  (`~/foto_sortierung/video_pruefung.json`), `--liste` schreibt die Kennungen ohne Standbild.
  Beides idempotent (Neuschreibung), im Repo passiert nichts.
- **Kein Netzzugriff ohne ausdrücklichen Schalter:** die Helligkeitsprüfung läuft nur mit
  `--standbild-probe N` (Vorgabe 0). Der Bildleser ist **injizierbar** (im Betrieb pCloud, im Test
  eine Attrappe).
- **Keine Namen:** ausgegeben werden Kennungen und Zahlen, nie Datei- oder Personennamen.
- Ehrliche Meldungen statt Ausnahmen: fehlende/kaputte Dateien und unlesbare Zeilen werden gezählt,
  nicht verschluckt; ein Lesefehler bei der Probe steht als `nicht_lesbar` im Bericht.

## Belege (in diesem Lauf selbst ausgeführt)

- Neu `backend/tests/test_video_pruefung.py` — **17 passed**: Plan liest nur `art: "video"`,
  fehlende Datei ist leer statt Ausnahme, kaputte Zeilen werden übersprungen, nur Video-Gesichter
  zählen, Wiederholung über mehrere Bildstellen, dieselbe Person zweimal **auf einer** Bildstelle,
  leere Zuordnung, doppelte Standbild-Kennungen, Standbild ohne Mass, Helligkeit schwarz/weiß,
  kaputte Bytes → `None`, Probe zählt dunkel und hält die Grenze ein, Lesefehler wird ehrlich
  gemeldet, `--standbild-probe 0` prüft nichts, die drei Mengen werden getrennt, der Bericht nennt
  Zahlen und keine Namen, der Trockenlauf schreibt nichts.
- Lauf am echten Bestand (nur lesend) mit den Zahlen oben; Probe über 30 Bilder von pCloud.
- Der **Gegenprobe-Nachweis** ist hier die Zahlengleichheit: dieselben Zahlen kamen aus dem
  Werkzeug und aus einer unabhängigen Handzählung über die drei Dateien.

## Grenzen (ehrlich)

- Die Helligkeitsaussage stützt sich auf **30** der 3.570 Standbilder; „nicht schwarz" ist damit
  belegt für die Stichprobe, nicht für alle Bilder. Ein voller Lauf wäre möglich
  (`--standbild-probe 3570`), kostet aber einen längeren pCloud-Lesevorgang — bewusst nicht
  gestartet.
- Die 225 Videos **ohne** Standbild können mit `video_standbilder.py --max-je-gruppe 0`
  (alle Gesichter) erzeugt werden; das **lädt Videos und schreibt Bilder in pCloud** und ist
  deshalb nicht Teil dieses Schritts.
- Ob ein Standbild das **richtige** Gesicht zeigt, sagt die Geometrie nicht — dafür braucht es
  Sebastians Blick am Gerät.
- Kein fremder Pfad angefasst, kein `git add -A`, nichts gelöscht, `status.json` nicht angefasst,
  keine Geräteeingriffe, keine `.env`, kein Bild an ein Modell. **Kosten 0 USD.**
