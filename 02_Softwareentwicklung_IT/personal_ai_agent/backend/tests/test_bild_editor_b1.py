"""Tests: Bild-Editor fuer jedes Bild, Schritt B1 Backend (Plan Fassung 8, 26.10.2026).

Offline, nur erfundene Kennungen und Namen („Person A", fileid 111 ...) in
``tmp_path`` (``GRUPPEN_QUIZ_BASIS``). Es wird nie ``~/foto_sortierung`` gelesen
oder geschrieben. Keine Vektoren, kein Netz.

Geprueft wird (Prueckriterien des Plans, soweit sie B1 betreffen):
  * Datenmodell ``bild_korrekturen.json`` (handy-eigen), Index >= 1000 nur vom Server,
    gid muss zur fileid gehoeren;
  * ``bild-gesichter`` bleibt rein additiv (alte Felder unveraendert);
  * "Bilder mit X" und ``personen_auf_bildern`` lesen dieselbe zusammengefuehrte Sicht;
  * ``bild-rahmen``: erst alles pruefen, bei Fehler nichts schreiben; Teilfehler ehrlich;
  * Entfernen hebt feste Zuordnungen zuerst auf, ``zuordnen`` hebt Ausschluesse gegen das
    neue Ziel auf — der PC-Leser (``personen_gruppieren``) wirft danach nie ``PersonenFehler``;
  * Rueckgaengig der Art ``bild_rahmen`` und ein Rueckgaengig je ``aktion``;
  * Sperrliste handy-eigener Namen (Handy-Holer) und Ablehnung im PC-Uploader.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bild_editor_b1.py -q
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
PROJEKT = os.path.dirname(BACKEND)
WERKZEUGE = os.path.join(PROJEKT, "tools", "foto_sortierung")

from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402


def _werkzeug(name, ordner=WERKZEUGE):
    sys.path.insert(0, ordner)
    spez = importlib.util.spec_from_file_location(name, os.path.join(ordner, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def _gruppe(kennung, groesse=10):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse, "videos": 0,
            "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []}


GRUPPEN = [_gruppe("Person_2001", 40), _gruppe("Person_2002", 30),
           _gruppe("Person_2003", 20), _gruppe("Person_2004", 10)]


def _zeile(bild, index, kennung, bbox, breite=1000, hoehe=800):
    return {"bild_id": str(bild), "index": index, "kennung": kennung, "bbox": bbox,
            "breite": breite, "hoehe": hoehe, "anteil": 0.05, "score": 0.95}


ZEILEN = [
    _zeile(111, 0, "Person_2001", [100, 80, 200, 160]),
    _zeile(111, 1, "Person_2003", [600, 80, 100, 100]),
    _zeile(222, 0, "Person_2002", [50, 50, 100, 100]),
    _zeile(333, 0, "Person_2001", [10, 10, 100, 100]),
]


@pytest.fixture
def basis(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    daten.mkdir()
    heim = tmp_path / "heim"
    heim.mkdir()
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(daten))
    monkeypatch.setenv("HOME", str(heim))             # ~/foto_sortierung darf nie angefasst werden
    monkeypatch.setenv("USERPROFILE", str(heim))
    gq._CACHE.clear()
    ordner = daten / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({"stand": "2026-10-26T01:00:00", "verfahren": "mittelpunkt", "gruppen": GRUPPEN}),
        encoding="utf-8")
    _zuordnung_schreiben(daten, ZEILEN)
    assert gq.antworten("Person_2001", "name", "Person A")["ok"] is not False
    assert gq.antworten("Person_2002", "name", "Person B")["ok"] is not False
    yield daten
    gq._CACHE.clear()
    assert list(heim.iterdir()) == []                  # nichts im Heimordner angelegt


def _zuordnung_schreiben(daten, zeilen):
    (daten / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    gq._CACHE.clear()


def _json(pfad):
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def _korrekturen(basis):
    pfad = basis / gq.KORREKTUREN_DATEINAME
    return _json(pfad) if pfad.exists() else None


def _vorgaben(basis):
    pfad = basis / gq.VORGABEN_DATEINAME
    return _json(pfad) if pfad.exists() else {}


def _protokoll(basis):
    pfad = basis / gq.PROTOKOLL_DATEINAME
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def _pc_lesen(basis):
    """So liest der PC-Gruppierlauf die Vorgaben (wirft PersonenFehler bei Widerspruch)."""
    pg = _werkzeug("personen_gruppieren")
    vorgaben = pg.vorgaben_lesen(str(basis / gq.VORGABEN_DATEINAME))
    return pg._einzelzuordnungen_auflosen(vorgaben, gq.bestaetigt_lesen())


def _gesichter(fileid):
    r = gq.gesichter_auf_bild(fileid)
    assert r["ok"], r
    return {g["gid"]: g for g in r["gesichter"]}


def _neu(bbox=(0.1, 0.2, 0.2, 0.25), **felder):
    return dict({"neu": True, "bbox_norm": list(bbox)}, **felder)


def _client():
    app = FastAPI()
    app.include_router(gruppen_router.router)
    return TestClient(app)


# ── Datenmodell + Index-Regel ───────────────────────────────────────────────

def test_neues_gesicht_bekommt_index_ab_1000_vom_server(basis):
    r = gq.bild_rahmen("111", [_neu(name="Nur Handy")])
    assert r["ok"] is True and r["neu"] == ["111:1000"]
    r2 = gq.bild_rahmen("111", [_neu(bbox=(0.5, 0.5, 0.1, 0.1))])
    assert r2["neu"] == ["111:1001"]
    daten = _korrekturen(basis)
    assert daten["version"] == 1
    rahmen = daten["bilder"]["111"]["rahmen"]
    assert sorted(rahmen) == ["1000", "1001"]
    assert rahmen["1000"] == {"bbox_norm": [0.1, 0.2, 0.2, 0.25], "quelle": "hand", "name": "Nur Handy"}
    assert rahmen["1001"]["name"] is None and rahmen["1001"]["quelle"] == "hand"
    assert daten["bilder"]["111"]["entfernt"] == []


def test_korrekturdatei_wird_atomar_mit_sicherung_geschrieben(basis):
    gq.bild_rahmen("111", [_neu()])
    erste = (basis / gq.KORREKTUREN_DATEINAME).read_text(encoding="utf-8")
    gq.bild_rahmen("111", [_neu(bbox=(0.5, 0.5, 0.1, 0.1))])
    assert (basis / (gq.KORREKTUREN_DATEINAME + ".vorher")).read_text(encoding="utf-8") == erste
    assert not (basis / (gq.KORREKTUREN_DATEINAME + ".tmp")).exists()


def test_repo_pfad_wird_abgelehnt_und_nichts_geschrieben(basis, monkeypatch):
    monkeypatch.setattr(gq, "_im_projekt", lambda pfad: True)
    r = gq.bild_rahmen("111", [_neu()])
    assert r["ok"] is False and "Projektordner" in r["fehler"]
    assert not (basis / gq.KORREKTUREN_DATEINAME).exists()


def test_bild_korrekturen_nur_im_handy_ordner_gelesen(basis):
    """Eine Kopie unter personen_gruppen/ (PC-Ordner) zaehlt nicht."""
    fremd = basis / gq.UNTERORDNER / gq.KORREKTUREN_DATEINAME
    fremd.write_text(json.dumps({"version": 1, "bilder": {"111": {
        "rahmen": {"1000": {"bbox_norm": [0.1, 0.1, 0.2, 0.2], "quelle": "hand", "name": "Fremd"}},
        "entfernt": []}}}), encoding="utf-8")
    assert all(g["quelle"] != "hand" for g in _gesichter("111").values())


UNGUELTIG = [
    ("fremde_gid", "111", [{"gid": "222:0", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}]),
    ("index_ohne_gesicht", "111", [{"gid": "111:5", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}]),
    ("gid_fuer_neu", "111", [{"neu": True, "gid": "111:1000", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}]),
    ("hand_index_vom_client", "111", [{"gid": "111:1000", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}]),
    ("mehr_als_30", "111", [_neu(bbox=(0.1, 0.1, 0.05, 0.05))] * 31),
    ("keine_aenderungen", "111", []),
    ("bbox_links_ausserhalb", "111", [_neu(bbox=(-0.1, 0.1, 0.2, 0.2))]),
    ("bbox_rechts_ausserhalb", "111", [_neu(bbox=(0.9, 0.1, 0.2, 0.2))]),
    ("bbox_unten_ausserhalb", "111", [_neu(bbox=(0.1, 0.95, 0.2, 0.2))]),
    ("bbox_zu_klein", "111", [_neu(bbox=(0.1, 0.1, 0.005, 0.2))]),
    ("bbox_falsche_laenge", "111", [{"neu": True, "bbox_norm": [0.1, 0.1, 0.2]}]),
    ("bbox_text", "111", [{"neu": True, "bbox_norm": ["a", 0.1, 0.2, 0.2]}]),
    ("bbox_wahrheitswert", "111", [{"neu": True, "bbox_norm": [True, 0.1, 0.2, 0.2]}]),
    ("bbox_nan", "111", [{"neu": True, "bbox_norm": [float("nan"), 0.1, 0.2, 0.2]}]),
    ("neu_ohne_bbox", "111", [{"neu": True, "name": "Nur Handy"}]),
    ("leerer_name", "111", [_neu(name="")]),
    ("name_nur_leerraum", "111", [{"gid": "111:0", "name": "   "}]),
    ("name_kein_text", "111", [{"gid": "111:0", "name": 5}]),
    ("name_zu_lang", "111", [{"gid": "111:0", "name": "x" * 61}]),
    ("aenderung_ohne_inhalt", "111", [{"gid": "111:0"}]),
    ("entfernen_mit_name", "111", [{"gid": "111:0", "entfernen": True, "name": "Person B"}]),
    ("gid_doppelt", "111", [{"gid": "111:0", "name": "Person B"},
                            {"gid": "111:0", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}]),
    ("gid_ohne_form", "111", [{"gid": "abc", "name": "Person B"}]),
    ("fileid_keine_zahl", "abc", [_neu()]),
    ("aenderung_kein_objekt", "111", ["111:0"]),
]


@pytest.mark.parametrize("fall,fileid,aenderungen", UNGUELTIG, ids=[u[0] for u in UNGUELTIG])
def test_ungueltige_aenderung_schreibt_nichts(basis, fall, fileid, aenderungen):
    vorher = sorted(p.name for p in basis.iterdir())
    protokoll = _protokoll(basis)
    r = gq.bild_rahmen(fileid, aenderungen)
    assert r["ok"] is False and r.get("fehler")
    assert r.get("geschrieben") is not True
    assert sorted(p.name for p in basis.iterdir()) == vorher          # keine neue Datei
    assert _protokoll(basis) == protokoll
    assert not (basis / gq.KORREKTUREN_DATEINAME).exists()
    assert "zugeordnet" not in _vorgaben(basis)


def test_ein_fehler_in_der_liste_verhindert_auch_die_gueltigen(basis):
    r = gq.bild_rahmen("111", [_neu(), {"gid": "222:0", "name": "Person A"}, _neu(name="X")])
    assert r["ok"] is False
    assert not (basis / gq.KORREKTUREN_DATEINAME).exists()
    assert "111:1000" not in _gesichter("111")


def test_genau_30_aenderungen_sind_erlaubt(basis):
    r = gq.bild_rahmen("111", [_neu(bbox=(0.01 * i, 0.1, 0.05, 0.05)) for i in range(30)])
    assert r["ok"] is True and len(r["neu"]) == 30
    assert r["neu"][0] == "111:1000" and r["neu"][-1] == "111:1029"


def test_bereits_entferntes_gesicht_wird_nicht_nochmal_geaendert(basis):
    assert gq.bild_rahmen("111", [{"gid": "111:1", "entfernen": True}])["ok"] is True
    r = gq.bild_rahmen("111", [{"gid": "111:1", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}])
    assert r["ok"] is False


# ── bild-gesichter: rein additiv ────────────────────────────────────────────

ALTE_FELDER = ("gid", "index", "kennung", "bbox", "breite", "hoehe", "name")


def test_bild_gesichter_alte_felder_unveraendert_neue_kommen_dazu(basis):
    g = _gesichter("111")
    assert [x["gid"] for x in gq.gesichter_auf_bild("111")["gesichter"]] == ["111:0", "111:1"]
    a = g["111:0"]
    assert {k: a[k] for k in ALTE_FELDER} == {
        "gid": "111:0", "index": 0, "kennung": "Person_2001", "bbox": [100, 80, 200, 160],
        "breite": 1000, "hoehe": 800, "name": "Person A"}
    assert a["quelle"] == "erkennung" and a["name_quelle"] == "gruppe"
    assert a["bbox_norm"] == pytest.approx([0.1, 0.1, 0.2, 0.2])
    b = g["111:1"]
    assert b["name"] is None and b["name_quelle"] is None and b["quelle"] == "erkennung"
    # unveraendert auch nach einer Korrektur an einem ANDEREN Bild
    gq.bild_rahmen("222", [_neu()])
    assert {k: _gesichter("111")["111:0"][k] for k in ALTE_FELDER} == {k: a[k] for k in ALTE_FELDER}


def test_hand_gesicht_traegt_auch_bbox_breite_hoehe(basis):
    gq.bild_rahmen("111", [_neu(bbox=(0.1, 0.2, 0.2, 0.25), name="Nur Handy")])
    h = _gesichter("111")["111:1000"]
    assert h["quelle"] == "hand" and h["kennung"] is None and h["index"] == 1000
    assert h["name"] == "Nur Handy" and h["name_quelle"] == "handy"
    assert h["bbox_norm"] == [0.1, 0.2, 0.2, 0.25]
    assert (h["breite"], h["hoehe"]) == (1000, 800)           # Bildmasse der anderen Gesichter
    assert h["bbox"] == [100, 160, 200, 200]


def test_hand_gesicht_auf_bild_ohne_erkennung_nutzt_mitgegebene_masse(basis):
    gq.bild_rahmen("444", [_neu(breite=2000, hoehe=1000)])
    h = _gesichter("444")["444:1000"]
    assert (h["breite"], h["hoehe"]) == (2000, 1000) and h["bbox"] == [200, 200, 400, 250]


def test_hand_gesicht_ohne_bildmasse_hat_keine_pixelwerte(basis):
    gq.bild_rahmen("444", [_neu()])
    h = _gesichter("444")["444:1000"]
    assert h["bbox"] is None and h["breite"] is None and h["hoehe"] is None
    assert h["bbox_norm"] == [0.1, 0.2, 0.2, 0.25]


def test_verschieben_aendert_nur_die_anzeige_die_gruppe_bleibt(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:1", "bbox_norm": [0.5, 0.5, 0.1, 0.125]}])
    assert r["ok"] is True
    g = _gesichter("111")["111:1"]
    assert g["kennung"] == "Person_2003" and g["quelle"] == "erkennung"
    assert g["bbox_norm"] == [0.5, 0.5, 0.1, 0.125]
    assert g["bbox"] == [500, 400, 100, 100] and (g["breite"], g["hoehe"]) == (1000, 800)
    rahmen = _korrekturen(basis)["bilder"]["111"]["rahmen"]["1"]
    assert rahmen == {"bbox_norm": [0.5, 0.5, 0.1, 0.125], "quelle": "erkennung", "name": None}
    assert _vorgaben(basis).get("ausgeschlossen", []) == []         # PC-Daten unberuehrt


def test_reihenfolge_von_links_nach_rechts_auch_nach_verschieben(basis):
    gq.bild_rahmen("111", [{"gid": "111:1", "bbox_norm": [0.02, 0.5, 0.1, 0.1]}])
    assert [g["gid"] for g in gq.gesichter_auf_bild("111")["gesichter"]] == ["111:1", "111:0"]


def test_bild_gesichter_route_liefert_zusammengefuehrte_sicht(basis):
    c = _client()
    r = c.post("/api/gruppen/bild-rahmen", json={"fileid": "111", "aenderungen": [_neu(name="Nur Handy")]})
    assert r.status_code == 200 and r.json()["ok"] is True
    g = c.get("/api/gruppen/bild-gesichter", params={"fileid": "111"}).json()
    assert g["ok"] and [x["gid"] for x in g["gesichter"]] == ["111:0", "111:1000", "111:1"] or \
        sorted(x["gid"] for x in g["gesichter"]) == ["111:0", "111:1", "111:1000"]
    assert c.get("/api/gruppen/bild-gesichter").status_code == 422


def test_route_bild_rahmen_zu_viele_aenderungen_meldet_text_nicht_422(basis):
    r = _client().post("/api/gruppen/bild-rahmen", json={
        "fileid": "111", "aenderungen": [_neu(bbox=(0.1, 0.1, 0.05, 0.05))] * 31}).json()
    assert r["ok"] is False and "30" in r["fehler"]


# ── Entfernen ──────────────────────────────────────────────────────────────

def test_hand_gesicht_entfernen_loescht_nur_den_eigenen_eintrag(basis):
    gq.bild_rahmen("111", [_neu(name="Nur Handy")])
    r = gq.bild_rahmen("111", [{"gid": "111:1000", "entfernen": True}])
    assert r["ok"] is True
    # ein leerer Bildeintrag wird nicht aufbewahrt: kein Rahmen, keine entfernten Gesichter
    eintrag = _korrekturen(basis)["bilder"].get("111", {"rahmen": {}, "entfernt": []})
    assert "1000" not in eintrag["rahmen"] and eintrag["entfernt"] == []
    assert "111:1000" not in _gesichter("111")
    assert _vorgaben(basis).get("ausgeschlossen", []) == []         # keine Gruppenaktion


def test_erkanntes_gesicht_entfernen_anzeige_und_ausschluss(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True}])
    assert r["ok"] is True
    assert _korrekturen(basis)["bilder"]["111"]["entfernt"] == ["0"]
    assert "111:0" not in _gesichter("111")
    assert {"kennung": "Person_2001", "bild_id": "111", "index": 0} in _vorgaben(basis)["ausgeschlossen"]
    _pc_lesen(basis)


def test_entfernen_ohne_vorschlag_eintrag_loest_trotzdem_nicht_den_pc_fehler_aus(basis):
    gq.bild_rahmen("111", [{"gid": "111:1", "entfernen": True}])       # Person_2003 (unbenannt)
    assert {"kennung": "Person_2003", "bild_id": "111", "index": 1} in _vorgaben(basis)["ausgeschlossen"]
    _pc_lesen(basis)


def _pc_neugruppierung(basis, gid, neue_kennung):
    """Simuliert den PC-Lauf: das Gesicht liegt danach in der Gruppe der Zielperson."""
    bild, index = gid.split(":")
    zeilen = copy.deepcopy(ZEILEN)
    for z in zeilen:
        if z["bild_id"] == bild and z["index"] == int(index):
            z["kennung"] = neue_kennung
    _zuordnung_schreiben(basis, zeilen)


def test_entfernen_eines_fest_zugeordneten_gesichts_ohne_pc_fehler_und_rueckgaengig(basis):
    # Zuordnen (Quiz-Weg) -> PC-Neugruppierung -> Entfernen -> PC-Lesen -> Rueckgaengig -> PC-Lesen
    assert gq.zuordnen("Person B", [{"kennung": "Person_2001", "gid": "111:0"}])["zugeordnet"] == 1
    _pc_lesen(basis)
    _pc_neugruppierung(basis, "111:0", "Person_2002")
    vorher = copy.deepcopy(_vorgaben(basis))
    r = gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True}])
    assert r["ok"] is True
    nachher = _vorgaben(basis)
    assert all(not (e["bild_id"] == "111" and e["index"] == 0) for e in nachher.get("zugeordnet", []))
    assert {"kennung": "Person_2002", "bild_id": "111", "index": 0} in nachher["ausgeschlossen"]
    _pc_lesen(basis)                                                  # kein PersonenFehler
    eintrag = [e for e in _protokoll(basis) if e["art"] == "ausschliessen"][-1]
    assert eintrag["vorher_zugeordnet"] and eintrag["vorher_zugeordnet"][0]["name"] == "Person B"
    assert gq.rueckgaengig()["ok"] is not False
    assert _vorgaben(basis) == vorher
    _pc_lesen(basis)
    assert "111:0" in _gesichter("111")


def test_ohne_aufheben_wuerde_der_pc_leser_abbrechen_gegenprobe(basis):
    """Belegt, WARUM Entfernen erst aufhebt: der alte Ausschluss-Weg erzeugt den Widerspruch."""
    gq.zuordnen("Person B", [{"kennung": "Person_2001", "gid": "111:0"}])
    _pc_neugruppierung(basis, "111:0", "Person_2002")
    assert gq.ausschliessen("Person_2002", ["111:0"])["ok"] is True   # alter Weg, ohne Aufheben
    pg = _werkzeug("personen_gruppieren")
    with pytest.raises(pg.PersonenFehler):
        _pc_lesen(basis)


def test_ausschliessen_mit_aufheben_hebt_alle_zuordnungen_des_gesichts_auf(basis):
    gq.zuordnen("Person B", [{"kennung": "Person_2001", "gid": "111:0"}])
    gq.zuordnen("Person A", [{"kennung": "Person_2001", "gid": "111:0"}])
    assert gq.ausschliessen("Person_2001", ["111:0"], aufheben=True)["ok"] is True
    assert not [e for e in _vorgaben(basis).get("zugeordnet", [])
                if e["bild_id"] == "111" and e["index"] == 0]
    eintrag = _protokoll(basis)[-1]
    assert eintrag["art"] == "ausschliessen" and len(eintrag["vorher_zugeordnet"]) == 2
    _pc_lesen(basis)
    gq.rueckgaengig()
    zug = [e for e in _vorgaben(basis)["zugeordnet"] if e["bild_id"] == "111"]
    assert [e["name"] for e in zug] == ["Person B", "Person A"]       # Reihenfolge erhalten


def test_ausschliessen_ohne_aufheben_bleibt_wie_vorher(basis):
    gq.zuordnen("Person B", [{"kennung": "Person_2001", "gid": "111:0"}])
    gq.ausschliessen("Person_2002", ["111:0"]) if False else None
    assert gq.ausschliessen("Person_2001", ["111:1"]) == {
        "ok": False, "fehler": "Gesicht gehört nicht (mehr) zu diesem Vorschlag."}
    assert gq.ausschliessen("Person_2003", ["111:1"])["ok"] is True
    assert "vorher_zugeordnet" not in _protokoll(basis)[-1]


# ── Namen: zuordnen oder handy-eigen ────────────────────────────────────────

def test_name_einer_benannten_person_geht_den_zuordnen_weg(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:1", "name": "person b"}])      # Gross/Klein egal
    assert r["ok"] is True
    zug = _vorgaben(basis)["zugeordnet"]
    assert [(e["bild_id"], e["index"], e["name"], e["kennung"]) for e in zug] == [
        ("111", 1, "Person B", "Person_2003")]
    g = _gesichter("111")["111:1"]
    assert g["name"] == "Person B" and g["name_quelle"] == "zuordnung"
    assert _korrekturen(basis) is None                                   # nichts Handy-eigenes noetig


def test_neuer_name_bleibt_handy_eigen_und_erreicht_den_pc_nicht(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:1", "name": "  Nur   Handy "}])
    assert r["ok"] is True
    g = _gesichter("111")["111:1"]
    assert g["name"] == "Nur Handy" and g["name_quelle"] == "handy" and g["kennung"] == "Person_2003"
    assert _korrekturen(basis)["bilder"]["111"]["rahmen"]["1"]["name"] == "Nur Handy"
    assert "zugeordnet" not in _vorgaben(basis)
    assert "Nur Handy" not in json.dumps(_vorgaben(basis))
    assert "Nur Handy" not in json.dumps(gq.bestaetigt_lesen())


def test_vorgaben_bekommen_nie_index_ab_1000_oder_hand_namen(basis):
    gq.bild_rahmen("111", [_neu(name="Nur Handy"), _neu(name="Person B", bbox=(0.5, 0.5, 0.1, 0.1)),
                           {"gid": "111:1", "name": "Person B"}, {"gid": "111:0", "entfernen": True}])
    text = json.dumps(_vorgaben(basis))
    assert "Nur Handy" not in text
    for liste in ("zugeordnet", "ausgeschlossen"):
        for e in _vorgaben(basis).get(liste, []):
            assert int(e["index"]) < 1000
    _pc_lesen(basis)


def test_handy_name_ersetzt_gruppennamen_und_zuordnen_loescht_ihn_wieder(basis):
    gq.bild_rahmen("111", [{"gid": "111:0", "name": "Ersatz"}])
    assert _gesichter("111")["111:0"]["name"] == "Ersatz"
    gq.bild_rahmen("111", [{"gid": "111:0", "name": "Person B"}])        # jetzt eine echte Zuordnung
    g = _gesichter("111")["111:0"]
    assert g["name"] == "Person B" and g["name_quelle"] == "zuordnung"
    assert _korrekturen(basis)["bilder"].get("111", {}).get("rahmen", {}).get("0") is None
    _pc_lesen(basis)


def test_name_gleich_dem_gruppennamen_aendert_nichts_in_den_vorgaben(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:0", "name": "Person A"}])
    assert r["ok"] is True
    assert "zugeordnet" not in _vorgaben(basis)
    assert _gesichter("111")["111:0"]["name_quelle"] == "gruppe"


@pytest.mark.parametrize("wege", ["quiz", "bild_rahmen"])
def test_namenswechsel_a_b_a_pc_leser_ohne_fehler_und_rueckgaengig_stellt_b_her(basis, wege):
    def wechsel(name):
        if wege == "quiz":
            r = gq.zuordnen(name, [{"kennung": "Person_2001", "gid": "111:0"}])
        else:
            r = gq.bild_rahmen("111", [{"gid": "111:0", "name": name}])
        assert r["ok"] is True

    wechsel("Person B")
    _pc_lesen(basis)
    assert {"kennung": "Person_2001", "bild_id": "111", "index": 0} in _vorgaben(basis)["ausgeschlossen"]
    wechsel("Person A")
    _pc_lesen(basis)                                                      # kein PersonenFehler
    assert {"kennung": "Person_2001", "bild_id": "111", "index": 0} not in _vorgaben(basis)["ausgeschlossen"]
    zuordnen_eintraege = [e for e in _protokoll(basis) if e["art"] == "zuordnen"]
    assert zuordnen_eintraege[-1]["ausschluesse_aufgehoben"] == [["Person_2001", "111:0"]]
    assert gq.rueckgaengig()["ok"] is not False
    _pc_lesen(basis)
    assert {"kennung": "Person_2001", "bild_id": "111", "index": 0} in _vorgaben(basis)["ausgeschlossen"]
    zug = [e for e in _vorgaben(basis)["zugeordnet"] if e["bild_id"] == "111"]
    assert [e["name"] for e in zug] == ["Person B"]
    assert _gesichter("111")["111:0"]["name"] == "Person B"


def test_zuordnen_hebt_nur_ausschluesse_gegen_das_neue_ziel_auf(basis):
    gq.ausschliessen("Person_2001", ["111:0"])                            # „ist nicht Person A"
    gq.ausschliessen("Person_2001", ["333:0"])
    assert gq.zuordnen("Person A", [{"kennung": "Person_2001", "gid": "111:0"}])["zugeordnet"] == 1
    aus = _vorgaben(basis)["ausgeschlossen"]
    assert {"kennung": "Person_2001", "bild_id": "333", "index": 0} in aus
    assert {"kennung": "Person_2001", "bild_id": "111", "index": 0} not in aus
    _pc_lesen(basis)


# ── Teilfehler und Rueckgaengig ─────────────────────────────────────────────

def test_protokoll_bild_rahmen_mit_vorher_nur_dieser_fileid(basis):
    gq.bild_rahmen("222", [_neu(name="Anderes Bild")])
    erstes = copy.deepcopy(_korrekturen(basis)["bilder"]["222"])
    r = gq.bild_rahmen("111", [_neu(name="Nur Handy")])
    eintrag = [e for e in _protokoll(basis) if e["art"] == "bild_rahmen"][-1]
    assert eintrag["fileid"] == "111" and eintrag["vorher"] is None and eintrag["aktion"] == r["aktion"]
    gq.bild_rahmen("222", [_neu(bbox=(0.5, 0.5, 0.1, 0.1))])
    zweiter = [e for e in _protokoll(basis) if e["art"] == "bild_rahmen"][-1]
    assert zweiter["fileid"] == "222" and zweiter["vorher"] == erstes
    assert "111" not in json.dumps(zweiter["vorher"])


def test_rueckgaengig_bild_rahmen_stellt_genau_den_vorherigen_eintrag_her(basis):
    gq.bild_rahmen("111", [_neu(name="Eins")])
    vor_zweitem = copy.deepcopy(_korrekturen(basis)["bilder"]["111"])
    gq.bild_rahmen("222", [_neu(name="Zwei")])
    gq.bild_rahmen("111", [_neu(bbox=(0.5, 0.5, 0.1, 0.1), name="Drei")])
    # fremde Aenderung eines ANDEREN Bildes ohne Protokoll (Zwischenaktion)
    daten = _korrekturen(basis)
    daten["bilder"]["999"] = {"rahmen": {"1000": {"bbox_norm": [0.1, 0.1, 0.2, 0.2],
                                                     "quelle": "hand", "name": "Fremd"}}, "entfernt": []}
    (basis / gq.KORREKTUREN_DATEINAME).write_text(json.dumps(daten), encoding="utf-8")
    r = gq.rueckgaengig()
    assert r["ok"] is not False and r["zurueckgenommen"]["art"] == "bild_rahmen"
    jetzt = _korrekturen(basis)["bilder"]
    assert jetzt["111"] == vor_zweitem
    assert jetzt["222"]["rahmen"]["1000"]["name"] == "Zwei"               # anderes Bild unberuehrt
    assert jetzt["999"]["rahmen"]["1000"]["name"] == "Fremd"             # fremde Aenderung bleibt
    zeile = [e for e in _protokoll(basis) if e["art"] == "rueckgaengig"][-1]
    drei = [e for e in _protokoll(basis) if e["art"] == "bild_rahmen"][-1]
    assert zeile["bezug"] == drei["id"]
    # der Eintrag ist danach nicht mehr offen: das naechste Rueckgaengig nimmt „Zwei" zurueck
    gq.rueckgaengig()
    assert "222" not in _korrekturen(basis)["bilder"]
    assert _korrekturen(basis)["bilder"]["111"] == vor_zweitem


def test_rueckgaengig_nach_erstem_eintrag_entfernt_den_bildeintrag(basis):
    gq.bild_rahmen("111", [_neu(name="Eins")])
    gq.rueckgaengig()
    assert _korrekturen(basis)["bilder"] == {}
    # der Eintrag ist zurueckgenommen: das naechste Rueckgaengig trifft die Einrichtung (Namen), nicht das Bild
    weiter = gq.rueckgaengig()
    assert weiter["zurueckgenommen"]["art"] != "bild_rahmen"
    assert _korrekturen(basis)["bilder"] == {}


def test_ein_aufruf_mit_entfernen_und_zuordnen_ein_rueckgaengig_nimmt_alles_zurueck(basis):
    gq.zuordnen("Person B", [{"kennung": "Person_2001", "gid": "333:0"}])     # ist „fremd" zum Aufruf
    # Setup abgeschlossen: Zustand vor dem Aufruf merken
    korr_vorher = _korrekturen(basis)
    vorg_vorher = copy.deepcopy(_vorgaben(basis))
    protokoll_vorher = len(_protokoll(basis))
    r = gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True},
                               {"gid": "111:1", "name": "Person B"},
                               _neu(name="Nur Handy")])
    assert r["ok"] is True
    neu = _protokoll(basis)[protokoll_vorher:]
    assert {e["art"] for e in neu} == {"bild_rahmen", "zuordnen", "ausschliessen"}
    assert len({e["aktion"] for e in neu}) == 1 and neu[0]["aktion"] == r["aktion"]
    assert _korrekturen(basis) is not None and _vorgaben(basis) != vorg_vorher
    res = gq.rueckgaengig()
    assert res["ok"] is not False
    assert _korrekturen(basis) == (korr_vorher if korr_vorher is not None else {"version": 1, "bilder": {}})
    assert _vorgaben(basis) == vorg_vorher
    zeilen = _protokoll(basis)
    zurueck = [e for e in zeilen[protokoll_vorher + len(neu):] if e["art"] == "rueckgaengig"]
    assert [z["bezug"] for z in zurueck] == [e["id"] for e in reversed(neu)]   # umgekehrte Reihenfolge
    assert zurueck[-1]["bezug"] == [e for e in neu if e["art"] == "bild_rahmen"][0]["id"]
    # keiner der Eintraege ist noch offen: das naechste Rueckgaengig trifft den Setup-Schritt davor
    assert gq.rueckgaengig()["zurueckgenommen"]["art"] == "zuordnen"
    assert 111 and "111:0" in _gesichter("111")


def test_teilfehler_im_zuordnen_teil_wird_gemeldet_und_korrekturen_bleiben(basis, monkeypatch):
    echt = gq.zuordnen
    monkeypatch.setattr(gq, "zuordnen", lambda *a, **k: {"ok": False, "fehler": "Speichern fehlgeschlagen (OSError)."})
    r = gq.bild_rahmen("111", [{"gid": "111:1", "name": "Person B"}, _neu(name="Nur Handy")])
    monkeypatch.setattr(gq, "zuordnen", echt)
    assert r["ok"] is False and r["teilweise"] is True and r["geschrieben"] is True
    teile = {t["teil"]: t for t in r["teile"]}
    assert teile["korrekturen"]["ok"] is True
    assert teile["zuordnen"]["ok"] is False and "Speichern" in teile["zuordnen"]["fehler"]
    assert "Person B" in r["fehler"] and "nicht übernommen" in r["fehler"]
    assert "111:1000" in _gesichter("111")                                  # (2) blieb gespeichert
    assert "zugeordnet" not in _vorgaben(basis)
    # ein Rueckgaengig nimmt den gespeicherten Teil zurueck — kein halber Zustand bleibt offen
    assert gq.rueckgaengig()["ok"] is not False
    assert "111:1000" not in _gesichter("111")


def test_teilfehler_im_ausschliessen_teil(basis, monkeypatch):
    monkeypatch.setattr(gq, "ausschliessen", lambda *a, **k: {"ok": False, "fehler": "Gesicht gehört nicht (mehr) zu diesem Vorschlag."})
    r = gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True}])
    assert r["ok"] is False and r["teilweise"] is True
    assert {t["teil"]: t["ok"] for t in r["teile"]} == {"korrekturen": True, "ausschliessen": False}
    assert _korrekturen(basis)["bilder"]["111"]["entfernt"] == ["0"]


def test_erfolgsantwort_nennt_jeden_teil_und_die_neue_sicht(basis):
    r = gq.bild_rahmen("111", [{"gid": "111:1", "name": "Person B"}, _neu(name="Nur Handy")])
    assert r["ok"] is True and r["teilweise"] is False and r["fileid"] == "111"
    assert {t["teil"] for t in r["teile"]} == {"korrekturen", "zuordnen"}
    assert all(t["ok"] for t in r["teile"])
    assert {g["gid"] for g in r["gesichter"]} == {"111:0", "111:1", "111:1000"}


# ── „Bilder mit X" und Erzaehlen lesen dieselbe Sicht ───────────────────────

def test_bilder_mit_findet_bild_mit_nur_einem_hand_gesicht(basis):
    assert "444" not in [t["fileid"] for t in gq.bilder_mit(["Person A"])["treffer"]]
    gq.bild_rahmen("444", [_neu(name="Person A")])                         # Bild ohne Erkennung
    treffer = [t["fileid"] for t in gq.bilder_mit(["Person A"])["treffer"]]
    assert "444" in treffer and "111" in treffer and "333" in treffer
    assert 444 in gq.bild_kennungen_person("Person A")["kennungen"]


def test_bilder_mit_kennt_handy_eigene_namen(basis):
    gq.bild_rahmen("444", [_neu(name="Nur Handy")])
    r = gq.bilder_mit(["Nur Handy"])
    assert [t["fileid"] for t in r["treffer"]] == ["444"] and r["unbekannte_namen"] == []
    k = gq.bild_kennungen_person("Nur Handy")
    assert k["kennungen"] == [444] and k["unbekannt"] is False
    assert gq.bild_kennungen_person("Niemand Bekannt")["unbekannt"] is True


def test_bilder_mit_entferntes_gesicht_zaehlt_nicht(basis):
    gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True}])
    treffer = [t["fileid"] for t in gq.bilder_mit(["Person A"])["treffer"]]
    assert "111" not in treffer and "333" in treffer
    assert gq.bild_kennungen_person("Person A")["kennungen"] == [333]


def test_bilder_mit_handy_ersatzname_ersetzt_den_gruppennamen(basis):
    gq.bild_rahmen("111", [{"gid": "111:0", "name": "Nur Handy"}])
    assert [t["fileid"] for t in gq.bilder_mit(["Person A"])["treffer"]] == ["333"]
    assert "111" in [t["fileid"] for t in gq.bilder_mit(["Nur Handy"])["treffer"]]


def test_bilder_mit_ohne_korrekturen_unveraendert(basis):
    r = gq.bilder_mit(["Person A"])
    assert sorted(t["fileid"] for t in r["treffer"]) == ["111", "333"]
    assert gq.bilder_mit(["Person A", "Person B"], "eine")["anzahl"] == 3


def test_personen_auf_bildern_hand_gesicht_mit_name_in_zeile_und_zaehlung(basis):
    gq.bild_rahmen("111", [_neu(name="Nur Handy")])
    gq.bild_rahmen("222", [_neu(name="Nur Handy", bbox=(0.5, 0.5, 0.1, 0.1))])
    r = gq.personen_auf_bildern(["111", "222", "333"])
    assert "Nur Handy" in r["bilder"]["111"]["namen"] and "Person A" in r["bilder"]["111"]["namen"]
    assert r["bilder"]["222"]["namen"] == ["Nur Handy", "Person B"]
    zaehlung = {e["name"]: e["bilder"] for e in r["benannt"]}
    assert zaehlung["Nur Handy"] == 2 and zaehlung["Person A"] == 2


def test_personen_auf_bildern_hand_gesicht_ohne_name_zaehlt_als_unbenannt(basis):
    gq.bild_rahmen("444", [_neu()])
    r = gq.personen_auf_bildern(["444"])
    assert r["bilder"]["444"]["namen"] == [] and len(r["bilder"]["444"]["ohne_namen"]) == 1
    assert r["mit_personen"] == 1 and r["ohne_namen"]["bilder"] == 1


def test_personen_auf_bildern_handy_ersatzname_ersetzt_gruppennamen(basis):
    gq.bild_rahmen("111", [{"gid": "111:0", "name": "Ersatz"}, {"gid": "111:1", "name": "Nur Handy"}])
    r = gq.personen_auf_bildern(["111", "333"])
    assert r["bilder"]["111"]["namen"] == ["Ersatz", "Nur Handy"]
    assert r["bilder"]["111"]["ohne_namen"] == []
    zaehlung = {e["name"]: e["bilder"] for e in r["benannt"]}
    assert zaehlung.get("Person A") == 1 and zaehlung["Ersatz"] == 1       # 111 zaehlt nicht mehr als „Person A"


def test_personen_auf_bildern_entferntes_gesicht_faellt_aus_zeile_und_zaehlung(basis):
    gq.bild_rahmen("111", [{"gid": "111:0", "entfernen": True}])
    r = gq.personen_auf_bildern(["111", "333"])
    assert "Person A" not in r["bilder"]["111"]["namen"]
    assert {e["name"]: e["bilder"] for e in r["benannt"]}["Person A"] == 1
    assert r["bilder"]["111"]["ohne_namen"] == ["Person_2003"]


def test_personen_auf_bildern_ohne_korrekturen_unveraendert(basis):
    r = gq.personen_auf_bildern(["111", "222", "333", "999"])
    assert r["bilder"]["111"] == {"namen": ["Person A"], "ohne_namen": ["Person_2003"]}
    assert r["bilder"]["222"] == {"namen": ["Person B"], "ohne_namen": []}
    assert {e["name"]: e["bilder"] for e in r["benannt"]} == {"Person A": 2, "Person B": 1}


def test_erzaehlen_route_nutzt_dieselbe_sicht():
    """Die Route ereignisse/<k>/personen ruft personen_auf_bildern — keine zweite Logik."""
    text = Path(BACKEND, "app", "router", "erzaehlen.py").read_text(encoding="utf-8")
    assert "gruppen_quiz.personen_auf_bildern(" in text


def test_gemeinsamer_helfer_statt_zweiter_logik():
    """bild-gesichter, „Bilder mit X" und Erzaehlen laufen ueber _bild_sicht."""
    quelle = Path(gq.__file__).read_text(encoding="utf-8")
    for funktion in ("gesichter_auf_bild", "bilder_mit", "bild_kennungen_person", "personen_auf_bildern"):
        rumpf = quelle.split(f"def {funktion}(", 1)[1].split("\ndef ", 1)[0]
        assert "_bild_sicht(" in rumpf or "_sicht_namen(" in rumpf, funktion


