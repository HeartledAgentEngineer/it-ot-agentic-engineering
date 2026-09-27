# N6b Rest: Massenlauf Themen für 1.967 Anlässe (gemessen) + Deckel-Korrektur

> **Datum:** 27.09.2026 · **Schritt:** N6b (Restlauf) aus
> `docs/plan-nachtlauf-2026-09-26.md` · **Rollen:** Planer = Hauptagent
> (Hermes), Ausführer = Werkzeuge `foto_themen.py` / `foto_themen_vision.py`
> plus ein Hermes-Subagent (`deepseek-v4.1-flash`) für die Code-Korrektur,
> Prüfer = `openai/gpt-5.6-luna` (fremde Modellfamilie).

## Was gemacht wurde

Der Rest der Anlässe wurde nach dem Muster „kleinster Stapel zuerst"
durchgezogen — Kontaktbögen bauen (pCloud-Vorschaubilder, nur lesend) und je
Anlass **ein** Vision-Aufruf (`google/gemini-2.5-flash`, Themen-Katalog
**Version 3** mit 53 Einträgen, Zuordnung nur aus dieser Liste).

Reihenfolge und Reihenfolge-Grund (kleinster Stapel zuerst, damit ein Abbruch
den billigsten Teil vollendet):

| Jahr | Anlässe | davon im Lauf gesehen | Fehlschläge | Bögen gebaut | Vorschaubilder (Bytes) | Kacheln | Tokens ein/aus | Dauer |
|---|---|---|---|---|---|---|---|---|
| 2026 | 301 | 298 | 0 | 298 | 816 (4.061.086) | 816 | 898.744 / 41.770 | 218 s + 600 s |
| 2025 | 380 | 379 | 1 | 378 | 1.444 (6.591.335) | 1.444 | 1.147.373 / 68.041 | 288 s + 781 s |
| 2022 | 409 | 408 | 1 | 409 | 1.946 (9.460.892) | 1.946 | 1.238.572 / 90.257 | 296 s + 916 s |
| 2024 | 430 | 430 | 0 | 430 | 1.969 (9.488.988) | 1.969 | 1.300.987 / 93.037 | 322 s + 1.012 s |
| 2023 | 447 | 447 | 0 | 447 | 1.547 (7.624.434) | 1.547 | 1.368.416 / 77.008 | 347 s + 872 s |
| **Summe** | **1.967** | **1.962** | **2** | **1.962** | **7.722 (37,2 MB)** | **7.722** | **5.954.092 / 370.113** | **24,5 min + 69,7 min** |

Zusätzlich drei Anlässe als Rauchtest vorab (2026-01-02, -01-03, -01-05;
0,0051 USD, 3/3 Katalog-Treffer) — deshalb 298 statt 301 im Lauf. Alle Läufe
endeten mit **Exit 0** (Protokoll `~/foto_sortierung/n6b_rest_massenlauf.log`).

## Endstand (gemessen, nach den Nachläufen)

* **2.128 Anlässe** insgesamt im Fortsetzungspunkt `~/foto_sortierung/themen.jsonl`
  — das ist der **vollständige** Bestand; Kontaktbögen liegen für alle 2.128 vor
  (`~/foto_sortierung/boegen/`, 70 MB, 2.128 JPEG).
