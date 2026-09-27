"""Tests: Router /api/cloud — alles OHNE Netz.

Der Router wird ueber die ECHTE App mit dem TestClient geprueft (kein
Server, kein Netz). Wo der Dienst gebraucht wird, steht eine Attrappe im
Weg; EIN Test laeuft bewusst durch den echten Dienst mit gemocktem httpx —
so ist die Verdrahtung selbst bewiesen und nicht nur der Attrappen-Weg.

Aufruf: cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_router.py -q
"""

import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.router import cloud as router_mod  # noqa: E402
from app.services import pcloud_service as service_mod  # noqa: E402

MASK = "se" + "*" * 15 + ".com"          # erfundene Adresse fuer den Maskentest
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 20   # rohe Bildbytes, wie thumb() sie liefert
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
DATEI = b"inhalt-einer-datei"

# Alle fuenf zugesagten Pfade samt Beispiel-Parametern.
PFADE = (
    ("/api/cloud/status", {}),
    ("/api/cloud/liste", {"folderid": 0}),
    ("/api/cloud/suche", {"q": "urlaub"}),
    ("/api/cloud/thumb", {"fileid": 1}),
    ("/api/cloud/datei", {"fileid": 1}),
)


class FakeDienst:
    """Attrappe des pCloud-Dienstes: feste Antworten, merkt sich Argumente."""

    def __init__(self, *, konfiguriert=True):
        self.konfiguriert = konfiguriert
        self.gesehen = {}
        self.fehler = None
        # Live liefert thumb() JPEG-Bytes; ein Test setzt hier PNG ein.
        self.bild_bytes = JPEG

    def ist_konfiguriert(self):
        return self.konfiguriert

    def status(self):
        self._vielleicht_fehler()
        return {
            "verbunden": True,
            "host": "eapi.pcloud.com",
            "email": MASK,
            "userid": 4738912,
            "premium": True,
            "email_verifiziert": True,
            "quota_gb": 2199.0,
            "belegt_gb": 390.5,
            "frei_gb": 1808.5,
        }

    def liste(self, folderid=0):
        self.gesehen["folderid"] = folderid
        self._vielleicht_fehler()
        return [
            {"name": "Bilder", "ist_ordner": True, "folderid": 42,
             "fileid": None, "groesse": None, "geaendert": None},
            {"name": "bericht.pdf", "ist_ordner": False, "folderid": None,
             "fileid": 7, "groesse": 100, "geaendert": None},
        ]

    def suche(self, begriff, folderid=0):
        self.gesehen["begriff"] = begriff
        self.gesehen["folderid"] = folderid
        self._vielleicht_fehler()
        return [
            {"name": "Urlaub 2024", "ist_ordner": True, "folderid": 5,
             "fileid": None, "groesse": None, "geaendert": None},
        ]

    def thumb(self, fileid, groesse="120x120"):
        self.gesehen["fileid"] = fileid
        self.gesehen["groesse"] = groesse
        self._vielleicht_fehler()
        return self.bild_bytes

    def datei_bytes(self, fileid):
        self.gesehen["fileid"] = fileid
        self._vielleicht_fehler()
        return DATEI

    def _vielleicht_fehler(self):
        if self.fehler:
            raise self.fehler


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


@pytest.fixture()
def fake(monkeypatch) -> FakeDienst:
    """FakeDienst an die Stelle des echten Dienstes im Router haengen."""
    dienst = FakeDienst()
    monkeypatch.setattr(router_mod, "pcloud_service", dienst)
    return dienst


def _route(pfad):
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == pfad and "GET" in getattr(route, "methods", set()):
            return route
    return None


# ── Verdrahtung ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pfad", [p for p, _ in PFADE])
def test_alle_fuenf_routen_sind_eingehaengt(pfad):
    assert _route(pfad) is not None, f"{pfad} fehlt in der App"


@pytest.mark.parametrize("pfad", [p for p, _ in PFADE])
def test_routen_haengen_am_api_key_schutz(pfad):
    """Wie die übrigen /api-Routen: ohne gültigen Key kein Zugriff."""
    route = _route(pfad)
    assert route is not None
    namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
    assert "require_api_key" in namen, f"Key-Schutz fehlt (Abhängigkeiten: {namen})"


# ── Ohne Token: 503 mit Klartext statt Absturz ─────────────────────────────

@pytest.mark.parametrize("pfad,params", PFADE)
def test_ohne_token_liefert_503_mit_klartext(client, monkeypatch, pfad, params):
    """Der echte, unkonfigurierte Dienst steht hier im Weg — kein Netzcall."""
    monkeypatch.setattr(settings, "pcloud_token", "")
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    antwort = client.get(pfad, params=params)
    assert antwort.status_code == 503
    assert "PCLOUD_TOKEN" in antwort.json()["detail"]


def test_dienst_ohne_token_wird_ebenfalls_503(client, fake):
    """Auch wenn der Dienst selbst 'nicht konfiguriert' meldet: 503."""
    fake.fehler = service_mod.PCloudNichtKonfiguriert("kein Token, klarer Text")
    antwort = client.get("/api/cloud/status")
    assert antwort.status_code == 503
    assert "klarer Text" in antwort.json()["detail"]


# ── Die fünf Endpunkte mit Dienst-Attrappe ─────────────────────────────────

def test_status_liefert_konto_ohne_klartextadresse(client, fake):
    antwort = client.get("/api/cloud/status")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["email"] == MASK
    assert daten["quota_gb"] == 2199.0
    assert daten["premium"] is True
    # Eine vollstaendige Adresse enthaelt "@" — die Maske nicht.
    assert "@" not in antwort.text


