"""Server-Protokoll (To-do Punkt 16, 18.10.2026): schreiben, lesen, anzeigen.

Wunsch Sebastian: „Früher war es so, dass in Termux der Server gesteuert wurde
und ich den Verlauf sehen konnte … Das ist nicht mehr möglich." Ursache: der
Server läuft abgekoppelt, seine Ausgaben landeten nirgends.

Geprüft werden drei Dinge getrennt:
1. **Lesen** (``app.services.protokoll.protokoll_lesen``) — letzte Zeilen,
   Kappung, ehrliche Meldungen, wirft nie.
2. **Schreiben** (``einrichten``) — nur mit gesetztem Pfad, mit Zeitstempel,
   Rotation, idempotent; ohne Pfad entsteht KEINE Datei.
3. **Weg** — die Route ``GET /api/system/protokoll`` (Schutz wie beim Update),
   der Startweg (``termux/server-protokoll.sh``, eingebunden von
   ``termux/backend-starten.sh``) und die Oberfläche (index.html/app.js/style.css).

Alles offline, nur erfundene Pfade und Zeilen; keine echten Personendaten,
kein Netz, kein Gerät.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.router import auth
from app.services import protokoll as server_protokoll

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
TERMUX = REPO / "termux"
START_SCRIPT = TERMUX / "backend-starten.sh"
PROTOKOLL_SCRIPT = TERMUX / "server-protokoll.sh"
API_KEY = "Attrappe-Protokoll-Schluessel-0815"


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _von_herkunft(herkunft: str):
    """ASGI-Hülle: setzt die Gegenstelle der Verbindung (wie in test_system_update)."""
    async def app_mit_client(scope, receive, send):
        neuer_scope = dict(scope)
        neuer_scope["client"] = (herkunft, 45321)
        await app(neuer_scope, receive, send)

    return app_mit_client


@pytest.fixture(autouse=True)
def _auth_zustand_sauber():
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()
    yield
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()


@pytest.fixture(autouse=True)
def _protokoll_handler_entfernen():
    """Der Protokoll-Anhang ist ein globaler Logging-Zustand — danach abräumen."""
    def _abraeumen():
        for name in server_protokoll.LOGGER_NAMEN:
            logger = logging.getLogger(name)
            for handler in list(logger.handlers):
                if getattr(handler, "_agent_protokoll", False):
                    logger.removeHandler(handler)
                    handler.close()

    _abraeumen()
    yield
    _abraeumen()


def _logdatei(tmp_path: Path, inhalt: str = "") -> Path:
    datei = tmp_path / "agent-server.log"
    datei.write_text(inhalt, encoding="utf-8")
    return datei


# ── 1. Lesen ────────────────────────────────────────────────────────────────

def test_fehlende_datei_wird_ehrlich_gemeldet_und_wirft_nicht(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "gibtsnicht.log"))

    stand = server_protokoll.protokoll_lesen()

    assert stand["vorhanden"] is False
    assert stand["zeilen"] == []
    assert stand["eingeschaltet"] is True
    assert "Kein Protokoll vorhanden" in stand["hinweis"]
    assert "termux/backend-starten.sh" in stand["hinweis"]


def test_letzte_zeilen_werden_gelesen_und_gezaehlt(tmp_path):
    datei = _logdatei(tmp_path, "\n".join(f"2026-10-18 10:00:0{i} INFO app: Zeile {i}"
                                          for i in range(5)) + "\n")

    stand = server_protokoll.protokoll_lesen(3, pfad=datei)

    assert stand["vorhanden"] is True
    assert len(stand["zeilen"]) == 3
    assert stand["zeilen"][-1].endswith("Zeile 4")
    assert stand["zeilen"][0].endswith("Zeile 2")
    assert stand["groesse"] == datei.stat().st_size
    assert stand["gekappt"] is False


def test_grosse_datei_wird_nur_am_ende_gelesen_und_die_angeschnittene_zeile_faellt_weg(tmp_path):
    lang = "\n".join("A" * 200 for _ in range(2000)) + "\n"
    datei = _logdatei(tmp_path, lang)

    stand = server_protokoll.protokoll_lesen(5, pfad=datei, max_bytes=1024)

    assert stand["gekappt"] is True
    assert len(stand["zeilen"]) == 5
    # Keine halbe Zeile: jede gelieferte Zeile ist vollstaendig (200 Zeichen).
    assert all(len(z) == 200 for z in stand["zeilen"])


def test_farbschluessel_des_servers_stehen_nicht_in_der_anzeige(tmp_path):
    datei = _logdatei(tmp_path, "\x1b[32mINFO\x1b[0m: Server läuft\n")

    stand = server_protokoll.protokoll_lesen(pfad=datei)

    assert stand["zeilen"] == ["INFO: Server läuft"]
    assert "\x1b" not in "".join(stand["zeilen"])


def test_leere_datei_nennt_den_grund(tmp_path):
    datei = _logdatei(tmp_path, "")

    stand = server_protokoll.protokoll_lesen(pfad=datei)

    assert stand["vorhanden"] is True
    assert stand["zeilen"] == []
    assert "leer" in stand["hinweis"]


def test_datei_ohne_protokoll_startweg_ist_kein_widerspruch(tmp_path, monkeypatch):
    """Datei liegt da, dieser Start schreibt aber nicht — das wird gesagt."""
    monkeypatch.delenv("AGENT_SERVER_PROTOKOLL", raising=False)
    datei = _logdatei(tmp_path, "alte Zeile\n")

    stand = server_protokoll.protokoll_lesen(pfad=datei)

    assert stand["eingeschaltet"] is False
    assert stand["zeilen"] == ["alte Zeile"]
    assert "nicht eingeschaltet" in stand["hinweis"]


def test_zeilenzahl_wird_begrenzt_und_unsinn_abgefangen(tmp_path):
    datei = _logdatei(tmp_path, "\n".join(f"Z{i}" for i in range(20)) + "\n")

    assert len(server_protokoll.protokoll_lesen(0, pfad=datei)["zeilen"]) == 1
    assert len(server_protokoll.protokoll_lesen("quatsch", pfad=datei)["zeilen"]) == 20
    assert len(server_protokoll.protokoll_lesen(99999, pfad=datei)["zeilen"]) == 20


def test_pfad_kommt_aus_der_umgebung_sonst_aus_dem_heimverzeichnis(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "meine.log"))
    assert server_protokoll.protokoll_pfad() == tmp_path / "meine.log"

    monkeypatch.delenv("AGENT_SERVER_PROTOKOLL", raising=False)
    assert server_protokoll.protokoll_pfad().name == "agent-server.log"
    assert server_protokoll.eingeschaltet() is False


# ── 2. Schreiben ────────────────────────────────────────────────────────────

def test_ohne_startweg_entsteht_keine_datei(tmp_path, monkeypatch):
    """Ohne Pfad in der Umgebung wird NICHTS angelegt — kein stiller Schreibzugriff."""
    monkeypatch.delenv("AGENT_SERVER_PROTOKOLL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert server_protokoll.einrichten() is None
    assert list(tmp_path.iterdir()) == []


def test_einrichten_schreibt_zeitstempel_und_ist_idempotent(tmp_path, monkeypatch):
    datei = tmp_path / "protokoll" / "agent-server.log"
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(datei))

    assert server_protokoll.einrichten() == datei
    logging.getLogger("app.test").info("Erste Zeile aus dem Server")
    assert server_protokoll.einrichten() == datei        # zweiter Start
    logging.getLogger("app.test").warning("Zweite Zeile aus dem Server")

    for handler in logging.getLogger("").handlers + logging.getLogger("uvicorn.access").handlers:
        handler.flush()

    text = datei.read_text(encoding="utf-8")
    assert "Erste Zeile aus dem Server" in text
    assert "Zweite Zeile aus dem Server" in text
    # Zeitstempel im Kopf jeder Zeile (die Rotation kommt aus der Standardbibliothek).
    assert re.search(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO app\.test: Erste Zeile",
                     text, re.M)
    # Genau ein Protokoll-Anhang je Loggername — der zweite Aufruf haengt nichts dazu.
    for name in server_protokoll.LOGGER_NAMEN:
        anhaenge = [h for h in logging.getLogger(name).handlers
                    if getattr(h, "_agent_protokoll", False)]
        assert len(anhaenge) == 1, name


def test_rotation_ist_eingestellt(tmp_path, monkeypatch):
    datei = tmp_path / "agent-server.log"
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(datei))
    server_protokoll.einrichten()

    (handler,) = [h for h in logging.getLogger("").handlers
                  if getattr(h, "_agent_protokoll", False)]

    assert handler.maxBytes == server_protokoll.MAX_BYTES
    assert handler.backupCount == server_protokoll.SICHERUNGEN
    assert server_protokoll.MAX_BYTES <= 1024 * 1024        # waechst nicht endlos


# ── 3. Route ────────────────────────────────────────────────────────────────

def test_route_liefert_die_letzten_zeilen_vom_geraet_selbst(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "agent-server.log"))
    _logdatei(tmp_path, "2026-10-18 09:00:00 INFO start: Server hoch\n"
                        "2026-10-18 09:00:01 INFO uvicorn.access: Zugriff\n")

    antwort = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver").get(
        "/api/system/protokoll?zeilen=10")

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is True
    assert daten["vorhanden"] is True
    assert daten["zeilen"] == [
        "2026-10-18 09:00:00 INFO start: Server hoch",
        "2026-10-18 09:00:01 INFO uvicorn.access: Zugriff",
    ]


def test_route_meldet_fehlendes_protokoll_ehrlich(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "gibtsnicht.log"))

    antwort = TestClient(_von_herkunft("::1"), base_url="http://testserver").get(
        "/api/system/protokoll")

    assert antwort.status_code == 200
    assert antwort.json()["vorhanden"] is False
    assert antwort.json()["zeilen"] == []


def test_route_ist_fuer_fremde_geraete_nur_ueber_https(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "agent-server.log"))
    _logdatei(tmp_path, "eine Zeile\n")

    fremd_ohne_schluessel = TestClient(app, base_url="https://testserver").get(
        "/api/system/protokoll")
    fremd_ueber_http = TestClient(app, base_url="http://testserver").get(
        "/api/system/protokoll", headers={"X-API-Key": API_KEY})
    fremd_ueber_https = TestClient(app, base_url="https://testserver").get(
        "/api/system/protokoll", headers={"X-API-Key": API_KEY})

    assert fremd_ohne_schluessel.status_code == 401
    assert fremd_ueber_http.status_code == 403
    assert fremd_ueber_https.status_code == 200


def test_route_verlangt_keine_anmeldung_vom_geraet_selbst(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "agent-server.log"))
    _logdatei(tmp_path, "eine Zeile\n")

    antwort = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver").get(
        "/api/system/protokoll")

    assert antwort.status_code == 200


def test_loopback_oeffnet_weiterhin_nur_die_system_wege(tmp_path, monkeypatch):
    """Gegenprobe: die Loopback-Ausnahme gilt für /api/system/ — nicht für alle Daten."""
    monkeypatch.setattr(settings, "api_key", API_KEY)
    monkeypatch.setenv("AGENT_SERVER_PROTOKOLL", str(tmp_path / "agent-server.log"))
    client = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver")

    assert client.get("/api/gruppen/personen").status_code == 401
    assert client.get("/api/health").status_code == 200


# ── 4. Startweg (Termux) ────────────────────────────────────────────────────

def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def test_startweg_setzt_den_protokollpfad_aus_dem_heimverzeichnis(tmp_path):
    """Ohne eigenen Pfad gilt ``$HOME/agent-server.log`` — genau eine Zeile Logik."""
    heim = "/tmp/protokoll-test-heim"
    lauf = subprocess.run(
        [_bash(), "-c", '. "$1"; printf "%s" "${AGENT_SERVER_PROTOKOLL:-}"', "_",
         str(PROTOKOLL_SCRIPT).replace("\\", "/")],
        env=dict(os.environ, HOME=heim, MSYS_NO_PATHCONV="1"),
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )

    assert lauf.returncode == 0, lauf.stderr
    assert lauf.stdout == heim + "/agent-server.log"


def test_startweg_laesst_einen_gesetzten_pfad_unveraendert(tmp_path):
    """Ein eigener Pfad (Umgebung) gewinnt — die Tests und ein Sonderaufbau nutzen das."""
    lauf = subprocess.run(
        [_bash(), "-c", '. "$1"; printf "%s" "${AGENT_SERVER_PROTOKOLL:-}"', "_",
         str(PROTOKOLL_SCRIPT).replace("\\", "/")],
        env=dict(os.environ, HOME=str(tmp_path).replace("\\", "/"),
                 AGENT_SERVER_PROTOKOLL="/tmp/woanders.log", MSYS_NO_PATHCONV="1"),
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )

    assert lauf.returncode == 0, lauf.stderr
    assert lauf.stdout == "/tmp/woanders.log"


def test_startstelle_bindet_den_protokollpfad_ein():
    text = START_SCRIPT.read_text(encoding="utf-8")

    assert 'server-protokoll.sh' in text
    assert re.search(r'^\s*\.\s+"\$HIER/server-protokoll\.sh"', text, re.M), \
        "backend-starten.sh bindet server-protokoll.sh nicht ein"
    # Der Serverstart selbst bleibt unveraendert (kein Umleiten der Ausgabe:
    # das wuerde die Abkopplung mit setsid zerstoeren).
    assert 'exec "${BEFEHL[@]}"' in text
    assert '"${_loeser[@]}" "${BEFEHL[@]}"' in text


# ── 5. Oberfläche ───────────────────────────────────────────────────────────

def test_oberflaeche_hat_bereich_knopf_und_route():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    for kennung in ('id="server-protokoll"', 'id="server-protokoll-btn"',
                    'id="server-protokoll-zeilen"', 'id="server-protokoll-stand"',
                    'id="server-protokoll-aktualisieren"', 'id="server-protokoll-neustart"'):
        assert kennung in index, kennung
    # Zugeklappt: der Bereich nimmt dem Chat keinen Platz weg, bis er geoeffnet wird.
    assert re.search(r'id="server-protokoll"[^>]*hidden', index)

    assert "/api/system/protokoll" in app_js
    assert "/api/system/update" in app_js          # „Neu starten"
    assert "serverProtokollStand" in app_js and "serverProtokollZeilenText" in app_js


def test_protokollzeilen_werden_nie_als_html_eingesetzt():
    """Protokollzeilen sind Fremdtext — sie gehen als Text in die Seite, nie als HTML."""
    app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    block = app_js[app_js.index("// ── Server-Protokoll"):]
    block = block[:block.index("// (Kanban-Board")]

    assert ".innerHTML" not in block
    assert "textContent" in block


def test_cache_schluessel_sind_hochgezogen():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")

    js = re.search(r"app\.js\?v=(\d{8}[A-Z]?)", index)
    css = re.search(r"style\.css\?v=(\d{8}[A-Z]?)", index)

    assert js and js.group(1) >= "20261018M", "app.js-Cache nicht hochgezogen"
    assert css and css.group(1) >= "20261018C", "style.css-Cache nicht hochgezogen"


def test_stil_ist_flach_und_hat_einen_eigenen_rollbereich():
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    block = css[css.index(".server-protokoll {"):]

    assert ".server-protokoll" in block
    assert "#server-protokoll-zeilen" in block
    assert "max-height" in block and "overflow: auto" in block
    assert "flex-wrap: wrap" in block            # Werkzeugzeile bricht um (Handybreite)
