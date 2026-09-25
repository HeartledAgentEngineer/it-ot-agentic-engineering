# Änderungsprotokoll 2026-09-25 — Quiz-Suche vollständig (alle Katalog-Personen, Kennzeichnen statt Ausblenden)

**Projekt:** Personal AI Agent · **Bereich:** Quiz „Wer ist auf dem Bild?" / Oberfläche
**Umfang:** nur Frontend (`frontend/app.js`, `frontend/index.html`, `frontend/tests/`) — Backend unberührt.
**Befund (Sebastian, 25.09.2026):** „Wenn ich eine Person suche, soll er ja
durch so eine Antwortauswahl kommen mit den Accounts. **Den finde ich nicht. Das
passiert nicht. Nur bei einigen Personen. Personen sollen auftauchen — nicht
David ausblenden.**" Dazu früher: „Ich sage, dass es David auf dem Bild ist. Und
ich will eine andere Person suchen, und dann wird David aufgelistet."

Kurzfassung: Die Namenssuche im Quiz kannte **nur die Kandidaten der laufenden
Runde**, nie den Personen-Katalog. Deshalb fehlten alle Personen, die das Modell
für dieses Bild nicht vorgeschlagen hat. Jetzt filtert die Suche über **alle**
`GET /api/gesichter`-Personen, die Kandidaten bleiben nur noch die *Sortierung*
(oben, in Backend-Wahrscheinlichkeit), bereits zugeordnete/bestätigte Personen
werden **markiert statt ausgeblendet**, eine unbekannte Eingabe bietet
„➕ … als neue Person anlegen" (bestehender Weg, kein neues Formular) und die
Liste wird bei jedem Öffnen/Tippen frisch gebaut.

---

## 1. Ursache (belegt)

`baueSuchMitVorschlaegen(alleNamen, onwaehl)` filterte ausschließlich über die
übergebene Liste (`frontend/app.js`, vor dem Fix Z. 3691/3710–3713). An allen
drei Aufrufstellen wurde **nur `optionen`** übergeben — das sind die Kandidaten
der laufenden Quiz-Runde aus `quiz/start` bzw. `quiz/analysiere`. Der
Personen-Katalog (`GET /api/gesichter`, `personen[].name`) kam dort **nie** an.

| # | Stelle | Beleg (Stand beim Bearbeiten; die Datei hatte sich gegenüber der Auftragsnotiz um ~30 Zeilen verschoben — dort genannt: Z. 3862 / 4138 / 4311) |
|---|---|---|
| 1 | **Gruppenbild** (`starteGruppenQuiz` → `zeigeAntwortZeile`) | `frontend/app.js` (alt) Z. 3891: `zeile.appendChild(baueSuchMitVorschlaegen(optionen, (n) => antworten(n, false, false)));` |
| 2 | **Rahmen selbst gezogen** (`zeigeEinzeichnen`) | `frontend/app.js` (alt) Z. 4167: `auswahl.appendChild(baueSuchMitVorschlaegen(optionen \|\| [], (n) => { … }));` |
| 3 | **Einzelbild** (`zeigeQuizKarte`) | `frontend/app.js` (alt) Z. 4340: `auswahlBox.appendChild(baueSuchMitVorschlaegen(optionen, (n) => quizBeantworten(pfad, n, false, '')));` |

Zwei Folgeprobleme:

* **Kein Ausblenden, aber auch kein Auftauchen:** Es gab keinerlei Kennzeichnung
  und keine Möglichkeit, eine *andere* Person zu wählen, wenn sie nicht in den
  Kandidaten stand — genau Sebastians Fall „Ich will eine andere Person suchen".
* **Eingefrorener Stand:** Die Liste wurde bei Tippen/Öffnen zwar neu
  gefiltert, aber über dieselbe, **nie nachgeladene** Namensliste — nach einer
  Zuordnung (Person gewählt / neue Person angelegt / übersprungen) konnte sich
  die Auswahl nicht ändern; es gab keinen Katalog-Cache, der verworfen wurde,
  und kein Nachladen beim Öffnen des Felds.

