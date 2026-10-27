# Bild-Editor B1 (Backend) — 26.10.2026

Planschritt B1 von „Bild-Editor für jedes Bild" (Plan Fassung 8). Nur Backend, Sperrliste und
eine kleine Weiche im Erzählen-Frontend; die Editor-Oberfläche (B4/B5) und die Neuerkennung
pro Bild (B2) kommen später.

## Was gebaut ist

### Datenmodell `bild_korrekturen.json` (handy-eigen)

Liegt in `basis()` des Gruppen-Quiz (`~/foto_sortierung`, übersteuerbar mit `GRUPPEN_QUIZ_BASIS`).
Konstante `gruppen_quiz.KORREKTUREN_DATEINAME`. Die Datei wird **nur am Handy** geschrieben und
weder vom Holer noch vom Uploader bewegt (siehe Sperrliste unten).

```json
{"version": 1,
 "bilder": {"<fileid>": {
     "rahmen":  {"<index>": {"bbox_norm": [x, y, w, h] | null, "quelle": "hand" | "erkennung",
                              "name": "…" | null, "breite": …, "hoehe": …}},
     "entfernt": ["<index>", …]}}}
```

- `bbox_norm` ist normiert (0..1: links, oben, Breite, Höhe), jeder Wert gerundet auf 6 Stellen;
  Breite und Höhe mindestens `BBOX_MIN` (0,01), `x+w` und `y+h` höchstens 1.
- Index < 1000: erkanntes Gesicht aus `gesicht_zuordnung.jsonl` (verschobener Rahmen und/oder
  handy-eigener Name; `entfernt` blendet es aus). Index >= `HAND_INDEX_AB` (1000): Hand-Gesicht.
  Hand-Indizes **vergibt nur der Server** (größter vorhandener Hand-Index + 1, mindestens 1000).
- Eine `gid` (`<fileid>:<index>`) muss zur `fileid` des Aufrufs gehören.
- `breite`/`hoehe` (Pixel) bei einem Hand-Gesicht sind optional; fehlen sie, werden die Maße eines
  erkannten Gesichts desselben Bildes genommen, sonst ist `bbox` (Pixel) `null`.
- Ein leerer Bildeintrag (kein Rahmen, nichts entfernt, keine fremden Schlüssel) wird nicht aufbewahrt.
  Fremde Schlüssel **innerhalb** eines Bildeintrags bleiben erhalten; ein Aufruf ohne echte Änderung
  schreibt nichts und legt keinen Protokolleintrag an (`geaendert: false`).
- Ein Index >= 1000 ohne Hand-Eintrag (z. B. ein erkanntes Gesicht mit so hohem Index) ergibt die
  Meldung „Dieses Gesicht gibt es auf dem Bild nicht.“ statt eines Absturzes; nichts wird geschrieben.
- Geschrieben wird atomar (`_atomar_schreiben`: Temp-Datei + `os.replace`, `.vorher`-Sicherung).
  Die Datei ist tolerant lesbar (`_korrekturen_lesen`); fremde Schlüssel bleiben beim Schreiben
  erhalten.

### Eine gemeinsame Sicht `_bild_sicht` (rein additiv)

`GET /api/gruppen/bild-gesichter?fileid=` (`gesichter_auf_bild`), „Bilder mit X"
(`bilder_mit`, `bild_kennungen_person`) und `personen_auf_bildern` (Erzählen) lesen **dieselbe**
zusammengeführte Sicht (`_sicht_quellen` + `_bild_sicht` / `_sicht_namen`). Bilder ohne Korrekturen
gehen weiter den bisherigen schnellen Weg; Bilder mit Korrekturen (auch reine Hand-Gesicht-Bilder,
die das Register nicht kennt) die Sicht.

- Alte Felder bleiben unverändert (`gid`, `index`, `kennung`, `bbox`, `breite`, `hoehe`, `name`);
  neu: `bbox_norm`, `name_quelle` (`gruppe` | `zuordnung` | `handy` | `null`), `quelle`
  (`erkennung` | `hand`). Hand-Gesichter haben `kennung: null`, `bbox`/`breite`/`hoehe` sofern die
  Maße bekannt sind.
