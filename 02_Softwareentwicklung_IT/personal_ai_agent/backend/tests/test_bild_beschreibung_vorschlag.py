"""Tests G2: Vision-Vorschlag für eine Bildbeschreibung (02.11.2026).

Plan: ``.hermes/plans/2026-11-02_geschichte-sprachmodell.md``, Schritt G2 Punkt 5,
Prüfkriterien (e) Vorschlag speichert nichts, (f) ``data_collection: deny``,
ehrliche Fehler, kein Text im Log.

Alles offline: Bildabruf und Modell-Client sind Attrappen (``httpx.MockTransport``
beziehungsweise ein Schein-Client). Kein Netz, keine echten Bilder, kein Schlüssel.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bild_beschreibung_vorschlag.py -q
"""
from __future__ import annotations

import json
import logging
import os
import sys

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import erzaehlen as erzaehlen_router  # noqa: E402
from app.services import bild_beschreibung_vorschlag as bv  # noqa: E402
from app.services import erzaehl_service as es  # noqa: E402
from app.services.modell_router import MODELL_VISION  # noqa: E402
from app.services.openrouter_client import OpenRouterZDRClient  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32          # erfundenes Bild (nur Kopfbytes)
GEHEIM_TEXT = "Zwei Personen sitzen am Steg und lachen."
SCHLUESSEL = "sk-or-GEHEIMER-TESTSCHLUESSEL"


def _antwort(text: str = GEHEIM_TEXT, usage: dict | None = None) -> dict:
    j = {"choices": [{"message": {"content": text}}]}
    if usage is not None:
        j["usage"] = usage
    return j


def _echter_client(handler) -> tuple[OpenRouterZDRClient, list[dict]]:
    """Der ECHTE ZDR-Client auf einem Schein-Transport: man sieht den wirklich gesendeten Rumpf."""
    gesehen: list[dict] = []

    def _h(request: httpx.Request) -> httpx.Response:
        gesehen.append({"url": str(request.url), "body": json.loads(request.content),
                        "auth": request.headers.get("authorization")})
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(_h))
    return OpenRouterZDRClient(api_key=SCHLUESSEL, client=http), gesehen


class SchwarzerKasten:
    """Schein-Client mit derselben Schnittstelle wie ``OpenRouterZDRClient.chat_completion``."""

    def __init__(self, antwort=None, wirft=None):
        self.antwort, self.wirft, self.aufrufe = antwort, wirft, []

    def chat_completion(self, messages, model, temperature=0.7, max_tokens=None, extra_payload=None):
        self.aufrufe.append({"messages": messages, "model": model, "max_tokens": max_tokens,
                             "extra_payload": extra_payload})
        if self.wirft:
            raise self.wirft
        return self.antwort


@pytest.fixture(autouse=True)
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    es._BILDINFO_SPEICHER.clear()
    return tmp_path


def _bild(fileid):
    return JPEG


# ── (f) data_collection: deny steckt im echten Aufruf ───────────────────────

def test_f_data_collection_deny_im_gesendeten_rumpf():
    client, gesehen = _echter_client(lambda r: httpx.Response(200, json=_antwort()))
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    assert erg["ok"] is True
    assert len(gesehen) == 1
    body = gesehen[0]["body"]
    assert body["provider"]["data_collection"] == "deny"
    assert body["provider"]["zdr"] is True
    assert body["model"] == MODELL_VISION == erg["modell"]


def test_f_aufruf_traegt_deny_auch_ohne_haertung_des_clients():
    """Der Dienst setzt ``data_collection: deny`` selbst — nicht nur der Client."""
    kasten = SchwarzerKasten(antwort=_antwort())
    bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=kasten)
    assert kasten.aufrufe[0]["extra_payload"]["provider"]["data_collection"] == "deny"


def test_f_bild_max_tokens_prompt_im_rumpf():
    client, gesehen = _echter_client(lambda r: httpx.Response(200, json=_antwort()))
    bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    body = gesehen[0]["body"]
    assert body["max_tokens"] == bv.MAX_TOKENS <= 400
    inhalt = body["messages"][-1]["content"]
    teile = {t["type"]: t for t in inhalt}
    assert teile["image_url"]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "Deutsch" in teile["text"]["text"] and "erfinde keine Namen" in teile["text"]["text"]
    assert body["stream"] is False


def test_f_zeitgrenze_30_sekunden_am_client():
    assert bv.ZEITGRENZE_S == 30
    kasten = bv.standard_client()
    assert kasten.timeout == 30


# ── (e) Vorschlag speichert nichts ───────────────────────────────────────────

