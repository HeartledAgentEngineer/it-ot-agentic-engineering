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
- Der Server merkt sich nur den sha256 des Tokens (höchstens 50 Sitzungen, die älteste
  fällt zuerst weg). **Nachtrag 18.10.2026:** Die Sitzungen liegen zusätzlich in
  `settings.sitzungen_datei` (Vorgabe `.sitzungen.json` neben dem Projekt, per
  `.gitignore` draußen) — nur die sha256-Werte samt Ablauf, nie das Cookie selbst.
  Damit **überlebt die Anmeldung den Neustart** des Servers; vorher (nur Speicher,
  wie hier ursprünglich beschrieben) war nach jedem Neustart neu anmelden nötig.
  Siehe `docs/changelog-2026-10-18-sitzung-ueberlebt-neustart.md`.
- `require_api_key` akzeptiert den Header `X-API-Key` **oder** ein gültiges Cookie.
  Abgelaufene Sitzungen werden beim Prüfen entfernt; Cookies über 200 Zeichen werden
  nicht gehasht. **Nachtrag 18.10.2026:** Für den Pfad `/api/system/`
  (Update/Neustart) entfällt die Abhängigkeit, wenn die Anfrage **vom Gerät
  selbst** kommt (Loopback) — siehe
  `docs/changelog-2026-10-18-update-knopf-vom-geraet.md`. Für alle anderen
  `/api`-Pfade gilt die Prüfung unverändert, auch für Loopback.
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

**Rollen (ehrlich, Kaskaden-Matrix vom 14.10.2026, 20:53):** H2 und H3a hat der Thinker
(Claude Opus) selbst umgesetzt. Die Matrix sieht dafür einen Worker vor (Lage 2B: Claude
Sonnet). Als sie kam, war H2 schon größtenteils fertig. Ab H3b setzt ein Sonnet-Subagent um;
der Thinker plant und nimmt ab.

## H3a: Ein Prozess, zwei Zugänge (`backend/serve.py`, 14.10.2026)

- `tls_bereit(ordner)`: `server.crt`, `server.key` **und** `ca.crt` vorhanden und nicht leer.
  Ordner `~/.agent_tls`, im Test über `AGENT_TLS_ORDNER` umleitbar.
- Mit TLS baut `konfigurationen()` zwei `uvicorn.Config` für dasselbe `app`-Objekt:
  - HTTP `127.0.0.1:8080` (Gerät selbst, Loopback für H1);
  - HTTPS `0.0.0.0:8443` mit `server.crt`/`server.key` (Heimnetz, Anmelden H2).
- Ohne TLS gibt es nur HTTP auf `HOST_BIND`, wie bisher. `HOST_BIND` kommt aus der Umgebung;
  die `.env` lesen weiter nur die Startskripte, `serve.py` liest sie nicht.
- **Lifespan nur einmal:** Die App hat eine `lifespan` (Start und Stopp der Hintergrundarbeit).
  Nur der erste Zugang führt sie aus (`lifespan="on"`), der zweite nicht (`"off"`). Der zweite
  startet erst, wenn der erste bereit ist. Kommt der erste nicht hoch, startet der zweite nie.
  Endet ein Zugang, enden alle.
- `proxy_headers=False` an beiden Zugängen: Adresse und Schema kommen nie aus Kopfzeilen
  (H1 prüft die echte Gegenstelle, H2 das echte Schema). `server_header=False`.
- `--reload` gibt es in diesem Modus nicht.
- **Noch nicht eingebunden:** Die Startskripte rufen `serve.py` erst mit H3b auf. Bis dahin
  ändert sich am Handy nichts.

**Tests** `backend/tests/test_serve.py` (16):
- zwei Zugänge mit allen drei Dateien;
- je fehlende und je leere Datei nur HTTP auf `HOST_BIND`;
- nur der TLS-Zugang lauscht im Netz;
- `proxy_headers` aus, Lifespan `on`/`off`;
- Ordner und `HOST_BIND` aus der Umgebung;
- Zusammenspiel mit Attrappen (Startreihenfolge, gemeinsames Ende, erster kaputt);
- **echter Lauf:** zwei uvicorn-Server in einem Prozess mit einer Mini-App und einem im Test
  erzeugten Zertifikat für `127.0.0.1`. HTTP und HTTPS antworten (HTTPS geprüft gegen die
  übergebene CA), die Lifespan läuft genau einmal.

