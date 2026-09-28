# Feinauftrag N27b — Chat-Andockung (Verknüpfungsschicht N27, Schritt 2 von 5)

> Auftraggeber: Planer (Hauptkontext, Nachtlauf). Ausführer: Hermes-Subagent
> (`deepseek-v4.1-flash`) — **kein** Codex (Kontingent gesperrt). Prüfer:
> frischer Kontext, **andere Modellfamilie** (`openai/gpt-5.6-luna`).
> Auftrag lesen, dann bauen. Sprache der Dateien: **Deutsch** wie die
> Nachbarmodule (`ereignisse_bauen.py`, `zuordnung_bauen.py`).

## Ziel

Je **Ereignis-Knoten** aus Schritt 1 die **Chat-Nachrichten im Zeitfenster**
andocken: welche Chats waren rund um den Tag aktiv, wie viele Nachrichten,
**welche Kontakte** haben geschrieben. Gespeichert werden **Kennungen und
Zählungen — niemals Nachrichtentext**.

## Werkzeug

`tools/foto_sortierung/chat_andocken.py` (neue Datei), Modul-Docstring mit
„Warum / Was es bewusst NICHT tut / Eingabe / Ausgabe / Regeln / Zählregeln"
(Aufbau wie `ereignisse_bauen.py`).

### Eingaben (alle **nur lesend**)

1. `--ereignisse` — Standard `~/foto_sortierung/ereignisse.jsonl`
   (JSONL-Linien aus N27a; gelesen werden `kennung`, `anlass_id`, `datum`,
   `art`; unbekannte Schlüssel ignorieren).
2. `--db` — Standard `msgstore.db` (Pfad unten). Wird **ausschließlich** über
   `sqlite3.connect("file:<pfad>?mode=ro", uri=True)` geöffnet.
3. `--zuordnung` — Standard `~/foto_sortierung/whatsapp_zuordnung.json`
   (aus `tools/whatsapp/zuordnung_bauen.py`: je `chat_row_id` → `art`,
   `telefonbuch_namen`, `whatsapp_name`, `nummer_maske`, `teilnehmer`).

Standardpfad der Datenbank (wörtlich so im Code, **außerhalb** des Repos):

```
C:\Users\sebas\Desktop\workspace agentic engineering\Chats von GPT, GEMINI, Claude
  \whatsapp_uebertragung\backup-decrypted\Databases\msgstore.db
```

### Zeitfenster (Regel, nicht Auslegung)

* **Einzelchat** (`art` = `einzel`/`sonstiges`): **±1 Tag** um das Ereignis-Datum
  → `[datum 00:00, datum+2 Tage 00:00)` in UTC-Millisekunden.
* **Gruppe** (`art` = `gruppe`): **strenger**, nur **derselbe Tag**
  → `[datum 00:00, datum+1 Tag 00:00)`.
* `newsletter`: wie Einzelchat (±1 Tag), aber eigener Zähler (kein Kontakt).
* Datum ohne Uhrzeit = Tagesdatum (UTC). Ereignisse **ohne** Datum: Knoten
  wird geführt, `nachrichten_gesamt: 0`, `fenster: null`.

### Ausgabe (eingefrorenes Schema, JSONL)

`--ausgabe`, Standard `~/foto_sortierung/chat_andockung.jsonl`. **Je Zeile
genau ein Ereignis**, `ensure_ascii=True`, `sort_keys=True`, sortiert nach
`datum` aufsteigend, bei Gleichstand `kennung` aufsteigend (datiert vor
undatiert, wie in N27a):

```
{"anlass_id", "art": "chat_andockung", "fenster": {"von", "bis", "tage"},
 "kennung": "E-" + anlass_id, "kontakte_gesamt", "nachrichten_gesamt",
 "chats": [ {"art", "beteiligte": [{"name", "nummer_maske", "nachrichten"}],
             "chat_name", "chat_row_id", "erste", "fenster_tage", "gekuerzt",
             "letzte", "medien", "nachrichten", "nachrichten_kennungen",
             "von_anderen", "von_mir"} ],
 "chats_anzahl", "datum", "quellen": {...}, "stand"}
```

* `erste`/`letzte` = ISO-8601 (UTC, `+00:00`) der ersten/letzten Nachricht
  dieses Chats im Fenster.
