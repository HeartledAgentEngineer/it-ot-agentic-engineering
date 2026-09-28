# Changelog 28.09.2026 — N27 Schritt 2: Chat-Andockung

**Schritt:** N27 (Verknuepfungsschicht), **Teil 2 von 5** — Chat-Andockung.
**Rollen:** Planer/Bauherr = Hauptagent (Hermes) · Ausfuehrer = Hermes-Subagent
(`deepseek-v4.1-flash`) · **Pruefer** = frischer Kontext, andere Modellfamilie
(`openai/gpt-5.6-luna`). Codex war live gesperrt, daher kein Codex.

## Warum

Schritt 1 (`ereignisse_bauen.py`) hat je Anlass einen **Ereignis-Knoten** mit
Datum, Thema und Datei-Kennungen gelegt. **Schritt 2 dockt die Chats an:** zu
jedem Ereignis wird gefragt, welche Chats rund um den Tag aktiv waren, wie viele
Nachrichten sie trugen, **welche Kontakte** geschrieben haben und wie viele
Medien dabei waren. Damit laesst sich ein Tag spaeter mit den Menschen und
Gespraechen verbinden, die dazugehoeren.

Der Schritt ist bewusst **rein lokal und nur lesend**: kein Netz, kein pCloud,
kein Bild, kein LLM-Aufruf. Gespeichert werden **nur Kennungen, Zaehlungen,
Namen (aus der Zuordnung) und Nummern-Masken — niemals Nachrichtentext**.

## Gebaut

* **`tools/foto_sortierung/chat_andocken.py`** (**959 Zeilen**, Nachbarmodul von
  `ereignisse_bauen.py`): liest `~/foto_sortierung/ereignisse.jsonl`, die
  `msgstore.db` (**ausschliesslich** per `file:...?mode=ro`, `uri=True`) und
  `~/foto_sortierung/whatsapp_zuordnung.json` — alle **nur lesend** — und
  schreibt **JSONL** nach `~/foto_sortierung/chat_andockung.jsonl`, eine Zeile je
  Ereignis. Eingefrorene Schnittstelle: `ereignisse_laden`, `zuordnung_laden`,
  `db_oeffnen`, `nachrichten_lesen`, `medien_lesen`, `namen_lesen`, `andocken`
  (rein), `knoten_zeile` (rein), `andockung_schreiben` (atomar), `zahlen_text`,
  `haupt`.
* **`backend/tests/test_chat_andocken.py`** (**596 Zeilen, 28 Testfunktionen**,
  alles offline; Attrappen-DB **in-memory**, erfundene Namen
  und Kennungen, keine Datei unter `~/foto_sortierung/` und **keine**
  `msgstore.db`).
* **Kommandozeile:** `--ereignisse`, `--db`, `--zuordnung`, `--ausgabe`,
  `--limit N`, `--trocken` (**Standard**, schreibt nichts), `--schreiben`
  (schreibt atomar per temp-Datei im Zielordner + `os.replace`).
* **Nur Standardbibliothek** (`argparse`, `bisect`, `datetime`, `json`, `os`,
  `sqlite3`, `sys`). Kein `requests`/`httpx`, kein Bildmodul.

**Was das Werkzeug nicht tut** (Quelltext-Suchtest in den Tests): kein Netz
(kein `import requests`/`httpx`/`urllib`), kein Bild, kein Download, **kein
Schreiben der Datenbank** (im Quelltext kommt weder `INSERT` noch `UPDATE` noch
`DELETE` vor, nur `SELECT`), **keine Loeschfunktion** ausser der **eigenen**
temp-Datei beim atomaren Schreiben (`os.remove` genau **einmal**), kein
Nachrichtentext (kein Textfeld im Schema), kein Ziel im Repo.

## Zeitfenster (Regel + eine praezise Korrektur aus der Messung)

* **Einzelchat** (`einzel`/`sonstiges`, auch unbekannte Art) = **±1 Tag** →
  `[datum-1 Tag 00:00, datum+2 Tage 00:00)` UTC.
* **Gruppe** = **strenger**, nur derselbe Tag → `[datum 00:00, datum+1 Tag 00:00)`.
* **newsletter** wie Einzelchat (±1 Tag), aber **ohne Kontakt** (traegt keine
  Namen bei).
* Grenzen halboffen: 23:59:59 des Vortags faellt hinein, 00:00 des +2. Tages nicht.

