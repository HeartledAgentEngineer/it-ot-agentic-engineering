# Themen-Stufe: Kontaktbögen je Anlass (Vorschaubilder in Stapeln)

> **Datum:** 27.09.2026 · **Auftrag:** Sebastian (Nachtlauf N4): „alle Fotos und
> Videos der pCloud nach Jahr/Thema sortieren" — Voraussetzung: der Agent kann
> die Bilder **sehen**, ohne 45 GB herunterzuladen. Deshalb Vorschaubilder in
> Stapeln und **Kontaktbögen** (Kacheln mit Nummern) je Tag/Anlass.
> Rahmen: `docs/plan-foto-personen-und-erinnerungen.md` (Stufe 2),
> Ablauf: `docs/plan-nachtlauf-2026-09-26.md` (N4).

## Warum es diesen Schritt gibt

Der Sortierschlüssel (Stufe 1) weiß, **was** da ist (9.430 Dateien, 8.302 mit
Datum), aber nicht, **was darauf zu sehen ist**. Der Vision-Blick auf jedes
Einzelbild wäre teuer und langsam; auf das Original ist er gar nicht nötig —
pClouds Vorschaubilder (120×120, ~4–6 KB statt 45 GB) reichen für das Thema.
Damit der Blick später „Kachel 12" sagen kann, trägt jede Kachel eine **Nummer**
und daneben liegt ein **Zuordnungs-JSON** (Nummer → fileid, Name, Größe,
`ist_video`). Ein Vision-Call je **Bogen** statt je Bild — das ist die
Kostengrenze dieser Stufe (Messung folgt als N5).

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/foto_themen.py` | Anlass-Bildung aus der Sortier-CSV, Vorschaubilder in Stapeln (pCloud), Kontaktbogen als JPEG, Zuordnungs-JSON, Kommandozeile |
| `backend/tests/test_foto_themen.py` | **25 Prüfungen** — alles ohne Netz (Attrappen für listfolder/getthumbs) |

**Reine Funktionen** (ohne pCloud testbar): `anlaesse_bilden`, `zeit_aus_name`,
`ist_video`, `bogen_bauen`, `zuordnung_schreiben`, `antwort_zerlegen`,
`ordner_finden`/`dateien_im_ordner`, `vorschau_holen`/`vorschau_stapel`.

**Die Anlass-Regel** (verbindlich, aus dem Plan „gleiche Minute = gleicher
Anlass"):

* Bilder **derselben Minute** landen **immer** im selben Anlass.
* Zusätzlich bilden Aufnahmen bis **30 Minuten** Abstand **eine Sitzung**
  (Standard; `--luecke N` änderbar, `--luecke 1` ≈ Minutengranularität).
  Ohne diese Regel wäre der „Anlass" faktisch das Einzelbild — dann hätte der
  Vision-Call je Anlass keinen Vorteil gegenüber je Bild.
* Dateien ohne Uhrzeit im Namen (WhatsApp-Empfang: `IMG-…-WA0001.jpg`) bilden
  einen eigenen Anlass **„ohne Uhrzeit" am Tagesende**.
* Ein Anlass zählt pro Tag (`2025-06-06_Anlass-01`, `-02`, …); eine Sitzung
  über Mitternacht wird am Tageswechsel getrennt (dokumentiert, nicht umgangen).

**Befehle** (venv des Backends — dort liegen `httpx` und `Pillow`; Pillow war
**bereits vorhanden**, 12.3.0, keine Neuinstallation nötig):

```bash
cd backend
# Nur planen/anzeigen — holt NICHTS, schreibt NICHTS, braucht keinen Token:
.venv/Scripts/python ../tools/foto_sortierung/foto_themen.py --jahr 2025 --limit 3 --trocken
.venv/Scripts/python ../tools/foto_sortierung/foto_themen.py --jahr 2025 --limit 0 --nur-liste

