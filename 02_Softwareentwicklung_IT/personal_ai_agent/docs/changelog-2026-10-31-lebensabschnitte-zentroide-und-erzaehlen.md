# Änderungsprotokoll: Lebensabschnitts-Zentroide, Zwillings-Trennung & KI-Bildgeschichten

**Datum:** 31. Oktober 2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Autor:** Antigravity (im Auftrag von Sebastian)  
**Status:** Verifiziert & abgeschlossen (Exit 0)

---

## 1. Kontext & Problemstellung
Sebastian sortiert am Smartphone ca. 30.000 Fotos und Gesichter aus seinem persönlichen Archiv (insb. schwierige Kinderfotos zwischen sich und seinem Zwillingsbruder Julian). Dabei traten mehrere Hürden auf:
1. **Unvollständige Lebensabschnitte:** `lebensabschnitte_service.py` las bisher nur die maximal 8 Vorschaubilder (`beispiele`) je Gruppe. Bei Personen wie Sebastian mit über 1.950 Gesichtern wurden dadurch tausende Fotos und Jahre in den Phasen übersprungen.
2. **Sortierung:** Die Standardansicht stand auf Güte statt auf Zeit, was chronologische Zeitabschnitte unvollständig wirken ließ.
3. **Kachel-Verzögerung:** Wurde ein Gesicht im Foto-Editor manuell einer anderen Person zugeordnet, verblieb es bis zum Neuladen in der Vorschaugruppe.
4. **Zwillings-Verwechslung:** Identische Zwillinge haben eine sehr hohe globale Gesichtsähnlichkeit (Cosinus ~0,78). Ohne genaue zeitliche Phasen-Zentroide und Cannot-Link-Bedingungen (zwei Gesichter auf demselben Foto können nicht derselbe Zwilling sein) ließen sich Kinderfotos schwer automatisiert trennen.
5. **Erzählen-Modus Maskierung & UI-Blockaden:** Fotos wurden fälschlicherweise durch Schlüsselwörter als „Intimer Inhalt verdeckt“ maskiert. Die Zeile „Auf diesem Bild: 1 Person noch ohne Namen“ irritierte. Der Klick auf „📝 Beschreibung“ blieb wirkungslos, da der übergeordnete Container `hidden` war.
6. **Fehlende Bildgeschichten:** Es fehlte eine Möglichkeit, auf Knopfdruck aus Datum, Ort, erkannten Personen, Bildbeschreibung und persönlicher Notiz eine natürliche Geschichte in wählbarer Perspektive (Ich-Form vs. neutrale Erzählersicht) zu generieren und vorzulesen.

---

## 2. Umgesetzte Lösungen

### A. 100 % aller Gesichter & Phasen-Zentroide
* **Vollabdeckung:** `lebensabschnitte_service._alle_gesichter_fuer_person` lädt alle Gesichter direkt aus `gesicht_zuordnung.jsonl` (unter Berücksichtigung von Ausschlüssen und manuellen Zuordnungen).
* **Phasenaufteilung:** `phasen_bilden_jahre` teilt lange Fotozeiträume sauber in Phasen von maximal 5 Jahren auf (z. B. 2008–2012, 2013–2017, 2018–2022, 2023–2026).
* **128-dim Phasen-Zentroide:** Jede Lebensphase berechnet einen normierten Vektormittelwert aus den 128-dimensionalen SFace-Embeddings der zugehörigen Gruppen (`kennungen.json`).
* **Cache-Invalidierung:** `invalidiere_cache()` leert Phasen-, Beziehungs- und Vektor-Caches bei jeder Bestätigung, Umbenennung oder Zuordnung in `gruppen_quiz.py`.

