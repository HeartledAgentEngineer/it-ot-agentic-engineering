# Nachweis kennt jetzt die Anlaesse (ordner_ereignisse.jsonl) — 11.10.2026

## Warum

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) zaehlt Plaene,
Gesichter, Beschreibungen, Gruppen, den Karten-Zweig, den Bildindex und die
Neuausrichtung nach. Die **Anlass-Stufe** (Ketten-Schritt 5) stand aber in
KEINEM Nachweis: `ordner_ereignisse.jsonl` — je Anlass ein Datum und die
Bild-Kennungen, aus EXIF/Dateiname/Ordnerjahr/Planjahr gebuendelt (2.268
Anlaesse am 10.10. gebaut) — tauchte in keiner Pruefzeile auf.

Diese Stufe ist nicht Beiwerk: sie traegt **„Anlaesse einer Person"**
(`person_auskunft`) und das **Erzaehlen**. Fehlt oder halbiert sie, merkt es
heute niemand — dieselbe Luecke wie bei OSM (Journal 8) und beim Bildindex
(Journal 12): eine gebaute Stufe ohne Zahl, die sich wiederholen laesst.

## Was jetzt geprueft wird

Neuer Abschnitt **„Anlaesse (ordner_ereignisse.jsonl)"**:

* **Anlaesse** insgesamt, **Datei-Kennungen** (Fotos + Videos zusammen) und
  davon **Videos**; dazu **kaputte Zeilen** (werden gezaehlt, nie geworfen).
* **Datum:** wie viele Anlaesse ein Datum tragen und **woher** es kommt
  (Schluessel aus `quellen.datum`, z. B. `exif`, `dateiname`, `ordnerjahr`,
  `planjahr`) — das ist die Datumsquelle, an der die Papas-Kette haengt.
* **Jahresspanne** (`jahr_min`–`jahr_max`).
* **Deckung:** wie viele Plan-Fotos in mindestens einem Anlass liegen — die
  einzige Zahl, die „ist jeder Anlass verortet?" fuer den Bestand beantwortet.
* Fehlt die Datei, steht das als **Luecke** in der Ergebnisliste
  („Anlaesse nicht gebaut"), nicht als stiller Nullwert. Abschaltbar mit
  `pruefen(..., anlaesse=None)`.

Wie der ganze Nachweis: **nur Zahlen.** Keine Titel, keine Themen, keine
Kategorien — das ist in den Tests festgehalten (Fantasietitel duerfen im
Bericht nicht auftauchen).

## Messung am echten Bestand (11.10.2026, Exit 0)

```
Anlaesse (ordner_ereignisse.jsonl): 2.268 Anlaesse, 17.966 Datei-Kennungen,
                                    davon 859 Videos
  Datum: 2.190 von 2.268 Anlaessen tragen eines (dateiname 567, exif 1.764,
         ohne 55, ordnerjahr 14, planjahr 9)
  Jahre: 1937-2026
  Deckung: 17.107 von 23.916 Plan-Fotos liegen in einem Anlass (71,5 %)
```

Die 2.190 Datumstraeger und 17.107 Fotos decken sich mit dem Schreibbericht des
Baus vom 10.10. (Journal 7: „aufgenommen 17.107 Fotos + 859 Videos"). Die
Differenz zu 23.916 ist ehrlich und erwartet: 8.458 Plan-Zeilen standen schon in
`ereignisse.jsonl`/`fotobuch_ereignisse.jsonl` und wurden uebersprungen, dazu die
Doppelten und Zeilen ohne Kennung/Name.

Ergebnisliste des Laufs unveraendert: **4 Luecken** (3 + 5 Fotos und 25 Videos
ohne Beschreibung bzw. Gesichtszeile im Einzelplan, 8 Fotos im Gesamtplan) —
alle kosten- bzw. geraetegebunden.

## Belege

* Tests: `backend/tests/test_bestand_und_handy_uebergabe.py` **35 passed**
  (4 neue: Zaehlung/Uebersicht, keine Titel und kaputte Zeilen, ehrliche Meldung
  bei fehlender Datei + Abschaltbarkeit, `anlaesse_lesen` wirft bei kaputter
  Datei nicht; die bestehenden unveraendert).
* Pruefbefehl frisch und vollstaendig: **3788 passed, 2 skipped, Exit 0**
  (206,0 s) — vorher 3784, also genau die vier neuen Tests, keine Nebenwirkung.
* Lauf am echten Bestand: Exit 0, Ausgabe oben.

## Dateien

* `tools/foto_sortierung/bestand_pruefen.py` — `STANDARD_ANLAESSE`,
  `anlaesse_lesen`, Abschnitt „Anlaesse", Parameter `anlaesse`
  (Standard `ordner_ereignisse.jsonl`), Docstring nachgezogen.
* `backend/tests/test_bestand_und_handy_uebergabe.py` — 4 neue Tests.
