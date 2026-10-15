# Lernt die Erkennung mit? Wo eine Gesichts-Korrektur heute nachführt (15.10.2026)

**Anlass.** Der Auftrag `.hermes/plans/2026-10-15_gesichter-im-detailbild.md` (Sebastian,
15.10.2026) verlangt vor dem Bau „belegt, nicht vermutet". Abgearbeitet waren bereits Abschnitt 1
(Erkennungseinstellungen, Kästchenzahl), Abschnitt 3 (rechnet das Handy Vektoren selbst) und
Abschnitt 4.1 (der Hinweis „als Referenz dieser Person" — zwei Speicherwege, kein Widerspruch).
**Offen war Abschnitt 4.2:**

> „Wunsch Nr. 8 ‚Erkennung lernt mit' ist damit verbunden: Wenn Korrekturen den Mittelpunkt
> nachführen sollen (`Issue #5`), dann ist genau dieses Verrücken-und-Speichern der Ort, an dem
> das passieren muss."

Gefragt ist also nicht „gibt es einen Referenzvektor" (4.1), sondern **wo im Bestand ein
Mittelpunkt nachgeführt wird** — und ob der Referenzvektor dafür reicht.

**Neues Werkzeug** `tools/foto_sortierung/gesicht_lernt_mit_wege_messen.py` — nur lesen: Code als
Text, lokale Zählung; kein Bild, kein Netz, kein Modell, kein Schreibzugriff, kein Prozessaufruf,
keine Personennamen im Bericht. Testdatei
`backend/tests/test_gesicht_lernt_mit_wege_messen.py` (14 Tests).

## 1. Der Referenzvektor (Gerät, Gesichter-Weg) — führt nach

| Was | Stelle |
|---|---|
| Dienst der Quiz-Antwort | `backend/app/services/gesicht_quiz.py:667` (`beantworte_runde`) |
| Einbettung des bestätigten (verschobenen) Rahmens | `backend/app/services/gesicht_quiz.py:713` (`face_service.embedding_fuer_bbox`) |
| neue Referenz mit `embedding` + Rahmen | `backend/app/services/gesicht_quiz.py:737` |
| Schwelle, ab der die Referenz angehängt wird | `backend/app/services/gesicht_quiz.py:765` (`zu_alt > 0.05`) |
| Speichern der Referenzliste | `backend/app/services/gesicht_quiz.py:768` |
| Ablageort des Referenzspeichers | `backend/app/services/gesichter_service.py:33` (`gesichter_katalog.json`) |
| Schreibfunktion / atomar | `backend/app/services/gesichter_service.py:158` / `:72` (`os.replace`) |

Der verschobene Rahmen wird **eingebettet** und als Referenz **angehängt** — aber nur, wenn er sich
von den bestehenden Referenzen um mehr als 0,05 (Cosinus-Distanz) unterscheidet. Ein Verrücken um
wenige Pixel ändert die Referenz danach **nicht**.

## 2. Der Gruppenmittelpunkt (PC, nächster Gruppenlauf) — führt nur dort nach

| Was | Stelle |
|---|---|
| feste Einzelzuordnung (Dienst) | `backend/app/services/gruppen_quiz.py:1125` (`zuordnen`) |
| schreibt sie nach `personen_vorgaben.json` | `backend/app/services/gruppen_quiz.py:1179` |
| atomares Schreiben der Vorgaben | `backend/app/services/gruppen_quiz.py:241` |
| Auflösen der festen Zuordnungen (PC) | `tools/foto_sortierung/personen_gruppieren.py:274` |
| der PC-Lauf liest sie (v2) | `tools/foto_sortierung/personen_gruppieren.py:1194` |
| daraus werden Vorbilder | `tools/foto_sortierung/personen_gruppieren.py:1219` |
| und fixierte Stellen | `tools/foto_sortierung/personen_gruppieren.py:1110` |
| Vorbild-Gruppen starten mit ihrem Mittelpunkt | `tools/foto_sortierung/personen_gruppieren.py:1099` |
| der eigentliche Gruppenlauf | `tools/foto_sortierung/personen_gruppieren.py:1242` (`gruppieren_v2`) |

Ein Mittelpunkt entsteht damit **ausschließlich** im PC-Lauf, und er kennt eine Korrektur nur, wenn
sie als **feste Einzelzuordnung** in `personen_vorgaben.json` steht.

## 3. Die Lücke dazwischen — gemessen, nicht behauptet (wörtlich aus dem Lauf)

```
    Gemessen: der PC-Gruppenlauf (personen_gruppieren.py) liest gesichter_katalog.json GENAU 0x —
    die Geraete-Referenzen kommen in der Gruppenbildung nicht vor.
    Gemessen: 0 Mittelpunkt-Stellen im Geraete-Code (gesicht_quiz.py: 0, gruppen_quiz.py: 0) —
    das Handy rechnet keinen Gruppenmittelpunkt nach.
    Gegenprobe: derselbe Suchbegriff findet im PC-Werkzeug 56 Stellen — der Begriff ist also
    nicht einfach unauffindbar.
```

Damit stehen drei Sätze fest, jeder mit Beleg:

1. Der Detailbild-Editor geht über den **Gesichter-Weg** (Abschnitt 4.1, gemessen) — er führt den
   **Referenzvektor** nach.
2. Den **Gruppenmittelpunkt** führt nur der PC-Gruppenlauf nach, und nur aus den **festen
   Einzelzuordnungen**.
3. Verbunden sind die beiden Wege **nicht**: kein Geräte-Code rechnet einen Mittelpunkt, und der
   PC-Gruppenlauf liest die Geräte-Referenzen nie.

## 4. Zahlen am echten Bestand (nur Zahlen, keine Namen)

```
  personen_vorgaben.json: zugeordnet: 0 · ausgeschlossen: 40 · gleich: 14 · verschieden: 5 · Summe 59
    Davon feste Einzelzuordnungen (zugeordnet): 0 — in dieser Kopie fuehrt heute keine Korrektur einen Mittelpunkt nach.
  personen_bestaetigt.json: dict · Summe der Listen 20
  personen_gruppen/gesicht_zuordnung.jsonl: 50.282 Zeilen (jede Zeile ein Gesicht mit Gruppe)
  personen_gruppen/kennungen.json: 1.367 Kennungen
  Ehrliche Grenze: gesichter_katalog.json liegt am PC nicht vor (Referenzspeicher liegt am Geraet) — Zahl der Referenzen NICHT zaehlbar am PC.
```

Kommentar zu den Zahlen:

* `zugeordnet: 0` ist **kein Nullbefund über die Arbeit**, sondern über diese **Kopie**: die Datei
  liegt am PC aus der Gerätesicherung (08.10.2026 23:51) und trägt die drei Regelarten, aber keine
  einzige feste Einzelzuordnung. Ob am Gerät welche stehen, ist am PC **nicht zählbar**.
* Die 50.282 Gesichtszeilen und 1.367 Kennungen sind der Bestand, auf dem ein Mittelpunkt heute
  gebildet würde.

## 5. Folge für den Bau (der Auftrag verlangt das ausdrücklich)

Soll „Verrücken und Speichern" den **Mittelpunkt** nachführen (Wunsch Nr. 8, `Issue #5`), reicht der
Referenzvektor **nicht**. Die Korrektur muss zusätzlich den Weg
`POST /api/gruppen/zuordnen` → `personen_vorgaben.json` (`zugeordnet`) nehmen; erst ein **PC-Lauf**
macht daraus ein Vorbild und damit einen neuen Mittelpunkt. Wer den Knopf baut, muss deshalb beide
Wirkungen nennen und darf die Nachführung nicht als sofort versprechen.

Die Referenz-Schwelle 0,05 (`gesicht_quiz.py:765`) gehört ebenfalls in den Plan: ein kleines
Verrücken ändert die Referenz absichtlich nicht.

## Belege

* Werkzeug `tools/foto_sortierung/gesicht_lernt_mit_wege_messen.py` (nur lesen), Testdatei
  `backend/tests/test_gesicht_lernt_mit_wege_messen.py` — **14 passed** (gegen den echten Code, mit
  Gegenprobe: ein echter Mittelpunkt-Treffer und ein `gesichter_katalog`-Treffer kippen das Urteil;
  fehlende und kaputte Dateien werden gemeldet statt geworfen; kein Personenname im Bericht; die
  Nur-Lese-Zusage wird am Quelltext geprüft).
* Messlauf am echten Bestand: **Exit 0**, Zeilen wörtlich oben und in Abschnitt 3.
* Kein Bild geöffnet, kein Netz, kein Modell, keine Modellkosten, kein Schreibzugriff.
