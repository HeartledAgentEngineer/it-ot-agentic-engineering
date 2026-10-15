# Wie tief sind die gespeicherten Bildbeschreibungen? — gemessen am 15.10.2026

Anlass: Abschnitt 2 des Plans `.hermes/plans/2026-10-10_personen-orte-erzaehlungen.md`
("Detailtiefe auf Zuruf") hat eine offene Frage. Dort steht als Annahme, die gespeicherten
Beschreibungen seien "~30 Woerter (2 Saetze)" — und der Vorschlag, fuer ein einzelnes Bild
auf Zuruf "so ausfuehrlich wie moeglich" nachzufassen. **Ob diese Annahme fuer welche Datei
stimmt, war nie gemessen.** Diese Messung schliesst die Luecke; gebaut wurde nichts.

## Was gemessen wurde

Neues Werkzeug `tools/foto_sortierung/beschreibungstiefe_messen.py` (nur lesen, nur Zahlen,
schreibt nichts, oeffnet kein Bild, kein Netz, kein Modell). Es liest die lokalen
Beschreibungsdateien und zaehlt je Datei Woerter (Median, Mittel, 90-Prozent-Wert, groesste),
Zeichen, Saetze, kaputte und leere Zeilen sowie eine grobe Sprachschaetzung. Zusaetzlich liest
es die **Wortgrenze je Prompt-Fassung** direkt aus `bild_beschreiben.PROMPT_VARIANTEN`
(einzige Quelle), damit Zahl und Grenze zusammen genannt werden.

Aufruf (aus `personal_ai_agent`):

```
backend\.venv\Scripts\python.exe tools\foto_sortierung\beschreibungstiefe_messen.py
```

Der Lauf endete **Exit 0**. Woertliche Ausgabe (nur Zahlen, keine Inhalte):

```
stichwort (Altbestand, 14-Wort-Grenze) (bild_beschreibungen.jsonl)
  Zeilen 19065 · kaputt 0 · leer 0 · Woerter Median 9 · Mittel 8.9 · 90 % 11 · groesste 14
  Zeichen Median 58 · groesste 94 · Saetze Median 1 · groesste 2
  ueberwiegend deutsch 90.4 % · ueberwiegend englisch 8.5 %

bildgeschichte Sammlung (bild_beschreibungen_reich.jsonl)
  Zeilen 17428 · kaputt 0 · leer 0 · Woerter Median 32.0 · Mittel 31.9 · 90 % 37 · groesste 50
  Zeichen Median 192.0 · groesste 293 · Saetze Median 3.0 · groesste 4
  ueberwiegend deutsch 0.0 % · ueberwiegend englisch 100.0 %

bildgeschichte Papa (bild_beschreibungen_papa_reich.jsonl)
  Zeilen 6336 · kaputt 0 · leer 0 · Woerter Median 32.0 · Mittel 32.2 · 90 % 37 · groesste 55
  Zeichen Median 189.0 · groesste 283 · Saetze Median 3.0 · groesste 4
  ueberwiegend deutsch 0.0 % · ueberwiegend englisch 100.0 %

bildgeschichte Nachzuegler (bild_beschreibungen_rest_reich.jsonl)
  Zeilen 984 · kaputt 0 · leer 0 · Woerter Median 32.0 · Mittel 31.6 · 90 % 37 · groesste 47
  Zeichen Median 187.0 · groesste 267 · Saetze Median 3.0 · groesste 4
  ueberwiegend deutsch 0.0 % · ueberwiegend englisch 100.0 %

bildgeschichte Altbestand-Nachzug (bild_beschreibungen_altbestand_reich.jsonl)
  Zeilen 604 · kaputt 0 · leer 0 · Woerter Median 33.0 · Mittel 32.3 · 90 % 36 · groesste 44
  Zeichen Median 195.0 · groesste 253 · Saetze Median 3.0 · groesste 4
  ueberwiegend deutsch 0.0 % · ueberwiegend englisch 100.0 %

Wortgrenze je Prompt-Fassung (aus bild_beschreiben.PROMPT_VARIANTEN):
  bildgeschichte: 70 Woerter
  stichwort: 14 Woerter
```

## Befund

1. **Die Annahme "~30 Woerter (2 Saetze)" trifft auf die neuen Dateien zu, nicht auf den
   Altbestand.** Die drei `bildgeschichte`-Dateien liegen bei **Median 32 Woertern und 3
   Saetzen** (Mittel 31,6–32,3; 90 % 36–37; groesste 44–55). Der Altbestand
   `bild_beschreibungen.jsonl` (19.065 Zeilen) liegt dagegen bei **Median 9 Woertern und 1
   Satz**, groesste genau **14** — das ist die Wortgrenze der Fassung `stichwort`
   (`BESCHREIBUNG_MAX_WOERTER = 14`), sie greift also im ganzen Bestand.
2. **Beide Fassungen sind englisch bzw. deutsch, wie entschieden.** Die `bildgeschichte`-Dateien
   sind **100 % englisch** (so gebaut, wie Sebastian am 10.10. festgelegt hat: die Beschreibung
   darf englisch sein, nur das Vorlesen ist deutsch). Der Altbestand ist zu 90,4 % deutsch.
3. **Die Grenze ist fassungsabhaengig und der Kopfraum ist gross.** Fassung `stichwort` = 14
   Woerter, Fassung `bildgeschichte` = **70 Woerter**. Die neuen Dateien nutzen davon rund
   46 % (Median 32). Eine Anfrage "hol mir dazu eine ausfuehrlichere Beschreibung" haette in
   der vorhandenen Fassung also noch **rund 38 Woerter** Luft, ohne dass ein neuer Prompt
   noetig waere — die Frage aus Abschnitt 2 (Ausgabegrenze) ist damit geklaert.
4. **Keine kaputten und keine leeren Zeilen** in allen fuenf Dateien (0 von 44.417).

## Was das fuer Abschnitt 2 bedeutet (nicht gebaut)

* Fuer den **Altbestand** ist der Wunsch "tiefer nachfassen" sachlich begruendet: 9 Woerter sind
  ein Suchstichwort, keine Beschreibung.
* Fuer die **neuen Dateien** ist die gespeicherte Tiefe schon die, die der Plan als Ziel nennt.
  Ob ein zweiter Durchgang "so ausfuehrlich wie moeglich" ueberhaupt noetig ist, ist damit eine
  Entscheidung an den Zahlen — nicht eine Vermutung.
* Gebaut wurde **nichts**: kein Prompt geaendert, kein Lauf gestartet, keine Datei geschrieben.
  Ein Nachfass-Lauf waere kostenpflichtig (Vision) und bleibt Sebastians Entscheidung.

## Belege

* Neues Werkzeug `tools/foto_sortierung/beschreibungstiefe_messen.py`.
* Neue Testdatei `backend/tests/test_beschreibungstiefe.py` — **13 passed** (erfundene Texte und
  Kennungen; geprueft u. a.: Woerter/Zeichen/Saetze, kaputte Zeile wird gezaehlt statt geworfen,
  fehlende `beschreibung` zaehlt als leer, fehlende Datei wird gemeldet ohne Abbruch,
  Sprachanteile, **kein Beschreibungstext im Bericht**, Wortgrenzen aus dem echten Werkzeug,
  Kommandozeilen-Abbruchwege).
* Messlauf am echten Bestand: **Exit 0**, Ausgabe oben woertlich.
* Nur Zahlen und Dateinamen im Bericht — **keine Beschreibungstexte, keine Personennamen,
  keine Bildkennungen**.
