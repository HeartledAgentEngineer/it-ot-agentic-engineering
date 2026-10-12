# Nachweis: verwaiste Personen-Kennungen werden benannt statt nur gezählt (12.10.2026)

## Warum

Journal 23 des Nachtlaufs hat mit der neuen Zeile „Personen (Quiz)" einen echten
Befund gefunden: **2 bestätigte Kennungen in `personen_bestaetigt.json` haben
keine Gruppe** — die Namen zeigen auf Gruppen, die es in
`personen_gruppen/personen_beispiele.json` nicht mehr gibt. Die Prüfzeile nannte
das seither nur als **Zahl** („2 Kennungen ohne Gruppe (Namen ohne Gesichter)").

Diese Zahl sagt aber nicht, was wirklich los ist. „Kennung ohne Gruppe" kann
zwei ganz verschiedene Dinge heißen:

* **verwaister Doppel-Eintrag** — derselbe Name trägt an einer *anderen*
  Kennung eine lebende Gruppe. Die Person ist **nicht verloren**, nur der eine
  Eintrag zeigt ins Leere (typisch nach einer Neugruppierung).
* **Name zeigt ins Leere** — derselbe Name kommt sonst nirgends vor; dann wäre
  die Person aus den Werkzeugen tatsächlich verschwunden.

Ohne die Trennung sieht der harmlose Doppel-Eintrag wie eine verlorene Person
aus — genau der Unterschied, der über Handarbeit oder Nichtstun entscheidet.

## Was jetzt gemessen wird

`personen_lesen()` liest beim Zählen der Gruppen auch deren **Namen** (nur die
Menge der Namen, die an einer lebenden Kennung hängen) und teilt die verwaisten
Kennungen in zwei Zahlen:

* `ohne_gruppe_doppelt` — derselbe Name (Groß-/Kleinschreibung egal) hängt an
  einer anderen Kennung mit Gruppe,
* `ohne_gruppe_ins_leere` — sonst (auch eine Kennung **ohne** Namen zählt hier:
  an ihr hängt nirgends ein Gesicht).

Die Berichtszeile nennt beide Zahlen, die Lücken-Zeile ebenfalls:

```
Personen (Quiz): personen_bestaetigt.json: 20 Kennungen mit Namen = 7 Personen;
2 Kennungen ohne Gruppe (davon 2 mit demselben Namen an einer Gruppe, 0 ins Leere)
```

**Keine neue Lücke** — die verwaisten Kennungen bleiben genau die eine Lücke
wie bisher; sie ist jetzt nur genau benannt. Ist die Gruppen-Datei nicht da,
bleibt es bei 0/0 („ohne Gruppen gibt es nichts zu vergleichen"), es wird nichts
geraten. Betriebs- und Anzeigecode unangetastet; **nur Zahlen — kein
Personenname**, auch nicht in der neuen Zeile (im Test festgehalten).

## Belege (frisch ausgeführt)

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **83 → 85
  Testfunktionen** (2 neue: „trennt verwaiste Namen von ins Leere" über Bericht
  *und* Lücke, „ohne Gruppendatei bleibt 0/0 + Namenloses zählt ins Leere +
  Groß-/Kleinschreibung versteckt den Doppel-Eintrag nicht"), Lauf der Datei
  **85 passed** (16,45 s).
* Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q`:
  siehe Journal 32 der Plandatei (Exit 0). Die einzige angepasste bestehende
  Prüfung ist die Lücken-Zeile der Personen-Stufe — sie erwartete den alten,
  jetzt erweiterten Text (inhaltlich dieselbe Aussage, plus die zwei Zahlen).
* **Messung am echten Bestand (Exit 0, nur lesend):**
  `Personen (Quiz): personen_bestaetigt.json: 20 Kennungen mit Namen =
  7 Personen; 2 Kennungen ohne Gruppe (davon 2 mit demselben Namen an einer
  Gruppe, 0 ins Leere)`.

## Der Befund (gemessen, nicht geändert)

**Keine der zwei verwaisten Kennungen steht für eine verlorene Person: beide
tragen denselben Namen wie eine lebende Gruppe** — es sind zwei verwaiste
Doppel-Einträge (ein Name hängt an mehreren Kennungen, die Neugruppierung hat
zwei davon fallengelassen). Für die Personen-Auskunft heißt das: sie findet die
Personen weiterhin, die zwei Alt-Einträge erzeugen nur eine Gruppe ohne
Gesichter.

**Geändert wurde nichts.** Die Einträge stehen in Sebastians eigener
Namens-Datei; die maßgebliche Fassung liegt am **Gerät** und der PC hat nur die
Kopie vom 08.10. — ein Eingriff am PC wäre wirkungslos und würde beim nächsten
Übernahmelauf überschrieben. Ob die zwei Einträge am Gerät entfernt werden, ist
seine Entscheidung.

## Nicht angefasst

Nichts gelöscht, kein Bild- oder Gesichtsdienst aufgerufen, keine
Handy-Eingriffe, keine kostenpflichtigen Massenläufe, keine pCloud-Zugriffe.
Committet wurden ausschließlich eigene Pfade (`git commit --only`, nie
`git add -A`).