# ── Sperrliste handy-eigener Namen ──────────────────────────────────────────

def _tool(name, unterordner):
    pfad = Path(PROJEKT, "tools", unterordner, name + ".py")
    spez = importlib.util.spec_from_file_location(name + "_b1", pfad)
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name + "_b1"] = modul
    spez.loader.exec_module(modul)
    return modul


def test_gleicher_name_in_allen_drei_stellen():
    holen = _tool("pcloud_dateien_holen", "handy")
    hochladen = _tool("uebergabe_hochladen", "pcloud")
    assert gq.KORREKTUREN_DATEINAME == "bild_korrekturen.json"
    assert gq.KORREKTUREN_DATEINAME in holen.HANDY_EIGENE_NAMEN
    assert gq.KORREKTUREN_DATEINAME in hochladen.HANDY_EIGENE_NAMEN


def test_holer_uebernimmt_bild_korrekturen_nie(tmp_path, monkeypatch):
    import httpx
    holen = _tool("pcloud_dateien_holen", "handy")

    class Antwort:
        def __init__(self, daten=None, content=b""):
            self._d, self.content, self.status_code = daten, content, 200

        def json(self):
            return self._d

    aufrufe = []

    def fake_get(url, params=None, timeout=None):
        aufrufe.append((url, dict(params or {})))
        if url.endswith("/listfolder"):
            return Antwort({"result": 0, "metadata": {"contents": [
                {"name": "bild_korrekturen.json", "fileid": 7, "size": 4, "isfolder": False},
                {"name": "a.json", "fileid": 1, "size": 3, "isfolder": False}]}})
        if url.endswith("/getfilelink"):
            return Antwort({"result": 0, "hosts": ["dl.example"], "path": "/g/" + str(params["fileid"])})
        return Antwort(content=b"abc")

    monkeypatch.setattr(httpx, "get", fake_get)
    meldungen = []
    liste = tmp_path / "liste.txt"
    ziel = tmp_path / "staging"
    bericht = holen.holen(ordner="/Agent/uebergabe", ziel=str(ziel), liste=str(liste),
                          token="test-token-nicht-echt", host="eapi.test.example",
                          protokoll=meldungen.append)
    assert bericht["geholt"] == ["a.json"] and bericht["fehler"] == []
    assert not (ziel / "bild_korrekturen.json").exists()
    assert "bild_korrekturen.json" not in liste.read_text(encoding="utf-8")
    assert any("bild_korrekturen.json" in m and "übersprungen: handy-eigen" in m for m in meldungen)
    assert not any(p.get("fileid") == 7 for _u, p in aufrufe)              # nicht einmal heruntergeladen