* `nachrichten_kennungen` = `message._id`-Werte aufsteigend, **höchstens 25**
  je Chat; `gekuerzt: true`, wenn mehr im Fenster liegen. **Kein** Text —
  es gibt im Schema **kein** Feld für Nachrichteninhalt (Test prüft das).
* `beteiligte` = Absender (`from_me = 0`) im Fenster, absteigend nach
  Nachrichtenzahl, bei Gleichstand Name aufsteigend.
* `chat_name`: Gruppen → `chat.subject` aus der DB (echter Gruppenname);
  Einzelchat → `telefonbuch_namen[0]`, sonst `whatsapp_name`, sonst
  `"unbekannt"`; fehlt der Chat in der Zuordnung → `"unbekannt"`.
  **Nie** eine Nummer im Klartext — der Name nur, wenn die Zuordnung ihn
  liefert.
* `quellen` nennt ehrlich, woher jedes Feld stammt, z. B.
  `{"datum": "ereignisse.jsonl", "fenster": "regel:einzel_1_tag|gruppe_0_tage",
    "nachrichten": "msgstore.db:message", "namen": "whatsapp_zuordnung.json",
    "medien": "msgstore.db:message_media"}`.

### Namensauflösung für Absender (kein Raten!)

* Einzelchat: der Partner ist die eine Person der Zuordnung → `name` =
  `telefonbuch_namen[0]` / `whatsapp_name` / `"unbekannt"`, `nummer_maske` aus
  der Zuordnung.
* Gruppe: die Absender-Nummer aus `jid.user` (`sender_jid_row_id` →
  `jid._id`) auf **letzte 4 Ziffern** maskieren und gegen die `teilnehmer`
  dieser Gruppe abgleichen. **Nur wenn genau ein Name übrig bleibt**, steht
  er in `name`; sonst `"unbekannt"`. Bei mehreren Treffern mit
  **verschiedenen** Namen ebenfalls `"unbekannt"` (kein Münzwurf) — die
  Maske bleibt trotzdem stehen, damit nachprüfbar ist.
* `from_me = 1` zählt in `von_mir` und erscheint **nicht** unter `beteiligte`.
* `sender_jid_row_id IS NULL` → `von_anderen` zählt mit, `beteiligte` nicht.

### CLI und Schutz (wie `ereignisse_bauen.py`)

* `--trocken` ist der **Standard**; `--schreiben` schreibt atomar
  (temp-Datei im Zielordner + `os.replace`).
* Ziel **im Repo** → deutsche Meldung + **Exit 2**, nichts geschrieben.
  Repo-Wurzel wie in `ereignisse_bauen.py` über `REPO` bestimmen.
* `--limit N` für die Konsolen-Vorschau (Standard 5).
* Nur Standardbibliothek (`argparse`, `bisect`, `datetime`, `json`, `os`,
  `sqlite3`, `sys`) — **kein** `requests`/`httpx`, **kein** Bildmodul.
* **Kein** pCloud-Aufruf, **kein** Download, **keine** Bilddatei.
* Einzige Entfernung im Quelltext: `os.remove` auf die **eigene** temp-Datei.
* Ausgabe enthält **keine** Telefonnummern im Klartext und **keinen**
  Nachrichtentext; die DB wird nur gelesen (die Werkzeug-Tests prüfen, dass
  die Datei-mtime unverändert bleibt und dass „INSERT/UPDATE/DELETE" im
  Quelltext nicht vorkommen).

## Vorgehen im Code (gemessen vom Planer, bitte so bauen)

Die naive Abfrage je Ereignis ist **zu langsam** (2.127 `COUNT(*)`-Abfragen
haben den Planer-Lauf über 3 Minuten getrieben). Richtiger Weg:

1. `SELECT m.timestamp, m.chat_row_id, m.from_me, m.sender_jid_row_id FROM message m`
   → **ein** Scan über 245.657 Zeilen (gemessen: 245.208 mit Chat-Bezug).
2. Nach `timestamp` sortierte Liste + `bisect` für die Fenstergrenzen.
3. `chat`/`jid` einmal laden (`chat._id → subject`, `jid._id → user`).
4. `message_media` einmal aggregieren (`chat_row_id`, `timestamp`-Bezug über
   `message`-Join) → `medien` je Chat im Fenster.
5. Je Ereignis nur noch Listen-Schnitte.

## Messwerte des Planers (Vorgabe für die Live-Messung)

