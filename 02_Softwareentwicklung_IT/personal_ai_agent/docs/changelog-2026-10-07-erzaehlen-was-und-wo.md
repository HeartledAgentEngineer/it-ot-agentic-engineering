# Änderungsprotokoll 07.10.2026 — Erzählen: Was und wo je Bild

Sebastians Wunsch: zu den einzelnen Bildern eine genauere Beschreibung mit Ort sehen, dazu, wer wo
drauf ist. Die Personen zeigt das Erzählen seit dem 06.10. Beschreibung und Ort lagen bisher nur
am PC:
- `bild_beschreibungen.jsonl` aus dem Kontaktbogen-Lauf
- `bild_orte.csv` aus `orte_aus_karte.py --zuordnen`

## Neu

**Dienst** (`erzaehl_service.bilder_info(kennung)`):
- Liefert je Bild eines Anlasses die Beschreibung und den Ort (`landmarke`, `art`, `ort`). Dazu
  kommen die drei häufigsten Orte der Gruppe.
- **Keine Hausnummern, keine Koordinaten.** Aus `bild_orte.csv` werden nur `landmarke`,
  `landmarke_art` und `ort_osm` gelesen.
- Bei mehreren Fassungen einer Beschreibung gilt die letzte. Leerraum wird geordnet, höchstens
  600 Zeichen.
- Je Datei gibt es einen Zwischenspeicher, der erst bei geänderter Zeit oder Größe neu liest. So
  wird die große Beschreibungsdatei am Handy nicht bei jedem Aufruf gelesen.
- Fehlen die Dateien, sind die Angaben leer. Es gibt keinen Fehler.

**Route:** `GET /api/erzaehlen/ereignisse/{kennung}/bilder-info` antwortet wie die
Personen-Route immer mit 200 und `ok`/`error`.

**App** (`erzaehlen.js`, `index.html`, `style.css`):
- **Übersicht:** Eine Zeile „📍 Orte: Gasthaus am See und Testdorf“ unter den Personen.
- **Einzelbild:** Ein Block „📍 Ort: …“ mit der Beschreibung darunter.
- Fehlt beides, bleibt der Block weg. Die Angaben kommen nach, die Übersicht steht sofort. Eine
  veraltete Antwort nach einem Anlass-Wechsel wird verworfen.
- **🔊 Alles vorlesen** liest Orte bzw. Ort und Beschreibung mit.
- Reine Funktionen `erzaehlOrtText` (Flug-Fotos: „Während des Flugs“) und `erzaehlOrteUebersicht`.
- Cache-Bump: `erzaehlen.js?v=20261007C`, `style.css?v=20261007C`.

**Übergabe ans Handy:**
- `bild_beschreibungen.jsonl` und `bild_orte.csv` stehen in der Dateiliste von `start-termux.sh`
  und `termux/agent-ensure.sh`.
- Der Wächter in `test_uebergabe_uebernehmen.py` kennt jetzt zwölf Dateien.
- `tools/handy/gruppen_aufs_handy.py` kann mit `--dateien` beliebige Dateien aus dem
  `--basis`-Ordner senden. Nur reine Dateinamen sind erlaubt. Ohne den Schalter bleibt alles wie
  bisher.

## Senden (Sebastian oder Hermes, Kabel am Handy)

```powershell
& backend\.venv\Scripts\python.exe tools\handy\gruppen_aufs_handy.py --basis "$HOME\foto_sortierung" --dateien bild_beschreibungen.jsonl bild_orte.csv --senden
```

Danach die App neu starten.

Ein Hinweis zu `bild_orte.csv`: Am besten erst neu zuordnen, mit dem neuen Standard ohne
Adresstabellen (`docs/changelog-2026-10-07-orte-nur-um-fotos.md`). Die Hausnummern liest die App
zwar nie, die Datei am Handy bleibt aber schlanker.

## Prüfung

- Neu `backend/tests/test_erzaehlen_bilder_info.py`, 5 Tests mit erfundenen Daten:
  - Beschreibung, Ort und häufigste Orte, ohne Hausnummern
  - fehlende Dateien
  - Zwischenspeicher liest eine geänderte Datei neu
  - Route mit Treffer und Fehlschlag
  - Sender mit eigener Dateiliste, fehlende Datei, Pfad abgewiesen, Trockenlauf
- `frontend/tests/test_erzaehlen.js` Abschnitt 13: Textbausteine, Verdrahtung, versteckte
  Blöcke, Vorlesen, CSS-`[hidden]`. Alle 25 Frontend-Tests sind grün.
- Prüfstand Edge headless, 375 px, mit Attrappe:

  | Ansicht | Ergebnis |
  |---|---|
  | Übersicht | „Orte: Gasthaus am See und Testdorf“ |
  | Bild 1 | Ort und Beschreibung |
  | Bild 2 | nur Ort, Beschreibung versteckt |
  | Bild 3 | Block weg |

  Keine Fehler in der Konsole.
- Prüfbefehl: siehe Commit.
