# 20.10.2026 – Zeitgrenze und „Erneut versuchen“ im Fenster „Personen benennen“

## Anlass

Antwortet der Server nicht, blieb die Gruppenübersicht (und die Liste „Benannt“)
ewig bei „… lädt“ stehen. Ursache: `jsonHolen` in `frontend/gruppen_quiz.js`
rief `fetch` ohne Zeitgrenze auf.

## Änderung

- `jsonHolen(pfad, optionen, zeitgrenzeMs)` gibt **immer ein Objekt zurück und wirft nie**:
  - **Lesende Abrufe (GET)** bekommen eine Zeitgrenze von 20 s
    (`GRUPPEN_ABRUF_ZEITGRENZE_MS`) per `AbortController` plus `Promise.race`
    (das Rennen zählt auch das Lesen des Antwortkörpers). Bei Ablauf:
    `{ ok: false, zeitueberschreitung: true, fehler: 'Server antwortet nicht (nach 20 s) – bitte erneut versuchen.' }`.
  - **Netzfehler** (fetch wirft): `{ ok: false, netzfehler: true, fehler: 'Keine Verbindung zum Agenten.' }`.
  - **Schreibende Abrufe (POST usw.)** haben bewusst **keine** Zeitgrenze: Ein Abbruch
    könnte eine tatsächlich erfolgte Speicherung verdecken – die Anzeige meldete
    „fehlgeschlagen“, der Nutzer tippt erneut, und es wird doppelt gespeichert.
    Netzfehler werden aber auch hier in das Fehlerobjekt übersetzt.
- Alle Aufrufer nutzen weiter `antwort.fehler`; die `.catch(() => null)`-Stellen
  (Quiz-Karte, Suche, Fortschritt, Person, Profil, Gesichterliste) zeigen jetzt die
  Fehlermeldung statt Endlos-„lädt“ (geprüft: `laden()` → `zeigen()` meldet den Fehler).
- **„Erneut versuchen“** bei Zeitüberschreitung/Netzfehler:
  - Gruppenübersicht (`gruppenListeLaden`): Knopf `gruppen-liste-erneut` in `gruppen-liste-meldung`.
  - Liste „Benannt“ (`personenLaden`): Knopf `gruppen-benannt-erneut` in `gruppen-benannt-info`.
  - Der Knopf startet denselben Ladevorgang erneut; die nächste Meldung räumt ihn weg.
  - Server-Fehlerantworten (`ok: false` vom Server) zeigen keinen Knopf.
- Nebenbei behoben: `personenLaden` rief nach dem Setzen der Fehlermeldung
  `personenZeigen()` auf, das die Info sofort überschrieb („Noch niemand benannt“
  statt der Fehlermeldung). Reihenfolge getauscht.
- Vorschaubilder (`vorschauLaden`) unverändert, ohne Zeitgrenze.
- Cache: `gruppen_quiz.js?v=20261020D`; `style.css` unverändert (Knopf nutzt `gruppen-knopf`).
  `test_gruppen_namensfelder.js` prüft den Versionsstand jetzt als „mindestens 20261020C“.

## Grenzen

- Nur die Ansichten Gruppenübersicht und „Benannt“ haben den Knopf; Quiz-Karte,
  Detail, Person usw. zeigen nur die Meldung (Neuladen/erneutes Öffnen wie bisher).
- 20 s sind fest; kein automatischer Wiederholversuch.
- Bricht die Zeitgrenze einen GET ab, kann der Server die Anfrage trotzdem noch
  abarbeiten (lesend, daher ohne Folgen).

## Prüfung

- Neu `frontend/tests/test_gruppen_zeitgrenze.js` (Fake-Timer; Zeitgrenze greift und
  bricht ab, POST ohne Signal/Timer, Fehlerform, Erneut-Knopf ruft das Laden erneut
  auf, keine „lädt“-Anzeige nach Ablauf, Netzfehler, Server-Fehler ohne Knopf);
  in `backend/tests/test_frontend_node.py` zugeordnet.
- Rotprobe: gegen den alten Stand schlägt der Test fehl.