## H3b: Ein Start, ein Stopp, Umstellung HTTP -> HTTPS (14.10.2026)

Grundlage: Auftrag `.hermes/plans/2026-10-14_https-h3b-auftrag.md`, Plan H3 (Fassung 6).
Umgesetzt vom Worker (Claude Sonnet); der Thinker nimmt ab und committet. Nicht committet.

### Port aus der Umgebung (`backend/serve.py`)
- Neu `port_http_lesen()`: `PORT` aus der Umgebung, Standard 8080. Ein unbrauchbarer Wert
  (keine Zahl, außerhalb 1-65535, oder gleich dem HTTPS-Port 8443) fällt auf 8080 zurück,
  statt den Start zu verhindern.
- `konfigurationen(..., port_http=None)` nimmt diesen Port für den HTTP-Zugang (mit Zertifikat
  auf `127.0.0.1`, sonst auf `HOST_BIND`). HTTPS bleibt fest 8443. Die Startmeldung nennt die
  tatsächlichen Ports.

### `termux/backend-starten.sh` - die einzige Startstelle
- Liest `PORT` und `HOST_BIND` gezielt aus `backend/.env` (dasselbe `grep`-Muster wie vorher,
  sonst wird nichts aus der Datei gelesen oder ausgegeben) und exportiert beide. Der Wert aus
  der `.env` gilt vor einem schon gesetzten `PORT`; ohne beides 8080 bzw. `0.0.0.0`. Eine
  nicht numerische Portangabe fällt mit einer Meldung auf 8080 zurück.
- `tls_bereit`: `server.crt`, `server.key` und `ca.crt` in `${AGENT_TLS_ORDNER:-$HOME/.agent_tls}`,
  jede mit `[ -s ]` (nicht leer) - dieselbe Bedingung wie in `serve.py`. `AGENT_TLS_ORDNER` wird
  exportiert, damit beide denselben Ordner prüfen.
- TLS bereit: `python serve.py` (HTTPS `0.0.0.0:8443`, HTTP nur `127.0.0.1:$PORT`). Sonst
  `python -m uvicorn app.main:app --host "$HOST_BIND" --port "$PORT"` wie bisher.
- Schalter: `--reload` (nur ohne TLS; mit TLS eine Logzeile "wird ignoriert"), `--log DATEI`
  (Ausgabe anhängen), `--abloesen` (`setsid`, sonst `nohup`, `< /dev/null`, Hintergrund; gibt
  die PID aus). **Ohne `--abloesen` ersetzt sich das Skript durch den Server (`exec`)**: Der
  Aufrufer hängt ein `&` an das Skript und hält in `$!` direkt die Server-PID, `kill -0` und
  `wait` (samt Exit-Code) funktionieren wie vorher.
- `--modus-pruefen` startet nichts: Exit 0 = passt, 3 = Umstellung nötig.
  - Fehlt eine der drei Dateien (oder ist eine leer), ist HTTP gewünscht: immer 0, nicht einmal
    `curl` wird gefragt.
  - Sonst 0 nur, wenn `curl -sf --max-time 3 --cacert <ordner>/ca.crt
    https://127.0.0.1:8443/api/health` gelingt (nie `-k`) **und** `ss -tln` den HTTP-Port nur auf
    `127.0.0.1` (oder `[::1]`) zeigt. Jede andere Lauschadresse (`0.0.0.0`, `*`, `[::]`, eine
    WLAN-Adresse) zählt als offen. Fehlt `curl` oder `ss`, lässt sich der Modus nicht belegen:
    Ergebnis 3.

### `termux/backend-beenden.sh` - die einzige Stoppstelle
- Beendet `uvicorn app.main:app`, `python -m uvicorn` und `python serve.py`: erst `pkill -TERM`
  je Muster, nach `BEENDEN_WARTEN_S` (Standard 10 s) `pkill -KILL`.
