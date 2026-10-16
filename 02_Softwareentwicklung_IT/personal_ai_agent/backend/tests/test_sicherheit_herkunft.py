"""P0 (12.10.2026): Fremde Webseiten kommen nicht mehr an Schlüssel und Daten.

Befund vorher (TestClient, Attrappen-Schlüssel): ``/api/konfig`` gab den
Schlüssel an jede Herkunft heraus, CORS stand auf ``*`` mit Zugangsdaten, kein
Host- und kein Herkunftscheck, keine Sicherheitskopfzeilen.

Alles offline mit dem TestClient; Schlüssel sind erfundene Attrappen.
``testserver`` als Host erlaubt die gemeinsame ``conftest.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import sicherheit
from app.config import settings
from app.main import app

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
ATTRAPPE = 'Attrappe"<&>schluessel'


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mit_schluessel(monkeypatch):
    monkeypatch.setattr(settings, "api_key", ATTRAPPE)
    return ATTRAPPE


def _client_von(adresse):
    """TestClient, dessen Verbindung von ``adresse`` kommt (``scope["client"]``).
    Der normale TestClient meldet sich als ``testclient`` — kein Loopback."""
    async def mit_gegenstelle(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope, client=(adresse, 50000))
        await app(scope, receive, send)
    return TestClient(mit_gegenstelle)


# ── P0.1 Herkunft ──────────────────────────────────────────────────────────

PRUEFPFADE = [("GET", "/api/health"), ("POST", "/api/auth/token"),
              ("GET", "/health"), ("GET", "/ping"), ("GET", "/status")]


@pytest.mark.parametrize("methode,pfad", PRUEFPFADE)
@pytest.mark.parametrize("herkunft", ["cross-site", "same-site"])
def test_fremde_herkunft_wird_abgewiesen(client, methode, pfad, herkunft):
    antwort = client.request(methode, pfad, headers={"Sec-Fetch-Site": herkunft})
    assert antwort.status_code == 403


@pytest.mark.parametrize("methode,pfad", PRUEFPFADE)
def test_fremder_origin_wird_abgewiesen(client, methode, pfad):
    antwort = client.request(methode, pfad, headers={"Origin": "http://boese.example"})
    assert antwort.status_code == 403


@pytest.mark.parametrize("origin", ["null", "http://testserver:9999",
                                    "https://testserver", "kaputt"])
def test_aehnliche_origins_sind_fremd(client, origin):
    assert client.get("/api/health", headers={"Origin": origin}).status_code == 403


@pytest.mark.parametrize("koepfe", [
    {"Sec-Fetch-Site": "same-origin"},
    {"Sec-Fetch-Site": "none"},
    {},
    {"Origin": "http://testserver"},
    {"Origin": "http://TESTSERVER:80", "Sec-Fetch-Site": "same-origin"},
])
def test_eigene_herkunft_und_werkzeuge_gehen_durch(client, koepfe):
    assert client.get("/api/health", headers=koepfe).status_code == 200


def test_schluessel_wird_weiter_geprueft(client, mit_schluessel):
    ohne = client.get("/api/auftraege", headers={"Sec-Fetch-Site": "same-origin"})
    assert ohne.status_code == 401
    falsch = client.get("/api/auftraege", headers={"X-API-Key": "falsch"})
    assert falsch.status_code == 401


def test_statische_dateien_ohne_herkunftspruefung(client):
    """Bilder/Skripte der eigenen Seite: dort schützt CORP, nicht der 403."""
    antwort = client.get("/icon-192.png", headers={"Sec-Fetch-Site": "cross-site"})
    assert antwort.status_code == 200
    assert antwort.headers["cross-origin-resource-policy"] == "same-origin"


def test_abweisungen_werden_gezaehlt(client):
    vorher = sicherheit.abgewiesen["origin"]
    client.get("/api/health", headers={"Origin": "http://boese.example"})
    assert sicherheit.abgewiesen["origin"] == vorher + 1


def test_selbsttest_zeigt_abweisungen(client):
    client.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"})
    daten = client.get("/api/selbsttest").json()
    assert daten["abgewiesen"]["cross-site"] >= 1


# ── P0.2 Host ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("host", ["boese.example", "boese.example:8080", "",
                                  "[::1", "localhost:abc", "localhost.boese.example"])
def test_fremder_host_wird_abgewiesen(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 400
    assert client.get("/", headers={"Host": host}).status_code == 400


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST.:8080", "127.0.0.1:8080",
                                  "[::1]:8080", "192.168.1.20:8080", "100.64.0.7"])
def test_localhost_und_ip_literale_gehen_durch(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", [
    "100.64.0.0", "100.97.77.126:8080", "100.127.255.255",
    "[::ffff:100.97.77.126]:8080",
])
def test_tailscale_ip_hosts_gehen_durch(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["8.8.8.8", "1.1.1.1"])
def test_oeffentliche_ip_hosts_werden_abgewiesen(client, host):
    assert client.get("/health", headers={"Host": host}).status_code == 400


def test_erlaubte_hosts_wirken_zur_laufzeit(client, monkeypatch):
    name = "mein-handy.tail-attrappe.ts.net"
    assert client.get("/health", headers={"Host": name}).status_code == 400
    monkeypatch.setattr(settings, "erlaubte_hosts", f"testserver, {name.upper()}.")
    assert client.get("/health", headers={"Host": f"{name}:8080"}).status_code == 200


def test_tailscale_fqdn_unter_explizit_configurierter_tailnet_domain(client, monkeypatch):
    monkeypatch.setattr(settings, "erlaubte_hosts", "*.tail-attrappe.ts.net")
    assert client.get("/health", headers={
        "Host": "motorola-edge-50.tail-attrappe.ts.net:8080",
    }).status_code == 200


def test_tailscale_kurzname_wird_exakt_freigegeben(client, monkeypatch):
    monkeypatch.setattr(settings, "erlaubte_hosts", "motorola-edge-50")
    assert client.get("/health", headers={"Host": "motorola-edge-50:8080"}).status_code == 200
    assert client.get("/health", headers={"Host": "anderes-handy"}).status_code == 400


@pytest.mark.parametrize("host", [
    "anderes-tailnet.ts.net",
    "tablet.tail-attrappe.ts.net.evil.example",
    "tablet.ts.net",
])
def test_tailnet_wildcard_erlaubt_keine_fremde_domain_oder_domainwurzel(
        client, monkeypatch, host):
    monkeypatch.setattr(settings, "erlaubte_hosts", "*.tail-attrappe.ts.net")
    assert client.get("/health", headers={"Host": host}).status_code == 400


def test_allgemeiner_ts_net_wildcard_ist_gesperrt(client, monkeypatch):
    monkeypatch.setattr(settings, "erlaubte_hosts", "*.ts.net")
    assert client.get("/health", headers={
        "Host": "motorola-edge-50.tail-attrappe.ts.net",
    }).status_code == 400


def test_leere_hostkonfiguration_erlaubt_keinen_hostnamen(client, monkeypatch):
    monkeypatch.setattr(settings, "erlaubte_hosts", "")
    antwort = client.get("/health", headers={"Host": "motorola-edge-50"})
    assert antwort.status_code == 400


def test_fremder_host_erhaelt_erlaeuterung_im_body_und_log(client, caplog, monkeypatch):
    monkeypatch.setattr(settings, "erlaubte_hosts", "")
    with caplog.at_level("WARNING", logger="app.sicherheit"):
        antwort = client.get("/health", headers={"Host": "boese.example"})
    assert antwort.status_code == 400
    assert "boese.example" in antwort.text
    assert "ERLAUBTE_HOSTS" in antwort.text
    assert "100.64.0.0/10" in antwort.text
    assert "boese.example" in caplog.text
    assert antwort.headers["content-type"].startswith("text/plain")


def test_host_anzeige_haelt_steuerzeichen_aus_der_antwort_heraus():
    anzeige = sicherheit._host_anzeige("boese.example\r\nX-Injected: true")
    assert "boese.example" in anzeige
    assert "\\r\\n" in anzeige
    assert "\r" not in anzeige and "\n" not in anzeige


@pytest.mark.parametrize("roh,erwartet", [
    ("[::1]:8080", ("::1", 8080)),
    ("LocalHost.:80", ("localhost", 80)),
    ("127.0.0.1", ("127.0.0.1", None)),
    ("::1", ("::1", None)),
    ("x:y", None),
    ("[::1]x", None),
    ("", None),
    ("localhost:²", None),     # Codex R2: isdigit() ja, int() nein
    ("[::1]:٨٠", None),        # arabisch-indische Ziffern
])
def test_host_zerlegen(roh, erwartet):
    assert sicherheit.host_zerlegen(roh) == erwartet


def _roh_anfrage(host: bytes):
    """Ruft die Middleware direkt auf (der Testclient sendet nur ASCII-Köpfe)."""
    import asyncio

    gesendet = []

    async def innen(scope, receive, send):  # darf nie erreicht werden
        raise AssertionError("Anfrage kam durch")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(nachricht):
        gesendet.append(nachricht)

    scope = {"type": "http", "method": "GET", "path": "/health", "scheme": "http",
             "headers": [(b"host", host)], "query_string": b"", "http_version": "1.1"}
    asyncio.run(sicherheit.SicherheitsMiddleware(innen)(scope, receive, send))
    return gesendet[0]


@pytest.mark.parametrize("host", [b"localhost:\xb2", b"localhost:\xd9\xa8\xd9\xa0"])
def test_seltsamer_port_ergibt_400_mit_kopfzeilen(host):
    start = _roh_anfrage(host)
    assert start["status"] == 400
    koepfe = {k.decode("latin-1").lower() for k, _ in start["headers"]}
    for name in sicherheit.SICHERHEITS_KOEPFE:
        assert name.lower() in koepfe, name


# ── P0.3 CORS ──────────────────────────────────────────────────────────────

def test_vorabfrage_fremder_seite_bekommt_keine_freigabe(client):
    antwort = client.options("/api/health", headers={
        "Origin": "http://boese.example",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-api-key",
    })
    assert antwort.status_code == 403
    assert "access-control-allow-origin" not in antwort.headers
    assert "access-control-allow-credentials" not in antwort.headers


def test_keine_cors_freigabe_bei_normaler_anfrage(client):
    antwort = client.get("/api/health")
    assert "access-control-allow-origin" not in antwort.headers


# ── P0.5 Kopfzeilen, Positivliste, Doku-Seiten ─────────────────────────────

@pytest.mark.parametrize("pfad", ["/", "/api/health", "/app.js", "/gibt-es-nicht"])
def test_sicherheitskopfzeilen_ueberall(client, pfad):
    antwort = client.get(pfad)
    for name, wert in sicherheit.SICHERHEITS_KOEPFE.items():
        assert antwort.headers.get(name) == wert, (pfad, name)


def _absturz_app():
    """Kleine App mit derselben Middleware und einer Route, die abstürzt."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.routing import Route

    async def absturz(_anfrage):
        raise RuntimeError("Probe-Absturz")

    return Starlette(routes=[Route("/api/absturz", absturz)],
                     middleware=[Middleware(sicherheit.SicherheitsMiddleware)])


