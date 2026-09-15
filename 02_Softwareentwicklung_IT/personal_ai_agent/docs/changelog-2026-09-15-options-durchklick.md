# Changelog 2026-09-15 — Abfragen mit mehreren Fragen: Durchklicken statt Liste

## Auslöser (Sebastian)

„Wenn so 'ne Abfrage kommt mit Frage und verschiedenen Antworten zum
Durchklicken, dann müssen die nacheinander gestellt werden, nicht alle
untereinander. Dann weiß ich ja gar nicht, was passiert, wenn auf einmal 12
Antworten da untereinander sind und die Fragen nicht mal dort stehen."

## Ursache

`frontend/app.js` hatte zwei getrennte Fehler im Smart-Output für rohe
Hermes-Auswahl-Menüs:

1. `parseOptionsMenue` sammelte ALLE nummerierten Zeilen der ganzen Ausgabe in
   EINE flache Optionsliste — bei mehreren Fragen standen also alle Antworten
   untereinander.
2. Als „Frage" galt nur der Text VOR der ersten Option. Alle weiteren
   Fragetexte (zwischen den Optionsgruppen) wurden verworfen → die Fragen waren
   in der UI gar nicht mehr zu sehen; es blieb eine nackte Antwortliste.

## Fix (frontend/app.js)

- `parseOptionsMenue` zerlegt die Ausgabe jetzt in **Frage-Blöcke**:
  `{fragen:[{frage, optionen:[…]}], optionen:[…flach], frage}`.
  Regel: eine Textzeile NACH bereits gesehenen Optionen eröffnet die nächste
  Frage. Erkennung unverändert für „1. …", „1) …" und „❯ 1. …", Pipes (`|`)
  werden weiter zu Zeilen gewandelt. Die flache Liste bleibt als Feld
  `optionen` erhalten (Rückwärtskompatibilität).
- `bauOptionsUi`: bei EINER Frage unverändert (Frage + klickbare Optionen,
  Klick sendet die Option).
- NEU `_bauOptionsAssistent(box, fragen)`: bei MEHREREN Fragen ein
  Durchklick-Assistent — sichtbar sind immer „Frage i von N", der Fragetext
  und NUR die Optionen dieser Frage; bereits gegebene Antworten stehen dezent
  als Häkchenliste darunter. Erst nach der letzten Wahl geht GENAU EINE
  Nachricht an den Agenten, Format:

  ```
  Meine Antworten:
  1) <Frage 1> → <Wahl 1>
  2) <Frage 2> → <Wahl 2>
  ```

  So ist die Zuordnung Antwort↔Frage eindeutig, statt 12 Antworten ohne
  Kontext abzuschicken. Der Assistent wird beim Laden aus dem Verlauf erneut
  aus der gespeicherten Rohtext-Nachricht aufgebaut (Verlauf bleibt
  append-only, unverändert).

## Cache-Bust

`index.html`: `app.js?v=20260915cA` → `app.js?v=20260915dA`.

## Verifikation (frisch ausgeführt)

```
node --check frontend/app.js                      # Syntax OK
node frontend/tests/test_options_assistent.js frontend/app.js
  -> ERGEBNIS: alle Prüfungen grün, exit=0
Kontrolllauf gegen den ALT-Stand (git show HEAD:…/app.js):
  -> 14 Prüfungen rot, exit=1
```

`frontend/tests/test_options_assistent.js` schneidet die echten Funktionen aus
`app.js` und fährt sie in Node mit DOM-Stub: Parser (2 Fragen, Optionen
korrekt zugeordnet, Frage 2 sichtbar), Assistent (erst Frage 1, nach Klick
Frage 2, genau eine gesendete Nachricht mit beiden Antworten und beiden
Fragetexten).

## Doku

`docs/faehigkeiten-hermes-delegation.md` Abschnitt „3. Smart-Output"
beschreibt Parser und Assistent jetzt codegenau; Testpfad ergänzt.
