# Changelog 28.09.2026 — N27 Schritt 3: Kalender-Andockung

**Schritt:** N27 (Verknuepfungsschicht), **Teil 3 von 5** — Kalender-Andockung.
**Rollen:** Planer/Bauherr = Hauptagent · Ausfuehrer = Hermes-Subagent
(`deepseek/deepseek-v4.1-flash`) · **Pruefer** = frischer Kontext, andere
Modellfamilie.

## Warum

Schritt 1 (`ereignisse_bauen.py`) hat je Anlass einen **Ereignis-Knoten** gelegt,
Schritt 2 (`chat_andocken.py`) die Chats angebunden. **Schritt 3 dockt den
Kalender an:** zu jedem Ereignis wird gefragt, welche Kalender-Termine an genau
diesem Tag lagen (inklusive **mehrtagiger** Termine, die den Tag enthalten) und
welche Termine nur **±1 Tag** daneben liegen — inklusive **jaehrlich
wiederkehrender Geburtstage**.

Der Schritt ist bewusst **rein lokal und nur lesend**: kein Netz, kein pCloud,
kein Bild, kein LLM-Aufruf. Das Takeout-Zip wird **ausschliesslich per
`zipfile`** gelesen, nie entpackt, nie kopiert.

## Gebaut

* **`tools/foto_sortierung/kalender_andocken.py`** (**784 Zeilen**, Nachbarmodul
  von `ereignisse_bauen.py`/`chat_andocken.py`): liest
  `~/foto_sortierung/ereignisse.jsonl` und die ICS aus dem Takeout-Zip (per
  `zipfile`) und schreibt **JSONL** nach
  `~/foto_sortierung/kalender_andockung.jsonl`, **eine Zeile je Ereignis, in
  derselben Reihenfolge wie die Eingabe**. Eingefrorene Schnittstelle:
  `ereignisse_laden`, `zip_ics_lesen`, `zeilen_entfalten`, `bloecke_sammeln`,
  `termin_bauen`, `termine_lesen`, `andocken` (rein), `knoten_zeile` (rein),
  `andockung_schreiben` (atomar), `zahlen_text`, `haupt`.
* **`backend/tests/test_kalender_andockung.py`** (**1.010 Zeilen, 114
  Testfunktionen**, alles offline; erfundene ICS-Beispiele **in-memory** bzw. in
  einem Attrappen-Zip im `tmp_path`, keine echte ICS, keine Datei unter
  `~/foto_sortierung/`).
* **Kommandozeile:** `--ereignisse`, `--zip`, `--mitglied`, `--ausgabe`,
  `--auch-nah`, `--stand`, `--limit N`, `--trocken` (**Standard**, schreibt
  nichts), `--schreiben` (atomar per temp-Datei im Zielordner + `os.replace`).
* **Nur Standardbibliothek** (`argparse`, `datetime`, `json`, `os`, `re`, `sys`,
  `zipfile`). Kein `requests`/`httpx`, kein Bildmodul, kein `shutil`.

**Was das Werkzeug nicht tut** (Quelltext-Suchtest in den Tests): kein Netz, kein
Bild, **kein Entpacken/Kopieren** (`extractall`/`extract`/`unzip`/`shutil`
kommen nicht vor), kein weiterer Termin-Text (`DESCRIPTION`/`LOCATION` werden
nicht gelesen), **keine Loeschfunktion** ausser der **eigenen** temp-Datei beim
atomaren Schreiben (`os.remove` genau **einmal**), kein Ziel im Repo.

## Fensterregel und jaehrliche Wiederkehr

* **Treffer** = Termine **am selben Tag** (ein mehrtagiger Termin enthaelt alle
  Tage `[DTSTART, DTEND)`); **nah** = Termine **±1 Tag**, die **kein**
  Tag-Treffer sind — nur als schwacher Hinweis gezaehlt (Lehre aus N6e).
  `--auch-nah` nimmt sie zusaetzlich in `treffer` auf; Standard = aus.
* **Jaehrlich ueber `RRULE` mit `FREQ=YEARLY`:** Treffer ueber **Tag+Monat**,
  unabhaengig vom Jahr; `wiederkehrend: true`, `beginn` ist das **Anlass-Jahr** +
  Monat/Tag.
