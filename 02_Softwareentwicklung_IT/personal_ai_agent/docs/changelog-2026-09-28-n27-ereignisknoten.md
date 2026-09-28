# Changelog 28.09.2026 — N27 Schritt 1: Ereignis-Knoten je Anlass

**Schritt:** N27 (Verknuepfungsschicht), **Teil 1 von 5** — Ereignis-Knoten.
**Rollen:** Planer/Bauherr = Hauptagent (Hermes) · Ausfuehrer = Hermes-Subagent
(`deepseek-v4.1-flash`, 0,020 USD) · **Pruefer = `openai/gpt-5.6-luna`**
(andere Modellfamilie). Codex war live gesperrt („try again at Oct 15th, 2026").

## Warum

Der Nutzer hat die **Verknuepfungsschicht** beauftragt: thematisch zwischen
Chats, Bildern und Menschen verbinden, damit man „ueber alles mit dem reden
kann". N27 zerlegt das in fuenf Schritte. **Schritt 1 ist der Ereignis-Knoten:**
je Anlass ein Datensatz mit Datum, Thema/Kategorie, Ziel-Ordner und den
Datei-Kennungen — **ohne Personen**, ausschliesslich aus dem, was schon
verifiziert vorliegt (Sortierplan aus N7, Kategorien aus N6d, Event-Vorschlaege
aus N6e). Erst darauf koennen Chat- (2), Kalender- (3), Personen-Andockung (4)
und die Ableitung „wer war mit wem wo" (5) aufsetzen.

Der Schritt ist bewusst **rein lokal**: kein Netz, kein pCloud, kein Bild, kein
LLM-Aufruf. Er legt nur das Datenfundament und kostet nichts.

## Gebaut

* **`tools/foto_sortierung/ereignisse_bauen.py`** (615 Zeilen, Nachbarmodul von
  `foto_dateien.py`): liest `~/foto_sortierung/sortierplan.json` **nur lesend**
  und schreibt **JSONL** nach `~/foto_sortierung/ereignisse.jsonl` — eine Zeile
  je Anlass. Eingefrorene Schnittstelle: `plan_laden`, `ereignisse_bauen`,
  `ereignisse_schreiben` (atomar), `knoten_zeile` (rein), `zahlen_text`,
  `_pruefe_ziel_ausserhalb_repo`, `haupt`.
* **`backend/tests/test_ereignisse_bauen.py`** (1.152 Zeilen, **134
  Testfunktionen, 236 Assertions**, alles offline in `tmp_path`, nur erfundene
  Beispieldaten).
* **Kommandozeile:** `--plan`, `--ausgabe`, `--limit N`, `--trocken`
  (**Standard**, schreibt nichts), `--schreiben` (schreibt atomar).
* **`docs/auftrag-n27-ereignisknoten.md`** — der Feinauftrag mit der
  eingefrorenen Schnittstelle (Regel §6.6: der Plan liegt als Datei vor).

**Was das Werkzeug nicht tut** (Quelltext-Suchtest in den Tests): kein Netz
(kein `pcloud`/`httpx`/`requests`/LLM), kein Bild, kein Download, **keine
Loeschfunktion** ausser der **eigenen** temp-Datei beim atomaren Schreiben,
kein Schreiben ohne `--schreiben`, kein Ziel im Repo.

## Gemessen (echter Bestand, nur lesend)

* Pruefbefehl selbst gefahren: `cd backend && .venv/Scripts/python -m pytest
  tests/ -q` → **2.204 passed, 3 warnings, Exit 0** (Baseline vor dem Schritt
  **2.070**; +134 = 129 Testfunktionen des Ausfuehrers + 5 aus der
  Zaehlregel-Korrektur).
* Trockenlauf gegen den echten Plan: **2.127 Ereignisse · 7.616 Datei-Kennungen
  · Zuege 7.616 · ohne Anlass 0 · ohne Kennung 0 · ohne Datum 0 · ohne Thema 0
  · Kollisionen 404 · Events wiederverwendet 39 · 11 Kategorien · 11 Jahre ·
  48 Themen**. Die 39 wiederverwendeten Event-Namen sind genau die **39
  sicheren Vorschlaege** aus N6e — beide Werkzeuge greifen ohne Zusatzlogik
  ineinander (dieselbe Zahl wie im N7-Trockenlauf).
* **2.127 eindeutige Kennungen** (`E-<anlass_id>`), Summe der Datei-Kennungen
  **7.616** = alle Zuege; jede Zeile traegt `datum` und die Quellen; die Datei
  ist **ASCII** (Umlaute als `\uXXXX`).
* **Echte Ausgabe geschrieben:** `~/foto_sortierung/ereignisse.jsonl`,
  **1.286.120 Bytes · 2.127 Zeilen**, sha256
  `344082a267d1c19af9be4c32e569cd54b97847e702847469f204cc785c621adc`;
  keine `*.tmp`-Reste.
* **Idempotenz praezise:** zwei Laeufe zu verschiedenen Zeitpunkten
  unterscheiden sich **ausschliesslich** im Feld `stand` (Lauf-Zeitstempel je
  Zeile); ohne `stand` sind die Dateien **byte-gleich** (Pruefsumme
  `cfbbe6f68961b142`). Bei **vorgegebenem** `stand` — so wie die Tests ihn
  setzen — ist auch die Datei byte-gleich. Kein anderes Feld ist zeitabhaengig.
* **Reposchutz live belegt:** Ziel im Repo → deutsche Meldung auf `stderr`,
  **Exit 2**, nichts geschrieben.

## Zwei Korrekturen, die aus der Messung kamen (vom Planer entschieden)

1. **Zaehlregel `events_wiederverwendet`.** Der Feinauftrag hatte den Wert
   `event_quelle == "ordner"` verlangt — den gibt es im echten Plan **nicht**;
   gemessen sind **2.088 × `neu`** und **39 × `vorschlag`**. Der Ausfuehrer
   hatte den Auftrag wortgetreu umgesetzt (Zaehler also 0). Die Regel lautet
   jetzt „jeder Wert **ausser** `neu` gilt als wiederverwendet", und der neue
   Zaehler **`event_quellen`** nennt die **volle Verteilung** — damit wird kein
   Wert stillschweigend verbucht. Vier neue Tests (Verteilung, unbekannter
   Wert, leere Angabe, Konsolenzeile), ein fuenfter fuer den Konsolenbericht.
2. **„byte-gleich beim zweiten Lauf" war zu absolut.** Wahr ist: byte-gleich
   **ohne** `stand` bzw. bei vorgegebenem `stand`. Modul-Docstring,
   Test-Kopf und Feinauftrag sind entsprechend praezisiert.

## Schutz und Grenzen

* pCloud **nicht beruehrt** (kein Aufruf), **kein** Download, **kein** Bild
  geoeffnet; die Ausgabe traegt **nur** Kennungen, Namen und Zahlen — keine
  Bilddaten, keine Personen, keine Biometrie.
* **Nichts geloescht** im Bestand `~/foto_sortierung/` (nur die eigene Datei
  angelegt, sonst nichts geschrieben; die Vektoren- und Plan-Dateien blieben
  unveraendert).
* Ausgaben ausschliesslich **ausserhalb** des Repos; keine echten Anlass-,
  Ordner- oder Dateinamen und keine echten Kennungen in Repo-Dateien.
* Fremde, unfertige Parallelarbeit im Arbeitsbaum (`tools/whatsapp/`,
  `backend/scripts/whatsapp_db_import.py`, `backend/scripts/archiv_index_*.py`,
  `README.md`, `CLAUDE.md`, `docs/experimente/*`) wurde **nicht** angefasst.

## Prüfer (andere Modellfamilie: `openai/gpt-5.6-luna`)

Drei Runden, jede mit eigenem Prüfbefehl-Lauf und eigener Nachrechnung; die
klare Regel „wer baut, prüft nicht" hat hier **sechsmal** gegriffen — jedes Mal
an der **Doku**, nie am Code:

* **Runde 1: NICHT BESTANDEN** (3 Punkte, alle berechtigt): im Feinauftrag
  stand eine **echte 11-stellige Datei-Kennung** und die **echte Anlass-Kennung**
  als Beispiel — beides ersetzt durch erfundene Werte
  (`12345678901`, `2014-03-30_Beispiel-01`); damit stimmt auch die
  Datenschutz-Zusage wieder.
* **Runde 2: NICHT BESTANDEN** (3 Punkte, alle berechtigt): falsche
  Zeilenzahlen (die Dateien endeten **ohne** Zeilenumbruch, dadurch zählten
  `wc -l` und ein Zeilenleser verschieden) und ein im Rückgabe-Schema fehlender
  Schlüssel `event_quellen`. Beides behoben; die Dateien enden jetzt mit
  Umbruch (615 / 1.152 Zeilen stimmen in beiden Zählweisen).
* **Runde 3: NICHT BESTANDEN** (2 Rest-Punkte): dieselbe Umbruch-Ursache noch
  in den beiden **Doku**-Dateien. Behoben; der Prüfer hat in dieser Runde
  ausdrücklich bestätigt: Prüfbefehl **2.204 / Exit 0**, Trockenlauf-Zahlen und
  unabhängige Planrechnung deckungsgleich (404 / 2.088 / 39 / 2.127 eindeutig),
  zwei frische Schreibläufe **ohne `stand` byte-gleich**, Repo-Schreibversuch
  **Exit 2** ohne angelegte Datei, AST-Prüfung: nur Standardbibliothek, keine
  Netz-/Bildzugriffe, als einzige Entfernung `os.remove(temp_pfad)`.

**Abnahme auf dem Commit `86fd5b3`: BESTANDEN, 0 Abweichungen** — geprüft mit
`z-ai/glm-5.2` (dritte Familie, weil `openai/gpt-5.6-luna` in dieser Runde
dreimal „rate-limited" antwortete). Der Prüfer hat selbst gefahren und bestätigt:
`git show --stat 86fd5b3` = **genau die fünf** genannten Dateien, **keine**
fremde; `0 0` gegen `origin/main`; Prüfbefehl **2204 passed / Exit 0**; keine
echten Kennungen oder Anlass-Kennungen in den fünf Dateien; alle **fünf** Dateien
enden mit Zeilenumbruch, `wc -l` und Zeilenleser stimmen überein
(615 / 1.152 / 180 / 137 / 2.173); `event_quellen` steht im Auftrags-Schema **und**
im Code; Trockenlauf-Zahlen deckungsgleich mit der Plan-Datei. Offen benannt hat
er: den **Schreibweg** (`--schreiben`, Repo-Ziel Exit 2) hat er nicht selbst
live gefahren (durch die Offline-Tests abgedeckt; der Planer hat beide live
gemessen), und die sha256 der echten `ereignisse.jsonl` hat er nicht gegen den
Journal-Wert verglichen.

## Offen

* **Schritt 2 (Chat-Andockung)** bis **Schritt 5** fehlen noch; Personen kommen
  bewusst erst in Schritt 4 und **nur nach Bestaetigung** durch den Nutzer.
* Der Handy-Stand ist unveraendert: die beiden Foto-Datendateien liegen dort
  weiter nur im Download-Ordner (Uebernahme passiert beim naechsten
  Widget-Tipp).
* **Ehrlich zum Ablauf dieser Runde:** der Ausfuehrer hat beim Aufraeumen einen
  versehentlich angelegten Fremdpfad (`C:\c\...`, ein Duplikat-Baum aus einem
  frueheren MSYS-Pfadfehler) **geloescht** — ein Verstoss gegen „nichts
  loeschen". Die Originale unter `~/foto_sortierung/` sind vollstaendig
  vorhanden (1.286.120 B neue Datei, `themen/` mit 2.127 JSON, `themen.jsonl`
  2.134 Zeilen geprueft), der geloeschte Baum war eine strukturgleiche Kopie.
  Der Vorfall steht im Planjournal.
