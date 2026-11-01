# Änderungsprotokoll: Vorlesen via Web Audio API & Neuanlage von Personenprofilen im Bild-Editor

**Datum:** 01.11.2026  
**Autor:** Antigravity  
**Betroffene Bereiche:** `personal_ai_agent` (Frontend & Backend)

---

## 1. Problemstellung

1. **Vorlese-Stille / „Vorlesen gerade nicht möglich.“ in allen Bilderansichten:**
   - Auf Mobilgeräten (Android Chrome auf Motorola Edge 50 / Xiaomi Pad 5) verwarfen die Browser-Sicherheitsrichtlinien die User-Aktivierung („Transient User Activation“), wenn die Sprachsynthese über den Server (`POST /api/speak` via Klaus/Edge-TTS) mehrere Sekunden in Anspruch nahm. Der anschließende Aufruf von `audio.play()` wurde mit `NotAllowedError` blockiert und sprang in den Fallback, der in WebViews mangels passender Offline-Stimmen ebenfalls scheiterte.
   - Beim Vorlesen der Notizen in der Gruppenansicht las der Vorleser fälschlicherweise Datumszeilen und Steuerungs-Emojis („2026-10-07... · tippen ✏️ 🗑️“) mit.

2. **Neue Person ohne bestehendes Profil benennen schlug fehl:**
   - Wenn ein Nutzer im Vollbild-Editor ein Gesicht antippte, einen neuen Namen in das Feld eintippte und direkt auf `💾 Speichern` drückte (ohne zuvor explizit auf den kleinen OK-Knopf oder Enter zu tippen), war der Name im Editorzustand noch nicht verbindlich zugeordnet. Die Funktion `bildEditorCloudAenderungen` fand 0 Änderungen und meldete: *„Keine Änderungen zu speichern.“*.
   - Zudem legte der Backend-Endpunkt `/api/gruppen/bild-rahmen` zwar den Bounding-Box-Eintrag in `bild_korrekturen.json` ab, legte für unbekannte Namen jedoch keinen Datensatz in `personen_profile.json` an.

3. **Erinnerungen löschen & Abfrage-Notiz:**
   - Zu einem Bild erfasste Erinnerungen konnten nicht gelöscht werden.
   - Bei der automatischen Bildgeschichten-Erstellung wurde die benutzerseitige Notiz nicht als Auslöser/Abfrage protokolliert.

---

## 2. Änderungen

### Frontend
- **Web Audio API Vorlese-Pipeline (`frontend/erzaehlen.js`):**
  - `audioVorabFreischalten()`: Initialisiert und entsperrt synchron beim Klick-Event einen `AudioContext` (`window.AudioContext || window.webkitAudioContext`).
  - `vorlesenText()`: Dekodiert die vom Server gelieferten MP3-Audiobytes über `decodeAudioData` und spielt sie über einen `AudioBufferSourceNode` ab. Dadurch ist die Wiedergabe immun gegen Timeout-Verfall der User-Gesture.
  - `geschichtenTextSammeln()`: Wählt gezielt `.erzaehl-geschichte-text` aus, sodass Zeitstempel, Quellenangaben und Aktions-Schaltflächen nicht mitgelesen werden.
- **Unbestätigte Namenseingaben automatisch übernehmen (`frontend/app.js`):**
  - In `speichereBildCloud`: Vor der Planung der Änderungen prüft der Editor, ob in `.vollbild-neue-person` noch ein Text steht, und weist diesen sofort dem aktuellen Rahmen zu (`rahmenPersonSetzen`).
- **Synchronisation & Aktualisierung (`frontend/erzaehlen.js`):**
  - `zeigeBildVollbild` übergibt `onClose: () => nachGesichtAenderung()`.
  - Globaler Event-Listener auf `bild-rahmen-gespeichert` aktualisiert Gesichter und Personen im Hintergrund.
- **Erinnerungen löschen (`frontend/erzaehlen.js`):**
  - Schaltfläche `🗑️` mit Bestätigungsdialog ruft `DELETE /api/erzaehlen/geschichten/{id}` auf und entfernt den Eintrag sofort aus der Ansicht.
- **Cache-Busting (`frontend/index.html`):**
  - Erhöht auf `?v=20261101B`.

### Backend
- **Profil-Erstellung bei neuen Personen (`backend/app/services/gruppen_quiz.py`):**
  - In `bild_rahmen`: Sammelt alle neu vergebenen Namen (`hat_name` oder `neu`) und legt sie über `_profil_ergaenzen` atomar in `personen_profile.json` an.
  - In `_antwort_anwenden` (`art == "name"`): Ein Personenprofil wird auch dann angelegt, wenn Beziehung/Notiz noch leer sind (`"neu_angelegt": True`).
  - In `_rueckgaengig_eintrag`: Neu angelegte, noch leere Profile werden bei Rückgängig sauber wieder entfernt.
- **Lösch-Endpunkt & Abfrage-Feld (`backend/app/router/erzaehlen.py`, `backend/app/services/erzaehl_service.py`):**
  - `DELETE /api/erzaehlen/geschichten/{id}` markiert den Eintrag in `geschichten.jsonl` revisionssicher als gelöscht (`"geloescht": True`).
  - `POST /api/erzaehlen/geschichten` speichert optional das Feld `abfrage`.

---

## 3. Verifikation

1. **Backend Tests:**
   - `pytest tests/test_bild_editor_b1.py tests/test_gruppen_quiz.py -q`: **173 passed**, Exit 0.
   - Neuer Testfall: `test_bild_editor_b1.py::test_bild_rahmen_neue_person_erstellt_profil_eintrag`.
2. **Frontend Tests:**
   - `node frontend/tests/test_erzaehlen.js`: **Alle Prüfungen bestanden**, Exit 0.
   - `node frontend/tests/test_bild_editor_b4.js`: **alle 129 Prüfungen bestanden**, Exit 0.
   - `pytest tests/test_frontend_node.py -q`: **59 passed**, Exit 0.
