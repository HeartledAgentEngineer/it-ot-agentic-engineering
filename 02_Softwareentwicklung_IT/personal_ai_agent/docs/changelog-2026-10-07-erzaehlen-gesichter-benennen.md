# Änderungsprotokoll 07.10.2026 — Erzählen: Gesichter im Einzelbild benennen (#11b)

Sebastians Wunsch vom 06.10. war: Die Personen im Erzählen sollen „auch zum Anlernen mitbenutzt
werden". Der Anlass ist das Fotobuch. Die ersten Seiten zeigen Vater, Mutter und Sebastian in den
ersten Wochen nach der Geburt. Diese Gesichter bilden nach dem Nachtrag eigene, noch unbenannte
Gruppen, und das Erzählen zeigte bisher nur „N Personen noch ohne Namen".

## Neu

**Dienst und Route.** `gruppen_quiz.gesichter_auf_bild(fileid)` liefert die Gesichter eines Fotos.
Die Route dazu ist `GET /api/gruppen/bild-gesichter?fileid=…`. Je Gesicht kommen `gid`
(bild_id:index), `kennung`, `name` (bestätigt oder `null`) und der Rahmen `bbox` mit
`breite`/`hoehe`. Die Gesichter stehen von links nach rechts sortiert.

Es fehlt dieselbe Auswahl wie bei der Personenzeile:
- ausgeschlossene Gesichter
- als „kenne ich nicht“ markierte Gruppen
- Video-Standbilder
- Gesichter ohne Rahmen

Der Zwischenspeicher hängt an Zeit und Größe der Datei.

**App** (`erzaehlen.js`): Im Einzelbild steht eine Leiste mit runden Gesichtsausschnitten. Sie
werden aus dem geladenen Großbild geschnitten (`gruppenAusschnitt` aus `gruppen_quiz.js`). Ohne
Maße erscheint ein 👤-Platzhalter. Unbenannte Gesichter tragen „Wer ist das?“ mit gestricheltem
Rand.

Antippen öffnet ein Feld mit großem Ausschnitt:

| Gesicht | Möglichkeiten |
|---|---|
| unbenannt | **Name** eingeben oder **Fremde Person** |
| benannt | **✕ Ist nicht X**: Das Gesicht verlässt die Gruppe |

Beim Tippen erscheinen Vorschläge wie im 👥-Quiz über `GET /api/gruppen/suche`: zuerst die schon
benannten Personen, dann die Telefonbuch-Kontakte (📇). Antippen speichert sofort. Bei einem
Kontakt wird die `kontakt_id` mitgeschickt, damit das Profil mit dem Kontakt verknüpft ist. Enter
speichert den getippten Namen. Ein `datalist` gibt es nicht, das Quiz hat es durch die Suche
ersetzt.

Gespeichert wird über die Wege des 👥-Quiz:
- Name und fremd über `POST /api/gruppen/antwort`.
- „Ist nicht“ über `POST /api/gruppen/ausschliessen`.

**Ein Name gilt für die ganze Gruppe**, also für alle Bilder dieser Person. Gibt es den Namen
schon, verknüpft der Dienst die Gruppen wie im Quiz als „gleich“.

Nach jeder Änderung steht eine Meldung mit **↩ Rückgängig** da (`POST /api/gruppen/rueckgaengig`,
nimmt die letzte Antwort zurück). Danach werden die Gesichter des Bildes und die Personen der
Gruppe neu geladen.

**Schutz und Bedienung.**
- Eine Sperre verhindert doppeltes Speichern.
- Eine veraltete Antwort nach einem Bildwechsel wird verworfen.
- Escape im Namensfeld schließt nur das Feld.
- Waagerechtes Wischen in der Gesichterleiste scrollt die Leiste und wechselt nicht das Bild.
- Namen stehen nur per `textContent` im Dokument.

Reine Funktionen: `erzaehlGesichtLabel`, `erzaehlGesichtMeldung`.

Cache-Bump: `erzaehlen.js?v=20261007D`, `style.css?v=20261007D`.

## Prüfung

- `backend/tests/test_gruppen_quiz.py`, 3 neue Tests:
  - Reihenfolge links nach rechts mit Namen. Video und fehlender Rahmen fallen weg, eine kaputte
    Kennung wird abgewiesen.
  - Ausgeschlossene und fremde Gruppen fehlen; Rückgängig bringt die fremde Gruppe zurück.
  - Benennen wirkt sofort, über die Route; ohne `fileid` kommt 422.
  - Alle 76 Tests der Datei sind grün.
- `frontend/tests/test_erzaehlen.js`, Abschnitt 14: Texte, Verdrahtung, Sperre, Wisch-Schutz,
  versteckte Blöcke, CSS-`[hidden]`. Alle 25 Frontend-Tests sind grün.
- Prüfstand Edge headless mit 375 px und erfundenem Vorschaubild mit drei farbigen „Gesichtern“:
  - Der Ausschnitt trifft das Gesicht: Das Mittelpixel hat die Gesichtsfarbe.
  - Benennen schickt `{kennung, art: "name", name}`, die Leiste zeigt danach den Namen.
  - Ein Kontakt-Vorschlag schickt zusätzlich `kontakt_id`.
  - „Ist nicht Testpapa“ schickt `{kennung, gesichter: [gid]}`, das Gesicht verschwindet.
  - Rückgängig wird gesendet.
  - Ein Wisch in der Leiste lässt das Bild stehen, ein Wisch auf dem Bild blättert weiter.
- Prüfbefehl: siehe Commit.

## Offen

- Den Wunsch aus #9/#11c erfüllt das noch nicht. Gemeint ist, aus dem Erzählten („das ist mein Papa
  und ich“) die Gesichter selbst zuzuordnen.
