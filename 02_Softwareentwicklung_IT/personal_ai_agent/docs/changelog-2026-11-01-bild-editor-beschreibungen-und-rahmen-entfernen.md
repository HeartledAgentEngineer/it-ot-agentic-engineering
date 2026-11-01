# Changelog: Bildbeschreibungen anzeigen & vorlesen, Alle Rahmen entfernen, Toolbar-Einpassung & Personensuche

**Datum:** 01.11.2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Wünsche Sebastian:**
1. KI-Bildbeschreibungen überall lesbar (durchscrollen) und vorlesbar machen (🔊-Button):
   - Im Anlass-Erzählteil (Einzelbild-Ansicht).
   - Im Vollbild-Bild-Editor zur Rahmen-Bearbeitung.
2. Vollbild-Bild-Editor: Das riesige `<select>`-Dropdown-Menü mit allen Personennamen entfernen/ausblenden, da der Such-Knopf (`👤 Person suchen … ▾` mit Popover, Autocomplete und KI-Vorschlägen) der ergonomischere Weg ist.
3. Vollbild-Bild-Editor: Das Bild so einpassen, dass das gesamte Bild ohne Verdeckung und ohne Zoom oberhalb der Leiste sichtbar ist. Die Leiste sitzt nicht mehr störend bei `bottom: 74px`, sondern bündig unten (`bottom: 12px`), und der Bild-Wrapper hält den nötigen Abstand ein.
4. Vollbild-Bild-Editor: Knopf `🗑️ Alle entfernen`, um alle falschen / fremden Gesichtsmarkierungen auf einem Bild auf einen Schlag zu verwerfen. Beim Klick auf `💾 Speichern` werden diese Referenzen atomar gelöscht und aus allen Gruppen/Clustern ausgeschlossen.

---

## Änderungen im Detail

### 1. KI-Bildbeschreibungen im Anlass-Erzählteil (`frontend/index.html` & `frontend/erzaehlen.js`)
- `frontend/index.html`:
  - Neben `#erzaehl-bild-beschreibung` einen Vorlese-Knopf `#erzaehl-bild-beschreibung-vorlesen` (🔊) platziert.
  - `#erzaehl-bild-beschreibung` scrollbar formatiert (`max-height: 120px; overflow-y: auto; line-height: 1.4; white-space: pre-wrap;`).
- `frontend/erzaehlen.js`:
  - `bildInfoAnzeigen()`: Steuert Sichtbarkeit von `#erzaehl-bild-beschreibung-vorlesen` basierend auf vorhandenem Beschreibungstext.
  - `init()`: Klick auf `#erzaehl-bild-beschreibung-vorlesen` schaltet Audio synchron vorab frei (`audioVorabFreischalten()`) und liest die Beschreibung via `vorlesenText()` vor.
  - Globale Freigabe von `window.vorlesenText` und `window.audioVorabFreischalten`, sodass der Bild-Editor die identische Audio-/TTS-Infrastruktur nutzen kann.

### 2. Bildbeschreibungen im Vollbild-Bild-Editor (`frontend/app.js`)
- In `zeigeBildVollbild`:
  - `.vollbild-beschreibung` von `pointer-events: none` auf `pointer-events: auto` umgestellt.
  - Scrollbarer Inhaltsbereich (`max-height: 85px; overflow-y: auto; text-align: left;`) ermöglicht das vollständige Durchlesen auch längerer Gemini-Beschreibungen.
  - Eigener Vorlese-Knopf `🔊 Vorlesen` (`.vollbild-beschreibung-vorlesen-btn`), der die Web-Audio- / TTS-Ausgabe startet.
  - Automatisches asynchrones Nachladen via `/api/erzaehlen/bild-beschreibung?fileid=...`, falls beim Öffnen noch keine Beschreibung im DOM-Datensatz hinterlegt war.
  - Beim manuellen Editieren und Speichern (`📝 Beschreibung`) synchronisiert sich die Beschreibungs-Box sofort.

### 3. Toolbar-Position & Bild-Einpassung ohne Zoom (`frontend/app.js`)
- `leiste`: `bottom: 12px` (vorher `74px`), wodurch die Toolbar kompakt am unteren Bildschirmrand liegt.
- `wrap`: `padding-top: 40px; padding-bottom: 120px; box-sizing: border-box;`
- `big`: `max-height: calc(100vh - 160px); max-width: 100vw; object-fit: contain;`
- **Ergebnis:** Vertikale und horizontale Fotos passen ohne Verschieben vollständig in den sichtbaren Viewport oberhalb der Buttons. Gesichter am unteren Bildrand werden nicht mehr verdeckt.

### 4. Personensuche statt Dropdown-Menü (`frontend/app.js`)
- `personWahl` (`select.vollbild-person-wahl`) visuell ausgeblendet (`display: none`), bleibt jedoch für DOM- und Quelltext-Wächter rückwärtskompatibel erhalten.
- Primärer Zuordnungsweg ist der Button `personSucheBtn` (`.vollbild-person-suche-btn`), der das interaktive Popover mit Schnellsuche, Filterung und KI-Vorschlägen öffnet.

### 5. „Alle Rahmen entfernen“-Knopf (`frontend/app.js`)
- Neuer Button `🗑️ Alle entfernen` (`.vollbild-alle-entfernen`) in der Editor-Werkzeugleiste.
- Setzt alle Live-Rahmen auf `null` und erstellt einen Undo-Snapshot (rückgängig machbar mit `↩`).
- Beim anschließenden Klick auf `💾 Speichern` erzeugt `bildEditorCloudAenderungen()` für alle Gesichter `{ gid, entfernen: true }`, wodurch das Backend (`POST /api/gruppen/bild-rahmen`) die Rahmen löscht und die Gesichter dauerhaft aus allen Gruppen ausschließt.

---

## Verifikation & Tests
- `frontend/tests/test_bild_editor_b4.js`: **135 passed** (inkl. neuer K11-Prüfungen für Alle-entfernen, Beschreibungs-Vorlesen & Vollbild-Einpassung).
- `frontend/tests/test_erzaehlen.js`: **grün** (Cache-Bust `20261101E`, Beschreibung mit Vorlese-Knopf).
- `frontend/tests/test_erzaehlen_hand_gesichter.js`: **grün**.
- `frontend/tests/test_vollbild_zoom.js`: **grün**.
- `frontend/tests/test_quiz_rahmen_neu_erkennen.js`: **grün**.
- `frontend/tests/test_person_suche_popover.js`: **grün**.
- Backend Gate `tools/gate/tor.py`: **83 passed**, Exit 0.
