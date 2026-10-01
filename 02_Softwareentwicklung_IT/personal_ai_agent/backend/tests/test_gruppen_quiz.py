"""Tests: Personen benennen im Gruppenmodus (app/services/gruppen_quiz.py, 01.10.2026).

Offline, erfundene Gruppen in ``tmp_path`` (GRUPPEN_QUIZ_BASIS). Geprueft wird
vor allem, dass die geschriebenen Dateien GENAU das Format haben, das
``tools/foto_sortierung/personen_gruppieren.py`` beim naechsten PC-Lauf liest —
dafuer werden dessen eigene Lesefunktionen benutzt.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppen_quiz.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")

from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402


def _werkzeug(name):
    sys.path.insert(0, WERKZEUGE)
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def _beispiel(fileid, jahr="2022", bbox=(10, 20, 30, 40)):
    return {"bild_id": str(fileid), "index": 0, "bbox": list(bbox), "breite": 1000,
            "hoehe": 750, "anteil": 0.01, "score": 0.9, "aufnahme": f"{jahr}-06-18T11:21:00"}


GRUPPEN = [
    {"kennung": "Person_1002", "groesse": 40, "bilder": 30, "videos": 1, "von": "2016-01-01",
     "bis": "2025-08-01", "zwilling_kandidaten": [], "beispiele": [_beispiel(200 + i) for i in range(10)]},
    {"kennung": "Person_1001", "groesse": 120, "bilder": 90, "videos": 3, "von": "2015-01-01",
     "bis": "2025-09-01",
     "zwilling_kandidaten": [{"kennung": "Person_1003", "aehnlich": 0.52, "gemeinsame_bilder": 4}],
     "beispiele": [_beispiel(100), _beispiel("12345#t=4"), {"bild_id": "101", "bbox": None},
                   _beispiel(102, "2019")]},
    {"kennung": "Person_1003", "groesse": 15, "bilder": 15, "videos": 0, "von": None, "bis": None,
     "zwilling_kandidaten": [{"kennung": "Person_1001", "aehnlich": 0.52, "gemeinsame_bilder": 4}],
     "beispiele": [_beispiel(300)]},
    {"kennung": "Person_1004", "groesse": 5, "bilder": 5, "videos": 0, "von": None, "bis": None,
     "zwilling_kandidaten": [], "beispiele": [_beispiel(400)]},
]


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({"stand": "2026-10-01T01:00:00", "verfahren": "mittelpunkt", "gruppen": GRUPPEN}),
        encoding="utf-8")
    yield tmp_path
    gq._CACHE.clear()


def _json(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


# ── Fehlende Dateien ────────────────────────────────────────────────────────

def test_ohne_gruppendatei_ehrlicher_hinweis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    s = gq.stand()
    assert s["ok"] is False and s["vorhanden"] is False
    assert "personen_gruppieren.py --schreiben" in s["fehler"]
    assert gq.naechste()["ok"] is False
    assert gq.bilder_mit(["Leon"])["ok"] is False
    assert list(tmp_path.iterdir()) == []          # nichts angelegt


def test_flache_ablage_der_uebergabe_wird_gefunden(tmp_path, monkeypatch):
    """Am Handy legt die Uebergabe die Datei direkt in ~/foto_sortierung ab."""
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    (tmp_path / gq.BEISPIELE_DATEINAME).write_text(json.dumps({"gruppen": GRUPPEN[:1]}),
                                                   encoding="utf-8")
    assert gq.stand()["gruppen"] == 1


# ── Naechste Gruppe ─────────────────────────────────────────────────────────

def test_groesste_gruppe_zuerst_mit_sauberen_beispielen(basis):
    n = gq.naechste()
    g = n["gruppe"]
    assert n["ok"] and not n["fertig"] and n["offen"] == 4
    assert g["kennung"] == "Person_1001" and g["groesse"] == 120
    # Video-Standbild und Beispiel ohne Rahmen fallen weg (kein Vorschaubild).
    assert [b["fileid"] for b in g["beispiele"]] == ["100", "102"]
    assert g["beispiele"][0]["aufnahme"] == "2022-06-18"
    z = g["zwillinge"][0]
    assert z["kennung"] == "Person_1003" and z["beispiel"]["fileid"] == "300" and z["name"] is None


def test_hoechstens_acht_beispiele(basis):
    gq.antworten("Person_1001", "unbekannt")
    assert len(gq.naechste()["gruppe"]["beispiele"]) == gq.BEISPIELE_MAX


# ── Antworten und Dateiformat ───────────────────────────────────────────────

def test_name_landet_im_format_des_gruppierers(basis):
    pg = _werkzeug("personen_gruppieren")
    r = gq.antworten("Person_1001", "name", "  Leon \t ")
    assert r["ok"] and r["gespeichert"]["name"] == "Leon"
    assert r["gruppe"]["kennung"] == "Person_1002"           # naechstgroesste
    assert pg.bestaetigt_lesen(str(basis / gq.BESTAETIGT_DATEINAME)) == {"Person_1001": "Leon"}
    s = gq.stand()
    assert (s["benannt"], s["offen"], s["gesichter_benannt"]) == (1, 3, 120)
    assert s["namen"] == ["Leon"]


def test_gleicher_name_zweimal_wird_gleich_paar(basis):
    pg = _werkzeug("personen_gruppieren")
    gq.antworten("Person_1001", "name", "Leon")
    gq.antworten("Person_1004", "name", "leon")               # Gross/Klein egal
    vorgaben = pg.vorgaben_lesen(str(basis / gq.VORGABEN_DATEINAME))
    assert vorgaben["gleich"] == {("Person_1001", "Person_1004")}
    assert gq.stand()["namen"] == ["Leon"]


def test_gleich_uebernimmt_den_namen_der_vergleichsgruppe(basis):
    gq.antworten("Person_1003", "name", "Tim")
    r = gq.antworten("Person_1001", "gleich", ziel="Person_1003")
    assert r["ok"] and r["gespeichert"]["name"] == "Tim"
    assert gq.bestaetigt_lesen()["Person_1001"] == "Tim"
    assert gq.vorgaben_lesen()["gleich"] == [["Person_1001", "Person_1003"]]


def test_verschieden_ersetzt_ein_altes_gleich(basis):
    gq.antworten("Person_1001", "gleich", ziel="Person_1003")
    gq.antworten("Person_1001", "verschieden", ziel="Person_1003")
    v = gq.vorgaben_lesen()
    assert v == {"gleich": [], "verschieden": [["Person_1001", "Person_1003"]]}


def test_spaeter_kommt_zum_schluss_wieder_unbekannt_nie(basis):
    gq.antworten("Person_1001", "spaeter")
    gq.antworten("Person_1002", "unbekannt")
    assert gq.naechste()["gruppe"]["kennung"] == "Person_1003"
    gq.antworten("Person_1003", "name", "Tim")
    gq.antworten("Person_1004", "name", "Oma")
    n = gq.naechste()
    assert n["gruppe"]["kennung"] == "Person_1001" and n["gruppe"]["war_spaeter"] is True
    gq.antworten("Person_1001", "name", "Leon")
    assert gq.naechste()["fertig"] is True
    s = gq.stand()
    assert (s["benannt"], s["unbekannt"], s["offen"]) == (3, 1, 0)


def test_sicherung_und_kein_temp_rest(basis):
    gq.antworten("Person_1001", "name", "Leon")
    gq.antworten("Person_1002", "name", "Tim")
    assert _json(basis / (gq.BESTAETIGT_DATEINAME + ".vorher")) == {"bestaetigt": {"Person_1001": "Leon"}}
    assert not list(basis.glob("*.tmp"))


def test_andere_felder_der_namensdatei_bleiben(basis):
    (basis / gq.BESTAETIGT_DATEINAME).write_text(
        json.dumps({"bestaetigt": {"Person_0007": "Mama"}, "hinweis": "von Hand"}), encoding="utf-8")
    gq.antworten("Person_1001", "name", "Leon")
    daten = _json(basis / gq.BESTAETIGT_DATEINAME)
    assert daten["hinweis"] == "von Hand"
    assert daten["bestaetigt"] == {"Person_0007": "Mama", "Person_1001": "Leon"}


@pytest.mark.parametrize("args, teil", [
    (("Person_1001", "name", "   "), "Namen"),
    (("Person_1001", "name", "x" * 61), "zu lang"),
    (("Person_9999", "name", "Leon"), "nicht (mehr)"),
    (("Person_1001", "gleich", None, None), "Vergleichsgruppe"),
    (("Person_1001", "gleich", None, "Person_1001"), "Vergleichsgruppe"),
    (("Person_1001", "loeschen", None), "Unbekannte Antwort"),
])
def test_ungueltige_antworten_schreiben_nichts(basis, args, teil):
    r = gq.antworten(*args)
    assert r["ok"] is False and teil in r["fehler"]
    assert sorted(p.name for p in basis.iterdir()) == [gq.UNTERORDNER]


def test_steuerzeichen_im_namen_fallen_weg():
    assert gq.name_saeubern("Le\x00on\n  Müller") == "Leon Müller"


def test_schreiben_im_projektordner_wird_abgelehnt(monkeypatch):
    ziel = os.path.join(BACKEND, "gruppen_test_tmp")
    os.makedirs(os.path.join(ziel, gq.UNTERORDNER), exist_ok=True)
    try:
        with open(os.path.join(ziel, gq.UNTERORDNER, gq.BEISPIELE_DATEINAME), "w",
                  encoding="utf-8") as d:
            json.dump({"gruppen": GRUPPEN}, d)
        monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", ziel)
        gq._CACHE.clear()
        r = gq.antworten("Person_1001", "name", "Leon")
        assert r["ok"] is False and "Projektordner" in r["fehler"]
        assert not os.path.exists(os.path.join(ziel, gq.BESTAETIGT_DATEINAME))
    finally:
        import shutil
        shutil.rmtree(ziel, ignore_errors=True)
        gq._CACHE.clear()


# ── Rueckgaengig ────────────────────────────────────────────────────────────

def test_rueckgaengig_nimmt_schritt_fuer_schritt_zurueck(basis):
    gq.antworten("Person_1001", "name", "Leon")
    gq.antworten("Person_1004", "name", "Leon")              # + gleich-Paar
    r = gq.rueckgaengig()
    assert r["ok"] and r["zurueckgenommen"] == {"kennung": "Person_1004", "art": "name"}
    assert gq.bestaetigt_lesen() == {"Person_1001": "Leon"}
    assert gq.vorgaben_lesen()["gleich"] == []
    gq.rueckgaengig()
    assert gq.bestaetigt_lesen() == {}
    assert gq.naechste()["gruppe"]["kennung"] == "Person_1001"
    assert gq.rueckgaengig()["ok"] is False                   # nichts mehr da


def test_rueckgaengig_stellt_verschieden_wieder_auf_gleich(basis):
    gq.antworten("Person_1001", "gleich", ziel="Person_1003")
    gq.antworten("Person_1001", "verschieden", ziel="Person_1003")
    gq.rueckgaengig()
    assert gq.vorgaben_lesen() == {"gleich": [["Person_1001", "Person_1003"]], "verschieden": []}


def test_rueckgaengig_von_spaeter_und_unbekannt(basis):
    gq.antworten("Person_1001", "unbekannt")
    assert gq.naechste()["gruppe"]["kennung"] == "Person_1002"
    gq.rueckgaengig()
    assert gq.naechste()["gruppe"]["kennung"] == "Person_1001"


# ── Register: Bilder mit Personen ───────────────────────────────────────────

def _zuordnung(basis):
    zeilen = [
        {"bild_id": "1", "kennung": "Person_1001", "aufnahme": "2022-06-18T11:00:00"},
        {"bild_id": "1", "kennung": "Person_1003", "aufnahme": "2022-06-18T11:00:00"},
        {"bild_id": "2", "kennung": "Person_1001", "aufnahme": "2023-01-01T10:00:00"},
        {"bild_id": "2", "kennung": None},                                     # Rauschen
        {"bild_id": "3", "kennung": "Person_1003", "aufnahme": "2021-05-05T09:00:00"},
        {"bild_id": "3", "kennung": "Person_1002", "aufnahme": "2021-05-05T09:00:00"},
        {"bild_id": "9#t=2", "video_id": "9", "kennung": "Person_1001", "aufnahme": "2020-01-01"},
        {"bild_id": "9#t=4", "video_id": "9", "kennung": "Person_1001", "aufnahme": "2020-01-01"},
    ]
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\nkaputt\n", encoding="utf-8")
    gq.antworten("Person_1001", "name", "Leon")
    gq.antworten("Person_1003", "name", "Tim")
    gq.antworten("Person_1002", "name", "Oma")


def test_bilder_mit_und_oder_genau(basis):
    _zuordnung(basis)
    alle = gq.bilder_mit(["Leon", "Tim"], "alle")
    assert [t["fileid"] for t in alle["treffer"]] == ["1"]
    eine = gq.bilder_mit(["leon", "TIM"], "eine")
    assert [t["fileid"] for t in eine["treffer"]] == ["2", "1", "3", "9"]   # neueste zuerst
    assert (eine["bilder"], eine["videos"]) == (3, 1)
    genau = gq.bilder_mit(["Leon"], "genau")
    assert [t["fileid"] for t in genau["treffer"]] == ["2", "9"]          # Rauschen zaehlt nicht
    assert gq.bilder_mit(["Leon", "Gibtsnicht"], "eine")["unbekannte_namen"] == ["Gibtsnicht"]


def test_bilder_mit_grenzen(basis):
    _zuordnung(basis)
    assert gq.bilder_mit([" "])["ok"] is False
    assert gq.bilder_mit(["Leon"], "vielleicht")["ok"] is False
    r = gq.bilder_mit(["Leon"], "eine", limit=1)
    assert r["anzahl"] == 3 and len(r["treffer"]) == 1


# ── Routen ──────────────────────────────────────────────────────────────────

def test_routen_antworten_immer_mit_200(basis):
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    assert c.get("/api/gruppen/stand").json()["gruppen"] == 4
    assert c.get("/api/gruppen/naechste").json()["gruppe"]["kennung"] == "Person_1001"
    r = c.post("/api/gruppen/antwort", json={"kennung": "Person_1001", "art": "name", "name": "Leon"})
    assert r.status_code == 200 and r.json()["gruppe"]["kennung"] == "Person_1002"
    falsch = c.post("/api/gruppen/antwort", json={"kennung": "Person_1001", "art": "name", "name": ""})
    assert falsch.status_code == 200 and falsch.json()["ok"] is False
    assert c.post("/api/gruppen/rueckgaengig").json()["ok"] is True
    assert c.get("/api/gruppen/bilder", params={"namen": "Leon", "modus": "quatsch"}).status_code == 422


def test_routen_sind_im_backend_mit_schluessel_geschuetzt():
    quelle = open(os.path.join(BACKEND, "app", "main.py"), encoding="utf-8").read()
    assert ("app.include_router(gruppen.router, dependencies=[Depends(auth.require_api_key)])"
            in quelle)


# ── Profil: Beziehung + Erinnerungen (01.10.2026) ───────────────────────────

def test_benennen_mit_beziehung_und_erinnerung_legt_profil_an(basis):
    r = gq.antworten("Person_1001", "name", "Leon", beziehung=" Schul\tfreund ",
                     notiz="Hurricane 2022,\r\nzusammen im Moshpit.\n\n\n\nDanach Pizza.")
    assert r["ok"] and r["gespeichert"]["notiz"] is True
    p = gq.profil("leon")                                     # Gross/Klein egal
    assert p["name"] == "Leon" and p["beziehung"] == "Schul freund"
    assert p["notizen"][0]["text"] == "Hurricane 2022,\nzusammen im Moshpit.\n\nDanach Pizza."
    assert p["notizen"][0]["kennung"] == "Person_1001" and p["notizen"][0]["quelle"] == "quiz"
    daten = _json(basis / gq.PROFILE_DATEINAME)
    assert list(daten["profile"]) == ["Leon"]


def test_weitere_erinnerung_wird_angehaengt_nicht_ersetzt(basis):
    gq.antworten("Person_1001", "name", "Leon", notiz="erste")
    gq.antworten("Person_1004", "name", "LEON", notiz="zweite")       # selbe Person
    r = gq.profil_ergaenzen("Leon", beziehung="bester Freund", notiz="dritte")
    assert r["ok"] and [n["text"] for n in r["notizen"]] == ["erste", "zweite", "dritte"]
    assert r["beziehung"] == "bester Freund"
    assert gq.profil_ergaenzen("Leon")["ok"] is False                  # nichts angegeben


def test_rueckgaengig_markiert_erinnerung_statt_zu_loeschen(basis):
    gq.antworten("Person_1001", "name", "Leon", beziehung="Bruder", notiz="falsch zugeordnet")
    gq.rueckgaengig()
    assert gq.profil("Leon")["notizen"] == [] and gq.profil("Leon")["beziehung"] == ""
    roh = _json(basis / gq.PROFILE_DATEINAME)["profile"]["Leon"]["notizen"]
    assert roh[0]["text"] == "falsch zugeordnet" and roh[0]["zurueckgenommen"] is True


def test_zu_lange_erinnerung_wird_abgelehnt_und_nichts_geschrieben(basis):
    r = gq.antworten("Person_1001", "name", "Leon", notiz="x" * (gq.NOTIZ_MAX + 1))
    assert r["ok"] is False and "zu lang" in r["fehler"]
    assert gq.bestaetigt_lesen() == {}
    assert not (basis / gq.PROFILE_DATEINAME).exists()


def test_profil_routen(basis):
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    r = c.post("/api/gruppen/antwort", json={"kennung": "Person_1001", "art": "name", "name": "Leon",
                                             "beziehung": "Bruder", "notiz": "Urlaub 2016"})
    assert r.json()["gespeichert"]["notiz"] is True
    assert c.get("/api/gruppen/profil", params={"name": "Leon"}).json()["beziehung"] == "Bruder"
    r2 = c.post("/api/gruppen/profil", json={"name": "Leon", "notiz": "Geburtstag"})
    assert [n["text"] for n in r2.json()["notizen"]] == ["Urlaub 2016", "Geburtstag"]


# ── „= dieselbe Person" ohne Namen, Namen fuer Verbundene (01.10.2026) ──────
#
# Befund am Handy: „= dieselbe Person" bei einem unbenannten Zwilling liess die
# Oberflaeche dieselbe Frage neu zeichnen ("flackert, nichts passiert").

def test_gleich_ohne_namen_verbindet_und_fragt_nicht_noch_einmal(basis):
    r = gq.antworten("Person_1001", "gleich", ziel="Person_1003")
    assert r["ok"] and r["gespeichert"]["name"] is None
    g = r["gruppe"]
    assert g["kennung"] == "Person_1001"                     # bleibt zum Benennen
    assert g["zwillinge"] == []                              # Frage ist beantwortet
    assert [v["kennung"] for v in g["verbunden"]] == ["Person_1003"]
    assert g["verbunden"][0]["beispiel"]["fileid"] == "300"  # Bild kommt dazu


def test_verschieden_fragt_nicht_noch_einmal(basis):
    r = gq.antworten("Person_1001", "verschieden", ziel="Person_1003")
    assert r["gruppe"]["kennung"] == "Person_1001"
    assert r["gruppe"]["zwillinge"] == [] and r["gruppe"]["verbunden"] == []


def test_name_gilt_fuer_alle_verbundenen_und_rueckgaengig_nimmt_ihn_mit(basis):
    gq.antworten("Person_1001", "gleich", ziel="Person_1003")
    gq.antworten("Person_1003", "gleich", ziel="Person_1004")    # mehrstufig
    r = gq.antworten("Person_1001", "name", "Leon")
    assert gq.bestaetigt_lesen() == {"Person_1001": "Leon", "Person_1003": "Leon",
                                     "Person_1004": "Leon"}
    assert r["gespeichert"]["weitere"] == 2
    assert r["gruppe"]["kennung"] == "Person_1002"               # weiter zur naechsten
    gq.rueckgaengig()
    assert gq.bestaetigt_lesen() == {}
    assert [v["kennung"] for v in gq.naechste()["gruppe"]["verbunden"]] == ["Person_1003", "Person_1004"]


def test_gleich_mit_benanntem_zwilling_benennt_auch_dessen_verbundene(basis):
    gq.antworten("Person_1003", "gleich", ziel="Person_1004")
    gq.antworten("Person_1004", "name", "Tim")                    # 1003 wird mit benannt
    gq.rueckgaengig()
    gq.antworten("Person_1002", "name", "Tim")
    r = gq.antworten("Person_1003", "gleich", ziel="Person_1002")
    assert r["gespeichert"]["name"] == "Tim" and r["gespeichert"]["weitere"] == 1
    assert gq.bestaetigt_lesen() == {"Person_1002": "Tim", "Person_1003": "Tim", "Person_1004": "Tim"}


def test_vorhandene_namen_werden_nie_ueberschrieben(basis):
    gq.antworten("Person_1003", "name", "Tim")
    gq.antworten("Person_1004", "name", "Oma")
    gq.antworten("Person_1003", "gleich", ziel="Person_1004")
    assert gq.bestaetigt_lesen() == {"Person_1003": "Tim", "Person_1004": "Oma"}
