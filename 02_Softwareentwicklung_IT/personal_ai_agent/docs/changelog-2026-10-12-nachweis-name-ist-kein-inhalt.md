# Der Name ist ein Hinweis, die Prüfsumme ist der Beleg (12.10.2026)

## Warum

Auf der Zahl **„8 Fotos ohne Beschreibung"** steht Sebastians Entscheidung über einen
bezahlten Nachzieh-Lauf mit Vision (Union-Plan, Journal 7/32/35). Der vorige Lauf hat die
Zahl schon genauer benannt: 8 **Kennungen** = 6 Bilder, eines davon „unter einer anderen
Kennung schon beschrieben" → „5 Bilder ohne Text".

Der letzte Schritt dieser Rechnung war **nicht gemessen, sondern aus dem Dateinamen
geschlossen**: dieselbe Kennung, derselbe Name — daraus wurde „dasselbe Bild". Zwei
Dateien mit demselben Namen können aber zwei verschiedene Fotos sein; gerade Kameranamen
wie `IMG20241117120204.jpg` kommen mehrfach vor.

## Was gemessen wurde (nur lesend, lokal + pCloud-Listung)

Die Duplikat-Prüfung (`pcloud_duplikate.py`, nur `listfolder`, kein Löschen) wurde frisch
gefahren — die Datei war vom 27.09. und kannte Papas 6.336 Fotos noch gar nicht:

| | vorher (27.09.) | frisch (12.10.) |
|---|---|---|
| verglichene Dateien | 23.715 | **32.944** |
| Duplikat-Gruppen | 2.606 | **3.998** |
| Lösch-Kandidaten | 2.133 (17,5 GB) | **2.620 (19,7 GB)** |
| Bäume | upload 12.080 / sammlung 11.635 | upload 12.786 / sammlung 20.158 |

Damit ist Ketten-Schritt 8 der Papas-Kette erfüllt (frische Datei mit Zeitstempel,
Kandidatenzahl im Bericht); die alte Fassung liegt als `duplikate.json.vorher` daneben
(kopiert, nichts überschrieben ohne Sicherung, nichts gelöscht).

**Der Befund an den 8 fehlenden Kennungen** (Prüfsumme = gleiche Größe UND gleicher Hash):

* **4 der 8 Kennungen bilden 2 Paare gleichen Inhalts** — beide Hälften ohne Beschreibung.
  Die zwei Namens-Dubletten sind damit **inhaltsgleich belegt** (nicht nur gleich benannt).
* Die eine Kennung mit „gleichnamiger beschriebener Stelle" steht in **keiner**
  Duplikat-Gruppe: der Name stimmt, der gleiche Inhalt ist **nicht belegt**.
* Ergebnis: **6 verschiedene Bilder** ohne Beschreibungstext — nicht 5. Die Zahl vor der
  Kostenentscheidung war um eins zu niedrig, weil ein Name als Inhalt gelesen wurde.

Die Lücke selbst bleibt unverändert **„8 Fotos ohne Beschreibung"** (nichts schöngerechnet).

## Was geändert wurde

**`tools/foto_sortierung/bestand_pruefen.py`**

1. `duplikate_lesen()` liefert zusätzlich `inhaltsgleich` (je Kennung die Partner-Kennungen
   derselben Größe+Prüfsumme-Gruppe) und `inhaltsgleich_kennungen`. Nur Kennungen — kein
   Name, kein Pfad, keine Prüfsumme im Ergebnis.
2. `bilder_zaehlen(..., inhaltsgleich=None)` trennt jetzt **Name** (Hinweis) von **Inhalt**
   (Beleg): neu `inhaltsgruppen`, `inhaltsgleich_kennungen`, `inhaltsgleich_beschrieben`,
   `inhalte`, `bilder_ohne_text_belegt`. Ohne Prüfsummen-Daten bleiben die zwei letzten
   `None` — es wird nichts geraten; die Namens-Sicht (`bilder`, `doppelte_kennungen`,
   `anderswo_beschrieben`, `bilder_ohne_text`) ist unverändert.
3. Der Bericht nennt dazu:
   * die Namens-Zeile jetzt ehrlich als „die Namens-Sicht ergäbe N Bilder … (nicht belegt)",
   * eine **zweite Zeile „Inhaltsgleich (Prüfsumme, duplikate.json vom <Datum>)"** mit
     Gruppen, abgedeckten Texten und der belastbaren Zahl — sie erscheint nur, wenn sie
     etwas sagt (keine Doppel-Gruppen und gleiche Zahl = keine Zeile).
4. Die Duplikat-Datei wird im Bericht **einmal** gelesen (vorher zweimal).

## Belege

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py`: **97 → 101
  Testfunktionen** (4 neu: Prüfsummen-Verknüpfung im Leser, Name-vs-Inhalt im Zähler,
  der echte Fall als Bericht mit der belastbaren Zahl, „ohne Prüfsummen wird nicht
  geraten"); Lauf der Datei **101 passed** (20,25 s).
* Prüfbefehl frisch und vollständig: **3930 passed, 2 skipped, Exit 0** (661,51 s). Ehrlich
  zur Zahl: vorher 3900 — die Differenz von 30 sind meine **4** neuen Tests und **26** aus
  fremder, inzwischen im Baum liegender Arbeit des Master-Chats (nicht aus meiner Änderung).
* Messung am echten Bestand (Exit 0, nur lesend): die zwei neuen Zeilen lauten

```
Bilder statt Kennungen: 8 Kennungen = 6 Bilder (2 Kennungen sind Doppel desselben Namens);
1 davon traegt einen Namen, der an einer anderen Kennung schon beschrieben ist (Name ist
kein Beleg fuer denselben Inhalt) - die Namens-Sicht ergaebe 5 Bilder ohne
Beschreibungstext (nicht belegt)
Inhaltsgleich (Pruefsumme, duplikate.json vom 2026-10-12): 4 der 8 Kennungen haben eine
inhaltsgleiche andere Datei, 2 Gruppe(n) gleichen Inhalts unter den Fehlenden; 0 davon hat
schon einen Text - es bleiben 6 verschiedene Bilder, 6 davon ohne Beschreibungstext
(belastbare Zahl fuer die Kostenentscheidung)
```

## Ehrliche Grenzen

* Was die 6 Bilder zeigen, sagt das Werkzeug nicht — dafür bräuchte es einen Vision-Aufruf,
  und Bilddaten gehen ohne Sebastians Entscheidung nicht an fremde Modelle.
* Ob die 3 nicht ladbaren Dateien in pCloud noch existieren, ist offline nicht messbar.
* Eine Datei, die in **keiner** Duplikat-Gruppe steht, kann auch „nicht verglichen" sein
  (pCloud liefert keine Prüfsumme); das Werkzeug meldet das als eigene Zahl und rechnet es
  nicht als Gleichheit.
* Der Lösch-Kandidaten-Bericht ist **nur eine Liste**: gelöscht wurde nichts, Kandidaten
  sind immer Upload-Kopien, nie die Sammlung. Über Löschen entscheidet Sebastian
  (`pcloud_duplikate_loeschen.py --wirklich`, Papierkorb).
* Nebenbefund (gemessen, nicht geändert): Papas entpackte Archive enthalten **4 Gruppen
  gleichen Inhalts innerhalb des Papa-Ordners** (8 Dateien, keine Lösch-Kandidaten, da
  Sammlung) — die 32 Archive überschneiden sich also teilweise.

Nichts gelöscht, kein Bild-/Gesichtsdienst, kein Schreibzugriff in die pCloud (nur
`listfolder`), keine Geräteeingänge, keine kostenpflichtigen Massenläufe.
