# Änderungsprotokoll 30.10.2026: Lebensabschnitte und belegbare Aussagen (On-Device)

## Anlass und Ziel

Auf Wunsch des Nutzers („alle Berechnungen sollen auch in Zukunft eigenständig auf dem Handy laufen“) wurde die Logik für chronologische **Lebensabschnitte (Phasen nach Jahren)** sowie **belegbare Aussagen** direkt in das Python-Backend des Smartphones (`personal_ai_agent` in Termux) integriert.

Bisher wurden alle Gesichter und Bildgruppen einer benannten Person ungeordnet dargestellt. Mit diesem Modul werden die Daten on-device strukturiert:
1. **Lebensabschnitte (Phasen):** Gesichter und Gruppen einer Person werden chronologisch nach Kalenderjahren gebündelt. Lücken > 2 Jahre oder Zeiträume > 5 Jahre mit Bruch führen zu eigenen Phasen (z. B. `2011 – 2013`, `2018 – 2019`). Bei hinterlegtem Geburtstag im Profil/Kontakt wird das ungefähre Lebensalter (z. B. `ca. 11–13 Jahre`) ausgewiesen.
2. **Belegbare Aussagen:** Für jede Phase wird ermittelt, wie viele Bilder existieren und welche Begleitpersonen am häufigsten gemeinsam mit ihr auf Fotos zu sehen waren (aus `beziehungen.jsonl`).
3. **Hypothesen für offene Gruppen:** Unbenannte Gruppen werden zeitlich mit den Lebensabschnitten bekannter Personen abgeglichen, um treffsichere Vorschläge für das Benennen und Andocken zu liefern.

## Geänderte & neue Dateien

- **Neu / Erweitert:** `backend/app/services/lebensabschnitte_service.py`
  - `jahr_aus(datum)`: Sichere Extraktion des 4-stelligen Kalenderjahrs.
  - `alter_in_jahr(geburtsdatum, ziel_jahr)`: Altersberechnung.
  - `phasen_bilden_jahre(jahre)`: Algorithmische Einteilung in Lebensabschnitte.
  - `begleiter_aus_beziehungen(name, von_jahr, bis_jahr)`: Auswertung häufiger Begleitpersonen aus `beziehungen.jsonl`.
  - `lebensabschnitte_fuer_person(name, vorschlaege, profil_daten)`: Hauptfunktion zur Berechnung der Phasen und der vorlesbaren Fließtext-Aussage.
  - `vorschlag_fuer_offene_gruppe(gruppe, katalog, personen_phasen)`: Hypothesenbildung für offene Gruppen mit Eindeutigkeitsprüfung (bei Mehrdeutigkeit reduzierter Score 0.50, um falsche Zuordnungen zu verhindern).
  - `andocken_kandidaten(...)`: Effiziente Vorevaluierung aller offenen Gruppen mit vorberechneten Phasen (< 5 ms).
- **Geändert:** `backend/app/services/gruppen_quiz.py`
  - `person(name)`: Ergänzt um die Schlüssel `lebensabschnitte` (Liste) und `lebensabschnitte_aussage` (String). Bestehende Felder (`vorschlaege`, `profil`) bleiben 100 % abwärtskompatibel.
  - `detail(kennung)`: Ergänzt offene Gruppen um `lebensabschnitt_vorschlag`, wenn ein passender Lebensabschnitt existiert.
  - `andocken(trocken, min_sicherheit, kennungen, ziel_name)`: On-Device-Andocken offener Gruppen an Lebensabschnitte bekannter Personen (Trockenlauf zur Vorschau oder Schreibmodus mit `_antwort_anwenden`).
- **Geändert:** `backend/app/router/gruppen.py`
  - `POST /api/gruppen/andocken`: Route für das Andocken und die Neugruppierung.
- **Geändert:** `frontend/index.html`, `frontend/gruppen_quiz.js`, `frontend/style.css`
  - Visualisierung von Lebensabschnitten in der Personenansicht mit Zeiträumen, Altersstufen, belegenden Miniatur-Kacheln und häufigen Begleitern.
  - Interaktives Andocken in der Gruppenübersicht: Knopf `⚡ Offene Gruppen andocken` ruft den Trockenlauf ab, zeigt passende Kandidaten (71 Gruppen, 825 Gesichter) und ermöglicht die direkte Übernahme (`POST /api/gruppen/andocken`).
  - Zugeordnete Gruppen (`vorschlaege`) werden mit ihrem jeweiligen Lebensabschnitt und Alter beschriftet (`🏷️ 2011 – 2012 (ca. 11–12 Jahre)`). Lebensabschnitts-Karten heben zugehörige Gruppen per Klick hervor.
  - Lebensabschnitts-Vorschlagskarte im Gruppen-Quiz mit Schnell-Übernahme-Knopf („Als X übernehmen“).
  - Cache-Bust `20261030B`.
- **Geändert:** `frontend/app.js` (Bildeditor)
  - `bildEditorCloudErkennung`: Bekannte Gesichter werden nicht mehr verworfen, sondern deren Modell-Namensvorschläge werden an den jeweiligen Live-Rahmen geheftet (`e.namensvorschlaege[k]`) und stehen im Personen-Auswahlmenü direkt ganz oben.
- **Wächtertests:**
  - `backend/tests/test_lebensabschnitte_service.py` (11 Tests, Exit 0).
  - `frontend/tests/test_gruppen_quiz.js` (Alle Prüfungen grün, Exit 0).
  - `frontend/tests/test_bild_editor_b4.js` (129 Prüfungen grün, Exit 0).

## Verifikation

- `pytest tests/test_lebensabschnitte_service.py` -> 11 passed (Exit 0)
- `node frontend/tests/test_gruppen_quiz.js` -> alle Prüfungen grün (Exit 0)
- `node frontend/tests/test_bild_editor_b4.js` -> 129 Prüfungen bestanden (Exit 0)
- `pytest tests/test_frontend_node.py` -> 57 passed (Exit 0)