---

## 2. Fix (`frontend/app.js`)

### Neue Bausteine (Zeilennummern nach dem Fix)

| Funktion | Zeile | Zweck |
|---|---|---|
| `quizKatalogVerwerfen()` | 3705 | wirft den Katalog-Cache weg (nach jeder Zuordnung) |
| `quizKatalogNamen()` | 3712 | aktueller Katalog-Stand (alle Namen) als Start-Liste des Suchfelds |
| `quizKatalogFehlerText()` | 3716 | letzte Fehlermeldung (ehrlicher Zustand) |
| `ladeQuizKatalogNamen(erzwingen)` | 3720 | holt **alle** Namen aus `GET /api/gesichter` (`personen[].name`), kurzer Cache (60 s), Fehler werden gemerkt statt still leer |
| `quizNamenAufBild(gesichter)` | 3748 | Namen, die auf diesem Bild schon zugeordnet sind (Backend-`bestaetigt` + lokal Zu-geordnetes) |
| `quizNamenFuerRegion(gesichter, idx, pfad)` | 3758 | Namen, die für diese Gesichts-Region schon bestätigt sind |
| `quizSuchVorschlaege(kandidaten, katalogNamen, eingabe, kontext)` | 3778 | **reine Listen-Logik** (ohne DOM, testbar): Reihenfolge, Kennzeichnung, neue-Person-Option |
| `baueSuchMitVorschlaegen(kandidaten, katalogNamen, onwaehl, kontext)` | 3845 | Suchfeld + Dropdown, baut die Liste bei jedem Öffnen/Tippen neu |

### Die drei Aufrufstellen (jetzt)

* Gruppenbild: `app.js` Z. 4140 — `quizKatalogNamen()` als zweite Liste,
  Kontext `{ aufBild: namenAufDiesemBild(), bestaetigt: namenFuerRegion(idx), onNeu: … }`
  (Helfer Z. 4101/4109).
* Rahmen selbst gezogen: `app.js` Z. 4434 — `quizKatalogNamen()`, Kennzeichnung
  aus dieser Sitzung; die gerade gezeichnete Region ist neu, deshalb kein
  „schon bestätigt"-Marker.
* Einzelbild: `app.js` Z. 4618 — `quizKatalogNamen()`, Kontext aus
  `gesichter` (bestaetigt je Gesicht + lokal).

### Regeln (so verhält sich die Suche jetzt)

1. **Sortierung:** Treffer, die auch Kandidat sind, stehen oben in
   Backend-Reihenfolge (Wahrscheinlichkeit), danach die übrigen Katalog-Namen
   **alphabetisch** (deutsche Sortierung). Kandidaten tragen den Marker
   `★ Vorschlag`.
