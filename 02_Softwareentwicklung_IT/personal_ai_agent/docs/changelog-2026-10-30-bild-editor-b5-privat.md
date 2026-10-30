# Bild-Editor B5 & Selektiver Privat-Schutz — 30.10.2026

Planschritt B5 von „Bild-Editor überall" und Umsetzung des selektiven Privat-Schutzes („Schutzmaske für intime Bilder beim Durchblättern").

## Was gebaut ist

### 1. Selektiver Privat-Schutz im Erzählen-Modus (`frontend/erzaehlen.js`)
- **Intelligente / selektive Erkennung (`erzaehlBildIstPrivat`):**
  * Bilder werden selektiv geschützt, wenn sie entweder in der lokalen Privatsphäre-Menge des Nutzers (`localStorage['erzaehlen_privat_dateien']`) enthalten sind, die Ereignis-Kategorie oder der Titel sensible Schlüsselwörter enthält (`privat|intim|sensibel`), oder Bildbeschreibungen intime Begriffe enthalten (`nackt|intim|penis|aktfoto|erotik`).
  * Neutrale/normale Alltagsfotos werden **sofort und ohne Klick/Verzögerung** normal angezeigt (0 Klicks Overhead).
- **Maskierung & Unschärfe-Filter:**
  * Private Bilder erhalten die CSS-Klasse `.erzaehl-privat-verdeckt` (`filter: blur(28px); transform: scale(1.05); overflow: hidden; pointer-events: none`).
  * Über dem Bild liegt ein zentriertes Schloss-Badge `#erzaehl-privat-sperre`: `🔒 Privat · Antippen zum Aufdecken`.
- **Interaktives Aufdecken:**
  * Ein Klick auf das Schloss-Badge deckt **nur dieses eine Bild** für die laufende Sitzung auf (`zustand.aufgedeckteBilder.add(fileid)`).
  * Weiterschalten (◀/▶, Swipe, nächster Anlass) schützt nachfolgende private Fotos weiterhin zuverlässig vor unerwünschtem Blickkontakt.
- **Manueller Umschalter (`#erzaehl-privat-toggle`):**
  * Jedes Bild kann über den Knopf `🔒 Privat` in der Steuerleiste jederzeit manuell als privat markiert oder de-markiert werden. Die Auswahl wird im `localStorage` persistent gespeichert.

### 2. Bildeditor überall verknüpft (B5)
- **Erzählen & Anlässe:**
  * In der Erzählen-Ansicht wurde die Steuerleiste `.erzaehl-bild-steuerleiste` eingefügt mit dem Knopf `✏️ Personen bearbeiten` (`#erzaehl-bild-editor-btn`).
  * Klick auf den Knopf oder Klick auf das Bild öffnet den vollwertigen Cloud-Bildeditor (`zeigeBildVollbild(bild, zustand.gesichter, { fileid: dateiKennung })`).
  * Bounding Boxes aller erkannten Personen werden eingeblendet, können editiert, neu erkannt (`POST /api/gruppen/bild-erkennen`) oder gespeichert (`POST /api/gruppen/bild-rahmen`) werden.
- **Galerie-Großansicht (`frontend/app.js`):**
  * In `oeffneFotoGross` wurde neben dem Schließen-Knopf ein `✏️ Personen`-Knopf ergänzt, der `zeigeBildVollbild` mit `{ fileid: fid }` aufruft.

### 3. Tests & Absicherung
- `frontend/tests/test_bild_editor_b5_privat.js`: 17 strukturierte Unittests für die Erkennung, Maskierung, Aufdeckung und Persistenz.
- Alle 57 Node-Frontend-Tests (`test_frontend_node.py`) grün.
