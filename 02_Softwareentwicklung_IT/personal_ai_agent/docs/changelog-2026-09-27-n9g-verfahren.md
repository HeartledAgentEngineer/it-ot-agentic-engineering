# N9g — Produktions-Verfahren des Gesichts-Clusterings: vollständige Verknüpfung

**Datum:** 27.09.2026 · **Schritt:** N9g (Plan `docs/plan-nachtlauf-2026-09-26.md`)
**Rollen:** Planer + Messung: Hauptagent · Ausführer (Code): Hermes-Subagent
`deepseek-v4.1-flash`, 0,024 USD · Prüfer (Code): `openai/gpt-5.6-luna` (andere
Modellfamilie), 1. Runde **BESTANDEN, 0 Abweichungen**.
**Codex:** live geprüft und weiter gesperrt („try again at Oct 15th, 2026 9:32 PM").

## Warum

N9f hat gemessen, dass das Bestandsverfahren **dichte** (DBSCAN-artig) bei
Schwelle 0,45 eine Gruppe mit Durchmesser **0,9032 = 2 × Schwelle** bildet — die
Verkettung ist also strukturell unbegrenzt. Die **vollständige Verknüpfung**
(Complete-Linkage) hat die Invariante *Durchmesser jeder Gruppe ≤ Schwelle*.
N9f-Messung galt aber nur für **92 Bilder** (8 Mengen-Anlässe). Deshalb zuerst
**breiter messen**, dann umstellen.

## Teil 1 — breitere Stichprobe (gemessen, nicht geschätzt)

Quelle: `sortierplan.json` + `themen.jsonl`; Auswahl **über die Jahre gestreut**
(je Jahr bis 6 Mengen-Anlässe), Erkennung **nur lesend**, Originale nur im
Arbeitsspeicher. Belege außerhalb des Repos: `~/foto_sortierung/n9g_messung.log`,
`…/n9g_messung.json`, Vektordatei `…/personen_vektoren_n9g.jsonl` (188 Zeilen),
Messskript `…/n9g_messung.py`.

* Anlässe mit Mengen-Thema im Bestand: **443**; ohne: **1.455**
* Auswahl: **192 Bilder** = **40 Mengen-Anlässe (152 Bilder)** + **40 Kontrollbilder**
  aus 40 verschiedenen Anlässen (N9f: 92 Bilder aus 8 Anlässen)
* Erkannt: **188 Bilder heruntergeladen**, **142 mit Gesicht**, **907 Gesichter**,
  **1.086,6 s**, **9 Fehlerzeilen** (4 × pCloud-Zeitüberschreitung (ReadTimeout),
  5 × „Bild nicht dekodierbar"), **0 Wächter-Auslösungen**
* Bildarten (Produktionsregel): `gruppe 74 · leer 41 · menge 20 · unklar 48`
  → **341 geclusterte Gesichter**

### Bodenwahrheit (hart, ohne Personen-Labels)

**210** Bild-Paare erkennbarer Gesichter (Flächenanteil ≥ 0,5 %; zwei *erkennbare*
Gesichter im selben Bild sind zwei Personen). Paar-Distanzen **min 0,4925 /
Median 0,8708 / max 1,1422** — **0 von 210 unter 0,45**.

### Ergebnis über 8 Schwellen (0,10–0,45) × 2 Mindestgrößen (2 und 3) = 16 Kombinationen je Verfahren

| Verfahren | verschmolzene Bodenwahrheits-Paare | Durchmesser max / Schwelle | > Schwelle? |
|---|---|---|---|
| **vollstaendig** | **0 von 210** (in allen 16 Kombinationen) | **0,99908** (knappste Stelle) | **nie** |
| dichte | **2 von 210** bei 0,45 **und** bei 0,40 (Quote 1,0 %) | **2,00234** (= 2 × Schwelle) | ab 0,45 abwärts bis 0,20 immer „ja" |
| mittelpunkt | **11 von 210** bei 0,45 (5,2 %), je 1 bei 0,40/0,35 | **2,1208** (0,6362 bei Schwelle 0,30); bei 0,45: 2,0533 (0,9240 absolut) | fast immer „ja" |

Bei **Schwelle 0,45** (Produktionseinstellung, Mindestgröße 3):

| Verfahren | Gruppen | größte | Gesichter in Gruppen | verschmolzen | Durchmesser max |
|---|---|---|---|---|---|
| dichte | 10 | 27 | 89 | **2** | 0,7782 |
| **vollstaendig** | 13 | 7 | 66 | **0** | **0,4395** |
| mittelpunkt | 9 | 39 | 86 | 11 | 0,9240 |

**Der neue Befund:** auf der breiteren Stichprobe verschmilzt das dichte Verfahren
**erstmals zwei erkennbare Gesichter** (bild-interne Paare fremder Personen) zu
einer Gruppe — bei 0,45 und bei 0,40, in beiden Mindestgrößen. N9f hatte auf 92
Bildern „0 von 131" gemessen; das war kein Gegenbeweis, sondern eine zu kleine
Stichprobe. Von **48** Verfahren-Schwellen-Kombinationen entfallen die **34**
verschmolzenen Paare zur Hälfte auf dichte (4 je Mindestgröße) und zur Hälfte auf
mittelpunkt (13 je Mindestgröße) — **vollstaendig trägt 0 bei**.

## Teil 2 — Verfahren im Produktionsmodul umgestellt (Code)

`tools/foto_sortierung/personen_cluster.py`

* neu: `VERFAHREN_DICHTE = "dichte"`, `VERFAHREN_VOLLSTAENDIG = "vollstaendig"`,
  `VERFAHREN`, **`CLUSTER_VERFAHREN = VERFAHREN_VOLLSTAENDIG`** (Produktionsstandard)
* neu: `vollstaendig_clustern(eintraege, schwelle, min_groesse)` — Complete-Linkage,
  nur `numpy`, deterministisch, Rauschen unter der Mindestgröße wird verworfen;
  Docstring nennt die Invariante
* `vektoren_clustern(..., verfahren=None)`: Standard = `CLUSTER_VERFAHREN`;
  `"dichte"` läuft **unverändert** (Kernpunkt-/Expansionslogik nicht angefasst);
  **unbekanntes Verfahren → deutsche `ValueError`**, kein stiller Rückfall
* der Produktionsaufruf in `referenzseiten_bauen` bleibt **ohne** `verfahren` →
  der neue Standard greift dort automatisch
* CLI: `--verfahren` (Standard `CLUSTER_VERFAHREN`), Ausgabe nennt das Verfahren

`tools/foto_sortierung/personen_schwelle.py`: der Aufruf ist auf
`verfahren="dichte"` **festgenagelt** — dieses Messwerkzeug muss weiter genau das
Bestandsverfahren beschreiben.

`tools/foto_sortierung/personen_verkettung.py`: `vollstaendig_clustern` behält
die Signatur und **delegiert** an `personen_cluster.vollstaendig_clustern`
(keine Doppelimplementierung); `gruppen_bilden` pinnt den `dichte`-Pfad
ausdrücklich. Kein Ringschluss (`personen_verkettung` importiert
`personen_cluster`, nicht umgekehrt).

## Prüfbefehl

`cd backend && .venv/Scripts/python -m pytest tests/ -q`
→ **1449 passed, 3 warnings, Exit 0** (vorher 1433; **+16 neue Testfunktionen** in
`backend/tests/test_personen_cluster.py`, 219 → 235). Zwei Testdateien zusätzlich
angepasst: `backend/tests/test_personen_verkettung.py` (drei Aufrufe der
Dichte-Baseline auf `verfahren="dichte"` festgelegt, Erwartungen unverändert).
Der Commit-Hook fährt dasselbe Tor beim Commit.

**Prüfer (`gpt-5.6-luna`, frische Sitzung, andere Modellfamilie): BESTANDEN,
„Abweichungen: keine."** Er hat selbst gefahren und nachgerechnet: Prüfbefehl
1449/Exit 0; Testfunktionen 219 → 235 (16 neue) bzw. 117 → 117; die
Durchmesser-Invariante über die Schwellen 0,10/0,20/0,30/0,45 und die Saatgüter
0/1/7/42/99; den Kettenfall (bei 0,25: dichte 0,72 gegen vollstaendig 0,20);
`ValueError` bei unbekanntem Verfahren; die unveränderte Kernlogik des
dichte-Zweigs im Diff gegen HEAD; die Delegation (gleiches Saatgut → gleiche
Gruppen); alle Schwellen wertgleich zu HEAD; Hygiene (keine Löschfunktion, keine
Netz-/pCloud-Aufrufe, keine neuen Abhängigkeiten, kein Ausgabeziel im Repo);
`git diff --stat` = **genau fünf** Dateien, die fremden `live_zahlen`-Dateien und
die zwei Recherche-HTML nicht enthalten.

**Prüfer Runde 2 (`gpt-5.6-luna`, Abnahme auf Commit `b88b41d`): NICHT BESTANDEN —
zwei berechtigte Abweichungen, beide korrigiert.**
(1) Die Tabelle nannte für `mittelpunkt` als **maximales** Verhältnis Durchmesser/Schwelle
`2,0533`; dieser Wert gilt nur bei Schwelle 0,45. Nachgerechnet aus der Messdatei ist der
Höchstwert **2,1208** (0,6362 bei Schwelle 0,30) — Zeile korrigiert.
(2) Die neu ergänzte Journal-Zeile enthielt den **Eigner-Namen**; ersetzt durch „dein Blick".
Alles andere hat der Prüfer bestätigt (Prüfbefehl 1449/Exit 0, genau sieben Dateien im
Commit, `0 0`, alle Messzahlen außer der einen, Doku deckt den Code, keine Bilder in den
Ausgaben).

## Entscheidung (statt Rückfrage)

**Produktion = vollständige Verknüpfung.** Begründung mit Zahlen: sie ist das
einzige der drei Verfahren mit der harten Invariante (Durchmesser ≤ Schwelle,
knappste Stelle 0,99908 × Schwelle) und mit **0 von 210** verschmolzenen
Bodenwahrheits-Paaren; das Bestandsverfahren verschmilzt nachweislich **2 von 210**
(verschiedene Personen im selben Bild in einer Gruppe) und reißt den Durchmesser
mit 2 × Schwelle. **Preis, ehrlich benannt:** bei 0,45 bleiben **66 statt 89**
Gesichtern in Gruppen (23 mehr im Rauschen, Gruppen 13 statt 10, größte 7 statt
27) — das ist der bewusste Tausch: *lieber eine Person in zwei unbenannten
Gruppen als zwei Personen in einer*. Schwellen selbst unverändert
(`CLUSTER_SCHWELLE 0,45`, `CLUSTER_MIN_NACHBAR 3`, `ANTEIL_MIN`, `ANTEIL_ERKENNBAR`,
`MENGE_ANZAHL`, `KATALOG_SCHWELLE`) — vom Prüfer als wertgleich bestätigt.

## Offen (nicht Teil dieses Schritts)

* Die 4 Zeitüberschreitungen beim Herunterladen wurden **nicht** wiederholt
  (192 ausgewählt, 188 erkannt) — die Stichprobe ist damit 188 Bilder groß.
* `_abstand_der_gueltigen` in `personen_verkettung.py` hat keinen Aufrufer mehr;
  Löschen war nicht Teil des Auftrags (nur der Planer entscheidet über Aufräumen).
* Der Personenweg läuft weiterhin nur auf einer Stichprobe des Bestands; die
  vollständige Verarbeitung ist ein eigener Schritt.

## Schutz

pCloud **nur lesend**; Originale **nur im Arbeitsspeicher**, **keine** Bilddatei
auf der Platte; **nichts gelöscht**; `manifest.jsonl` existiert nicht (keine
Buchung); alle Ausgaben außerhalb des Repos unter `~/foto_sortierung/`; keine
Schlüsselwerte, keine Namen Dritter. Die fremden `live_zahlen`-Dateien und die
zwei Recherche-HTML des zweiten Agenten blieben unberührt.
