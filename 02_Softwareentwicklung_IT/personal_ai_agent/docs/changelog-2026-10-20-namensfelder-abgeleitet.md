# Namensfelder: Vorname und Nachname beim Lesen abgeleitet (Schritt 1 von 3)

20.10.2026, Hermes-Cron. Auftrag aus der laufenden Übergabe `personal_ai_agent`
(Sebastian, 20.10.2026): „Personenbuch mit Feldern Vorname / Nachname /
Spitzname (Datenmodell → erst kurz durchsprechen)." Die Entscheidungen liegen
vor; der Umsetzungsvorschlag steht in
`.hermes/plans/2026-10-20_personen-namensfelder.md` und verlangt dort
ausdrücklich eine **kurze Gegenprüfung vor dem Bau**.

## Die Gegenprüfung (frischer Kontext, vor dem Bau)

Ein unabhängiger Prüflauf (eigener Kontext, nur lesend) hat den Vorschlag gegen
den echten Code geprüft und kam auf **EINWAND mit neun belegten Befunden**. Zwei
davon waren hart:

1. **Datenverlust-Gefahr beim Zusammenführen:** `umbenennen()` führt zwei Profile
   zusammen und nimmt dabei nur `beziehung`, `notizen` und `kontakt` mit
   (`app/services/gruppen_quiz.py`, Zweig „zusammenfuehren"). Ein von Hand
   gesetztes `vorname`/`nachname`/`spitznamen` des alten Namens ginge verloren.
2. **Die Trennregeln hatten Gegenbeispiele:** ein Rollenwort schluckt einen
   echten Nachnamen (`Kollege Beispiel`), ein Einwort-Nachname war inkonsistent
   (`Meier` gegen `Anna Meier`), die Ziffernregel blockierte echte Nachnamen,
   die Zusatzliste war unvollständig (`van den`, `de la`), das Kürzel `M.` war
   mehrdeutig, und die **Rangfolge** der Regeln war nirgends festgelegt.

Dazu zwei Hinweise, die den Umfang bestimmt haben: „letztes Wort = Nachname" und
die Namens-/Umlaut-Normalisierung **existieren schon**
(`services/websuche_schutz.py` `bestand_bauen`, `gruppen_quiz._suchformen`) —
die neue Funktion muss sie teilen statt sie nachzubauen. Und: der
Oberflächen-Teil trifft dieselbe Datei (`frontend/gruppen_quiz.js`) wie ein
gerade laufender Fremdstrang (Filter/Sortierung der Personenliste).

**Folge: der Vorschlag wird in drei Schritten umgesetzt; dieser Commit ist
Schritt 1** (reine Funktion + Ableitung nur beim Lesen).

## Was dieser Schritt baut (eine Codedatei, eine Prüfdatei, dieses Dokument)

In `backend/app/services/gruppen_quiz.py`:

- **`name_zerlegen(name, alle_namen=())`** — reine Funktion, keine Datei, kein
  Netz, **wirft nie**. Regeln mit fester Rangfolge (erste passende gewinnt):
  1. **Namenszusatz** (`von`, `van`, `de`, `del`, `della`, `den`, `der`, `des`,
     `di`, `da`, `dos`, `la`, `le`, `ten`, `ter`, `zu`, `zur`, `zum`, `am`, `im`,
     `in`, `of`, `mac`, `mc`, `bin`, `bint`, `ben`, `ap`, `o`) macht alles ab
     dort zum Nachnamen (`Jan van den Berg` → `Jan` / `van den Berg`); steht der
     Zusatz am Ende, gibt es keinen Nachnamen.
  2. **Kürzel am Ende** (`Anna M.` → Nachname `M.`); dasselbe Kürzel am Anfang
     ist ein Vorname-Kürzel (`M. Beispiel` → `M.` / `Beispiel`).
  3. **Rollenwort am Anfang** (Oma, Opa, Onkel, Tante, Papa, Mama, Kollege,
     Chef, Nachbar …) oder **Ziffern am Ende** des letzten Wortes sind kein
     Nachname — **es sei denn, das Familiensignal stützt ihn**.
  4. Sonst ist bei mindestens zwei Wörtern das **letzte Wort der Nachname**; ein
     einzelnes Wort ist der Vorname.
  - **Familiensignal** (`familienwoerter`): dasselbe Wort am Ende einer anderen
    mehrteiligen Person (Naherung wie `websuche_schutz.bestand_bauen`) hebt die
    Regeln 3 auf und lässt auch ein Einwort-Nachname zu (`Meier` neben
    `Anna Meier`). Ein Name stützt sich dabei nie selbst.
  - **Klammerzusatz** (`Oma (Test)`) ist kein Nachname; ohne Nachname bleibt der
    ganze Name im Feld `vorname` — es wird nichts behauptet, was der Name nicht
    hergibt.
- **`_namensfelder(eintrag, name, alle_namen)`** — Vorname / Nachname /
  Spitznamen für Anzeige und Suche. **Von Hand gesetzte Felder haben Vorrang**;
  fehlen sie, wird abgeleitet. Die Antwort sagt ehrlich, woher sie kommt
  (`namensfelder_quelle`: `profil` oder `abgeleitet`). Spitznamen werden
  getrimmt, leere und unbrauchbare Werte fallen weg, höchstens
  `SPITZNAMEN_MAX = 10`.
- Verdrahtet an den **Lese**stellen `profil()` und `personen()`. Der Name bleibt
  unverändert die Kennung: **es wird dabei nichts geschrieben** — eine Prüfung
  vergleicht die Profildatei Byte für Byte vor und nach dem Lesen.

## Belege (in diesem Lauf selbst gefahren)

- Neu `backend/tests/test_name_zerlegen.py`: **28 Prüfungen** — alle Regeln mit
  **erfundenen** Namen (auch die Gegenbeispiele aus der Prüfung), dazu die
  Verdrahtung: Ableitung im Profil, Vorrang der Handfelder, Begrenzung der
  Spitznamen, Felder in der Personenliste, Datei unverändert.
  Lauf: `.venv/Scripts/python -m pytest tests/test_name_zerlegen.py -q`
  → **28 passed** (2,50 s).
- Nachbardateien zusammen (`test_name_zerlegen`, `test_gruppen_quiz`,
  `test_gruppen_quiz_video`, `test_gruppen_liste`, `test_gruppen_aufloesen`,
  `test_gruppen_diagnose`, `test_personen_werkzeuge_quiz`, `test_werkzeuge`)
  → **240 passed** (22,37 s) — die zusätzlichen Felder brechen keinen Leser.
- Voller Prüfbefehl im Hauptbaum: siehe Journal dieses Laufs.

## Was dieser Schritt bewusst NICHT macht (ehrlich)

- **Kein Schreibweg, keine Oberfläche** (Schritt 2 und 3): die Felder werden von
  Hand gesetzt erst dann gespeichert, wenn `profil_ergaenzen` samt
  `Rückgängig`-Weg und Zusammenführen sie mitzieht (Befund 2 der Prüfung).
  Solange nichts geschrieben wird, kann dabei auch nichts verloren gehen.
- **Die Oberfläche** (drei Eingabefelder, Suche über Vorname/Nachname/
  Spitznamen) wartet auf den **Zusammenschluss des laufenden Fremdstrangs** —
  sie trifft dieselbe Datei.
- **Echte Namen** waren in diesem Lauf nicht nötig und wurden nicht in Berichte
  übernommen; alle Prüfungen nutzen erfundene Namen in `tmp_path`.
