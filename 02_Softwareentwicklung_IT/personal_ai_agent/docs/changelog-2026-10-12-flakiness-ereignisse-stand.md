# Zeitgrenzen-Flakiness gehärtet: `--stand` für die Ereignis-Knoten

Datum: 12.10.2026. Werkzeug: `tools/foto_sortierung/ereignisse_bauen.py`.
Test: `backend/tests/test_ereignisse_bauen.py`. Auftragsdoku:
`docs/auftrag-n27-ereignisknoten.md`.

## Der Anlass, belegt

Der Commit-Haken (erzwingt `pytest` vor jedem Commit) hat in diesem Nachtlauf
einen eigenen Commit **abgewiesen**:

```
FAILED tests/test_ereignisse_bauen.py::test_haupt_schreiben_ist_byte_gleich_wiederholbar
1 failed, 3971 passed, 2 skipped, 3 warnings in 260.62s
```

Gemessen statt vermutet: derselbe Test lief **isoliert 134 passed** (1,78 s) —
kein Bezug zur eigenen Änderung (dort ging es um `bestand_pruefen.py`). Die
Ursache ist eine **Zeitgrenze**, die schon am 29.09.2026 dokumentiert und
damals **bewusst nicht** angefasst wurde (Changelog
`changelog-2026-09-29-n28-beziehungen-antwortstufe.md`): das Werkzeug schreibt
`stand` aus `datetime.now().isoformat(timespec="seconds")`, und der Zeitstempel
steht in **jeder** Zeile. Fallen zwei Schreibvorgänge auf zwei Sekunden,
unterscheiden sich die Dateien — der Test prüfte also eine Eigenschaft, die von
der Uhr abhängt, statt zu messen, was das Werkzeug zusagt.

Kein `--no-verify`, keine Sperre von Hand gelöscht: kurz gewartet, erneut
committet — der Haken fuhr den Prüfbefehl unabhängig grün.

## Was geändert wurde

1. `--stand TEXT` als **Kommandozeilen-Option** (Standard: jetzt). Der Wert
   wurde schon immer als Funktionsparameter getragen (`ereignisse_bauen(plan,
   *, stand=...)`, für Tests) — auf der Konsole fehlte er, deshalb konnte kein
   Lauf und kein Test über `haupt([...])` den Zeitstempel fest vorgeben.
   Ein leerer/blanker Wert wird **nicht** stillschweigend zur Uhrzeit: die
   vorhandene Prüfung greift, es gibt Exit 2 und nichts wird geschrieben.
2. Der Test prüft jetzt die **zugesagte** Eigenschaft:
   - gleicher `--stand` zweimal → Dateien **byte-gleich** (Prüfsumme), und die
     Zeile trägt genau diesen Stand;
   - **ohne** `--stand` → zwei Läufe unterscheiden sich **ausschließlich** im
     Feld `stand` (das ist immer wahr, während Byte-Gleichheit ohne festen
     Stand Glückssache wäre).
3. Doku folgt dem Code: Modulkopf, `haupt`-Docstring und die Auftragsdoku
   `auftrag-n27-ereignisknoten.md` (Kommandozeile, Testliste, Prüfkriterium)
   nennen die Option und die Grenze.

## Belege

- `tests/test_ereignisse_bauen.py`: **134 → 136 Testfunktionen** (1 Test
  verschärft, 2 neue), Lauf der Datei **136 passed** (4,93 s).
- Prüfbefehl: siehe Commit (frisch und vollständig, Exit 0).
- Der geänderte Test war vorher in einem vollen Lauf rot und ist jetzt
  deterministisch: er hängt nicht mehr an der Uhr.

## Grenzen (ehrlich)

- Die Flakiness war **nicht** die Ursache des roten Hakens allein: rote Hakens
  können auch von fremder, gerade laufender Arbeit kommen (Journal 36). Hier
  war es nachweislich dieser Test.
- Der Test bleibt ein Test **dieses** Werkzeugs; andere zeitabhängige Tests
  wurden nicht gesucht und nicht angefasst.
