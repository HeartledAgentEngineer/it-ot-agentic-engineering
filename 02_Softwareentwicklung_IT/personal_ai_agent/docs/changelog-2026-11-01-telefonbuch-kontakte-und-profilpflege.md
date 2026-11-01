# Änderungsprotokoll: Telefonbuchfelder & Kontaktpflege im Chat überschreibbar

**Datum:** 01.11.2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Autor:** Antigravity  

---

## 1. Ausgangslage & Problem
Das LLM verweigerte das Ändern von Telefonbuchfeldern, Geburtstagen und Telefonnummern mit der Begründung:
*„Das Telefonbuchfeld selbst kann ich nicht überschreiben — dafür habe ich kein Werkzeug, das ist ein Eingriff in die Systemdaten.“*

Ursachen im Code:
1. Das Werkzeug `person_profil_aendern` in `backend/app/services/werkzeuge.py` bot nur `name`, `beziehung`, `notiz`, `vorname`, `nachname`, `spitznamen` an. Parameter für `geburtstag`, `telefonnummer` / `nummern` und `kontakt_id` fehlten vollständig.
2. `backend/app/services/faehigkeiten.py` beschränkte die Profilpflege explizit auf `(Beziehung, Beruf, Vor-/Nachname)` und schloss Systemdaten/Telefonbuch unklar aus.
3. `backend/app/services/auftrags_erkennung.py` enthielt keine Signale für `telefonbuch`, `kontakt`, `geburtstag` und `telefonnummer`.
4. `backend/app/services/gruppen_quiz.py` bot keine Funktion, um `geburtstag` und `nummern` im Profil oder in `kontakte.json` zu aktualisieren, und `profil_ergaenzen` speicherte diese Felder nicht in `personen_profile.json`.

---

## 2. Änderungen

### Backend
1. **`backend/app/services/gruppen_quiz.py`**:
   - `_kontakt_eintrag_aktualisieren(kid, geburtstag, nummern)`: Aktualisiert Einträge direkt in `kontakte.json`, falls vorhanden.
   - `_profil_ergaenzen(...)`: Unterstützt nun `geburtstag` und `nummern` (aktualisiert Profil und `kontakt`-Objekt, schreibt `geburtstag_vorher` / `nummern_vorher` ins Änderungsprotokoll für Rückgängig).
   - `profil(name)`: Liefert `geburtstag` und `nummern` direkt im Profil-Dictionary zurück.
   - `profil_ergaenzen(...)`: Akzeptiert `geburtstag`, `telefonnummer` und `nummern`, normalisiert Datumsangaben (`DD.MM.YYYY` -> `YYYY-MM-DD`) und Telefonnummernlisten, aktualisiert `personen_profile.json` und synchronisiert `kontakte.json`.
   - `rueckgaengig`: Stellt `geburtstag_vorher` und `nummern_vorher` bei Profil-Änderungen sauber wieder her.

2. **`backend/app/services/werkzeuge.py`**:
   - `_person_auskunft`: Zeigt `Geburtstag: ...` und `Telefon: ...` im vorlesbaren Volltext an.
   - `_person_profil_aendern`: Nimmt `geburtstag`, `telefonnummer`, `nummern`, `kontakt_id` entgegen und ruft `gruppen_quiz.profil_ergaenzen` auf. Formuliert eine sprechbare Bestätigung mit gesetztem Geburtstag/Telefon.
   - `REGISTER["person_profil_aendern"]`: Parameter und Tool-Beschreibung erweitert, damit das LLM weiß, dass es Telefonbuchfelder und Systemdaten direkt überschreiben und korrigieren kann.

3. **`backend/app/services/auftrags_erkennung.py`**:
   - `_DATEN_PFLEGE_SIGNALE` um `"telefonbuch"`, `"kontakt"`, `"kontakte"`, `"geburtstag"`, `"telefonnummer"`, `"handynummer"` ergänzt.

4. **`backend/app/services/faehigkeiten.py`**:
   - `_DATEN_PFLEGE_WORTE` und Erklärung erweitert: Chat-Pflege von Telefonbuchfeldern, Geburtstagen und Telefonnummern ist explizit erlaubt und verlangt keinen Hermes.

### Tests
- `backend/tests/test_daten_aendern_werkzeuge.py` (6 Tests):
  - `test_neue_werkzeuge_registriert`
  - `test_faehigkeiten_grenze_erlaubt_persoenliche_daten`
  - `test_auftrags_erkennung_ignoriert_persoenliche_daten`
  - `test_notiz_speichern_ausfuehrung`
  - `test_person_profil_aendern_ausfuehrung`
  - `test_person_auskunft_zeigt_geburtstag_und_telefon`
- Alle Tests grün (6 passed in 2.83s).
- `test_gruppen_quiz.py` unverändert grün (92 passed in 19.41s).
- `test_werkzeuge.py` unverändert grün (30 passed in 18.11s).
