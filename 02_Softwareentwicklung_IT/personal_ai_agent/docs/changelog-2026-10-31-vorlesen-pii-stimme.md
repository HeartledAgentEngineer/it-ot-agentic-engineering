# Änderungsprotokoll 31.10.2026 — Vorlesen & PII-Shield: Natürliche Cloud-Stimme, Text-Glättung und PII-Maskierung

## Kontext & Problemstellung
1. **TTS-Stimmenauswahl in `erzaehlen.js`:**
   In `frontend/erzaehlen.js` prüfte `vorlesenText(sprech)` bisher `window.speechSynthesis` *zuerst*. Auf Android/Chrome (Xiaomi Pad 5 / Motorola Edge 50) ist `speechSynthesis` vorhanden, sodass die Funktion immer abfing und die monotone, abgehackte Systemstimme abspielte, statt der natürlichen Klaus-Stimme (`/api/speak` über Edge-TTS).
2. **Fragmentarische Vorlesetexte:**
   Beim Vorlesen von Geschichten und Ereignissen las das System UI-Hinweise wie `"12 Bilder · Antippen öffnet ein Bild einzeln"` wörtlich vor, und Aufzählungen wie `"Auf diesem Bild: Sebastian und Leon."` klangen nach Rohdaten statt nach einem fließenden Tagebucheintrag.
3. **Datenschutz bei Textglättung (`polish_text`):**
   `llm_service.polish_text` schickte Rohtext unmaskiert an Cloud-Modelle (OpenRouter). Klarnamen und private Daten wurden vor dem LLM-Aufruf nicht geschützt.

---

## Änderungen

### 1. Frontend (`frontend/erzaehlen.js`)
- **Vorlese-Priorisierung umgekehrt:**
  `vorlesenText(sprech)` versucht zuerst `POST /api/speak` (Edge-TTS Klaus). Erst wenn der Server nicht erreichbar oder offline ist, greift der Fallback auf `window.speechSynthesis`.
- **Neue reine Funktion `erzaehlGlaetteFuerStimme(text)`:**
  - Entfernt visuelle Klick-Hinweise (`"Antippen öffnet ein Bild einzeln"`, `"Antippen zum Vergrößern"`).
  - Formuliert fragmentarische Zähler um: `"12 Bilder"` → `"Insgesamt 12 Fotos."`, `"1 Bild"` → `"Ein Foto."`.
  - Wandelt Aufzählungen in fließende Sätze: `"Auf diesem Bild: A und B."` → `"Auf diesem Bild sind A und B zu sehen."`, `"Erkannt: Sebastian (5 Bilder)."` → `"Erkannt wurden Sebastian mit 5 Fotos."`.
  - Bereinigt Satzzeichen (`.` statt `·`, keine doppelten Punkte).
- **Cache-Busting:**
  `index.html` und zugehörige Tests auf `erzaehlen.js?v=20261031A` angehoben.

### 2. Backend (`backend/app/services/llm_service.py`)
- **PII-Shield in `polish_text` integriert:**
  - Bindet `PIIShield` deterministisch ein.
  - Pre-Flight-Encoding: Ersetzt bekannte Namen (`bestand.volle`), E-Mails und Telefonnummern durch geschützte Tokens (`[PERSON_01]`, `[EMAIL_01]`, etc.), bevor der Prompt an OpenRouter geht.
  - Re-Substitution: Nach der Modellantwort werden alle Tokens deterministisch wieder in Klarnamen dekodiert.
- **`POLISH_ANWEISUNG` erweitert:**
  - Explizites Verbot in den System-Prompts, Maskierungs-Tokens wie `[PERSON_01]` zu entfernen oder abzuwandeln.

---

## Verifikation & Tests
1. **Frontend-Tests:**
   - `node 02_Softwareentwicklung_IT/personal_ai_agent/frontend/tests/test_erzaehlen.js` → Alle Prüfungen bestanden (Exit 0).
   - `node 02_Softwareentwicklung_IT/personal_ai_agent/frontend/tests/test_erzaehlen_hand_gesichter.js` → Alle Prüfungen bestanden (Exit 0).
   - `node 02_Softwareentwicklung_IT/personal_ai_agent/frontend/tests/test_vorlesen_tabellen.js` → Alle Prüfungen bestanden (Exit 0).
   - `node 02_Softwareentwicklung_IT/personal_ai_agent/frontend/tests/test_sprachaufnahme.js` → Alle Prüfungen bestanden (Exit 0).
2. **Backend-Tests:**
   - `tests/test_spracheingabe.py`: Neuer Test `test_glattung_mit_pii_shield_maskiert_und_stellt_namen_wieder_her` verifiziert, dass Tokens an OpenRouter gesendet und Klarnamen im Rückgabewert rekonstruiert werden.
   - `python tools/gate/tor.py` → Selektiver Lauf von 5 Testdateien (93 Tests) in 18,29 s bestanden (Exit 0).
