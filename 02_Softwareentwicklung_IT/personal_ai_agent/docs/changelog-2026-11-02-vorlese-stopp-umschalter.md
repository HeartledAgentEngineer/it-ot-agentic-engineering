# Changelog 02.11.2026 — Vorlese-/Stopp-Knopf überall als Umschalter

## Wunsch (Sebastian)
„Wenn ich vorlesen lasse, muss der Vorlese-Button mit Stopp verbunden sein, damit ich wieder
drücken kann, damit es aufhört. Ist ganz wichtig, überall." Bisher startete jeder Vorlese-Knopf
nur; zum Anhalten am selben Knopf gab es keinen Weg.

## Lösung
Jeder Vorlese-Knopf ist jetzt ein Umschalter:
- Erster Druck startet das Vorlesen, der Knopf zeigt **„⏹ Stopp"**.
- Zweiter Druck auf **denselben** Knopf hält an und setzt den Knopf auf seine Beschriftung zurück.
- Startet ein **anderer** Vorlese-Knopf, wird der vorher laufende zurückgesetzt (nur einer aktiv).
- Am **Ende** des Vorlesens (Audio zu Ende, Browserstimme fertig, Fehler) setzt sich der Knopf von
  selbst zurück — kein Hängenbleiben auf „⏹ Stopp".

## Änderung (nur Frontend)

### `frontend/erzaehlen.js` (Cache `?v=20261102D` → `20261102E`)
- Merker `aktiverVorleseKnopf` (nur ein Knopf gleichzeitig aktiv).
- Reine Funktion `erzaehlVorleseLabel(spielt, standard)` → `'⏹ Stopp'` beim Spielen, sonst die
  gemerkte Standardbeschriftung (testbar, kein DOM).
- `_knopfVorlese(knopf, spielt)` merkt die Originalbeschriftung in `dataset.vorleseStandard`, setzt
  Text, Klasse `vorlesen-aktiv` und `aria-pressed`.
- `_vorleseFertig()` — ein zentrales Zurücksetzen, aus allen Ende-Pfaden aufgerufen
  (WebAudio `onended`, HTMLAudio `onended`, SpeechSynthesis `onend`/`onerror`).
- `vorlesenText(sprech, knopf)` / `vorlesen(quelleId, knopf)` / `allesVorlesen(knopf)` nehmen den
  Knopf entgegen; `vorlesenStoppen()` setzt den aktiven Knopf zurück. Umschalt-Prüfung
  (`aktiverVorleseKnopf === knopf` → anhalten) in den Startwegen.
- Alle acht Vorlese-Knöpfe reichen sich selbst durch (Personen Gruppe/Bild, Geschichten
  Gruppe/Bild, Bildbeschreibung, Alles, Bildgeschichte, Anlassgeschichte).
- Neuer globaler Umschalter `window.vorleseTextMitKnopf(sprech, knopf)` für andere Dateien.

### `frontend/bild_beschreibung.js` (Cache `?v=20261102A` → `20261102B`)
- `bildBeschreibungVorlesen(txt, knopf)` nutzt bevorzugt `window.vorleseTextMitKnopf` (Umschalter),
  sonst den alten Weg, sonst Browserstimme.
- Der Vorlese-Knopf des Lese-Kastens reicht sich selbst durch.

### `frontend/app.js` (Cache `?v=20261102E` → `20261102F`)
- Der Vorlese-Knopf der Bildbeschreibung im Vollbild-/Quiz-Editor (`descVorlesenBtn`) reicht sich
  selbst durch — damit auch dort der zweite Druck anhält.

## Tests (offline, Node)
- Neu `frontend/tests/test_erzaehlen_vorlese_stopp.js` (20 Prüfungen): Label-Funktion
  (spielt → „⏹ Stopp", sonst Standard, ohne Standard kein Hängenbleiben); Verdrahtung
  (Knopf-Durchreichung, Merker, Umschalt-Prüfung, zentrales Zurücksetzen, globaler Umschalter);
  alle acht Knöpfe reichen sich durch; Cache `erzaehlen.js?v >= 20261102E`.
- Registriert in `backend/tests/test_frontend_node.py` (`ZUORDNUNG` → `erzaehlen.js`).

## Beleg Rot vor Grün
- Vor der Umsetzung: `node tests/test_erzaehlen_vorlese_stopp.js` bricht ab
  (`Funktion nicht gefunden: erzaehlVorleseLabel`). Nach der Umsetzung: „Alle Prüfungen bestanden."
- Zwei Nachbartests pinnten `erzaehlen.js?v=20261102D` exakt
  (`test_erzaehlen.js`, `test_erzaehlen_hand_gesichter.js`) und einer die alte Bindungsform ohne
  Knopf-Argument (`test_erzaehlen_geschichte_getrennt.js`). Diese Pins wurden auf den neuen Stand
  nachgezogen (Ursache: brittle Exakt-Pins, nicht ein Fehler der Umsetzung).

## Offen / nächste Schritte
- Erzählen-Filter („Ereignis suchen" / „Jahr") funktionieren nicht — eigener Slice.
- Neustart-Schirm: visuelles Feedback + Rückkehr in den Chat — eigener Slice.
- 50-Pixel-Gesichtsfilter als allgemeine Einstellung + Gesichtszuordnung neu laufen lassen.
- Löschen von Geschichten/Erinnerungen in der Oberfläche sichtbar verdrahten.
