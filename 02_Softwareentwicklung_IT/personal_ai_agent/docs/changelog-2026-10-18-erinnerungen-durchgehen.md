# Personen ohne Erinnerung nacheinander durchgehen (S8-Rest 2, 18.10.2026)

Sebastians Wunsch zu To-do Punkt 10, wörtlich: „dass ich eine Liste habe, die noch keine Erinnerung
haben, und dann nach und nach diese durchgehen kann und eine Sprachnotiz aufnehmen kann, als
Erinnerung innerhalb des benannten Personenprofils."

Der vorige Schritt (S8-Rest) hat die **Liste** und den **Filter „ohne Erinnerung"** gebaut. Offen
war der **Weg von einer Person zur nächsten**: heute muss man zurück in die Liste und die nächste
Zeile antippen. Dieser Schritt schließt genau diese Lücke — die **Aufnahme selbst** gibt es im
Personenprofil schon (Feld `#gruppen-person-notiz` mit dem 🎙-Knopf `#gruppen-person-mikro`, das
Diktat läuft über das vorhandene `starteFeldDiktat`), gespeichert wird sie als Erinnerung über
`POST /api/gruppen/profil` mit `notiz`.

## Was der Code jetzt tut

- **Neuer Knopf im Personenprofil** (`frontend/index.html`): `#gruppen-person-weiter`, Klasse
  `gruppen-knopf`, **von Anfang an `hidden`**. Beschriftung im Betrieb:
  „Nächste ohne Erinnerung (N) →", wobei **N** die Zahl der Personen ohne Erinnerung ist, die in
  dieser Ansicht **noch nach der gerade offenen** kommen; dazu ein `aria-label`, das das Ziel
  benennt („… — weiter zu <Name>").
- **Reine Funktionen** (`frontend/gruppen_quiz.js`):
  - `gruppenPersonenGefiltert(personen, frage, gruppe, erinnerung)` — die **eine** Regel für die
    Anzeige-Reihenfolge (Suchzeile UND Gruppenauswahl UND Erinnerungsfilter, alphabetisch). Die
    Liste zeichnet jetzt genau damit (`personenGefiltert()`), der Weiter-Weg benutzt dieselbe
    Funktion — es gibt keine zweite Filterregel.
  - `gruppenReiheOhneErinnerung(personen)` — die Namen ohne Erinnerung in Anzeige-Reihenfolge.
  - `gruppenRestOhneErinnerung(personen, name)` — die, die **nach** ``name`` noch kommen
    (leer, wenn keine mehr; steht ``name`` nicht in der Reihe, ist es die ganze Reihe, weil die
    Person dann schon eine Erinnerung hat).
  - `gruppenNaechsteOhneErinnerung(personen, name)` — die nächste Person (leer, wenn keine).
  - `gruppenWeiterText(rest)` — Beschriftung; leer, wenn nichts mehr zu gehen ist.
- **Kein Ringlauf** (bewusst): läuft die Reihe aus, verschwindet der Knopf, statt wieder bei der
  ersten Person zu landen — sonst käme man bei Personen heraus, die in dieser Runde schon dran
  waren. Die Beschriftung zählt genau die noch Kommenden, nicht die ganze Reihe.
- **Nach einer gespeicherten Erinnerung** führt der Knopf weiter zur nächsten, ohne Neuladen:
  die eigene Person zählt in der Reihe nicht mehr mit, auch wenn die geladene Liste ihre neue Zahl
  erst nach dem nächsten Laden trägt. Zurück in der Liste (`← Alle Personen`) wird sie ohnehin
  frisch geladen.
- Cache: `gruppen_quiz.js?v=20261018D` (`index.html`). **Am CSS nichts geändert** — der Knopf
  steht in `.gruppen-profil`, einer Spalte (`flex-direction: column`, `gap: 8px`); er füllt sie
  wie der Speichern-Knopf und bricht nicht.
- **Kein Backend-Eingriff**: die Route `POST /api/gruppen/profil` und ihre Notiz-Regel bleiben
  unverändert — weiterhin genau **eine** Zählregel (`erinnerungen` aus `gruppen_quiz.personen()`).

## Belege (in diesem Lauf ausgeführt)

- **`frontend/tests/test_gruppen_personenliste.js` Exit 0** — eine neue Prüfung mit echten
  Abläufen in der DOM-Attrappe (jetzt neun): Personen „Anna" (2 Erinnerungen), „Bea", „Cem",
  „Dana"; Filter „ohne Erinnerung" → Liste `[Bea, Cem, Dana]`; „Bea" öffnen → Knopf sichtbar,
  Beschriftung „(2)", Ziel im `aria-label`; Klick → **genau** `GET /api/gruppen/person?name=Cem`
  wird geladen (Protokoll der Anfragen), Titel „Cem", Beschriftung „(1)"; weiter → „Dana", Knopf
  **verschwindet** (letzte ohne Erinnerung, kein Ringlauf); bei „Anna" (hat Erinnerung) führt der
  Knopf zur **ersten** ohne („(3)"); mit Suchzeile „d" (nur „Dana" sichtbar) ist der Knopf
  **weg** — der Weg folgt den gesetzten Filtern. Dazu die reine Regel selbst (kein Ringlauf,
  unbekannter Name beginnt vorne, leere Reihe, Beschriftung bei Rest 0).
- **Gegenprobe gegen den alten Stand** (HEAD-Fassungen von `gruppen_quiz.js`, `index.html`,
  `style.css` in einen Ordner **außerhalb des Repos**, dieselbe Prüfdatei): **1 von 9 rot** —
  „der Weiter-Knopf fehlt im HTML (das Durcharbeiten ist nicht erreichbar)". Die Fähigkeit gab es
  vorher nachweislich nicht; die acht bestehenden Prüfungen blieben grün.
- **Alle Frontend-Tests grün**: `python -m pytest tests/test_frontend_node.py -q` →
  **46 passed** (Exit 0), darin alle 45 Prüfdateien.
- **Rendermessung im echten Browser** (Edge headless, **echtes** `index.html` und `style.css`,
  Skript außerhalb des Repos, Personenansicht sichtbar geschaltet, Knopf gefüllt):
  **1400 px** → Knopf links 16 px, rechts 1384 px, Höhe **37 px** (Spalte, volle Breite), **kein**
  überbreites Element, Dokument `scrollWidth 1400 = clientWidth 1400`; **380 px** → links 16,
  rechts 364, Höhe **37 px**, kein überbreites Element, Dokument `380 = 380`.
- **Volles Tor** über den Commit-Haken (Zahl im Journal des Dauerlauf-Plans).

## Ehrliche Grenzen

- **Nicht geprüft:** die Bedienung mit dem Finger am echten Gerät (Knopf drücken, Blättern,
  Aufnahme) — das bleibt Sebastians Abnahme am Handy. Der Browser-Beleg zeigt nur die Geometrie.
- **Offen** bleibt aus Punkt 10 das **Wischen** zur nächsten/vorherigen Person (eigener kleiner
  Schritt; am PC wären Pfeiltasten die Entsprechung).
- Der Knopf bietet **keinen** Ringlauf an; wer die letzte Person erreicht hat, geht über die Liste
  weiter. Der Filter wertet den **Inhalt** der Notiz nicht aus.
- Kein Backend-Eingriff, kein Bild, kein Vision-/pCloud-Aufruf, keine Geräteeingriffe, nichts
  gelöscht, keine echten Personennamen (nur erfundene wie „Anna"). **Kosten 0 USD.**
