# Changelog: Autocomplete-Suche & Vektor-Priorisierung beim Foto-Sortieren

**Datum:** 31.10.2026  
**Ziel:** Ablösung des unhandlichen nativen `<select>`-Dropdowns beim Benennen von Personen durch ein schnelles, berührungsfreundliches Autocomplete-Suchfeld mit KI-/Vektor-Vorschlägen ganz oben.

---

## 1. Problemstellung
Bisher mussten Nutzer beim Benennen von erkannten oder gezogenen Gesichtsrahmen im Vollbild-Editor ein langes natives `<select>`-Dropdown durchscrollen. Bei Dutzenden oder Hunderten Personen im Archiv auf Smartphone/Tablet war dies extrem mühsam, da native Select-Boxen auf Touch-Geräten kein Suchfeld bieten.

---

## 2. Technische Umsetzung

1. **Vollbild-Editor (`frontend/app.js`):**
   * Neuer Schnellauswahl-Knopf `.vollbild-person-suche-btn`: Zeigt die aktuelle Person oder lädt zur Suche ein.
   * Neues modales Such-Popover `.vollbild-person-suche-modal`:
     * Eingabefeld `.vollbild-person-suche-input` mit Live-Filterung in Echtzeit bei Tastatureingabe.
     * **KI- & Vektor-Vorschläge:** Werden aus den SFace-Embeddings (`_quizEditor.namensvorschlaege`) an die oberste Stelle als Prominente Chips (`⭐ KI-VORSCHLAG`) gesetzt.
     * Direkte Option `➕ "<Name>" als neue Person anlegen (nur am Handy)` bei unbekannten Eingaben.
   * Abwärtskompatibilität: Die vorhandene `.vollbild-person-wahl`-Struktur bleibt synchronisiert im DOM für bestehende automatisierte Tests.
2. **Gruppen-Quiz (`frontend/gruppen_quiz.js`):**
   * In `alleNamenZeigen()`: Bei mehr als 4 Personen erscheint ein Filter-Eingabefeld `.gruppen-namen-suche`, das die Namens-Chips sofort beim Tippen filtert.
3. **Sicherheit:**
   * Strikte Trennung: Keine `innerHTML`-Verwendung mit Nutzerdaten. Alle Namen und Vorschläge werden ausschließlich über `textContent` und `createElement` gerendert.
4. **Verifikation:**
   * Neuer Integrationstest `frontend/tests/test_person_suche_popover.js` (Exit 0).
   * Alle 129 Tests in `test_bild_editor_b4.js` und Gruppen-Tests grün.
   * Cache-Busting: `app.js?v=20261031A`, `gruppen_quiz.js?v=20261031A`.
