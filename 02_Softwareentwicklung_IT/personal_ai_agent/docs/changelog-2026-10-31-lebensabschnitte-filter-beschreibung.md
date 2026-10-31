# Änderungsprotokoll: Pixel-Filter (≥ 50 px), Gruppen-Auflösung in Lebensabschnitte & Bildbeschreibung

**Datum:** 31.10.2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Autor:** Antigravity AI Pair Programmer

---

### 1. Zusammenfassung der Änderungen

1. **Filter für pixelige Mini-Gesichter (< 50 px):**
   - **Backend (`gruppen_quiz.py`, `gruppen.py`):**
     - Neuer Parameter `min_px: int = 0` in `naechste()` und `liste()`.
     - Filtert Gruppen aus, deren Beispiel-Gesichter allesamt kleiner als `min_px` (Standard 50 px) sind. 472 unkenntliche/pixelige Gruppen werden übersprungen.
   - **Frontend (`index.html`, `gruppen_quiz.js`):**
     - Checkbox `Nur Gesichter ≥ 50 px (pixelige Mini-Gesichter ausblenden)` (standardmäßig aktiv).
     - Steuert dynamisch die Abfrage von `/api/gruppen/naechste` und `/api/gruppen/liste`.

2. **Gruppen-Auflösung in Lebensabschnitte bei bestätigten Personen:**
   - **Frontend (`gruppen_quiz.js`):**
     - In der Personen-Detailansicht (`personZeigen`) werden bestätigte Personen primär nach ihren chronologischen **Lebensabschnitten** gegliedert.
     - Jeder Lebensabschnitt zeigt Titel, Zeitspanne, altersbezogene Aussage, Begleitpersonen, Bildkacheln und den Button *„🔍 Alle X Gesichter dieser Phase“*.
     - Die redundanten, technischen Cluster-Vorschläge (`Person_001`, `Person_1113` etc.) werden nicht mehr als störende Hauptkarten gezeigt, sondern aufgeräumt in einem aufklappbaren Details-Container (`⚙️ Technische Cluster-Gruppen anzeigen`).
     - Metazeile zeigt jetzt: `X Gesichter · Y Lebensabschnitte`.

3. **Bildbeschreibung anzeigen & bearbeiten:**
   - **Backend (`erzaehl_service.py`, `erzaehlen.py`):**
     - Funktionen `beschreibung_holen(fileid)` und `beschreibung_speichern(fileid, text)`.
     - Routen `GET /api/erzaehlen/bild-beschreibung?fileid=...` und `POST /api/erzaehlen/bild-beschreibung`.
     - Schreibt atomar/anhängend in `bild_beschreibungen.jsonl` und aktualisiert `life_archive.db` (Spalte `beschreibung_reich` / `beschreibung`) sowie den In-Memory-Cache.
   - **Frontend (`index.html`, `erzaehlen.js`, `app.js`):**
     - In der Diashow/Anlässe: Button `📝 Beschreibung` blendet ein Inline-Textfeld zum direkten Bearbeiten und Speichern ein.
     - Im Vollbild-Viewer mit Rahmen (`zeigeBildVollbild` in `app.js`): Button `📝 Beschreibung` in der Werkzeugleiste öffnet einen modalen Editor zur Anzeige und Anpassung der Bildbeschreibung.

---

### 2. Verifikation

- `python -m pytest tests/test_gruppen_quiz.py tests/test_erzaehlen_bilder_info.py -q`: **99 passed, Exit 0**
- `node frontend/tests/test_gruppen_quiz.js`: **alle Prüfungen grün, Exit 0**
- `node frontend/tests/test_gruppen_liste.js`: **alle Prüfungen grün, Exit 0**
- `node frontend/tests/test_erzaehlen.js`: **alle Prüfungen bestanden, Exit 0**
- `node frontend/tests/test_bild_editor_b5_privat.js`: **alle Prüfungen bestanden, Exit 0**
