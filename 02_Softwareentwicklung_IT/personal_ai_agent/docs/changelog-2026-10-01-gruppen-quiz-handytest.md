# Changelog 01.10.2026 (Nachmittag) — Personen benennen: Befunde aus dem ersten Handytest

Cloud-Sitzung (Branch `claude/epic-newton-51vx5l`); Zusammenführen nach `main`
übernimmt der PC (Issue #2). Ausgangslage: Sebastians erster Versuch am Handy
mit 👥 „Personen benennen“.

## Teil 1 — „= dieselbe Person“ tat scheinbar nichts, Wechsel unsichtbar

### Befund (Ursache vor Reparatur)

- **„= dieselbe Person“ bei unbenanntem Zwilling:** Das Backend speicherte nur
  das `gleich`-Paar. Die aktuelle Gruppe blieb offen, und `naechste()` lieferte
  **dieselbe Gruppe mit demselben Zwillings-Vorschlag** zurück. Die Oberfläche
  zeichnete also exakt dasselbe neu: Am Handy flackerte es kurz, sonst passierte
  nichts. Dasselbe galt für „≠ andere Person“.
- **Nach „Speichern“ kein sichtbarer Wechsel:** Die nächste Gruppe kam, sah aber
  oft gleich aus. Die größten Gruppen auf dem eigenen Handy sind meist der
  Besitzer selbst; das ist eine Vermutung, am Handy nicht gemessen. Es gab keine
  Nummer und keine Bewegung, an der man den Wechsel erkannt hätte.

### Änderung

Backend `backend/app/services/gruppen_quiz.py`:
- `naechste()` blendet Zwillings-Vorschläge aus, deren Paar schon entschieden
  ist (`gleich` **oder** `verschieden` in `personen_vorgaben.json`). Eine
  beantwortete Frage kommt nicht noch einmal.
- Neu `gruppe.verbunden`: die per `gleich` verbundenen, noch unbenannten
  Vorschläge (auch mehrstufig) mit je einem Beispielbild.
- Neu `_gleich_komponente()`: Beim Benennen und bei `gleich` mit bekanntem Namen
  bekommen alle verbundenen, **unbenannten** Vorschläge denselben Namen.
  Vorhandene Namen werden nie überschrieben. Jede Änderung steht in
  `namen_vorher`, deshalb nimmt „Rückgängig“ die Weitergabe mit zurück.
- Antwort `gespeichert.weitere`: Zahl der mitbenannten Vorschläge.

Frontend (`gruppen_quiz.js`, `index.html`, `style.css`):
- Kopfzeile zeigt „Vorschlag 1003“ (`#gruppen-nummer`, reine Funktion
  `gruppenNummer`).
- Beim Wechsel blendet die Karte mit einer kurzen Bewegung ein
  (`.gruppen-wechsel`, 0,45 s; abgeschaltet bei „Bewegung reduzieren“) und
  springt nach oben.
- Neu `#gruppen-verbunden`: „🔗 Verbunden mit 1 weiteren Vorschlag — der Name
  gilt für alle“ plus das Bild des verbundenen Vorschlags. Das ist das „Bild
  kommt dazu“, das am Handy fehlte.
- Klarere Rückmeldungen (`gruppenAntwortText`): „verbunden — der Name, den du
  jetzt vergibst, gilt für beide“, „… · auch für 2 verbundene Vorschläge“,
  „→ nächster Vorschlag“.
- Knopf „⏭ Später“ heißt jetzt „⏭ Weiter (später)“.
- Cache: `gruppen_quiz.js?v=20261001C`, `style.css?v=20261001C`
  (`frontend/tests/test_foto_galerie.js` prüft die CSS-Version exakt und ist
  nachgezogen).

### Prüfung

- `backend/tests/test_gruppen_quiz.py`: **36 passed** (31 → 36, fünf neue Tests:
  gleich ohne Namen, verschieden, Namensweitergabe mehrstufig + Rückgängig,
  gleich mit benanntem Zwilling, nie überschreiben).
- `frontend/tests/test_gruppen_quiz.js`: alle Prüfungen grün (neu: Nummer,
  Verbunden-Text, Rückmeldungen, Animation, Knopftext, IDs, Cache-Stand).
- Alle 25 Frontend-Testdateien Exit 0.
- Voller Prüfbefehl in der Cloud (Linux, `python3 -m pytest tests/ -q`):
  **3318 passed, 3 skipped, 5 failed**. Die 5 roten Tests (`test_agentbus`,
  `test_event_abgleich`, `test_foto_kategorien`, `test_foto_themen_vision` ×2)
  sind auf dem **unveränderten** `main` in derselben Umgebung ebenso rot, sie
  hängen also nicht an dieser Änderung. Vermutete Ursache: Sie prüfen
  Windows-Pfade ohne Unterscheidung von Groß- und Kleinschreibung. Das ist
  nicht belegt. Der maßgebliche Lauf ist der Windows-Prüfbefehl am PC beim
  Zusammenführen.

## Teil 2 — Schon benannte Person per Antippen zuordnen

### Befund

Gleicher Name verknüpft schon heute automatisch (`gleich`-Paar, Groß/Klein egal),
aber nur, wenn man den Namen **neu tippt**. Die Vorschlagsliste (`<datalist>`
`#gruppen-namen`) zeigt die Android-WebView oft gar nicht an. Das ist bekanntes
WebView-Verhalten und am Handy nicht gemessen.

### Änderung

- Neu `#gruppen-schnellnamen` über dem Namensfeld: alle schon vergebenen Namen
  als Knöpfe („Schon benannt — antippen, wenn es dieselbe Person ist:“). Ein
  Tipp speichert sofort wie „✓ Speichern“, samt Beziehung und Erinnerung aus
  den Feldern darunter. Falsch getippt? „↩ Rückgängig“.
- Reine Funktion `gruppenSchnellNamen(namen, max)`: ohne Leere und Doppelte
  (Groß/Klein egal), höchstens 40 Knöpfe, bei vielen Namen scrollbar.
- Namen nur per `textContent`, nie als HTML.
- `nameSpeichern(vorgabe)` nimmt optional einen Namen. Der Speichern-Knopf
  übergibt kein Klick-Ereignis mehr als Namen.
- Cache: `gruppen_quiz.js?v=20261001D`, `style.css?v=20261001D`.

### Prüfung

- `frontend/tests/test_gruppen_quiz.js`: alle Prüfungen grün (neu:
  Schnellnamen-Funktion, direkte Speicherung, nur Text, ID, Cache-Stand).
- Alle 25 Frontend-Testdateien Exit 0.
- Backend unverändert.