* **Titel-Rueckfall** (falls **keine** `RRULE` gesetzt ist): Titel mit
  „Geburtstag"/„Jahrestag" und vollstaendigem Datum gelten ebenfalls als
  jaehrlich. **Liegt eine (auch nicht-jaehrliche) `RRULE` vor, greift der
  Rueckfall nicht** — so der Klammerzusatz des Auftrags.

## Gemessen (echter Bestand, nur lesend)

* **Pruefbefehl** selbst gefahren:
  `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **2.414 passed, 3 warnings, Exit 0** (die neue Testdatei bringt **114**
  Testfunktionen ein).
* **Trockenlauf** gegen den echten Bestand (Standardpfade, `--trocken`):
  * Ereignisse: **2.127** (wie beauftragt) · ohne Datum: **0** · Treffer-Zeilen
    (Ereignisse mit ≥1 Treffer): **812**
  * Termine am Tag (Treffer gesamt): **957** · Nah-Treffer (±1 Tag): **1.162** ·
    davon wiederkehrend: **253** · Maximum Treffer je Ereignis: **3**
  * ICS-Leser: **Termine 405** · Bloecke **405** · defekte Bloecke **0** ·
    ungeschlossene Bloecke **0** · ohne Titel **0**.
* **Gegenprobe `--auch-nah`:** Treffer-Zeilen **1.300**, Treffer gesamt
  **2.119** (= 957 + 1.162), Nah-Zahl bleibt **1.162**, wiederkehrend **742**,
  Maximum **6**. Belegt die Fenster-Additivitaet sauber.
* **Zwei Schreiblaeufe in einen frischen Ordner ausserhalb des Repos**
  (`C:/Users/sebas/foto_sortierung/_n27c_probe/`, fester `--stand
  2026-09-28T00:00:00+02:00`): beide **601.653 Bytes · 2.127 Zeilen**,
  sha256 `cef6aedaaff6197810eeaaa54949d6099a40d92795c9eb5fed96fa745249d07e` —
  **byte-gleich**; **keine** `*.tmp`-Reste.
* **Nichts am Bestand veraendert:** `ereignisse.jsonl` und das Takeout-Zip sind
  vor/nach allen Laeufen **byte- und mtime-identisch**
  (`ereignisse.jsonl`: sha256 `344082a267d1c19af9be4c32e569cd54b97847e702847469f204cc785c621adc`,
  mtime `1790600079.493485`, 1.286.120 B; Zip:
  sha256 `233f5fe0c549134ba4bbd7794b75ae2edcc27ebb80b4ccaee747f555f5ae93e0`,
  mtime `1786569382.6689484`, 1.437.891.009 B). Das Zip wurde nur per `zipfile`
  gelesen, nichts entpackt.
* **`manifest.jsonl` unberuehrt** — die Datei existiert im Bestand derzeit
  **nicht**; es wurde nichts angelegt oder entfernt.
* **Reposchutz live belegt:** Ziel im Repo mit `--schreiben` → deutsche Meldung
  auf `stderr`, **Exit 2**, **keine** Datei entsteht.

## Ehrlich offen / Abweichungen zum Feinauftrag

1. **Zusatzschalter `--stand`.** Der Auftrag listet nur `--ereignisse`, `--zip`,
   `--mitglied` als konfigurierbar, verlangt fuer den Idempotenzbeleg aber „zwei
   `--schreiben`-Laeufe … mit **festem** `stand`". Ohne einen Schalter waere der
   `stand` nicht fixierbar; deshalb ist `--stand` ergaenzt (Standard: jetzt).
   Alle drei beauftragten Standardschalter haben **genau** die vorgegebenen
   Standardwerte.
2. **`--mitglied`-Standard ist leer (siehe Nachtrag unten).** Ein fest
   eingetragener Dateiname im Takeout-Zip ist eine Mailadresse und gehoert nicht
   ins Repo. Die Vorgabe liest deshalb **alle** `Takeout/Kalender/*.ics`; die
   Konsole nennt nur die **Anzahl** gefundener Kalenderdateien. In Code, Tests und
   Doku steht damit **kein** echter Termin-, Orts-, Personen- oder Kontoname.
3. **`ende` bei jaehrlicher Wiederkehr.** Der Auftrag legt nur `beginn` fest
   (Anlass-Jahr + Monat/Tag). Umgesetzt ist `ende` = `beginn` + Spanne des
   Termins (bei Geburtstagen also der Folgetag), damit `beginn`/`ende` zusammen
   passen. Beim **29. Februar** wird in Nicht-Schaltjahren auf den **28.
   Februar** geklemmt (deterministisch, dokumentiert).
4. **`anzahl_nah` bleibt ehrlich.** Auch mit `--auch-nah` nennt `anzahl_nah` die
   Zahl der Nah-Termine (sie stehen dann zusaetzlich in `treffer`), damit keine
   Zahl durch eine Option verschwindet.
5. **Kein weiterer Termin-Text.** `DESCRIPTION` und `LOCATION` werden gar nicht
   erst gelesen; die Ausgabe traegt nur `SUMMARY` (auf 120 Zeichen gekuerzt).

## Schutz und Grenzen

* Takeout-Zip **nur lesend** per `zipfile` — nie entpackt, kopiert oder
  verschoben; keine neue Abhaengigkeit.
* Ausgabe ausschliesslich **ausserhalb** des Repos; **nichts geloescht** (einzige
  Entfernung im Quelltext: die eigene temp-Datei beim fehlgeschlagenen atomaren
  Schreiben).
* Fremde Parallelarbeit im selben Arbeitsbaum wurde **nicht** angefasst; es
  wurden **keine** `git`-Befehle ausgefuehrt (Commit macht der Planer).

## Offen

* Die **echte** Ausgabedatei `~/foto_sortierung/kalender_andockung.jsonl` wurde
  bewusst **nicht** geschrieben (nur Trockenlauf + Probeschreiblaeufe in einen
  frischen Ordner); das Schreiben bleibt dem Planer/naechsten Lauf.
* Schritte **4–5** von N27 fehlen; Personen kommen bewusst erst in Schritt 4 und
  **nur nach Bestaetigung** durch den Nutzer.

## Nachtrag: Vorgabe findet den Kalender im Zip automatisch

Grund der Aenderung: Die bisherige Vorgabe `STANDARD_MITGLIED` trug den
**Kontonamen** (Mailadresse) im Quelltext — Punkt 2 der Abweichungen. Das ist
unzulaessig, deshalb ist der Standard jetzt **leer** (`STANDARD_MITGLIED = None`);
ohne `--mitglied` liest `zip_ics_lesen()` automatisch **alle** Eintraege
`Takeout/Kalender/*.ics` im Zip und haengt ihre Texte mit Zeilenumbruch
aneinander. Gibt es keine Kalenderdatei, kommt eine deutsche Klartextmeldung
(und auf der Kommandozeile Exit 2); ein **ausdruecklich genannter**, aber
fehlender Eintrag bleibt weiterhin ein Klartextfehler. Die Konsole nennt den
**gefundenen Eintragsnamen nicht** (das ist ein Kontoname) — sie zeigt nur die
**Anzahl** der gefundenen Kalenderdateien (`Kalenderdateien: 2`). Die Tests
pruefen mit erfundenen Namen (`Takeout/Kalender/beispiel-a.ics`,
`beispiel-b.ics`); die beiden betroffenen Tests (Vorgabe-Name bzw. „ohne
mitglied ist Fehler") sind entsprechend umgeschrieben. **Punkt 2 der
Abweichungen ist damit erledigt/ueberholt** — im Quelltext, in den Tests und in
dieser Doku steht keine Mailadresse mehr.

**Zahlen unveraendert** (Trockenlauf gegen den echten Bestand, Standardpfade):
Ereignisse **2.127** · ohne Datum **0** · Treffer-Zeilen **812** · Termine am
Tag **957** · Nah-Treffer **1.162** · davon wiederkehrend **253** · Maximum **3**
· ICS-Termine **405** · Bloecke **405** · defekte Bloecke **0** ·
ungeschlossen **0** · ohne Titel **0** — **alle Zahlen identisch zum Lauf
oben**, keine Abweichung. Die Testdatei bleibt bei **114 Testfunktionen**,
**114 passed, Exit 0**.
