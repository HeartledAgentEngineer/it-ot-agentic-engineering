# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Beziehungen

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse
(`ordner_ereignisse.jsonl`), Ortsnamen und die Erzaehl-Quellen. Eine Stufe
fehlte weiterhin: **die Beziehungen.**

`beziehungen_service` (Antwortstufe N28, `router/beziehungen.py` und das
Chat-Werkzeug) liest **zwei** Dateien, die zusammen die Auskunft „wer war mit
wem wo" tragen:

| Datei | Inhalt | Nachweis vorher |
|---|---|---|
| `beziehungen.jsonl` | 15.051 Aussagen (Anlass, Datum, Unterart, Personen) | keiner |
| `beziehungen.json` | Kennzahlen (Arten, Kontakte, Kennungen, Datumsspanne) | keiner |

**Keine der beiden** hatte einen Nachweis. Faellt `beziehungen.jsonl` weg oder
halbiert sie sich, schweigt die Auskunft „wer war mit wem wo" — und es faellt
heute niemandem auf. Das ist derselbe blinde Fleck wie bei OSM (Journal 8), beim
Bildindex (Journal 12), bei den Anlaessen (Journal 19), bei den Ortsnamen
(Journal 20) und bei den Erzaehl-Quellen (Journal 21).

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Beziehungen"** in `bestand_pruefen.py`: Aussagen,
   Anlaesse (verschiedene `anlass_id`), Tage (verschiedene `datum`),
   Unterarten als Zaehler, Personen-Eintraege (davon bestaetigt / mit Kennung),
   Kategorien als Anzahl, Datumsspanne, kaputte Zeilen. Dazu eine Zeile zur
   **Uebersicht** `beziehungen.json` (nennt die Zahl der Aussagen, Kontakte,
   Kennungen, Datumsspanne). Abschaltbar mit
   `pruefen(..., beziehungen=None, beziehungen_uebersicht=None)`.
2. **Die Kennzahlen werden gegen die gemessene Datei gestellt.** Nennt die
   Uebersicht eine andere Aussagen-Zahl als die gemessene Zeilenzahl, steht das
   als Abweichung **und** als Luecke da („nicht reproduzierbar") — die Antwort
   der Stufe darf nicht auf Kennzahlen beruhen, die zur Datei nicht passen.
3. **Fehlende Datei = Luecke, nicht stiller Nullwert** („Beziehungen nicht
   abgeleitet" bzw. „Beziehungs-Kennzahlen fehlen"); eine nicht lesbare
   Uebersicht meldet „nicht lesbar".
4. **Nur Zahlen:** keine Namen, keine Chat-Namen, keine Themen, keine
   Zielordner. Die Aussagen-Datei traegt `personen[].name` und
   `beleg.chat_name` — nichts davon wird gelesen oder ausgegeben. In den Tests
   mit Fantasieworten festgehalten (`NAME_DARF_NICHT_ERSCHEINEN`,
   `CHAT_DARF_NICHT_ERSCHEINEN`, `KATEGORIE_DARF_NICHT_ERSCHEINEN`).

Neu sind die zwei Leser `beziehungen_lesen(pfad)` und
`beziehungen_uebersicht_lesen(pfad)` (keiner wirft bei kaputten Zeilen/Dateien),
der Helfer `_ganze_zahl(wert)`, die Konstanten `STANDARD_BEZEIHUNGEN` /
`STANDARD_BEZEIHUNGEN_UEBERSICHT` und der Docstring-Abschnitt.

## Belege

- Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **43 → 47
  Testfunktionen** (4 neue: Zaehlung/Reproduzierbarkeit, keine Namen +
  Abweichung als Luecke, ehrliche Meldung bei fehlenden Dateien +
  Abschaltbarkeit, beide Leser tolerant bei kaputter/fehlender Datei).
- Pruefbefehl frisch und vollstaendig: **3800 passed, 2 skipped, Exit 0**
  (204,9 s) — vorher 3796, also genau die vier neuen Tests, keine Nebenwirkung.
- **Messung am echten Bestand (Exit 0, nur lesend):**
  - `beziehungen.jsonl`: **15.051 Aussagen, 1.301 Anlaesse, 645 Tage,
    11 Kategorien**; Unterarten `fotos 23`, `fotos_und_chat 126`,
    `gemeinsam_im_chat 14.902`; Datum 15.051 von 15.051, Jahre **2016–2025**.
  - `beziehungen.json`: nennt **15.051 Aussagen** (fotos 23, fotos_und_chat 126,
    gemeinsam_im_chat 14.902); Kontakte 253, Kennungen 12; 2016-05-04 bis
    2025-08-16. **Die gemessene Zeilenzahl deckt sich exakt mit der Kennzahl**
    (15.051 = 23 + 126 + 14.902) — keine Abweichung.
  - Ergebnis unveraendert **4 Luecken**, alle kosten- bzw. geraetegebunden.

## Ehrlich offen

- Am Handy nicht gegengeprueft, kein Bild-/Gesichtsdienst aufgerufen, nichts
  geloescht, keine Geraeteeingaenge.
- Unveraendert 4 Luecken: 8 Fotos ohne Beschreibung und 25 Videos ohne
  Gesichter-Lauf (bezahlte Netzaufrufe = Sebastians Entscheidung),
  WhatsApp-Verdrahtung (Geraet), `eigene_orte.json` (Privatorte).
