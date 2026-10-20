# Namensfelder: Vorname / Nachname / Spitznamen in der Oberfläche (Schritt 3 von 3)

20.10.2026, Hermes-Cron. Fortsetzung von
`docs/changelog-2026-10-20-namensfelder-schreibweg.md` (Schritt 2: Schreibweg).
Grundlage: `.hermes/plans/2026-10-20_personen-namensfelder.md`, Entscheidungen
Sebastian vom 20.10.2026 („Personenbuch mit Vorname / Nachname / Spitzname").

## Was dieser Schritt baut

**Personenansicht** (`frontend/index.html`, `frontend/style.css`): im Profil
stehen jetzt über der Beziehung drei Felder — **Vorname**, **Nachname** und
**Spitznamen** (mit Komma getrennt). Vorname und Nachname stehen nebeneinander,
die Spitznamen-Zeile läuft über die volle Breite; unter 480 px Breite stehen
alle drei untereinander (wie am Handy üblich). Darunter eine Hinweiszeile, die
ehrlich sagt, woher die Werte kommen: „Von Hand gesetzt – leeren heißt: wieder
aus dem Namen ableiten." bzw. „Aus dem Namen abgeleitet – tippen überschreibt."

**Oberflächenlogik** (`frontend/gruppen_quiz.js`):

- `gruppenSpitznamenListe(text)` — Komma-getrennt, getrimmt, doppelte weg
  (Groß/Klein gilt als derselbe); ohne Komma bleibt der ganze Text ein Spitzname.
- `gruppenSpitznamenZuviele(liste)` — mehr als 10 Spitznamen lehnt die
  Oberfläche selbst ab, mit derselben Grenze wie das Backend
  (`SPITZNAMEN_MAX`); es wird dann **nichts** geschickt.
- `gruppenNamensfelderKoerper(profil, vorname, nachname, spitznamen)` — schickt
  **nur wirklich Geändertes**. Verglichen wird mit dem, was das Profil gerade
  zeigt (auch abgeleitet): ein unverändertes Feld bleibt draußen, ein geleertes
  Feld geht **leer** mit (das Backend entfernt dann das Handfeld und die
  Ableitung greift wieder).
- `gruppenNamensfelderHinweis(profil)` — Text der Hinweiszeile.
- `gruppenPersonPasstNamensfelder(p, frage)` — die **Personensuche der Liste**
  prüft jetzt Name, Vorname, Nachname und Spitznamen (`gruppenPersonenGefiltert`
  nutzt es). Wer „Mausi" tippt, findet die Person auch ohne ihren vollen Namen.
- Beim Öffnen eines Profils (`personZeigen`) füllt `namensfelderZeigen` die drei
  Felder und die Hinweiszeile; „Profil speichern" (`profilSpeichern`) schickt die
  Felder gemeinsam mit Beziehung/Erinnerung an `POST /api/gruppen/profil`.
- Fehlt ein Feld im HTML (ältere Seite), passiert nichts — die Ansicht bleibt
  dann wie vorher.

**Cache:** `gruppen_quiz.js?v=20261020C`, `style.css?v=20261020B` — sonst holt
der Browser am Handy die alte Datei aus dem Zwischenspeicher.

## Belege (in diesem Lauf selbst gefahren)

- Neu `frontend/tests/test_gruppen_namensfelder.js` (reine Funktionen +
  Verdrahtung): **30 Prüfungen**, alle grün (`node tests/test_gruppen_namensfelder.js gruppen_quiz.js`).
- Neu `frontend/tests/test_gruppen_namensfelder_ui.js` (**Runtime-Vertrag**, die
  echten Handler in der DOM-Attrappe, nur HTTP-Antworten sind Attrappen):
  **8 Prüfungen**, alle grün — Felder stehen beim Öffnen im Profil, Herkunft
  steht dran, Speichern schickt nur das Geänderte (im abgeschickten Rumpf
  geprüft), Leeren schickt den leeren Wert und der abgeleitete Vorname kommt
  zurück, Spitznamen komma-getrennt inklusive Dubletten-Regel, 11 Spitznamen
  werden ohne Serveranfrage abgelehnt, ohne Änderung passiert nichts, die
  Suchzeile findet über Spitzname **und** Nachname.
- `backend/tests/test_frontend_node.py` (alle Frontend-Tests laufen im
  Prüfbefehl): **52 passed** — die zwei neuen Tests sind dort fest zugeordnet.
- Zwei **eigene** Fehler dabei gefunden und behoben (nicht umgangen):
  `test_gruppen_quiz.js` schneidet Funktionen wörtlich aus und kannte
  `gruppenPersonPasstNamensfelder` nicht (ReferenceError → in die Liste
  aufgenommen), und `test_server_zustand.js` hatte den Stil-Schlüssel
  `style.css?v=20261020A` fest verdrahtet (jetzt wie die anderen Tests
  „mindestens 20261020A", damit der nächste berechtigte Bump nicht wieder rot
  wird).
- Voller Prüfbefehl im Hauptbaum: siehe Journal des Laufs.

## Was dieser Schritt bewusst NICHT macht (ehrlich)

- **Keine Chat-Werkzeuge** über die neuen Felder (`person_auskunft` & Co. bleiben
  unverändert) — die stehen als eigener Punkt im Plan.
- **Der Name bleibt die Kennung.** Die Felder sind Zusatz; ein Umbenennen gibt es
  nicht, und abgeleitete Felder werden unverändert **nicht** gespeichert.
- **Keine Migration** alter Profile; fehlende Felder werden abgeleitet (Schritt 1).
- Geprüft wurde mit **erfundenen** Namen und Attrappen — kein echter Name, kein
  Bild, kein Gesicht, kein Modellaufruf (Kosten 0 USD). Ein Blick auf die echte
  Oberfläche am Handy bleibt Sebastian (der Prüfbefehl belegt Code und
  Verdrahtung, nicht den Geschmack).
