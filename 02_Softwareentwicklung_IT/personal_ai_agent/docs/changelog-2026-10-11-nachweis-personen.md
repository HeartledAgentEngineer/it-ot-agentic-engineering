# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Personen-Stufe (Quiz + Telefonbuch)

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen und Beziehungen. Eine Stufe fehlte weiterhin: **die Personen.**

Seit dem 10.10. lesen die Chat-Werkzeuge `personen_liste`, `person_auskunft` und
`fotos_mit_person` die **Quiz-Quelle** (`gruppen_quiz.personen()`) statt des
alten Gesichtskatalogs. Gelesen werden dafuer:

| Datei | Inhalt | Nachweis vorher |
|---|---|---|
| `personen_bestaetigt.json` | Kennung → Name (die benannten Personen) | keiner |
| `personen_vorgaben.json` | gleich / verschieden / ausgeschlossen | keiner |
| `personen_profile.json` | Beziehung, Notizen, Telefonbuch-Kontakt | keiner |
| `kontakte.json` | Telefonbuch-Auszug (Name, Nummern, Geburtstag) | keiner |
| `gruppen_quiz_stand.json` | spaeter / unbekannt | keiner |
| `gruppen_antworten.jsonl` | Protokoll (Rueckgaengig, Nachvollziehbarkeit) | keiner |

Gezaehlt wurden bisher nur die **Gruppen** (`personen_beispiele.json`), nie die
**Namen**. Faellt `personen_bestaetigt.json` weg oder halbiert sie sich, findet
die Personen-Auskunft niemanden mehr — und es faellt heute niemandem auf. Das ist
derselbe blinde Fleck wie bei OSM (Journal 8), beim Bildindex (Journal 12), bei
den Anlaessen (Journal 19), bei den Ortsnamen (Journal 20), bei den
Erzaehl-Quellen (Journal 21) und bei den Beziehungen (Journal 22).

Die Dateien liegen an **zwei Orten**, und der Dienst liest beide:
`personen_gruppen/<datei>` (so schreibt der PC) und `<datei>` direkt im Ordner
(so legt die Uebergabe sie am Handy ab — genau der Fall bei `kontakte.json`).
Der Nachweis geht denselben Weg (`_quiz_pfad`); ohne diesen zweiten Ort meldete
er Dateien als fehlend, die der Dienst sehr wohl liest.

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Personen (Quiz)"** in `bestand_pruefen.py`: Kennungen mit
   Namen, **verschiedene Namen** (dieselbe Person an mehreren Kennungen ist eine
   Person), Kennungen ohne Namen; Vorgaben (gleich/verschieden/ausgeschlossen);
   Profile (Eintraege, mit Beziehung, mit Notiz samt Notizzahl, mit
   Telefonbuch-Kontakt); Telefonbuch (Kontakte, davon mit Geburtstag);
   Quiz-Stand (spaeter/unbekannt) und Protokoll-Zeilen. Abschaltbar mit
   `pruefen(..., personen=None)`.
2. **Zwei ehrliche Pruefungen.** `kennungen_ohne_gruppe` zaehlt bestaetigte
   Kennungen, zu denen es in `personen_beispiele.json` **keine Gruppe** gibt
   (ein Name ohne Gesichter) — das steht als Zahl in der Zeile und als Luecke in
   der Ergebnisliste. Und eine **leere** Namen-Datei meldet „0 Personen" statt
   erfundener Werte.
3. **Fehlende bzw. unlesbare Namens-Datei = Luecke, nicht stiller Nullwert**
   („Personen ohne Namen" bzw. „nicht lesbar"). Die optionalen Dateien
   (Profile, Telefonbuch, Stand, Protokoll) stehen als Zeile „Noch nicht
   angelegt: …" da — sie sind kein Mangel, sondern ein Zustand.
4. **Nur Zahlen: NIE ein Personenname, nie eine Telefonnummer, nie ein
   Geburtstag, nie eine Notiz.** Die Namen sind der sensibelste Bestand des
   ganzen Nachweises. In den Tests mit Fantasieworten festgehalten
   (`NAME_DARF_NICHT_ERSCHEINEN_A/B`, `KONTAKT_DARF_NICHT_ERSCHEINEN`,
   `BEZIEHUNG_DARF_NICHT_ERSCHEINEN`, `NOTIZ_DARF_NICHT_ERSCHEINEN`, `0176`,
   `1990-01-01`).

