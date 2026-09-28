# Auftrag N27c — Kalender-Andockung (Verknüpfungsschicht N27, Schritt 3 von 5)

> Eingefrorener Auftrag (Rollen-Regel `CLAUDE_EXTENDS.md` §6.6).
> **Ausführer:** genau dieser Schritt. **Prüfer:** anderer Kontext/andere Familie
> gegen **diesen** Auftrag, führt den Prüfbefehl selbst aus.
> **Planer/Committer:** Hauptagent (nachtlauf-2026-09-26, Zeile N27 Schritt 3).

## Ziel in einem Satz

Je **Ereignis-Knoten** (Anlass aus `ereignisse.jsonl`) die **passenden
Kalender-Termine** anhängen — inklusive **jährlich wiederkehrender Geburtstage** —
und das Ergebnis als eigene Datei **außerhalb des Repos** ablegen.

## Eingaben (nur lesen)

| Quelle | Pfad | Rolle |
|---|---|---|
| Ereignis-Knoten | `C:/Users/sebas/foto_sortierung/ereignisse.jsonl` (2.127 Zeilen) | je Schritt-1-Knoten: `anlass_id`, `datum` (`JJJJ-MM-TT`), `thema`, `kategorie`, `event`, `ziel_ordner` |
| Google Kalender (ics) im Takeout-Zip | `C:/Users/sebas/Desktop/workspace agentic engineering/Chats von GPT, GEMINI, Claude/raw/takeout-20260812T203313Z-3-001.zip` → `Takeout/Kalender/*.ics` (Vorgabe: **alle** Kalenderdateien darin, automatisch gefunden) | Termine; **ausschließlich per `zipfile`** gelesen, nie entpackt, nie kopiert |

Pfade **konfigurierbar** (CLI-Schalter `--ereignisse`, `--zip`, `--mitglied`,
`--ausgabe`, `--stand`), übrige Standardwerte genau wie oben. **Nachtrag
(28.09., nach dem Bau):** der Vorgabewert für `--mitglied` ist **leer** — es
werden alle `Takeout/Kalender/*.ics` gelesen. Grund: ein fest eingetragener
Dateiname ist eine Mailadresse und hat im Repo nichts zu suchen (die Konsole
nennt deshalb nur die **Anzahl** gefundener Kalenderdateien). Ein ausdrücklich
genannter, aber fehlender Eintrag bleibt ein Klartextfehler.
**Kein** Kopieren, Entpacken oder Verschieben der Eingaben.

## Ausgabe (schreiben nur mit `--schreiben`)

`C:/Users/sebas/foto_sortierung/kalender_andockung.jsonl` — eine Zeile je
Ereignis-Knoten, **gleiche Reihenfolge** wie die Eingabe, **UTF-8 ohne BOM**:

```json
{"anlass_id": "JJJJ-MM-TT_Anlass-XX", "datum": "JJJJ-MM-TT",
 "art": "kalender_andockung", "kennung": "K-JJJJ-MM-TT_Anlass-XX",
 "anzahl_treffer": 2, "anzahl_nah": 3,
 "treffer": [{"titel": "…", "beginn": "JJJJ-MM-TT", "ende": "JJJJ-MM-TT",
              "ganztags": true, "wiederkehrend": false, "quelle": "ics"}],
 "stand": "…"}
```

* `treffer` = Termine **am selben Tag** wie der Anlass (auch mehrtägige, die
  diesen Tag enthalten).
* `nah` = Termine **±1 Tag** — nur als **schwacher Hinweis** gezählt
  (`anzahl_nah`), **nicht** in `treffer` (Lehre aus N6e: ein bloß benachbartes
  Datum ist kein Beleg). Ein Schalter `--auch-nah` darf sie zusätzlich in
  `treffer` aufnehmen; Standard = aus.
* **Jährliche Wiederkehr:** Termine mit `RRULE` und `FREQ=YEARLY` (typisch
  Geburtstage) treffen über **Tag+Monat** — unabhängig vom Jahr; Feld
  `wiederkehrend: true`, `beginn` ist das **Anlass-Jahr** + Monat/Tag. Ebenso
  Termine, deren `TITEL` „Geburtstag“ oder „Jahrestag“ enthält **und** die ein
  vollständiges Datum haben (Rückfall, falls keine `RRULE` gesetzt ist).
* `titel` auf **120 Zeichen** gekürzt; **kein** weiterer Termin-Text
  (`DESCRIPTION`, `LOCATION`) wird übernommen.
* Datei wird **atomar** geschrieben (temp im Zielordner + `os.replace`).

## Regeln (hart)

