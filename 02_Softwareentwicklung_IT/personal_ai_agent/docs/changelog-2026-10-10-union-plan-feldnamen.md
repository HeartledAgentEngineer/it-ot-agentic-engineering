# Änderungsprotokoll 10.10.2026 — Union-Plan: Papas 6.336 Fotos fielen aus dem Beschreibungslauf

## Anlass

Der reiche Beschreibungslauf über den Gesamtplan meldete **17.580 Zeilen / 489
Bögen**, der Plan führt aber **28.796 Züge in 26.424 eindeutigen Kennungen**. Im
Planjournal stand das als „Zahlenrätsel, Ursache offen". Die Nachmessung am
echten Plan erklärt es vollständig — und deckt einen echten Fehler auf:

`plan_zeilen_lesen()` in `tools/foto_sortierung/bild_beschreiben.py` las den
Dateinamen nur als `von_name`. Der zusammengeführte Plan
`sortierplan_reich_gesamt.json` mischt aber die Feldnamen seiner Einzelpläne:

| Quelle im Union-Plan | Züge | Feldnamen | gelesen (alt) |
|---|---|---|---|
| `sortierplan_bildervideos.json` | 11.630 | `von_name` / `von_ordner` | ja |
| `sortierplan.json` | 7.616 | `von_name` / `von_ordner` | ja |
| **`sortierplan_papa.json`** | **6.336** | **`name` / `ordner`** | **nein — still verworfen** |
| `gedreht_plan.json` | 2.373 | nur `fileid` | nein (Doppelte bereits benannter Bilder) |
| `fotobuch_plan.json` | 841 | `fileid` / `jahr` | nein (kein Dateiname) |

**Folge:** Papas 6.336 Fotos waren im Beschreibungslauf **nicht enthalten**
(0 von 6.336 beschrieben) — obwohl der Plan ausdrücklich „alle 6.336 Papa-fileids
enthalten" belegt. Das Prüfkriterium von Schritt 6 hätte sie nicht gefunden.

## Änderung

`plan_zeilen_lesen(pfad, statistik=None)` liest den Dateinamen jetzt aus
**beiden** Formen: `von_name` **oder** `name`, den Ordner aus `von_ordner`
**oder** `ordner`. Züge ohne jeden Dateinamen bleiben wie bisher aus (sie sind
ohne Namensabgleich nicht benennbar), werden aber **gezählt statt still
verschluckt**: Ist `statistik` übergeben, füllt die Funktion `keine_kennung`,
`kein_name`, `video` und `doppelt`. Der Kommandozeilenlauf druckt die vier
Zahlen als eigene Zeile („Ausgelassen: …"), damit ein unvollständiger Plan
sofort auffällt.

Unverändert: der Videoschnitt nach Endung, die Kennungs-Entdopplung, die
Datumsableitung aus dem Dateinamen (nichts wird geraten), die Bogenpackung, die
Kostenbremse und das Überspringen bereits beschriebener Bilder. Der heutige
Standardweg (`--plan` mit `von_name`) liefert dasselbe Ergebnis wie vorher.

## Prüfung (offline, kein Vision-Aufruf, kein Netz)

- **Messung am echten Plan** (`sortierplan_reich_gesamt.json`, nur lesend):
  mit dem Fix **23.916 geplante Zeilen** statt 17.580; **6.336 von 6.336
  Papa-Kennungen** enthalten (vorher 0). Ausgelassen laut Zähler:
  842 ohne Dateinamen, 1.666 Videos, 2.372 Doppelte, 0 ohne Kennung —
  842 + 1.666 + 2.372 = 4.880; 23.916 + 4.880 = 28.796 (der ganze Plan).
- `backend/tests/test_bild_beschreiben.py`: neuer Test
  `test_plan_zeilen_liest_beide_feldnamen_formen_und_zaehlt_ausgelassenes`
  (beide Feldformen, Video raus, Zählerstand) — **55 passed**.
- **Voller Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → siehe Commit (grün, Exit 0).

## Offen (ehrlich)

- Die **842 Züge ohne Dateinamen** (Fotobuch-Scans, `fotobuch_plan.json`) bleiben
  unbeschrieben — sie tragen im Plan keine Datei, ein Namensabgleich per
  pCloud-listfolder wäre ein eigener Schritt. Die 2.372 `gedreht`-Züge sind
  Doppelte längst benannter Bilder und zu Recht ausgelassen.
- Der **laufende** Beschreibungslauf hat den alten Code im Speicher und holt
  Papa **nicht** nach. Ein zweiter Durchgang mit derselben `--jsonl` (Werkzeug
  setzt fort) ist nötig: **9.487 offen** (Stand 10:2x), Papa darunter 6.336.
  Das ist der im Plan (Schritt 6, Prüfkriterium 3) vorgesehene Nachzug.
