# Änderungsprotokoll 31.10.2026 — Live-Voice-Modus, KI-Sprachsteuerung, Datenpflege per Chat & Erzählen-Reparatur

## Kontext & Problemstellung
1. **Live-Nutzung & Vollduplex (Stufe D):**
   Der Router für die Voice-Sessions (`voice_stream.py`) war als Backend-Fundament angelegt, aber noch nicht in `main.py` gemountet. Es fehlte der echte bi-direktionale Audio- und Event-WebSocket (`/api/voice/stream/{session_id}`) für unterbrechbares Streaming (Barge-In) und Zustandssynchronisation.
2. **App-weite Sprachsteuerung („KI-isch"):**
   Befehle zur Navigation (Quiz öffnen, Erzählmodus öffnen, Chat), zum relativen Blättern mit Zahlwörtern („gehe mal fünf Seiten weiter“, „drei Bilder zurück“), zum Auswählen („oberstes Event öffnen und zeig mir das erste Bild“), zum Notizen-Diktat („Notizen hinzufügen ...“) und zum Triggern von KI-Bildgeschichten oder Neu-Vorsortieren wurden nicht als Aktionen verstanden.
3. **Persönliche Daten per Chat ändern (ohne Hermes):**
   Bisher war Tool-Use v1 rein lesend; `faehigkeiten.py` wies das LLM an: *„Sage ehrlich, dass das eine Aufgabe für den Coding-Agenten Hermes ist und dass mehr als Lesen/Suchen/Erklären hier nicht geht“*. Sebastian wünschte ausdrücklich: *„Jegliche Daten möchte ich per Chat ändern können aktuell meint das llm er bräuche Hermes dafür...bitte ändern“*.
4. **Erzählen-Modus Fehlerbehebungen (Standardmäßig sichtbar, Geschichte, Beschreibung):**
   - Im Erzählen-Modus war die CSS-Regel `.erzaehl-privat-sperre { display: flex; }` aktiv, ohne dass ein `[hidden]`-Gegenstück existierte. Dadurch war das Sperr-Overlay („Intimer Inhalt verdeckt · Antippen zum Aufdecken“) auf ausnahmslos jedem Bild permanent sichtbar, das Bild durch `backdrop-filter: blur(20px)` unscharf, und der Aufdecken-Knopf wegen `pointer-events: none` nicht anklickbar.
   - Der Bildgeschichten-Aufruf warf einen `ReferenceError: jsonSenden is not defined`, wodurch der Klick auf „✨ Bildgeschichte“ wirkungslos blieb.
   - Die Bildbeschreibung war bei Fotos ohne Vorab-Beschreibung unsichtbar; im Vollbild-Editor kollidierte die Beschreibungsausgabe mit dem Gesichts-Vorschaurahmen.

---

## Änderungen

### 1. Backend-Aktivierung & WebSocket-Stream
- **`backend/app/main.py`:**
  - `voice_stream` importiert und per `app.include_router(voice_stream.router, dependencies=[Depends(auth.require_api_key)])` registriert.
- **`backend/app/router/auth.py`:**
  - `require_api_key` von `Request` auf Starlette `HTTPConnection` verallgemeinert, sodass HTTP- und WebSocket-Anfragen gleichermaßen geschützt sind.
  - Unterstützt Authentifizierung via `X-API-Key`-Header, Session-Cookie oder Query-Parameter (`?key=` / `?token=`).
- **`backend/app/router/voice_stream.py`:**
  - Neuer Endpunkt `POST /api/voice/befehl` zur Intent-Analyse (`BefehlAnalyseRequest`).
  - Neuer WebSocket-Endpunkt `/api/voice/stream/{session_id}` für bi-direktionalen Live-Audio-Transfer (PCM-Chunks), VAD/Barge-In-Signale (`interrupted`) und strukturierte Befehlsrückgabe (`befehl_ergebnis`).

### 2. Sprachbefehl-Service (`backend/app/services/sprachbefehl_service.py`)
- Robuste Erkennung deutscher Sprachbefehle:
  - **Navigation:** `quiz_oeffnen` („Öffne das Quiz“, „Gruppen-Quiz“), `erzaehlen_oeffnen` („Öffne den Erzählmodus“, „Diashow“), `chat_oeffnen` („Zurück zum Chat“).
  - **Blättern:** `blaettern` mit Ziffern und Zahlwörtern („gehe mal fünf Seiten weiter“ -> `vor`, 5; „drei Bilder zurück“ -> `zurueck`, 3).
  - **Auswahl:** `event_oeffnen` („oberstes Event / Anlass öffnen“ -> Index 0), `bild_oeffnen` („zeig mir das erste Bild“ -> Index 0).
  - **Mehrschritt-Befehle:** Verknüpfung mit „und / danach / anschließend“ (z. B. „öffne das oberste Event oder den obersten Anlass und zeig mir das erste Bild“ erzeugt sequentiell `event_oeffnen` gefolgt von `bild_oeffnen`).
  - **Aktionen:** `notiz_hinzufuegen` (extrahiert Notizinhalt unter Beibehaltung der Groß-/Kleinschreibung), `geschichte_erzaehlen` („Erzähl mir von da jetzt die Geschichte“), `neu_vorsortieren` („Neu vorsortieren“), `speichern` („speichern“).
  - **Konversations-Fallback:** Reine Fragen („Wer ist auf diesem Bild zu sehen?“) werden als `ist_befehl: false` belassen.

### 3. Datenänderung per Chat ohne Hermes
- **`backend/app/services/werkzeuge.py`:**
  - 4 neue Werkzeuge hinzugefügt (Register jetzt 15 Werkzeuge):
    1. `erinnerung_speichern`: Legt Fakten/Erinnerungen im ChromaDB-Gedächtnis an.
    2. `erinnerung_loeschen`: Löscht Fakten/Erinnerungen aus dem Gedächtnis.
    3. `person_profil_aendern`: Ändert Beziehungen, Rollen, Vor-/Nachnamen und Notizen zu Personen im Katalog.
    4. `notiz_speichern`: Speichert Geschichten und Bildnotizen an Ereignissen/Fotos.
  - `SYSTEM_HINWEIS` und Selbstbild angewiesen, persönliche Daten des Nutzers direkt per Chat-Werkzeugen zu pflegen und dafür niemals auf Hermes zu verweisen.
- **`backend/app/services/faehigkeiten.py`:**
  - `FAEHIGKEITEN["kann"]` um `daten_aendern` erweitert.
  - `stoesst_an_grenze`: Signale persönlicher Datenpflege (Notiz, Erinnerung, Profil, Beziehung etc.) von der Hermes-Grenzprüfung ausgenommen.
- **`backend/app/services/auftrags_erkennung.py`:**
  - Sätze zur Datenpflege werden nicht mehr als Coding-Aufträge für Hermes klassifiziert.

### 4. Erzählen-Modus & Layout-Reparaturen
- **`frontend/style.css`:**
  - `.erzaehl-privat-sperre[hidden] { display: none !important; }` ergänzt: Behebt das permanente, unschließbare Sperr-Overlay auf allen Bildern.
  - `.erzaehl-privat-sperre * { pointer-events: auto; }`: Der Aufdecken-Knopf reagiert nun auf Klicks und Touches.
- **`frontend/erzaehlen.js`:**
  - `jsonSenden(pfad, koerper)` implementiert (POST-JSON-Helper): Behebt den `ReferenceError` beim Generieren von Bildgeschichten und Speichern von Beschreibungen.
  - Standardmäßig sichtbar: Bei `!privat` wird `sperreEl.style.display = 'none'` gesetzt und der Blur entfernt.
  - Bildbeschreibung: `bildInfoAnzeigen` zeigt im Einzelbild immer den Beschreibungsstatus an (bei leerem Text: `Keine Bildbeschreibung hinterlegt.` in dezenter Schrift). Klick auf `📝 Beschreibung` scrollt den Editor sanft ins Blickfeld und fokussiert das Textfeld.
- **`frontend/app.js` (Personen-Editor):**
  - Kollisionsschutz: Die feste Bildbeschreibungs-Box im Vollbild-Editor wurde nach oben (`top: 60px`) verlegt, damit sie nicht mehr mit den Gesichts-Vorschaurahmen am unteren Bildschirmrand kollidiert.
  - Beim Öffnen des Beschreibungs-Editors wird die Hintergrund-Box automatisch ausgeblendet.
- **Cache-Busting:**
  - `index.html`, `test_erzaehlen.js` und `test_erzaehlen_hand_gesichter.js` auf `?v=20261031B` angehoben.

---

## Verifikation & Tests
1. **`tests/test_daten_aendern_werkzeuge.py` (neu, 5 Tests):**
   - Prüft Registrierung aller 4 Datenpflege-Tools, Ausführung von `notiz_speichern` und `person_profil_aendern`, sowie Ausnahme von `stoesst_an_grenze` und `ist_auftrag` (Exit 0).
2. **`tests/test_sprachbefehle.py` (neu, 10 Tests):**
   - Prüft alle vom Nutzer genannten Mustersätze auf exakte Aktions- und Parameter-Extraktion (Exit 0).
3. **`tests/test_voice_session.py` (erweitert, 9 Tests):**
   - Prüft REST-Endpunkt `/api/voice/befehl` und WebSocket-Stream `/api/voice/stream/{session_id}` (Exit 0).
4. **`frontend/tests/test_bild_editor_b5_privat.js`:**
   - Selektive Erkennung und Entsperr-Logik (Exit 0).
5. **`frontend/tests/test_erzaehlen.js` & `test_erzaehlen_hand_gesichter.js`:**
   - 100% grün mit `v=20261031B` (Exit 0).
6. **Tor-Prüflauf (`tools/gate/tor.py`):**
   - 126 Tests bestanden in 37.85s (Exit 0).
