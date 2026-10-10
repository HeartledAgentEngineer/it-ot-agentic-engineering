# Änderungsprotokoll 10.10.2026 — Fortschritt: zwei lebende Balken für die laufende Arbeit

Anlass: Im Nachtlauf 10./11.10.2026 laufen zwei schwere Arbeiten gleichzeitig — die **reiche
Bildbeschreibung** (Auftrag: 489 Bögen zu je 36 Kacheln = 17.580 Bilder, Ergebnisdatei
`bild_beschreibungen_reich.jsonl`) und die **Gesichtserkennung über Papas Fotos** (Auftrag:
6.336 Bilder, Ergebnisdatei `personen_vektoren_papa.jsonl`). Beide schreiben fortlaufend in ihre
Ergebnisdateien; auf dem Dashboard stand davon bisher nichts (nur „Papas Archive entpackt" und die
Schrittliste). Sebastian wollte den Stand — „wie viel Prozent, wie viele von wie viel" — auch für
diese beiden Arbeiten live sehen, samt Kosten und „wo steht er gerade".

## Was neu ist

`werkzeuge/fortschritt/fortschritt.py` misst seit dieser Änderung bei **jedem** Aufruf zwei neue
Kennzahlen aus den Ergebnisdateien. Rein lokal, nur lesend: kein pCloud-Aufruf, kein Netzzugriff,
keine neuen Schreibziele (geschrieben werden wie bisher nur `status.json` und das Dashboard).

- **Bildbeschreibung reich** — Balken über „beschriebene Zeilen von 17.580" (489 Bögen zu je
  36 Kacheln), dazu **Kosten** = Summe der Felder `kosten_usd` gegen den Budgetdeckel 12,00 USD,
  dazu „zuletzt bearbeitet: Datei — Uhrzeit" aus der letzten lesbaren Zeile.
- **Gesichtserkennung Papas Fotos** — Balken über „Zeilen von 6.336"; „zuletzt: Bild-Kennung —
  Datei geaendert …" (die Vektorzeilen tragen keine eigene Uhrzeit, deshalb gilt der Dateistand
  der Ergebnisdatei; das steht so in der Anzeige).

Zählregel und Fehlertoleranz (der Kern des Auftrags):

- Gezählt werden nur **abgeschlossene Zeilen** (mit Zeilenende). Eine gerade erst halb
  geschriebene Schlusszeile zählt noch nicht. Abgeschlossene Zeilen, die kein JSON-Objekt sind,
  zählen nicht mit.
- Für „wo steht er gerade" gilt die **letzte lesbare Zeile** — ist die Schlusszeile angebrochen
  oder unlesbar, wird bis zur letzten brauchbaren zurückgegangen und ein **Hinweis** angezeigt.
