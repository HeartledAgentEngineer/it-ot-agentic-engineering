# Änderungsprotokoll 10.10.2026 — Bestandsprüfung: Deckung über den Gesamtplan

## Anlass

Der Bericht der Bestandsprüfung zählte die Beschreibungen **je Sortierplan** und
meldete danach drei plus fünf Fotos als „ohne Beschreibung" (Lücken). Für die
Schlussabrechnung des Nachtlaufs ist aber eine andere Frage entscheidend:

> Sind wirklich **alle** Fotos des Gesamtbestands beschrieben — egal aus welcher
> der inzwischen vier Beschreibungsdateien die Zeile kommt?

Diese Zahl war nirgends ablesbar. Sie wurde von Hand nachgerechnet (Ad-hoc-Skript)
und **von der Prüfung nicht reproduziert** — genau der Zustand, den die Regel
„fertig ist, was verifiziert ist" ausschließt. Zusätzlich fehlten zwei der vier
Beschreibungsquellen in der Voreinstellung: `bild_beschreibungen_reich.jsonl`
(17.428 Zeilen, reiche Fassung der Sammlung) und
`bild_beschreibungen_rest_reich.jsonl` (984 Zeilen, Nachzügler-Lauf).

## Änderung

- `STANDARD_BESCHREIBUNGEN` führt jetzt **alle vier** Quellen (Altspeicher, Papas
  reiche Fassung, reiche Fassung der Sammlung, Nachzügler). Der Bericht druckt
  weiterhin eine Zeile je Datei; die Zuordnung zu den Plänen läuft über die
  Kennungen (Vereinigung) und wird dadurch erst vollständig.
- Neuer Abschnitt **„Gesamtplan"** (`gesamtplan_lesen()`): der Union-Plan
  `sortierplan_reich_gesamt.json` wird gegen **alle** Beschreibungsdateien
  zusammen gestellt. Eine Zeile nennt Einträge = Fotos + Videos + ohne Namen
  (+ ohne Kennung), die zweite die Deckung samt Zahl der Fotos, die in **keiner**
  Datei eine Zeile haben. Fehlende Fotos landen als Lücke im Ergebnis.
- Der Union-Plan mischt die Feldnamen der Quell-Pläne (`von_name` bei Sammlung
  und Sortierplan, **`name` bei Papas Plan**) — es werden wie im
  Beschreibungs-Werkzeug **beide** Formen gelesen. Genau dieser Fehler hatte am
  Vormittag Papas 6.336 Fotos still aus dem reichen Beschreibungslauf geworfen
  (Changelog `union-plan-feldnamen`); der neue Abschnitt ist der Regressionshaken
  dagegen. Einträge ohne Namen (Fotobuch-Scans) und ohne Kennung werden gezählt,
  nicht verschluckt.
- Abschaltbar über `gesamtplan=None` (andere Bestände).

Unverändert: nur lesend, nur Zahlen und Dateinamen (keine Namen, keine
Beschreibungen, keine Koordinaten, keine Vektoren), es wird nichts geschrieben,
Exit-Code 0 (Bericht) / 2 (Basisordner fehlt).

## Prüfung (offline, nur lesend)

- **Lauf am echten Bestand** (`backend/.venv/Scripts/python
  tools/foto_sortierung/bestand_pruefen.py`, 13:4x, Exit 0) — neuer Abschnitt:

  ```
  Gesamtplan sortierplan_reich_gesamt.json: 28.796 Eintraege = 23.916 Fotos + 1.666 Videos + 3.214 ohne Namen
    Beschreibungen:   23.908 von 23.916 Fotos (100,0 %) - in keiner Beschreibungsdatei fehlen 8
  ```

  Damit ist das „Zahlenrätsel" der Beschreibungsläufe (17.580 geplant / 26.424
  eindeutige Kennungen / 23.916 nach dem Feldnamen-Fix) in einer Zeile
  beantwortet: **8 Fotos des Gesamtplans haben in keiner der vier Dateien eine
  Zeile** — die früher gemeldeten 3 + 5 sind dieselben acht, verteilt über zwei
  Einzelpläne.
- Neue Tests in `backend/tests/test_bestand_und_handy_uebergabe.py`:
  `test_gesamtplan_deckung_liest_beide_feldnamen` (Papa-Form `name` wird
  mitgelesen: 2 Fotos statt 1; Lücke wird gemeldet) und
  `test_gesamtplan_fehlt_wird_ehrlich_gemeldet` (fehlender Plan wird gemeldet,
  `gesamtplan=None` schaltet den Abschnitt ab) — **17 passed**.
- **Voller Prüfbefehl:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → siehe Commit (grün, Exit 0).

## Offen (ehrlich)

- Die 8 Fotos werden als Zahl gemeldet, nicht benannt (kein Klartext-Inhalt) —
  welcher Grund sie hat (keine Vorschau, Video-Erkennung, Dublette), ist offen.
- Die Lückenliste nennt die acht Fotos zweimal (einmal je Einzelplan, einmal
  Gesamtplan). Das ist Absicht (Detail + Gesamtsicht), kann aber wie doppelt
  wirken.
- Für Videos gibt es weiterhin keine Beschreibungen (eigener, nie beauftragter
  Weg) — der Gesamtplan weist sie deshalb getrennt aus.
