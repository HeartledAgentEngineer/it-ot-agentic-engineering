# Changelog 2026-09-15 — Gedanken klar erkennbar + Zwischennachricht per Diktat

Anlass (Nutzer-Auftrag, diktiert): Beim Zuschauen während der Hermes-Arbeit war
nicht unterscheidbar, was nur ein **Gedanke** (Zwischenstand) und was eine
echte **Antwort** ist. Außerdem ließ sich während der Arbeit keine
Zwischennachricht per Sprache absenden.

## 1. Gedanken-Blasen sind jetzt klar von Antworten unterscheidbar
`frontend/app.js` (`fuegeGedankeMitAbbruchHinzu`) + `frontend/style.css`:

- Kopfzeile heißt nur noch **„🧠 Gedanke"** statt „🧠 Hermes". Das Wort
  „Hermes" ist dort überflüssig — der Chatpartner *ist* Hermes; es erzeugte
  den Eindruck einer Reihe kleiner Hermes-Symbole.
- Neue CSS-Klassen `.gedanken-strom`, `.gedanken-kopf`, `.gedanken-inhalt`,
  `.gedanken-zeit`: Der Gedanke ist **keine Sprechblase** mehr, sondern ein
  gedämpfter, kursiver Block mit Randlinie links, kleinerer Schrift und
  eigenem Zeitstempel-Stil. Vorher trug der Gedanke dieselbe Optik wie eine
  normale Assistant-Nachricht.
- `.message.gedanken-strom` erzwingt `flex-direction: column`. Da `.message`
  `display:flex` (Zeile) ist, liefen Kopf, Inhalt und Zeitstempel vorher
  nebeneinander — das ergab die „Warteschlange kleiner Hermes-Symbole".
- Die untere Lade-Bubble zeigt statt „🐚 Hermes: …" nur noch „🧠 …"
  (`setzeTutZeile`, `sendMessage`).

## 2. Kein Gedanken-Schwall mehr („alles auf einmal")
`frontend/app.js` (Typewriter in `fuegeGedankeMitAbbruchHinzu`):

- Der frühere Sofort-Sprung bei Rückstand (>2 wartende Blasen: Text ohne
  Tipp-Animation komplett hineinsetzen) ist **entfernt**.
- Stattdessen wird bei Rückstand nur die Tipp-Geschwindigkeit erhöht
  (18 ms/Zeichen normal, 9 ms ab 3 wartenden, 4 ms ab 5 wartenden Blasen).
  Jede Blase bleibt dadurch ein kleiner, lesbarer Abschnitt; es kommt nichts
  mehr schlagartig auf einmal.

## 3. Zwischennachricht während der Arbeit absendbar (Spracheingabe)
`frontend/app.js` (`updateSendButton`):

- Während eine Aufnahme läuft (`state.isRecording`) zeigt der Sende-Knopf jetzt
  **immer** das Senden-Symbol (nie den Stopp-Würfel) mit Titel „Aufnahme
  beenden & senden". Vorher blieb das Stopp-Symbol stehen — nicht erkennbar,
  ob ein Druck die laufende Hermes-Aufgabe abbricht. Tatsächlich beendet
  `handleSubmit` in diesem Zustand nur die Aufnahme und schickt das Diktat
  ab (`stopRecording()` → `/api/transcribe` → `sendMessage`).

## Verifikation
- `node --check frontend/app.js` → Exit 0.
- Cache-Bust erhöht: `app.js?v=20260915cA`, `style.css?v=20260907bE`.
- Frisch vom Server geliefert geprüft (siehe Übergabe/Commit).

## Offen
- Die genaue Ursache von „Mikrofon-Druck bricht irgendwie ab" ist am Code
  allein **nicht belegt**. Rückfrage an Sebastian: Aufnahme sofort beendet /
  gar kein Text / Nachricht verschwunden?