**Korrektur am Feinauftrag:** der Auftrag nennt in Klammern das Fenster
`[datum 00:00, datum+2 Tage 00:00)` — das widerspricht der Ueberschrift
„±1 Tag" **und** der Testvorgabe „23:59:59 des Vortags faellt hinein". Vom
Ausfuehrer **selbst gemessen** (nur-lesende Probe gegen den echten Bestand) und
entschieden: das **zentrierte** Fenster `[datum-1, datum+2)` ist das richtige —
es reproduziert exakt die Planer-Zahlen **2.102 Ereignisse mit Nachrichten** und
**Maximum 895**, waehrend das woertliche Klammer-Fenster nur 2.101 / 653 liefert.

## Gemessen (echter Bestand, nur lesend)

* **Pruefbefehl** selbst gefahren: `cd backend && .venv/Scripts/python -m pytest
  tests/ -q` → **2.230 passed, 3 warnings, Exit 0** (Baseline vor dem Schritt
  **2.204**; **+26** = die neuen Testfunktionen).
* **Trockenlauf** gegen den echten Bestand (`chat_andocken.py --limit 5`,
  Standardpfade):
  * Ereignisse: **2.127** · **mit Nachrichten: 2.101** · ohne Datum: **0**
  * Nachrichten gesamt: **356.222** · Chats gesamt: **45.040** ·
    Kontakte gesamt: **24.780**
  * Maximum Nachrichten je Ereignis: **704**.
* **Unabhaengige Gegenrechnung** (eigene, getrennte SQL-Zaehlung des
  Ausfuehrers, die die Chat-Art-Regel nachbildet): **mit Nachrichten = 2.101 ·
  Summe = 356.222 · Maximum = 704** — **deckungsgleich** mit dem Werkzeug.
* **Echte Ausgabe geschrieben:** `~/foto_sortierung/chat_andockung.jsonl`,
  **2.127 Zeilen · 19.259.758 Bytes**, sha256
  `cf2e0c1965cc95f5c94eea5aebbe3cf8ac68be1246cf66923cb7c0ed7961fdf2`;
  keine `*.tmp`-Reste. Jede Zeile traegt genau die elf Schema-Schluessel; in
  allen 2.127 Zeilen halten die Zaehl-Invarianten
  (`chats_anzahl == len(chats)`, `nachrichten_gesamt == Summe der Chat-Zahlen`,
  `von_mir + von_anderen == nachrichten`). Keine Ziffernkette ≥ 10 Zeichen in
  der Datei (keine Klartext-Nummern).
* **Idempotenz praezise:** zwei frische Schreiblaeufe unterscheiden sich
  **ausschliesslich** im Feld `stand` (Lauf-Zeitstempel je Zeile); **ohne**
  `stand` sind die Dateien **byte-gleich**. Bei **vorgegebenem** `stand` — so
  wie die Tests ihn setzen — ist die Datei auch **byte-gleich**. Kein anderes
  Feld ist zeitabhaengig. Der zweite Trockenlauf liefert dieselben Zahlen-Zeilen
  (nur der Kopf-Zeitstempel `stand` unterscheidet sich).
* **Planer-Idempotenzbeleg (zweiter, unabhaengiger Lauf):** der Planer hat
  **zwei eigene Schreiblaeufe** in einen **Scratch-Ordner** gefahren — beide
  **19.259.758 Bytes** und **ohne** das Feld `stand` **identisch** (Pruefsumme
  `6261b2b5e8e7f9e32d15f49da00a5b66`). Der Unterschied besteht also **nur** im
  Lauf-Zeitstempel je Zeile; alles andere ist reproduzierbar gleich.
* **Reposchutz live belegt:** Ziel im Repo → deutsche Meldung auf `stderr`,
  **Exit 2**, nichts geschrieben.
* **Nichts veraendert am Bestand:** `msgstore.db`-mtime und die mtimes von
  `ereignisse.jsonl`/`whatsapp_zuordnung.json` sind vor/nach allen Laeufen
  **unveraendert**; die DB wurde nur per `mode=ro` gelesen.

## Ehrlich offen / Abweichungen zu den Planer-Erwartungen

1. **Summe der Treffer: 356.222 statt der Planer-Vorgabe 469.091.** Die
   Planer-Probe hat **alle** Chats mit ±1 Tag gezaehlt (auch Gruppen); das
   Werkzeug setzt die **beauftragte** Regel um — Gruppen zaehlen **nur am
   selben Tag** — und kommt deshalb auf die kleinere, aber richtige Summe. Die
   Planer-Vorgabe sagt ausdruecklich: die Live-Messung des Ausfuehrers zaehlt
   selbst.
2. **Ereignisse mit Nachrichten: 2.101 statt 2.102.** Genau **ein** Ereignis
   hatte Nachrichten **nur** ueber eine Gruppe ausserhalb des Ereignistags; mit
   der strengeren Gruppenregel faellt es heraus. Die Abweichung von 1 ist damit
   begruendet (nicht die sekundengenauen Grenzen, sondern die Gruppenregel).
