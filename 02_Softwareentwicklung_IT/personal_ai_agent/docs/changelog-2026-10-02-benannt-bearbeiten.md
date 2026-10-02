# Änderungsprotokoll 02.10.2026 — Benannte Personen wieder aufrufen und bearbeiten

Wunsch Sebastian: „Aktuell bin ich immer nur am Sortieren und Gruppieren, aber ich kann die alten
nicht aufrufen und noch mal bearbeiten — wie ein Dokument aufrufen und direkt bearbeiten. Dann
beim nächsten, der noch nicht sortiert ist, fange ich an."

## Was neu ist

- **Reiter im Blatt „👥 Personen benennen“**: „🆕 Offen“ ist der bisherige Ablauf (größter offener
  Vorschlag zuerst), „👤 Benannt“ listet alle benannten Personen. Wechsel jederzeit; eine späte
  Antwort aus „Offen“ überschreibt „Benannt“ nicht.
- **Liste „Benannt“**: eine Person = alle Vorschläge mit demselben Namen (Groß/Klein egal), sortiert
  nach Gesichtern; je Zeile ein Gesicht, Name, Gesichter, Vorschläge, Beziehung, Erinnerungen, 📇.
  Suchfeld filtert am Wortanfang, Umlaute egal (wie die Suche im Backend).
- **Person öffnen**: je Vorschlag Kopf („Vorschlag 1001 · 120 Gesichter · 2015–2025“), bis zu 8
  Gesichter (Antippen = ganzes Foto), „🔍 Alle N Gesichter“ (dieselbe Gesamtansicht zum
  Ausschließen; „Zurück“ führt zur Person), „✂ Gehört nicht zu …“ (zwei Tipps, dann ist der
  Vorschlag wieder unter „Offen“).
- **Bearbeiten**: Name ändern (gibt es den neuen Namen schon, werden beide Personen
  zusammengeführt: Namen, „gleich“-Paar, Profil mit allen Erinnerungen), Beziehung ändern,
  Erinnerung anhängen (🎙 einsprechen wie in der Karte), Telefonbuch-Kontakt suchen und
  verknüpfen. Bisherige Erinnerungen stehen mit Datum darunter.
- **Rückgängig** gilt für alles davon — auch für Profiländerungen, die bisher nicht im Protokoll
  standen. Nach dem Zurücknehmen einer Umbenennung landet die Ansicht beim alten Namen.

## Backend

- `gruppen_quiz.personen()` + `GET /api/gruppen/personen`; `gruppen_quiz.person(name)` +
  `GET /api/gruppen/person?name=` (Vorschläge ohne ausgeschlossene Gesichter, dazu das Profil).
- `gruppen_quiz.umbenennen(alt, neu)` + `POST /api/gruppen/umbenennen {alt, neu}`: Protokoll
  `art: umbenennen` mit `namen_vorher`, `paare_neu` und `profile_vorher` (alte Profile als Kopie).
- `gruppen_quiz.loesen(kennung)` + `POST /api/gruppen/loesen {kennung}`: Name weg, „gleich“-Paare
  dieses Vorschlags weg (sonst käme der Name über die Verbindung zurück); Protokoll `art: loesen`.
- `profil_ergaenzen(..., kontakt_id)` + `POST /api/gruppen/profil` mit `kontakt_id`; schreibt jetzt
  einen Protokolleintrag `art: profil`.
- `rueckgaengig()` nimmt zusätzlich `umbenennen`, `loesen`, `profil` zurück und stellt
  `profile_vorher` wieder her; bei `umbenennen` steht der alte Name in `zurueckgenommen.name`.
- Alles bleibt am Handy (dieselben Dateien unter `~/foto_sortierung`); keine neue Datei, kein Netz.

## Prüfung

- `backend/tests/test_gruppen_quiz.py` +14 (66 gesamt): Liste fasst Vorschläge zusammen, ohne
  Namen/ohne Datei, Person mit Vorschlägen und Profil, ohne ausgeschlossene Beispiele, Umbenennen
  (Namen + Profil), Zusammenführen (gleich-Paar, Erinnerungen beider), Rückgängig stellt Namen,
  Profile und Paare inhaltsgleich wieder her, nur Groß/Klein, ungültige Eingaben schreiben nichts, Lösen +
  Rückgängig, Profil mit Kontakt + zweistufiges Rückgängig, Routen.
- `frontend/tests/test_gruppen_quiz.js` erweitert (Filter, Texte, Verdrahtung aller neuen
  Elemente, Routen, textContent, Zwei-Tipp-Schutz); `test_foto_galerie.js` Versionsabgleich.
  Alle 25 Frontend-Tests Exit 0. `gruppen_quiz.js`/`style.css?v=20261002C`.
- Browser-Prüfstand (erfundene Personen, Backend als Attrappe): Liste mit 2 Personen, Person
  öffnen, Erinnerung speichern, Kontakt suchen und verknüpfen, Umbenennen, Rückgängig zurück zum
  alten Namen, Lösen mit zwei Tipps, Alle Gesichter und zurück zur Person, Wechsel nach „Offen“
  zeigt die Karte; keine Konsolenfehler.
- Prüfbefehl `cd backend && .venv/Scripts/python -m pytest tests/ -q` → **3377 passed, 1 skipped,
  Exit 0** (vorher 3363).

## Offen

- Rückweg Handy → PC: Umbenennungen und gelöste Vorschläge wirken am Handy sofort; der nächste
  Gruppierlauf am PC kennt sie erst, wenn die Antwort-Dateien zurückkommen (wie beim Ausschließen).