* Nachrichten: **245.657** Zeilen, Zeitraum **2014-08-29 … 2026-09-25**.
* Ereignisse: **2.127** (alle mit Datum).
* Ereignisse mit Nachrichten im Fenster ±1 Tag: **2.102** (98,8 %).
* Summe der Treffer über alle Ereignisse: **469.091** (Mehrfachzählung
  erwartet — dasselbe Chat-Fenster trifft mehrere Ereignisse), Maximum je
  Ereignis **895**.
* `from_me = 1`: **81.262** Nachrichten.
Diese Zahlen sind **Planer-Messungen** (eigene Probe). Sie dürfen beim Bauen
als Erwartung dienen, **aber nicht** abgeschrieben werden — die Live-Messung
des Ausführers zählt selbst.

## Tests (`backend/tests/test_chat_andocken.py`, alles offline)

* Attrappen-Datenbank **in-memory** (`sqlite3.connect(":memory:")`) mit den
  vier Tabellen `message`, `chat`, `jid`, `message_media` in **kleinem**
  Umfang; erfundene Namen (keine echten Personen, Orte, Kennungen).
* Mindestens: Fenster-Grenzen exakt (23:59:59 des Vortags fällt hinein,
  00:00 des +2. Tages nicht), Gruppe strenger als Einzelchat, undatiertes
  Ereignis, Kürzung auf 25 Kennungen + `gekuerzt`, Namensauflösung
  eindeutig/mehrdeutig/fehlend, `from_me` zählt nur in `von_mir`,
  leere Zuordnung, fehlende DB → deutsche Fehlermeldung + Exit ≠ 0,
  Repo-Ziel → Exit 2, `--trocken` schreibt nichts, `--schreiben` schreibt
  atomar (keine `*.tmp`-Reste), Sortierung stabil, Zähl-Invarianten
  (`chats_anzahl == len(chats)`, `nachrichten_gesamt == Summe der
  Chat-Zahlen`, `von_mir + von_anderen == nachrichten`),
  **kein Textfeld im Schema**, kein `INSERT`/`UPDATE`/`DELETE` im Quelltext.
* Tests dürfen **kein** `msgstore.db` und **keine** Datei unter
  `~/foto_sortierung/` verwenden.

## Acceptance (Prüfkriterien für den Prüfer)

1. Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
   **Exit 0**, Zahl **größer 2.204** (Baseline vor diesem Schritt, selbst
   gefahren vom Planer).
2. Live-Trockenlauf gegen den echten Bestand liefert **2.127** Zeilen,
   `chats_anzahl`/`nachrichten_gesamt` stimmen mit einer **unabhängigen
   Zählung** (eigene SQL-Abfrage des Prüfers) überein; die Zahl der Ereignisse
   **mit** Nachrichten ist in der Größenordnung **2.102** (Abweichung
   begründbar, weil die Zählgrenzen sekundengenau sind).
3. Zweiter Lauf bei **vorgegebenem** `stand` ist **byte-gleich**
   (Prüfsumme); ohne `stand` unterscheiden sich die Läufe nur im Feld `stand`.
4. Repo-Ziel → **Exit 2**, nichts geschrieben; `msgstore.db`-mtime und
   `ereignisse.jsonl` vorher/nachher **unverändert**.
5. Keine Nachrichtentexte, keine Klartext-Nummern, keine Bilder, kein Netz.
6. Changelog `docs/changelog-2026-09-28-n27b-chat-andockung.md` mit den
   **gemessenen** Zahlen (nicht den Planer-Erwartungen) und den ehrlich
   offenen Punkten; Plan-Journal-Zeile ergänzt der **Planer**.
7. **Keine** echten Personennamen, Gruppen-/Orts-/Ereignisnamen und keine
   echten Kennungen in Repo-Dateien (Code, Tests, Changelog) — Datenschutz.
   Die Ausgabedatei liegt **außerhalb** des Repos.

## Verboten

* `git`-Befehle jeder Art (macht der Planer).
* Löschen (auch keinen Ordner aufräumen) — Ausnahme: die eigene temp-Datei.
* `msgstore.db` schreiben, kopieren, entschlüsseln oder verschieben.
* Dateien des zweiten Agenten anfassen (`tools/whatsapp/*`,
  `backend/scripts/*`, `docs/experimente/live_zahlen.*`).