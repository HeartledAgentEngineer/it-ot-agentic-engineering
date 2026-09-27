# N7 — Trockenlauf des Sortierens (`foto_sortieren.py`)

**Datum:** 27.09.2026 · **Plan:** `docs/plan-nachtlauf-2026-09-26.md`, Schritt N7 ·
**Feinauftrag:** `docs/auftrag-n7-sortieren-trockenlauf.md`

## Was gebaut wurde

`tools/foto_sortierung/foto_sortieren.py` (1.149 Zeilen) baut aus dem fertigen
Sortierschlüssel **einen Plan**: welche Ordner unter
`Agent/Fotos/<Jahr>/<Kategorie>/<Event>` neu entstehen und welche Datei wohin
zieht. Tests: `backend/tests/test_foto_sortieren.py` (1.086 Zeilen,
**119 Testfunktionen**, alles offline mit `tmp_path`, kein Netz).

Der Trockenlauf **schreibt nichts**: keine schreibende pCloud-Operation, kein
Manifest-Eintrag, kein Download. Ein Test belegt, dass im Repo kein Ausgabeziel
akzeptiert wird, und eine Quelltext-Prüfung belegt, dass es **keine**
Löschfunktion (`deletefile`, `deletefolder`, `os.remove`, `os.unlink`,
`shutil.rmtree`) und **kein** `trocken=False` gibt.

## Regeln (Kurzform)

1. Zeilen werden über `thema_quelle` zu Anlässen gebündelt (deterministisch);
   Zeilen ohne Anlass-ID werden gezählt und übersprungen.
2. Zeilen mit gefüllter Spalte `doppelung` werden **nicht** eingeplant (nie
   gelöscht) — die Zählung ist aufgeschlüsselt (siehe Zahlen).
3. Zielkategorie aus dem Thema (Thema → Bucket → echter Ordner). Fehlt die
   Kategorie im Bestand oder ist sie nicht gebunden, wird der Rückfallordner
   geplant — **Neubau statt Abbruch**.
4. Anlass ohne Thema → Event-Ebene `Ohne-Thema` (Auflage aus N6b). Kein Abbruch.
5. Event-Wahl: Vorschlag aus `event_abgleich.vorschlag_fuer` wird **nur** bei
   `sicher: True` verwendet (gleiches Jahr allein ist **kein** Vorschlag); sonst
   ein neuer Name `"<Datum> <Thema>"`, bei Namensgleichheit deterministisch mit
   Anlass-Zusatz in Klammern.
6. Jahr aus dem Anlass, sonst aus dem Datum, sonst gezählt als `ohne_jahr`.
7. Ordnerkette wird je Pfadteil **einmal** geplant (kein doppeltes
   `createfolder`), vorhandene Teile als `vorhanden`.
8. Züge deterministisch sortiert (Jahr, Kategorie, Event, Dateiname).

## Zahlen (echter Trockenlauf, nur lesend, 27.09.2026)

* **9.430 Zeilen** · **2.127 Anlässe** · **7.616 Züge** (alle mit Dateikennung)
* Doppelungen: **1.534** in der CSV — davon **866** in Zeilen ohne Anlass-ID
  (ohnehin übersprungen) und **668** in geplanten Anlässen übersprungen
* **1.146 Zeilen ohne Anlass-ID** übersprungen (kein Datum im Namen → kein
  Anlass; 1.011 davon aus dem Wurzelordner eines zweiten Geräts)
* 0 Anlässe ohne Thema · 0 Anlässe ohne Jahr
* Ordner: **2.108 neu**, **82 vorhanden**; Events: **2.088 neu**,
  **39 wiederverwendet** (deckt sich mit den 39 sicheren Vorschlägen aus N6e)
* **11 Kategorien** werden belegt · je Jahr:
  2014: 1 · 2016: 1 · 2017: 1 · 2019: 27 · 2020: 36 · 2021: 95 · 2022: 408 ·
  2023: 447 · 2024: 430 · 2025: 380 · 2026: 301
* Plan: `~/foto_sortierung/sortierplan.json` (außerhalb des Repos)

## Prüfung

* **Prüfbefehl selbst gefahren:** `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **879 passed, Exit 0** (Baseline vor diesem Schritt 760).
* **Prüfer (`openai/gpt-5.6-luna`, andere Modellfamilie), zwei Runden:**
  * **Runde 1: NICHT BESTANDEN** — berechtigt: die Konsole nannte nur `668`
    Doppelungen, obwohl die CSV **1.534** gefüllte `doppelung`-Felder hat
    (irreführend, weil 866 davon in Zeilen ohne Anlass-ID liegen). Zweiter,
    kleinerer Punkt: eine wirkungslose Assertion (`… or True`) in den Tests.
  * **Runde 2: BESTANDEN, „Abweichungen: keine."** Der Prüfer hat alle Zahlen
    unabhängig gegen die CSV nachgerechnet (9.430 / 8.284 / 1.146 / 1.534 / 866 /
    668 / 7.616, Invariante `9.430 − 1.146 − 668 = 7.616`), den Prüfbefehl selbst
    gefahren (879/Exit 0), die Aufschlüsselung als getestet bestätigt, die
    Verbotsliste geprüft und den Datenschutzvergleich gefahren.

## Schutz (belegt)

* `~/foto_sortierung/manifest.jsonl` **nicht vorhanden** (0 Einträge) — der
  Trockenlauf bucht nichts.
* md5 der Eingaben unverändert, u. a. Original-Sortierschlüssel
  `70642d2988b6e38ff417561ccf870ba8`; nur gelesen, nichts verschoben, nichts
  gelöscht; pCloud-Aufrufe ausschließlich `listfolder` (7 Quellordner).
* Keine echten Bestandsnamen in den Repo-Dateien (Prüfer-Scan; Ausnahmen sind
  blanke Kalenderjahre und die generischen Bucket-Namen aus N6d).

## Offene Punkte für N8 (echter Lauf)

* **1.146 Dateien ohne Datum im Namen** haben keinen Anlass und bleiben liegen
  (12,2 % der Zeilen). Vorschlag: eigene Ablage (z. B. `Ohne-Datum` je Kategorie)
  erst nach Sebastians Blick — nicht Teil von N7.
* Der abgelehnte Anlass `2022-09-05_Anlass-02` (403 `PROHIBITED_CONTENT`) hat
  weiterhin kein Thema → landet über den Rückfall auf `Sonstiges`/`Ohne-Thema`.
