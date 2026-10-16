# Keine leere Blase im Chat, während der Agent arbeitet (S6)

**Datum:** 16.10.2026 · **Schritt:** S6 der Dauerlauf-Liste (To-do Punkt 3 „Leere Blase im
Chat") · **Plan:** `.hermes/plans/2026-10-16_hermes-ui-leere-blase.md` · **Betroffen:**
`frontend/app.js`, `frontend/index.html` (`?v=`-Bump), neuer Test
`frontend/tests/test_leere_blase.js`

## Ausgangslage (Sebastians Befund)

„Wenn der Agent zu arbeiten beginnt, erscheint eine Blase mit ‚…' und daneben steht, was er
gerade tut. **Das findet Sebastian gut.** Fehler: Darüber erscheint eine **leere Blase**."

Die untere „Denke nach…"-Bubble (Drei-Punkte-Animation + Arbeitsschritt-Text) ist gewollt.
Die leere Blase darüber war ein **Anzeigefehler**: die Antwort-Blase im Stream-Weg wurde beim
**ersten Häppchen** eingeblendet, ohne den Inhalt anzusehen
(`frontend/app.js`, Zweig `if (daten.delta)`: `zeigeAntwortBlase()`). Liefert das Modell zuerst
nur einen **Zeilenumbruch oder ein Leerzeichen** — das kommt vor, wenn die eigentliche Arbeit
noch läuft (Werkzeugaufrufe) und der Text erst danach kommt — dann wurde die Blase sichtbar
und blieb **leer** (nur der Zeitstempel stand darin), solange gearbeitet wurde.

## Jetzt

- **Eine Antwort-Blase wird nur noch mit lesbarem Inhalt gezeigt.** Neue reine Funktion
  `blaseHatLesbarenText(contentDiv)` (`frontend/app.js:800`) prüft den **gerenderten** Text
  einer Blase (nicht den Rohtext): ein führender Zeilenumbruch, ein Leerzeichen oder ein
  Markdown-Rest wie „`**`" zählt **nicht** als Inhalt.
- Die Blase wird an **beiden** Stellen des Stream-Wegs nur über diese Prüfung eingeblendet:
  beim Häppchen (`if (antwort.trim()) zeigeAntwortBlase();`, `:6656`) und nach dem Zeichnen
  (`if (blaseHatLesbarenText(contentDiv)) zeigeAntwortBlase();`, `:6672`).
- `finishReply` nutzt **dieselbe** Funktion (`:2808`) statt einer eigenen, doppelt gepflegten
  Bedingung — eine Regel, eine Stelle.
- Ohne lesbaren Text bleibt die Blase **unsichtbar** (kein Kasten, kein Zeitstempel); der
  Fortschritt steht weiter in der unteren „Denke nach…"-Bubble, die Sebastians Zitat ausdrücklich
  gut findet. Sie wird **nicht** angefasst.

## Belege

- **Der Fehler ist nachgestellt, nicht behauptet.** Der neue Test
  `frontend/tests/test_leere_blase.js` lädt die **echte** `frontend/app.js` in eine kleine
  DOM-Umgebung (Elemente aus der echten `index.html`), ruft das **echte** `sendMessage()` auf und
  liefert den Stream als kontrollierte Attrappe: erst ein Häppchen mit **nur einem Zeilenumbruch**,
  danach echten Text. Geprüft wird am DOM (sichtbar/unsichtbar, Inhalt), nicht im Quelltext.
  - **Alter Stand** (`git show HEAD:./frontend/app.js`) → **rot**: „sichtbare Antwort-Blasen: 1
    (Inhalt „15:42:10")" — genau die leere Blase mit nichts als dem Zeitstempel.
  - **Neuer Stand** → **grün**: 0 sichtbare Blasen nach dem leeren Häppchen, danach genau **eine**
    sichtbare Blase, und sie trägt den Text „Hallo".
  - Aufruf: `node frontend/tests/test_leere_blase.js frontend/app.js` (Gegenprobe mit dem
    HEAD-Stand als Argument, Rezept im Dateikopf).
- **Alle Frontend-Tests:** `backend/.venv/Scripts/python -m pytest tests/test_frontend_node.py -q`
  → **39 passed** (38 vorhandene + der neue).
- **Cache:** `frontend/index.html` lädt `app.js?v=20261016F` (vorher `…E`) — ohne den Bump hätte
  der Browser die alte Datei behalten.
- **Prüfbefehl** `cd backend && .venv/Scripts/python -m pytest tests/ -q` → siehe Tor-Protokoll
  im Commit-Log (pre-commit-Haken).

## Ehrliche Grenzen

- **Belegt ist der Mechanismus, nicht Sebastians Einzelfall.** Nachgestellt ist der Weg, der eine
  leere Blase erzeugt — mit einem Stream, der mit einem Zeilenumbruch beginnt. Ob **genau dieser**
  Weg sein Fall war, ist damit nicht bewiesen; die Regel greift aber unabhängig davon an **allen**
  Stellen, die die Antwort-Blase einblenden: ohne lesbaren Text ist sie unsichtbar.
- **Nicht angefasst:** die untere „Denke nach…"-Bubble und die Kosten-/Kontextleiste (Sebastians
  Regel). Gedanken-Blasen (`🧠 Gedanke`) hatten ihre Leer-Schutzregel schon (Wunsch 25.09.2026).
- **Geprüft wurde im Modell der Seite, nicht am Gerät:** der Test fährt den echten Sendeweg in einer
  DOM-Attrappe; eine Sichtprüfung am Handy/Browser mit echtem Modellaufruf ist in diesem Durchlauf
  **nicht** erfolgt (sie hätte Geld gekostet und ist für diese reine Anzeigeregel nicht nötig).
  Bleibt Sebastians Abnahme am Gerät.
