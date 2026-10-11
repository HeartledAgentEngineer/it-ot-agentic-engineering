# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Fotos-Uebersicht der App (N11/N13a)

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen, Beziehungen und Personen. Zwei Stufen fehlten weiterhin: **die
beiden abgeleiteten App-Dateien der Fotos-Uebersicht.**

| Datei | Inhalt | Gelesen von | Nachweis vorher |
|---|---|---|---|
| `fotos_uebersicht.json` | Zahlen + Event-Namen („wie viele Events gab's?") | `services/foto_uebersicht.py` (`router/fotos.py`, Chat-Werkzeug) | keiner |
| `fotos_dateien.json` | je Event die Datei-Kennungen fuer die Bildvorschau | `services/foto_bilder.py` (dieselben Verbraucher) | keiner |

Beide leitet das PC-Werkzeug (`foto_uebersicht.py` / `foto_dateien.py`) aus dem
lokalen `sortierplan.json` ab, beide werden **ans Handy uebergeben**
(`tools/handy/uebergabe_uebernehmen.py` nennt genau diese zwei Namen). Faellt
eine weg oder halbiert sie sich, zeigt die App falsche Zahlen oder keine
Vorschaubilder — und es faellt heute niemandem auf. Das ist derselbe blinde
Fleck wie bei OSM (Journal 8), beim Bildindex (Journal 12), bei den Anlaessen
(Journal 19), bei den Ortsnamen (Journal 20), bei den Erzaehl-Quellen
(Journal 21), bei den Beziehungen (Journal 22) und bei den Personen
(Journal 23).

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Fotos-Uebersicht (App)"** in `bestand_pruefen.py` mit zwei
   Lesern `app_uebersicht_lesen(pfad)` und `app_dateien_lesen(pfad)` (werfen
   nie). Gezaehlt werden je Datei die Kennzahlen aus dem `zahlen`-Block, die
   Event-Zeilen und die Laengen der Listen `jahre`/`kategorien`/`themen` bzw.
   die Datei-Eintraege und die Summe der `anzahl`-Werte. Abschaltbar mit
   `pruefen(..., app_uebersicht=None, app_dateien=None)`.
2. **Ehrliche Pruefungen statt stiller Nullwerte.** Fehlt eine Datei, steht das
   als Luecke da („App-Uebersicht nicht abgeleitet" bzw. „Vorschau ohne
   Datei-Kennungen"); ist sie kein lesbares JSON, meldet der Nachweis „nicht
   lesbar (kein JSON)". Events ohne Namen und Dateien ohne Kennung werden
   ebenfalls als Zeile und (bei den Kennungen) als Luecke gefuehrt.
3. **Abgleich der beiden Dateien.** Sie stammen aus derselben Quelle
   (`sortierplan.json`) und muessen dieselbe Zahl Events und Dateien nennen; die
   Zeile „Abgleich: Events … / …; Dateien … / …" stellt sie gegeneinander. Eine
   Abweichung — auch zwischen den Event-Zeilen und `zahlen.events` bzw.
   `zahlen.dateien` — ist eine Luecke („nicht reproduzierbar"), kein stiller
   Wert. Genau diese Pruefung fehlte bisher.
4. **Nur Zahlen: kein Event-Name, kein Kategorien-Name, kein Thema, kein
   Dateiname.** In den Tests mit Fantasieworten festgehalten
   (`EVENT_DARF_NICHT_ERSCHEINEN`, `KAT_DARF_NICHT_ERSCHEINEN`,
   `THEMA_DARF_NICHT_ERSCHEINEN`, `DATEI_EVENT_DARF_NICHT_ERSCHEINEN`,
   `DATEINAME_DARF_NICHT_ERSCHEINEN`). Modul-Docstring um den neuen Abschnitt
   ergaenzt, neue Konstanten `STANDARD_APP_UEBERSICHT` / `STANDARD_APP_DATEIEN`.

## Belege

* Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py`: **47 → 51
  Testfunktionen** (4 neue) — Zaehlung/Abgleich, keine Inhalte + Abweichung als
  Luecke, ehrliche Meldung bei fehlenden Dateien + Abschaltbarkeit, beide Leser
  tolerant bei kaputter/fehlender Datei. Lauf der Datei: **55 passed**.
* **Messung am echten Bestand (Exit 0, nur lesend):**
  * `fotos_uebersicht.json`: **2.098 Events**, 11 Jahre, 11 Kategorien,
    48 Themen, 0 Events ohne Namen; `zahlen` 9.430 Zeilen / 2.127 Anlaesse /
    7.616 Zuege; Stand **2026-09-27T22:40:09+02:00**.
  * `fotos_dateien.json`: **2.098 Events**, **7.616 Datei-Kennungen**, Summe
    `anzahl` 7.616, 0 Events ohne Dateien, 0 Dateien ohne Kennung; `zahlen`
    2.098 events / 7.616 dateien / 0 ohne_kennung; Stand
    **2026-09-28T09:44:53+02:00**, Plan-Stand 2026-09-27T13:49:46.
  * **Abgleich: Events 2.098 / 2.098; Dateien 7.616 / 7.616** — die beiden
    Dateien passen zusammen.
* Ergebnisliste des Nachweises unveraendert **5 Luecken** (vier kosten- bzw.
  geraetegebunden: 8 Fotos ohne Beschreibung, 25 Videos ohne Gesichter-Lauf,
  WhatsApp-Verdrahtung, `eigene_orte.json`; die fuenfte ist der Befund aus
  Journal 23: 2 Kennungen ohne Gruppe).

## Ehrlicher Neben-Befund (nicht behoben)

Beide App-Dateien sind vom **27./28.09.2026**, abgeleitet aus dem damaligen
`sortierplan.json` (7.616 Zuege). Sie enthalten daher **weder Papas 6.336 Fotos**
(der Papas-Plan kam spaeter, 10.10.) **noch** die reichen Beschreibungen — die
App-Uebersicht und die Bildvorschau am Handy kennen Papas Bestand also nicht.
Ob und wann die beiden Dateien neu gebaut und erneut uebergeben werden, ist
**Sebastians Entscheidung** (ein Lauf `foto_uebersicht.py` / `foto_dateien.py`
ueber einen erweiterten Plan waere moeglich, aber eine Inhalts-/Umfangsentscheidung
und keine Nachweis-Aufgabe). Hier nur gemessen und benannt, nicht geaendert.

## Grenzen

Nichts geloescht, kein Bild- oder Gesichtsdienst aufgerufen, keine
kostenpflichtigen Massenlaeufe, keine Handy-Eingriffe (nur gelesen). Nur eigene
Pfade committet (nie `git add -A`).
