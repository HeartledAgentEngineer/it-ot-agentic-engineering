# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Doppelte-Pruefung (pCloud, Pruefsumme)

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse, Ortsnamen,
Erzaehl-Quellen, Beziehungen, Personen und die App-Uebersicht. Eine Stufe fehlte
weiterhin: **die Duplikat-Pruefung per Pruefsumme.**

| Datei | Inhalt | Gelesen von | Nachweis vorher |
|---|---|---|---|
| `duplikate.json` | Duplikat-Gruppen der zwei pCloud-Baeume `Automatic Upload` und `Bilder & Videos` (je Gruppe `size`, `hash`, `art`, `mitglieder`, `loesch_kandidaten`), dazu `baeume` (gelesene Ordner/Dateien/Tiefe) und `zusammenfassung` | Sebastian selbst — die Datei ist die Entscheidungsgrundlage „was ist doppelt, was wuerde eine Freigabe bringen?"; `pcloud_duplikate.py` schreibt sie, **geloescht wird nie** | keiner |

Faellt die Datei weg oder halbiert sie sich, faellt die Entscheidungsgrundlage
weg — und es faellt heute niemandem auf. Das ist derselbe blinde Fleck wie bei
OSM (Journal 8), beim Bildindex (Journal 12), bei den Anlaessen (Journal 19),
bei den Ortsnamen (Journal 20), bei den Erzaehl-Quellen (Journal 21), bei den
Beziehungen (Journal 22), bei den Personen (Journal 23) und bei der
App-Uebersicht (Journal 24).

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Doppelte (pCloud)"** in `bestand_pruefen.py` mit dem Leser
   `duplikate_lesen(pfad)` und dem Helfer `_zahlen_baum(...)` (beide werfen nie).
   Gezaehlt werden Gruppen, betroffene Dateien, Mitglieder, die Zahl je `art`,
   die Kandidaten je Gruppe und die Kandidaten-Gesamtliste; je Baum Dateien,
   gelesene Ordner, erreichte Tiefe, Vollstaendigkeit (`abgebrochen`,
   `offen_gelassen`) und die Zaehler `ohne_hash`/`ohne_groesse`/`ohne_kennung`/
   `kaputte_eintraege`; dazu die Kennzahlen der Zusammenfassung und die Groesse in
   MB (neu der Helfer `_mb`). Abschaltbar mit `pruefen(..., duplikate=None)`.
2. **Ehrliche Pruefungen statt stiller Nullwerte.** Fehlt die Datei, steht das
   als Luecke da („Doppelte nicht geprueft"); ist sie kein lesbares JSON, meldet
   der Nachweis „nicht lesbar (kein JSON)". Ein **nicht zu Ende gelesener Baum**
   (`abgebrochen` oder `offen_gelassen > 0`) und Dateien **ohne Pruefsumme,
   Groesse oder Kennung** sind eigene Luecken — sonst waere die Doppeltenzahl nur
   ein Teil und wuerde trotzdem als vollstaendig gelesen.
3. **Abgleich (Kennzahlen gegen die gezaehlte Liste).** Die Zusammenfassung wird
   gegen die wirklich gezaehlten Gruppen gestellt: `duplikatgruppen` gegen die
   Gruppen-Zahl, `betroffene_dateien` gegen die Summe der `anzahl`-Werte (und
   gegen die Mitgliederzahl), die Kandidatenzahl gegen Listenlaenge und
   Gruppensumme, dazu `ueber_baeume` + `innerhalb` gegen die Gesamtzahl. Jede
   Abweichung ist eine Luecke („nicht reproduzierbar"), kein stiller Wert.
4. **Nur Zahlen — kein Dateiname, kein Pfad, keine Pruefsumme.** Die Mitglieder
   der Gruppen tragen Namen, Pfade und `hash_text` (Handy-Upload-Namen); der
   Nachweis liest sie **nicht** und gibt sie nicht aus — nur ihre Zahl. In den
   Tests mit Fantasieworten festgehalten.
5. **Modul-Docstring nachgezogen** (neuer Aufzaehlungspunkt „Doppelte"),
   Konstante `STANDARD_DUPLIKATE = "duplikate.json"`.

## Belege

* **Tests:** `backend/tests/test_bestand_und_handy_uebergabe.py` von 55 auf
  **59 Testfunktionen** (4 neue: Zaehlung/Abgleich an einer stimmigen Datei; keine
  Dateinamen/Pfade/Pruefsummen + Abweichung als Luecke; ehrliche Meldung bei
  fehlender Datei + Abhoengbarkeit; Leser tolerant bei kaputter/fehlender Datei).
  Lauf der Datei: **59 passed**.
* **Pruefbefehl** frisch und vollstaendig: `cd backend && .venv/Scripts/python -m
  pytest tests/ -q` → **3812 passed, 2 skipped, Exit 0** (214,25 s) — vorher 3808,
  also genau die vier neuen Tests, keine Nebenwirkung.
* **Messung am echten Bestand (Exit 0, nur lesend):** `duplikate.json` 2.606
  Gruppen, 6.467 betroffene Dateien, 6.467 Mitglieder
  (`innerhalb_sammlung` 978, `innerhalb_upload` 329, `ueber_baeume` 1.299);
  Baum `sammlung` 11.635 Dateien in 171 Ordnern (Tiefe 4), Baum `upload` 12.080
  Dateien in 20 Ordnern (Tiefe 7), beide vollstaendig gelesen, 0 Dateien ohne
  Pruefsumme; Zusammenfassung 23.715 gescannte = 23.715 vergleichbare Dateien
  (12.080 + 11.635), 2.606 Duplikatgruppen, 6.467 betroffene; **45.393,1 MB** in
  allen Kopien, **17.465,7 MB** Loesch-Kandidaten (2.133 Dateien); Abgleich
  Gruppen 2.606/2.606, Dateien 6.467/6.467, Kandidaten 2.133/2.133 — **alles
  stimmig, kein Befund**; Stand 27.09.2026 22:15 (Trockenlauf, es wurde nichts
  geloescht).
* Ergebnisliste unveraendert **5 Luecken** (vier kosten-/geraetebunden, die
  fuenfte der Personen-Befund aus Journal 23).

## Ehrlicher Neben-Befund (nicht behoben)

`duplikate.json` ist vom **27.09.2026** — vor Papas Fotos (10.10.), vor der
Neuausrichtung und vor dem vollen Index. Die Zahl „was ist doppelt" kennt den
heutigen Bestand also nicht. Ein neuer Lauf ist **kostenfrei** (nur
`listfolder`), aber ein pCloud-Schwall — er gehoert nicht neben einen anderen
pCloud-lastigen Lauf. Gemessen und benannt, nicht gestartet.

## Ehrlich offen

Am Handy nichts gegengeprueft, kein Bild-/Gesichtsdienst aufgerufen, nichts
geloescht, keine Handy-Eingaenge. Nur eigene Pfade committet (nie `git add -A`);
fremde Aenderungen im Arbeitsbaum (AGENTS.md, typeFREE, docs/experimente,
agentbus-protokoll.md, Rechercheseiten, status.json, `pcloud_agent_schreiber.py`)
blieben unangetastet. `status.json` nicht angefasst (Papa-Zaehler 6.336
unveraendert = nichts nachzutragen).
