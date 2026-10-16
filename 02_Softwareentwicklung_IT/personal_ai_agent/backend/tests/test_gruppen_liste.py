"""Synthetische Vertragstests für Liste, Detail und Reaktivieren von Gruppen."""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402


def _gruppe(kennung, groesse, **extra):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse - 1,
            "videos": 1, "von": "2018-01-01", "bis": "2024-12-31",
            "beispiele": [], "zwilling_kandidaten": [], **extra}


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    yield tmp_path
    gq._CACHE.clear()


def _gruppen_schreiben(basis, gruppen):
    pfad = basis / gq.UNTERORDNER / gq.BEISPIELE_DATEINAME
    pfad.write_text(json.dumps({"gruppen": gruppen}), encoding="utf-8")
    gq._CACHE.clear()
    return pfad


def _json_schreiben(basis, name, wert):
    pfad = basis / name
    pfad.write_text(json.dumps(wert, ensure_ascii=False), encoding="utf-8")
    return pfad


def test_liste_trennt_status_mit_prioritaet_benannt_vor_unbekannt_vor_spaeter(basis):
    _gruppen_schreiben(basis, [_gruppe("G-a", 40), _gruppe("G-b", 30),
                               _gruppe("G-c", 20), _gruppe("G-d", 10)])
    bestaetigt = _json_schreiben(basis, gq.BESTAETIGT_DATEINAME,
                                 {"bestaetigt": {"G-a": "Mustername"}})
    vorgaben = _json_schreiben(basis, gq.VORGABEN_DATEINAME,
                               {"gleich": [["G-a", "G-b"]], "verschieden": []})
    stand = _json_schreiben(basis, gq.STAND_DATEINAME,
                             {"spaeter": ["G-a", "G-b", "G-c"],
                              "unbekannt": ["G-a", "G-b"]})
    vorher = [p.read_bytes() for p in (bestaetigt, vorgaben, stand)]

    erwartet = {
        "benannt": [("G-a", "Mustername")],
        "ausgeblendet": [("G-b", None)],
        "spaeter": [("G-c", None)],
        "offen": [("G-d", None)],
    }
    for status, zeilen in erwartet.items():
        r = gq.liste(status)
        assert r == {"ok": True, "status": status, "gruppen": [
            {"kennung": k, "groesse": groesse, "bilder": groesse - 1, "videos": 1,
             "von": "2018-01-01", "bis": "2024-12-31", "status": status, "name": name}
            for k, name in zeilen
            for groesse in [{"G-a": 40, "G-b": 30, "G-c": 20, "G-d": 10}[k]]
        ], "gesamt": 1, "seite": 1, "seiten": 1, "je_seite": 24}
    assert [p.read_bytes() for p in (bestaetigt, vorgaben, stand)] == vorher


def test_liste_sortiert_stabil_und_blaettert_25_gruppen(basis):
    gruppen = [_gruppe(f"G-{n:02d}", 50 if n in (2, 7) else 100 - n) for n in range(25)]
    _gruppen_schreiben(basis, gruppen)

    erste = gq.liste("offen", seite=1, je_seite=24)
    zweite = gq.liste("offen", seite=2, je_seite=24)
    dahinter = gq.liste("offen", seite=3, je_seite=24)

    assert erste["gesamt"] == 25 and erste["seiten"] == 2
    assert erste["seite"] == 1 and len(erste["gruppen"]) == 24
    assert [g["kennung"] for g in erste["gruppen"][:4]] == ["G-00", "G-01", "G-03", "G-04"]
    assert [g["kennung"] for g in erste["gruppen"] if g["groesse"] == 50] == ["G-02"]
    assert zweite["gruppen"] == [{"kennung": "G-07", "groesse": 50, "bilder": 49,
                                   "videos": 1, "von": "2018-01-01", "bis": "2024-12-31",
                                   "status": "offen", "name": None}]
    assert dahinter == {"ok": True, "status": "offen", "gruppen": [], "gesamt": 25,
                        "seite": 3, "seiten": 2, "je_seite": 24}


