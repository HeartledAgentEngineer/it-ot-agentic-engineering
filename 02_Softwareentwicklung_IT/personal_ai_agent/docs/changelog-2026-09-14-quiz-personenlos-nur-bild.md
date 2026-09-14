# Changelog — Quiz: personenlose Bilder ohne Ja/Nein (2026-09-14)

## Was
Beim Gesichter-Quiz wird ein Bild, bei dem **keine Person erkannt** wird
(0 erkannte Gesichter), jetzt automatisch nur noch mit dem Bild und der
Bildunterschrift **„keine bekannte Person erkannt"** angezeigt — ohne die
bisherige Ja/Nein-Abfrage („ist auf dem Bild doch jemand…?") und ohne eine
zweite Quiz-Session.

## Warum
Sebastian: „Wenn beim Laden eines Bilds keine Person erkannt wird, muss nicht
extra ein Ja/Nein-Button erscheinen — lieber nur das Bild mit Unterschrift."

## Änderungen
- `frontend/app.js` — `zeigeQuizKarte`, Fall `0 erkannte Gesichter`:
  statt der Ja/Nein-Box („✅ Ja → Person einzeichnen" / „❌ Nein → nächstes
  Bild") wird direkt `quizUeberspringen(pfad)` gerufen. Das baut die Karte auf
  „Bild + Bildunterschrift ‚🚫 Keine bekannte Person erkannt'" um und ruft
  `naechsteQuizRunde()` — ein Schritt, fließend weiter.
- `frontend/app.js` — Bildunterschrift-Text in `quizUeberspringen` auf
  „🚫 Keine bekannte Person erkannt" umbenannt.
- Cache-Bust `app.js?v=20260914bU`.

## Verifikation
- `node --check frontend/app.js` → Exit 0.
- Manuell im Browser (Quiz starten mit personenlosem Lieblingsbild): das Bild
  erscheint sofort mit Untertitel, es gibt keinen Ja/Nein-Button, danach kommt
  das nächste Bild.