- **Fehlende Datei** ergibt 0 Prozent mit Hinweis („Ergebnisdatei fehlt noch") statt eines
  Fehlers. Die Messung steckt zusätzlich in einem try/except wie der bestehende pCloud-Zähler:
  Die Anzeige stürzt nie ab, im Fehlerfall bleiben die alten Zahlen stehen.
- Für die großen Vektorzeilen (~12 KB je Zeile) wird nur das Dateiende wirklich als JSON
  gelesen; gezählt wird über Byte-Muster (Zeilenanfänge/-enden), ohne die Datei zu
  entschlüsseln. Die Bildbeschreibungs-Zeilen (klein) werden voll geparst, weil die
  Kostensumme jede Zeile braucht.

Anzeige (deutsch, ohne Emojis und ohne Häkchen-Symbole):

- **Terminal** (`--terminal`): neuer Abschnitt „Laufende Arbeiten:" mit Balken, „x von y Bilder",
  Prozent, Kostenzeile (nur Bildbeschreibung) und der letzten Zeile.
- **Dashboard** (`.hermes/widgets/fortschritt.html`): neuer Abschnitt „Laufende Arbeiten" im
  vorhandenen dunklen Design (Theme-Variablen), Balken als einfache CSS-Rechtecke
  (einfarbiger `div`-Füllstand), keine Fremdbibliotheken, kein Netz, keine Schriftarten von außen.
  Die Seite lädt sich wie bisher alle 5 Sekunden neu.
- Die Zahlen landen unter `laufende` in `status.json` (eine Wahrheit, zwei Ansichten) und werden
  dort bei jedem Lauf frisch geschrieben; alle übrigen Felder bleiben unangetastet.
- Der bestehende Cron (`fortschritt_tick.py`, alle 2 Minuten, `--zaehle --html`) blieb
  **unverändert** und still — der Wrapper fängt die Ausgabe ab; die Messung läuft in diesem Pfad
  mit.

Leistung (gemessen am 10.10.2026, während beide schweren Hintergrundläufe liefen — die Maschine
war dadurch durchgehend ausgelastet):

- Messung der beiden echten Ergebnisdateien: **rund 0,1–0,2 s** (zusammen ~12 MB).
- Synthetische Dateien in angenommener Endgröße (88,7 MB Vektorzeilen, 7,4 MB Beschreibungen):
  Vektordatei allein **~1,0–1,1 s**, Beschreibungsdatei allein **~0,7–0,9 s**, beide zusammen
  **~1,9–2,3 s**. Die echten Dateien sind noch klein und wachsen erst zum Laufende auf diese
  Größe (die Vektordatei auf ~6.300 Zeilen); gemessen wird, was gerade da ist.
- Kompletter Aufruf `--html` mit den echten Dateien: **1,5–1,6 s**, unter Last Ausreißer bis
  ~2,5 s. Zum Vergleich der Stand VOR der Änderung auf derselben belasteten Maschine:
  ~2,0–2,8 s — die neue Messung schlägt nicht spürbar durch (sie liest nur; die Streuung
  kommt vom Rechner).

## Prüfung

Neu `backend/tests/test_fortschritt_laufend.py` — 12 Tests, offline, erfundene Dateien in
`tmp_path`; die echten Ergebnisdateien werden nie angefasst. Abgedeckt: Prozentzahl bei 50 von
100; mehr Zeilen als geplant (Balken kappt bei 100 Prozent); fehlende Datei → 0 Prozent ohne
Absturz; halb geschriebene Schlusszeile → kein Absturz, letzte lesbare Zeile plus Hinweis;
unlesbare Zeile mitten in der Datei wird übersprungen und gemeldet; Kosten werden summiert (auch
bei kaputtem Kostenwert); „zuletzt" aus Eintragsfeld bzw. aus dem Dateistand; Anzeige in Terminal
und HTML inklusive „keine Fremdquellen" (kein `http`, kein `<script>`).

Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **3647 passed,
2 skipped, Exit 0** (675,39 s).

Belege am echten Lauf (Momentaufnahme 10.10.2026 07:34:48, `status.json`): Bildbeschreibung
**2.806 von 17.580 (16,0 %), Kosten 1,0942 von 12,00 USD**, zuletzt DSC_1707.JPG 07:34:42;
Gesichtserkennung **778 von 6.336 (12,3 %)**, zuletzt Bild 108862603024, Datei geändert
07:34:45. Die Werte stehen nach jedem Lauf frisch in `status.json` unter `laufende`.

## Dateien

- geändert: `werkzeuge/fortschritt/fortschritt.py` (Messung + beide Anzeigen; alle bestehenden
  Ansichten unverändert), `02_Softwareentwicklung_IT/personal_ai_agent/CLAUDE.md`
  (Änderungsprotokoll-Zeile).
- neu: `02_Softwareentwicklung_IT/personal_ai_agent/backend/tests/test_fortschritt_laufend.py`,
  dieses Changelog.
- `werkzeuge/fortschritt/status.json` ist Laufzeitzustand und wird vom 2-Minuten-Cron
  fortlaufend aktualisiert; sie ist nicht Teil dieses Commits.

## Offen / Hinweise

- Die Zählung startet bei einem Neustart des jeweiligen Werkzeugs bei 0 neu geschriebener Datei
  (Datei wird ersetzt) — die Anzeige misst die Datei, nicht die Historie.
- Die zwei echten Läufe bringt diese Änderung nicht zum Stehen: es wird nur gelesen.