### B. Zwillings-Trennung & Kindheits-Filter
* **Cannot-Link:** Ist ein Zwilling (z. B. Julian) bereits auf demselben Foto erkannt, wird die offene Gruppe automatisch dem anderen Zwilling (Sebastian) zugeordnet (Sicherheit 0,95).
* **Phasen-Differenzierung:** Bei überlappenden Phasen entscheidet der Cosinus-Abstand zum jeweiligen Phasen-Zentroid ($\Delta \ge 0{,}04 \rightarrow$ Sicherheit 0,85). Bei zu geringer Differenz werden ehrlich beide Kandidaten genannt (Sicherheit 0,50).
* **Temporal-Filter:** In Kinderjahren ($< 16$ Jahre) werden zeitliche Abweichungen $> 2$ Jahre streng gefiltert; Abweichungen $> 5$ Jahre werden strikt ausgeschlossen.
* **Knopf „⚡ Neu vorsortieren“:** Ruft `POST /api/gruppen/neu-vorsortieren` auf, leert die Caches und aktualisiert die Vorschlags-Pille am Smartphone.

### C. Sofortige Kachel-Entfernung
* In `app.js` löst `speichereBildCloud` bei Erfolg ein `CustomEvent('bild-rahmen-gespeichert')` aus.
* In `gruppen_quiz.js` entfernt der Event-Listener sofort alle DOM-Kacheln mit der betroffenen `gid`, aktualisiert den Zähler und schaltet weiter, wenn die Karte leer ist.

### D. Erzählen-Modus Bereinigung
* **Privat-Sperre:** `erzaehlBildIstPrivat` maskiert Bilder nicht mehr automatisch anhand von Textmustern; standardmäßig unzensiert („Nicht privat“).
* **Keine Unbenannten-Zeile:** `personenAnzeigen` entfernt im Einzelbild die fragmentarische Zeile „1 Person noch ohne Namen“.
* **Beschreibungsklick repariert:** `erzaehl-beschreibung-toggle-btn` blendet den Container `erzaehl-bild-info` ein und fokussiert das Textfeld.
* **Layout-Entflechtung:** `.erzaehl-info` besitzt `position: relative; z-index: 10`, sodass Face-Canvas und Textboxen sich nicht überlagern.

### E. KI-Bildgeschichten-Generator
* **Backend:** Neuer Endpunkt `POST /api/erzaehlen/ki-geschichte` in `erzaehlen.py` und Dienstfunktion `ki_geschichte_generieren` in `erzaehl_service.py`.
* **Perspektiven:**
  - `ich`: Ich-Form („Ich erinnere mich gut an diesen Moment am 15. Juli 2018 in Hamburg. Auf dem Foto bin ich zusammen mit Matthias zu sehen...“)
  - `erzaehler`: Neutrale Erzählersicht („Eine Aufnahme am 15. Juli 2018 aus Hamburg. Auf diesem Bild sind Sebastian und Matthias zu sehen...“)
* **Frontend:** Knöpfe `✨ Bildgeschichte` und `👤 Ich-Form` (umschaltbar auf `📖 Erzähler`). Das Ergebnis wird in das Notizfeld eingetragen und direkt über Klaus TTS (`/api/speak`) vorgelesen.

---

## 3. Verifikation & Nachweise

Alle Tests laufen über `tools/gate/tor.py` bzw. `node` und schließen mit **Exit-Code 0** ab:
1. `pytest tests/test_bild_editor_b1.py`: **80 passed** in 31,27s
2. `pytest tests/test_lebensabschnitte_service.py`: **14 passed** in 3,28s
3. `pytest tests/test_erzaehlen_ki_geschichte.py`: **4 passed** in 4,49s
4. `pytest tests/test_gruppen_quiz.py`: **92 passed** in 18,45s
5. `pytest tests/test_erzaehlen*.py`: **74 passed** in 22,31s
6. `node frontend/tests/test_bild_editor_b4.js`: **129 passed** (alle 129 Prüfungen bestanden)
7. `node frontend/tests/test_gruppen_quiz.js`: **alle Prüfungen grün**
8. `node frontend/tests/test_erzaehlen.js`: **alle Prüfungen bestanden**
9. `node frontend/tests/test_erzaehlen_hand_gesichter.js`: **alle Prüfungen bestanden**
