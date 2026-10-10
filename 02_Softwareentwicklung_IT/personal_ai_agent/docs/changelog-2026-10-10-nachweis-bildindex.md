# Changelog 10.10.2026 — Nachweis kennt den Bildindex (und findet eine Lücke)

## Warum

Der Nachweis (`tools/foto_sortierung/bestand_pruefen.py`) zählte Pläne, Gesichter,
Beschreibungen, den Gesamtplan, die Orte/OSM-Stufe und die Gruppen nach. **Der
Bildindex (`bild_index.db`, Ketten-Schritt 7) stand in keiner einzigen Prüfzeile**
— obwohl er der Schluss der Kette ist: ohne Vektor je Bild gibt es keine
Bildsuche, und niemand hätte gemerkt, wenn er halb gefüllt wäre. Dieselbe Lücke
wie zuvor bei der OSM-Stufe (Journal 8 des Nachtlaufs).

## Was

Neu im Nachweis:

* `bildindex_lesen(pfad)` — liest `bild_index.db` **nur lesend** (`mode=ro`) und
  zählt: Bilder, Bilder mit Vektor, Bilder mit nicht-leerer Beschreibung, dazu
  die Menge der Kennungen. Der Beschreibungstext, der Ordner und die Vektoren
  werden **nie** gelesen oder ausgegeben; eine fehlende oder kaputte Datei meldet
  ehrlich `fehlt` statt zu werfen.
* `_bildindex_kopf(meta)` — Modell, Dimension, Token, Kosten und Stand aus der
  eigenen `meta`-Tabelle des Index.
* Neuer Abschnitt **„Bildindex (Bildsuche)“** in `pruefen(...)`, abschaltbar mit
  `bild_index=None`. Zwei Abgleichrichtungen gegen die Beschreibungsdateien:
  * *beschrieben, aber ohne Vektor im Index* → die Bildsuche wäre unvollständig
    (das ist die eine **offene Lücke**),
  * *im Index, aber nicht beschrieben* → der Index trägt etwas, das keine Quelle
    kennt.

## Beleg (Lauf am echten Bestand, Exit 0 — nur lesend)

```
Bildindex (Bildsuche): bild_index.db: 25.352 Bilder, 25.352 mit Vektor, 25.352 mit Beschreibung
  openai/text-embedding-3-small; 1536 Dimensionen; 947.779 Token; 0,02 USD; Stand 2026-10-10T14:32:29+00:00
  Beschrieben, aber ohne Vektor im Index: 889; im Index, aber nicht beschrieben: 0
...
Ergebnis: 5 Luecke(n)
  - sortierplan.json: 3 Fotos ohne Beschreibung
  - sortierplan_bildervideos.json: 25 Videos ohne Gesichter-Lauf
  - sortierplan_bildervideos.json: 5 Fotos ohne Beschreibung
  - sortierplan_reich_gesamt.json: 8 Fotos ohne Beschreibung
  - bild_index.db: 889 beschriebene Fotos ohne Vektor (Bildsuche unvollstaendig)
```

**Die neue Prüfzeile hat sofort etwas gefunden, das bisher niemand sehen konnte:**
**889 beschriebene Fotos haben keinen Vektor im Index.** Sie stammen gemessen
**alle** aus dem Altspeicher `bild_beschreibungen.jsonl` (19.065 Zeilen, davon
**18.176 im Index, 889 nicht**); die drei reichen Quellen (`bild_beschreibungen_reich`,
`_papa_reich`, `_rest_reich`) sind **vollständig** im Index. Die Gegenrichtung ist
leer: **0** Einträge im Index, die keine Beschreibungsdatei kennt.

## Ehrlich offen

* **Ursache der 889 ist offen.** Aus welcher Quelle bzw. welchem Plan genau der
  Index gebaut wurde, ist nicht dokumentiert, und keine Kombination der vier
  Beschreibungsdateien ergibt genau 25.352 (gemessen). Also **nicht geraten**:
  die Zahlen stehen fest, der Grund nicht.
* **Nicht nachgezogen.** Ein Nachlauf über die 889 kurzen Texte kostet über
  OpenRouter (0,02 USD / 1 Mio Token — deutlich unter einem Cent), ist aber ein
  bezahlter Netzaufruf und damit Sebastians Entscheidung, nicht die des Nachtlaufs.
* Der Bildindex selbst bleibt unverändert; dieses Werkzeug schreibt nichts.

## Tests

`backend/tests/test_bestand_und_handy_uebergabe.py` — 5 neue Tests, Datei
**28 passed**:

* Zählung und `meta`-Kopf stimmen (echte Mini-SQLite im `tmp_path`),
* fehlender Index wird als Lücke gemeldet und ist mit `bild_index=None` abschaltbar,
* ein beschriebenes Foto ohne Vektor wird **benannt** (Zahl + Lücke),
* **keine Inhalte** aus dem Index im Bericht (keine Beschreibung, kein Ordner),
* kaputte Datei und fehlende Datei melden `fehlt` statt zu werfen.

Rückwärts: die bestehenden Tests der Datei (Orte/OSM, Übergabe) blieben
unverändert grün.

## Geänderte Dateien

* `tools/foto_sortierung/bestand_pruefen.py` (neue Funktionen, neuer Abschnitt,
  Kopf-Docstring nachgezogen)
* `backend/tests/test_bestand_und_handy_uebergabe.py` (5 Tests)
* `docs/changelog-2026-10-10-nachweis-bildindex.md` (diese Datei)
