# Änderungsprotokoll 30.10.2026: Lebensabschnitte und belegbare Aussagen (On-Device)

## Anlass und Ziel

Auf Wunsch des Nutzers („alle Berechnungen sollen auch in Zukunft eigenständig auf dem Handy laufen“) wurde die Logik für chronologische **Lebensabschnitte (Phasen nach Jahren)** sowie **belegbare Aussagen** direkt in das Python-Backend des Smartphones (`personal_ai_agent` in Termux) integriert.

Bisher wurden alle Gesichter und Bildgruppen einer benannten Person ungeordnet dargestellt. Mit diesem Modul werden die Daten on-device strukturiert:
1. **Lebensabschnitte (Phasen):** Gesichter und Gruppen einer Person werden chronologisch nach Kalenderjahren gebündelt. Lücken > 2 Jahre oder Zeiträume > 5 Jahre mit Bruch führen zu eigenen Phasen (z. B. `2011 – 2013`, `2018 – 2019`). Bei hinterlegtem Geburtstag im Profil/Kontakt wird das ungefähre Lebensalter (z. B. `ca. 11–13 Jahre`) ausgewiesen.
2. **Belegbare Aussagen:** Für jede Phase wird ermittelt, wie viele Bilder existieren und welche Begleitpersonen am häufigsten gemeinsam mit ihr auf Fotos zu sehen waren (aus `beziehungen.jsonl`).
3. **Hypothesen für offene Gruppen:** Unbenannte Gruppen werden zeitlich mit den Lebensabschnitten bekannter Personen abgeglichen, um treffsichere Vorschläge für das Benennen und Andocken zu liefern.

## Geänderte & neue Dateien

- **Neu:** `backend/app/services/lebensabschnitte_service.py`
  - `jahr_aus(datum)`: Sichere Extraktion des 4-stelligen Kalenderjahrs.
  - `alter_in_jahr(geburtsdatum, ziel_jahr)`: Altersberechnung.
  - `phasen_bilden_jahre(jahre)`: Algorithmische Einteilung in Lebensabschnitte.
  - `begleiter_aus_beziehungen(name, von_jahr, bis_jahr)`: Auswertung häufiger Begleitpersonen aus `beziehungen.jsonl`.
  - `lebensabschnitte_fuer_person(name, vorschlaege, profil_daten)`: Hauptfunktion zur Berechnung der Phasen und der vorlesbaren Fließtext-Aussage.
  - `vorschlag_fuer_offene_gruppe(gruppe, katalog)`: Hypothesenbildung für offene Gruppen.
- **Geändert:** `backend/app/services/gruppen_quiz.py`
  - `person(name)`: Ergänzt um die Schlüssel `lebensabschnitte` (Liste) und `lebensabschnitte_aussage` (String). Bestehende Felder (`vorschlaege`, `profil`) bleiben 100 % abwärtskompatibel.
  - `detail(kennung)`: Ergänzt offene Gruppen um `lebensabschnitt_vorschlag`, wenn ein passender Lebensabschnitt existiert.
- **Neu:** `backend/tests/test_lebensabschnitte_service.py`
  - 9 Wächtertests für alle Kernfunktionen, Randfälle, synthetische Begleiterdaten und Endpunkt-Integration.

## Verifikation

- `pytest tests/test_lebensabschnitte_service.py` -> 9 passed (Exit 0)
- `pytest tests/test_gruppen_quiz.py tests/test_personen_werkzeuge_quiz.py` -> 114 passed (Exit 0)
