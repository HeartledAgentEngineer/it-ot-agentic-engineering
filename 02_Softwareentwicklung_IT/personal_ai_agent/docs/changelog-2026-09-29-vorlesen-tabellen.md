# Änderungsprotokoll 29.09.2026: Tabellen richtig vorlesen

## Was
- `frontend/app.js` bekommt zwei neue reine Funktionen:
  - `tabelleFuerStimme(block)`: Jede Tabellenzeile wird ein Satz. Die erste Zelle nennt die Zeile, die übrigen Zellen tragen ihre Spaltenüberschrift. Leere Zellen werden ausgelassen, Trennzeilen, Striche und Sternchen fallen weg. Vorweg sagt die Stimme „Tabelle mit N Zeilen".
  - `tabellenImTextFuerStimme(text)`: wendet das auf alle Tabellen eines ganzen Textes an.
- Mitlese-Vorleser (`addSpeakControls` → `naechstesStueck`): Eine Tabelle wird als **ganzes** Stück genommen. Solange sie noch einläuft, wartet der Vorleser. Vorher wurde sie Zeile für Zeile ohne Kopfzeile gelesen.
- Die Browser-Rückfallstimme (`speakResponse`) nutzt dieselbe Umwandlung.
- Cache-Bump: `app.js?v=20260929A`.

## Warum
Befund Sebastian am Handy: Tabellen in Antworten wurden als Zellbrei mit Strichen vorgelesen, man hörte nicht, welcher Wert zu welcher Spalte gehört.

## Prüfung
- Neu: `node frontend/tests/test_vorlesen_tabellen.js` mit 12 Prüfungen, Exit 0.
- Alle 19 Frontend-Tests laufen mit Exit 0. `test_foto_galerie.js` wurde auf die neue Versionsnummer nachgezogen.
- `node --check frontend/app.js` ist grün.
- Nicht am Gerät geprüft: Den Klang prüft Sebastian nach `git pull` am Handy, denn am PC läuft bewusst kein Backend.
