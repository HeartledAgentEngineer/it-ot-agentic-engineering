# Changelog 29.09.2026 — N27d: Personen-Andockung (Verknüpfungsschicht, Schritt 4 von 5)

**Auftrag:** `docs/auftrag-n27d-personen-andockung.md` (Planer: Hauptagent;
Ausführer: Hermes-Subagent `deepseek-v4.1-flash`; Prüfer: `openai/gpt-5.6-luna`,
andere Modellfamilie). **Codex war gesperrt** — live geprüft:
„You've hit your usage limit … try again at Oct 15th, 2026 9:32 PM".

## Was gebaut wurde

Neu `tools/foto_sortierung/personen_andocken.py` (**1.136 Zeilen**) und
`backend/tests/test_personen_andockung.py` (**1.258 Zeilen, 144 Testfunktionen**,
alles offline mit `tmp_path` und erfundenen Daten).

Das Werkzeug führt die Personenstufe mit den drei bestehenden Andockungen
zusammen:

* Ereignis-Knoten (`ereignisse.jsonl`) → welcher Anlass welche Bilder hat,
* Gesichts-Cluster (`personen_cluster.lauf_rechnen`, Produktionsverfahren
  „vollstaendig", Schwelle 0,45, Altbestand aus `personen_n9f/kennungen.json`)
  → welche `Person_00x` auf welchem Bild steht,
* Chat-Andockung (`chat_andockung.jsonl`) → welche Chat-/Kontakt-Namen im
  Fenster des Anlasses vorkommen.

Ergebnis sind zwei Dateien **außerhalb des Repos**:

* `~/foto_sortierung/personen_andockung.jsonl` — je Anlass die Personen
  (Kennung, Bildzahl, Gesichtszahl, bestätigt/Name),
* `~/foto_sortierung/personen_vorschlaege.json` — je Person eine Übersicht mit
  Datumsspanne, Anlässen und den stärksten **Namensvorschlägen**.

**Kernregel: das Werkzeug schlägt vor, es benennt nicht.** `vorschlag` und
`name` sind getrennte Felder; `bestaetigung_anwenden` liest einen Namen
**ausschließlich** aus `~/foto_sortierung/personen_bestaetigt.json`, die der
Nutzer pflegt. Ein Vorschlag kann sich nicht selbst bestätigen.

## Prüfbefehl (selbst gefahren)

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
→ 2558 passed, 3 warnings, Exit 0  (226 s)
```

Baseline vor dem Schritt (frisch gezählt): **2.414**, danach **2.558** — genau
**+144** = die neuen Testfunktionen. Die Zahl wächst weiter durch fremde
Parallelarbeit im selben Arbeitsbaum (der zweite Agent committet dort
`tools/agentbus/`, `docs/experimente/live_zahlen.*`).

## Live-Läufe (echte Dateien, alles nur lesend)

Trockenlauf (`--trocken`, Standard) — Sollwerte der Vormessung des Planers und
Ist-Werte des Laufs, **Zeile für Zeile identisch**:

| Größe | Soll | Ist |
|---|---|---|
| Vektorzeilen gelesen | 151 | **151** (0 defekt) |
| Bilder-Arten | `gruppe 41 · leer 64 · menge 11 · unklar 35` | identisch |
| Personen (Gruppen) | 12 (2 neu, 10 wiederverwendet) | identisch |
| Gruppengrößen | `11, 10, 10, 5, 4, 4, 4, 4, 4, 3, 3, 3` | identisch |
| Personen ohne Anlass-Zuordnung | 0 | **0** (Bilder ohne Anlass: 0) |
| Anlässe mit ≥ 1 Person | 5 | **5** |
| Personen mit Kandidatennamen | 12 von 12 | **12 von 12** |
| verschiedene Kandidatennamen | 34 | **34** |
| Kandidaten je Person (größte zuerst) | `24, 19, 12, 12, 10, 10, 10, 10, 8, 8, 8, 8` | identisch |
| Namen bestätigt / Namen in der Ausgabe | 0 | **0 / 0** |

Zwei Schreibläufe mit festem `--stand` in einen **frischen** Ordner außerhalb des
Repos: **byte-gleich**, keine `.tmp`-Reste.

* `knoten.jsonl` — **2.833 B**, sha256 `de840a885fd7af0e833d59d887374a2296910734b1f040a32adc9abb92c60f37`, 5 Zeilen
* `vorschlaege.json` — **7.454 B**, sha256 `06583b77aede8e5f58a1f63a99bd9cf39fbec8c12ebf7e9c5e623ffa6a9d21fd`, 12 Personen

Die Hashes des Ausführers wurden vom Planer **selbst nachgefahren** (identisch).

Weitere Belege:

* **Repo-Ziel** mit `--schreiben` → deutsche Meldung, **Exit 2**, keine Datei
  (`docs/verbot.jsonl` existiert nicht).
* **Keine Namen ohne Bestätigung:** 0 Treffer im Feld `name`, 0 Nummern-Masken
  (`***`), keine Ziffernfolge ≥ 7 Zeichen außer Datumsangaben. Mit einer
  Probe-Bestätigung (erfundener Name für `Person_001`) trägt **genau diese**
  Person einen Namen, alle anderen bleiben `null`.
* **Eingaben unverändert** (sha256 vor/nach gleich): `ereignisse.jsonl`
  `344082a2…`, `chat_andockung.jsonl` `cf2e0c19…`,
  `personen_vektoren_n9e.jsonl` `bfb00374…`, `…_burst.jsonl` `53724eeb…`,
  `personen_n9f/kennungen.json` `e630a8b1…`; `manifest.jsonl` **existiert nicht**
  (nichts gebucht, nichts verschoben).

## Der ehrliche Fund dieser Runde (offengelegt)

Die Vormessung des Planers zählte die `beteiligte` mit, filterte sie aber auf
**Zeichenketten** — in `chat_andockung.jsonl` sind sie jedoch **Objekte**
(`{"name": …, "nummer_maske": …}`). Damit floss faktisch nur `chat_name` in die
Zahl **34** ein. Nachgemessen (dieselben fünf Anlässe): mit `chat_name` **und**
`beteiligte` sind es **44** verschiedene Namen (10 nur aus `beteiligte`).

Der Ausführer hat das erkannt und gemeldet (genau die Regel „Abweichung ist ein
Befund" aus dem Auftrag). **Entscheidung des Planers:** ausgeliefert wird
`chat_name` als Namensquelle, `beteiligte` nur als Rückfall, wenn `chat_name`
leer ist. Grund: bei Gruppen ist `chat_name` der **Gruppenname** — als „Person"
wäre er falsch, und die Teilnehmerliste einer Gruppe ist für „wer ist auf dem
Foto" ein schwacher Beleg. Die reichere Regel (**Einzelchat → `chat_name`,
Gruppe → Teilnehmer**) ist als Folgekandidat benannt, aber **nicht** in diesem
Schritt gebaut (ein Schritt pro Runde). Der Nachtrag steht im Auftrag und im
Modulkopf.

## Was dieser Schritt nicht liefert (bewusst offen)

* **Massenlauf der Gesichter über alle 9.430 Fotos.** Basis sind hier die
  vorhandenen Vektoren (151 Bilder). Gemessener Anker: 192 Bilder = 1.086,6 s →
  für den vollen Bestand eine Größenordnung von **~15 Stunden** Rechenzeit
  (kein Netz, kein Guthaben). Das braucht eine eigene Entscheidung und eine
  eigene Messung — als **N27f** vorgemerkt, nicht hier gebaut.
* **Im Chat genannte Namen** (aus dem Nachrichtentext) sind **nicht** enthalten:
  `chat_andockung.jsonl` trägt bewusst keinen Text, und dieser Schritt liest
  keinen. Der Vorschlag stützt sich auf Chat- und Kontaktnamen im Fenster.
* Die **Bestätigung** selbst ist Handarbeit des Nutzers
  (`personen_bestaetigt.json`) — ohne sie bleibt jede Kennung unbenannt.

## Doku-Stand

Auftrag `docs/auftrag-n27d-personen-andockung.md`, dieser Changelog,
`docs/plan-nachtlauf-2026-09-26.md` (Schritt-Zeile N27d + Journal),
Projekt-`CLAUDE.md` (Protokollzeile) — „code + docs" in einem Commit.