2. **Kennzeichnen statt Ausblenden:** „schon auf diesem Bild zugeordnet" →
   `✓ schon auf diesem Bild`; „für diese Region bestätigt" →
   `✓ schon bestätigt`. Beide Marker können zusammen erscheinen; die Person
   bleibt **immer wählbar** (Sebastians Wunsch: „Personen sollen auftauchen").
3. **Neue Person direkt im Dropdown:** Kennt Katalog (und Kandidatenliste) die
   Eingabe nicht, steht als **erste** Option `➕ <Eingabe> als neue Person
   anlegen`. Der Klick öffnet den **bestehenden** Weg: im Gruppen- und im
   Einzelbild-Formular wird die vorhandene „Neue Person"-Box aufgeklappt und der
   Name vorbelegt (`inp.value`/`neuName.value`), im Weg „Rahmen selbst gezogen"
   ist der bestehende Weg die Namenswahl selbst (dort existiert kein Formular;
   das Backend legt die unbekannte Person dabei an). **Kein neues Formular**
   erfunden — die Zahl der „➕ Neue Person"-Knöpfe bleibt 2.
4. **Liste wird neu berechnet:** Aufbau bei jedem `input`-Ereignis und bei
   `focus`; beim Öffnen wird der Katalog nachgeladen. Nach einer Zuordnung
   (`d.ok`) ruft der Client `quizKatalogVerwerfen()` (Z. 4328 Gruppenbild,
   Z. 5118 Einzelbild/Rahmen) — beim nächsten Öffnen/Tippen steht der neue
   Stand. Kein eingefrorenes Array (der frische Stand ersetzt `katalog`).
   Obergrenze 8 Einträge wie bisher — **markierte Personen und die
   neue-Person-Option werden nie abgeschnitten**.
5. **Ehrliche Zustände:** Beim Laden steht sichtbar `⏳ Personenkatalog lädt …`
   unter dem Feld; schlägt das Laden fehl, steht dort
   `⚠️ Personenkatalog nicht ladbar — nur Vorschläge` (die Kandidaten bleiben
   wählbar). Nie still leer.
6. **Cache-Bump:** `frontend/index.html` Z. 234 auf `?v=20260925C`.

---

## 3. Tests

**Neu:** `frontend/tests/test_quiz_suche_vollstaendig.js` (Aufruf
`node tests/test_quiz_suche_vollstaendig.js app.js`), sechs Abschnitte:

* **A)** Quelltext-Nachweis: genau **drei** Aufrufstellen, jede übergibt
  `quizKatalogNamen()` und **nicht mehr nur `optionen`** — mit Begründung im
  Testausdruck (`Grund: …`); Katalogquelle ist `GET /api/gesichter`,
  `personen[].name`; das Suchfeld lädt selbst nach.
* **B)** Kennzeichnungs-Texte vorhanden (`✓ schon auf diesem Bild`,
  `✓ schon bestätigt`), Marker hängen am Eintrag, **kein** `return`/`filter`
  entfernt markierte Personen, der Builder zeichnet alle Vorschläge.
* **C)** `➕ … als neue Person anlegen` vorhanden, Klick läuft über
  `neuePersonWaehlen` → vorhandenes `onNeu` (Gruppen- und Einzelbild-Formular
  werden vorbelegt); ohne `onNeu` bleibt der bestehende Weg; weiterhin genau
  **2** „➕ Neue Person"-Knöpfe (kein neues Formular); das Suchfeld baut keinen
  eigenen Button.
* **D)** Neuberechnung: `aktualisieren()` rechnet bei jedem Aufbau,
  `focus` → `katalogFrisch()`, frischer Katalog ersetzt den alten Stand,
  `quizKatalogVerwerfen()` in beiden Zuordnungswegen, TTL 60 s, Lade- und
  Fehlerhinweis vorhanden.
* **E)** **Reine Logik-Tests** der echten Funktion `quizSuchVorschlaege`
  (per `eval(extractFn(...))`, ohne DOM): Kandidat vor Alphabet (E1/E2),
  markierte Person bleibt (E3/E3b), neue-Person-Option zuerst + getrimmt
  (E4/E4b/E4c), leere Eingabe → leere Liste (E5), keine Dubletten (E6),
  8er-Grenze (E7) und markierte Person über der Grenze bleibt sichtbar (E8).
* **F)** **Verhaltens-Tests im Stub-DOM** mit dem echten Suchfeld: Ladehinweis →
  geladen; Tippen `da` → `➕ da als neue Person anlegen` + `David`
  (Katalog-Treffer, obwohl kein Kandidat!); Tippen `an` → zugeordnete Person
  bleibt mit beiden Markern wählbar; Klick auf die neue-Person-Option ruft den
  bestehenden Weg mit vorbelegtem Namen; Klick auf einen Katalog-Namen geht in
  den Antwortweg; Enter mit vorhandenem Namen wählt die Person, mit unbekanntem
  öffnet den neue-Person-Weg; Ladefehler wird sichtbar gemeldet, Kandidaten
  bleiben nutzbar.

Bestehende Tests unverändert grün (keiner prüfte die alte Suchsignatur).

---

## 4. Verifikation (echte Ausgaben, 25.09.2026)

