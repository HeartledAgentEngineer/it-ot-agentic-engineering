"""Update und Neustart aus der Oberfläche: Route, Schutz und Termux-Ablauf."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.router import auth

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "termux" / "update-und-neustart.sh"
FRONTEND = REPO / "frontend"
API_KEY = "Attrappe-Update-Schluessel-0815"
UPDATE_MELDUNG = "Stand wird geholt, Server startet neu — die Seite ist gleich wieder da."


def _von_herkunft(herkunft: str):
    """ASGI-Hülle: setzt die Gegenstelle der Verbindung auf ``herkunft``.

    Der ``TestClient`` meldet sonst überall ``("testclient", 50000)`` — damit
    ließe sich die Loopback-Regel („vom Gerät selbst") nicht nachstellen.
    Überschrieben wird nur ``scope["client"]``, genau die Größe, die auch
    ``sicherheit.client_ist_loopback`` liest (keine Header).
    """
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


def test_update_startet_skript_abgekoppelt_erst_nach_der_antwort(monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)
    ereignisse = []
    aufrufe = []

    def fake_popen(argumente, **optionen):
        ereignisse.append("skript_gestartet")
        aufrufe.append((argumente, optionen))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    async def antwort_protokoll_app(scope, receive, send):
        async def protokoll_send(nachricht):
            if (nachricht["type"] == "http.response.body"
                    and not nachricht.get("more_body", False)):
                ereignisse.append("antwort_gesendet")
            await send(nachricht)

        await app(scope, receive, protokoll_send)

    client = TestClient(antwort_protokoll_app, base_url="https://testserver")
    antwort = client.post(
        "/api/system/update",
        json={"branch": "unerwuenscht", "command": "unerwuenscht"},
        headers={"X-API-Key": API_KEY},
    )

    assert antwort.status_code == 202
    assert antwort.json() == {"ok": True, "message": UPDATE_MELDUNG}
    assert ereignisse == ["antwort_gesendet", "skript_gestartet"]
    assert len(aufrufe) == 1
    argumente, optionen = aufrufe[0]
    assert argumente == ["bash", str(SCRIPT)]
    assert optionen == {
        "cwd": str(REPO),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "start_new_session": True,
        "close_fds": True,
    }


def test_update_verlangt_anmeldung_und_https(monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)
    aufrufe = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: aufrufe.append((a, k)))

    ohne_anmeldung = TestClient(app, base_url="https://testserver").post(
        "/api/system/update"
    )
    ueber_http = TestClient(app, base_url="http://testserver").post(
        "/api/system/update", headers={"X-API-Key": API_KEY}
    )

    assert ohne_anmeldung.status_code == 401
    assert ueber_http.status_code == 403
    assert aufrufe == []


def test_update_bleibt_ohne_api_key_konfiguration_gesperrt(monkeypatch):
    """Ohne API_KEY bleibt nur noch die HTTPS-Sperre für FREMDE Geräte.

    Die frühere 503-Sperre („erst API_KEY einrichten") ist entfallen — sie war
    für Sebastian der zweite tote Weg zum Update-Knopf. Belegt wird beides:
    fremd über HTTPS läuft (202), fremd über HTTP bleibt gesperrt (403).
    """
    monkeypatch.setattr(settings, "api_key", None)
    aufrufe = []

    def fake_popen(argumente, **optionen):
        aufrufe.append((argumente, optionen))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    ueber_https = TestClient(app, base_url="https://testserver").post(
        "/api/system/update"
    )
    ueber_http = TestClient(app, base_url="http://testserver").post(
        "/api/system/update"
    )

    assert ueber_https.status_code == 202
    assert ueber_http.status_code == 403
    assert len(aufrufe) == 1        # nur der HTTPS-Aufruf hat das Skript gestartet


def test_update_geht_vom_geraet_selbst_immer(monkeypatch):
    """Loopback darf IMMER: ohne HTTPS UND trotz eingerichtetem API_KEY ohne Anmeldung.

    Genau das war der Befund (Sebastian, 16.10.2026): die App am Handy spricht
    den Server über HTTP an, ein API_KEY war gesetzt, der Knopf war tot.
    """
    monkeypatch.setattr(settings, "api_key", API_KEY)
    aufrufe = []

    def fake_popen(argumente, **optionen):
        aufrufe.append((argumente, optionen))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    client = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver")
    antwort = client.post("/api/system/update")      # kein Key, kein Cookie, kein HTTPS

    assert antwort.status_code == 202
    assert antwort.json() == {"ok": True, "message": UPDATE_MELDUNG}
    assert len(aufrufe) == 1
    assert aufrufe[0][0] == ["bash", str(SCRIPT)]


def test_update_geht_vom_geraet_selbst_auch_ueber_ipv6(monkeypatch):
    """Dasselbe für IPv6-Loopback (::1) — ohne API_KEY-Konfiguration."""
    monkeypatch.setattr(settings, "api_key", None)
    aufrufe = []

    def fake_popen(argumente, **optionen):
        aufrufe.append((argumente, optionen))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    antwort = TestClient(_von_herkunft("::1"), base_url="http://testserver").post(
        "/api/system/update"
    )

    assert antwort.status_code == 202
    assert len(aufrufe) == 1


def test_loopback_oeffnet_nur_den_update_weg(monkeypatch):
    """Gegenprobe: die Loopback-Ausnahme gilt NUR für /api/system/ — nicht für alle Daten."""
    monkeypatch.setattr(settings, "api_key", API_KEY)
    client = TestClient(_von_herkunft("127.0.0.1"), base_url="http://testserver")

    assert client.get("/api/gruppen/personen").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_update_akzeptiert_das_gueltige_sitzungscookie(monkeypatch):
    monkeypatch.setattr(settings, "api_key", API_KEY)
    aufrufe = []

    def fake_popen(argumente, **optionen):
        aufrufe.append((argumente, optionen))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    client = TestClient(app, base_url="https://testserver")
    anmeldung = client.post("/api/auth/anmelden", json={"passwort": API_KEY})
    antwort = client.post("/api/system/update")

    assert anmeldung.status_code == 200
    assert antwort.status_code == 202
    assert len(aufrufe) == 1


def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def _posix(pfad: Path) -> str:
    return str(pfad).replace("\\", "/")


def _script_sandbox(tmp_path: Path, pull_exit: int):
    projekt = tmp_path / "projekt"
    termux = projekt / "termux"
    termux.mkdir(parents=True)
    (projekt / "backend").mkdir()
    skript = termux / SCRIPT.name
    skript.write_bytes(SCRIPT.read_bytes())

    events = tmp_path / "events.log"
    stopp = termux / "backend-beenden.sh"
    stopp.write_bytes(
        b'#!/bin/sh\nprintf "backend-beenden\\n" >> "$EVENTS"\nexit 0\n'
    )

    heim = tmp_path / "home"
    (heim / "storage" / "downloads").mkdir(parents=True)
    ensure = heim / "agent-ensure.sh"
    ensure.write_bytes(
        b'#!/bin/sh\nprintf "agent-ensure\\n" >> "$EVENTS"\nexit 0\n'
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_bytes(
        b'#!/bin/sh\nprintf "git %s\\n" "$*" >> "$EVENTS"\n'
        b'printf "simulierter Pull-Grund\\n" >&2\n'
        b'exit "$GIT_EXIT"\n'
    )
    for pfad in (stopp, ensure, git):
        pfad.chmod(0o755)

    umgebung = dict(
        os.environ,
        HOME=_posix(heim),
        EVENTS=_posix(events),
        GIT_EXIT=str(pull_exit),
        PATH=_posix(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        MSYS_NO_PATHCONV="1",
        MSYS2_ARG_CONV_EXCL="*",
    )
    return projekt, skript, heim, events, umgebung


def _run_script(tmp_path: Path, pull_exit: int):
    projekt, skript, heim, events, umgebung = _script_sandbox(tmp_path, pull_exit)
    lauf = subprocess.run(
        [_bash(), _posix(skript)],
        cwd=projekt,
        env=umgebung,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    log = heim / "storage" / "downloads" / "hermes_diag" / "update-und-neustart.log"
    return lauf, events, log


def test_pull_fehler_bricht_ab_und_protokolliert_den_grund(tmp_path):
    lauf, events, log = _run_script(tmp_path, pull_exit=7)

    assert lauf.returncode == 7, lauf.stdout + lauf.stderr
    assert events.read_text(encoding="utf-8").splitlines() == ["git pull --ff-only"]
    protokoll = log.read_text(encoding="utf-8")
    assert "simulierter Pull-Grund" in protokoll
    assert "git pull --ff-only fehlgeschlagen (Exit 7)" in protokoll
    assert "Server nicht beendet und nicht neu gestartet" in protokoll


def test_erfolgreicher_pull_beendet_dann_startet_das_backend(tmp_path):
    lauf, events, log = _run_script(tmp_path, pull_exit=0)

    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert events.read_text(encoding="utf-8").splitlines() == [
        "git pull --ff-only",
        "backend-beenden",
        "agent-ensure",
    ]
    protokoll = log.read_text(encoding="utf-8")
    assert "Git-Pull erfolgreich" in protokoll
    assert "Backend beendet" in protokoll


def test_frontend_hat_update_knopf_rueckmeldung_und_neuen_cache_stand():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")

    assert 'id="system-update-btn"' in index
    assert 'id="system-update-status"' in index
    assert "/api/system/update" in app_js
    assert UPDATE_MELDUNG in app_js
    # Der Cache-Schluessel muss beim Frontend-Schritt hochgezogen werden (der
    # Update-Knopf darf kein altes app.js ausliefern) — geprueft wird deshalb
    # "vorhanden UND mindestens der Stand 20261016", nicht ein fester Wert:
    # ein fest verdrahteter Wert wurde bei jeder Erhoehung rot (Befund
    # 18.10.2026, Cache-Schritt auf 20261018I bei Schritt E des Rahmeneditors).
    treffer = re.search(r"app\.js\?v=(\d{8}[A-Z]?)", index)
    assert treffer, "index.html laedt app.js ohne Cache-Schluessel"
    assert treffer.group(1) >= "20261016", (
        f"Cache-Schluessel zu alt: {treffer.group(1)} — beim Frontend-Schritt hochziehen"
    )
