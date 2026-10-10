# Falsche Zeitpunkte in den Archiv-Fundstellen — und der Zustand des Wissensspeichers — 10.10.2026

## Anlass

Sebastian, 10.10.2026 um 07:00: „**Falsche Daten** in den Verweisen auf die
Chat-Archive (ChatGPT, Claude, Gemini): die Belegstellen nennen Zeitpunkte, die
nicht stimmen. Zu pruefen ist die Datumsermittlung im Archiv-Index."

Diese Arbeit hat **gemessen statt geraten** — am echten Index
(`Chats von GPT, GEMINI, Claude/db/archiv_index.db`, 447 MB, nur lesend: 52.679
Chunks, 282.029 Nachrichten).

## Befund 1: das Zitat nennt den ersten Tag des Abschnitts, nicht den Tag der Stelle

`chunks.beginn` ist der Zeitstempel des **ersten**, `chunks.ende` der des
**letzten** Eintrags eines Abschnitts (Chunk). Zitiert wurde in allen vier
Anzeigewegen nur `beginn[:10]`:

* `router/chat.py` (`_archiv_tool`, die Notiz an das Modell),
* `services/llm_service.py` (`_build_archiv_context`, der System-Prompt),
* `services/werkzeuge.py` (`archiv_suchen`),
* `services/archiv_suche.py` (`_datum_kurz`, der Chronik-/Erwaehnungsweg).

Steht der gesuchte Satz spaeter im Abschnitt, nennt das Zitat einen **falschen
Tag**. Gemessene Groesse des Fehlers:

| Quelle | Chunks | mehr als ein Tag | Anteil |
|---|---|---|---|
| whatsapp | 21.788 | 9.165 | 42,1 % |
| chatgpt | 19.443 | 72 | 0,4 % |
| gemini | 4.537 | 8 | 0,2 % |
| claude-ai | 3.280 | 10 | 0,3 % |
| claude-code | 3.185 | 8 | 0,3 % |

Weitester Einzelfall: ein ChatGPT-Abschnitt von **11.02. bis 13.06.2025**
(Chunk 1342, Nachrichten 5.515/5.516 und 7.703) — ein Zitat aus dem Juni wurde
als „11.02." ausgegeben.

Gegenprobe, damit keine Vermutung stehenbleibt: `chunks.beginn` ist tatsaechlich
der erste Eintrag (Stichprobe 200 Chunks: in allen 200 innerhalb ±60 Sekunden).
Die FTS-Zeilen sind ebenfalls sauber (`rowid` = `chunks.id`, Texte identisch,
Stichprobe 40/40) — die Ursache liegt also im Zitat, nicht im Index.

## Befund 2: der Zustand des Wissensspeichers meldete sich faelschlich als „nicht verfuegbar"

`archiv_service.status()` las die Nachrichtentabelle `messages` — der echte
Index heisst `nachrichten` (so steht es im Schema von `archiv_suche.SCHEMA_SQL`).
Gemessen am echten Index:

```
Archiv-Status nicht lesbar: no such table: messages
status: {'verfuegbar': False, 'fehler': 'no such table: messages'}
```

Gleichzeitig lief die Suche einwandfrei (3 Treffer). Ein Zustand, der sich bei
241.402 Nachrichten als „nicht verfuegbar" ausgibt, schickt jeden auf die
falsche Spur.

## Was jetzt anders ist

* Neu `archiv_service.zeitraum_kurz(beginn, ende)`: **gleicher Tag → ein Datum,
  sonst die Spanne** (`2026-02-11–2026-06-13`). Fehlt `ende` (aeltere Aufrufer,
  Attrappen), bleibt es wie vorher beim Einzeldatum — keine harte Umstellung.
* Alle vier Anzeigewege nennen jetzt Tag oder Spanne. `archiv_suche._datum_kurz`
  kann dasselbe (eigener kleiner Helfer, damit dieses Modul ohne den Dienst
  auskommt) — beide Wege rechnen auf dieselbe Weise, sonst gaebe es zwei
  Wahrheiten.
* `suche()` und `semantische_suche()` tragen `ende` mit durch (vorher fehlte es
  im Ergebnis ganz — ohne `ende` kann kein Zitat die Spanne bilden).
* `status()` liest die Nachrichtentabelle unter beiden Namen (`nachrichten`,
  sonst `messages`) und nennt die benutzte Tabelle als
  `nachrichten_tabelle` — der alte Index, die Handy-Heimkopie und der neue
  Stand bleiben lesbar.

## Belege

* Tests: `backend/tests/test_archiv_datum_und_status.py` — **10 neue Tests**
  (Tag/Spanne/fehlendes `ende`, Notiz an das Modell, System-Prompt, Suche
  liefert `ende`, Zustand mit beiden Tabellennamen). Der Test der alten
  Tabelle `messages` ist der Rueckwaerts-Schutz.
* Der bestehende Test `test_archiv_tool.py` blieb unveraendert gruen: seine
  Treffer tragen kein `ende` — das ist der Rueckwaerts-Beleg.
* Pruefbefehl des Projekts: siehe Commit.

## Dateien

* `backend/app/services/archiv_service.py` — `zeitraum_kurz`, `ende` in beiden
  Suchwegen, Zustand unter beiden Tabellennamen.
* `backend/app/services/archiv_suche.py` — `_datum_kurz(wert, ende=None)`.
* `backend/app/router/chat.py`, `backend/app/services/llm_service.py`,
  `backend/app/services/werkzeuge.py` — Zitat mit Tag oder Spanne.
* `backend/tests/test_archiv_datum_und_status.py` — neu.

## Ehrlich offen

* Die zweite Haelfte der Beschwerde — „kein Gespraechsfluss, die Verweise
  wirken wie Striche statt wie Rede" — ist **nicht** angefasst: das gehoert in
  den Auftrag des Antwort-Wegs (Prompt), nicht in den Index.
* Ob Sebastian genau diese Faelle gesehen hat, laesst sich nicht mehr
  feststellen: sein Chat-Verlauf liegt auf dem Handy, am PC gibt es keine
  Kopie. Belegt ist der Fehler selbst — nicht, dass es sein Beispiel war.