- Danach Prüfung: Exit 0 nur, wenn kein solcher Prozess mehr läuft **und** `ss -tln` die Ports
  `$PORT` (aus `.env`, Standard 8080) und 8443 frei zeigt. Prozess lebt noch: Exit 1. Port noch
  belegt: Exit 2. Fehlt `ss`, steht ein Hinweis und die Portprüfung entfällt.
- Der Inbox-Daemon (`hermes_inbox_daemon.py`) wird **nicht** beendet; das bleibt bei den
  Aufrufern, die es heute tun.
- `--laeuft-noch` beendet nichts und meldet nur (Exit 0 = es läuft noch eine der drei Arten):
  die Prozessliste steht so nur hier.

### Die vier Startwege und drei Stoppwege
| Datei | Stopp | Start |
|---|---|---|
| `termux/agent-start` (Widget) | `backend-beenden.sh` (vorher `pkill -9` plus Schleife) | `backend-starten.sh &`, ohne Schalter |
| `start-termux.sh` | `backend-beenden.sh` (vorher TERM/KILL-Block) | `backend-starten.sh --reload &` |
| `termux/agent-ensure.sh` | - (beendet nichts, außer in der Umstellung) | `backend-starten.sh --abloesen --reload --log "$LOG"` |
| `termux/neu-start-nach-lauf.sh` | `backend-beenden.sh` (der Daemon-Kill bleibt dort) | `backend-starten.sh --abloesen --log "$LOG"`, ohne `--reload` |

Logziele und Wartelogik (`health_ok`, `agent_antwortet`, Rücksprung zur App, Wartezeit auf
`/api/health`) sind unverändert. `agent-start` meldet zusätzlich auch Exit 143 (SIGTERM aus
`backend-beenden.sh`) als "abgelöst" und schließt die Sitzung wie bei 137, weil der Server jetzt
sanft (TERM) statt hart (`kill -9`) beendet wird.

### Umstellung eines laufenden Servers (`termux/tls-umstellung.sh`)
Alle vier Startwege rufen es nach der Vorbereitung auf; die Logik steht einmal hier.
1. `backend-starten.sh --modus-pruefen`: 0 = nichts zu tun.
2. Bei 3 und **nur wenn tatsächlich ein Server läuft** (`backend-beenden.sh --laeuft-noch`):
   weiter. Läuft keiner, folgt der reguläre Start und wählt den Modus selbst.
3. **Schleifenschutz:** Steht in `backend/hermes_diag/tls_umstellung_gescheitert.txt` dieselbe
   sha256 von `server.crt` und `ca.crt` wie jetzt, gibt es nur eine Logzeile, keinen Versuch.
4. Logzeile "Umstellung HTTP -> HTTPS", **genau einmal** `backend-beenden.sh`.
5. Ohne `--nur-beenden`: `backend-starten.sh` mit den Schaltern des Aufrufers, dann bis zu
   `UMSTELLUNG_WARTEN_S` (Standard 90 s) auf `--modus-pruefen` = 0 warten. Wird es nicht 0 (oder
   misslang das Beenden): kein zweiter Versuch, sondern die Warnungsdatei mit
   `server.crt sha256=...` und `ca.crt sha256=...`, Exit 4. Neue Zertifikatsdateien geben wieder
   genau einen Versuch frei.
- Exit: 0 nichts getan, 10 umgestellt (bei `--nur-beenden`: beendet), 4 gescheitert.
- `agent-ensure.sh`: Die Modusprüfung steht **vor** dem Ausstieg bei laufendem Server (Reihenfolge:
  Vorbereitung, Umstellung, "Serverstart uebersprungen", Start). Meldet die Umstellung 10 oder 4,
  startet die Datei nichts ein zweites Mal.
