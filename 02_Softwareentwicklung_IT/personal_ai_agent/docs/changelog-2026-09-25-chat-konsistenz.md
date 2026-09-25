# Änderungsprotokoll 2026-09-25 — Chat-Konsistenz (kein fremder Verlauf, keine alten Bilder)

**Projekt:** Personal AI Agent · **Bereich:** Chat-Verlauf + Oberfläche
**Befund (Sebastian, 25.09.2026):** „Ein ganz großes Problem ist auch die
Konsistenz. Ich habe den Chat geschlossen, dann einen alten Chat geöffnet oder
einen neuen Chat geöffnet und dann aktualisiert gedrückt — und dann kam wieder
was ganz anderes. Jetzt kommen auch schon wieder Bilder, die ich irgendwann
schon mal hatte, und da ist gar keine Konsistenz drin, was zuvor war."

Kurzfassung: **Es gab vier Ursachen.** (1) Die Oberfläche fiel bei jedem
Fehlschlag still auf das *jüngste* Gespräch zurück — das war je nach Lage
`conv_code` (Programmier-Chat). (2) Der Server bog eine unbekannte Kennung
still auf `conv_main` um, während die Oberfläche die *angefragte* Kennung
weiter als „offen" führte. (3) Ein Bild aus dem 10-Minuten-RAM-Cache wurde als
Bild einer **neuen** Nachricht gespeichert und erschien nach jedem Reload an
der falschen Stelle. (4) Die Sofort-Sicherung der Frage + der Abschluss konnten
dieselbe Frage **doppelt** in den Verlauf schreiben.

---

## 1. Ursachen (belegt)

