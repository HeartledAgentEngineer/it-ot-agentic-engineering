# N11 (Teil A) — Kleine Fotos-Übersicht als Datendatei

**Datum:** 27.09.2026 · **Schritt:** N11, Teil A (Nachtlauf)
**Auftrag:** `docs/auftrag-n11-foto-uebersicht.md` (Abschnitte „Harte Regeln“,
„Eingefrorene Schnittstelle“, „Teil A“)
**Ausführer:** Hermes-Subagent (`deepseek-v4.1-flash`) — Teil B (Endpunkt,
Chat-Anschluss, Selbsttest) baut ein zweiter Subagent parallel.

## Warum dieser Schritt

Am Handy lassen sich Fragen wie „wie viele Events gab es?“ oder „zeig mir die
Urlaube 2021“ heute nicht beantworten: Sortierschlüssel, `themen.jsonl` und
`kategorien.json` liegen **nur auf dem PC**. `sortierplan.json` (N7, Trockenlauf)
enthält aber bereits alle Zahlen und Event-Namen. Teil A zieht daraus **eine
kleine Datei** — Zahlen und Namen, sonst nichts. Teil B liest sie für den
Endpunkt `/api/fotos/uebersicht` und die Notiz im Chat.

## Neu gebaut

| Datei | Umfang |
|---|---|
| `tools/foto_sortierung/foto_uebersicht.py` | 566 Zeilen |
| `backend/tests/test_foto_uebersicht_werkzeug.py` | 846 Zeilen, **98 Testfunktionen** |
| `docs/changelog-2026-09-27-n11-uebersicht-datei.md` | diese Doku |

### Schnittstelle (eingefroren, wortgleich zum Auftrag)

```json
{
  "version": 1,
  "art": "foto_uebersicht",
  "stand": "2026-09-27T22:30:00+02:00",
  "quelle": {"plan_stand": "2026-09-27T13:49:46+02:00", "trocken": true},
  "zahlen": {"zeilen", "anlaesse", "zuege", "events", "events_neu",
             "events_wiederverwendet", "ordner_neu", "ordner_vorhanden",
             "themen", "kategorien", "doppelung_gesamt",
             "doppelung_ohne_anlass", "doppelung_uebersprungen",
             "ohne_thema", "ohne_jahr", "ohne_datum", "jahre"},
  "jahre": [{"jahr", "anlaesse", "dateien", "events"}],
  "themen": [{"thema", "anlaesse", "dateien"}],
  "kategorien": [{"kategorie", "anlaesse", "dateien", "events"}],
  "events": [{"jahr", "kategorie", "name", "dateien", "quelle"}]
}
```

Schlüsselnamen, Typen und Sortierungen sind exakt wie im Auftrag; die
Schlüsselreihenfolge in der Datei ist die Reihenfolge des Schemas. Sortiert
wird: `jahre` aufsteigend nach `jahr`; `themen`/`kategorien` absteigend nach
`anlaesse`, bei Gleichstand alphabetisch; `events` aufsteigend nach `jahr`, dann
alphabetisch nach `name` (die Kategorie als dritter Schlüssel macht die
Reihenfolge auch bei gleichem Namen eindeutig). `zahlen.jahre = len(jahre)`.

### Funktionen

* `plan_laden(pfad)` — `json.load`, nur lesend; fehlende Datei/kein Wörterbuch/
  kaputtes JSON → deutsche `ValueError`-Meldung (kein stiller Leerplan).
* `uebersicht_bauen(plan, *, stand=None)` — **rein** (kein Datei-, kein
  Netzzugriff, verändert den Plan nicht); `stand` injizierbar. Ungültiger Plan
  (kein Wörterbuch oder ohne `anlaesse` **und** ohne `zusammenfassung`) →
  deutsche `ValueError`-Meldung.
* `uebersicht_laden(pfad)` — liest die Übersichtsdatei (nur lesend).
* `uebersicht_schreiben(pfad, daten) -> str` — atomar: temp-Datei im Zielordner
  + `os.replace`; Ziel im Repo → deutsche `ValueError`-Meldung, es wird nichts
  geschrieben.
* `uebersicht_text(daten) -> str` — deutsche mehrzeilige Zusammenfassung.
* `haupt(argv) -> int` — CLI mit `--plan`, `--ausgabe`, `--schreiben`; ohne
  `--schreiben` reiner Trockenlauf. Ziel im Repo → Meldung auf `stderr`, Exit 2.

### Zählregeln (mit Kommentar im Code)

1. `zeilen`, `anlaesse`, `zuege`, `doppelung_*`, `ohne_thema`, `ohne_jahr`,
   `events_neu`, `events_wiederverwendet`, `ordner_neu`, `ordner_vorhanden`
   kommen aus `plan["zusammenfassung"]`; fehlender/unbrauchbarer Wert → `0`.
   `anlaesse` wird zusätzlich gegen `len(plan["anlaesse"])` geprüft — bei
   Abweichung gewinnt der **echte Listenwert** (kein stiller Widerspruch
   zwischen Kopfzahl und Liste).
2. `events` = Anzahl **verschiedener** `(jahr, kategorie, event)`-Kombinationen.
3. `dateien` je Gruppe = Summe der `dateien`-Felder ihrer Anlässe (im Plan eine
   Zahl; eine Liste wird als ihre Länge gelesen).
4. `jahre`/`themen`/`kategorien` = Anzahl verschiedener Jahre bzw. `thema`- bzw.
   `kategorie`-Werte (ein **leerer** Name wird nicht als Gruppe geführt).
