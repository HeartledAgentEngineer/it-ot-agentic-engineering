# Der Nachweis meldete eine ausgelieferte Web-Datei als Lücke — jetzt ist sie benannt statt gezählt

Datum: 12.10.2026 · Werkzeug: `tools/foto_sortierung/bestand_pruefen.py` ·
Test: `backend/tests/test_bestand_und_handy_uebergabe.py`

## Ausgangslage (gemessen, nicht behauptet)

Der Lauf vom 12.10. (Journal 38) führte **6 Lücken**. Die sechste lautete wörtlich:

```
- manifest.json: der Dienst liest sie, sie kommt aber auf keinem der beiden
  Uebergabe-Wege ans Geraet (keine Kabel-Liste, nicht kabellos uebergeben)
```

Ursache, gemessen: der Scanner `dienst_dateinamen()` zieht per AST **alle**
Zeichenketten-Literale aus `backend/app`, die wie eine Datendatei aussehen
(`.json`, `.jsonl`, `.db`, `.csv`). In `backend/app/sicherheit.py` steht die
Positivliste der Dateien, die der Server aus dem **Frontend-Ordner ausliefert**
(`FRONTEND_DATEIEN`); darin steht `manifest.json` — das PWA-Manifest des
Agenten (`frontend/manifest.json`: Name, Symbole, `start_url`). Es fällt als
einziges dieser Liste unter das Datendatei-Muster, deshalb erschien es als
„vom Dienst gelesen", obwohl es **kein Datenbestand** ist: es kommt mit dem
**Code** ans Gerät (das Backend läuft im Termux im Projektordner und zieht den
Stand per `git pull`). Ein Übergabe-Weg ist für sie weder nötig noch gedacht —
so wie für `index.html`, `app.js` oder `style.css`, die nur deshalb nie
auffielen, weil ihre Endungen nicht zum Muster passen.

Damit war die Zeile ein **Fehlalarm in der Lückenliste**: eine echte Lücke sah
aus wie eine ausgelieferte Web-Datei, und umgekehrt.

## Was geändert wurde

- **Neue Menge, aus EINER Quelle gelesen:** `frontend_dienst_liste(pfad, konstante)`
  liest die Positivliste des Servers per AST aus
  `backend/app/sicherheit.py` (`FRONTEND_DATEIEN`, Standard in
  `STANDARD_FRONTEND_QUELLE`). Keine zweite Liste im Nachweis — die würde still
  veralten, sobald im Server eine Datei dazukommt. Fehlende Datei, fehlende
  Konstante oder kaputter Quelltext ⇒ **leere** Menge (kein Wurf), dann bleibt
  es beim alten Verhalten: jeder gelesene Name zählt.
- **Eigener Eimer im Ergebnis:** `uebergabe_deckung_pruefen()` führt
  `ausgeliefert` (Namen, Zahl) und hält diese Namen aus `ohne_liste` heraus.
  Über `frontend=None` abschaltbar (alter Zustand).
- **Der Bericht sagt es, er verschweigt es nicht:**
  ```
  Dienst liest 32 Datendateinamen; auf einer Liste 12, geraeteseitig 19, ausgeliefert 1, ohne Liste 0
  Vom Server ausgeliefert (kommen mit dem Code, kein Datenbestand - kein Uebergabe-Weg noetig) (1): manifest.json
  ```
  Die zweite Zeile erscheint nur, wenn sie etwas sagt. **Zeile, keine Lücke** —
  welcher Weg benutzt wird, entscheidet Sebastian; ein Befund wäre ein
  Dauer-Fehlalarm.

## Belege (in dieser Sitzung ausgeführt)

- `bestand_pruefen.py` am echten Bestand, **Exit 0**: die neue Zeile lautet
  „… ausgeliefert 1, ohne Liste 0", dazu „Vom Server ausgeliefert (…): manifest.json";
  **Ergebnis 6 → 5 Lücken**, die übrigen fünf unverändert (3 + 5 + 8 Fotos,
  25 Videos, 2 Kennungen ohne Gruppe).
- Testdatei `test_bestand_und_handy_uebergabe.py`: **3 neue Testfunktionen**
  (Positivliste lesen — `frozenset`/Tupel/Einzelwert, falscher Konstantenname,
  fehlende und kaputte Quelle; ausgelieferte Datei ist Zeile und keine Lücke;
  ohne Quelle bleibt es bei der Lücke), Lauf der Datei **107 passed**.
- Eine bestehende Zeile wurde mitgezogen (die Berichtszeile nennt den neuen
  Eimer): `test_uebergabe_listen_zaehlt_namen_und_stellen` prüft jetzt
  „… geraeteseitig 1, ausgeliefert 0, ohne Liste 0".

## Grenze (ehrlich)

Der Scanner unterscheidet weiterhin nicht „der Dienst **liest** diese Datei" von
„der Dienst **nennt** ihren Namen". Für die ausgelieferten Frontend-Dateien ist
das jetzt begründet getrennt; ein Datenname, der künftig in einer Positivliste
auftaucht, bliebe dagegen unsichtbar — deshalb steht er als eigene Zeile mit
Namen im Bericht, statt still aus der Zahl zu verschwinden.