@pytest.mark.parametrize("status,seite,je_seite", [("falsch", 1, 24), ("offen", 0, 24),
                                                    ("offen", 1, 101)])
def test_liste_service_lehnt_ungueltige_argumente_ab(basis, status, seite, je_seite):
    _gruppen_schreiben(basis, [_gruppe("G-a", 1)])
    assert gq.liste(status, seite, je_seite) == {"ok": False, "fehler": "Ungültige Listenparameter."}


def test_liste_meldet_fehlende_datei_ohne_neue_datei(basis):
    r = gq.liste("offen")
    assert r["ok"] is False and "Gruppen-Datei fehlt" in r["fehler"]
    assert list(basis.iterdir()) == [basis / gq.UNTERORDNER]


def test_leere_gruppenliste_hat_null_seiten(basis):
    _gruppen_schreiben(basis, [])
    assert gq.liste() == {"ok": True, "status": "offen", "gruppen": [],
                          "gesamt": 0, "seite": 1, "seiten": 0, "je_seite": 24}


def test_detail_ist_alte_naechste_antwort_mit_status_und_name_ohne_schreiben(basis):
    beispiel = {"bild_id": "501", "index": 0, "bbox": [10, 20, 30, 40],
                "breite": 1000, "hoehe": 750, "aufnahme": "2021-04-05T10:00:00"}
    _gruppen_schreiben(basis, [_gruppe("G-top", 10), _gruppe("G-detail", 2, bilder=2, videos=0,
                                       von="2021-01-01", bis="2021-12-31",
                                       beispiele=[beispiel])])
    status = _json_schreiben(basis, gq.STAND_DATEINAME, {"spaeter": [], "unbekannt": []})
    vorher = status.read_bytes()

    r = gq.detail("G-detail")

    assert r == {"ok": True, "fertig": False, "offen": 2, "namen": [], "gruppe": {
        "kennung": "G-detail", "groesse": 2, "bilder": 2, "videos": 0,
        "von": "2021-01-01", "bis": "2021-12-31", "war_spaeter": False,
        "beispiele": [{"fileid": "501", "index": 0, "bbox": [10, 20, 30, 40],
                       "breite": 1000, "hoehe": 750, "aufnahme": "2021-04-05"}],
        "zwillinge": [], "verbunden": [], "status": "offen", "name": None}}
    assert status.read_bytes() == vorher
    assert gq.naechste() == {"ok": True, "fertig": False, "offen": 2, "namen": [], "gruppe": {
        "kennung": "G-top", "groesse": 10, "bilder": 9, "videos": 1,
        "von": "2018-01-01", "bis": "2024-12-31", "war_spaeter": False,
        "beispiele": [], "zwillinge": [], "verbunden": []}}


def test_antwort_offen_und_undo_stellen_status_exakt_wieder_her(basis):
    _gruppen_schreiben(basis, [_gruppe("G-spaeter", 2), _gruppe("G-aus", 1)])
    _json_schreiben(basis, gq.STAND_DATEINAME,
                    {"spaeter": ["G-spaeter"], "unbekannt": ["G-aus"]})
    bestaetigt = _json_schreiben(basis, gq.BESTAETIGT_DATEINAME,
                                 {"bestaetigt": {"G-benannt": "Mustername"}})
    vorgaben = _json_schreiben(basis, gq.VORGABEN_DATEINAME,
                               {"gleich": [["G-benannt", "G-anders"]], "verschieden": []})
    bestaetigt_vorher, vorgaben_vorher = bestaetigt.read_bytes(), vorgaben.read_bytes()

    for kennung in ("G-spaeter", "G-aus"):
        r = gq.antworten(kennung, "offen")
        assert r["ok"] is True
        status = json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8"))
        assert kennung not in status["spaeter"] and kennung not in status["unbekannt"]
        undone = gq.rueckgaengig()
        assert undone["ok"] is True
        status = json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8"))
        assert (kennung in status["spaeter"]) == (kennung == "G-spaeter")
        assert (kennung in status["unbekannt"]) == (kennung == "G-aus")
    assert gq.antworten("G-benannt", "offen")["ok"] is False
    assert bestaetigt.read_bytes() == bestaetigt_vorher
    assert vorgaben.read_bytes() == vorgaben_vorher


