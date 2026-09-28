# Changelog 28.09.2026 — WhatsApp-Vollimport (Handy-Sicherung -> Archiv)

**Auftrag:** Die entschluesselte Handy-Sicherung (`msgstore.db`, 245.657
Nachrichten aus 2.471 Chats) ins Archiv uebernehmen: normalisieren, an den
bestehenden Bestand **anhaengen** (kein Neuaufbau), Index und Einbettungen
**inkrementell** ergaenzen, Kosten protokollieren (Grenze 1,00 USD). In
Bericht, Log und Repo erscheinen nur Zahlen — keine Namen, keine Nummern,
keine Nachrichteninhalte.

## Was gebaut wurde

- **`backend/scripts/whatsapp_db_import.py`** (neu, ~600 Zeilen) — liest
  `msgstore.db` **nur lesend** (`file:...?mode=ro`) und haengt neue Zeilen an
  `normalized/messages.jsonl` an:
  - **Feldgleichheit** mit dem Bestand: `conversation_id, source, timestamp,
    role, text, title, project`, `source = "whatsapp"`, Zeitstempel ISO/UTC
    (Sekunden), Rollen `user` / `kontakt` / `system` (eigene Nachrichten =
    `user`), Zeilenende CRLF wie der WhatsApp-Block vom 25.09.
  - **Kategorien:** Text (inkl. Untertitel), Anhang-Platzhalter
    (`<Dateiname> (Datei angehaengt)`), geloeschte Nachrichten (zwei Wortlaute
    je eigener/fremder), Anrufe (`Verpasster`-Praefix bei Dauer 0),
    Standorte (`Standort: <url>`). Ohne Text und ohne Anhang/Anruf/Standort
    wird **nichts** importiert (Systemzeilen), nur gezaehlt.
  - **Doppelungsschutz:** die bestehenden WhatsApp-Zeilen werden ueber
    `(Text, Minute)` wiedererkannt; ein Abgleich findet die bestehenden
    Gespraeche anhand von Textueberdeckung (Schwelle max(3 Zeilen, 15 %),
    Zweitbester muss unterlegen sein) und behaelt ihre Kennung bei.
  - **Kennungen** fuer neue Gespraeche aus der privaten Zuordnung
    (Telefonbuch > WhatsApp-Name > Maske `***1234` > `unbekannt-<chat_id>`,
    Gruppen aus `subject`, Kanaele aus `newsletter`). Kollisionen werden
    **innerhalb des Laufs** und deterministisch aufgeloest (`-2`, `-3`) —
    ein zweiter Aufruf erzeugt dieselben Kennungen und findet nichts Neues.
  - **Sicherung + Anhang:** vor dem Schreiben entsteht
    `normalized/messages_vor_import_<JJJJMMTT-HHMM>.jsonl`; geschrieben wird
    ausschliesslich im Modus `ab` (anhaengen). Bestehende Bytes bleiben
    unangetastet (nachgewiesen: Byte-Praefix der Datei ist identisch).
  - Trockenlauf ist der Standard; `--schreiben` schreibt.
- **`backend/scripts/archiv_index_ergaenzen.py`** (neu, ~600 Zeilen) —
  haengt danach an **zwei** Stellen an, statt neu zu bauen:
  1. **`db/memory.db` (Textschicht, kostenlos)** ueber die Werkzeuge des
     Archivs (`src.normalform`, `src.filter`, `src.chunker`, `src.speicher`)
     — dieselbe Zerlegung wie beim Bau, keine zweite Chunker-Implementierung.
     Chunks werden ueber Text-Fingerabdruck gegen Dubletten geprueft; die
     FTS-Suche wird neu aufgebaut.
  2. **`db/archiv_index.db` (Text, FTS, Vektoren)** — neue Nachrichten, neue
     Chunks, FTS-Zeilen, **nur fehlende** Vektoren (`hat_vektor = 0`), danach
     Auffrischen der betroffenen `gespraeche`-Zeilen und `meta` (Zaehler und
     Kosten werden **addiert**, die Bauwerte vom 25.09. bleiben erhalten).
  - **Budget-Grenze hart:** Schaetzung vor dem Lauf und Nachrechnen nach
    jedem Buendel; wird die Grenze gerissen, bricht der Lauf ab, ohne den
    Rest anzufassen (gerechnete Buendel bleiben, der Chunk steht weiter auf
    `hat_vektor = 0` und wird beim naechsten Aufruf nachgeholt).
  - Sicherungskopie des Index vor dem Schreiben
    (`archiv_index_vor_ergaenzung_<JJJJMMTT-HHMM>.db`), Wiederaufnahme-fest,
    doppelte Ausfuehrung haengt nichts doppelt an.
