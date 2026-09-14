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
- `frontend/app.js` — **Race-Fix (Skip während des Ladens, „zwei Quiz"):**
  1. `quizUeberspringen` bricht die laufende Gesichts-Analyse jetzt **ganz am
     Anfang** ab (VOR dem ersten `await`), nicht erst nach dem
     `/antwort`-Fetch. Sonst konnte die Analyse in der Zwischenzeit fertig
     werden und die Karte noch als Quiz (Rahmen/Ja-Nein) rendern.
  2. In der Sofort-Analyse prüft der Abort **danach gegen den lokalen**
     `abortCtrl` statt gegen die globale `_analyseAbort`. Beim Skip ruft
     `naechsteQuizRunde()` die globale auf einen NEUEN Controller fürs nächste
     Bild um; eine hängende Analyse des vorigen Bildes hätte sonst den neuen
     (nicht abgebrochenen) Controller geprüft und das Quiz doppelt gerendert.
- `frontend/app.js` — **Lauf-Token „nie zwei Quizze parallel" (Wunsch Sebastian,
  Cache-Bust `bW`):** `naechsteQuizRunde` hat KEINEN Guard gegen parallele Läufe
  und wird von vielen Skip-Wegen (skipSofort, `quizUeberspringen`,
  `markiereBildErledigt`/`weiter`/`Naechstes Bild`, und mehrere `setTimeout`)
  aufgerufen. Jeder dieser Wege kann eine neue Runde starten, während die alte
  noch in ihrem `await` hängt → zwei Quiz-Karten/-Sessions nebeneinander. Fix:
  eine globale `_rundeToken`-Zählung. Jede `naechsteQuizRunde` nimmt sich
  `token = ++_rundeToken` und prüft nach jedem `await` (`abgeloest()`), ob eine
  neuere Runde gestartet wurde; wenn ja, verwirft sie sich selbst (kein Rendern,
  keine zweite Karte). Da alle Ablöse-Wege am Ende selbst `naechsteQuizRunde()`
  aufrufen, inkrementieren sie den Token und lösen die alte Runde zwingend ab.
- Cache-Bust `app.js?v=20260914bW`.

## Verifikation
- `node --check frontend/app.js` → Exit 0.
- Manuell im Browser (Quiz starten mit personenlosem Lieblingsbild): das Bild
  erscheint sofort mit Untertitel, es gibt keinen Ja/Nein-Button, danach kommt
  das nächste Bild.