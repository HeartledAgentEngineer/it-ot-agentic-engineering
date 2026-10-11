# Nachtrag 11.10.2026: Der Nachweis kennt jetzt die Erzaehl-Quellen

## Warum

Der Bestandsnachweis (`tools/foto_sortierung/bestand_pruefen.py`, „fertig ist,
was verifiziert ist") zaehlt die gebauten Stufen selbst nach: Plaene, Gesichter,
Beschreibungen, Gruppen, OSM, Bildindex, Neuausrichtung, Anlaesse
(`ordner_ereignisse.jsonl`) und Ortsnamen. Eine Stufe fehlte weiterhin:
**die beiden aelteren Erzaehl-Quellen.**

`erzaehl_service._ereignisse_laden()` liest zum Erzaehlen **drei** Dateien:

| Datei | Inhalt | Nachweis vorher |
|---|---|---|
| `fotobuch_ereignisse.jsonl` | 78 Fotobuch-Seiten | keiner |
| `ereignisse.jsonl` | 2.127 Anlaesse der Sammlung | keiner |
| `ordner_ereignisse.jsonl` | 2.268 Anlaesse (Bau 10.10.) | seit Journal 19 |

**Nur die dritte** hatte einen Nachweis. Faellt `ereignisse.jsonl` weg oder
halbiert sich, fehlen dem Erzaehlen 2.127 Anlaesse — und es faellt heute
niemandem auf. Das ist derselbe blinde Fleck wie bei OSM (Journal 8), beim
Bildindex (Journal 12), bei den Anlaessen (Journal 19) und bei den Ortsnamen
(Journal 20).

## Was geaendert wurde

Nur Werkzeug, Test und Doku — **kein Betriebs- oder Anzeigecode**.

1. **Neuer Abschnitt „Erzaehl-Anlaesse"** in `bestand_pruefen.py`, je Quelle
   eine Zeile: Anlaesse, Datei-Kennungen, kaputte Zeilen, **Zeilen ohne
   Kennung**, Datum + Quellen-Schluessel, Jahresspanne, Deckung gegen die
   Plan-Fotos. Dazu die Sammelzeile, **wie viele dieser Quellen vorhanden sind**
   (der Dienst braucht alle drei) und bei 0 eine Luecke
   („Geschichten ohne Anlass"). Abschaltbar mit `pruefen(..., erzaehl_quellen=None)`.
2. **Zeilen ohne Kennung werden gezaehlt** (`anlaesse_lesen` fuehrt jetzt
   `ohne_kennung`): `erzaehl_service._datei_ereignisse_laden()` verwirft eine
   Zeile ohne brauchbare `kennung` **still** — ein Anlass verschwindet damit
   aus den Geschichten, ohne dass es auffiele. Die Pruefung steht an der einen
   Lesestelle, die alle drei Quellen bedient; die bestehende Anlass-Zeile
   (`ordner_ereignisse.jsonl`) nennt die Zahl ebenfalls, wenn sie groesser 0 ist.
3. **Quellenangabe als Text verstanden:** die Sammlungs-Anlaesse nennen die
   Datumsquelle als Zeichenkette (`"quellen": {"datum": "sortierplan.json:anlaesse"}`)
   statt als Zaehler-Dict. Vorher haette der Bericht dort „keine
   Quellenangabe" behauptet, obwohl die Quelle dasteht — jetzt steht
   `sortierplan.json 2.127`.
4. **Nur Zahlen:** keine Titel, keine Buchnamen, keine Buchseiten, keine
   Buchtexte, keine Themen, keine Kategorien. In den Tests mit Fantasieworten
   festgehalten (`TITEL_DARF_NICHT_ERSCHEINEN`, `BUCH_DARF_NICHT_ERSCHEINEN`,
   `TEXT_DARF_NICHT_ERSCHEINEN`).

## Belege

- Testdatei `backend/tests/test_bestand_und_handy_uebergabe.py` **39 → 43
  Testfunktionen** (4 neue: Zaehlung/Deckung, keine Titel + Anlass ohne Kennung,
  ehrliche Meldung bei fehlender Quelle + Abschaltbarkeit, `anlaesse_lesen`
  zaehlt `ohne_kennung` und versteht die Text-Quellenangabe). Ein bestehender
  Test wurde praezisiert: die Abschaltbarkeit prueft jetzt **beide**
  Anlass-Sichten (`anlaesse=None, erzaehl_quellen=None`).
- Pruefbefehl frisch und vollstaendig: siehe Commit-Nachricht (Exit 0).
- **Messung am echten Bestand (Exit 0, nur lesend):**
  - `ereignisse.jsonl`: **2.127 Anlaesse, 7.616 Datei-Kennungen**, Datum 2.127
    von 2.127 (sortierplan.json), Jahre **2014–2026**, Deckung 6.809 von 23.916
    Plan-Fotos (28,5 %).
  - `fotobuch_ereignisse.jsonl`: **78 Seiten, 842 Datei-Kennungen**, kein Datum,
    Deckung 0 von 23.916 (die Scans liegen ausserhalb des Union-Plans).
  - **Erzaehl-Dienst: 2 von 2 dieser Quellen vorhanden** (dazu
    `ordner_ereignisse.jsonl`) — keine neue Luecke, Ergebnis unveraendert
    **4 Luecken**, alle kosten- bzw. geraetegebunden.

## Ehrlich offen

- Am Handy nicht gegengeprueft, kein Bild-/Gesichtsdienst aufgerufen, nichts
  geloescht, keine Geraeteeingaenge.
- Unveraendert 4 Luecken: 8 Fotos ohne Beschreibung und 25 Videos ohne
  Gesichter-Lauf (bezahlte Netzaufrufe = Sebastians Entscheidung),
  WhatsApp-Verdrahtung (Geraet), `eigene_orte.json` (Privatorte).
- **Naechster freier Punkt derselben Familie:** die **Beziehungen**
  (`beziehungen.jsonl`, 15.051 Aussagen „wer war mit wem wo", gelesen von
  `router/beziehungen.py` und dem Chat-Werkzeug; Kennzahlen in
  `beziehungen.json`) stehen in keiner Pruefzeile.