1. **`--trocken` ist der Standard.** Ohne `--schreiben` wird **nichts** auf Platte
   geschrieben; die Ausgabezeilen werden nur gezählt. Ein **Ziel im Repo** wird
   verweigert (deutsche Meldung, **Exit 2**) — auch mit `--schreiben`.
2. **Kein Netz, kein pCloud, keine Bilder, keine Datenbank.** Nur
   Standardbibliothek (`zipfile`, `json`, `datetime`, `os`, `argparse`,
   `hashlib` erlaubt). Keine neue Abhängigkeit.
3. **Keine Löschfunktion** im Werkzeug — als einzige Entfernung ist
   `os.remove(temp)` auf die **eigene** temp-Datei erlaubt.
4. **Zweiter Lauf = kein Schaden:** zweimal `--schreiben` mit festem `stand`
   ergibt **byte-gleiche** Dateien; die Eingaben bleiben byte- und mtime-identisch.
5. **Datenschutz:** Die Ausgabedatei liegt **außerhalb** des Repos und darf
   Termin-Titel tragen (privat). **Im Repo** (Code, Tests, Doku) stehen
   **keine** echten Termin-, Orts- oder Personennamen: Tests arbeiten mit
   **erfundenen** Beispielen (z. B. `Beispiel-Geburtstag`, `2014-03-30_Beispiel-01`).
6. **Ehrlich ausgeben:** die Konsole nennt die Zahlen, die wirklich gelten
   (Ereignisse, Treffer-Zeilen, Termine am Tag, `nah`-Treffer, wiederkehrende
   Treffer, übersprungen/unlesbar). Keine geschönte Zahl, keine Null, die
   „alles gut“ bedeuten soll.

## ICS-Leser (eigene, kleine Umsetzung — kein neues Paket)

* Zeilenweise falten auflösen (Fortsetzungszeilen beginnen mit Leerzeichen/Tab),
  `VEVENT`-Blöcke einsammeln, Eigenschaften `DTSTART`, `DTEND`, `SUMMARY`,
  `RRULE`, `UID` lesen; `DTSTART;VALUE=DATE:20200315`, `DTSTART:20200315T180000Z`
  und lokale Zeiten ohne `Z` müssen erkannt werden (Zeitzonen **nicht** umrechnen:
  das Datum wird aus den ersten 8 Ziffern gelesen).
* Fehlende/defekte Blöcke werden **gezählt und gemeldet**, nie still verschluckt.
* Ganztags = `VALUE=DATE` oder fehlende Uhrzeit.

## Abgabe (genau diese Dateien)

1. `tools/foto_sortierung/kalender_andocken.py` — Werkzeug (deutsche Meldungen,
   englisches Coding, Docstring-Kopf mit Aufrufhinweis)
2. `backend/tests/test_kalender_andockung.py` — **nur offline**, `tmp_path`,
   erfundene ICS-Beispiele in-memory, kein Netz, keine echten Namen
   (Ziel: ≥ 25 Testfunktionen; Abdeckung: Fensterregel Tag/±1, Jährlich über
   `RRULE`, Jährlich über Titel-Rückfall, Ganztags vs. Zeit, mehrtägiger Termin,
   defekter Block, Idempotenz, Repo-Ziel Exit 2, kein Löschen, keine
   Netz-/Bild-Importe, `--trocken` schreibt nichts, Titel-Kürzung)
3. `docs/changelog-2026-09-28-n27c-kalender-andockung.md` — Zahlen des Live-Laufs
   + Aufrufe + Prüfbefehl mit Exit-Code

**Keine** git-Befehle (Commit macht der Planer). Der Prüfbefehl lautet:
`cd backend && .venv/Scripts/python -m pytest tests/ -q` (muss Exit 0 liefern).

## Prüfkriterien (woran der Prüfer den Schritt abnimmt)

* Prüfbefehl selbst gefahren → Exit 0, Zahl genannt.
* Live-Trockenlauf gegen die **echten** Eingaben liefert: Anzahl Ereignisse
  (= 2.127), Zeilen mit Treffern, Termine am Tag, `nah`-Treffer, wiederkehrende
  Treffer, defekte Blöcke.
* Zwei `--schreiben`-Läufe in einen **frischen** Ordner (außerhalb des Repos) mit
  festem `stand` → byte-gleich; Eingaben (Größe + mtime + sha256) unverändert;
  `manifest.jsonl` bleibt unberührt; **nichts** gelöscht.
* Repo-Ziel mit `--schreiben` → **Exit 2**, keine Datei entsteht.
* Keine echten Namen/Orte/Kennungen in den drei Repo-Dateien (der Prüfer sucht
  selbst). Keine Lösch-/Netz-/Bildfunktion im Quelltext.
* zweiter Lauf = idempotent.
