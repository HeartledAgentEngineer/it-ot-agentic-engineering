"""Tagesimport im Checks-Fenster (C3): Dienst und zwei Routen.

Plan: ``.hermes/plans/2026-10-25_tagesimport-handy.md``, Abschnitt „C3 im Einzelnen".

Das Werkzeug ``tools/handy/tageslauf.py`` (C1) schreibt Bericht und Stand und liest die
Schalterdatei ``tageslauf.json``. Dieser Dienst zeigt sie an (``GET /api/tageslauf``) und
ändert die Schalterdatei auf Wunsch (``POST /api/tageslauf/einstellungen``). Geprüft wird:

* Lesen: Standardwerte, Bericht von heute / veraltet / defekt, Gemini-Erinnerung,
  unlesbare Einstellungen, nichts wird beim Lesen geschrieben, nie ein 500.
* Schreiben: nur echte Bool-Werte, derselbe Ordner-Regelsatz wie im Werkzeug, Lesen-Ändern-
  Schreiben (fremde Schlüssel bleiben), unzulässige Eingabe -> 400 und Datei unverändert,
  unlesbare Datei -> 409 und Datei unverändert, Link oder Repo als Ziel -> abgelehnt.
* Schutz: beide Routen hängen am API-Key.

Alles in ``tmp_path`` mit ``TAGESLAUF_DATEN``; das echte ``~/foto_sortierung`` wird nie berührt.
Kein Netz, keine echten Namen oder Pfade.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.router import auth
from app.services import tageslauf_status

API_KEY = "Attrappe-Tageslauf-Schluessel-0815"
HEUTE = datetime.date(2026, 10, 26)
KOPF = {"X-API-Key": API_KEY}
GET_PFAD = "/api/tageslauf"
POST_PFAD = "/api/tageslauf/einstellungen"
APP_PY = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def daten(tmp_path, monkeypatch):
    """Eigener Datenordner (noch nicht angelegt), fester Tag, Schutz mit Attrappen-Schluessel."""
    ordner = tmp_path / "tagesdaten"
    monkeypatch.setenv("TAGESLAUF_DATEN", str(ordner))
    monkeypatch.setattr(tageslauf_status, "_heute", lambda: HEUTE)
    monkeypatch.setattr(settings, "api_key", API_KEY)
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()
    yield ordner
    auth._SITZUNGEN.clear()
    auth._FEHLVERSUCHE.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _schreibe(ordner: Path, name: str, inhalt) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / name
    text = inhalt if isinstance(inhalt, str) else json.dumps(inhalt)
    pfad.write_text(text, encoding="utf-8")
    return pfad


def _bericht(datum: str = "2026-10-26", exit_code: int = 0) -> dict:
    return {
        "version": 1, "zeit": f"{datum}T07:30:00", "datum": datum, "modus": "wenn_faellig",
        "exit": exit_code, "stand_fortgeschrieben": exit_code == 0,
        "bausteine": [
            {"name": "wa_bilder", "status": "ok", "exit": 0,
             "text": "WhatsApp-Bilder: 12 hochgeladen", "zahlen": {"hochgeladen": 12}},
            {"name": "wa_chats", "status": "nicht_eingerichtet", "exit": 0,
             "text": "WhatsApp-Chats: nicht eingerichtet (W2 Teil B)", "zahlen": {}},
            {"name": "kamera", "status": "ok", "exit": 0,
             "text": "Kamera: 30 neue Dateien seit letztem Lauf", "zahlen": {"neu": 30}},
            {"name": "gemini", "status": "erinnerung", "exit": 0,
             "text": "Gemini: Takeout-Export fällig (alle 2 Monate)", "zahlen": {}},
        ],
    }


def _lesen(daten: Path) -> dict:
    return json.loads((daten / "tageslauf.json").read_text(encoding="utf-8"))


def _holen(client) -> dict:
    antwort = client.get(GET_PFAD, headers=KOPF)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


# ── 1. Lesen ────────────────────────────────────────────────────────────────

def test_ohne_dateien_gelten_die_standardwerte_und_nichts_wird_geschrieben(client, daten):
    d = _holen(client)

    assert d["ok"] is True
    assert d["an"] is False
    assert d["einstellungen_lesbar"] is True
    assert d["kamera_ordner"] == {"gesetzt": False, "wert": None}
    assert d["bericht"] is None
    assert d["heute_gelaufen"] is False
    assert d["bericht_veraltet"] is False
    assert d["gemini"]["letzter_export"] is None
    assert d["gemini"]["tage_seit_export"] is None
    assert d["gemini"]["faellig"] is True
    assert not daten.exists(), "Lesen darf den Datenordner nicht anlegen"


def test_an_und_kamera_ordner_werden_gelesen(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True, "kamera_ordner": "/Beispiel/Kamera"})

    d = _holen(client)

    assert d["an"] is True
    assert d["kamera_ordner"] == {"gesetzt": True, "wert": "/Beispiel/Kamera"}


def test_nur_ein_echtes_true_schaltet_ein(client, daten):
    for falsch in ("true", 1, "ja", None, [True]):
        _schreibe(daten, "tageslauf.json", {"an": falsch})
        assert _holen(client)["an"] is False, falsch


def test_bericht_von_heute_wird_auf_das_noetige_gekuerzt(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True})
    _schreibe(daten, "tageslauf_bericht.json", _bericht())
    _schreibe(daten, ".tageslauf_stand.json", {"version": 1, "letzter_gesamtlauf": "2026-10-26"})

    d = _holen(client)

    assert d["heute_gelaufen"] is True
    assert d["bericht_veraltet"] is False
    assert d["bericht"]["datum"] == "2026-10-26"
    assert d["bericht"]["exit"] == 0
    assert [b["name"] for b in d["bericht"]["bausteine"]] == [
        "wa_bilder", "wa_chats", "kamera", "gemini"]
    for baustein in d["bericht"]["bausteine"]:
        assert set(baustein) == {"name", "status", "text"}
    assert d["bericht"]["bausteine"][0]["text"] == "WhatsApp-Bilder: 12 hochgeladen"


def test_veralteter_bericht_wird_erkannt(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True})
    _schreibe(daten, "tageslauf_bericht.json", _bericht(datum="2026-10-24"))
    _schreibe(daten, ".tageslauf_stand.json", {"letzter_gesamtlauf": "2026-10-24"})

    d = _holen(client)

    assert d["bericht_veraltet"] is True
    assert d["heute_gelaufen"] is False
    assert d["bericht"]["datum"] == "2026-10-24"


def test_stand_von_heute_ohne_bericht_gilt_als_gelaufen(client, daten):
    _schreibe(daten, ".tageslauf_stand.json", {"letzter_gesamtlauf": "2026-10-26"})

    d = _holen(client)

    assert d["heute_gelaufen"] is True
    assert d["bericht"] is None
    assert d["bericht_veraltet"] is False


@pytest.mark.parametrize("inhalt", ["{kaputt", "[]", '"text"', "42", "null"])
def test_defekter_bericht_und_stand_ergeben_nie_einen_fehler(client, daten, inhalt):
    _schreibe(daten, "tageslauf_bericht.json", inhalt)
    _schreibe(daten, ".tageslauf_stand.json", inhalt)

    d = _holen(client)

    assert d["bericht"] is None
    assert d["heute_gelaufen"] is False
    assert d["bericht_veraltet"] is False


def test_bericht_mit_unsinn_in_den_bausteinen_wirft_nicht(client, daten):
    unsinn = {"datum": "2026-10-26", "exit": "x", "bausteine": [
        None, 5, {"name": 3, "status": ["a"], "text": None},
        {"name": "kamera", "status": "ok", "text": "Kamera: ok"}]}
    _schreibe(daten, "tageslauf_bericht.json", unsinn)

    d = _holen(client)

    assert d["bericht"]["exit"] is None
    assert [b["name"] for b in d["bericht"]["bausteine"]] == ["kamera"]


def test_bericht_ohne_datum_gilt_als_veraltet(client, daten):
    _schreibe(daten, "tageslauf_bericht.json", {"exit": 0, "bausteine": []})

    d = _holen(client)

    assert d["bericht"]["datum"] is None
    assert d["bericht_veraltet"] is True


def test_gemini_erinnerung_rechnet_mit_dem_heutigen_tag(client, daten):
    _schreibe(daten, "tageslauf.json", {"gemini_letzter_export": "2026-10-20"})
    g = _holen(client)["gemini"]
    assert g == {"letzter_export": "2026-10-20", "tage_seit_export": 6, "faellig": False}

    _schreibe(daten, "tageslauf.json", {"gemini_letzter_export": "2026-08-01"})
    g = _holen(client)["gemini"]
    assert g["tage_seit_export"] == 86 and g["faellig"] is True

    for unsinn in ("gestern", 5, None, "2026-13-40", "2027-01-01"):
        _schreibe(daten, "tageslauf.json", {"gemini_letzter_export": unsinn})
        g = _holen(client)["gemini"]
        assert g["letzter_export"] is None and g["faellig"] is True, unsinn


def test_unlesbare_einstellungen_werden_ehrlich_gemeldet(client, daten):
    for inhalt in ("{kaputt", "[1, 2]"):
        _schreibe(daten, "tageslauf.json", inhalt)
        d = _holen(client)
        assert d["einstellungen_lesbar"] is False
        assert d["an"] is False
        assert d["kamera_ordner"] == {"gesetzt": False, "wert": None}


def test_antwort_enthaelt_keinen_pfad_des_datenordners(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True, "kamera_ordner": "/Beispiel/Kamera"})
    _schreibe(daten, "tageslauf_bericht.json", _bericht())

    text = client.get(GET_PFAD, headers=KOPF).text

    assert str(daten) not in text
    assert "tagesdaten" not in text


def test_standard_datenordner_ist_foto_sortierung_im_heimverzeichnis(monkeypatch):
    monkeypatch.delenv("TAGESLAUF_DATEN", raising=False)

    assert tageslauf_status.daten_ordner() == os.path.expanduser("~/foto_sortierung")


# ── 2. Schreiben ────────────────────────────────────────────────────────────

def test_einschalten_legt_die_datei_an_und_liefert_den_neuen_stand(client, daten):
    antwort = client.post(POST_PFAD, json={"an": True}, headers=KOPF)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ok"] is True
    assert antwort.json()["an"] is True
    assert _lesen(daten) == {"an": True}
    assert _holen(client)["an"] is True


def test_ausschalten_und_erneutes_einschalten(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True})

    assert client.post(POST_PFAD, json={"an": False}, headers=KOPF).status_code == 200
    assert _lesen(daten) == {"an": False}
    assert client.post(POST_PFAD, json={"an": True}, headers=KOPF).status_code == 200
    assert _lesen(daten) == {"an": True}


def test_lesen_aendern_schreiben_laesst_fremde_schluessel_stehen(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": False, "zusatz": {"a": [1, 2]},
                                        "gemini_letzter_export": "2026-09-01"})

    assert client.post(POST_PFAD, json={"an": True}, headers=KOPF).status_code == 200
    assert client.post(POST_PFAD, json={"kamera_ordner": "/Beispiel/Kamera"},
                       headers=KOPF).status_code == 200

    assert _lesen(daten) == {"an": True, "zusatz": {"a": [1, 2]},
                             "gemini_letzter_export": "2026-09-01",
                             "kamera_ordner": "/Beispiel/Kamera"}


@pytest.mark.parametrize("falsch", ["true", "false", 1, 0, "ja", None, [True], {}])
def test_an_muss_ein_echtes_bool_sein(client, daten, falsch):
    pfad = _schreibe(daten, "tageslauf.json", {"an": False})
    vorher = pfad.read_bytes()

    antwort = client.post(POST_PFAD, json={"an": falsch}, headers=KOPF)

    assert antwort.status_code == 400, antwort.text
    assert isinstance(antwort.json()["detail"], str) and antwort.json()["detail"]
    assert pfad.read_bytes() == vorher


def test_kamera_ordner_wird_gespeichert_und_von_umgebendem_leerraum_befreit(client, daten):
    antwort = client.post(POST_PFAD, json={"kamera_ordner": "  /Beispiel/Kamera  "}, headers=KOPF)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["kamera_ordner"] == {"gesetzt": True, "wert": "/Beispiel/Kamera"}
    assert _lesen(daten) == {"kamera_ordner": "/Beispiel/Kamera"}


UNZULAESSIGE_ORDNER = [
    "Beispiel/Kamera",                 # kein fuehrendes /
    "/",                               # nur die Wurzel
    "",
    "   ",
    "/Beispiel/../Kamera",             # ..
    "/Beispiel\\Kamera",               # Rueckstrich
    "/Beispiel//Kamera",               # //
    "/Crypto Folder/Kamera",           # Teil mit crypto
    "/beispiel/MeinCRYPTOordner",
    "/" + "a" * 200,                   # 201 Zeichen
    "/Beispiel/Kam\x00era",            # Steuerzeichen
    "/Beispiel/Kam\nera",
    5, True, None, ["/Beispiel"],
]


@pytest.mark.parametrize("ordner", UNZULAESSIGE_ORDNER, ids=lambda w: repr(w)[:30])
def test_unzulaessiger_kamera_ordner_ergibt_400_und_die_datei_bleibt(client, daten, ordner):
    pfad = _schreibe(daten, "tageslauf.json", {"an": True, "kamera_ordner": "/Beispiel/Alt"})
    vorher = pfad.read_bytes()

    antwort = client.post(POST_PFAD, json={"kamera_ordner": ordner}, headers=KOPF)

    assert antwort.status_code == 400, antwort.text
    assert pfad.read_bytes() == vorher


def test_genau_200_zeichen_sind_noch_erlaubt(client, daten):
    ordner = "/" + "a" * 199

    assert client.post(POST_PFAD, json={"kamera_ordner": ordner}, headers=KOPF).status_code == 200
    assert _lesen(daten)["kamera_ordner"] == ordner


def test_gemini_export_heute_traegt_das_heutige_datum_ein(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True, "gemini_letzter_export": "2026-08-01"})

    antwort = client.post(POST_PFAD, json={"gemini_export_heute": True}, headers=KOPF)

    assert antwort.status_code == 200, antwort.text
    assert _lesen(daten) == {"an": True, "gemini_letzter_export": "2026-10-26"}
    assert antwort.json()["gemini"] == {"letzter_export": "2026-10-26",
                                        "tage_seit_export": 0, "faellig": False}


@pytest.mark.parametrize("falsch", [False, "true", 1, None])
def test_gemini_export_heute_nur_mit_echtem_true(client, daten, falsch):
    pfad = _schreibe(daten, "tageslauf.json", {"an": True})
    vorher = pfad.read_bytes()

    antwort = client.post(POST_PFAD, json={"gemini_export_heute": falsch}, headers=KOPF)

    assert antwort.status_code == 400
    assert pfad.read_bytes() == vorher


def test_mehrere_felder_in_einem_aufruf(client, daten):
    antwort = client.post(POST_PFAD, json={"an": True, "kamera_ordner": "/Beispiel/Kamera",
                                           "gemini_export_heute": True}, headers=KOPF)

    assert antwort.status_code == 200
    assert _lesen(daten) == {"an": True, "kamera_ordner": "/Beispiel/Kamera",
                             "gemini_letzter_export": "2026-10-26"}


def test_ein_ungueltiges_feld_verhindert_alle_aenderungen(client, daten):
    pfad = _schreibe(daten, "tageslauf.json", {"an": False})
    vorher = pfad.read_bytes()

    antwort = client.post(POST_PFAD, json={"an": True, "kamera_ordner": "relativ"}, headers=KOPF)

    assert antwort.status_code == 400
    assert pfad.read_bytes() == vorher


@pytest.mark.parametrize("koerper", [
    {}, {"unbekannt": 1}, {"an": True, "unbekannt": 1}, [], "text", 5, None,
])
def test_leere_oder_fremde_koerper_ergeben_400(client, daten, koerper):
    antwort = client.post(POST_PFAD, json=koerper, headers=KOPF)

    assert antwort.status_code == 400, antwort.text
    assert not daten.exists()


def test_kein_json_ergibt_400(client, daten):
    antwort = client.post(POST_PFAD, content=b"{kaputt",
                          headers={**KOPF, "Content-Type": "application/json"})

    assert antwort.status_code == 400
    assert not daten.exists()


@pytest.mark.parametrize("inhalt", ["{kaputt", "[1, 2]", ""])
def test_unlesbare_einstellungsdatei_ergibt_409_und_bleibt_unveraendert(client, daten, inhalt):
    pfad = _schreibe(daten, "tageslauf.json", inhalt)
    vorher = pfad.read_bytes()

    antwort = client.post(POST_PFAD, json={"an": True}, headers=KOPF)

    assert antwort.status_code == 409, antwort.text
    assert pfad.read_bytes() == vorher


def test_hartes_link_als_ziel_wird_abgelehnt(client, daten):
    original = _schreibe(daten, "anderes.json", {"an": False})
    try:
        os.link(original, daten / "tageslauf.json")
    except (OSError, NotImplementedError):
        pytest.skip("harte Links auf diesem System nicht moeglich")
    vorher = original.read_bytes()

    antwort = client.post(POST_PFAD, json={"an": True}, headers=KOPF)

    assert antwort.status_code == 403, antwort.text
    assert original.read_bytes() == vorher


def test_symbolischer_link_als_ziel_wird_abgelehnt(client, daten):
    original = _schreibe(daten, "anderes.json", {"an": False})
    try:
        os.symlink(original, daten / "tageslauf.json")
    except (OSError, NotImplementedError):
        pytest.skip("symbolische Links auf diesem System nicht moeglich")
    vorher = original.read_bytes()

    antwort = client.post(POST_PFAD, json={"an": True}, headers=KOPF)

    assert antwort.status_code == 403, antwort.text
    assert original.read_bytes() == vorher


def test_ziel_in_einem_git_repo_wird_abgelehnt(client, tmp_path, monkeypatch):
    repo = tmp_path / "irgendein_repo"
    (repo / ".git").mkdir(parents=True)
    ordner = repo / "daten"
    monkeypatch.setenv("TAGESLAUF_DATEN", str(ordner))

    antwort = client.post(POST_PFAD, json={"an": True}, headers=KOPF)

    assert antwort.status_code == 403, antwort.text
    assert not ordner.exists()


def test_nach_dem_schreiben_bleibt_keine_temp_datei_liegen(client, daten):
    client.post(POST_PFAD, json={"an": True}, headers=KOPF)
    client.post(POST_PFAD, json={"kamera_ordner": "/Beispiel/Kamera"}, headers=KOPF)

    assert sorted(p.name for p in daten.iterdir()) == ["tageslauf.json"]


def test_schreiben_aendert_weder_bericht_noch_stand(client, daten):
    bericht = _schreibe(daten, "tageslauf_bericht.json", _bericht())
    stand = _schreibe(daten, ".tageslauf_stand.json", {"letzter_gesamtlauf": "2026-10-26"})
    b0, s0 = bericht.read_bytes(), stand.read_bytes()

    assert client.post(POST_PFAD, json={"an": True}, headers=KOPF).status_code == 200

    assert bericht.read_bytes() == b0 and stand.read_bytes() == s0


# ── 3. Schutz ───────────────────────────────────────────────────────────────

def test_beide_routen_verlangen_den_api_key(client, daten):
    assert client.get(GET_PFAD).status_code == 401
    assert client.post(POST_PFAD, json={"an": True}).status_code == 401
    assert client.get(GET_PFAD, headers={"X-API-Key": "falsch"}).status_code == 401
    assert not daten.exists()
    assert client.get(GET_PFAD, headers=KOPF).status_code == 200


def test_der_dienst_greift_nicht_auf_tools_zu():
    """Das Backend importiert aus ``tools/`` nichts; der Schreibhelfer ist bewusst eigen."""
    quelle = (APP_PY / "services" / "tageslauf_status.py").read_text(encoding="utf-8")
    router = (APP_PY / "router" / "tageslauf.py").read_text(encoding="utf-8")

    for text in (quelle, router):
        assert "from tools" not in text and "import tools" not in text
        assert "tageslauf.py" not in text.replace("tools/handy/tageslauf.py", "")


def test_router_ist_mit_key_schutz_in_main_eingehaengt():
    main = (APP_PY / "main.py").read_text(encoding="utf-8")

    assert "tageslauf" in main.split("from app.router import (")[1].split(")")[0]
    assert "app.include_router(tageslauf.router, dependencies=[Depends(auth.require_api_key)])" in main


# ── 4. Selbsttest-Block ─────────────────────────────────────────────────────

def test_selbsttest_hat_einen_block_tageslauf(client, daten):
    _schreibe(daten, "tageslauf.json", {"an": True, "kamera_ordner": "/Beispiel/Kamera"})
    _schreibe(daten, "tageslauf_bericht.json", _bericht())
    _schreibe(daten, ".tageslauf_stand.json", {"letzter_gesamtlauf": "2026-10-26"})

    antwort = client.get("/api/selbsttest", headers=KOPF)

    assert antwort.status_code == 200
    block = antwort.json()["tageslauf"]
    assert block["an"] is True
    assert block["kamera_gesetzt"] is True
    assert block["heute_gelaufen"] is True
    assert block["letzter_lauf"] == "2026-10-26"
    assert block["letzter_exit"] == 0
    assert block["bericht_veraltet"] is False
    assert block["gemini_faellig"] is True
    assert block["einstellungen_lesbar"] is True
    assert str(daten) not in json.dumps(block)


def test_selbsttest_block_wirft_nie_auch_wenn_der_dienst_kaputt_ist(client, daten, monkeypatch):
    def kaputt():
        raise RuntimeError("Absicht")

    monkeypatch.setattr(tageslauf_status, "status", kaputt)

    antwort = client.get("/api/selbsttest", headers=KOPF)

    assert antwort.status_code == 200
    assert "error" in antwort.json()["tageslauf"]


# ── 5. Oberflaeche: Cache-Schluessel ────────────────────────────────────────

def test_cache_schluessel_stehen_auf_20261026a():
    index = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")

    m_app = re.search(r"app\.js\?v=(\d{8}[A-Z])", index)
    m_css = re.search(r"style\.css\?v=(\d{8}[A-Z])", index)
    assert m_app and m_app.group(1) >= "20261026A"
    assert m_css and m_css.group(1) >= "20261026A"
