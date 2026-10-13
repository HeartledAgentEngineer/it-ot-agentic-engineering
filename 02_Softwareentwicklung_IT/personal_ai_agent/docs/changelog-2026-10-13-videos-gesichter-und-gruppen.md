# 13.10.2026 — Die 25 Videos sind durch, und 5.060 nie angedockte Videogesichter stehen jetzt in den Gruppen

Drei Dinge in einem Zug: erstens ist die Lücke „25 Videos ohne Gesichter-Lauf"
geschlossen (ihre Ursache war eine Werkzeug-Voreinstellung, kein fehlendes
Material), zweitens sind **5.060 Videogesichter** in die Personengruppen
angedockt worden, die vorher in der Vektordatei lagen, aber nie eine Zuordnung
bekommen hatten, drittens ist der neue Gruppenstand kabellos ans Handy gegeben
und unabhängig nachgerechnet worden.

## 1. Der Fund — alle 25 offenen Videos lagen über der Voreinstellung des Werkzeugs

**Anlass.** Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) führte seit
dem 10.10. eine Lücke „sortierplan_bildervideos.json: 25 Videos ohne
Gesichter-Lauf" — eine Zahl ohne Grund.

**Gemessen (nur lesend).** Plan `sortierplan_bildervideos.json`: **859 Videos**,
davon **834 unter 300 MB** (alle fertig) und **25 über 300 MB** (alle offen).
Die Voreinstellung von `video_gesichter.py` ist `STANDARD_MAX_MB = 300` — die 25
wurden also **nicht vergessen, sondern als `zu_gross` verworfen**. Das ist
dieselbe Fehlerfamilie wie die 8-MB-Kachelgrenze bei den Fotos (10.10.): eine
Voreinstellung lässt eine ganze Gruppe still zurück, und die Prüfzeile nennt nur
die Zahl. Größen der 25: kleinste **305,3 MB**, größte **2.406,6 MB**, zusammen
**15,16 GiB**. Der Median aller 859 Videos liegt bei 45,9 MB — die 300 MB sind
damit eine sinnvolle Grenze, die Ausnahme sind genau diese 25.

