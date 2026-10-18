# Update-/Neustart-Knopf: das Gerät selbst darf immer (18.10.2026)

## Befund (Sebastian, 16.10.2026)

Der Knopf war für ihn **nicht benutzbar**. Zwei Sperren in
`backend/app/router/system_update.py` verhinderten den Aufruf:

1. `if not auth._ist_https(request)` → **403**. Seine App am Handy spricht den
   lokalen Server über **HTTP** an.
2. `if not settings.api_key` → **503**. Ohne eingerichteten `API_KEY` (genau der
   Zustand, den er will) war der Knopf dauerhaft tot.

Dazu kam die globale Abhängigkeit `auth.require_api_key`: mit gesetztem
`API_KEY` hätte eine Anfrage vom Gerät ohne Schlüssel/Cookie **401** bekommen —
der Knopf wäre auch dann nicht durchgekommen.

## Verhalten jetzt

- **Das Gerät selbst (Loopback) darf immer.** Als Loopback zählt ausschließlich
  die Gegenstelle der Verbindung (`scope["client"]`, geprüft mit dem
  vorhandenen `sicherheit.client_ist_loopback`: `127.0.0.0/8`, `::1`, auch
  IPv4-abgebildete Adressen). Kein Header wird gelesen — `X-Forwarded-For`
  kann jeder im WLAN frei setzen.
- Für Loopback entfallen **beide** Sperren: HTTP genügt, und es wird **keine
  Anmeldung** verlangt, auch wenn ein `API_KEY` gesetzt ist. Dafür ist die
  Ausnahme in `require_api_key` eng gefasst: nur der Pfad `/api/system/`
  (`LOOPBACK_FREI_PFIXE`), und nur für Loopback.
- **Fremde Geräte** (LAN, Tailscale) bleiben wie bisher gesperrt: ohne
  HTTPS **403**. Der Schutz nach außen ist das Netz plus die Verschlüsselung.
- Die Sperre „erst `API_KEY` einrichten" (503) ist **ganz entfallen**.
- Unverändert: das feste `termux/update-und-neustart.sh` wird als
  Hintergrundaufgabe **nach** der Antwort gestartet, fremde JSON-Felder
  (`branch`, `command`) werden ignoriert, das Skript holt selbst `git pull
  --ff-only` und startet den Server neu.

## Belege

`backend/tests/test_system_update.py` (**10 passed**, Exit 0), neu bzw. geändert:

- `test_update_geht_vom_geraet_selbst_immer`: Loopback `127.0.0.1`, **HTTP**,
  `API_KEY` gesetzt, **kein** Schlüssel und **kein** Cookie → **202**, Skript
  genau einmal mit `["bash", …/update-und-neustart.sh]` gestartet.
- `test_update_geht_vom_geraet_selbst_auch_ueber_ipv6`: dasselbe für `::1`, ohne
  `API_KEY`.
- `test_update_bleibt_ohne_api_key_konfiguration_gesperrt` (umgeschrieben, vorher
  503): fremd über HTTPS → **202**, fremd über HTTP → **403**, gestartet wird nur
  der HTTPS-Aufruf.
- `test_loopback_oeffnet_nur_den_update_weg` (Gegenprobe): Loopback mit
  gesetztem `API_KEY` bekommt auf `/api/gruppen/personen` weiterhin **401**;
  `/api/health` bleibt offen (**200**).
- Unverändert grün: Antwort-vor-Prozessstart, Sitzungscookie, fremd ohne
  Anmeldung → 401, fremd über HTTP mit Schlüssel → 403, Shell-Sandkasten für
  Pull-Fehler und Erfolg, Frontend-Knopf/Cache-Wächter.

**Gegenprobe, dass vorher wirklich nichts ging** (Messung mit den HEAD-Fassungen
von `system_update.py` und `auth.py` in einem Kopie-Ordner außerhalb des Repos):
gegen den alten Stand **3 failed, 1 passed** — `503 == 202` (Sperre ohne
`API_KEY`), `401 == 202` (Sitzungsschicht blockierte `127.0.0.1`), `403 == 202`
(HTTPS-Sperre blockierte `::1`). Die Fähigkeit gab es vorher nachweislich nicht.

## Ehrliche Grenzen

Geprüft sind Route und Schutzschicht über den TestClient mit gestellter
Gegenstelle. Der **echte Durchlauf am Handy** (Knopf drücken → Seite kommt
zurück) ist damit nicht belegt — das bleibt Sebastians Abnahme. Der Knopf
startet unverändert einen Server-Neustart; die Seite ist danach kurz weg.