Neu sind der Leser `personen_lesen(basis, namen_datei)`, die Helfer
`_quiz_pfad(basis, name)` (die zwei Lesepfade wie `gruppen_quiz._lesepfad`) und
`_json_lesen(pfad)` (nie ein Wurf), die Konstanten `STANDARD_PERSONEN` /
`PERSONEN_VORGABEN` / `PERSONEN_PROFILE` / `PERSONEN_KONTAKTE` / `PERSONEN_STAND`
/ `PERSONEN_PROTOKOLL` und der Docstring-Abschnitt.

## Belege

- Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **47 → 51
  Testfunktionen** (4 neue: Zaehlung, keine Namen/Nummern/Geburtstage +
  Kennung-ohne-Gruppe als Luecke, ehrliche Meldung bei fehlender Datei +
  Abschaltbarkeit, Leser tolerant bei kaputter/fehlender Datei).
- Pruefbefehl frisch und vollstaendig: **3804 passed, 2 skipped, Exit 0**
  (206,7 s) — vorher 3800, also genau die vier neuen Tests, keine Nebenwirkung.
- **Messung am echten Bestand (Exit 0, nur lesend):**
  - `personen_bestaetigt.json`: **20 Kennungen mit Namen = 7 Personen**, 0 ohne
    Namen; **2 Kennungen ohne Gruppe**.
  - `personen_vorgaben.json`: gleich 14, verschieden 5, ausgeschlossen 40.
  - `personen_profile.json`: noch nicht angelegt; `gruppen_quiz_stand.json` und
    `gruppen_antworten.jsonl` ebenfalls noch nicht.
  - `kontakte.json` (flach): **596 Kontakte, davon 55 mit Geburtstag**.
  - Ergebnis jetzt **5 Luecken** (vorher 4): die neue Zeile hat auf ihrem ersten
    Lauf sofort einen echten Befund gefunden — **2 bestaetigte Kennungen ohne
    Gruppe** (`Person_262`, `Person_850`; gegengeprueft: von 20 Kennungen der
    Namens-Datei fehlen genau diese zwei in den 1.017 Gruppen der
    Gruppen-Datei). Sie stammen offenbar aus einer Gruppierung VOR dem
    Neu-Lauf vom 09.10.; die Namen zeigen also auf Gruppen, die es nicht mehr
    gibt. Der Nachweis benennt das jetzt, statt es zu verschweigen.

## Ehrlicher Befund zum Namensstand

Der Plan nennt fuer den 10.10. „106 benannte Personen" in `personen_bestaetigt.json`.
Gemessen hat die PC-Datei **20 Kennungen / 7 verschiedene Namen** (571 Byte,
Stand 08.10. 23:51); die Gruppen-Datei traegt 18 benannte Gruppen mit denselben
7 Namen. Die „106" ist am PC **nicht reproduzierbar**. Wahrscheinlichste
Erklaerung: die Namensarbeit laeuft im Quiz **am Handy**, die PC-Kopie stammt vom
Uebergabelauf am 08.10. und ist seither nicht nachgezogen worden (die
Uebergabeliste enthaelt `personen_bestaetigt.json` nicht). Belegen laesst sich
das nur am Geraet — deshalb hier als Befund notiert und nicht als Ursache
behauptet. Der Nachweis zeigt den Zustand jetzt dauerhaft an.

## Ehrlich offen

- Am Handy nicht gegengeprueft, kein Bild-/Gesichtsdienst aufgerufen, nichts
  geloescht, keine Geraeteeingaenge.
- Vier der fuenf Luecken sind unveraendert kosten- bzw. geraetegebunden: 8 Fotos
  ohne Beschreibung und 25 Videos ohne Gesichter-Lauf (bezahlte Netzaufrufe =
  Sebastians Entscheidung), WhatsApp-Verdrahtung (Geraet), `eigene_orte.json`
  (Privatorte). Die fuenfte ist der neue Befund oben (2 Kennungen ohne Gruppe) —
  sie ist am PC loesbar, aber nur durch Sebastians Entscheidung: entweder die
  zwei Namen fallen lassen oder die Gruppen neu zuordnen (der Neu-Lauf
  `personen_gruppieren.py` vergibt neue Kennungen, deshalb bleibt es Handarbeit).