* **2.127 davon mit Katalog-Thema**, **1 ohne** (siehe „Der eine offene Fall").
* **48 verschiedene Themen** werden tatsächlich benutzt; **242 × `Sonstiges`**
  = **11,4 %** (bei N6c auf 161 Anlässen waren es 8,7 % — der größere Bestand
  enthält mehr Bildschirmfotos, Memes und Textbilder).
* Häufigste Themen: `Konzert und Buehne` 325, `Sonstiges` 242, `Fest und Feier`
  167, `Dinge und Stillleben` 153, `Reise und Urlaub` 109,
  `Text und Screenshot` 100, `Technik und Geraete` 86, `Essen und Trinken` 84.
* **Kosten**: der Fünfjahres-Lauf **5.954.092 ein / 370.113 aus Tokens =
  2,711510 USD** (Preise 0,30/2,50 USD je 1 Mio, live abgefragt). Über den
  gesamten Bestand summiert (`kosten_usd` in `themen.jsonl`, inklusive der
  früheren Messungen aus N5/N6/N6c): **2,938515 USD**.
  Die Hochrechnung aus N6b Stapel 1 (2,56 USD für 1.967 Anlässe) wurde um
  **0,15 USD (≈ 6 %)** überschritten — akzeptiert, nicht umgangen.
* **Original-Sortierschlüssel unverändert**:
  `md5 70642d2988b6e38ff417561ccf870ba8`. Geschrieben wurde nur die Kopie
  `~/foto_sortierung/sortierschluessel_themen.csv` (**9.430 Zeilen, davon 8.284
  mit Thema** — die übrigen Zeilen sind Videos/Dateien ohne Anlass-Zuordnung).
* **Alles außerhalb des Repos**: `~/foto_sortierung/` (boegen/ 70 MB,
  themen/ 11 MB, themen.jsonl, CSV-Kopie). Keine Bilder, keine Themen im Repo.
* **Nichts gelöscht, nichts verschoben, nichts in die pCloud geschrieben** —
  alle pCloud-Aufrufe waren lesend (`listfolder`, `getthumbs`).
* Nicht im Repo: `themen_vor_n6b_rest_20260927_091225.jsonl` — eine **Kopie**
  des Fortsetzungspunkts vor dem Richten (488 Zeilen → 161 eindeutige), damit
  der Zwischenstand jederzeit vergleichbar bleibt.

## Deckel-Korrektur (echter Codefehler, vom Lauf aufgedeckt)

Der größte Anlass des Bestands — `2025-01-17_Anlass-02`, **108 Kacheln**
(19:09–22:17, 35 Videos, 1,3 GB) — scheiterte **zweimal** mit
„Modellantwort ist kein lesbares JSON (JSONDecodeError)", auch mit
`flash-lite`. Ursache **gemessen**, nicht geraten: die Antwort enthält je
Kachel ein JSON-Objekt, der Aufruf hatte aber einen harten Deckel
`MAX_TOKENS = 4000`; bei 108 Kacheln wird die Antwort abgeschnitten.

**Korrektur** (`tools/foto_sortierung/foto_themen_vision.py`): neue reine
Funktion `max_tokens_fuer(anzahl) = max(4000, min(16000, 1200 + 60 * anzahl))`,
`anfrage_bauen()` nutzt sie nur, wenn **kein** Wert ausdrücklich übergeben wird.
Kleine Bögen bleiben damit **exakt** bei 4.000 (Payload unverändert), sehr
große werden bei 16.000 gekappt.

**Beleg, dass genau das die Ursache war:** derselbe Anlass läuft nach der
Korrektur durch — **108/108 Kacheln, Thema `Konzert und Buehne`, 4.420
Ausgabe-Tokens** (also *über* dem alten Deckel von 4.000), 0,012073 USD, 16,4 s.
Sechs neue Tests in `backend/tests/test_foto_themen_vision.py` (4.000 bei
kleinen Bögen, 7.680 bei 108, Monotonie, Deckel 16.000, Payload-Wert,
ausdrücklicher Wert gewinnt).

## Der eine offene Fall (bewusst nicht umgangen)

`2022-09-05_Anlass-02` (18 Kacheln, 14:46–15:18) wird vom **Anbieter
abgelehnt**. Nachweis, selbst erhoben und abgelegt unter
`~/foto_sortierung/n6b_probe_2022-09-05.log`:

```
HTTP-Status: 200
Top-Schluessel: ['error', 'id']
Fehler-code: 403
Fehler-message: Gemini blocked the request: PROHIBITED_CONTENT
choices: keine
```

Das Werkzeug meldet dafür nur „OpenRouter lieferte keine Antwort aus" — die
Ablehnung selbst ist im Werkzeug-Log **nicht** sichtbar; sie wurde mit einer
eigenen Sonde direkt gegen die API belegt (der Schlüssel wurde dabei nie
ausgegeben).

**Entscheidung:** Der Inhalt wird **nicht** auf ein Modell umgeschoben, der ihn
akzeptiert. Ein Anbieter, der Aufnahmen ablehnt, kann dafür einen Grund haben
(Sebastian sieht die Bilder vor dem Sortieren in pCloud) — **keine
Umgehung**. Der Anlass bleibt als Marker ohne Thema im Fortsetzungspunkt; das
Werkzeug versucht ihn bei jedem Lauf erneut (kostet nichts, weil vor der
Token-Abrechnung abgelehnt wird). Der Bogen liegt als
`~/foto_sortierung/boegen/2022/2022-09-05_Anlass-02.jpg` (0,12 MB) bereit.

## Nebenbefund: Fehlschläge sind Wiederholungsmarker

Ein Fehlversuch schreibt **keinen** Themen-Eintrag mit Inhalt, sondern einen
Marker mit `thema: null` in `themen.jsonl` (und eine neue Zeile je Versuch —
daher 2.134 Zeilen bei 2.128 eindeutigen Anlässen). Der nächste Lauf findet
den Anlass dadurch wieder und überspringt ihn nicht. Das ist gewollt: dieselbe
Mechanik hat den 108-Kachel-Fall nach der Code-Korrektur automatisch
eingesammelt.

## Prüfbefehl und Abnahme

* **Prüfbefehl selbst gefahren** (`cd backend && ./.venv/Scripts/python.exe -m
  pytest tests/ -q`): **671 passed, Exit 0** (71 s). Vor der Code-Korrektur
  waren es 665 (657 zum Zeitpunkt des N6c-Commits, danach +8 aus parallel
  laufendem Strang im selben Arbeitsbaum); die sechs neuen Tests dieser Runde
  zählen auf 671 hoch.
* **Prüfer** (`openai/gpt-5.6-luna`) hat den Prüfauftrag selbst abgearbeitet
  (eigener Prüflauf 671/Exit 0, `max_tokens_fuer` nachgerechnet, Token- und
  Kostensummen nachgerechnet, md5 geprüft) und **drei Punkte** gemeldet:
  1. „Vier geänderte Dateien statt zwei" — die zwei zusätzlichen
     (`docs/experimente/live_zahlen.*`) stammen vom **zweiten Agenten** im
     selben Arbeitsbaum (N3-Strang) und wurden deshalb mit `git commit --only`
     ausdrücklich **nicht** mitgenommen.
  2. Der Zählstand „2.128 Einträge / 2 ohne Thema" war zum Prüfzeitpunkt
     **veraltet**, weil zwischen Messung und Prüfung weitere Nachläufe liefen
     (Marker je Versuch). Endstand jetzt: **2.128 eindeutige Anlässe, 1 ohne
     Thema, 2.127 Themen-Dateien** — hier korrigiert.
  3. Die 403-`PROHIBITED_CONTENT`-Angabe sei „im Log nicht belegt" — richtig,
     sie stammt aus der eigenen Sonde (siehe oben), weil das Werkzeug die
     Ablehnung nur als leere Antwort meldet; der Sonde-Beleg ist jetzt als
     Datei abgelegt.
* **Prüfer-Runde 2** auf dem committeten Stand (`0318e56`): **„BESTANDEN",
  0 Abweichungen.** Nachgerechnet wurden: Commit-Inhalt (genau vier Dateien,
  die fremden `live_zahlen`-Dateien des zweiten Agenten **nicht** enthalten),
  Push-Stand `0 0`, Zählstand (2.134 Zeilen / 2.128 eindeutige Anlässe /
  1 ohne Thema / 2.127 Themen-Dateien / 48 Themen / 242 `Sonstiges` =
  11,37218 %), Jahresverteilung (Summe 2.128), Sonde-Beleg
  (`n6b_probe_2022-09-05.log`, kein Schlüsselwert darin), Token- und
  Kostensummen, md5 des Originals, Prüfbefehl (671/Exit 0),
  `max_tokens_fuer` für 10/108/5.000 Kacheln und der 108-Kachel-Anlass
  (Thema `Konzert und Buehne`, 4.420 Ausgabe-Tokens).

## Was dieser Schritt NICHT getan hat

* **Nichts in die pCloud geschrieben**, nichts verschoben, nichts gelöscht.
* Kein Trockenlauf des Sortierens (N7) und kein echtes Sortieren (N8).
* Keine Personen-Stufe (N9).
* Beim Sortieren (N7) ist zu berücksichtigen: **ein** Anlass hat kein Thema —
  der Sortierer braucht dafür einen ausdrücklichen Rückfallordner
  (z. B. `Ohne-Thema`), statt den Vorgang abzubrechen.