def test_uploader_lehnt_den_namen_im_ordner_modus_ab(tmp_path):
    hochladen = _tool("uebergabe_hochladen", "pcloud")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bild_korrekturen.json").write_text("{}", encoding="utf-8")
    with pytest.raises(hochladen.UebergabeFehler) as fehler:
        hochladen.dateien_sammeln(None, str(tmp_path))
    assert "handy-eigen" in str(fehler.value)


def test_uploader_lehnt_den_namen_auch_als_einzeldatei_und_beim_hochladen_ab(tmp_path):
    hochladen = _tool("uebergabe_hochladen", "pcloud")
    datei = tmp_path / "bild_korrekturen.json"
    datei.write_text("{}", encoding="utf-8")
    with pytest.raises(hochladen.UebergabeFehler):
        hochladen.dateien_sammeln([str(datei)], None)
    with pytest.raises(hochladen.UebergabeFehler):
        hochladen.hochladen("bild_korrekturen.json", b"{}", 1, token="x", host="h",
                                  senden=lambda *a, **k: pytest.fail("darf nicht senden"))


# ── Ergebnisprüfung Codex R1 (nicht sperrend, umgesetzt) ────────────────────

def test_fremde_schluessel_im_bildeintrag_bleiben_erhalten(basis):
    # R1-1: neu_bild wurde frisch gebaut -> fremde Schlüssel gingen verloren
    gq.bild_rahmen("111", [_neu(name="Nur Handy")])
    daten = _korrekturen(basis)
    daten["bilder"]["111"]["notiz_spaeter"] = {"x": 1}
    (basis / gq.KORREKTUREN_DATEINAME).write_text(json.dumps(daten), encoding="utf-8")
    gq._CACHE.clear()
    r = gq.bild_rahmen("111", [{"gid": "111:1000", "name": "Anderer Name"}])
    assert r["ok"] is True
    eintrag = _korrekturen(basis)["bilder"]["111"]
    assert eintrag["notiz_spaeter"] == {"x": 1}
    assert eintrag["rahmen"]["1000"]["name"] == "Anderer Name"
    # gleicher Name nochmal: keine echte Änderung -> kein Schreiben, kein Protokolleintrag
    anzahl = len(_protokoll(basis))
    r = gq.bild_rahmen("111", [{"gid": "111:1000", "name": "Anderer Name"}])
    assert r["ok"] is True and r["teile"][0]["geaendert"] is False
    assert len(_protokoll(basis)) == anzahl


def test_foto_gesicht_mit_index_ab_1000_ergibt_klartext_statt_absturz(basis):
    # R1-2: Index >= 1000 in der Zuordnungsdatei (Foto-Gesicht) darf keinen KeyError werfen
    _zuordnung_schreiben(basis, ZEILEN + [_zeile(444, 1000, "Person_2004", [10, 10, 50, 50])])
    r = gq.bild_rahmen("444", [{"gid": "444:1000", "bbox_norm": [0.1, 0.1, 0.2, 0.2]}])
    assert r["ok"] is False and isinstance(r.get("fehler"), str) and r["fehler"]
    assert _korrekturen(basis) is None
