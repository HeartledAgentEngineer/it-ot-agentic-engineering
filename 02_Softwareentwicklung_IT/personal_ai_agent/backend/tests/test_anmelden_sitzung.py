"""HTTPS-Plan H2 (14.10.2026): Anmelden aus dem Heim-WLAN mit Sitzungs-Cookie.

Seit H1 bekommt nur ein Loopback-Client den Schlüssel in der Startseite. PC und
Tablet im WLAN melden sich über HTTPS an (Benutzer ``agent``, Passwort =
API-Schlüssel) und bekommen ein Cookie ``agent_sitzung`` (Secure, HttpOnly,
SameSite=Strict). Alles offline mit dem TestClient, Schlüssel ist eine Attrappe.
``https://testserver`` setzt ``scope["scheme"] = "https"`` wie uvicorn mit TLS.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.router import auth

ATTRAPPE = "Attrappe-Sitzungs-Schluessel-4711"
GESCHUETZT = "/api/auftraege"


@pytest.fixture(autouse=True)
def sauber():
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()
    yield
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()


@pytest.fixture
def mit_schluessel(monkeypatch):
    monkeypatch.setattr(settings, "api_key", ATTRAPPE)
    return ATTRAPPE


def _https():
    return TestClient(app, base_url="https://testserver")


def _anmelden(client, passwort=ATTRAPPE):
    return client.post("/api/auth/anmelden", json={"passwort": passwort})


# ── Anmelden ───────────────────────────────────────────────────────────────

def test_richtiges_passwort_setzt_sicheres_cookie(mit_schluessel):
    antwort = _anmelden(_https())
    assert antwort.status_code == 200 and antwort.json() == {"ok": True}
    kopf = antwort.headers["set-cookie"].lower()
    assert kopf.startswith(auth.SITZUNG_COOKIE + "=")
    for merkmal in ("secure", "httponly", "samesite=strict", "path=/",
                    f"max-age={int(auth.SITZUNG_DAUER.total_seconds())}"):
        assert merkmal in kopf
    assert ATTRAPPE.lower() not in kopf          # Cookie ist nicht der Schlüssel
    assert len(auth._SITZUNGEN) == 1


def test_gespeichert_wird_nur_der_hash(mit_schluessel):
    client = _https()
    _anmelden(client)
    token = client.cookies.get(auth.SITZUNG_COOKIE)
    assert token and token not in auth._SITZUNGEN
    assert auth._hash(token) in auth._SITZUNGEN


def test_falsches_passwort_401_ohne_cookie(mit_schluessel):
    antwort = _anmelden(_https(), "falsch")
    assert antwort.status_code == 401 and "set-cookie" not in antwort.headers
    assert auth._SITZUNGEN == {}


def test_ueber_http_wird_nicht_angemeldet(mit_schluessel):
    antwort = _anmelden(TestClient(app))
    assert antwort.status_code == 403 and "set-cookie" not in antwort.headers


def test_ohne_schluessel_in_der_env_kein_anmelden(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    assert _anmelden(_https()).status_code == 409


def test_fremder_origin_wird_abgewiesen(mit_schluessel):
    antwort = _https().post("/api/auth/anmelden", json={"passwort": ATTRAPPE},
                            headers={"Origin": "https://boese.example"})
    assert antwort.status_code == 403 and auth._SITZUNGEN == {}


def test_eigener_https_origin_geht_durch(mit_schluessel):
    antwort = _https().post("/api/auth/anmelden", json={"passwort": ATTRAPPE},
                            headers={"Origin": "https://testserver"})
    assert antwort.status_code == 200


def test_ueberlanges_passwort_wird_abgelehnt(mit_schluessel):
    assert _anmelden(_https(), "x" * 501).status_code == 422


# ── Bremse ─────────────────────────────────────────────────────────────────

def test_bremse_nach_fuenf_fehlversuchen(mit_schluessel):
    client = _https()
    for _ in range(auth.BREMSE_VERSUCHE):
        assert _anmelden(client, "falsch").status_code == 401
    # Auch das richtige Passwort wartet jetzt — sonst wäre Raten nur langsamer.
    assert _anmelden(client).status_code == 429
    assert auth._SITZUNGEN == {}


def test_bremse_loest_sich_nach_dem_fenster(mit_schluessel, monkeypatch):
    client = _https()
    for _ in range(auth.BREMSE_VERSUCHE):
        _anmelden(client, "falsch")
    jetzt = auth._jetzt()
    monkeypatch.setattr(auth, "_jetzt", lambda: jetzt + auth.BREMSE_FENSTER + timedelta(seconds=1))
    assert _anmelden(client).status_code == 200


# ── Cookie öffnet die API ──────────────────────────────────────────────────

def test_cookie_oeffnet_geschuetzte_route(mit_schluessel):
    client = _https()
    assert client.get(GESCHUETZT).status_code == 401
    _anmelden(client)
    assert client.get(GESCHUETZT).status_code != 401


def test_fremdes_cookie_oeffnet_nichts(mit_schluessel):
    client = _https()
    client.cookies.set(auth.SITZUNG_COOKIE, "erfunden-" + "a" * 40)
    assert client.get(GESCHUETZT).status_code == 401


def test_ueberlanges_cookie_wird_nicht_gehasht(mit_schluessel):
    client = _https()
    client.cookies.set(auth.SITZUNG_COOKIE, "a" * 300)
    assert client.get(GESCHUETZT).status_code == 401


def test_abgelaufene_sitzung_oeffnet_nichts_und_wird_entfernt(mit_schluessel, monkeypatch):
    client = _https()
    _anmelden(client)
    jetzt = auth._jetzt()
    monkeypatch.setattr(auth, "_jetzt", lambda: jetzt + auth.SITZUNG_DAUER + timedelta(seconds=1))
    assert client.get(GESCHUETZT).status_code == 401
    assert auth._SITZUNGEN == {}


def test_header_schluessel_geht_weiter(mit_schluessel):
    assert TestClient(app).get(GESCHUETZT, headers={"X-API-Key": ATTRAPPE}).status_code != 401


# ── Sitzung abfragen, Abmelden, Obergrenze ─────────────────────────────────

def test_sitzung_meldet_zustand(mit_schluessel):
    client = _https()
    assert client.get("/api/auth/sitzung").json() == {
        "angemeldet": False, "https": True, "schutz": True}
    _anmelden(client)
    assert client.get("/api/auth/sitzung").json()["angemeldet"] is True
    assert TestClient(app).get("/api/auth/sitzung").json()["https"] is False


def test_sitzung_ohne_schluessel_ist_offen(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    assert _https().get("/api/auth/sitzung").json() == {
        "angemeldet": True, "https": True, "schutz": False}


def test_sitzung_gibt_den_schluessel_nicht_heraus(mit_schluessel):
    assert ATTRAPPE not in _https().get("/api/auth/sitzung").text


def test_abmelden_beendet_die_sitzung(mit_schluessel):
    client = _https()
    _anmelden(client)
    antwort = client.post("/api/auth/abmelden")
    assert antwort.status_code == 200 and auth._SITZUNGEN == {}
    assert client.get(GESCHUETZT).status_code == 401


def test_hoechstens_fuenfzig_sitzungen_aelteste_weg(mit_schluessel):
    client = _https()
    _anmelden(client)
    erste = auth._hash(client.cookies.get(auth.SITZUNG_COOKIE))
    for _ in range(auth.SITZUNGEN_MAX):
        _anmelden(_https())
    assert len(auth._SITZUNGEN) == auth.SITZUNGEN_MAX and erste not in auth._SITZUNGEN


# ── Oberfläche wird ausgeliefert ───────────────────────────────────────────

def test_anmelden_js_wird_ausgeliefert():
    antwort = TestClient(app).get("/anmelden.js")
    assert antwort.status_code == 200 and "function anmeldenZustand" in antwort.text


def test_startseite_aus_dem_wlan_hat_anmeldefenster_aber_keinen_schluessel(mit_schluessel):
    antwort = _https().get("/")
    assert antwort.status_code == 200
    assert 'id="anmelden"' in antwort.text and "anmelden.js?v=" in antwort.text
    assert ATTRAPPE not in antwort.text          # testclient ist kein Loopback (H1)