- **`backend/scripts/archiv_index_bauen.py`** (kleine Aenderung):
  `_schluessel_holen()` sucht den `OPENROUTER_API_KEY` jetzt auch in der
  `.env` der **Workspace-Wurzel** — dieselbe Reihenfolge, die `app/config.py`
  fuer den Dienst schon nutzt. Vorher fand das Bautool den Schluessel dort
  nicht.

## Gemessene Zahlen (Lauf vom 28.09.2026)

Quelle: `whatsapp_uebertragung/backup-decrypted/Databases/msgstore.db`
(Stand der Sicherung: 25.09.2026), Zeilen 29.08.2014 – 25.09.2026.

| Groesse | Wert |
|---|---|
| Chats in der Datenbank | 2.471 |
| ... mit mindestens einer Nachricht | 2.025 |
| Nachrichten gesamt | 245.657 |
| ... ohne Chat-Eintrag (verwaiste `chat_row_id`) | 449 in 217 Kennungen |
| Chats mit genau 1 Nachricht | 1.233 (1.459 Chats haben ≤3, davon 1.735 von 1.762 Zeilen Systemzeilen) |
| Nachrichten mit Text | 217.467 |
| Systemzeilen **mit** Text | 582 |
| Anhang-Platzhalter | 19.595 |
| geloeschte Nachrichten | 1.436 |
| Anrufe | 191 |
| Standorte (mit URL) | 17 |
| Systemzeilen **ohne** Text (uebersprungen) | 5.385 |
| sonstige ohne Text (uebersprungen) | 535 |
| **Duplikate zum Bestand** (uebersprungen) | **40.033** |
| ... davon Text-Treffer im grossen Bestandsgespraech | 38.388 von 42.138 Zeilen (Zweitbester: 11) |
| ... zweites Bestandsgespraech | 3 von 9 Zeilen |
| **Neu angehaengt** | **199.255 Zeilen** (81,1 % von 245.657) |
| davon neue Gespraechskennungen | 483 (Median 43 Zeilen, groesstes 43.046) |
| Zeichen neuer Text | 15.716.676 |
| Rollen der neuen Zeilen | `kontakt` 140.712 / `user` 57.961 / `system` 582 |
| Zeitraum der neuen Zeilen | 29.08.2014 – 25.09.2026 (UTC) |
| Zeilen ohne Zeitstempel im Import | 0 |

Fortschreibung der Dateien (nichts geaendert, nur angehaengt):

| Datei | vorher | nachher |
|---|---|---|
| `normalized/messages.jsonl` | 82.774 Zeilen / 59,3 MB | **282.029 Zeilen / 116,9 MB** |
| Sicherung daneben | — | `messages_vor_import_20260928-1151.jsonl` (59.329.747 B, Byte-Praefix identisch) |
| `db/memory.db` — `messages` | 82.774 | 282.029 |
| `db/memory.db` — `chunks` | 33.312 | **52.679** (+19.367; 234 Chunk-Dubletten uebersprungen) |
| `db/archiv_index.db` — `nachrichten` | 82.774 | 282.029 |
| `db/archiv_index.db` — `chunks` / `chunks_fts` | 33.312 / 33.312 | **52.679 / 52.679** |
| `db/archiv_index.db` — `vektoren` | 33.312 | **52.679** (0 Nullvektoren) |
| `db/archiv_index.db` — `gespraeche` | 1.111 | **1.590** (+479; 4 Gespraeche haben nur Nachrichten ohne Chunk — dieselbe Regel wie beim Bau) |
| `db/archiv_index.db` — Dateigroesse | 275,5 MB | **447,5 MB** |
| Sicherung daneben | — | `archiv_index_vor_ergaenzung_20260928-1203.db` |