def test_sicherheitskopfzeilen_auch_bei_absturz():
    """Codex-Einwand R1: Die 500 entstand außerhalb der Middleware, ohne Kopfzeilen."""
    antwort = TestClient(_absturz_app(), raise_server_exceptions=False).get("/api/absturz")
    assert antwort.status_code == 500
    for name, wert in sicherheit.SICHERHEITS_KOEPFE.items():
        assert antwort.headers.get(name) == wert, name


def test_absturz_wird_weitergereicht():
    """Der Fehler wird nicht verschluckt: Er erreicht das Log des Servers."""
    with pytest.raises(RuntimeError, match="Probe-Absturz"):
        TestClient(_absturz_app()).get("/api/absturz")


def test_csp_erlaubt_blob_nur_fuer_bilder_und_ton():
    for teil in sicherheit.CSP.split(";"):
        richtlinie = teil.strip().split(" ")[0]
        if "blob:" in teil:
            assert richtlinie in ("img-src", "media-src"), teil
    assert "script-src 'self'" in sicherheit.CSP
    assert "unsafe-inline" not in sicherheit.CSP.split("style-src")[0]


@pytest.mark.parametrize("pfad", sorted(sicherheit.FRONTEND_DATEIEN))
def test_jede_datei_der_positivliste_wird_ausgeliefert(client, pfad):
    assert client.get("/" + pfad).status_code == 200