**Stichprobe vor dem Massenlauf** (Regel „teure Wege vorher messen"): ein Video
mit `--max-mb 4096` → 8,8 s, 5 Frames entnommen, 5 mit Gesicht. Also fahrbar,
kostenfrei (das Gesichtsmodell YuNet + SFace läuft lokal; das Werkzeug hat
**keinen** Netz-Import außer pCloud-Lesen, kein Vision-Aufruf, kein fremdes
Modell).

**Sicherung als Kopie (nie löschen), dann der Lauf:**

| Datei | Sicherung | Größe |
|---|---|---|
| `video_vektoren_bildervideos.jsonl` | `.vorher_videos25-20261013` | 82.136.773 B, md5 `c0dd5a8f9842…` |
| `video_vektoren_bildervideos.jsonl.videos_fertig` | `.vorher_videos25-20261013` | 10.829 B |

Aufruf (wiederaufnahmefähig, `--fortsetzen`):

```
venv_gesicht/Scripts/python.exe tools/foto_sortierung/video_gesichter.py \
    --plan C:/Users/sebas/foto_sortierung/sortierplan_bildervideos.json \
    --vektoren C:/Users/sebas/foto_sortierung/video_vektoren_bildervideos.jsonl \
    --schreiben --fortsetzen --max-videos 30 --max-mb 4096
```

**Ergebnis (die eigene Schlusszeile des Laufs):** „Videos gesamt: 25   geholt: 25
zu_gross: 0   Fehler: 0", **1.481 Frames**, davon **946 mit Gesicht**,
**946 Vektorzeilen geschrieben**, Laufzeit 4.402,8 s (rund 73 min).
Vektorzeilen der Datei: 7.734 → **8.680**; Fortschrittsdatei 833 → 858 Zeilen
(834 bereits fertige plus 25 neue minus die eine, die schon vorher über eine
Vektorzeile als fertig galt).

**Beleg aus dem Nachweis (frisch, Exit 0):** „sortierplan_bildervideos.json …
**Gesichter Videos: 859 von 859 (100,0 %)**". Der zweite Aufruf wäre 0 zu tun
(`--fortsetzen` liest Fortschrittsdatei **und** Vektorzeilen).

## 2. Der zweite Fund — 5.060 Videogesichter lagen in der Vektordatei, aber nie in einer Gruppe

Beim Anschluss-Schritt (Videogesichter andocken, `personen_gruppieren.py
--nachtragen`, Trockenlauf) kam heraus:

* **5.060 neue Gesichter** (davon 4.599 schon vorhanden und übersprungen),
* **1.854 andockbar** an 201 bestehende Gruppen,
* **153 neue Gruppen** (Kennungen `Person_1529…Person_1681`),
* 2.468 als Rauschen (nicht angedockt).

Von den 5.060 stammen nur **946 aus dem heutigen Video-Lauf** — die übrigen
rund **4.114 Videogesichter lagen schon vorher in der Vektordatei, ohne je
angedockt worden zu sein.** Die Stufe „Gesichter Videos 834 von 834 (100,0 %)"
war also vollständig, ihre Gesichter erreichten den Personenkatalog aber nicht:
genau die Familie „gebaute Stufe ohne Verbraucher".

**Geschrieben** (Sicherung vorher als Kopie:
`personen_gruppen/gesicht_zuordnung.jsonl.vorher_videos25-20261013`, 8.741.862 B,
dazu `personen_beispiele.json.vorher_videos25-20261013`).
**Idempotenz belegt:** zweiter Aufruf = „Neue Gesichter: 0 (schon vorhanden,
übersprungen: 9.659), Andgedockt: 0, Neue Gruppen: 0, Rauschen: 0".

**Beleg aus dem Nachweis (Exit 0):** Gruppen **1.017 → 1.170** (Stand
2026-10-13T14:18:43), Gesichter in Gruppen **23.932 → 26.524**, Zuordnung
**36.566 → 41.626** Gesichter (65,4 % → 63,7 % — der Anteil sinkt, weil die
neuen Videogesichter zum Teil Einzelgesichter bleiben; das ist ehrlich so und
kein Rückschritt).

## 3. Der neue Gruppenstand ist am Handy bereitgestellt — mit unabhängiger Gegenprobe

Der Nachweis hatte es selbst gemeldet (neue Zeile, die genau dafür gebaut wurde):
„Seit der letzten Uebergabe geaendert (2) — das Geraet holt beim naechsten Start
die alte Fassung: gesicht_zuordnung.jsonl, personen_beispiele.json".

**Trockenlauf** über die acht Dateien der Übergabeliste: 6 × „übersprungen
(Prüfsumme gleich)", 2 × „würde hochgeladen" — genau die zwei geänderten. Dann
`--schreiben` (Weg = Sebastians Freigabe vom 10.10., Ziel nur unter `/Agent/`,
kein Löschen):

| Datei | Größe | sha256 | fileid |
|---|---|---|---|
| `gesicht_zuordnung.jsonl` | 9.943.224 B | `eb43c237f109…` | 108912351235 |
| `personen_beispiele.json` | 1.655.983 B | `227e3479e451…` | 108912352107 |

Je Datei eine Manifest-Zeile (`~/foto_sortierung/uebergabe_manifest.jsonl`,
außerhalb des Repos; jetzt 13 Buchungen, 8 verschiedene Dateien).

**Unabhängige Gegenprobe (nicht die Erfolgsmeldung des Werkzeugs):** beide
Dateien über `getfilelink` frisch aus pCloud geladen und örtlich nachgerechnet —
`gesicht_zuordnung.jsonl` 9.943.224 B sha256 `eb43c237f109e731…` und
`personen_beispiele.json` 1.655.983 B sha256 `227e3479e4514476…`, **beide
byte-gleich** zur lokalen Datei. Nachweis danach: „Uebergabe (Handy):
13 Buchungen, 8 verschiedene Dateien (gleich 8, geaendert 0, am PC fehlt 0)".

## Stand und ehrliche Grenzen

* **Lücken im Nachweis: 5 → 4.** Die Video-Lücke ist geschlossen, die
  Übergabe-Lücke ist während des Laufs aufgetreten und mit dem Upload wieder
  weg. Es bleiben: 3 + 5 + 8 Fotos ohne Beschreibung (dieselben 6 verschiedenen
  Bilder), 2 Kennungen ohne Gruppe.
* **Was NICHT geändert wurde:** die Voreinstellung `STANDARD_MAX_MB = 300`
  bleibt. 834 von 859 Videos liegen darunter; die Grenze ist damit richtig
  gewählt, und das Werkzeug nennt `zu_gross` samt Nachholweg. Ob sie steigen
  soll, ist eine Entscheidung, keine Nachtarbeit.
* **Kein Bild an ein fremdes Modell.** Gesichter entstehen lokal (YuNet +
  SFace); der Lauf holt nur Videos aus pCloud. Keine Vision, keine Kosten,
  keine Geräteeingriffe (`adb devices` war leer), nichts gelöscht — die
  einzigen Löschungen sind die vom Werkzeug selbst angelegten Temp-Dateien je
  Video (`finally`, dokumentiert im Modulkopf).
* **Grenze der Videogesichter:** Frames im Abstand von 2 s, höchstens 60 je
  Video (`--abstand-s`/`--max-frames`) — wer zwischen zwei Frames zu sehen ist,
  wird nicht erfasst. `metadaten` (GPS, Aufnahmezeit) bleiben bei Videos
  bewusst `None` (im Container, mit `cv2` nicht lesbar; `ffprobe` wird nicht
  vorausgesetzt).
* **Die Lücken-Zeile für Videos nennt weiter keinen Grund** — die Prüfzeile
  dafür gehört in `bestand_pruefen.py`, und diese Datei liegt gerade **fremd
  und halbfertig im Arbeitsbaum** (Arbeit des Master-Chats zur ausgelieferten
  Frontend-Dateiliste). Deshalb **nicht angefasst**: `git commit --only` würde
  den fremden Stand mitveröffentlichen.
* **Nicht angefasst:** `personen_vektoren_papa.jsonl`, `orte.jsonl`,
  `bild_orte.csv`, `bild_index.db` (unverändert), die 4 Dateien „übergeben, aber
  von keinem Dienst gelesen" (Sebastians Entscheidung), die Zwillings-Cluster
  (nur Sichtung, nie automatisch zusammenlegen).

Werkzeuge in diesem Lauf: `tools/foto_sortierung/video_gesichter.py`,
`tools/foto_sortierung/personen_gruppieren.py --nachtragen`,
`tools/pcloud/uebergabe_hochladen.py`, `tools/foto_sortierung/bestand_pruefen.py`
(alle nur benutzt, **keine** Zeile im Baum geändert — dies ist ein Daten- und
Dokulauf).
