# Changelog: Anlass-Geschichten & Transparente Vorlese-Fehlermeldungen

**Datum:** 01.11.2026  
**Bereich:** `02_Softwareentwicklung_IT/personal_ai_agent`  
**Autor:** Antigravity (Pair Programming mit Sebastian)

---

## 1. Problemstellung & Nutzeranliegen
1. **Fehlermeldung beim Anhören/Vorlesen transparent machen:**
   Beim Antippen des 🔊-Symbols in der Erzählen-Ansicht (beim Titel oder bei „Notizen und Geschichten“) erschien lediglich die statische Meldung:
   > *„Vorlesen gerade nicht möglich.“*
   Der Nutzer fragte berechtigt:
   > *„Jetzt würde ich mich fragen, warum, und warum dann nicht die Fehlermeldung, warum es nicht möglich ist, da steht.“*
   Ursache: Bei einem Scheitern des `/api/speak`-Aufrufs (z. B. Netzwerk-Timeout, OpenRouter-Quota oder fehlender API-Schlüssel) fing `vorlesenText` den Fehler zwar ab, schluckte ihn jedoch komplett und setzte nach dem Scheitern der Browser-Stimme stets den Blindtext ohne Fehlerursache. Im Backend meldete `_als_mp3` zudem pauschal nur *„Details stehen im Server-Log“*, ohne den eigentlichen Grund zu nennen.
2. **Anlass-Geschichten generieren, vorlesen und optional speichern:**
   Der Nutzer wünschte sich:
   > *„Demnächst will ich Bildergeschichten generieren, aber ich will das Gleiche auch bei den Anlässen haben, Anlass Geschichte erstellen und vorlesen, und dann auch mich entscheiden können, ob ich die Anlass-Geschichte speichern möchte oder nicht. Dann kann ich sie bestimmt auch mal vorlesen, ohne noch mal wieder Tokens für LLM zu bezahlen.“*

---

## 2. Technische Umsetzung

### A. Transparente Vorlese-Fehlerdiagnose (Backend & Frontend)
- **`backend/app/services/llm_service.py`:**
  - `LLMService` merkt sich in `self.letzter_vorlese_fehler` den konkreten Fehlergrund (z. B. `Kein OpenRouter-API-Schlüssel konfiguriert`, `OpenRouter HTTP 402: Insufficient credits`, `Verbindungsfehler: ...`).
- **`backend/app/router/speak.py`:**
  - Bei fehlendem Audio liefert HTTP 502 den konkreten Grund im `detail`-Feld an den Client:
    `Sprachausgabe fehlgeschlagen ({grund}).`
- **`frontend/erzaehlen.js`:**
  - `vorlesenText(sprech)` parst bei `!res.ok` die Serverantwort und extrahiert `errData.detail`.
  - Bei Fehlschlag des Servers und der Browser-Stimme wird die exakte Ursache in `#erzaehl-hinweis` angezeigt (z. B. `Vorlesen nicht möglich (Sprachausgabe fehlgeschlagen (OpenRouter HTTP 402: Insufficient credits). · Browser-Stimme: ...)`).
  - `audioVorabFreischalten()` entsperrt synchron beim Klick neben `AudioContext` auch `window.speechSynthesis.resume()`.

### B. Anlass-Geschichten-Generator (0 Token LLM-Kosten)
- **`backend/app/services/erzaehl_service.py`:**
  - Neue Funktion `anlass_geschichte_generieren(ereignis_kennung, perspektive, notiz, ...)`:
    - Führt Anlasstitel, formatiertes Datum/Zeitraum, beteiligte Personen (via `gruppen_quiz.personen_auf_bildern`), Orte (aus OSM-Zuordnung) und vorhandene Notizen zusammen.
    - Vollständig deterministisch und kostenlos (0 LLM-Tokens).
    - Unterstützt `ich`-Perspektive (*„Das ist die Geschichte zu … Ich erinnere mich gern an diese Zeit … Mit dabei waren …“*) und neutrale `erzaehler`-Sicht (*„Fotodokumentation zum Anlass … Erkannte Beteiligte …“*).
- **`backend/app/router/erzaehlen.py`:**
  - Neuer Endpunkt `POST /api/erzaehlen/anlass-geschichte` mit Eingabemodell `AnlassGeschichteEingabe`.
- **`frontend/index.html` & `frontend/erzaehlen.js`:**
  - Im Anlass-Kopf (`#erzaehl-uebersicht`) Steuerleiste mit `✨ Anlass-Geschichte` und `👤 Ich-Form` (umschaltbar auf `📖 Erzähler`).
  - Beim Antippen von `✨ Anlass-Geschichte`:
    1. Synchrones Entsperren des Web-Audio-Kontexts (`audioVorabFreischalten()`).
    2. Abrufen der Geschichte via `POST /api/erzaehlen/anlass-geschichte`.
    3. Eintragen des Entwurfs in das Textfeld `#erzaehl-text`.
    4. Sofortiges Vorlesen via `vorlesenText(...)`.
    5. Statushinweis: *„Anlass-Geschichte erstellt. Tippe auf 💾 Speichern, wenn du sie dauerhaft behalten möchtest.“*
  - **Volle Entscheidungsfreiheit:** Der Text wird erst dann dauerhaft gespeichert, wenn der Nutzer auf `💾 Speichern` klickt. Wird er gespeichert, steht er dauerhaft als Gruppennotiz bereit und kann jederzeit per 🔊 ohne erneute KI-Kosten angehört werden!

---

## 3. Verifikation
- `tests/test_erzaehlen_ki_geschichte.py`: 7 Tests bestanden (Ich-Form, Erzähler, Route).
- `tor.py`: Selektiver Lauf über alle 6 betroffenen Testdateien (83 passed, 0 failures, Exit-Code 0).
- `test_frontend_node.py`: 59 Tests bestanden (Exit-Code 0).
- `test_erzaehlen.js`: Alle Prüfungen bestanden inkl. Anlass-Geschichte-Verdrahtung (Exit-Code 0).
- `test_erzaehlen_hand_gesichter.js`: Alle Prüfungen bestanden (Exit-Code 0).
- Cache-Version auf `?v=20261101D` angehoben.
