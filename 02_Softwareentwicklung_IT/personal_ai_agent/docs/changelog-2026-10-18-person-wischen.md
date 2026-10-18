# Wischen zur nächsten/vorherigen Person (S8-Rest 3, 18.10.2026)

Sebastians Wunsch zu To-do Punkt 10, wörtlich: „**Wischen statt Klicken:** Ist man auf einer Person,
soll man mit **Wischen nach links/rechts** zur nächsten bzw. vorherigen Person wechseln können
(Ergänzung Sebastian). Gilt für Handy/Tablet; am PC zusätzlich sinnvoll: Pfeiltasten links/rechts."

Die zwei vorigen Schritte haben die **Liste** (alphabetisch, Suchzeile, Sprungmarken), den **Filter
„mit/ohne Erinnerung"** und den **Weg über den Knopf** zu den Personen ohne Erinnerung gebaut. Offen
war genau das hier: der **Finger-Weg** von Person zu Person, ohne zurück in die Liste zu gehen — und
am PC die Pfeiltasten. Damit ist Punkt 10 bis auf die Abnahme am Gerät abgearbeitet.

## Was der Code jetzt tut

- **Wischen am Personenbereich** (`#gruppen-person` in `frontend/index.html`): `pointerdown` merkt
  den Startpunkt, `pointerup` rechnet die Bewegung aus. **Nach links = nächste Person, nach rechts =
  vorherige.** `pointercancel` und `pointerleave` verwerfen einen begonnenen Wisch (kein
  Geisterwechsel).