# Einen Anlass bauen (Standard-Limit 3 Anlässe, klein halten):
.venv/Scripts/python ../tools/foto_sortierung/foto_themen.py --jahr 2025 --anlass 2025-06-06_Anlass-01
```

**Regeln, die das Werkzeug einhält:**

* **Nur lesend** gegenüber der pCloud: `listfolder` (ein Ordner = ein Aufruf,
  kein rekursiver Vollscan) + `getthumbs`. Kein Schreiben, kein Löschen.
* **Ausgabe nur außerhalb des Repos:** `~/foto_sortierung/boegen/<Jahr>/` —
  je Bogen `<Titel>.jpg` + `<Titel>.json`. Im Repo liegt nur das Werkzeug.
* **Token bleibt geheim:** er wird nie ausgegeben/gebloggt und aus jeder
  Fehlermeldung entfernt (`ohne_token`, per Test belegt).
* **Idempotent:** vorhandener Bogen (JPEG + JSON) wird übersprungen — zweiter
  Lauf holt nichts nach (live belegt, siehe unten).

## Live-Funde (27.09.2026, eapi.pcloud.com — nur gelesen)

* `getthumbs` liefert **keine Binärdaten**, sondern Textzeilen
  `fileid|0|86x120|data:image/jpeg;base64,…`; angefragt wird `type=jgp`
  (PNG scheitert bei diesem Konto mit Code 5002 — Fund aus N1).
* **Mehrere fileids in EINEM Aufruf** funktionieren (Stapel): 40 ids → 40 Zeilen
  in ~1 s. Die **Reihenfolge ist nicht garantiert** → Zuordnung strikt über die
  fileid, nie über die Position (per Test mit verdrehter Antwort abgesichert).
  Stapelgröße hier: 25 je Aufruf.
* **Videos und HEIC** bekommen von pCloud ebenfalls ein JPEG-Vorschaubild
  (mp4 → 68×120). Die Kachel zeigt es und trägt zusätzlich das Kennzeichen
  **„VIDEO"**; `ist_video: true` steht im JSON. (Ein echter erster Frame via
  `ffmpeg` bleibt als späterer Schritt notiert — für die Themen-Stufe nicht
  nötig.)
* Nicht gefundene/fehlende fileids: `…|2009|0` bzw. `…|5002|0` → Platzhalter-
  Kachel mit Nummer („kein Bild"/„VIDEO"), ehrliche Zählung „nicht gefunden".
* **Geräteübergreifende Doppelungen live gesehen:** ein Anlass enthielt dasselbe
  Foto je einmal aus dem Motorola- und dem OnePlus-Ordner (die CSV markiert die
  Kopie in der Spalte `doppelung`). Der Bogen zeigt **alle** Zeilen des Anlasses
  (jede Datei braucht ihr Thema); N6 kann über `doppelung` deduplizieren.

## Echte Stichprobe (nur lesend, 2 Anlässe aus 2025)

```
2025-02-21_Anlass-01   20:04–20:15   10 Kacheln (2 Videos)
  10 Vorschauen geholt (44.294 Bytes), Bogen 62.566 Bytes, 3,1 s
  -> ~/foto_sortierung/boegen/2025/2025-02-21_Anlass-01.jpg (1382×362, alle 10 Kacheln nummeriert)

2025-01-06_Anlass-01   17:34–18:36   36 Kacheln (6 Videos)
  36 Vorschauen geholt (186.514 Bytes), Bogen 262.437 Bytes, 5,8 s
  -> ~/foto_sortierung/boegen/2025/2025-01-06_Anlass-01.jpg (1382×872, alle 36 Kacheln nummeriert)

Zweiter Lauf (Idempotenz): geholt: 0 Vorschaubilder, uebersprungen: 1, Dauer 0,4 s.
Trockenlauf (--jahr 2025 --limit 3 --trocken): 0,3 s, nichts geholt, nichts geschrieben
  (erkannte den vorhandenen Bogen als „waere uebersprungen").
```

**Bestandsbild (30-Minuten-Regel, aus der echten CSV):** 2.128 Anlässe über alle
Jahre — 2022: 409, 2023: 447, 2024: 430, **2025: 380**, 2026: 301; davon 369
„ohne Uhrzeit". Kacheln je Anlass: Median 2, Mittel 3,9, Maximum 108 (9 Anlässe
über 48 Kacheln — für N5/N6 im Blick behalten). 6.804 der 8.302 datierten
Dateien tragen eine Uhrzeit im Namen; die übrigen 1.498 (WhatsApp & Co.) sind
die „ohne Uhrzeit"-Anlässe.

## Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
→ 525 passed, Exit 0 (58,7 s; vorher 500 → +25 neue Prüfungen)

nur die neuen: .venv/Scripts/python -m pytest tests/test_foto_themen.py -q
→ 25 passed, Exit 0 (1,2 s)
```

Nach dem parallelen N2-Schritt (Rückroll-Werkzeug, +20 Prüfungen) lief derselbe
volle Befehl erneut: **545 passed, Exit 0** (71,4 s) — nichts rot.

Abgedeckt u. a.: gleiche Minute = ein Anlass, verschiedene Tage getrennt,
Lücken-Regel, „ohne Uhrzeit", Überspringen ohne Datum, Kachel-Nummern **im
Bild** (Pixelprüfung), Platzhalter/VIDEO-Kennzeichen, vollständiges
Zuordnungs-JSON (+ Ablehnung lückenloser Nummerierung), Stapel-Zuordnung über
fileid bei verdrehter Antwort, Wiederholung bei Netzfehler (max. 3),
definitiver Code 5002 ohne Wiederholung, Trockenlauf/Nur-Liste ohne Netz,
Idempotenz, **Token taucht nirgends auf**.

## Was dieser Schritt NICHT getan hat

* **Kein Vision-Blick** — wer die Bögen ansieht, entscheidet der Hauptagent
  (Kostengrenze: erst eine Stichprobe messen, N5).
* **Nichts in die pCloud geschrieben**, nichts sortiert, nichts verschoben.
* **Nichts ins Repo geschrieben** — Bögen und Zuordnungen liegen nur unter
  `~/foto_sortierung/boegen/`.
* Keine Gesichtserkennung (Stufe 3), keine Themen-Spalte im Sortierschlüssel
  (N6 füllt sie).

## Nächste Schritte

1. **N5:** einen vorhandenen Bogen an Vision geben und die Kosten je Bogen
   messen (Stichprobe reicht — die Bögen sind fertig).
2. **N6:** Thema je Anlass in die Spalte `thema` des Sortierschlüssels
   schreiben; Doppelungen über `doppelung` mitziehen.
3. Offen im Stufe-2-Plan (`plan-foto-personen-und-erinnerungen.md`): Statuszeile
   nachziehen, wenn N5/N6 stehen — diese Datei gehört dem Hauptagenten.