- `agent-start`, `start-termux.sh` und `neu-start-nach-lauf.sh` beenden den alten Server ohnehin
  vorher selbst und starten ihn danach; dort ruft die Umstellung mit `--nur-beenden` auf und
  greift nur, wenn nach dem Beenden doch noch ein nicht passender Server läuft (etwa ein parallel
  gestarteter Weg). Gestartet wird dann vom Aufrufer.

### Tests
- `backend/tests/test_serve.py`: +3 Funktionen (10 Fälle) für den Port aus der Umgebung.
- Neu `backend/tests/test_backend_start_stopp.py` (57 Fälle): echte Läufe in Git Bash im
  Sandkasten, Attrappen für `python`, `ss`, `curl`, `pgrep`, `pkill`, `setsid`, `nohup`.
  - Start: drei Dateien = `serve.py`; je Datei einzeln fehlend oder leer = `uvicorn`;
    `--reload` nur ohne TLS; `PORT`/`HOST_BIND` aus der `.env`; `--abloesen` (setsid/nohup,
    Log); unbekannter Schalter = Exit 2.
  - `--modus-pruefen`: TLS + curl ok + HTTP nur lokal = 0; curl scheitert, HTTP auf `0.0.0.0`,
    `*`, `[::]`, WLAN-Adresse = 3; ohne vollständiges Zertifikat = 0 ohne `curl`-Aufruf;
    der curl-Aufruf enthält `--cacert` und nie `-k`.
  - Beenden: alle drei Prozessarten, erst TERM dann KILL, Prozess nicht wegzubekommen = Exit 1,
    Port belegt = Exit 2, Port aus der `.env`, der Daemon bleibt unberührt.
  - Übergangstest über `agent-ensure.sh`: HTTP auf `0.0.0.0` läuft, ohne Zertifikat kein
    Neustart, Zertifikate kommen = ein Beenden und ein `serve.py`, zweiter Lauf startet nichts,
    Zertifikat weg = kein Neustart; gescheiterte Umstellung = Warnung mit sha256, weiterer Lauf
    versucht es nicht, neue `ca.crt` (und neues `server.crt`) gibt wieder genau einen Versuch frei;
    Beenden misslingt = Warnung, kein doppelter Start.
  - Echte Läufe von `neu-start-nach-lauf.sh` (mit und ohne Zertifikat).
  - **Wächter:** Außer `backend-starten.sh` und `backend-beenden.sh` enthält keine Datei unter
    `termux/` und kein `start-termux.sh` eine Nicht-Kommentarzeile mit `uvicorn` oder `serve.py`;
    `pkill` nur auf den Inbox-Daemon, kein `kill -9`/`-TERM`. Reihenfolge der Aufrufe in den
    vier Startwegen. `bash -n` und reine LF für alle geänderten Skripte.
- Nachgezogene Alttests (gleiche Aussage, neuer Aufruf als Marker statt `python -m uvicorn ...`
  / `nohup python -m uvicorn`): `test_agent_ensure_app.py` (2), `test_ein_startweg.py` (1),
  `test_pcloud_schluessel_uebernahme.py`, `test_vorlese_schluessel.py`,
  `test_termux_sicherung.py`, `test_uebergabe_uebernehmen.py` (2),
  `test_widget_agent_start.py` (2). `test_datenschutz_waechter.py`: die Bindungsregeln prüfen
  jetzt die eine Startstelle (HOST_BIND-Muster unverändert und genau einmal, Standard
  `0.0.0.0`, `--host "$HOST_BIND"`) und dass die drei Skripte nur noch über sie starten.

### Grenzen
- Am Handy nicht gelaufen: alles gemessen mit Attrappen in Git Bash, kein echter Server, kein
  echtes Zertifikat. Ob `ss` in Termux vorhanden ist, ist offen; ohne `ss` meldet
  `--modus-pruefen` bei gewünschtem TLS immer 3 (einmal Umstellung, danach Schleifenschutz).
- Die Wartezeit-Abfragen von Widget, `start-termux.sh` und App-Weg lesen `PORT` weiter nur aus
  der Umgebung (Standard 8080), nicht aus der `.env`. Steht dort ein anderer Port, startet
  `backend-starten.sh` darauf, die Wartelogik fragt aber 8080.
