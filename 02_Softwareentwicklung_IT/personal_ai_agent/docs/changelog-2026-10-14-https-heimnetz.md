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