def test_liste_gibt_folderid_weiter_und_zaehlt(client, fake):
    antwort = client.get("/api/cloud/liste", params={"folderid": 7})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["folderid"] == 7
    assert daten["anzahl"] == 2
    assert daten["eintraege"][0]["name"] == "Bilder"
    assert fake.gesehen["folderid"] == 7


def test_liste_ohne_folderid_fragt_die_wurzel(client, fake):
    antwort = client.get("/api/cloud/liste")
    assert antwort.status_code == 200
    assert antwort.json()["folderid"] == 0
    assert fake.gesehen["folderid"] == 0


def test_liste_lehnt_negativen_folderid_ab(client):
    assert client.get("/api/cloud/liste", params={"folderid": -1}).status_code == 422


def test_suche_gibt_den_begriff_weiter(client, fake):
    antwort = client.get("/api/cloud/suche", params={"q": "urlaub", "folderid": 3})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["frage"] == "urlaub"
    assert daten["folderid"] == 3
    assert daten["anzahl"] == 1
    assert daten["treffer"][0]["name"] == "Urlaub 2024"
    assert fake.gesehen == {"begriff": "urlaub", "folderid": 3}


def test_suche_ohne_q_wird_von_der_app_abgelehnt(client):
    assert client.get("/api/cloud/suche").status_code == 422


def test_thumb_antwortet_als_bild(client, fake):
    """Live liefert pCloud JPEG — der Medientyp kommt aus den Bytes."""
    antwort = client.get("/api/cloud/thumb", params={"fileid": 42})
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("image/jpeg")
    assert antwort.content == JPEG
    assert fake.gesehen == {"fileid": 42, "groesse": "120x120"}


def test_thumb_setzt_den_medientyp_aus_den_bytes(client, fake):
    """PNG-Bytes (andere Quelle/Version) bekommen image/png statt image/jpeg."""
    fake.bild_bytes = PNG
    antwort = client.get("/api/cloud/thumb", params={"fileid": 3})
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("image/png")


def test_thumb_gibt_die_groesse_weiter(client, fake):
    antwort = client.get(
        "/api/cloud/thumb", params={"fileid": 42, "groesse": "32x32"}
    )
    assert antwort.status_code == 200
    assert fake.gesehen["groesse"] == "32x32"


def test_thumb_groessere_vorschauen_sind_erlaubt(client, fake):
    """480x480/800x800 sind live geprueft (27.09.2026) — fuer Screenshots."""
    antwort = client.get(
        "/api/cloud/thumb", params={"fileid": 42, "groesse": "800x800"}
    )
    assert antwort.status_code == 200
    assert fake.gesehen["groesse"] == "800x800"


def test_thumb_lehnt_fremde_groesse_ab(client):
    antwort = client.get(
        "/api/cloud/thumb", params={"fileid": 42, "groesse": "9999x9999"}
    )
    assert antwort.status_code == 422


def test_datei_antwortet_als_download(client, fake):
    antwort = client.get("/api/cloud/datei", params={"fileid": 9})
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("application/octet-stream")
    assert "attachment" in antwort.headers["content-disposition"]
    assert antwort.content == DATEI
    assert fake.gesehen["fileid"] == 9


# ── Fehler der pCloud werden ehrlich uebersetzt ────────────────────────────

def test_pcloud_fehler_wird_502_mit_fehlertext(client, fake):
    fake.fehler = service_mod.PCloudFehler(
        "pCloud meldet Fehler 2005: Directory does not exist."
    )
    antwort = client.get("/api/cloud/liste", params={"folderid": 999})
    assert antwort.status_code == 502
    assert "Directory does not exist." in antwort.json()["detail"]


def test_zu_grosse_datei_wird_413(client, fake):
    fake.fehler = service_mod.PCloudZuGross(
        "Datei ist 27.3 MB gross und ueberschreitet die Obergrenze von 26.2 MB."
    )
    antwort = client.get("/api/cloud/datei", params={"fileid": 1})
    assert antwort.status_code == 413
    assert "Obergrenze" in antwort.json()["detail"]


# ── Verdrahtung selbst: Router -> echter Dienst -> (gemocktes) httpx ───────

def test_echter_dienst_mit_gemocktem_httpx(client, monkeypatch):
    """Kein Netz, aber der ECHTE Weg: Router ruft den echten Dienst.

    Beweist, dass der Router den Dienst aus den Einstellungen benutzt und
    der Token nur als auth-Parameter im Request landet.
    """
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.setattr(settings, "pcloud_token", "test-token-router")
    monkeypatch.setattr(settings, "pcloud_host", "api.test.example")

    class Antwort:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {
                "result": 0,
                "metadata": {
                    "contents": [
                        {"name": "Bilder", "isfolder": True, "folderid": 42},
                        {"name": "bericht.pdf", "isfolder": False, "fileid": 7,
                         "size": 100},
                    ]
                },
            }

    aufrufe = []

    def fake_get(url, params=None, timeout=None):
        aufrufe.append({"url": url, "params": dict(params or {})})
        return Antwort()

    monkeypatch.setattr(service_mod.httpx, "get", fake_get)

    antwort = client.get("/api/cloud/liste", params={"folderid": 0})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["anzahl"] == 2
    assert daten["eintraege"][0]["name"] == "Bilder"
    assert aufrufe[0]["url"] == "https://api.test.example/listfolder"
    assert aufrufe[0]["params"]["auth"] == "test-token-router"
    assert aufrufe[0]["params"]["folderid"] == 0