def test_neue_get_routen_und_parametergrenzen(basis):
    _gruppen_schreiben(basis, [_gruppe("G-api", 4)])
    app = FastAPI()
    app.include_router(gruppen_router.router)
    client = TestClient(app)

    assert client.get("/api/gruppen/liste").json()["gruppen"][0]["kennung"] == "G-api"
    assert client.get("/api/gruppen/liste", params={"status": "ausgeblendet"}).status_code == 200
    assert client.get("/api/gruppen/liste", params={"status": "falsch"}).status_code == 422
    assert client.get("/api/gruppen/liste", params={"seite": 0}).status_code == 422
    assert client.get("/api/gruppen/liste", params={"je_seite": 101}).status_code == 422
    assert client.get("/api/gruppen/detail/G-api").json()["gruppe"]["kennung"] == "G-api"
    assert client.get("/api/gruppen/detail/G-fehlt").json()["ok"] is False


def test_antwort_offen_fehlende_kennung_schreibt_nichts(basis):
    gruppen = _gruppen_schreiben(basis, [_gruppe("G-a", 1)])
    stand = _json_schreiben(basis, gq.STAND_DATEINAME, {"spaeter": [], "unbekannt": []})
    vorher = (gruppen.read_bytes(), stand.read_bytes())
    r = gq.antworten("G-fehlt", "offen")
    assert r["ok"] is False
    assert (gruppen.read_bytes(), stand.read_bytes()) == vorher


def test_wiederholtes_reaktivieren_verliert_beim_undo_keinen_status(basis):
    _gruppen_schreiben(basis, [_gruppe("G-spaeter", 2)])
    _json_schreiben(basis, gq.STAND_DATEINAME,
                    {"spaeter": ["G-spaeter"], "unbekannt": []})
    vorgaben = _json_schreiben(basis, gq.VORGABEN_DATEINAME,
                               {"gleich": [["G-x", "G-y"]], "verschieden": []})
    bestaetigt = _json_schreiben(basis, gq.BESTAETIGT_DATEINAME, {"bestaetigt": {}})
    vorher = (vorgaben.read_bytes(), bestaetigt.read_bytes())

    assert gq.antworten("G-spaeter", "offen")["ok"] is True
    assert gq.antworten("G-spaeter", "offen")["ok"] is True
    assert json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8")) == {
        "spaeter": [], "unbekannt": []}
    gq.rueckgaengig()
    assert json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8")) == {
        "spaeter": [], "unbekannt": []}
    gq.rueckgaengig()
    assert json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8")) == {
        "spaeter": ["G-spaeter"], "unbekannt": []}
    assert (vorgaben.read_bytes(), bestaetigt.read_bytes()) == vorher


def test_detail_video_standbild_nutzt_bisherige_beispielaufbereitung(basis):
    kennung = "G-video"
    _gruppen_schreiben(basis, [_gruppe(kennung, 4, bilder=0, videos=1,
                                       von=None, bis=None)])
    video_id = "88#t=2.0"
    zeile = {"bild_id": video_id, "video_id": "88", "zeit_s": 2.0, "index": 0,
             "kennung": kennung, "bbox": [100, 200, 300, 400], "breite": 1920,
             "hoehe": 1080, "anteil": 0.5, "score": 0.9}
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        json.dumps(zeile) + "\n", encoding="utf-8")
    karte = {"bild_id": video_id, "video_id": "88", "zeit_s": 2.0,
             "standbild_fileid": 9001, "breite": 960, "hoehe": 540, "skala": 0.5}
    (basis / gq.UNTERORDNER / gq.VIDEO_STANDBILDER_DATEINAME).write_text(
        json.dumps(karte) + "\n", encoding="utf-8")

    r = gq.detail(kennung)
    assert r["gruppe"]["beispiele"] == [{"fileid": "9001", "index": 0,
                                         "bbox": [50, 100, 150, 200], "breite": 960,
                                         "hoehe": 540, "aufnahme": None, "video": True,
                                         "zeit_s": 2.0}]
    assert r["gruppe"]["videos"] == 0