- Namenspriorität: handy-eigen vor Einzelzuordnung vor Gruppenname.
- Filter wie bisher (Ausgeschlossene und „kenne ich nicht" fehlen, von Hand Zugeordnete bleiben),
  dazu `entfernt` und der verschobene Rahmen.
- Handy-eigene Namen zählen bei „Bilder mit X" als bekannt (`unbekannt` bleibt falsch).

### `POST /api/gruppen/bild-rahmen`

Body: `{fileid, aenderungen: [...]}`, höchstens `BILD_RAHMEN_MAX` = 30 Änderungen. Eine Änderung ist
`{gid, bbox_norm?, name?}`, `{gid, entfernen: true}` oder `{neu: true, bbox_norm, name?}`.

1. **Alles zuerst prüfen**, bei einem Fehler wird nichts geschrieben (HTTP 200, `ok: false`,
   `geschrieben: false`, deutscher `fehler`).
2. `bild_korrekturen.json` atomar schreiben + Protokolleintrag `art: "bild_rahmen"` mit `aktion`,
   `fileid` und `vorher` (Stand des Bildeintrags vor dem Aufruf, `null` = gab es nicht).
3. Gruppenanteile: Name einer **bereits benannten** Person (Groß/Klein egal) an einem erkannten
   Gesicht läuft über `zuordnen`; Entfernen eines erkannten Gesichts über `ausschliessen(aufheben=True)`.
   Ein neuer Name bleibt handy-eigen und erreicht `personen_vorgaben.json`/den PC nie. In
   `personen_vorgaben.json` landet nie ein Index >= 1000.
4. Alle Protokolleinträge eines Aufrufs tragen dieselbe `aktion`.
5. Antwort: `ok`, `teilweise`, `geschrieben`, `fileid`, `aktion`, `neu` (vergebene gids), `teile`
   (je Teil `teil`, `ok`, `geaendert`, ggf. `fehler`) und `gesichter` (neue Sicht). Scheitert ein
   Gruppenanteil nach dem Schreiben der Korrekturen, steht das ehrlich als `teilweise: true` mit
   Klartext in `fehler` — nichts wird still verschluckt.

Entfernen eines Hand-Gesichts löscht nur den eigenen Eintrag in `bild_korrekturen.json` (die einzige
Löschfunktion in B1). Entfernen eines erkannten Gesichts: zuerst werden feste Zuordnungen dieses
Gesichts aufgehoben (Protokollfeld `vorher_zugeordnet`), dann folgt der Ausschluss — sonst würde der
PC-Leser (`personen_gruppieren`) mit `PersonenFehler` abbrechen.

### `zuordnen` hebt Ausschlüsse auf (auch der bestehende Quiz-Weg)

`zuordnen` entfernt vorhandene Ausschlüsse dieser Gesichter gegen das **neue** Ziel (jeder Vorschlag
der Person). Sie stehen im Protokoll als `ausschluesse_aufgehoben`; Rückgängig stellt sie wieder her.
Neue Parameter: `ausschliessen(..., aufheben=False, _extra=None)` und `zuordnen(..., _extra=None)`.

### Rückgängig

- `rueckgaengig` kennt `bild_rahmen` (`_bild_rahmen_zuruecknehmen`: stellt den `vorher`-Stand des
  Bildeintrags wieder her; `null` entfernt ihn).
- Hat der letzte offene Eintrag eine `aktion`, nimmt **ein** Rückgängig alle offenen Einträge dieser
  `aktion` in umgekehrter Reihenfolge zurück (zuerst `zuordnen`/`ausschliessen`, zuletzt
  `bild_rahmen`); aufgehobene Zuordnungen und Ausschlüsse kommen zurück. Scheitert ein Teil,
  `teilweise: true` und Klartext. Umbau: `_offene_eintraege`, `_rueckgaengig_eintrag`,
  Konstante `ZURUECKNEHMBAR`.

### Sperrliste handy-eigener Namen

- `tools/handy/pcloud_dateien_holen.py`: `HANDY_EIGENE_NAMEN = ("bild_korrekturen.json",)`; die Datei
  wird nicht heruntergeladen und nicht in die Übernahmeliste geschrieben, Meldung
  „übersprungen: handy-eigen".
- `tools/pcloud/uebergabe_hochladen.py`: gleiche Konstante; `dateien_sammeln` (Einzeldatei und
  Ordnermodus), `hochladen` und `hochladen_ohne_ueberschreiben` lehnen den Namen ab.

### Frontend (Weiche in Erzählen)

`frontend/erzaehlen.js`: neue reine Funktion `erzaehlGesichtHandHinweis`; `gesichtSpeichern` sendet
bei Hand-Gesichtern (`quelle: "hand"`) **keine** Gruppenaktion, sondern meldet „Hand-Gesicht –
Bearbeitung im Bild-Editor." Erkannte Gesichter (und Antworten ohne `quelle`) laufen unverändert.
Cache-Bump `erzaehlen.js?v=20261026B` in `index.html`.

## Nachgezogene bestehende Stellen

- `tools/foto_sortierung/gesicht_wege_messen.py`: die Filterzeilen der Detailbild-Auswahl stehen
  jetzt in `_bild_sicht`/`_sicht_quellen`; `anzeige_orte` sucht in der Vereinigung der Rümpfe
  (`FILTER_FUNKTIONEN`). Der zugehörige Wächtertest prüft gegen dieselbe Vereinigung.
- `tests/test_gruppen_quiz.py::test_gesichter_auf_bild_links_nach_rechts_mit_namen`: statt des
  Gleichheitstests der ganzen Gesichtsstruktur eine Teilmengenprüfung der alten Felder plus Prüfung
  der drei neuen Felder.
- `tests/test_erzaehlen.js` (Zeile 344) und `tests/test_frontend_node.py` (Zuordnung des neuen
  JS-Tests).

## Tests

- Neu `backend/tests/test_bild_editor_b1.py`: **80 Tests** (55 Testfunktionen), offline, erfundene
  fileids/Namen, Basisordner per Fixture umgeleitet, Prüfung dass das echte Heimverzeichnis leer
  bleibt. Deckt Datenmodell, Index >= 1000, Additivität, gemeinsame Sicht (Bilder mit X, Erzählen),
  Alles-oder-nichts, Teilfehler, Entfernen/Zuordnen mit Aufheben (inkl. PC-Leser ohne
  `PersonenFehler`), Rückgängig je `aktion`, Sperrliste.
- Neu `frontend/tests/test_erzaehlen_hand_gesichter.js` (läuft in `test_frontend_node.py` mit).
- Rot vorab belegt: `73 failed, 5 passed` bzw. JS „nicht gefunden: erzaehlGesichtHandHinweis".
- Grün: siehe Bericht der Ausführung (Befehl und Endzeile dort).
- Bekannte, nicht von B1 stammende Rot-Fälle im Worktree: `test_pcloud_uebergabe.py::
  test_skripte_sind_syntaxgeprueft_und_reine_lf` (`pcloud-uebernehmen.sh` hat CRLF im Worktree-
  Checkout) und drei `test_frontend_node.py::test_quiz_rahmen_*` — beides vor B1 identisch rot.

## Offen (nicht B1)

- B2: `bild-erkennen` (Neuerkennung pro Bild).
- B4/B5: Editor-Oberfläche (Rahmen ziehen, Gesicht anlegen/entfernen/benennen).
- B6: Anbindung an die übrigen Bildansichten.
- Handy-Übernahme der Hand-Gesichter in Vektor-/Personenpfade bleibt bewusst aus (Hand-Gesichter
  haben keine Kennung und keinen Vektor).