def test_e_vorschlag_speichert_nichts(umgebung):
    kasten = SchwarzerKasten(antwort=_antwort())
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=kasten)
    assert erg["ok"] is True and erg["vorschlag"] == GEHEIM_TEXT
    assert not os.path.exists(es.beschreibungen_pfad())
    assert not os.path.exists(es.life_archive_pfad())
    assert es.beschreibung_holen(101) is None


def test_antwortform_und_kosten_aus_usage():
    kasten = SchwarzerKasten(antwort=_antwort(usage={"prompt_tokens": 800, "completion_tokens": 120, "cost": 0.00123}))
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=kasten)
    assert set(erg) == {"ok", "vorschlag", "modell", "kosten_usd"}
    assert erg["kosten_usd"] == pytest.approx(0.00123)


def test_kosten_aus_tokens_wenn_kein_cost_feld():
    kasten = SchwarzerKasten(antwort=_antwort(usage={"prompt_tokens": 1000, "completion_tokens": 100}))
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=kasten)
    ein, aus = bv.PREISE_USD_PRO_MIO[MODELL_VISION]
    assert erg["kosten_usd"] == pytest.approx((1000 * ein + 100 * aus) / 1_000_000)


def test_kosten_null_wenn_unbekannt():
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=SchwarzerKasten(antwort=_antwort()))
    assert erg["kosten_usd"] is None


def test_vorschlag_wird_auf_speicherlaenge_begrenzt_und_geordnet():
    lang = "Ein Satz am See.   Noch   ein\nSatz. " * 60
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=SchwarzerKasten(antwort=_antwort(lang)))
    assert len(erg["vorschlag"]) <= es.BESCHREIBUNG_MAX_LAENGE
    assert "  " not in erg["vorschlag"] and "\n" not in erg["vorschlag"]
    assert erg["vorschlag"].endswith(".")


# ── (f) Fehler: ehrlich, ohne Schlüssel und URL ─────────────────────────────

def _pruefe_ehrlich(erg):
    assert erg["ok"] is False
    grund = erg["grund"]
    assert isinstance(grund, str) and grund
    assert SCHLUESSEL not in grund and "://" not in grund and "openrouter.ai" not in grund


def test_f_zeitgrenze_ehrliche_meldung():
    def h(request):
        raise httpx.ReadTimeout("zu langsam", request=request)
    client, _ = _echter_client(h)
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    _pruefe_ehrlich(erg)
    assert "30" in erg["grund"] and "Zeit" in erg["grund"]


def test_f_http_fehler_nennt_statuscode_ohne_url():
    client, _ = _echter_client(lambda r: httpx.Response(429, json={"error": "limit"}))
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    _pruefe_ehrlich(erg)
    assert "429" in erg["grund"]


def test_f_verbindungsfehler_ehrlich():
    def h(request):
        raise httpx.ConnectError("kaputt https://openrouter.ai/x " + SCHLUESSEL, request=request)
    client, _ = _echter_client(h)
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    _pruefe_ehrlich(erg)


def test_f_unerwartete_ausnahme_ohne_text_der_ausnahme():
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild,
                                   client=SchwarzerKasten(wirft=RuntimeError("Schluessel " + SCHLUESSEL)))
    _pruefe_ehrlich(erg)


def test_f_leere_oder_kaputte_antwort():
    for antwort in ({"choices": []}, {"choices": [{"message": {"content": "   "}}]}, {}, "kein json"):
        erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=SchwarzerKasten(antwort=antwort))
        _pruefe_ehrlich(erg)


def test_f_bild_nicht_ladbar_ruft_modell_nicht_auf():
    kasten = SchwarzerKasten(antwort=_antwort())

    def kaputt(fileid):
        raise bv.BildNichtLadbar("pCloud ist nicht konfiguriert.")

    erg = bv.vorschlag_fuer_fileid("101", bild_holer=kaputt, client=kasten)
    _pruefe_ehrlich(erg)
    assert kasten.aufrufe == []


def test_f_ungueltige_fileid_ruft_nichts_auf():
    kasten = SchwarzerKasten(antwort=_antwort())
    erg = bv.vorschlag_fuer_fileid("abc", bild_holer=_bild, client=kasten)
    _pruefe_ehrlich(erg)
    assert kasten.aufrufe == []


def test_f_ohne_schluessel_kein_aufruf(monkeypatch):
    monkeypatch.setattr(bv, "_schluessel", lambda: "")
    erg = bv.vorschlag_fuer_fileid("101", bild_holer=_bild)
    _pruefe_ehrlich(erg)
    assert "Schl" in erg["grund"]


