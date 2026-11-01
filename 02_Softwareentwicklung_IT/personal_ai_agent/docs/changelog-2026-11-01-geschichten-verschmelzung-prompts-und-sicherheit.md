# Changelog: Geschichten-Verschmelzung, Prompts & Fehler-Maskierung (01.11.2026)

## 1. Anlass & Motivation
* **Organische Geschichten statt Fakten-Staccato:** Sebastian bemängelte den abgehackten, schablonenhaften Klang früherer Fassungen (`[Titel] + [Umfang] + [Personen] + [Bildanalyse] + [Notiz] + [Schluss]`). Bildbeschreibungen und persönliche Erinnerungen sollen wie eine echte, warmherzige Geschichte verschmelzen – melodisch und natürlich zum Zuhören.
* **Prompt & Zusammensetzung:** Bereitstellung eines präzisen System- und User-Prompts für LLMs sowie einer deterministischen Verschmelzungslogik (`verschmelze_geschichte`, 0 Token Kosten) als zuverlässiger Fallback.
* **Datenschutz & Fehler-Maskierung:** OpenRouter liefert bei HTTP 403 (Key-Limit überschritten) im Fehlertext eine Hilfs-URL mit der internen ID des Schlüssels (`https://openrouter.ai/workspaces/default/keys/<hash>`). Diese wurde zuvor unmaskiert an das Frontend durchgereicht.

## 2. Technische Änderungen

### `backend/app/services/erzaehl_service.py`
1. **`GESCHICHTE_SYSTEM_PROMPT` & `erstelle_geschichte_prompt`:**
   * Verbindliche Prompt-Leitplanken für Sprachmodelle:
     * Harmonische Verschmelzung visueller Details mit persönlichen Gedanken.
     * Strikter Verzicht auf Faktenlisten, Aufzählungszeichen und Staccato-Sätze.
     * Verbot von Zitatzeichen oder Labels wie *„Meine Notiz dazu:“*.
     * Echte familiäre Beziehungen statt generischer Rollen (*„Mein Papa Matthias“*, *„ich als kleines Baby“* statt *„Ein Erwachsener“* / *„Ein Baby“*).
2. **`personalisiere_szene(beschreibung, personen, notiz, perspektive)`:**
   * Übersetzt Gemini-Vision-Muster ins Deutsche und personalisiert die Rollen anhand von Beteiligten und Notizinhalt.
   * Erkennt z. B. Papa Matthias Wenck und Sebastian als Baby auf dem Foto und ersetzt generische Beschreibungen durch persönliche Bezüge.
3. **`verschmelze_geschichte(...)`:**
   * Verwebt Metadaten (Titel, Datum, Ort, Begleitpersonen) in einen warmherzigen situativen Rahmen (*„Eine wunderbare Erinnerung an „{titel}“ {datum} in {ort} – festgehalten zusammen mit {personen}.“*).
   * Verknüpft den persönlichen Auftakt der Notiz direkt mit der lebendigen Bildszene (*„Auf dem Foto wird dieser Augenblick lebendig: ...“*).
   * Schließt persönliche Gedanken fließend an und rundet mit einem stimmigen Ausklang ab.
4. **Integration in `ki_geschichte_generieren` & `anlass_geschichte_generieren`:**
   * Beide Generierungspfade nutzen die organische Verschmelzung sowohl für Einzelbilder als auch für gesamte Fotoanlässe.

### `backend/app/services/llm_service.py`
1. **`fehlertext`:**
   * Fängt `key limit`, `limit exceeded` und `credits` ab und gibt eine saubere, verständliche deutsche Statusmeldung zurück.
   * Maskiert URLs mit internen Schlüssel-Hashes generisch (`https://openrouter.ai/settings/keys`).
2. **`speak`:**
   * Fängt `APIStatusError` von OpenRouter ab und setzt `letzter_vorlese_fehler` auf neutrale Klartext-Meldungen ohne sensible IDs oder URLs.

### `backend/tests/test_erzaehlen_ki_geschichte.py`
* Tests auf die neue fließende Verschmelzung und die Personalisierung visueller Bildelemente angepasst.

## 3. Verifikation
* `python tools/gate/tor.py`: **84 passed** in 26.62s (selektiver Best-Practice-Lauf, Exit-Code 0).
* `backend/.venv/Scripts/python.exe -m pytest tests/test_frontend_node.py`: **59 passed** in 28.74s.
* `backend/.venv/Scripts/python.exe -m pytest tests/test_erzaehlen_ki_geschichte.py`: **8 passed** in 3.67s.
