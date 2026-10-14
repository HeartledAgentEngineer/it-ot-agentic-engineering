# 14.10.2026 – Verschlüsselter Zugang im Heim-WLAN (HTTPS-Plan)

Plan: `.hermes/plans/2026-10-14_https-heimnetz.md`, Fassung 6, Codex FREI nach 6 Runden.

Ziel: Sebastian bedient die App vom PC und vom Tablet im eigenen WLAN, verschlüsselt und
mit Anmeldung über Bitwarden. Der API-Schlüssel landet dabei nicht mehr im Klartext auf
fremden Geräten.

## H1 – Schlüssel nur noch an das Gerät selbst

**Befund vorher:**
- Der Server setzte den API-Schlüssel in jede ausgelieferte `index.html` und
  `hermes_status.html` ein (Meta-Feld `agent-schluessel`, seit P0 am 12.10.).
- Damit bekam ihn jedes Gerät, das die Startseite im WLAN abrief. Über unverschlüsseltes HTTP
  konnte ihn zudem jeder im selben Netz mitlesen.

**Jetzt:**
- Neu `sicherheit.client_ist_loopback(scope)`. Sie prüft nur die Gegenstelle der Verbindung
  (`scope["client"]`):
  - Loopback sind `127.0.0.0/8`, `::1` und `::ffff:127.0.0.1`.
  - Kopfzeilen wie `X-Forwarded-For`, `X-Real-IP` oder `Forwarded` werden **nie** gelesen, da
    jeder Client im WLAN sie frei setzen kann.
  - Ein unbekannter oder fehlender Client gilt nicht als Loopback.
- `NoCacheStaticFiles.get_response` setzt den Schlüssel nur noch für Loopback-Clients ein,
  also für die App-Hülle und den Browser am Handy. Alle anderen bekommen die Seite mit
  **leerem** Meta-Feld.
- **Folge:** Vom PC oder Tablet lädt die Oberfläche, aber die API antwortet ohne Anmeldung
  mit 401. Die Anmeldung kommt mit H2. Am Handy ändert sich nichts.

**Tests** in `backend/tests/test_sicherheit_herkunft.py`. Der TestClient bekommt über einen
kleinen ASGI-Mantel eine echte Gegenstelle:
- Loopback (`127.0.0.1`, `127.0.0.2`, `::1`, `::ffff:127.0.0.1`) × 3 Seiten: Schlüssel
  maskiert im Meta-Feld.
- WLAN und unbekannt (`192.168.178.20`, `10.0.0.5`, `172.16.1.1`, `::ffff:192.168.1.2`,
  `fe80::1`, `testclient`, leer) × 3 Seiten: Meta-Feld leer.
- Vier Täuschungs-Kopfzeilen von einem WLAN-Client: kein Schlüssel.
- Fehlende Gegenstelle: kein Schlüssel.
- `test_sicherheit_herkunft.py` und `test_datenschutz_waechter.py` zusammen: 197 passed.

## H2: Anmelden aus dem Heim-WLAN (14.10.2026)

PC und Tablet bekommen seit H1 den Schlüssel nicht mehr in die Startseite. Neu melden sie
sich einmal an und erhalten ein Sitzungs-Cookie.

**Backend** (`backend/app/router/auth.py`):
- Benutzer `agent`, Passwort = API-Schlüssel aus der `.env`. Es gibt kein zweites
  Geheimnis; Bitwarden speichert und füllt beides.
- `POST /api/auth/anmelden` `{passwort}`:
  - ohne `API_KEY` in der `.env` → 409;
  - über HTTP → 403 (nur über HTTPS, maßgeblich ist `scope["scheme"]` der Verbindung,
    keine Kopfzeile);
  - Bremse: nach 5 Fehlversuchen derselben Gegenstelle in 10 Minuten → 429, auch für das
    richtige Passwort;
  - falsches Passwort → 401 (Vergleich in konstanter Zeit);
  - sonst Cookie `agent_sitzung`: `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`,
    30 Tage.
- Der Server merkt sich nur den sha256 des Tokens, im Speicher des Prozesses (höchstens 50
  Sitzungen, die älteste fällt zuerst weg). Nach einem Neustart des Backends ist neu
  anmelden nötig.
- `require_api_key` akzeptiert den Header `X-API-Key` **oder** ein gültiges Cookie.
  Abgelaufene Sitzungen werden beim Prüfen entfernt; Cookies über 200 Zeichen werden
  nicht gehasht.
- `GET /api/auth/sitzung` → `{angemeldet, https, schutz}`, nie den Schlüssel.
- `POST /api/auth/abmelden` beendet die eigene Sitzung und löscht das Cookie.
- Die drei Routen stehen bewusst in der Wächterliste der offenen Routen
  (`test_datenschutz_waechter.py`, jetzt sieben). Die Herkunftsprüfung gilt weiter:
  fremder `Origin` → 403.

**Oberfläche**:
- Neu `frontend/anmelden.js`, geladen **vor** `app.js`. Bei leerem Meta-Feld fragt sie
  `/api/auth/sitzung` ab:
  - angemeldet oder kein Schutz → nichts;
  - über HTTPS → Anmeldefenster mit Formular (`autocomplete="username"` mit Wert
    `agent`, `current-password`), damit Bitwarden es erkennt;
  - über HTTP → nur der Hinweis auf die HTTPS-Adresse, kein Passwortfeld;
  - Abfrage gescheitert → nichts (keine Sperre durch einen Netzfehler).
- Nach erfolgreicher Anmeldung lädt die Seite neu. `app.js` bleibt unverändert: Der Browser
  schickt das Cookie an die eigene Adresse von selbst mit.
- Am Handy selbst (Schlüssel im Meta-Feld) erscheint nie ein Fenster.
- `anmelden.js` steht in `sicherheit.FRONTEND_DATEIEN`. Cache-Bump `style.css` und
  `anmelden.js` auf `?v=20261014B`.

**Abweichung vom Plan:** Ohne `API_KEY` in der `.env` sperrt die Oberfläche nicht
(`schutz: false`), und `anmelden` antwortet 409. Der Plan setzte den Schlüssel voraus; so
bleibt die lokale Entwicklung ohne `.env` wie bisher.

**Tests:**
- `backend/tests/test_anmelden_sitzung.py` (22): Cookie-Merkmale, nur der Hash gespeichert,
  falsch/HTTP/ohne Schlüssel/fremder Origin, eigener HTTPS-Origin, Bremse und Ablauf der
  Bremse, Cookie öffnet `/api`, fremdes/überlanges/abgelaufenes Cookie, Header geht weiter,
  Sitzungsabfrage, Abmelden, Obergrenze 50, Auslieferung von `anmelden.js` und Startseite
  ohne Schlüssel.
- `frontend/tests/test_anmelden.js` (24 Prüfungen): `anmeldenZustand`, `anmeldenMeldung`,
  Verdrahtung in `index.html` (Reihenfolge, Felder, versteckt).
- Sichtprüfung in Handybreite: nur als statische Kopie mit von Hand eingesetztem Stil
  (der Vorschaubereich lädt keine verlinkten Dateien). Echt am Gerät erst nach H3/H4.

**Noch nicht wirksam:** Das Backend spricht noch kein HTTPS (H3), und ein Zertifikat fehlt
(H4). Bis dahin antwortet `anmelden` aus dem WLAN mit 403.
