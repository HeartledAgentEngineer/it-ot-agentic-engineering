# Änderungsprotokoll 10.10.2026 — Personen im Chat: die Quiz-Quelle anbinden

Befund Sebastian (10.10.2026): Der Chat findet eine gepflegte Person nicht, obwohl ihr Profil im
Personen-Quiz steht — die App selbst meldete „Im Gesichtskatalog stehen 10 Personen".

## Ursache (belegt im Code)

Es gab **zwei getrennte Welten**:

- `backend/app/services/werkzeuge.py` baute `personen_liste` auf
  `gesichter_service.liste_personen()` → `gesichter_katalog.json` (der **alte** Katalog, 10 Personen).
- Das Quiz führt dagegen über 100 benannte Personen in `personen_bestaetigt.json`,
  `personen_vorgaben.json`, `personen_profile.json` (`backend/app/services/gruppen_quiz.py`).

Der Chat sah also nur den alten Katalog — deshalb „nicht verknüpft".

## Was neu ist

- **`personen_liste` liest jetzt die Quiz-Quelle** (`gruppen_quiz.personen()`): Name, Beziehung und
  Zahl der Gesichter. Fehlen die Quiz-Dateien, greift der alte Katalog als **Notnagel** (Verhalten
  unverändert, wenn kein Quiz-Bestand vorhanden ist).
- **Neu `person_auskunft(person)`** — dieselbe Quiz-Quelle (`gruppen_quiz.person`): Beziehung,
  eigene Notizen (zurückgenommene zählen nicht), Geburtstag (aus dem Telefonbuch-Auszug) und die
  Zahl der Fotos (Summe der Vorschlagsgrößen). Nur Klartext — **keine Vektoren, keine Bilddaten,
  keine Pfade**.
- `docs/spec-tool-use-v1.md`: Werkzeug-Tabelle nachgezogen (10 Werkzeuge).

## Prüfung (echte Ausgabe)

- Neu `backend/tests/test_personen_werkzeuge_quiz.py` (6 Tests, erfundene Daten in `tmp_path`,
  `GRUPPEN_QUIZ_BASIS`): die Liste kommt aus der Quiz-Datei (Namen + Gesichterzahlen), ohne
  Quiz-Bestand werden **keine** Personen erfunden, `person_auskunft` liefert Beziehung, Notiz,
  Geburtstag und Fotozahl, zurückgenommene Notizen fehlen, unbekannter Name ist ehrlich, nie
  Vektoren/Pfade.
- Angepasst: `test_werkzeuge.py` (Werkzeugzahl 9 → 10; der Vektoren-/Pfad-Test prüft jetzt den
  **Notnagel-Weg**, der Quiz-Weg hat einen eigenen Test).
- **Prüfbefehl grün:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
  **3619 passed, 2 skipped** (Exit 0).

## Offen (ehrlich benannt)

- `fotos_mit_person` läuft noch über `gesicht_fotos.suche_bilder_mit_person` (alter
  `gesichter_service`-Weg). Die Umstellung auf die Quiz-Quelle braucht eine Kennung→Pfad-Zuordnung
  (die Quiz-Gesichter tragen `fileid`, nicht den Dateipfad) — eigener Schritt.
- „Anlässe" einer Person (in welchen Ereignissen sie vorkommt) ist noch nicht in `person_auskunft`:
  dafür fehlt die Verknüpfung Gesicht → Ereignis als Dienst. Eigener Schritt.
