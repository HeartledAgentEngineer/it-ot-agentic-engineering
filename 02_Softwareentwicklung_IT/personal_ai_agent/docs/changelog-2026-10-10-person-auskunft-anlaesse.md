# Änderungsprotokoll 10.10.2026 — Anlässe einer Person in `person_auskunft` (Schritt 7)

Fortsetzung von `changelog-2026-10-10-fotos-mit-person-quiz.md`. Dort blieb als offener Punkt:
*„Anlässe einer Person" fehlt, weil die Verknüpfung **Gesicht → Ereignis** noch keinen Dienst hatte.*
Diese Verknüpfung steht jetzt.

## Ursache (belegt im Code)

Zwei getrennte Welten, die sich nie trafen:

- Die Personen-/Foto-Werkzeuge kennen je Bild die **`fileid`** (pCloud-Kennung) — die Quiz-Zuordnung
  (`gesicht_zuordnung.jsonl`) trägt sie an jedem Gesicht.
- Die Anlässe (`erzaehl_service`, aus `ereignisse.jsonl` + `fotobuch_ereignisse.jsonl`) tragen ihre
  Dateien als **`datei_kennungen`** (Liste von `fileid`s).

Der Verbinder dazwischen existierte nicht — deshalb konnte `person_auskunft` zwar die Fotozahl, aber
keine Anlässe nennen.

## Was neu ist

- **Neuer Dienst `erzaehl_service.anlaesse_zu_kennungen(kennungen, limit)`** (Verknüpfung
  Gesicht → Anlass): schneidet die übergebenen Bild-Kennungen mit den `datei_kennungen` jedes
  Anlasses (Ereignisse + Fotobuch + Ordner-Quelle, zusammengeführt wie in der Erzählliste). Ergebnis
  je Anlass nur Klartext: `datum, jahr, titel, kategorie, anzahl_dateien, treffer` — neueste zuerst,
  **wirft nie**, fehlt eine Ereignisquelle bleibt es leer.
- **Neue Quiz-Funktion `gruppen_quiz.bild_kennungen_person(name)`**: alle Bild/Video-Kennungen mit
  dieser Person, **ohne Obergrenze** (dieselbe Quelle wie `bilder_mit`, nur nicht auf 500 begrenzt —
  für Verknüpfungen braucht es die volle Menge). Ausschluss und Handzuordnung zählen wie im Register,
  unbekannter Name wird ehrlich gemeldet.
- **`person_auskunft` zeigt jetzt „Anlässe (N)"** — bis zu 10 Zeilen `Datum | Titel`, die Gesamtzahl
  im Kopf. Nur Klartext: **keine Kennungen, keine Pfade, keine Bilder**. Werkzeug-Beschreibung und
  `docs/spec-tool-use-v1.md` nachgezogen.

## Prüfung (echte Ausgabe)

- Neu in `backend/tests/test_personen_werkzeuge_quiz.py` (3 Tests, erfundene Daten in `tmp_path`):
  die Anlässe kommen aus den `datei_kennungen` der Ereignisse; der Anlass einer anderen Person taucht
  nicht auf; ohne Ereignisquelle bzw. ohne Treffer bleibt die Zeile weg.
- Messung am echten Bestand (PC, nur lesend): für die meistfotografierte bestätigte Person liefert
  `bild_kennungen_person` **1.117 Kennungen**, der neue Dienst daraus **127 Anlässe** (von 2.205
  Anlässen im Bestand); `person_auskunft` gibt sie als Klartextliste aus.
- **Prüfbefehl grün:** `cd backend && .venv/Scripts/python -m pytest tests/ -q` → Exit 0
  (Zahl im Nachtlauf-Abschlussbericht).

## Offen (ehrlich benannt)

- Die **Papa-Fotos** haben noch keine Anlässe: `ereignisse_ordner_bauen.py` wurde für die Sammlung
  nie gefahren (`ordner_ereignisse.jsonl` fehlt), also gibt es für Papas Bilder nichts zu verknüpfen
  (eigener Ketten-Schritt). Für den bestehenden Bestand funktioniert die Verknüpfung.
