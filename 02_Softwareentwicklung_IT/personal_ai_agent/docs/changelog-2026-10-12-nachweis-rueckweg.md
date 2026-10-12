# Nachweis: der Rückweg Handy → PC steht jetzt in einer Prüfzeile (12.10.2026)

## Warum

Der Rückweg wurde am 12.10. gebaut (Journal 33: `termux/rueckweg-bereitstellen.sh`
stellt die am Gerät erzeugten Datendateien in den freigegebenen Ordner,
`tools/handy/rueckweg_holen.py` holt sie ab und bucht je Datei eine
Manifest-Zeile). **Der Nachweis kannte diesen Weg aber nicht.**

Genau daran hing der Kern des Fundes von Journal 33: die zwei Stufen
„Eigene Geschichten" und „Eigene Titel" waren die **einzigen** im ganzen
Nachweis, die nur in *eine* Richtung prüfbar waren — der Nachweis konnte sagen
„noch nicht angelegt", aber nie, ob das, was am PC liegt, wirklich die vom Handy
geholte Fassung ist. Solange das offen ist, kann er eine kaputte oder veraltete
Kopie nicht von einer guten unterscheiden.

## Was jetzt gemessen wird

Neuer Leser `rueckweg_lesen()` und neuer Abschnitt **„Rückweg (Handy → PC)"** in
`bestand_pruefen.py` (abschaltbar mit `--rueckweg`, leer = nicht prüfen):

* Je Namen gilt die **jüngste Buchung** des Manifests. Sie wird gegen die lokale
  Fassung (`<basis>/<name>` = der Zielordner des Hol-Werkzeugs) gestellt:
  * `gleich` — Bytes **und** sha256 stimmen: die geholte Kopie liegt unversehrt,
  * `abweichend` — lokal ist etwas anderes: am PC liegt **nicht** die gebuchte Fassung,
  * `fehlt_lokal` — gebucht, aber am PC nicht (mehr) vorhanden,
  * `ohne_pruefsumme` / `unlesbar` — nicht vollständig vergleichbar.
* Dazu benannt: Buchungen **außerhalb** der erlaubten Liste, **mehrfach** gebuchte
  Namen (jeder Lauf bucht — normal), und Namen, zu denen eine **`.vorher`**-Sicherung
  beiseite liegt (eine ältere Fassung wurde ersetzt, der Rückweg ist damit offen).
* **Deckung** als Zeile, nicht als Lücke: wie viele Dateien entstehen am Gerät
  (19 bekannt) und wie viele davon haben überhaupt einen Rückweg (2). Welche
  Datei nur am Gerät lebt, ist eine Entscheidung — kein Dauer-Fehlalarm.
* **Wächter:** die Dateiliste der Prüfzeile (`STANDARD_RUECKWEG_NAMEN`) muss die
  des Hol-Werkzeugs (`ERLAUBTE_NAMEN`) sein — der Test liest sie per **AST** aus
  `tools/handy/rueckweg_holen.py`. Sonst meldete die Prüfzeile Buchungen als
  „außerhalb der Liste", die längst dazugehören.

Lücken entstehen nur dort, wo wirklich etwas fehlt: kaputte Buchungen, abweichende
Kopien, gebuchte-aber-fehlende Dateien, unlesbare Dateien, Buchungen ohne
Prüfsumme. **Nur Zahlen, Dateinamen und Zustand** — nie ein Geschichtentext, nie
ein eigener Titel, kein Pfad (im Test festgehalten).

## Belege

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py`: **85 → 93
  Testfunktionen** (8 neue), Lauf der Datei **93 passed** (18,49 s).
* Prüfbefehl frisch und vollständig: siehe Commit.
* **Messung am echten Bestand (Exit 0, nur lesend):**
  „Rueckweg (Handy → PC): rueckweg_manifest.jsonl noch nicht angelegt — die am
  Gerät erzeugten Datendateien sind noch nie an den PC geholt" plus
  „Geräteseitige Dateien: 19 bekannt, 2 mit Rückweg, 17 ohne".

## Ehrliche Grenze

Der ehrliche Ist-Stand bleibt: **noch keine Buchung** — das Handy zieht den neuen
Stand erst beim nächsten App-Start, und heute hängt kein Gerät am Kabel
(`adb devices` leer). Der Abschnitt ist damit gebaut und leer-geprüft, aber noch
nicht mit echten Daten durchlaufen. Was seit dem Holen **am Gerät** dazukommt,
ist offline nicht sichtbar — auch das steht in der Zeile nicht als Behauptung.
