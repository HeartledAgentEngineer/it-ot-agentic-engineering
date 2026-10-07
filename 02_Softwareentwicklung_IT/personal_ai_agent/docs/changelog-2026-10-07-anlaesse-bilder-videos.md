# Änderungsprotokoll 07.10.2026 — Anlässe für „Bilder & Videos" (Issue #4, A1)

Befund Hermes (Issue #4): Die Sammlung „Bilder & Videos" (11.630 Einträge: 10.771 Fotos,
859 Videos, 171 Ordner, darin die Urlaube) hatte **null** Anlässe. Nur der Upload-Stapel
(2.127 Anlässe) und das Fotobuch standen im Erzählen. Sebastian: „da fehlen auch noch ganz viele
Anlässe".

## Neu: `tools/foto_sortierung/ereignisse_ordner_bauen.py`

Baut aus dem Sortierplan der Sammlung (`sortierplan_bildervideos.json`) Anlässe im Format der
Erzähl-Diashow und schreibt sie in eine **eigene** Datei `~/foto_sortierung/ordner_ereignisse.jsonl`.
Die vorhandenen Ereignisdateien werden nicht angefasst.

**Datum je Datei.** Die Reihenfolge weicht bewusst von der Übergabe ab („Dateiname zuerst"):

1. **EXIF-Aufnahmezeit**: `metadaten.aufnahme` aus den Vektordateien des Gesichterlaufs. Jedes Foto
   wurde dort schon einmal geladen, ein neuer Download entfällt. Die Kamera-Uhr liefert die Uhrzeit,
   und das Datum übersteht Bearbeiten und Umbenennen.
2. **Dateiname**: `IMG_20190705_143000`, `IMG-…-WA0001`, `PXL_…`, `2019-07-05 14.30.00`. Bei
   Kamera-Dateien steht dort dasselbe wie im EXIF. WhatsApp entfernt das EXIF, dort trägt nur der
   Name das Datum, ohne Uhrzeit.
3. **pCloud `modified`**, falls die Planzeile oder `--liste` (JSONL `{fileid, modified}`) es
   liefert. `created` ist nur der Upload und wird nie benutzt.
4. Sonst nur das **Jahr** aus dem Ordnerpfad (`…/2016`), sonst das Plan-Jahr.

**Plausibilität.** Gültig sind Daten ab 1990 bis heute. Die Unsinns-Jahre 1901–1970 aus Dateinamen
und Kamera-Uhren auf 1970 fallen auf die nächste Quelle zurück.

**Ordnerjahr.** Trägt der Ordner ein Jahr und weicht das Datum um mehr als ein Jahr davon ab
(Scan- oder Bearbeitungsdatum), gewinnt das Ordnerjahr. Die Toleranz von einem Jahr hält
Silvesterfotos nach Mitternacht im richtigen Anlass.

**Bündelung.** Die Aufnahmen werden je Handordner chronologisch geordnet. Ein neuer Anlass beginnt
nach mehr als 18 Stunden Pause (`--luecke-stunden`).
- Eine Reise mit Fotos an jedem Tag bleibt so ein Anlass, weil die Nachtpause bei etwa 12 Stunden
  liegt.
- Zwei Konzerte an zwei Abenden werden getrennt, weil dazwischen etwa 24 Stunden liegen.
- Dateien mit Datum, aber ohne Uhrzeit (WhatsApp) gelten als 12:00.
- Dateien nur mit Jahr bilden je Ordner und Jahr einen Anlass „ohne genaues Datum“.

**Kein Bild doppelt.** Bilder, die schon im Upload-Stapel (`ereignisse.jsonl`) oder im Fotobuch
(`fotobuch_ereignisse.jsonl`) stehen, werden übersprungen (`--ohne`).

**Ausgabe.** Je Anlass eine Zeile mit allen Schlüsseln von `ereignisse.jsonl` und einigen
Zusätzen:

| Feld | Inhalt |
|---|---|
| `kennung` | `O-<kleinste fileid>`, stabil, hängt nicht an der Reihenfolge |
| `event` | Titel aus Ordnername und Zeitraum, z. B. „Konzerte Party · Juni 2016“ |
| `thema` | Ordnername |
| `kategorie` | erste Ordnerebene |
| `datei_kennungen` | in Aufnahmereihenfolge |
| `datum`, `bis` | erster und letzter Tag |
| `sammlung` | `bilder_videos` |
| `videos` | Zahl der Videos |
| `quellen.datum` | Zahl je Datumsquelle |

**Bericht und Schutz.**
- Die Konsole zeigt **nur Zahlen**: Planzeilen, übersprungen, je Datumsquelle, verworfen, Anlässe,
  Jahre, Größen.
- Standard ist der Trockenlauf. `--schreiben` schreibt atomar. Bei gleichem Inhalt bleibt die
  Datei unangetastet, der Lauf ist also wiederholbar.
- Liegt das Ziel im Repo, endet der Lauf mit Exit 2.
- `--senden` legt die Datei per adb nach `/sdcard/Download`.

## Geändert

- `backend/app/services/erzaehl_service.py`:
  - Liest `ordner_ereignisse.jsonl` neben `ereignisse.jsonl` (übersteuerbar mit
    `ERZAEHL_ORDNER_EREIGNISSE_PFAD`) und führt beide **chronologisch** zusammen. Die Sortierung
    ist stabil; Anlässe nur mit Jahr stehen am Ende ihres Jahres.
  - Das Fotobuch bleibt vorn.
  - Ohne die neue Datei bleibt die Reihenfolge wie bisher.
  - `ereignisse_existiert()` kennt die Datei.
- Übergabe ans Handy: `ordner_ereignisse.jsonl` steht in der Dateiliste von `start-termux.sh` und
  `termux/agent-ensure.sh` (echter App-Startweg). Der Wächter in
  `test_uebergabe_uebernehmen.py` kennt jetzt zehn Dateien.

## Lauf (PowerShell, aus dem Projektordner)

Der Lauf geht über Sebastians Daten und wird von Sebastian oder Hermes gestartet. Zuerst der
Trockenlauf, er zeigt nur Zahlen:

```powershell
& backend\.venv\Scripts\python.exe tools\foto_sortierung\ereignisse_ordner_bauen.py
```

Danach schreiben und ans Handy senden (Kabel, USB-Debugging):

```powershell
& backend\.venv\Scripts\python.exe tools\foto_sortierung\ereignisse_ordner_bauen.py --senden
```

Beim nächsten App-Start übernimmt das Handy die Datei. Die Anlässe stehen dann im 📖 Erzählen,
chronologisch zwischen den bisherigen.

## Prüfung

- Neu `backend/tests/test_ereignisse_ordner_bauen.py`, 16 Tests mit erfundenen Daten:
  - Datumsquellen und ihre Reihenfolge
  - Plausibilität: 1970, 1901 und Zukunft werden verworfen
  - Ordnerjahr gegen Scan-Datum, Silvester-Toleranz
  - Ordnerpfad zerlegen
  - Reise bleibt zusammen, zwei Konzertabende werden getrennt; Monatsspanne im Titel
  - Anlässe nur mit Jahr und ohne Datum
  - Vergebene, doppelte und kennungslose Zeilen werden übersprungen
  - Trockenlauf nur mit Zahlen, ohne Ordner- und Dateinamen
  - Schreiben wiederholbar und byte-gleich
  - Schutz: Repo-Ziel (Exit 2), fehlender Plan (Exit 3), Senden ok und fehlgeschlagen
  - Diashow: chronologisches Zusammenführen, Jahresfilter, Detail, Reihenfolge ohne die Datei
    unverändert, die Datei allein reicht als Quelle
- Prüfbefehl: siehe Commit.

## Offen

- Der echte Lauf (Sebastian oder Hermes) und die Zahlen daraus.
- Orte im Titel (#15/#16): Möglich über `anlass_namen.py` mit `orte.jsonl`/`bild_orte.csv`,
  sobald die Orte gefiltert vorliegen.
- Fotos im Fotobuch-Ordner, die nicht im Buch stehen, tragen oft das Scan-Datum 2013. Ihr Titel
  nennt den Ordner, sie sind also erkennbar.