def test_detail_ohne_gesichtsdatei_legt_nichts_an(basis):
    _gruppen_schreiben(basis, [_gruppe("G-ohne-datei", 3, beispiele=[])])
    stand = _json_schreiben(basis, gq.STAND_DATEINAME, {"spaeter": [], "unbekannt": []})
    vorher = stand.read_bytes()
    assert gq.detail("G-ohne-datei")["gruppe"]["beispiele"] == []
    assert stand.read_bytes() == vorher
    assert not (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).exists()


# ── Ergebnisprüfung Runde 1, Befund 4: Rückgängig stellt die Reihenfolge wieder her ──

def _stand_lesen(basis):
    return json.loads((basis / gq.STAND_DATEINAME).read_text(encoding="utf-8"))


@pytest.mark.parametrize("liste", ["spaeter", "unbekannt"])
def test_undo_nach_offen_stellt_reihenfolge_der_liste_wieder_her(basis, liste):
    _gruppen_schreiben(basis, [_gruppe("G-a", 3), _gruppe("G-b", 2), _gruppe("G-c", 1)])
    start = {"spaeter": [], "unbekannt": []}
    start[liste] = ["G-a", "G-b", "G-c"]
    _json_schreiben(basis, gq.STAND_DATEINAME, start)

    # Vorderstes, mittleres und letztes Element: jeweils exakt dieselbe Position danach.
    for kennung in ("G-a", "G-b", "G-c"):
        assert gq.antworten(kennung, "offen")["ok"] is True
        assert kennung not in _stand_lesen(basis)[liste]
        assert gq.rueckgaengig()["ok"] is True
        assert _stand_lesen(basis) == start, kennung


def test_undo_nach_offen_stellt_beide_listen_in_ihrer_reihenfolge_wieder_her(basis):
    _gruppen_schreiben(basis, [_gruppe("G-a", 3), _gruppe("G-b", 2), _gruppe("G-c", 1)])
    start = {"spaeter": ["G-b", "G-a"], "unbekannt": ["G-b", "G-c"]}
    _json_schreiben(basis, gq.STAND_DATEINAME, start)
    assert gq.antworten("G-b", "offen")["ok"] is True
    assert _stand_lesen(basis) == {"spaeter": ["G-a"], "unbekannt": ["G-c"]}
    assert gq.rueckgaengig()["ok"] is True
    assert _stand_lesen(basis) == start


def test_undo_alteintrag_ohne_position_haengt_wie_bisher_ans_ende(basis):
    _gruppen_schreiben(basis, [_gruppe("G-a", 3), _gruppe("G-b", 2)])
    _json_schreiben(basis, gq.STAND_DATEINAME, {"spaeter": [], "unbekannt": []})
    # Protokolleintrag aus der Zeit vor „listen_position“: nur die Mitgliedschaft.
    alt = {"id": "altaltalt001", "zeit": "2026-10-01T10:00:00", "kennung": "G-a",
           "art": "offen", "ziel": None, "namen_vorher": {},
           "paare_neu": {"gleich": [], "verschieden": []},
           "paare_weg": {"gleich": [], "verschieden": []},
           "listen_vorher": {"spaeter": True, "unbekannt": False}}
    (basis / gq.PROTOKOLL_DATEINAME).write_text(json.dumps(alt) + "\n", encoding="utf-8")
    _json_schreiben(basis, gq.STAND_DATEINAME, {"spaeter": ["G-b"], "unbekannt": []})
    assert gq.rueckgaengig()["ok"] is True
    assert _stand_lesen(basis) == {"spaeter": ["G-b", "G-a"], "unbekannt": []}
