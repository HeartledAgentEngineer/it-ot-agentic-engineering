"""HTTPS-Plan H3a (14.10.2026): ``backend/serve.py`` — ein Prozess, zwei Zugänge.

Offline: Konfigurationen werden nur gebaut (nicht geladen, also ohne echtes
Zertifikat), das Zusammenspiel der Server läuft mit Attrappen.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import ssl

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("serve_h3", os.path.join(BACKEND, "serve.py"))
serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve)


def _ordner(tmp_path, *namen, leer=()):
    for name in namen:
        (tmp_path / name).write_text("" if name in leer else "attrappe", encoding="utf-8")
    return tmp_path


def test_mit_allen_drei_dateien_zwei_zugaenge(tmp_path):
    ordner = _ordner(tmp_path, *serve.TLS_DATEIEN)
    http, https = serve.konfigurationen(ordner, "0.0.0.0")
    assert (http.host, http.port, http.ssl_certfile) == ("127.0.0.1", 8080, None)
    assert (https.host, https.port) == ("0.0.0.0", 8443)
    assert https.ssl_certfile == str(ordner / "server.crt")
    assert https.ssl_keyfile == str(ordner / "server.key")


def test_nur_der_tls_zugang_lauscht_im_netz(tmp_path):
    configs = serve.konfigurationen(_ordner(tmp_path, *serve.TLS_DATEIEN), "0.0.0.0")
    assert [c.host for c in configs if c.ssl_certfile is None] == ["127.0.0.1"]


@pytest.mark.parametrize("fehlt", serve.TLS_DATEIEN)
def test_fehlt_eine_datei_nur_http_auf_host_bind(tmp_path, fehlt):
    ordner = _ordner(tmp_path, *[n for n in serve.TLS_DATEIEN if n != fehlt])
    (config,) = serve.konfigurationen(ordner, "192.0.2.1")
    assert (config.host, config.port, config.ssl_certfile) == ("192.0.2.1", 8080, None)


@pytest.mark.parametrize("leer", serve.TLS_DATEIEN)
def test_leere_datei_zaehlt_als_fehlend(tmp_path, leer):
    ordner = _ordner(tmp_path, *serve.TLS_DATEIEN, leer=(leer,))
    assert not serve.tls_bereit(ordner)
    assert len(serve.konfigurationen(ordner)) == 1


def test_kopfzeilen_bestimmen_weder_adresse_noch_schema(tmp_path):
    for ordner in (_ordner(tmp_path, *serve.TLS_DATEIEN), tmp_path / "leer"):
        for c in serve.konfigurationen(ordner):
            assert c.proxy_headers is False


def test_lifespan_laeuft_nur_einmal(tmp_path):
    configs = serve.konfigurationen(_ordner(tmp_path, *serve.TLS_DATEIEN))
    assert [c.lifespan for c in configs] == ["on", "off"]
    assert serve.konfigurationen(tmp_path / "leer")[0].lifespan == "on"


def test_tls_ordner_aus_umgebung(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TLS_ORDNER", str(tmp_path))
    assert serve.tls_ordner() == tmp_path
    monkeypatch.delenv("AGENT_TLS_ORDNER")
    assert serve.tls_ordner().name == ".agent_tls"


def test_host_bind_aus_umgebung(monkeypatch):
    monkeypatch.delenv("HOST_BIND", raising=False)
    assert serve.host_bind_lesen() == "0.0.0.0"
    monkeypatch.setenv("HOST_BIND", " 127.0.0.1 ")
    assert serve.host_bind_lesen() == "127.0.0.1"


# ── Zusammenspiel (Attrappen statt uvicorn.Server) ──────────────────────────

class _Server:
    protokoll: list = []

    def __init__(self, config):
        self.config, self.started, self.should_exit = config, False, False

    async def serve(self):
        name = self.config
        _Server.protokoll.append(("start", name))
        if name == "kaputt":
            return
        await asyncio.sleep(0.1)
        self.started = True
        _Server.protokoll.append(("bereit", name))
        if name == "zweiter":                    # endet nach kurzer Zeit von selbst
            await asyncio.sleep(0.05)
        else:
            while not self.should_exit:          # laeuft, bis man ihn stoppt
                await asyncio.sleep(0.01)
        _Server.protokoll.append(("ende", name))


@pytest.fixture
def attrappe(monkeypatch):
    _Server.protokoll = []
    monkeypatch.setattr(serve.uvicorn, "Server", _Server)
    return _Server.protokoll


def test_zweiter_startet_erst_wenn_erster_bereit(attrappe):
    asyncio.run(asyncio.wait_for(serve.laufen(["erster", "zweiter"]), 5))
    assert attrappe.index(("bereit", "erster")) < attrappe.index(("start", "zweiter"))


def test_endet_einer_enden_alle(attrappe):
    asyncio.run(asyncio.wait_for(serve.laufen(["erster", "zweiter"]), 5))
    assert ("ende", "erster") in attrappe and ("ende", "zweiter") in attrappe


def test_kommt_der_erste_nicht_hoch_startet_der_zweite_nie(attrappe):
    asyncio.run(asyncio.wait_for(serve.laufen(["kaputt", "zweiter"]), 5))
    assert ("start", "zweiter") not in attrappe


# ── Echte Probe: zwei uvicorn-Server in einem Prozess (eigene Mini-App) ─────

def _zertifikat(ordner):
    """Selbst signiertes Zertifikat fuer 127.0.0.1 (nur fuer diesen Test)."""
    x509 = pytest.importorskip("cryptography.x509")
    from datetime import datetime, timedelta, timezone
    from ipaddress import IPv4Address

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    schluessel = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    jetzt = datetime.now(timezone.utc)
    zert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(schluessel.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(jetzt - timedelta(minutes=1)).not_valid_after(jetzt + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(IPv4Address("127.0.0.1"))]),
                           critical=False)
            .sign(schluessel, hashes.SHA256()))
    pem = zert.public_bytes(serialization.Encoding.PEM)
    (ordner / "server.crt").write_bytes(pem)
    (ordner / "ca.crt").write_bytes(pem)
    (ordner / "server.key").write_bytes(schluessel.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))


def test_echte_zwei_zugaenge_teilen_app_und_lifespan_einmal(tmp_path):
    httpx = pytest.importorskip("httpx")
    _zertifikat(tmp_path)
    zaehler = {"lifespan": 0}

    async def mini_app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                nachricht = await receive()
                if nachricht["type"] == "lifespan.startup":
                    zaehler["lifespan"] += 1
                    await send({"type": "lifespan.startup.complete"})
                elif nachricht["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        text = f'{scope["scheme"]} {scope["client"][0]}'.encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": text})

    configs = serve.konfigurationen(tmp_path, app=mini_app)
    for c in configs:                       # freie Ports statt 8080/8443, nur lokal
        c.host, c.port, c.log_level = "127.0.0.1", 0, "warning"

    async def probe():
        server_vorher = serve.uvicorn.Server
        laeufer = []

        class Merker(server_vorher):
            def __init__(self, config):
                super().__init__(config)
                laeufer.append(self)
        serve.uvicorn.Server = Merker
        try:
            aufgabe = asyncio.create_task(serve.laufen(configs))
            while len(laeufer) < 2 or not all(s.started for s in laeufer):
                await asyncio.sleep(0.05)
            ports = [s.servers[0].sockets[0].getsockname()[1] for s in laeufer]
            kontext = ssl.create_default_context(cafile=str(tmp_path / "ca.crt"))
            async with httpx.AsyncClient(verify=kontext) as client:
                a = await client.get(f"http://127.0.0.1:{ports[0]}/")
                b = await client.get(f"https://127.0.0.1:{ports[1]}/")
            laeufer[0].should_exit = True
            await asyncio.wait_for(aufgabe, 10)
            return a.text, b.text
        finally:
            serve.uvicorn.Server = server_vorher

    a, b = asyncio.run(asyncio.wait_for(probe(), 30))
    assert a == "http 127.0.0.1" and b == "https 127.0.0.1"
    assert zaehler["lifespan"] == 1
