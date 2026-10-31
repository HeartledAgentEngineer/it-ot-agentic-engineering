# Änderungsprotokoll: Performance-Optimierung Lebensabschnitte & Selektiver Nacktheits-Schutz

**Datum:** 31. Oktober 2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Prüfstatus:** 17 Backend-Tests passed (Exit 0), Frontend-Test `test_bild_editor_b5_privat.js` passed (Exit 0).

---

## 1. Problem & Ursachenanalyse

1. **Server-Blockade durch 150-faches JSONL-Neulesen:**
   - In `lebensabschnitte_service.py` rief `vorschlag_fuer_offene_gruppe(gruppe)` bei unbenannten Gruppen für alle bekannten Personen `lebensabschnitte_fuer_person(n)` auf.
   - Jede Person löste für jeden Lebensabschnitt `begleiter_aus_beziehungen()` aus, was die 12,6 MB große Datei `beziehungen.jsonl` Zeile für Zeile von der Flash-Speicherplatte des Smartphones las und parste.
   - Bei 50 Personen und mehreren Phasen entstanden über 150 Festplatten-Scans (1,9 GB Datenmenge pro Request), wodurch der Python-Prozess auf dem Smartphone 6–8 Minuten bei 100 % CPU blockierte.
   - Folge: Das Frontend im Browser auf dem Xiaomi Pad 5 lief in das 20-Sekunden-Timeout (`⚠️ Server antwortet nicht (nach 20 s)`).

2. **Fehlalarm bei Privatsphäre-Verschleierung:**
   - `erzaehlBildIstPrivat` markierte Fotos pauschal als privat, sobald im Titel oder der Kategorie des Anlasses das Wort "privat" stand (z. B. "Familie privat").
   - Dadurch wurden normale Familien- und Urlaubsbilder fälschlicherweise verpixelt.
   - Die Verpixelung sollte laut Sebastian ausschließlich bei tatsächlicher Nacktheit / Genitalien greifen.
   - Durch fehlendes `position: relative` auf `.erzaehl-bild-rahmen` lag das Overlay zudem falsch positioniert und Tappen auf mobilen Touchscreens deckte das Foto nicht zuverlässig auf.

---

## 2. Durchgeführte Änderungen

1. **In-Memory-Caching & Indizierung (`lebensabschnitte_service.py`):**
   - `_beziehungen_index(pfad)`: Liest `beziehungen.jsonl` genau einmal in einen In-Memory-Index (`name.casefold() -> [(jahr, begleiter), ...]`). Folgende Abfragen laufen in unter 0,01 ms statt 380 ms.
   - `alle_personen_phasen(basis_pfad)`: Baut die Lebensabschnitte aller benannten Personen in einem schnellen Durchlauf aus den ohnehin im Speicher liegenden Gruppen/Namen auf und cacht das Ergebnis unter Prüfung der Datei-Zeitstempel (`st_mtime`).
   - `vorschlag_fuer_offene_gruppe`: Nutzt den Cache statt rekursiver Festplatten-Ladevorgänge.

2. **Präziser Nacktheits-Schutz & Entsperr-Gedächtnis (`erzaehlen.js`):**
   - Der pauschale Filter auf das Wort "privat" in Anlass-Titeln wurde entfernt.
   - `erzaehlBildIstPrivat`: Reagiert selektiv auf explizite Genitalien/Nacktheit in der KI-Beschreibung (`genital`, `penis`, `vagina`, `scham`, `aktfoto`), schließt aber normalen "nackten Oberkörper" am Strand/Pool aus.
   - `entsperrtSet`: Speichert manuell aufgedeckte Fotos in `localStorage` (`personal_ai_entsperrte_bilder`). Ein aufgedecktes Bild bleibt dauerhaft unverschleiert.
   - Schaltfläche `🔒 Privat (aktiv)` / `🔓 Nicht privat` schaltet zwischen den Listen um.

3. **Touch-Optimierung & Vollbild-Rahmen (`index.html`, `style.css`):**
   - `.erzaehl-bild-rahmen` besitzt nun `position: relative`, sodass das Schloss-Overlay exakt auf dem Bild sitzt.
   - `.erzaehl-privat-sperre` unterstützt `touch-action: manipulation`, `onpointerdown` und enthält einen expliziten "Aufdecken"-Knopf.
   - Antippen des aufgedeckten Bildes öffnet wie gewünscht die Vollbildansicht mit den erkannten Gesichtern und Rahmen (`zeigeBildVollbild`).