| # | Ursache | Belegstelle (Stand vor dem Fix) |
|---|---|---|
| 1 | **Stiller Rückfall auf einen fremden Chat:** Schlug das Laden der gemerkten Kennung fehl, lud der Start das *jüngste* Gespräch (`/api/conversations` → letzter Eintrag). Da `conv_code` später als `conv_main` angelegt wird, konnte so der Programmier-Chat erscheinen. | `frontend/app.js` (alt) Z. 7636–7637: `const juengste = await letzteGespraechsId(); if (juengste) await zeigeGespraech(juengste);` |
| 2 | **Server bog unbekannte Kennungen still um:** Eine alte `conv_8` im localStorage lieferte den Inhalt von `conv_main` — die Antwort trug `"id": "conv_main"`. Die Oberfläche setzte aber die **angefragte** Kennung in Zustand + Speicher. Angezeigter Inhalt, gemerkte Kennung und die nächste Nachricht konnten auseinanderlaufen. | `backend/app/router/chat.py` (alt) Z. 1946–1948 (`conversation_id = chat_verlauf._AKTIVE_CONVERSATION_ID`) · `frontend/app.js` (alt) Z. 7442/7444 (`state.conversationId = id; localStorage.setItem('conversation_id', id)`) trotz `"id"` in der Antwort |
| 3 | **Altes Bild an neuer Nachricht:** Der gespeicherte Bildpfad kam aus `datei_bilder` — das enthielt auch das Bild aus dem 10-Minuten-RAM-Cache (Fortsetzungsfragen wie „was war noch drauf?"). Damit wurde ein **altes** Bild an eine **neue** Assistant-Nachricht geschrieben (inkl. `bild_vorschau` an den Client) und erschien nach jedem Reload wieder. | `backend/app/router/chat.py` (alt) Z. 506–508: `bild_pfad=(datei_bilder[0].get("pfad") if datei_bilder else None) …` (Cache-Befüllung: Z. 372–384) |
| 4 | **Doppelte Frage nach Reload:** Die Frage wird beim Stream-Start sofort gesichert; der Abschluss verglich nur mit der **allerletzten** Zeile. Kam dazwischen eine Hermes-Zwischenmeldung, wurde die Frage ein zweites Mal angehängt. | `backend/app/services/chat_verlauf.py` (alt) Z. 382–388: `_letzter = history[-1] … if _letzter.role == "user" and …` |
| 5 | **Später Stream schaltete den offenen Chat um:** Der Abschluss übernahm seine `conversation_id` blind — auch wenn man inzwischen in einen anderen Chat gewechselt hatte. | `frontend/app.js` (alt) Z. 2394–2397: `if (abschluss.conversation_id) { state.conversationId = …; localStorage.setItem(…) }` |

Zusätzlich geprüft (kein Fehler gefunden): Der Verlauf wurde **nicht** doppelt
gerendert (`zeigeGespraech` leert `#messages` vor dem Aufbau), die Reihenfolge
kommt aus der append-only-Liste (keine Sortierung nach Zeit), und `conv_code`
schreibt nicht in `conv_main` (jede Nachricht wird über ihre
`conversation_id` zugeordnet). Neu abgesichert ist lediglich der Fall, dass
sich zwei Ladevorgänge überholen (Schnellwechsel + Reload) — dafür gibt es
jetzt einen Reentranz-Schutz.

---

## 2. Fix

### Backend
* `GET /api/conversations/{id}` liefert für eine **unbekannte** Kennung jetzt
  `404` mit klarer Meldung (`"Chat 'conv_8' existiert nicht (leer oder nicht
  gefunden)."`) plus Liste der vorhandenen Chats (`id`, `message_count`) —
  **ohne** fremden Nachrichteninhalt. Die Whitelist-Chats `conv_main` /
  `conv_code` werden weiterhin angelegt und leer ausgeliefert. Der
  **Schreibweg** bleibt unverändert (unbekannte Kennungen landen weiterhin in
  `conv_main`) — es geht nur um die Anzeige. → `chat.py` Z. 1983–2030
* `finish_exchange` findet die beim Stream-Start gesicherte Frage über die neue
  Markierung `offen` wieder (statt nur die letzte Zeile zu prüfen) und räumt
  sie beim Abschluss ab; der Zitat-Anhang („↩ Antworten") wird dabei
  berücksichtigt. → `chat_verlauf.py` Z. 240–272, 349–423 · `chat.py` Z. 1546–1554
* Angezeigt/gespeichert wird nur noch ein Bild, das **in dieser Runde** gefunden
  wurde (`datei_tool_bilder`), nicht mehr eines aus dem RAM-Cache.
  → `chat.py` Z. 530–545 (und Z. 549–560 für `bild_vorschau`/`bild_pfad`)
* Der RAM-Bild-Cache trägt jetzt den Index der Nachricht, zu der er gehört
  (`nachricht_index`, `chat.py` Z. 390–399) und lässt sich verwerfen:
  `POST /api/chat/bild-cache/verwerfen` (`chat.py` Z. 50–66, 1953–1963).

### Frontend (`frontend/app.js`)
* **Stabile Kennung:** `state.conversationId` kommt weiterhin aus
  `localStorage` (Z. 96) und wird **erst** zum Server-Stand, wenn der Server
  geantwortet hat — übernommen wird die *aufgelöste* Kennung `daten.id`
  (Z. 7478 ff.). Es werden keine Chat-Nummern erzeugt.
* **Kein stiller Fallback:** `stelleVerlaufWiederHer` (Z. 7859–7884) lädt nur
  die gemerkte Kennung. Bei `404` erscheint eine klare Meldung
  („Dieser Chat ist leer bzw. nicht gefunden … es wird bewusst *kein anderer*
  Verlauf angezeigt") mit Knöpfen zum Öffnen der vorhandenen Chats
  (`zeigeChatNichtGefunden`, Z. 7376–7428); die tote Kennung wird aus
  `localStorage` entfernt. Bei Netzwerkfehler bleibt die Kennung gemerkt und es
  gibt „🔄 Erneut versuchen" (`zeigeVerlaufLadefehler`, Z. 7430–7456).
  Autofall nur noch, wenn **gar keine** Kennung gemerkt ist — und dann sichtbar
  als „automatisch geöffnet (kein Chat gemerkt)" (Bevorzugung `conv_main`).
* **Sichtbare Chat-Kennzeichnung:** neues Feld `#chat-aktuell`
  (`index.html` Z. 51–55) zeigt „💬 Haupt-Chat (conv_main) · 128 Nachrichten ·
  zuletzt 10:05" (`setzeChatAnzeige`, Z. 7319–7337); gesetzt beim Öffnen, beim
  Wechsel und nach jeder Antwort (`aktualisiereChatAnzeigeVomServer`).
* **Bild gehört zur Nachricht:** `zeigeBildVorschau` bindet die Vorschau an die
  Nachricht (`container.dataset.bildPfad`, Z. 2291); die Vorschau wird nur noch
  in die Blase des Chats geheftet, aus dem die Antwort kam (Z. 2409–2423). Es
  gibt keinen globalen „letztes Bild"-Zustand. Der RAM-Cache wird beim
  Chat-Wechsel (`chatWechseln`, Z. 7212 ff.) und beim Start verworfen
  (`verwerfeBildCache`, Z. 7363–7374; Aufruf in `DOMContentLoaded` Z. 7898).
* **Kein stilles Umschalten:** Ein Abschluss übernimmt seine Kennung nur, wenn
  er zum offenen Chat (bzw. zu der Anfrage, `_sendChatId`, Z. 5394) gehört.
* **Kein Doppel-Rendern:** Reentranz-Marke `_gespraechToken` (Z. 7283) — nur
  der jüngste Ladevorgang baut die Anzeige.
* **Cache-Bump:** `index.html` Z. 10 und Z. 234 auf `?v=20260925B`
  (die Datei trug bereits `20260925A` aus einer parallelen Änderung; ein
  Rücksetzen auf das im Auftrag genannte `20260920C` wäre ein *älterer* Stand).

---

## 3. Tests

**Neu (Backend):** `backend/tests/test_verlauf_konsistenz.py` — 9 Tests:
(i) gleiche Kennung → gleicher Verlauf über zwei Abrufe, (ii) unbekannte
Kennung → 404 ohne fremden Inhalt (Service-Ebene *und* echter HTTP-Aufruf über
den Router), (iii) `conv_main`/`conv_code` bleiben getrennt, (iv) Reihenfolge
stabil + keine Dublette trotz Zwischenmeldung (+ Zitat-Anhang), (v) Bildpfad
bleibt an seiner Nachricht, kein Cache-Bild an einer neuen Antwort, Cache
verwerfbar. Die Verlaufsdatei wird in einen Temp-Ordner umgebogen — die echten
Daten (`chroma_data/conversations.json`) werden nicht angefasst.

**Neu (Frontend):** `frontend/tests/test_chat_konsistenz.js` — Quelltext-Nachweise
für: Wiederherstellung der gemerkten Kennung, kein Rückfall auf das jüngste
Gespräch, klare Meldung bei 404 (inkl. Räumen der toten Kennung), Übernahme der
Server-Kennung, sichtbare Chat-Anzeige (+ `#chat-aktuell` in `index.html`),
Bindung Vorschau↔Nachricht (`dataset.bildPfad`), Verwerfen des Caches bei
Wechsel/Start, `_sendChatId`-Guard, Reentranz-Schutz.

Nebenbei angepasst: `frontend/tests/test_gedaechtnis_ui.js` prüfte den
Cache-Parameter fest auf `20260925A` und wurde dadurch beim nächsten Bump rot.
Der Test prüft jetzt versionsunabhängig („nicht mehr der alte Parameter, aber
überhaupt einer").

---

## 4. Verifikation (echte Ausgaben)

```
$ cd backend && .venv/Scripts/python -m pytest tests/ -q
271 passed, 3 warnings in 28.53s          [Exit 0]   (Baseline vorher: 263)

$ cd backend && .venv/Scripts/python -m pytest tests/test_verlauf_konsistenz.py -q
9 passed, 3 warnings in 3.30s             [Exit 0]

$ cd frontend && node --check app.js
(keine Ausgabe)                           [Exit 0]

$ cd frontend && node tests/test_chat_konsistenz.js app.js
ERGEBNIS: alle Prüfungen grün             [Exit 0]

$ cd frontend && for t in tests/*.js; do node "$t" app.js; done
test_chat_konsistenz.js    exit=0  alle Prüfungen grün
test_conv_code_live_stream.js exit=0  alle Prüfungen grün
test_diff_darstellung.js   exit=0  alle Prüfungen grün
test_gedaechtnis_ui.js     exit=0  Fehler: 0
test_options_assistent.js  exit=0  alle Prüfungen grün
test_quiz_ende.js          exit=0  Fehler: 0
test_quiz_geo.js           exit=0  Fehler: 0
test_quiz_rahmen_quelle.js exit=0  Fehler: 0
test_ref_loeschen_ui.js    exit=0  Fehler: 0
test_serielles_tippen.js   exit=0

Gegenprobe (neuer Frontend-Test gegen den Stand VOR dem Fix):
ERGEBNIS: 20 Prüfungen rot                [Exit 1]
```

---

## 5. Offene Punkte (ehrlich)

1. **Option B im Nicht-Streaming-Weg ist nur halb wirksam:** Im Weg
   `POST /api/chat` wird der RAM-Cache zwar gepflegt, aber die Bildliste an den
   LLM kommt aus `datei_tool_bilder` — das gemerkte Bild wird dort also *nicht*
   mitgeschickt (`chat.py` Z. 519–522). Die Oberfläche nutzt normalerweise den
   Stream-Weg (`/api/chat/stream`), deshalb ist das kein akuter Fehler; wer
   „was war noch drauf?" ohne erneutes Suchen beantworten will, muss hier
   nachziehen. Bewusst **nicht** mitgeändert (minimal-invasiv).
2. **Ein „neuer Chat" im Sinne eines eigenen Verlaufs existiert nicht:** Es gibt
   genau zwei dauerhafte Chats (`conv_main`, `conv_code`). Der Wunsch „neuer
   Chat" müsste als eigenes Feature entschieden werden (append-only-Regel!).
3. **Beobachtung nebenbei:** In `frontend/app.js` steht ein zweiter,
   unerreichbarer `else if (daten.done)`-Zweig (toter Code im Stream-Handler).
   Nicht angefasst, um den Fix klein zu halten.
4. **Parallele Änderung im selben Arbeitsstand:** `app.js`/`index.html` wurden
   während dieser Arbeit von einer zweiten Änderung (Erinnerungs-Anzeige)
   mitgeschrieben; der Cache-Parameter steht deshalb auf `20260925B`. Beim
   Zusammenführen darauf achten, dass beide Änderungen erhalten bleiben.

_Kein Git-Commit in diesem Schritt — der Hauptagent committet zentral._
