# 13.10.2026 — Kabellose Übergabe des neuen Ortsstands, und die Anzeige misst ihre Zahlen

Zwei Dinge an einem Nachmittag: erstens sind die zwei am 13.10. geänderten
Ergebnisdateien kabellos ans Handy gegeben worden, zweitens nennt die
Fortschrittsanzeige die Zahlen der Bildkette jetzt gemessen statt in einem
freien Text (der still veraltete).

## 1. Kabellose Übergabe: `orte.jsonl` und `bild_orte.csv` (Kettenschritt 9)

**Anlass.** Am 13.10. sind zwei Dateien der Bildkette neu entstanden:
`orte.jsonl` (Ortsnamen nachgetragen, jetzt 9.259 Zeilen statt 9.252) und
`bild_orte.csv` (Papas Fotos fehlten komplett, jetzt 25.177 Zeilen statt
18.840). Beide lagen nur am PC; im pCloud-Ordner `/Agent/uebergabe` stand noch
der Stand vom 10.10. — das Handy hätte beim nächsten Start die unvollständige
Fassung übernommen (dieselbe Lage wie am 10.10. beim Bildindex).

**Weg und Freigabe.** Sebastians ausdrückliche Freigabe vom 10.10. („Ergebnisse
kabellos ans Handy"): der PC lädt die Dateien nach `/Agent/uebergabe`, das
Handy holt sie beim Start (`termux/pcloud-uebernehmen.sh`). Werkzeug:
`tools/pcloud/uebergabe_hochladen.py` — Trockenlauf ist Standard, geschrieben
nur mit `--schreiben`, Ziel nur unter `/Agent/`, kein Löschen.

**Ergebnis (Trockenlauf und Schreiben, je acht Dateien).**

| Datei | Lauf | Ergebnis |
|---|---|---|
| `bild_index.db` | übersprungen | Prüfsumme gleich (107.900.928 B, `024be534…`) |
| `ordner_ereignisse.jsonl` | übersprungen | Prüfsumme gleich (1.351.519 B, `0872011a…`) |
| `bild_beschreibungen_reich.jsonl` | übersprungen | Prüfsumme gleich (8.509.164 B, `a6de9da1…`) |
| `bild_beschreibungen_papa_reich.jsonl` | übersprungen | Prüfsumme gleich (2.938.567 B, `0263f2d8…`) |
| `gesicht_zuordnung.jsonl` | übersprungen | Prüfsumme gleich (8.741.862 B, `c4381b60…`) |
| `personen_beispiele.json` | übersprungen | Prüfsumme gleich (1.595.146 B, `abda14a4…`) |
| `orte.jsonl` | **hochgeladen** | 1.977.946 B, `24accf9a4d20`, fileid 108911243226 |
| `bild_orte.csv` | **hochgeladen** | 3.753.789 B, `131a77995bb0`, fileid 108911245985 |

Je Datei eine Manifest-Zeile in `~/foto_sortierung/uebergabe_manifest.jsonl`
(außerhalb des Repos). Zweiter Aufruf wäre wieder 0 zu laden (Idempotenz über
Größe **und** Prüfsumme).

**Unabhängige Gegenprobe (nicht die Erfolgsmeldung des Werkzeugs).** Die beiden
Dateien wurden über `getfilelink` frisch aus der pCloud geladen und örtlich
nachgerechnet: `bild_orte.csv` 3.753.789 B sha256 `131a77995bb03009…` — gleich
der lokalen Datei; `orte.jsonl` 1.977.946 B sha256 `24accf9a4d2014e8…` — gleich
der lokalen Datei. Größe und Änderungszeit (13.10. 09:55 UTC) stimmen in der
Ordnerliste.

## 2. Die Anzeige misst ihre Zahlen statt sie zu behaupten

**Befund.** Der freie Hinweistext der Fortschrittsanzeige nannte weiter
„bild_orte.csv 18.840 Zeilen", während die Datei nach dem Papa-Nachtrag 25.177
Zeilen hatte — dieselbe stille Veraltung wie bei einer zweiten Liste. Die
Anzeige ist Sebastians Kontrollinstrument; eine falsche Zahl dort ist genau der
Fehler, den er nicht gebrauchen kann.

**Änderung (`werkzeuge/fortschritt/fortschritt.py`).** Neuer Abschnitt
„Kennzahlen (gemessen)" in Terminal **und** Dashboard, gespeist aus
`messe_kennzahlen()`:

* `zeilen_zaehlen()` — Datenzeilen einer Textdatei über die Zeilenenden
  (Kopfzeile wird abgezogen, damit dieselbe Zahl wie im Nachweis steht).
* `sqlite_zaehlen()` — Zeilen einer Tabelle und davon mit gefülltem Feld, rein
  lesend (`mode=ro`), keine Inhalte.
* Nicht messbar heißt ehrlich „nicht messbar" — es wird kein Wert erfunden.
* Der Text-Hinweis in `status.json` trägt die veraltenden Zahlen nicht mehr.

**Belege.** `backend/tests/test_fortschritt_laufend.py` **17 → 22
Testfunktionen** (5 neue: Zeilenzählung mit/ohne Zeilenende und fehlender Datei,
SQLite-Zählung samt drei Fehlerfällen ohne Ausnahme, Kennzahlen-Messung an
erfundener CSV und Mini-SQLite, Anzeige in Terminal und HTML mit ehrlichem
„nicht messbar", unveränderte Anzeige ohne Kennzahlen), Lauf der Datei
**22 passed**. Messung am echten Bestand (nur lesend): „Ortsstufen je Bild
(bild_orte.csv): **25.177 Zeilen**" — dieselbe Zahl wie der Nachweis — und
„Bildindex (bild_index.db): **26.241 Bilder, 26.241 mit vektor**".

## Grenzen dieses Schritts

Kein Bild geöffnet oder an ein fremdes Modell gesendet, kein Vision-Aufruf,
keine Kosten, keine Geräteeingriffe (kein Gerät am Kabel), nichts gelöscht.
Schreibzugriff nur unter `/Agent/` in pCloud (freigegebener Weg). Die neuen
Daten liegen jetzt am PC **und** in der pCloud; das Handy nimmt sie beim
nächsten Start selbst.
