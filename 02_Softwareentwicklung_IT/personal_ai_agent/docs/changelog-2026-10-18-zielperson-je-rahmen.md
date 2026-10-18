# 18.10.2026 — Schritt G: Zielperson JE RAHMEN (Auswahlliste statt „ist nicht <Name>")

Plan „Rahmeneditor im Detailbild" (Fassung 13), Abschnitt 4, **Schritt G** (Auftragspunkt 2) aus dem
16.10.-Auftrag und Sebastians Wunsch aus To-do-Punkt 6 (S9): *„Auswahlliste (Dropdown) statt nur
‚ist nicht <Name>'"*. Schritt E hat den Rahmen von Hand aufziehen lassen und verwies für die
Zuordnung ausdrücklich auf **Schritt G** („Die Zuordnung kommt mit dem Ziel-Personen-Menü") — dieser
Schritt löst das ein.

## Was neu ist

| Ort | Neu |
|---|---|
| `frontend/app.js`, `rahmenPersonWahl(e, idx)` | Die Person, die für **diesen** Rahmen gilt: der eigene Eintrag `personen[idx]`, sonst die **globale** Zielperson (rückwärtsverträglich). `''` heißt ausdrücklich „unbekannt" (Schritt E) und fällt **nicht** auf die globale Person zurück |
| `frontend/app.js`, `rahmenPersonSetzen(e, idx, person)` | Setzt die Person für **einen** Rahmen (getrimmt; leerer Wert = zurück auf „unbekannt"). Ändert die globale Zielperson **nicht**. Ungültiger Rahmenindex = keine Wirkung |
| `frontend/app.js`, `rahmenPersonMenueListe(katalogNamen, aktuell)` | Einträge des Menüs: der gesetzte Wert zuerst, dann der Katalog — jeder Name genau einmal, Leerraum beschnitten, Leeres fällt weg |
| `frontend/app.js`, `editorSpeicherZiel(e, idx)` | Nimmt jetzt den **Rahmen** entgegen und holt die Person daraus. Ohne Angabe gilt Rahmen 0 — dieselbe Antwort wie vorher, wenn kein eigener Eintrag gesetzt ist |
| `frontend/app.js`, `speichereEditorRahmen` | Sendet mit der Person **dieses** Rahmens (`editorSpeicherZiel(e, idx)`) — auf einem Foto mit mehreren Personen schreibt jeder Rahmen seine eigene Zuordnung |
| `frontend/app.js`, `zeigeBildVollbild` (Werkzeugleiste) | Neues Menü **„👤 Person für diesen Rahmen …"** (`select`, Klasse `vollbild-person-wahl`): Auswahl aus dem Personenkatalog (`GET /api/gesichter`). Es zeigt immer die Person des **ausgewählten** Rahmens und füllt sich nach, wenn der Katalog erst später eintrifft. **Nicht** in der Referenz-Nachbearbeitung |
| `frontend/app.js`, `resync()` / `personWahlMalen` | Ein Rahmen mit eigener Person trägt deren **Namen** sichtbar (vorher war die Namensmarke nur bei „unbekannt"). Die Namensmarke wird bei jeder Auswahl neu gemalt |
| `frontend/index.html` | Cache-Schlüssel `app.js?v=20261018I` → **`20261018J`** |

## Was ausdrücklich NICHT geändert wurde

- **Rückwärtsverträglich:** ohne Menüwahl gilt weiter die globale Zielperson (`_aktuelleQuizPerson`).
  Der Riegel aus Schritt A2 (kein Speichern ohne passendes Bild) ist unverändert; der Riegel aus
  Schritt E (ein Rahmen mit `personen[idx] === ''` wird nicht gespeichert) ebenfalls.
- Kein **Löschen** irgendwo, kein Server-Schreibvorgang aus dem Menü selbst — geschrieben wird erst
  mit **💾 Speichern**.
- Die Auswahlliste im Quiz („ist nicht &lt;Name&gt;") bleibt bestehen; das Menü ist der neue Weg
  **je Rahmen**, kein Ersatz.

## Belege (in diesem Lauf selbst ausgeführt)

- **Neuer Test** `frontend/tests/test_quiz_rahmen_person_je_rahmen.js` (Abschnitte A–G, führt die
  **echten** Funktionen aus): **alle Prüfungen bestanden, Exit 0** —
  A: zwei Rahmen, zwei Personen, **globale Person leer** → jeder Rahmen trägt seine eigene (Zustand
  `_quizEditor.personen`, `rahmenPersonWahl`, `editorSpeicherZiel`);
  B: der **Sendeaufruf** nennt je Rahmen die richtige Person (Zähler **2**, gesendet „Anna" und „Tim",
  derselbe Bildpfad, Referenz-Weg unberührt);
  C: **Gegenprobe** — ohne Menüwahl gilt weiter die globale Zielperson, und das Setzen für einen
  Rahmen ändert sie **nicht**;
  D: ein von Hand gezogener Rahmen („unbekannt") sendet nichts, wird über das Menü zuordenbar, und
  eine Leerwahl setzt ihn zurück;
  E: ungültiger Rahmenindex/negativer Index verändern nichts;
  F: Menü-Liste (eigener Wert vorn, keine Doppelten/Leerzeilen);
  G: Verdrahtung im Quelltext (Menü, `editorSpeicherZiel(_quizEditor, sel)`, kein Menü in der
  Referenz-Nachbearbeitung, Namensmarke, Cache-Schlüssel `>= 20261018J`).
- **Gegenprobe gegen den HEAD-Stand** (eigenes Messskript außerhalb des Repos,
  `…/cache/scratch/gegenprobe-g-2026-10-18/gegenprobe.js`, extrahiert die echten Funktionen **aus dem
  HEAD-`app.js`**): Zuordnung „Anna"/„Tim" je Rahmen gesetzt, globale Person leer —
  **HEAD:** `editorSpeicherZiel("Anna")` `ok: false`, **0 Sendeversuche**;
  **neuer Stand:** `ok: true`, Person `"Anna"`, **1 Sendeversuch**.
  Die Fähigkeit gab es vorher also nachweislich **nicht** (kein leer-grüner Test).
- **Nachgezogene Tests** (jeder pinnte die alte Fassung fest, keiner wurde gelöscht oder abgeschwächt):
  `test_quiz_rahmen_ziel.js` (Funktionsliste + `editorSpeicherZiel(e)` → `(e, idx)`),
  `test_quiz_rahmen_mehrfach.js` (dito), `test_quiz_rahmen_unbekannt.js` (Funktionsliste; der
  Cache-Schlüssel wurde vorher als **fester Buchstabe** `20261018I` geprüft und wäre bei jedem
  legitimen Bump rot geworden → jetzt Muster + Mindeststand), `test_quiz_referenz_meldung.js`
  (Funktionsliste).
- **Alle Frontend-Tests** über den Prüfbefehl:
  `.venv/Scripts/python.exe -m pytest tests/test_frontend_node.py -q` → **43 passed**, Exit 0.

## Offen / ehrliche Grenzen

- Der Wirkungsnachweis am **Gerät** (auf einem Foto zwei Gesichter zwei Personen zuordnen, speichern,
  neu laden) ist am PC nicht nachstellbar und bleibt **Sebastians Abnahme am Handy**.
- Das Menü zeigt nur, welche Person der **ausgewählte** Rahmen trägt; auf dem Bild selbst steht der
  Name am Rahmen (neu), die Farbe bleibt wie bisher (ausgewählt = grün).
- Kommt der Personenkatalog nicht ans Netz, stehen im Menü nur die bereits gesetzten Namen —
  der Ladefehler wird nicht still verschluckt (`quizKatalogFehlerText()` nennt ihn im Quiz-Suchfeld).
