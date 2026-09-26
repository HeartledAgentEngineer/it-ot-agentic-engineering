# Sortierschlüssel für die pCloud-Fotos — Schritt 1 (Stufe B: Jahr/Thema)

> **Datum:** 26.09.2026 · **Auftrag:** Sebastian (26.09.): Fotos in der pCloud
> sortieren — „die Sortierung der letzten vier Jahre, alles was im Upload-Ordner
> ist", Zielstruktur **B: `Jahr/Thema`** (per Zuruf entschieden), dazu
> **Personen clustern** nach dem Schema des Quiz.

## Warum es diesen Schritt gibt

Vorher gab es zum Sortieren **nur Planung** (`docs/plan-pcloud-anbindung.md`,
`docs/ubergabe-2026-09-15-pcloud-planung.md`), **keinen Code**. Ohne
Sortierschlüssel ist jede weitere Stufe Blindflug: Man weiß nicht, wie viele
Dateien in welchem Jahr liegen, welche Dateien kein Datum im Namen tragen und
wie viel überhaupt zu lesen wäre.

Nebenbefund aus der Messung: **Rekursives Durchlaufen der pCloud läuft in einen
Timeout** (belegt 180 s, Exit 124). Der Schlüssel liest deshalb **Ebene für
Ebene** mit fester Tiefenbegrenzung (3) — die ganze Inventur dauerte dadurch
**1,44 s**.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/sortierschluessel.py` | liest Namen + Größen im Upload-Ordner, schreibt die CSV, gibt eine Übersicht aus |
| `backend/tests/test_foto_sortierung.py` | 8 Prüfungen der reinen Funktionen (Datum, Motivname, Zielordner, Doppelungen) |

**Reine Funktionen** (ohne pCloud testbar): `datum_aus_name`, `motiv_name`,
`ziel_ordner`, `doppelungen_markieren`, `uebersicht`.

**Datenschutz und Projektregeln, die das Werkzeug einhält:**

* Es liest **nur Namen und Größen** — kein Bild wird geöffnet, geladen oder
  kopiert, die pCloud wird **nicht verändert**.
* Die CSV enthält private Dateinamen und liegt deshalb **außerhalb des Repos**:
  `~/foto_sortierung/sortierschluessel.csv`. Im Repo liegt nur das Skript.
* Zielstruktur (berechnet, noch nicht angelegt):
  `Agent/Fotos/<Jahr>/<Thema>/<Gerät>` — Schreibziel ist der eigene `Agent/`-
  Ordner, nie `Familie`, `Dokumente` oder ein bestehender Ordner.
* **Kopie, nie Verschieben**: Originale bleiben, wo sie sind.
* **Zusätzliche Absicherung in `.gitignore`** (26.09.): `sortierschluessel*.csv`,
  `foto_sortierung/` und `aussortierte_gesichter/` sind gesperrt — falls jemand
  das Werkzeug doch einmal im Repo startet, landen die privaten Dateinamen nicht
  in Git. (Anlass: Sebastians berechtigte Rückfrage, ob Referenzdaten in GitHub
  gelangt sind. Prüfung: in **allen** Zweigen wurden nie Bild-, Vektor- oder
  Datenbankdateien committet — nur die beiden App-Symbole `icon-192.png` /
  `icon-512.png`.)

## Messung (echte Ausgabe, 26.09.2026)

```
Jahr          Dateien  Motive  Größe GB  Doppel  ohne Datum
2014                4       1      0.01       3           0
2016                2       1      0.00       1           0
2017                2       1      0.00       1           0
2019               90      40      0.46      50           0
2020              116      48      0.45      68           0
2021              296     247      1.05      49           0
2022             1946    1833      7.64     113           0
2023             1548    1546      5.24       2           0
2024             1971    1785     12.01     186           0
2025             1490    1286     13.73     204           0
2026              837     837      6.90       0           0
ohne Datum       1128     271     49.10     857        1128

Dateien gesamt: 9430   mit Datum: 8302   offen: 1128
```

**Lesart:**

* Die **letzten vier Jahre** (2022–2026) sind **7.792 Dateien ≈ 45,5 GB**.
* **2023 liegt fast vollständig beim OnePlus** (1.546 von 1.548) — Gerätewechsel,
  kein fehlendes Jahr.
* **1.128 Dateien ohne Datum** — überwiegend Videos (`Oplus_0.mp4` …) und
  empfangene Bilder (`file_00000000….png`). Sie machen mit **49,1 GB** mehr
  Volumen aus als zwei Jahre zusammen; für sie muss das **EXIF-Aufnahmedatum**
  gelesen werden (Dateikopf genügt), nicht der Name geraten.
* **Doppelungen** (`(2)`, `_Kopie`) sind markiert — z. B. 780 beim OnePlus.
  Die Motiv-Zahl (Motive-Spalte) zählt sie nicht mit.

## Was dieser Schritt NICHT getan hat

* **Keine Sortierung angelegt** — es wurde nichts kopiert und nichts verschoben.
* **Kein Clustering** — die Spalte `thema` ist bewusst leer (Stufe 2 füllt sie).
* **Keine Personen** — dafür existiert bereits eine eigene Kette (siehe unten,
  Stufe 3).
* **Kein Token** — pCloud wird bisher über das Laufwerk `P:\` gelesen.

## Nächste Stufen (Stand nach der Messung)

* **Stufe 2 — Themen-Clustering:** Kontaktbögen aus Vorschaubildern je Tag/Anlass,
  Vision-Blick auf den Bogen (nicht auf jedes Bild) → Thema je Anlass →
  `Agent/Fotos/<Jahr>/<Thema>/…` als **Kopie**.
* **Stufe 3 — Personen-Clustering (Sebastians Zuruf 26.09.):** Die Kette
  existiert bereits auf dem Handy — `backend/face_infer.py` (YuNet-Erkennung +
  SFace-Erkennungserkennung als ONNX, mit EXIF-Drehung), `gesichter_service.py`,
  `face_service.py`, `router/gesichter.py`, `gesicht_quiz.py` (Quiz-Fragen
  JA/NEIN je Gesicht), `sortiere_gesichter.py` (sortiert nach bekannten Personen,
  Unbekanntes nach `_neu`), `trainiere_gesichter.py`. Sie arbeitet heute aber nur
  auf `~/storage/dcim/Lieblingsbilder` **auf dem Handy** — nicht auf der pCloud.
  Für die pCloud fehlen: Zugang auf dem Handy (rclone/Token), ein Lauf über die
  Jahre in Stapeln, ein Cluster-Schritt für die **unbekannten** Gesichter
  (SFace-Vektoren gruppieren), und die Bestätigung im Quiz („diese Gruppe ist
  dieselbe Person") als Anlern-Schleife.
* **Randbedingung, ehrlich:** Gesichtserkennung braucht brauchbare Auflösung —
  pClouds Vorschaubilder (120 × 120) reichen dafür **nicht**. Für die
  Personen-Stufe müssen die Originale gelesen werden (2022–2026: ≈ 45,5 GB),
  sinnvoll in Jahres-Stapeln. Für die Themen-Stufe (Kontaktbögen) genügen
  Vorschaubilder.

## Prüfung

```
cd backend && .venv/Scripts/python -m pytest tests/test_foto_sortierung.py -q
→ 8 passed, Exit 0
```

Der volle Prüfbefehl läuft beim Commit über den Git-Hook.
