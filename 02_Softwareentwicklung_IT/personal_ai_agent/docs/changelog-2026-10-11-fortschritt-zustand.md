# Fortschritts-Anzeige: Zustand wird gemessen, nicht behauptet (11.10.2026)

## Anlass

Das Fortschritts-Brett (`werkzeuge/fortschritt/`) ist das Fenster, das Sebastian
waehrend des Nachtlaufs ansieht. Nach dem Ende der zwei grossen Laeufe zeigte es
sie unveraendert unter **„Laufende Arbeiten"**:

- `Bildbeschreibung reich`: 17.428 von 17.580 (99,1 %) — der Lauf war am
  10.10. um 10:51:56 gestorben (152 Zeilen nie geschrieben), der Balken stand
  14 h spaeter noch genau so da.
- `Gesichtserkennung Papas Fotos`: 6.336 von 6.336 (100,0 %) — fertig, wurde
  aber weiter als „laufend" gefuehrt.

Kein einziger Foto-Prozess lief mehr (gemessen: nur die zwei
Hermes-Prozesse). Die Anzeige behauptete also Arbeit, die es nicht gab.

## Was geaendert wurde

`werkzeuge/fortschritt/fortschritt.py`:

1. **Neue reine Funktion `lage_bestimmen(fertig, gesamt, alter_minuten,
   ruhe_minuten)`** — leitet den Zustand aus Messwerten ab:
   - `fertig`, sobald das Ziel erreicht ist (`fertig >= gesamt`),
   - sonst `angehalten`, wenn die Ergebnisdatei laenger als `RUHE_MINUTEN`
     (Voreinstellung 120 Minuten) unveraendert ist,
   - sonst `laeuft`.
2. **`_alter_minuten(pfad)`** misst das Alter der Ergebnisdatei; `messe_jsonl`
   traegt es als `stand_minuten` mit (None, wenn nicht messbar), damit die
   Anzeige den Zustand begruenden kann statt ihn zu raten.
3. **`messe_laufende_arbeiten(arbeiten=None)`** traegt je Arbeit `lage` und
   `stand_minuten` mit; die Arbeitsliste ist jetzt als Parameter
   uebergebbar (testbar, ohne die echten Pfade zu beruehren).
4. **Terminal und HTML trennen in zwei Abschnitte**: „Laufende Arbeiten"
   (nur `lage == laeuft`) und „Abgeschlossen oder angehalten" (alles andere,
   mit einer Zustandszeile je Arbeit, z. B. „angehalten – keine neue Zeile
   seit rund 14,7 h"). Der ruhende Balken wird gedaempft gezeichnet
   (`fuell-ruhe`), damit er nicht wie ein laufender aussieht.

Der Zustand wird **gemessen, nie behauptet**: keine Prozessabfrage, keine
Netzzugriffe, keine neuen Abhaengigkeiten. Fehlt die Datei oder ist das Alter
nicht messbar, bleibt der bisherige Weg (0 Prozent mit Hinweis).

## Belege

- **Testdatei `backend/tests/test_fortschritt_laufend.py`: 17 passed** (5 neue
  Tests: Ziel erreicht vor Ruhe; Grenze `RUHE_MINUTEN` = noch laufend, +1 Minute
  = angehalten; frisch/kein Messwert = laeuft; `messe_laufende_arbeiten`
  traegt den Zustand samt `stand_minuten`; Anzeige trennt die zwei Abschnitte in
  Terminal UND HTML, `fuell-ruhe`/`lauf-zustand` vorhanden, weiter ohne
  Fremdbibliotheken).
- **Lauf am echten Bestand** (`python werkzeuge/fortschritt/fortschritt.py
  --terminal`): kein Abschnitt „Laufende Arbeiten" mehr; beide Arbeiten stehen
  unter „Abgeschlossen oder angehalten" — Gesichtserkennung „Ziel erreicht",
  reiche Bildbeschreibung „angehalten - keine neue Zeile seit rund 14,7 h".
- **Pruefbefehl des Projekts**: `cd backend && .venv/Scripts/python -m pytest
  tests/ -q` → Exit 0 (Zahlen im Commit).

## Nebenbei richtiggestellt

Der Hinweis unter der Anzeige nannte `bild_index.db` mit **25.352 Vektoren** —
das war der Stand vor dem Schliessen der 889-Luecke. Gemessen sind es jetzt
**26.241 Bilder, alle mit Vektor** (`bestand_pruefen.py`, Exit 0). Der Hinweis
in `werkzeuge/fortschritt/status.json` ist entsprechend berichtigt und nennt
den Zustand der zwei Laeufe.

## Nicht angefasst

Keine Loeschung, keine Bild- oder Gesichtsdaten an fremde Modelle, kein Bild-
oder Netzdienst, keine Handy-Eingriffe. Fremde Aenderungen im Arbeitsbaum
(typeFREE, AGENTS.md, docs/experimente, Rechercheseiten, `status.json`-
Zaehlerteil, `pcloud_agent_schreiber.py`) blieben unangetastet; committet wurden
nur die eigenen Pfade.