```
$ cd frontend && node --check app.js
(keine Ausgabe)                                            [Exit 0]

$ cd frontend && node tests/test_quiz_suche_vollstaendig.js app.js
A) Alle drei Aufrufstellen übergeben die KATALOG-Liste (nicht nur optionen)
  OK   genau drei Aufrufstellen (Gruppenbild, Rahmen, Einzelbild)
  ...
F) Verhalten des Suchfelds (echter Code, Stub-DOM)
  OK   F7 Kandidaten bleiben trotzdem waehlbar

  --> Fehler: 0                                            [Exit 0]
  (80 OK-Prüfungen, 0 Fehler)

$ cd frontend && for t in tests/*.js; do node "$t" app.js; done
test_chat_konsistenz.js        exit=0  ERGEBNIS: alle Prüfungen grün
test_conv_code_live_stream.js  exit=0  ERGEBNIS: alle Prüfungen grün
test_diff_darstellung.js       exit=0  ERGEBNIS: alle Prüfungen grün
test_gedaechtnis_ui.js         exit=0    --> Fehler: 0
test_options_assistent.js      exit=0  ERGEBNIS: alle Prüfungen grün
test_quiz_ende.js              exit=0    --> Fehler: 0
test_quiz_geo.js               exit=0    --> Fehler: 0
test_quiz_rahmen_quelle.js     exit=0    --> Fehler: 0
test_quiz_suche_vollstaendig.js exit=0   --> Fehler: 0     (neu)
test_ref_loeschen_ui.js        exit=0    --> Fehler: 0
test_serielles_tippen.js       exit=0  Alle Prüfungen grün

Gegenprobe (Kopie von app.js in einen Scratch-Ordner, in der die drei
Aufrufstellen wieder wie VOR dem Fix nur die Kandidaten übergeben):
  FAIL Aufruf 1/2/3: übergibt quizKatalogNamen() als Katalog-Liste
  --> Fehler: 3                                            [Exit 1]
```

Damit ist belegt: der neue Test wird **rot**, sobald die drei Stellen wieder
nur die Kandidaten bekommen — er prüft also den Befund und nicht nur sich selbst.

---

## 5. Offene Punkte (ehrlich)

1. **Kein End-to-End-Test am Gerät:** Verhalten ist über Quelltext-Nachweise,
   reine Logik-Tests und Stub-DOM-Tests belegt — **nicht** in einem echten
   Browser/am Handy geklickt. Sebastian sollte einmal am Handy „dav" tippen und
   prüfen, dass David erscheint (Backend/Server in diesem Schritt nicht gestartet).
2. **Liste erscheint weiterhin erst beim Tippen** (leere Eingabe = keine Liste,
   so im Auftrag/Test E5 festgehalten). Der Platzhalter sagt jetzt
   „(alle Personen im Katalog)"; will Sebastian beim Antippen sofort alle
   Personen sehen, ist das eine kleine Folgeänderung (eine Bedingung in
   `quizSuchVorschlaege`/`aktualisieren`).
3. **Weg „Rahmen selbst gezogen"** hat kein eigenes „Neue Person"-Formular; dort
   nutzt die Option den bestehenden Weg der Namenswahl (Backend legt die Person
   an). Ein Formular an dieser Stelle wäre ein eigenes Vorhaben.
4. **Katalog-Cache 60 s:** Legt ein *anderer* Weg eine Person an (z. B. Chat-
   Befehl „neue person X"), sieht das Suchfeld sie spätestens nach 60 s bzw.
   nach der nächsten eigenen Zuordnung. Eigene Zuordnungen verwerfen den Cache
   sofort.
5. **Marker `★ Vorschlag`** ist neu und nur erklärend (Reihenfolge) — falls er
   stört, ist er eine Zeile im Dropdown-Aufbau von `baueSuchMitVorschlaegen`
   (`app.js` Z. 3906).
6. **Paralleler Strang:** Backend wurde in diesem Schritt nicht angefasst.

_Kein Git-Commit in diesem Schritt — der Hauptagent committet zentral._
