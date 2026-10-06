# Änderungsprotokoll 07.10.2026 — Alle Gesichter einer Person in einer Liste, Endlos-Scrollen

Wunsch Sebastian: Bei bekannten Personen mit mehreren Vorschlägen (Gruppen) alle Gesichter
**zusammen** durchscrollen und Falsche aussortieren — gerade nach dem Zusammenlegen/Nachtragen
(Fotobuch-Gesichter docken an erwachsene Mittelpunkte an, Fehltreffer möglich) — und dabei **nie
mehr „Weitere laden" drücken** (Punkt #4 der Liste vom 06.10.).

## Vorher

- „🔍 Alle Gesichter" gab es nur je Vorschlag; eine Person mit drei Vorschlägen hieß drei Listen.
- Seitenweise (48) mit dem Knopf „Weitere laden".

## Änderung

- **Backend** (`gruppen_quiz`): `gesichter_person(name, seite)` — alle nicht ausgeschlossenen
  Gesichter über **alle** Vorschläge der Person (Name Groß/Klein egal), beste zuerst
  (`anteil × score`), seitenweise; jedes Gesicht trägt seine `kennung`. `ausschliessen_person(name,
  [{kennung, gid}])` — prüft, dass jede Kennung zur Person und jedes Gesicht zu seiner Kennung
  gehört, schreibt **einen** Protokolleintrag (mit `je_kennung`, wenn mehrere Vorschläge betroffen
  sind); `rueckgaengig()` nimmt ihn in **einem** Schritt zurück. Die Schreiblogik des Ausschließens
  steckt jetzt in `_ausschluss_schreiben` (gemeinsam für Vorschlag und Person; Format für den
  Gruppierer unverändert).
- **Routen:** `GET /api/gruppen/gesichter?name=…&seite=…` (neben `?kennung=`; ohne beides ehrliche
  Meldung), `POST /api/gruppen/person/ausschliessen` `{name, gesichter: [{kennung, gid}]}`.
- **App** (`gruppen_quiz.js`): in der Personenansicht oben „🔍 Alle N Gesichter von … durchsehen";
  die Gesamtansicht arbeitet für Vorschlag **oder** Person (Info nennt „aus N Vorschlägen").
  **Endlos-Scrollen:** ein Merker hinter der Liste (IntersectionObserver, 400 px Vorlauf) lädt die
  nächste Seite von selbst, mit Sperre gegen Doppel-Laden; nach dem Ausschließen wird sofort
  nachgeladen, falls die Liste kürzer wurde. Ohne IntersectionObserver bleibt „Weitere laden" als
  Rückfall. Reine Funktion `gruppenPersonAlleKnopf`.

## Prüfung

- `backend/tests/test_gruppen_quiz.py`: 6 neue Tests (Person über zwei Vorschläge, beste zuerst,
  Seiten; Ausschließen über zwei Vorschläge im Format des Gruppierers + Rückgängig in einem Schritt;
  fremde Kennung / falscher Vorschlag / kaputte Kennung / leer → nichts geschrieben; Routen) —
  alle 73 Tests der Datei grün, darunter die bisherigen Ausschluss-Tests unverändert.
- `frontend/tests/test_gruppen_quiz.js`: neue Prüfungen (Knopftext, Info, Verdrahtung, Endlos-
  Scrollen, Rückfall); eine alte Prüfung erwartete wörtlich `gesichter?kennung=` und verlangt jetzt
  beide Modi. Alle Prüfungen grün.
- Prüfbefehl und Cache-Bump: siehe Commit.

## Nebenbei

- `frontend/tests/test_foto_galerie.js`: Versionsabgleich auf `style.css?v=20261007A` — der Commit
  `3a3239c` (Notizen, Hermes) hatte die Version erhöht, den Test aber nicht nachgezogen (war rot).
- Cache-Bump: `gruppen_quiz.js?v=20261007A`.
