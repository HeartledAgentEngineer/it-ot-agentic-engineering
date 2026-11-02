# Changelog 02.11.2026 — Bild-/Anlassgeschichte getrennt von den eigenen Notizen (Plan G1)

## Anlass
Die erzeugte Bildgeschichte wurde bisher als Notiz gespeichert und stand im Notizfeld und in der
Notizliste. Beim nächsten Erzeugen wurde sie als „Notiz“ wieder in den Generator gespeist, die
Geschichte fraß sich selbst. Plan: `.hermes/plans/2026-11-02_geschichte-sprachmodell.md`, Schritt G1
(Altbestand-Sätze: `…_geschichte-altbestand-saetze.md`).

## Datenmodell (`geschichten.jsonl`, nur anhängend wie bisher)
- Neues optionales Feld `art`: `bildgeschichte` | `anlassgeschichte`. Keine `art` = Notiz.
- Neue `quelle` `generiert` (Geschichte vom Generator). Notiz-Quellen bleiben `tippen`, `sprache`, `import`.
- Neues Feld `notiz_bestaetigt` (nur echtes `true`): „Das ist eine Notiz“ trotz Treffer in der Altbestand-Erkennung.
- Korrekturen bleiben neue Zeilen mit `ersetzt: <id>`; angezeigt wird die neueste Fassung. Es wird nichts gelöscht oder umgeschrieben.

## Backend
- `services/erzaehl_service.py`:
  - EINE Regel `zeile_einordnen(zeile)` → `ist_notiz`, `ist_altbestand`, `art`. Reihenfolge: `art` gesetzt → Geschichte;
    `notiz_bestaetigt is True` → Notiz; `ist_erzeugt_alt` → Altbestand (keine Notiz); sonst Quelle tippen/sprache/import → Notiz.
  - Altbestand-Erkennung `ist_erzeugt_alt` über die Satzliste `ALTE_GENERATOR_SAETZE` (69 Sätze aus den vier alten Generatorfassungen
    1da2f9f, 27466f2, 96de1fc, 05db80b): ein Treffer der Gruppe „eindeutig“ im Text ODER mindestens zwei verschiedene Treffer
    der Gruppe „mehrdeutig“ am Satzanfang. Leerraum wird vereinheitlicht.
  - `eigene_notizen(ereignis_kennung, fileid)` ist die einzige Quelle der Generatoren. Ein mitgeschicktes `notiz` wird ignoriert.
  - `geschichten()` liefert jede Zeile mit der Einordnung; `ereignisse_liste` (Kachelzähler) zählt nur Notizen.
  - `geschichte_speichern(…, art, notiz_bestaetigt)` prüft `art` und `quelle`.
- `router/erzaehlen.py`: `GeschichteEingabe` mit `art` und `notiz_bestaetigt`; die Antwort des POST enthält die gespeicherte
  Zeile samt Einordnung. `notiz` in `KiGeschichteEingabe` / `AnlassGeschichteEingabe` wird angenommen, aber nicht mehr verwendet.
- `services/notizen_service.py`: der Chat liest nur noch Notizen (`ist_notiz`), keine Geschichten und keinen Altbestand.
- Die Vorlage `verschmelze_geschichte` bleibt in G1 unverändert (G2/G3/G4 folgen).

## Frontend (`frontend/erzaehlen.js`, `index.html`)
- Neu `istNotiz(zeile)`: liest `ist_notiz`; fehlt das Feld (alte Antwort), gilt `!art`.
- Notizliste, Zähler ✎ und „alles vorlesen“ zeigen nur Notizen. Die Geschichte steht in eigenen Lese-Bereichen
  `#erzaehl-bildgeschichte` und `#erzaehl-anlassgeschichte` (je mit 🔊), nicht im Notizfeld.
- „Bildgeschichte“ / „Anlass-Geschichte“ speichern die Geschichte als eigene Zeile (`art`, `quelle: generiert`, `ersetzt` = vorherige Geschichte);
  die alte Zeile bleibt in der Datei. Ein ungespeicherter Notizfeld-Inhalt wird vorher als Notiz gespeichert.
- „📖 Das ist keine Notiz, sondern eine Geschichte“ hängt genau eine Zeile mit `ersetzt` an.
- Nach dem Speichern steht eine neue Notiz bzw. Bildgeschichte ohne Neuladen am richtigen Ort.
- Latenter Fehler behoben: der Speichern-Knopf übergab das Klick-Ereignis als `ersetzt`-ID; jetzt Aufruf ohne Argument und Typprüfung.
- Cache-Bump `erzaehlen.js?v=20261102B`.

## Tests
- Neu `backend/tests/test_erzaehlen_geschichte_trennung.py` (70): Einordnung, Altbestand (12 Beispieltexte aus den vier Commits, mit erfundenen Daten),
  Generator-Quelle nur aus der Datei, Kachelzähler, Chat, POST-Antwort.
- Neu `frontend/tests/test_erzaehlen_geschichte_getrennt.js` (Zuordnung in `test_frontend_node.py`).
- Angepasst: `test_erzaehlen_ki_geschichte.py`, `test_notizen_service.py`, `test_erzaehlen_bilder_info_erweitert.py`
  (Notizen kommen aus der Datei, Fixtures mit `quelle`), `test_erzaehlen.js` (`istNotiz`, Version, Zahl der Vorlese-Knopf-Handler 4 → 6),
  `test_erzaehlen_hand_gesichter.js` (Version).
- Rotprobe: Backend-Tests gegen den Stand `HEAD` 69 failed / 1 passed (ein statischer Test), danach 70 passed.

## Grenzen
- Der Altbestand wird nur erkannt, nicht umgeschrieben. Eine fälschlich als Altbestand erkannte Notiz lässt sich mit `notiz_bestaetigt` zurückholen.
- Die Geschichte selbst bleibt die deterministische Vorlage; die Sprachmodell-Fassung ist G2 ff.