## Kosten (protokolliert)

| Posten | Wert |
|---|---|
| Modell | `openai/text-embedding-3-small` (OpenRouter), 1.536 Dimensionen, float16 |
| Schaetzung vorher | 4.819.386 Token ≈ 0,0964 USD |
| **Tatsaechlich gezaehlt** | **5.636.408 Token = 0,112728 USD** |
| Grenze | 1,00 USD — eingehalten (11,3 %) |
| Dauer | 470,7 s (Textschicht ~30 s, Einbetten ~465 s, 194 Aufrufe) |
| Dauer gesamt (Anhang + Index) | ~504 s (Anhang `messages.jsonl` ~33 s, Index 470,7 s) |
| Index gesamt (Bau 25.09. + Ergaenzung) | 0,207989 + 0,112728 = **0,320717 USD** |

Keine weiteren Kosten: die Textschicht von `memory.db` kostet nichts, und die
Vektordatei von `memory.db` (siehe Befund) wurde bewusst nicht angefasst —
anderer Anbieter, andere Kostenhoheit.

## Befund: die Vektordatei von `memory.db` ist kaputt (nicht angefasst)

Gemessen, nicht vermutet:

- `db/memory.vektoren.f32` — die Datei, die `src/speicher.py` erwartet —
  **fehlt**.
- Daneben liegt `db/memory.vektoren [conflicted].f32` (33.312 Zeilen × 1.024
  float32): davon sind **30.902 Zeilen Nullvektoren**, nur 2.410 echt.
- `db/memory_vor_whatsapp_20260925-1524.vektoren.f32` (30.891 Zeilen) ist
  **komplett** null.
- `memory.db` meldet trotzdem `hat_vektor = 1` fuer **alle** 33.312 Chunks —
  ein normaler `python -m src.build_db`-Lauf wuerde also **nichts**
  nachrechnen, weil alles als fertig gilt.

Konsequenz: die Bedeutungssuche der Archiv-eigenen `memory.db` ist derzeit
wertlos; die Volltextsuche und der `archiv_index.db` (dort sind alle Vektoren
echt) sind es nicht. Empfehlung fuer einen eigenen, bezahlten Lauf (Mistral,
`mistral-embed`, 0,10 USD/Mio Token): `hat_vektor` fuer die Nullzeilen
zuruecksetzen, die echte Zeile als Erbe angeben und `src.build_db` mit
`--erbe-von` laufen lassen — Groessenordnung 30.900 Chunks ≈ 8 Mio Token
≈ 0,80 USD. **Nicht** in diesem Auftrag erledigt: anderer Anbieter, andere
Kostenhoheit.

## Gegenprobe (nach dem Schreiben, nur lesend gemessen)

- **Datei-Anhang:** `messages.jsonl` 282.029 Zeilen = 82.774 + 199.255; die
  Sicherung `messages_vor_import_20260928-1151.jsonl` hat 82.774 Zeilen, und
  `cmp -n 59329747` meldet zwischen Sicherung und neuer Datei **0
  Unterschiede** in den ersten 59.329.747 Bytes — es wurde nur angehaengt.
- **Altbestand unberuehrt:** Stichproben aus der Indexpflicht (5 Chunks: Text,
  Quelldatei, `hat_vektor`, **Vektor-Bytes**; 3 Nachrichten: Kennung, Quelle,
  Zeitstempel, Rolle, Text, Titel) sind gegen
  `archiv_index_vor_ergaenzung_20260928-1203.db` **identisch**.