5. `ohne_datum = max(0, zeilen - zuege - doppelung_uebersprungen)` — die Zeilen
   ohne Datum im Namen. Gegenprobe N7: 9.430 − 7.616 − 668 = **1.146**.

### Trockenlauf-Garantien

* Kein Netz, kein pCloud, keine Bilder, keine Datei-Kennungen: das Modul
  importiert nur `argparse`, `datetime`, `json`, `os`, `sys` (im Test per AST
  geprüft). Weder `fileid` noch `folderid` noch Bildendungen stehen in der
  Ausgabe.
* Die **einzige** Löschung im Modul ist das Entfernen der eigenen temp-Datei im
  Fehlerfall des atomaren Schreibens (im Test per AST geprüft: genau ein
  `os.remove(...)`, und dessen Argument ist die temp-Variable).
* Ausgaben nur außerhalb des Repos; der Repo-Zielpfad wird verweigert — auch im
  Trockenlauf, damit der Fehler früh auffällt.

## Trockenlauf gegen den echten Plan (ohne Schreiben)

`python tools/foto_sortierung/foto_uebersicht.py` (Exit 0, keine Datei angelegt):

```
Fotos-Uebersicht — Stand 2026-09-27T22:27:41+02:00 (Plan-Stand 2026-09-27T13:49:46, trocken: ja)
Anlaesse: 2.127   Events: 2.098   Dateien: 7.616
Jahre: 11   Themen: 48   Kategorien: 11
Zeilen: 9.430   Zuege: 7.616
Events neu: 2.088   Events wiederverwendet: 39
Ordner neu: 2.108   Ordner vorhanden: 82
Doppelungen: 1.534 gesamt · 866 ohne Anlass-ID · 668 uebersprungen
Zeilen ohne Datum: 1.146   Anlaesse ohne Thema: 0   Anlaesse ohne Jahr: 0
ohne Bilddaten, ohne Datei-Kennungen
```

Alle Werte bis auf `events` stehen wortgleich in `sortierplan.json`
(`zusammenfassung`). `ohne_datum` = 1.146 ist die nachgerechnete Gegenprobe aus
Regel 5.

### Hinweis zu `zahlen.events` (2098 gegen 2127)

Der Schema-Block des Auftrags nannte als Beispiel `"events": 2127` — das war die
Zahl der **Anlässe** und ist am 27.09.2026 vom Planer auf **2098** korrigiert
worden (Auftragsdatei, `events`). Bindend war und ist die Zählregel:
`events` = Anzahl **verschiedener** `(jahr, kategorie, event)`-Kombinationen —
also die Zahl der Ziel-Ordner. Beides ist im echten Plan nicht gleich:
**2.127 Anlässe** stehen **2.098 Kombinationen** gegenüber, weil
**10** wiederverwendete Event-Ordner (`event_quelle: "vorschlag"`, vom Planer
selbst aus `sortierplan.json` nachgezählt) je mehrere Anlässe aufnehmen:
**39 Anlässe in 10 Ordnern** (davon 7 Ordner mit mehr als einem Anlass;
39 − 10 = 29 = 2.127 − 2.098). Umgesetzt ist die Zählregel; die Zahl ist damit
semantisch „so viele Event-Ordner gibt es“, nicht „so viele Anlässe gab es“.
`events_neu` (2.088) und `events_wiederverwendet` (39) sind dagegen **Anlässe**
und stammen aus der Plan-Zusammenfassung — sie summieren sich zu 2.127.
Teil B liest die Datei, es ist keine Änderung am Schema.

## Prüfbefehl

```
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

Ergebnis (Ausführer-Lauf, 27.09.2026, 22:3x): **`1687 passed, 3 warnings in
104.57s`, 39 Zeilen Ausgabe, Exit-Code 0** — Baseline war 1503 (die Suite
enthält zusätzlich die Dateien des parallel arbeitenden zweiten Subagenten).
Nur die neue Datei: `98 passed in 0.88s`, Exit 0.

## Bewusst offen gelassen

* **Nicht geschrieben (Trockenlauf):** der Trockenlauf von Teil A legt **keine**
  `~/foto_sortierung/fotos_uebersicht.json` an — das Schreiben ist ein eigener
  Aufruf (`--schreiben`). **Nachtrag des Planers (27.09.2026, 22:40):** genau
  dieser Aufruf ist danach erfolgt; die Datei existiert jetzt
  (**344.615 Bytes**, `stand 2026-09-27T22:40:09+02:00`, aus dem echten
  `sortierplan.json`, **ohne** Bilddaten und **ohne** Datei-Kennungen) und ist im
  Changelog B im Rauchtest gegen den echten Bestand belegt.
* **Keine Kennungen, kein `je_jahr`/`je_kategorie`-Block:** die Übersicht bleibt
  bewusst klein; wer die Aufschlüsselung je Jahr/Kategorie braucht, liest
  `sortierplan.json` am PC.
* **Kein Zeitlimit-Alter:** die Datei trägt `stand` und `quelle.plan_stand`, aber
  keine eigene Gültigkeitsprüfung — „zu alt“ ist eine Entscheidung des Lesers
  (Teil B kann `plan_stand` gegen `stand` vergleichen).
* **Leere `thema`/`kategorie`-Werte** werden nicht als Gruppenzeile geführt (im
  echten Plan kommen sie nicht vor: `ohne_thema` = 0).
