# Änderungsprotokoll 30.09.2026 — Personen gruppieren über alle Gesichter (Foto-Gedächtnis, Schritt 1)

Plan: `C:\Users\sebas\.claude\plans\dapper-roaming-rose.md` (Foto-Gedächtnis: Personen und
Anlässe über das Quiz anlernen, dann im Chat fragen). Schritt 1 = die Gruppen, die das Quiz
später zum Benennen zeigt.

## Anlass

Die Gesichtsvektoren sind für alle Bilder fertig (Aufgabe 1: 7.530, Aufgabe 3: 11.310 Zeilen,
dazu Video-Standbilder). Gruppiert wurde bisher nur eine Stichprobe (92 Bilder → 12 Personen):
`personen_cluster.vollstaendig_clustern` baut eine volle n × n-Matrix und legt bei jeder
Verschmelzung neue n × n-Arrays an (`personen_cluster.py:794–820`) — bei ~30.000 Gesichtern rund
7 GB je Matrix und etwa n³ Schritte. Zudem las das Werkzeug nur **eine** Vektordatei.

## Neu: `tools/foto_sortierung/personen_gruppieren.py`

Eigenes Werkzeug; `personen_cluster.py` (235 Tests) bleibt unverändert und liefert per Import
Zeilenprüfung, Mengen-Regel (`bild_entscheidung`), Gesichtsbewertung, Schwellen, Kennungsmuster,
Repo-Schutz und Altbestand-Lesen.

Verfahren **Mittelpunkt** (nur numpy, Speicher O(n × 128), keine n × n-Matrix):
1. Anlegen: Gesichter nach Qualität (Anteil × Score); jedes an die ähnlichste Gruppe mit
   Mittelpunkt-Cosinus ≥ 0,55 (= bisherige Cluster-Grenze 0,45 als Distanz) — **nie** an eine
   Gruppe mit einem Gesicht desselben Bildes (cannot-link).
2. Zwei Verfeinerungsrunden: alle Gesichter neu zuordnen, je Bild ohne Doppelung.
3. Verschmelzen bei Mittelpunkt-Cosinus ≥ 0,60 — außer bei gemeinsamem Bild, Nutzervorgabe
   „verschieden" (`personen_vorgaben.json`) oder verschiedenen bestätigten Namen
   (`personen_bestaetigt.json`); Vorgabe „gleich" legt zusammen.
4. Gruppen unter 3 Gesichtern = Rauschen (keine Kennung).
5. Ähnliche, getrennt gebliebene Gruppen (Cosinus ≥ 0,45) als Kandidaten fürs Quiz — mit Zahl
   gemeinsamer Bilder (> 0 = sicher zwei Menschen, z. B. Zwillinge). Entschieden wird nie
   automatisch.

Stabile Kennungen über Läufe (Mittelpunkt-Abgleich wie `gruppen_kennungen`, aber vektorisiert),
größte Gruppe zuerst.

Ausgaben (nur `--schreiben`, nur außerhalb des Repos, atomar), Standardordner
`~/foto_sortierung/personen_gruppen/`:
- `gesicht_zuordnung.jsonl` — je Gesicht Bild, Index, Kennung, bbox, Größe, Anteil, Score,
  Aufnahme, Video — **ohne Vektoren** (darf ans Handy).
- `personen_beispiele.json` — je Gruppe Größe, Bilder, Videos, Zeitraum, Name (falls bestätigt),
  Kandidaten und bis zu 8 Beispiel-Gesichter (nur Fotos, je Bild eins, über die Jahre
  gestreut) — **ohne Vektoren** (darf ans Handy, Grundlage des Quiz).
- `kennungen.json` — Mittelpunkte je Kennung (Biometrie, **bleibt am PC**).

Bericht nur Zahlen (keine Namen, keine Kennungen, keine Dateinamen von Fotos).

## Mitgezogen: Kennungen ab 1.000 in `personen_andocken.py`

`_ist_person` erkannte nur genau drei Ziffern; ab der 1.000. Gruppe vergibt `Person_%03d`
aber `Person_1000` — bestätigte Namen wären still ignoriert worden. Jetzt gilt genau die
Schreibweise von `Person_%03d` (≥ 3 Ziffern, keine zusätzlichen führenden Nullen);
`test_personen_andockung.py` um drei Fälle erweitert.

## Prüfung

- Neu `backend/tests/test_personen_gruppieren.py`: 17 Tests, offline mit erfundenen Vektoren
  (Reinheit, Größenordnung, selbes Bild nie in einer Gruppe, Zwillinge auf gemeinsamen Bildern
  getrennt + markiert, Rauschen, Determinismus, 6.000-Gesichter-Probe, stabile Kennungen,
  `Person_1000`, Vorgaben verschieden/gleich, verschiedene Namen verschmelzen nie, Beispiele,
  Lesen mehrerer Dateien mit Doppelten/Kaputten/Menschenmenge/Video, Trockenlauf schreibt nichts,
  Ausgabe ohne Vektoren, Repo-Ziel Exit 2, Bericht ohne Namen).
- Größenprobe (künstlich, nicht im Test): 31.781 Gesichter (19.031 von 400 Personen + 12.750
  Einzelgänger) → **28,5 s**, 384 Gruppen, **alle rein**, 384 von 400 Personen gefunden.
- Prüfbefehl `backend/.venv/Scripts/python.exe -m pytest tests/ -q` → siehe Commit.

## Offen

- **Echter Lauf** (Sebastian, echte Gesichter — Claude führt ihn nicht aus):
  Trockenlauf, dann `--schreiben`; Bericht (nur Zahlen) zurück an Claude. Die Schwellen sind an
  künstlichen Daten geprüft; am echten Bestand entscheidet der Bericht (Anteil Rauschen, Zahl der
  Gruppen, Kandidaten-Paare), ob `--zuordnung`/`--verschmelzen` nachgestellt werden.
- Video-Standbilder ohne Bildgröße fallen durch die Zeilenprüfung (gezählt als ungültig).
- Schritt 2: Quiz im Gruppen-Modus und Übergabe ans Handy.