3. **`fenster.tage` / `chat.fenster_tage`** sind als **Rand** in Tagen
   umgesetzt (Einzelchat `1` = ±1 Tag, Gruppe `0` = nur der Ereignistag), passend
   zur Quellenangabe `regel:einzel_1_tag|gruppe_0_tage`; `von`/`bis` sind die
   tatsaechlichen ISO-8601-Grenzen. Der Feinauftrag definiert `tage` nicht
   explizit.
4. **`kontakte_gesamt`** = Anzahl **verschiedener** Namen unter allen
   `beteiligte`-Eintraegen des Ereignisses; der Platzhalter `unbekannt` zaehlt
   **nicht** als Kontakt. Der Feinauftrag definiert den Zaehler nicht explizit.
5. **MSYS-Pfadfalle (eigener Bedienfehler, ehrlich):** ein erster Schreiblauf
   mit `--ausgabe "$HOME/..."` uebergab dem nativen Python den MSYS-Pfad
   `/c/Users/...`; Python legte die Datei daraufhin unter
   `C:\c\Users\sebas\foto_sortierung\chat_andockung_b.jsonl` an (**ausserhalb**
   des Repos, also kein Repo-Verstoss). Der Lauf wurde mit einem nativen Pfad
   (`C:/Users/sebas/...`) wiederholt; die echte Ausgabe liegt am Sollpfad
   `~/foto_sortierung/chat_andockung.jsonl`. Der Fehlpfad wurde gemaess der
   Regel „nichts loeschen" **nicht** entfernt.

## Schutz und Grenzen

* `msgstore.db` **nur lesend** (`file:...?mode=ro`) — nie geschrieben, kopiert,
  entschluesselt oder verschoben.
* Ausgabe enthaelt **keinen** Nachrichtentext und **keine** Klartext-Nummer
  (nur Masken `***1234`); Namen nur, wenn die Zuordnung sie liefert.
* **Nichts geloescht** im Bestand (einzige Entfernung im Quelltext: die eigene
  temp-Datei beim fehlgeschlagenen atomaren Schreiben).
* Ausgaben ausschliesslich **ausserhalb** des Repos; keine echten Personen-,
  Gruppen-, Orts- oder Ereignisnamen und keine echten Kennungen in Repo-Dateien.
* Fremde Parallelarbeit (`tools/whatsapp/*`, `backend/scripts/*`,
  `docs/experimente/live_zahlen.*`) wurde **nicht** angefasst; **keine**
  `git`-Befehle (macht der Planer).

## Pruefer-Runde 1

Ein **unabhaengiger Pruefer** (frische Modellfamilie, `openai/gpt-5.6-luna`) hat
den Bau vollstaendig geprueft. Er hat **ausser einem Punkt nichts gefunden**:
die Tests sicherten die **nur-lesende** Eigenschaft der privaten `msgstore.db`
**nicht selbst** ab — die Live-Pruefung (mtime unveraendert) war separat
gefahren und erfolgreich, aber es fehlte ein **dauerhafter** Test, der die
Schreibsperre belegt. **Behoben in dieser Runde:** zwei Testfunktionen ergaenzt —
`test_schreibsperre_ist_belegt` (die `db_oeffnen`-Verbindung laesst kein
`INSERT`/`UPDATE`/`CREATE TABLE` zu → `sqlite3.OperationalError`) und
`test_eingaben_bleiben_byte_und_mtime_identisch` (voller Lauf Laden + Andocken +
Schreiben; **Bytes und mtime** jeder Eingabedatei hinterher exakt unveraendert).
Beide **offline**: erfundene Tabellen und Zeilen, Attrappen-Dateien im
`tmp_path`, keine echte `msgstore.db`, keine Datei unter `~/foto_sortierung/`.

**Pruefbefehl nach der Ergaenzung** selbst gefahren:
`cd backend && .venv/Scripts/python -m pytest tests/ -q` → **2.232 passed,
3 warnings, Exit 0** (vorher **2.230**; **+2** = die zwei neuen Testfunktionen).
Am Werkzeug selbst wurde dabei **nichts** geaendert.

## Offen

* Der Pruefer-Lauf ist **erledigt** (siehe Abschnitt „Pruefer-Runde 1"): kein
  offener Punkt mehr aus der Pruefung. Der einzige Fund — der fehlende
  Schreibsperren-Test — ist **ergaenzt**.
* Schritte **3–5** von N27 fehlen; Personen kommen bewusst erst in Schritt 4 und
  **nur nach Bestaetigung** durch den Nutzer.
* Die Plan-Journal-Zeile ergaenzt der **Planer**.