- **Neue Vektoren echt:** 0 Nullvektoren unter den 19.367 neuen Vektoren.
- **Zaehler stimmen ueberein:** `nachrichten` = `chunks` = `chunks_fts` =
  `vektoren` = 52.679; `chunks` mit `hat_vektor = 0`: 0.
- **Idempotent:** Trockenlauf des Importers findet danach 239.288 Zeilen als
  Dubletten und **0 neue**; Trockenlauf der Index-Ergaenzung meldet **0 neue
  Nachrichten, 0 neue Chunks, 0 offene Vektoren**. Ein zweiter Aufruf aendert
  also nichts.

## Geheimnis-Regeln (eingehalten)

- stdout/stderr, Tests, Changelog und Commit nennen nur Zaehlungen und
  Kennungen — **keine** Namen, Rufnummern, Chatnamen oder Inhalte. Der
  Bericht des Importwerkzeugs wurde genau darauf getestet
  (`test_bericht_zaehlt_nur`).
- `msgstore.db` und die Inkrement-Dateien wurden **nur lesend** geoeffnet;
  nichts entschluesselt, nichts geladen, nichts geloescht.
- Der Archivordner bleibt per `.gitignore` gesperrt; der Index liegt weiter
  **im Archivordner**, nicht im Repo.

## Inkrement-Dateien (`msgstore-increment-1..3.db`) — geprueft, nicht importiert

Gemessen (Hex-Kopf, `zipfile`, SQLite-Open):

- Alle drei Dateien (53,1 / 63,5 / 63,8 KB) sind **keine SQLite-Datenbanken**.
  Der Kopf ist `50 4b 03 04` = **ZIP**; `sqlite3` bricht mit „file is not a
  database" ab. Die Hauptdatei beginnt dagegen mit `SQLite format 3`.
- Inhalt der Zips: das **Inkrement-Backup-Format von WhatsApp** — JSON-Deltas
  je Tabelle (`chat_modified_1.json`, `jid_modified_1.json`,
  `receipt_*`, `group_participant_*`, `props_*`, `sequences.json`) und je eine
  binaere `messages.bin` (66,8 / 72,7 / 92,6 KB, Kopf z. B. `de 89 04 08 02` =
  Protobuf-Wire-Format), dazu `header.json`.
- **Es gibt keine `message`-Tabelle** und damit keine Zeilen, die sich ohne
  einen Parser fuer dieses Format uebernehmen liessen. Ehrliches Ergebnis:
  **nicht importiert, kein Raten.** Die Hauptdatei `msgstore.db` deckt den
  Zeitraum bis 25.09.2026 vollstaendig ab (245.657 Zeilen, min/max
  1.409.329.412.000 – 1.790.337.637.000 ms).
- Falls die Inkremente spaeter interessant werden: `header.json` nennt Format
  und Geraet, `messages.bin` ist ohne Formatkenntnis nicht deutbar — das ist
  ein eigener Auftrag, nicht Teil dieses Imports.

## Tests

- Neu: **`backend/tests/test_whatsapp_db_import.py`** — 25 Offline-Tests
  (Attrappen-Schema, erfundene Daten: Rollen, Anhang-Platzhalter, geloeschte
  Nachrichten, Anrufe, Standort, Systemzeilen, unsichtbare Steuerzeichen,
  Kennungen/Titel, Kollisionen, Dubletten, Wiederholbarkeit, Sicherung,
  Bericht ohne Inhalte).
- Neu: **`backend/tests/test_archiv_index_ergaenzen.py`** — 15 Offline-Tests
  (nur neue Zeilen, Altbestand unveraendert inkl. Vektor-Bytes, FTS,
  Gespraechs-Zaehler, Kostenaddition, Sicherung, Wiederholbarkeit,
  Budget-Abbruch vor dem Lauf und mitten im Lauf, Fortsetzbarkeit).
- Pruefbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  -> **1.937 passed**, Exit 0 (vorher 1.922 mit den 25 Import-Tests, davor
  1.897; die 15 Index-Tests sind neu).
