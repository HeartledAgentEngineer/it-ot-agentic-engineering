# N6b Stapel 1: Kontaktbögen + Themen für 2014–2021 (gemessen)

> **Datum:** 27.09.2026 · **Schritt:** N6b (Massenlauf, erster Stapel) aus
> `docs/plan-nachtlauf-2026-09-26.md` · **Rollen:** Planer = Hauptagent
> (Hermes), Ausführer = Werkzeuge `foto_themen.py` / `foto_themen_vision.py`
> (aus N4/N6, nur lesend bzw. nur außerhalb des Repos schreibend),
> Prüfer = `openai/gpt-5.6-luna` (fremde Modellfamilie).

## Was gemacht wurde

„Kleinster Stapel zuerst": die kleinsten Jahre des Bestands wurden **komplett**
durchgezogen — Kontaktbögen bauen (pCloud-Vorschaubilder) und je Anlass **ein**
Vision-Aufruf. Es wurden **nur lesende** pCloud-Aufrufe gemacht; geschrieben
wurde ausschließlich außerhalb des Repos unter `~/foto_sortierung/`.

| Jahr | Anlässe | Kacheln | Bögen | Themen | Fehler | Dauer Bögen | Dauer Themen |
|---|---|---|---|---|---|---|---|
| 2014 | 1 | 4 | 1 | 1 | 0 | 2,4 s | 3 s |
| 2016 | 1 | 2 | 1 | 1 | 0 | 2,2 s | 2 s |
| 2017 | 1 | 2 | 1 | 1 | 0 | 2,5 s | 3 s |
| 2019 | 27 | 90 | 27 | 27 | 0 | 8,0 s | 49 s |
| 2020 | 36 | 116 | 36 | 36 | 0 | 19,2 s | 79 s |
| 2021 | 95 | 296 | 95 | 95 | 0 | 54,6 s | 178 s |
| **Summe** | **161** | **510** | **161** | **161** | **0** | **1,5 min** | **5 min 14 s** |

Alle Läufe endeten mit **Exit 0** (Rückgabewert je Jahr im Protokoll
`~/foto_sortierung/n6b_boegen_stapel1.log` bzw. `…themen_stapel1.log` protokolliert).

## Gemessene Zahlen (keine Schätzung)

* Vorschaubilder: **510** geholt, 1.527.879 Bytes (2021) + 576.346 (2020) +
  441.240 (2019) + 29.642 Bytes (Einzeljahre).
* Vision: **438.072 Eingabe- / 26.082 Ausgabe-Tokens** für 161 Anlässe,
  **0,196610 USD** gesamt = **0,001221 USD je Anlass** (kleinste 0,000973,
  größte 0,004354 USD).
* Laufzeit je Anlass: Mittel **1,91 s**, größte 8,67 s (16-Kachel-Bogen).
* Kachel-Ebene: **510 Kacheln** in den Themen-JSONs, davon **0 als unbrauchbar**
  gekennzeichnet, **0 unvollständige** Bögen, **0 Fehlerzeilen**.
* Original-Sortierschlüssel unverändert: `md5 70642d2988b6e38ff417561ccf870ba8`.
  Geschrieben wurde nur die Kopie `~/foto_sortierung/sortierschluessel_themen.csv`.

## Kostenhochrechnung für den Rest (2.128 Anlässe gesamt)

Auf Basis der gemessenen **0,001221 USD je Anlass** (2.128 Anlässe):
`google/gemini-2.5-flash` **2,60 USD**, `google/gemini-2.5-flash-lite`
**0,72 USD**, `google/gemini-3.7-flash` **5,64 USD**. Preise am 27.09.2026 live
über `/api/v1/models` abgefragt (0,30/2,50 · 0,10/0,40 · 0,75/3,75 je 1 Mio).
**0,72 vs. 2,60 USD** ist der Grund, vor dem Restlauf die Qualität von
`flash-lite` am Katalog zu messen — der Vollauf kostet sonst das Dreifache ohne
belegten Gewinn.

## Befund, der den nächsten Schritt bestimmt

**155 verschiedene Themen bei 161 Anlässen = 96 % Einzelstücke.** Beispiele aus
dem echten Lauf: „Haus Garten" **und** „Haus und Garten"; „Sonnenuntergang
Stadtansicht", „Sonnenuntergang Meer", „Sonnenuntergang am See". Als
Ordnerstruktur (`Agent/Fotos/<Jahr>/<Thema>/`) ist das **untauglich** — jedes
Foto bekäme faktisch einen eigenen Ordner, und dasselbe Motiv läge zerstreut.

**Ursache im Code, nicht im Modell:** `prompt_bauen()` in
`tools/foto_sortierung/foto_themen_vision.py` (Zeile ~412) verlangt „2 bis 4
deutsche Woerter, die den Anlass benennen" — **ohne Wortschatz**. Ohne feste
Liste erfindet jedes Modell (gleich welches) bei jedem Aufruf neue Wörter.

**Konsequenz (Entscheidung, keine Rückfrage):** Vor dem Restlauf kommt **N6c —
Themen-Katalog**: eine feste, überschaubare Themenliste (Zielgröße 40–60
Einträge) und ein prompt, der **nur** aus dieser Liste wählen darf, plus eine
Zuordnung für die bereits gelaufenen 161 Anlässe (`--wiederholen`, Kosten
≈ 0,20 USD, gemessen). Erst danach der Massenlauf über die restlichen 1.967
Anlässe.

## Prüfbefehl und Abnahme

* **Prüfbefehl des Projekts** (selbst gefahren, vor dem Commit):
  `cd backend && .venv/Scripts/python.exe -m pytest tests/ -q` → **628 passed,
  Exit 0** (121 s). Unverändert gegenüber N6 — dieser Schritt hat **keinen**
  Projektcode geändert, nur ausgeführt und dokumentiert.
* **Prüfer** (`openai/gpt-5.6-luna`, fremde Modellfamilie): hat alle elf
  Prüfpunkte **selbst nachgerechnet** — Bögen und Themen-JSONs je Jahr,
  Zeilen/eindeutige Titel in `themen.jsonl`, Token- und Kostensummen,
  Themenvielfalt (155 von 161 = 96,27 %), die genannten Themenbeispiele, den
  md5 des Sortierschlüssels, die Kachel-Ebene, die `exit=0`-Zeilen beider
  Protokolle, die Code-Stelle `prompt_bauen()` und die Repo-Sauberkeit.
  Ergebnis: **„bestanden", 0 Abweichungen** („Nicht prüfbar: nichts").

## Was dieser Schritt NICHT getan hat

* **Nichts in die pCloud geschrieben**, nichts verschoben, nichts gelöscht.
* Kein Modellvergleich (flash-lite ist noch **nicht** getestet) — bewusst auf
  N6c verschoben, damit der Vergleich am Katalog stattfindet und nicht am
  freien Prompt.
* Keine Personen-Stufe (N9), kein Trockenlauf des Sortierens (N7).