# ── (f) Log: nur Modell, Dauer, Zeichenzahl, Kosten ─────────────────────────

def test_f_log_enthaelt_keinen_text_und_keinen_schluessel(caplog):
    caplog.set_level(logging.DEBUG)
    kasten = SchwarzerKasten(antwort=_antwort(usage={"cost": 0.0011}))
    bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=kasten)
    client, _ = _echter_client(lambda r: httpx.Response(500, text=GEHEIM_TEXT + SCHLUESSEL))
    bv.vorschlag_fuer_fileid("101", bild_holer=_bild, client=client)
    # Gemeint sind die Log-Zeilen dieses Programms (``app.*``); die Bibliothek httpx
    # protokolliert die Anfrage-URL (ohne Schlüssel und Inhalt) selbst.
    eigene = [r for r in caplog.records if r.name.startswith("app.")]
    alles = "\n".join(r.getMessage() for r in eigene)
    assert alles
    assert GEHEIM_TEXT not in alles and "Steg" not in alles and SCHLUESSEL not in alles
    assert "openrouter.ai" not in alles and "101" not in alles
    erfolg = [r.getMessage() for r in eigene if "Bildbeschreibung-Vorschlag" in r.getMessage()]
    assert erfolg and MODELL_VISION in erfolg[0] and str(len(GEHEIM_TEXT)) in erfolg[0]


# ── Bildabruf: pCloud-Vorschau mittlerer Größe ──────────────────────────────

def test_standard_bild_holer_nimmt_mittlere_vorschau(monkeypatch):
    aufrufe = []

    class FakePCloud:
        def ist_konfiguriert(self):
            return True

        def thumb(self, fileid, groesse="120x120"):
            aufrufe.append((fileid, groesse))
            return JPEG

    monkeypatch.setattr(bv, "pcloud_service", FakePCloud())
    assert bv.standard_bild_holer(4711) == JPEG
    assert aufrufe == [(4711, bv.VORSCHAU_GROESSE)] and bv.VORSCHAU_GROESSE == "480x480"


def test_standard_bild_holer_ohne_pcloud(monkeypatch):
    class Aus:
        def ist_konfiguriert(self):
            return False

    monkeypatch.setattr(bv, "pcloud_service", Aus())
    with pytest.raises(bv.BildNichtLadbar):
        bv.standard_bild_holer(1)


def test_standard_bild_holer_pcloud_fehler_wird_ehrlich(monkeypatch):
    from app.services.pcloud_service import PCloudFehler

    class Kaputt:
        def ist_konfiguriert(self):
            return True

        def thumb(self, fileid, groesse="120x120"):
            raise PCloudFehler("pCloud antwortete mit HTTP 404.")

    monkeypatch.setattr(bv, "pcloud_service", Kaputt())
    with pytest.raises(bv.BildNichtLadbar) as e:
        bv.standard_bild_holer(1)
    assert "404" in str(e.value)


# ── Router ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client_app(monkeypatch):
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    return TestClient(app)


def test_router_vorschlag_speichert_nichts_und_uebernehmen_genau_eine_zeile(client_app, monkeypatch):
    kasten = SchwarzerKasten(antwort=_antwort())
    monkeypatch.setattr(bv, "_schluessel", lambda: "test")
    monkeypatch.setattr(bv, "standard_client", lambda: kasten)
    monkeypatch.setattr(bv, "standard_bild_holer", _bild)

    r = client_app.post("/api/erzaehlen/bild-beschreibung/vorschlag", json={"fileid": "555"})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["vorschlag"] == GEHEIM_TEXT and j["modell"] == MODELL_VISION
    assert "kosten_usd" in j
    assert not os.path.exists(es.beschreibungen_pfad())

    r2 = client_app.post("/api/erzaehlen/bild-beschreibung/uebernehmen",
                         json={"fileid": "555", "beschreibung": j["vorschlag"]})
    assert r2.json()["ok"] is True
    zeilen = [json.loads(z) for z in open(es.beschreibungen_pfad(), encoding="utf-8")]
    assert len(zeilen) == 1 and zeilen[0]["quelle"] == "einzel_ki"


def test_router_vorschlag_fehler_ist_ok_false_mit_status_200(client_app, monkeypatch):
    monkeypatch.setattr(bv, "_schluessel", lambda: "test")
    monkeypatch.setattr(bv, "standard_client", lambda: SchwarzerKasten(wirft=RuntimeError("x")))
    monkeypatch.setattr(bv, "standard_bild_holer", _bild)
    r = client_app.post("/api/erzaehlen/bild-beschreibung/vorschlag", json={"fileid": "555"})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["grund"]
