# N6d — Zielkategorien aus Sebastians eigenen Ordnern

> **Stand:** 27.09.2026 · **Nachtlauf-Schritt N6d** (Planer: Hauptagent,
> Ausführer: Hermes-Subagent `deepseek-v4.1-flash`, Prüfer: `openai/gpt-5.6-luna`)
> **Anlass:** Sebastian: „Du kannst ja meine Kategorien bei Videos und Bilder in
> der pCloud sehen — sortiere auf Tags und Blöcke, die man dann Events zuordnet."

## Das Problem, das N6d löst

Die Themen-Stufe (N6/N6b) liefert je Anlass **ein Motiv-Thema aus 53 festen
Einträgen** („Konzert Band Auftritt", „Sonnenuntergang Meer"). Diese 53 Themen
sind als **Ordner untauglich** — Sebastian hat in seiner pCloud längst eigene
Kategorien angelegt. Ein Zielordnerbaum aus 53 erfundenen Motiven würde seinen
Bestand doppeln statt ergänzen.

## Die Übersetzung (drei Stufen)

```
Motiv-Thema (53, aus themen_katalog.py)   →  was ist zu sehen
Bucket (11, generisch, im Code)           →  wohin gehört es grob
echter pCloud-Ordner (lokal gebunden)     →  Zielordner  bzw. null = Neubau
```

* **Stufe 2 steht im Code** (`BUCKETS`, `MOTIV_ZU_BUCKET`): elf generische Eimer,
  `Urlaub`, `Ausfluege`, `Familie`, `Freunde`, `Konzerte und Partys`,
  `Schule und Studium`, `Hobbys`, `Screenshots`, `Rezepte`,
  `Alltag und Wohnen`, `Sonstiges` (Rückfall). Alle 53 Katalog-Einträge sind
  zugeordnet — ein Test prüft die Vollständigkeit gegen `themen_katalog.py`,
  damit kein neues Thema aus N6c stillschweigend ohne Ziel bleibt.
* **Stufe 3 steht NICHT im Code**, sondern lokal in
  `~/foto_sortierung/kategorie_zuordnung.json` — die echten Ordnernamen enthalten
  Namen Dritter und Ortsnamen und gehen das Repository nichts an (dieselbe Regel
  wie beim Bestand selbst, s. `changelog-2026-09-27-kategorien-bestand.md`).
  `null` heißt „Ordner gibt es noch nicht" → wird beim Sortieren neu angelegt.

**Bindung (lokal geprüft, `--zeigen`, Exit 0):** 11 Buckets, **10 gebunden,
1 × `null`** (`Sonstiges` → eigener Ordner, bewusst nicht auf einen bestehenden
gelegt, damit Sebastians Sammelordner nicht zugemüllt wird).

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/foto_kategorien.py` (855 Zeilen) | Bestand lesen/anzeigen, Bucket-Zuordnung laden und prüfen, Zielpfade bauen, Bestand **lesend** aus der pCloud holen |
| `backend/tests/test_foto_kategorien.py` (644 Zeilen) | **38 Prüfungen**, alles ohne Netz, alle Ausgaben nach `tmp_path` |

Öffentliche Schnittstelle: `BUCKETS`, `MOTIV_ZU_BUCKET`, `bucket_fuer_thema`,
`kategorien_laden`, `zuordnung_laden`, `ziel_kategorie`, `pfad_saeubern`,
`ziel_pfad`, `bestandsbericht`, `bestand_holen`, `KategorienFehler`, `main`.

* **Zielpfad-Schema:** `Agent/Fotos/<Jahr>/<Kategorie>/<Event>` — jeder Teil läuft
  durch `pfad_saeubern` (verbotene Zeichen, Rand-Leerzeichen, Länge; Umlaute
  bleiben). Das Jahr wird auf 1900–2100 geprüft.
* **Idempotent:** `bestand_holen` vergleicht den eingelesenen Bestand **ohne**
  Zeitstempel mit dem Inhalt der Datei; ist nichts neu, bleibt die Datei
  byte-identisch (im Test per md5 vor/nach dem zweiten Lauf belegt). Geschrieben
  wird atomar (temp + `os.replace`) und **nur** der übergebene Pfad — ein Ziel
  innerhalb des Repos wird verweigert.
* **Nur lesend gegen die pCloud:** `service.liste` in fester Tiefe 2 (Kategorie →
  Unterordner), kein `thumb`, kein Download, kein Schreiben, keine Rekursion.
* **Keine Löschfunktion** — im Quelltext kommen `deletefile`/`deletefolder` nicht
  vor; ein Test prüft genau das.

## Zahlen (selbst gefahren, nicht behauptet)

* Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **709 passed, 3 warnings, Exit 0** (70,8 s; Baseline vor der Änderung: **671**,
  also +38 neue Prüfungen, keine Regression).
* Live gegen den echten Bestand (`--zeigen`, nur lesend):
  **18 Kategorien · 113 Unterordner · 10 Kategorien mit Unterordnern ·
  11 Buckets (10 gebunden, 1 × null)**, Exit 0, es wurde nichts geschrieben.
* Bestandsdatei `kategorien.json` unverändert (mtime 09:40:53 vor und nach dem Lauf).

## Entscheidungen (statt Fragen)

1. **Generische Buckets im Repo, echte Namen lokal.** So bleibt der Code
   committbar, ohne private Ordnernamen zu veröffentlichen — und die Bindung ist
   an einer Stelle (lokale Datei) änderbar, ohne Code anzufassen.
2. **`Sonstiges` = Neubau statt Umleitung.** Der Rückfallordner wird neu angelegt;
   ein bestehender Sammelordner wird nicht als Müllhalde benutzt.
3. **Ungebundene Kategorien bleiben bestehen.** Nicht jede der 18 Kategorien ist
   ein Sortierziel (Phasen wie BFD/Studium, „Lieblingsbilder", einzelne
   Sammlungen) — sie werden nicht angefasst, nur die Buckets auf Ziele gelegt.
4. **Fehlende Buckets in der Zuordnungsdatei sind ein Fehler, keine stille
   Erweiterung** — die Datei soll sichtbar machen, was noch nicht zugeordnet ist.

## Offen für die nächste Runde

* **N6e** — Event-Abgleich (Datums-Block gegen bestehende Event-Ordner; Muster
  `Jahr + Ort`, `Jahr_Monat + Ereignis`, `Jahr + Person`) → **Vorschlag** statt
  Neubau, Trefferquote an einer Stichprobe messen.
* **N7** — Trockenlauf des Sortierens (`--trocken`) mit Zielstruktur
  `Agent/Fotos/<Jahr>/<Kategorie>/<Event>`, Rückfallordner für Anlässe ohne
  Thema, jede Bewegung ins Manifest.