- **Reine Funktionen** (`frontend/gruppen_quiz.js`), alle ohne DOM prüfbar:
  - `gruppenWischRichtung(startX, startY, endX, endY)` → `'weiter'` (Finger nach links),
    `'zurueck'` (nach rechts) oder `''`. Es ist nur dann ein Wisch, wenn die waagerechte Strecke
    mindestens `WISCH_MINDEST_PX = 60` beträgt **und** deutlich (`WISCH_UEBERGEWICHT = 1.5`)
    überwiegt — sonst rollt Sebastian die Seite, statt zu blättern.
  - `gruppenReiheNamen(personen)` — die Namen in Anzeige-Reihenfolge.
  - `gruppenNachbarName(personen, name, richtung)` — der Nachbar in der Reihe; **leer** am Anfang
    bzw. Ende. Steht `name` nicht in der Reihe, beginnt `weiter` vorne und `zurueck` hinten
    (dieselbe Regel wie beim Weiter-Knopf).
  - `gruppenWischHinweis(richtung)` — ehrlicher Klartext am Rand („Das ist die letzte Person in
    dieser Ansicht.") statt eines stillen Nichtvorgangs.
  - `gruppenWischGesperrt(ziel)` — beginnt der Wisch in einem **Bedienfeld** (`INPUT`, `TEXTAREA`,
    `SELECT`, `BUTTON`) oder auf einer **Kachel** (`gruppen-kachel`, die den langen Druck zum
    Markieren kennt), gehört der Finger dem Feld bzw. der Kachel — es wird **nicht** geblättert.
  - `gruppenWischTaste(key)` — `ArrowRight` → `weiter`, `ArrowLeft` → `zurueck`, sonst leer.
- **In welcher Reihe wird gewischt?** In der **angezeigten** Reihe: die gerade gesetzten Filter
  (Suchzeile, Gruppenauswahl, Erinnerungsfilter) **und** die alphabetische Sortierung gelten — über
  dieselbe Funktion `gruppenPersonenGefiltert(...)`, die auch die Liste zeichnet. Es gibt keine
  zweite Reihenfolge. Der **Weiter-Knopf** bleibt für die Sonderreihe „ohne Erinnerung" zuständig;
  das Wischen blättert die ganze Ansicht (so ist der Wunsch formuliert: „zur nächsten bzw.
  vorherigen Person").
- **Kein Ringlauf** (bewusst, wie beim Weiter-Knopf): am Anfang und am Ende passiert nichts außer
  der Meldung. Sonst landete man beim Weiterwischen wieder bei den Personen, die man in dieser Runde
  schon durch hat. Umkehrweg, falls Sebastian doch einen Umlauf will: eine Zeile in
  `gruppenNachbarName` (die `|| ''`-Rückfälle) — dann braucht es aber eine Ansage, dass die Reihe von
  vorn beginnt.
- **Tastatur am PC:** ein `keydown`-Zuhörer am Dokument reagiert auf ← und → — aber nur, wenn
  **wirklich eine Person offen** ist (`zustand.person`) und der Fokus **nicht** in einem Bedienfeld
  steht. Ohne offene Person (nach „← Alle Personen") tut keine Taste etwas.
- **Hinweiszeile im Profil** (`#gruppen-person-wisch`, Klasse `gruppen-meta`): „Wischen nach
  links/rechts wechselt zur nächsten bzw. vorherigen Person – am PC gehen auch die Pfeiltasten ←
  und →." Ohne sie wüsste niemand am Gerät, dass es das gibt.
- Cache: `gruppen_quiz.js?v=20261018D` → **`20261018E`** (`index.html`). **Am CSS nichts geändert**
  (die Zeile ist eine normale `gruppen-meta`-Zeile, das Profil ist eine Spalte).
- **Kein Backend-Eingriff**: geladen wird über den vorhandenen Weg
  `GET /api/gruppen/person?name=…` (dieselbe Funktion `personOeffnen`, die auch Liste und
  Weiter-Knopf benutzen) — eine Ladequelle, keine zweite.

## Belege (in diesem Lauf ausgeführt)

- **Neu `frontend/tests/test_gruppen_wischen.js` — Exit 0** (sechs Prüfungen, führt die **echten**
  Handler in der DOM-Attrappe aus, nur die HTTP-Antworten sind Attrappen):
  1. Wisch nach links bei „Bea" lädt **genau** `GET /api/gruppen/person?name=Cem` (Protokoll der
     Anfragen), Titel wechselt, Rückmeldung „nächste Person"; Wisch nach rechts lädt genau
     „Bea" zurück; mit Suchzeile „a" (nur Anna) blättert der Wisch **nicht** weg und meldet
     „letzte Person" — die Filter gelten.
  2. Ränder: bei „Anna" (erste) rechts wischen → kein Wechsel, Meldung „erste Person"; bei „Cem"
     (letzte) links wischen → kein Wechsel, Meldung „letzte Person" (**kein Ringlauf**).
  3. Kurze Bewegung (20 px) und schräge Bewegung (70 px waagerecht, 200 px senkrecht) blättern
     **nicht**; ein `pointercancel` verwirft den begonnenen Wisch. Dazu die reine Regel
     (`gruppenWischRichtung`) mit ihren Grenzen.
  4. Bedienfelder behalten den Finger: Wisch, der im `TEXTAREA` beginnt, lädt nichts;
     `gruppenWischGesperrt` erkennt Feld, tief verschachteltes Feld, `SELECT`/`BUTTON`, Kachel und
     lässt eine normale Stelle durch.
  5. **Pfeiltasten** über den echten Dokument-Zuhörer: → lädt genau „Cem", ← lädt „Bea"; `ArrowUp`
     und „a" laden nichts; im Namensfeld (`INPUT`) wirkt ← / → **nicht**; nach „← Alle Personen"
     lädt keine Taste mehr. Dazu `gruppenWischTaste`.
  6. Reine Nachbar-Regel: Reihenfolge aus der Anzeige (`gruppenPersonenGefiltert` mit Umlaut
     „Änne" vor „Bea"), Ränder leer, unbekannter Name beginnt vorne bzw. hinten, leere Reihe,
     Ein-Personen-Reihe, Texte der Rand-Meldung.
- **Gegenprobe gegen den alten Stand** (HEAD-Fassungen von `gruppen_quiz.js`, `index.html`,
  `style.css` in einen Ordner **außerhalb des Repos**, dieselbe Prüfdatei): **6 von 6 rot** —
  „der Wisch-Hinweis fehlt im HTML", „der Anfang wird nicht gemeldet", `gruppenWischRichtung is not
  a function`, `gruppenWischGesperrt is not a function`, „die Pfeiltasten sind nicht verdrahtet",
  `gruppenReiheNamen is not a function`. Die Fähigkeit gab es vorher nachweislich nicht.
- **Alle Frontend-Tests grün**: `python -m pytest tests/test_frontend_node.py -q` → **47 passed**
  (Exit 0) — die 46 Prüfdateien des Vorlaufs plus diese neue.
- **Rendermessung im echten Browser** (Edge headless, **echtes** `markup` der Personenansicht und
  **echtes** `style.css`, Skript außerhalb des Repos, Personenansicht sichtbar geschaltet):
  **1374 px** → Hinweiszeile links 16, rechts 1343, Höhe **19 px** (eine Zeile), **kein**
  überbreites Element, Dokument `1374 = Fenster 1374`; **496 px** (schmaler öffnet Edge headless
  nicht) → zwei Zeilen (37 px), kein Überlauf, `496 = 496`; **360-px-Rahmen** (Edge headless öffnet
  nicht schmaler, deshalb der Rahmen wie im Vorlauf) → drei Zeilen (56 px), links 16, rechts 329,
  kein überbreites Kind.
- **Volles Tor** über den Commit-Haken (`cd backend && .venv/Scripts/python -m pytest tests/ -q`,
  Zahl und Log im Journal des Dauerlauf-Plans).

## Ehrliche Grenzen

- **Nicht geprüft:** die Finger-Bedienung am echten Gerät (Wischen auf dem Handy) — das bleibt
  Sebastians Abnahme. Der Browser-Beleg zeigt nur die **Geometrie** der Hinweiszeile; der Test
  beweist die **geladenen Anfragen**, nicht die Wahrnehmung am Gerät.
- **Kein Ringlauf** ist eine Entscheidung dieses Laufs (Begründung oben, Umkehrweg benannt) — sie
  ist in der Beschriftung nirgends erklärt, nur im Verhalten spürbar.
- Das Wischen blättert die **angezeigte** Reihe, nicht nur die Personen ohne Erinnerung; wer gezielt
  die Reihe „ohne Erinnerung" durcharbeiten will, nimmt weiter den Knopf.
- Ein Wisch, der auf einer **Kachel** beginnt, blättert nicht (dort gilt der lange Druck) — am Rand
  einer Kachel muss man etwas daneben wischen.
- Kein Backend-Eingriff, kein Bild geöffnet oder gesendet, kein Vision-/pCloud-Aufruf, keine
  Geräteeingriffe, nichts gelöscht, keine echten Personennamen (nur erfundene wie „Anna").
  **Kosten 0 USD.**
