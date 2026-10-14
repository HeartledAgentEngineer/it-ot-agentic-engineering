# B0 beantwortet: Kennt der Chat den Österreich-Urlaub 2022? (nur gemessen, nichts geändert)

14.10.2026, Nachtlauf. Auftrag: `.hermes/plans/2026-10-12_fliesstext-und-urlaubserzaehlung.md`,
Abschnitt **B0** — dort ausdrücklich als **Hermes-Auftrag** vermerkt („sensibel, nur Zahlen").
Gelesen wurde ausschließlich lokal; kein Bild geöffnet, kein Modell aufgerufen, kein Netz,
keine Kosten, kein Gerät.

**Ehrlich vorweg:** Abschnitt 1 des Plans `2026-10-10_personen-orte-erzaehlungen.md` hatte ein
früherer Lauf dieser Nacht bereits beantwortet (Dokument
`changelog-2026-10-14-orte-im-antwortweg.md`). B0 überschneidet sich damit teilweise; hier stehen
die in B0 **ausdrücklich verlangten Zahlen**, die dort fehlten (Jahr 2022, GPS-Deckung, Deckung der
drei Wege). Keine Doppelarbeit in der Sache, sondern die fehlende Hälfte.

---

## 1. Frage B0-a: Kennt `fotos_uebersicht` den Österreich-Urlaub 2022 schon (Event-Name)?

**Antwort: Er kennt die Reise als Anlässe — aber ohne jeden Ortsnamen.**

Gemessen an `C:/Users/sebas/foto_sortierung/fotos_uebersicht.json` (Stand 27.09.2026, 2.098
Events, Feld `events[]` mit `jahr, kategorie, name, dateien, quelle`):

| Messung | Wert |
|---|---|
| Events im Reisefenster 30.07.–06.09.2022 | **100** (100 verschiedene Namen, alle `quelle = neu`) |
| davon mit Kategorie „Urlaub" | **48** |
| Dateien dieser Events zusammen | **663** |
| Event-Namen mit „Österreich"/„österreich" | **0** |
| Event-Namen mit „Griechenland", „Korfu", „Tirol"/„Tyrol" | **0** |
| Event-Namen mit „Urlaub"/„Reise" (ganze Datei) | 107 (Jahre: 2024: 48, 2026: 21, **2022: 18**, 2023: 12, 2019: 4, 2025: 3, 2020: 1) |

Die Namen der Reise-Anlässe sind **motivbasiert**, nicht ortsbasiert: „Berg und Tal",
„Wanderung im Wald", „Reise und Urlaub", „Essen und Trinken" — je Tag mehrfach durchnummeriert
(„(02)", „(03)" …). Ein Ortswort, das ein Nutzer sagen würde, steht in **keinem** Titel.

**Folge:** Beantwortet der Chat heute über diesen Weg, sieht er Reise-Anlässe (Kategorie „Urlaub"),
kann aber „Österreich" nirgends nachschlagen — genau das, was Sebastian beobachtet hat.

## 2. Frage B0-b: Wie viele Bilder 2022 mit Land Österreich in `orte.jsonl` — wie viele ohne GPS?

Feldaufbau `orte.jsonl` (9.259 Zeilen): `bild_id, land, land_code, region, ort, abstand_km,
aufnahme, quelle, version`. Eine Zeile existiert **nur** für Bilder mit GPS (Quelle
`offline-geonames`) — „ohne Ortszeile" heißt also: **kein GPS / kein Ortsbezug**.

Gemessen über den Union-Plan `sortierplan_reich_gesamt.json` (26.424 verschiedene `fileid`) gegen
`orte.jsonl`:

| Menge | Bilder | mit Ortszeile | **ohne Ortszeile** | AT | GR | DE |
|---|---|---|---|---|---|---|
| **alle Bilder des Plans** | 26.424 | 9.259 | **17.165 (65,0 %)** | 412 | 830 | 6.854 |
| **alle Bilder mit Jahr 2022** | 3.199 | 2.655 | **544 (17,0 %)** | **383** | 771 | 1.417 |
| Sammlung 2022 (ohne Papas Album) | 3.086 | 2.599 | 487 | 337 | 771 | 1.415 |
| Papas Album 2022 | 113 | 56 | **57 (50,4 %)** | **46** | 0 | 2 |

- **Österreich 2022 = 383 Bilder**, alle mit Ortszeile (sie sind ja daraus gezählt).
  Die 412 AT-Zeilen der ganzen Datei verteilen sich auf die Jahre 2014: 1, 2018: 28,
  **2022: 383** — Österreich ist praktisch **eine** Reise.
- Griechenland 2022 = 771 Bilder (AT 383 + GR 771 = 1.154 = der Reisekern).
- **544 der 3.199 Bilder von 2022 haben gar keine Ortszeile** (= kein GPS). Für diese Bilder
  ist über den Ortsweg **kein** Aufnahmeort bestimmbar — sie können nur über Datum/Anlass
  gefunden werden. Bei Papas Album von 2022 ist es sogar **jedes zweite** Bild (57 von 113).

**Grenze der Messung, ehrlich:** Bilder **ohne** Ortszeile haben auch kein Aufnahmedatum in
`orte.jsonl`; „544" ist deshalb über das Plan-Jahr gemessen, nicht über das Reisefenster.
Eine fenstergenaue Zahl für die ohne-GPS-Bilder ist mit den vorhandenen Dateien nicht belegbar.

## 3. Die drei vorhandenen Wege im Reisefenster gegenübergestellt

Fenster 30.07.–06.09.2022 (`aufnahme` aus `orte.jsonl`, nur Bilder **mit** Ortszeile):

| Weg | Abdeckung im Fenster | Quelle |
|---|---|---|
| Ortsstufe (GPS → Land/Region/Ort) | **1.362 Bilder** — GR 771, AT 383, DE 124, IT 73, AL 11 | `orte.jsonl` |
| Anlass-/Event-Liste (was der Chat heute liest) | **100 Events / 663 Dateien**, kein Ortswort | `fotos_uebersicht.json` |
| Bildbestand des Jahres 2022 insgesamt | **3.199 Bilder** (2.655 mit Ortszeile) | Union-Plan |

Damit ist das Verhältnis klar: der Anlass-Weg erreicht im Fenster **663 Dateien** und kennt kein
Land; der Ortsweg erreicht **1.362 Bilder** und kennt kein Wort des Nutzers („Korfu" kommt in
keiner Datei vor — im Vorlaufdokument belegt); und **544 Bilder des Jahres 2022 haben überhaupt
keinen Ortsbezug**, sind also nur über Datum und Anlass erreichbar.

Dazu die Gegenprobe: die Kategorien der 100 Fenster-Events sind gemischt —
Urlaub 48, Konzerte_Party 21, Ausflüge 11, WG 6, Sonstiges 4, Rezepte 3, Freunde 3, Familie 2,
Hobbys 2. Das Fenster ist also **nicht** die Reise allein; eine Reise-Stufe muss den Ort als
Kriterium benutzen, nicht das Datum allein.

## 4. Was daraus für Paket B folgt (Feststellung, keine Änderung)

1. **B2 braucht beide Quellen, nicht eine.** Der Ort allein (GPS) lässt 544 Bilder von 2022
   (und 65 % des ganzen Bestands) liegen; der Anlass allein kennt keine Ortsnamen. Eine
   Reise-Stufe muss **Anlass-Kennungen ⊕ Ortszeilen** verbinden — die Verknüpfung läuft über
   die Bildkennung, die beide Seiten tragen (`bild_id` in `orte.jsonl`, `datei_kennungen` in
   `ordner_ereignisse.jsonl`).
2. **Achtung bei der Anlassquelle: es gibt zwei, und sie gruppieren verschieden.** Diese Datei
   (`fotos_uebersicht.json`, 2.098 Events) liefert im Fenster **100 Anlässe / 663 Dateien**.
   `ordner_ereignisse.jsonl` dagegen (2.268 Anlässe, `datum` in **2.190** Zeilen gefüllt,
   nur 78 ohne) liefert im selben Fenster **36 Anlässe / 899 Dateien** — und ganz anders
   zusammengesetzt (19 x Kategorie „Lieblingsbilder", 3 x „Urlaub"). Beide Wege sind also
   **nicht austauschbar**; eine Reise-Stufe muss sich auf eine Quelle festlegen oder beide
   über die Bildkennung verbinden.
   (Erste Fassung dieses Abschnitts behauptete, `datum` sei leer — **falsch**, gemessen:
   nur 78 der 2.268 Zeilen. Berichtigt.)
3. **B1 (Übergabe) ist messbar dringend:** `anlass_namen.jsonl` und `orte.jsonl` stehen in
   keiner Übergabeliste, und `orte.jsonl` liest heute **kein** Dienst (Vorlaufdokument).
   Ohne B1 kann B2 am Handy gar nichts finden.
4. **Weiterhin Sebastians Entscheidung, nichts gebaut:** die Reise-Stufe selbst, der
   Wortschatz-Abgleich („Korfu" ↔ Region „Ionian Islands"), und ob Papas Album (Hälfte ohne
   Ortszeile) zuerst nachgezogen wird.

## 5. Grenzen dieses Schritts

- **Nur gelesen.** Keine Datei geändert, nichts gelöscht, kein `--schreiben`, kein Schreibzugriff
  auf pCloud, kein Geräteeingriff (heute kein Gerät am Kabel, `adb devices` leer).
- Kein Vision-Aufruf, kein fremdes Modell, keine Kosten — die Messung ist Textzählung.
- **Keine personenbezogenen Angaben im Dokument:** nur Zahlen, Kategorien und Motivwörter der
  Anlass-Titel; keine Koordinaten, keine Pfade, keine Namen, keine Kennungen.
- Gemessen am PC-Stand vom 14.10.2026; `fotos_uebersicht.json` datiert vom 27.09.2026 und kann
  hinter dem Bestand her sein (der Unterschied der beiden Anlasswege untereinander — 663 gegen 899
  Dateien — ist **nicht** mit einem Alter erklärbar; die Zählweise ist eine andere, und welche die
  richtige ist, wird hier nicht behauptet).
