# Änderungsprotokoll 29.09.2026: Kein Quiz-Autostart, Recherche-Blase, Link-Farbe

## Befund (Sebastian, Handy)
1. Beim Öffnen der App „ging das Quiz wieder los".
2. Eine Recherche-Antwort lief rechts über die Sprechblase hinaus, Text war abgeschnitten.
3. Links in Antworten waren dunkelblau auf dunklem Grund.

## Ursachen
1. `stelleVerlaufWiederHer()` → `_baueChronikBlase()`: Die letzte Verlaufsnachricht mit `[QUIZ-OFFEN]` wurde über `_baueOffeneQuizKarte()` als **laufende** Quiz-Karte nachgebaut, mit `_quizAktiv = true`. Eine einmal nicht beantwortete Frage startete so bei jedem Öffnen neu. Das Frontend startet das Quiz sonst nur auf Befehl.
2. `.sources` ist ein Flex-Container. Die Quellen-Links hatten `white-space: nowrap`, aber kein `min-width: 0`. Flex-Kinder schrumpfen dann nicht unter ihre Textbreite, deshalb griff die Ellipse nie, und lange Titel schoben den Inhalt über den Blasenrand.
3. Es gab keine Regel für `.message-content a`, also galt die Browser-Standardfarbe.

## Änderung
1. Die offene Frage aus dem Verlauf erscheint nur noch als Historie (Bild) mit dem Knopf **„▶ Quiz fortsetzen"** (`_quizFortsetzenKnopf` → `quizFortsetzen()`). `_baueOffeneQuizKarte` ist entfernt, weil sie nicht mehr genutzt wird.
2. `.sources a`: `display: block; min-width: 0; max-width: 100%`.
3. `.message-content a`: helle Farbe `#c9d4e3`, unterstrichen, `overflow-wrap: anywhere`; beim Überfahren weiß.
4. Cache-Bump `app.js?v=20260929B`, `style.css?v=20260929B`.

## Prüfung
- Neu: `frontend/tests/test_start_ohne_quiz_und_lesbarkeit.js` mit 6 Prüfungen. Vor der Reparatur waren alle 6 rot, danach sind sie grün.
- Alle 20 Frontend-Tests laufen mit Exit 0. `test_foto_galerie.js` wurde auf die neuen Versionsnummern nachgezogen.
- `node --check app.js` ist grün.
- Am Gerät nicht geprüft: Der Blick am Handy folgt nach `git pull` und Neustart. Am PC läuft bewusst kein Backend.
