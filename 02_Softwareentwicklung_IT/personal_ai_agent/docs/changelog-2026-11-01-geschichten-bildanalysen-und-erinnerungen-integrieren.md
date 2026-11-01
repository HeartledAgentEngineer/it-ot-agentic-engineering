# Änderungsprotokoll: KI-Bildanalysen einbinden & Erinnerungen inhaltlich übernehmen (keine Zitate)

**Datum:** 01.11.2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Autor:** Antigravity  
**Referenz:** Nutzer-Feedback Sebastian (*„Bin unzufrieden mit der bild und Anlassgeschichte...die ki generierten bildanalysen fließen nicht mit ein und die Erinnerungen bitte nicht zitieren sondern Informationen inhaltlich übernehmen in die Geschichten“*)

---

## 1. Problemstellung & Motivation

1. **Fehlende KI-Bildanalysen in den Geschichten:**
   - In `anlass_geschichte_generieren` wurden die visuellen Bildbeschreibungen der Bilder (`_beschreibungen_gesamt_lesen()`) überhaupt nicht abgefragt oder einbezogen. Die Anlass-Geschichte erwähnte lediglich Titel, Datum und Personen, ignorierte jedoch das, was auf den Fotos tatsächlich visuell zu sehen ist.
   - In `ki_geschichte_generieren` wurden englische Gemini-Vision-Beschreibungen oft nur fragmentarisch mit starrem Präfix (*„Auf dem Bild zu sehen: ...“*) angehängt, anstatt fließend und natürlich in die Szene eingebettet zu werden.
2. **Unerwünschte Zitate von Erinnerungen:**
   - Erinnerungen und Notizen wurden bisher starr mit einleitenden Labels zitiert (z. B. `Meine Notiz dazu: ...`, `Dazu die persönliche Notiz: "..."` oder `Dazugehörige Anmerkung: „...“`).
   - Dadurch wirkte die Geschichte wie das Auslesen von Datenbank-Metadaten statt wie eine zusammenhängende, persönliche Erzählung.

---

## 2. Änderungen im Detail

### A. Backend (`backend/app/services/erzaehl_service.py`)

1. **Eindeutschung & Glättung von Bildbeschreibungen (`deutsch_fuer_bildbeschreibung`):**
   - Erkennt englische Gemini-Vision-Muster (z. B. *„An adult lies down indoors playing with a small baby...“*, *„A young man sits indoors...“*, *„Warm sunlight illuminates the scene“*) und übersetzt sie regelbasiert in elegantes, natürliches Deutsch.
   - Deutsche Bildbeschreibungen bleiben unverändert erhalten.

2. **Inhaltliche Übernahme von Erinnerungen (`_notiz_fuer_geschichte`):**
   - Entfernt Zitatzeichen (`"`, `„`, `“`, `»`, `«`) und führende Metadaten-Labels (`Meine Notiz dazu:`, `Erinnerung:`, etc.).
   - **Ich-Form:** Die Erinnerung fließt direkt als persönlicher Bericht des Nutzers in den Fließtext ein – ohne einleitendes Zitat-Label.
   - **Erzähler-Sicht:** Wird sachlich als überlieferte Schilderung eingebunden (`Aus den überlieferten Aufzeichnungen: ...`), ebenfalls ohne Zitatzeichen.
   - **Ereignis-Fallback:** Hat eine Einzeldatei keine eigene Notiz, wird automatisch die Notiz des übergeordneten Anlasses herangezogen.

3. **Vollständige Einbindung in die Anlass-Geschichte (`anlass_geschichte_generieren`):**
   - Liest für alle Bilder des Anlasses (`dateien`) die vorhandenen Bildbeschreibungen aus dem Gesamtbestand (`_beschreibungen_gesamt_lesen()`).
   - Bei Einzelaufnahmen: Das Foto fängt den konkreten Augenblick visuell ein.
   - Bei Bilderserien: Die ersten prägnanten Bildanalysen werden als zusammenhängende Szenenfolge formuliert.
   - Neuer Parameter `beschreibungen: Optional[List[str]] = None` ermöglicht auch die explizite Übergabe von Bildbeschreibungen.

4. **Vollständige Einbindung in die Bild-Geschichte (`ki_geschichte_generieren`):**
   - Bildanalyse wird eingedeutscht und als Teil der Szene erzählt (*„Das Foto fängt diesen Augenblick ein: ...“* bzw. *„Die visuelle Bildanalyse dokumentiert: ...“*).
   - Die Notiz schließt direkt und fließend an den visuellen Eindruck an.

### B. Router (`backend/app/router/erzaehlen.py`)
- `AnlassGeschichteEingabe`: Neues optionales Feld `beschreibungen: Optional[List[str]] = Field(default=None)` hinzugefügt und an `erzaehl_service.anlass_geschichte_generieren` durchgereicht.

---

## 3. Verifikation & Prüfbelege

1. **Selektiver Testlauf (`tor.py`):**
   ```text
   [Tor] Selektiver Best-Practice-Lauf: 6 Testdatei(en) fuer geaenderte Komponenten:
     * tests/test_erzaehlen.py
     * tests/test_erzaehlen_bilder_info.py
     * tests/test_erzaehlen_bilder_info_erweitert.py
     * tests/test_erzaehlen_ki_geschichte.py
     * tests/test_erzaehlen_personen.py
     * tests/test_erzaehlen_titel.py
   84 passed, 3 warnings in 5.86s
   [Tor] GRUEN in 6.0s (Exit 0)
   ```
2. **Frontend Node Tests (`test_frontend_node.py`):**
   - 59 passed in 5.37s.
3. **Beispieltest an echten Daten (`fotobuch-fotobuch-sebastian-001`):**
   - Generierte Anlass-Geschichte:
     > *„Das ist die Geschichte zu unserem Anlass „Fotobuch Sebastian · Umschlag – Unser“. Dieser Moment ist auf einem Foto festgehalten. Auf dem Foto bin ich zusammen mit Matthias Wenck zu sehen. Ein Erwachsener liegt drinnen und spielt mit einem kleinen Baby, das daneben liegt. Er schneidet spielerisch Grimassen, während das Baby aufmerksam zuschaut. Die Umgebung ist gemütlich und sanft beleuchtet. Das ist das Titelbild meines Fotobuchs: Mein Papa und ich. Wie alt ich da war, bin ich mir nicht sicher. Ich nicht, da war ich irgendwo auf Papas Bauch, irgendwo auf dem Sofa oder im Bett. Ich müsste da ungefähr so ein paar Wochen alt, höchstens ein paar Monate alt. Eine wertvolle Erinnerung, die für immer bleibt.“*
   - Die Bildanalyse ist vollständig eingedeutscht integriert; die Notiz wird direkt als Sebastians persönlicher Gedanke weitererzählt (kein Zitat).