@pytest.mark.parametrize("pfad", [
    "/tests/test_diff_darstellung.js",
    "/%74ests/test_diff_darstellung.js",
    "/tests/./test_diff_darstellung.js",
    "/Tests/test_diff_darstellung.js",
    "/wecken.js",
    "/app.js.bak",
    "/api/konfig",
    "/../backend/app/config.py",
    "/docs",
    "/redoc",
    "/openapi.json",
])
def test_alles_andere_ist_404(client, pfad):
    assert client.get(pfad).status_code == 404


def test_wurzel_liefert_index(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "<title>Personal AI Agent</title>" in antwort.text
    assert antwort.headers["cache-control"].startswith("no-store")


# ── P0.4 Schlüssel im HTML ─────────────────────────────────────────────────

@pytest.mark.parametrize("seite", ["/", "/index.html", "/hermes_status.html"])
@pytest.mark.parametrize("adresse", ["127.0.0.1", "127.0.0.2", "::1", "::ffff:127.0.0.1"])
def test_schluessel_steht_maskiert_im_meta_feld(mit_schluessel, seite, adresse):
    text = _client_von(adresse).get(seite).text
    assert ('<meta name="agent-schluessel" content="Attrappe&quot;&lt;&amp;&gt;schluessel">'
            in text)
    assert ATTRAPPE not in text


def test_ohne_schluessel_bleibt_das_meta_feld_leer(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    assert '<meta name="agent-schluessel" content="">' in _client_von("127.0.0.1").get("/").text


# ── H1 (HTTPS-Plan, 14.10.2026): Schlüssel nur an das Gerät selbst ─────────

@pytest.mark.parametrize("seite", ["/", "/index.html", "/hermes_status.html"])
@pytest.mark.parametrize("adresse", ["192.168.178.20", "10.0.0.5", "172.16.1.1", "::ffff:192.168.1.2",
                                     "fe80::1", "testclient", ""])
def test_wlan_und_unbekannte_clients_bekommen_keinen_schluessel(mit_schluessel, seite, adresse):
    text = _client_von(adresse).get(seite).text
    assert '<meta name="agent-schluessel" content="">' in text
    assert "Attrappe" not in text


@pytest.mark.parametrize("kopf", ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-Client-IP"])
def test_kopfzeile_kann_keinen_loopback_vortaeuschen(mit_schluessel, kopf):
    wert = "for=127.0.0.1" if kopf == "Forwarded" else "127.0.0.1"
    text = _client_von("192.168.178.20").get("/", headers={kopf: wert}).text
    assert "Attrappe" not in text


def test_ohne_gegenstelle_kein_schluessel(mit_schluessel):
    assert sicherheit.client_ist_loopback({"type": "http"}) is False
    assert sicherheit.client_ist_loopback({"type": "http", "client": None}) is False
    assert sicherheit.client_ist_loopback({"type": "http", "client": ("127.0.0.1", 1)}) is True


def test_andere_dateien_bekommen_keinen_schluessel(client, mit_schluessel):
    for pfad in ("/app.js", "/sw.js", "/manifest.json"):
        assert "Attrappe" not in client.get(pfad).text


def test_beide_seiten_tragen_den_platzhalter():
    for name in sicherheit.SCHLUESSEL_SEITEN:
        text = (FRONTEND / name).read_text(encoding="utf-8")
        assert text.count(sicherheit.SCHLUESSEL_PLATZHALTER) == 1, name


def test_keine_route_liefert_den_schluessel_als_skript():
    pfade = {getattr(r, "path", "") for r in app.routes}
    assert "/api/konfig" not in pfade
    quelltext = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "__API_KEY__" not in quelltext


# ── Wächter: alles, was geladen wird, steht in der Positivliste ────────────

def _geladene_dateien():
    gefunden = {}
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for ziel in re.findall(r'(?:src|href)="([^"#]+)"', index):
        gefunden[ziel] = "index.html"
    status = (FRONTEND / "hermes_status.html").read_text(encoding="utf-8")
    for ziel in re.findall(r'src="([^"]+)"', status):
        gefunden[ziel] = "hermes_status.html"
    sw = (FRONTEND / "sw.js").read_text(encoding="utf-8")
    treffer = re.search(r"const STATIC_ASSETS = \[([\s\S]*?)\];", sw)
    assert treffer, "sw.js: STATIC_ASSETS nicht gefunden"
    liste = treffer.group(1)
    for ziel in re.findall(r"'([^']+)'", liste):
        gefunden[ziel] = "sw.js"
    app_js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    for ziel in re.findall(r"(?:addModule|register)\('([^']+)'\)", app_js):
        gefunden[ziel] = "app.js"
    manifest = (FRONTEND / "manifest.json").read_text(encoding="utf-8")
    for ziel in re.findall(r'"src"\s*:\s*"([^"]+)"', manifest):
        gefunden[ziel] = "manifest.json"
    return gefunden


def test_waechter_geladene_dateien_stehen_in_der_positivliste():
    geladen = _geladene_dateien()
    assert len(geladen) >= 8, geladen
    fehlend = []
    for ziel, quelle in geladen.items():
        name = ziel.split("?")[0].lstrip("./").lstrip("/")
        if name not in sicherheit.FRONTEND_DATEIEN:
            fehlend.append(f"{quelle}: {ziel}")
    assert not fehlend, f"geladen, aber nicht ausgeliefert: {fehlend}"
