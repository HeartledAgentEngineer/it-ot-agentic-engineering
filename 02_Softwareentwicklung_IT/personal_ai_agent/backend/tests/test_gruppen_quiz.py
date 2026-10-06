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


# ── Kontakte + Suche (02.10.2026, Issue #3 Teil A/B) — erfundene Kontakte ──

KONTAKTE = {"stand": "2026-10-02", "quelle": "telefonbuch-adb", "kontakte": [
    {"id": "11", "name": "Leon Müller", "nummern": ["+4917000000001"], "geburtstag": "1997-03-14"},
    {"id": "12", "name": "Lea Schulz", "nummern": [], "geburtstag": "--08-02"},
    {"id": "13", "name": "Tim Becker", "nummern": ["+4917000000003", "040000003"], "geburtstag": None},
]}


def _kontakte(basis):
    (basis / gq.KONTAKTE_DATEINAME).write_text(json.dumps(KONTAKTE), encoding="utf-8")


def test_suche_findet_wortanfang_umlaute_egal_personen_zuerst(basis):
    _kontakte(basis)
    gq.antworten("Person_1001", "name", "Leo")
    r = gq.suche("le")
    assert r["ok"] and r["kontakte_vorhanden"] is True
    assert [p["name"] for p in r["personen"]] == ["Leo"]
    assert [k["name"] for k in r["kontakte"]] == ["Lea Schulz", "Leon Müller"]
    for frage in ("mül", "muel", "MUL", "leon m"):
        assert [k["id"] for k in gq.suche(frage)["kontakte"]] == ["11"], frage
    assert gq.suche("ller")["kontakte"] == []                         # nur Wortanfang
    leer = gq.suche("")
    assert leer["personen"][0]["name"] == "Leo" and leer["kontakte"] == []   # kein Telefonbuch-Auszug ohne Frage


def test_benennen_mit_kontakt_verknuepft_das_profil(basis):
    _kontakte(basis)
    r = gq.antworten("Person_1001", "name", None, kontakt_id="11")
    assert r["ok"] and r["gespeichert"]["name"] == "Leon Müller" and r["gespeichert"]["kontakt"] is True
    p = gq.profil("Leon Müller")
    assert p["kontakt"]["id"] == "11" and p["kontakt"]["geburtstag"] == "1997-03-14"
    assert p["kontakt"]["nummern"] == ["+4917000000001"]
    assert gq.suche("leon")["kontakte"][0]["verknuepft_mit"] == "Leon Müller"
    assert gq.suche("leon")["personen"][0]["kontakt"] is True


def test_eigener_name_plus_kontakt_bleibt_beim_eigenen_namen(basis):
    _kontakte(basis)
    gq.antworten("Person_1001", "name", "Leo", kontakt_id="11")
    assert gq.bestaetigt_lesen()["Person_1001"] == "Leo"
    assert gq.profil("Leo")["kontakt"]["name"] == "Leon Müller"


def test_unbekannter_kontakt_wird_abgelehnt_und_nichts_geschrieben(basis):
    _kontakte(basis)
    r = gq.antworten("Person_1001", "name", None, kontakt_id="999")
    assert r["ok"] is False and "Telefonbuch" in r["fehler"]
    assert gq.bestaetigt_lesen() == {}


def test_rueckgaengig_nimmt_die_kontakt_verknuepfung_ab(basis):
    _kontakte(basis)
    gq.antworten("Person_1001", "name", None, kontakt_id="13")
    gq.rueckgaengig()
    assert gq.bestaetigt_lesen() == {}
    assert gq.profil("Tim Becker")["kontakt"] is None


def test_suche_ohne_kontaktdatei(basis):
    r = gq.suche("le")
    assert r["ok"] and r["kontakte_vorhanden"] is False and r["kontakte"] == []


def test_suche_route(basis):
    _kontakte(basis)
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    assert [k["id"] for k in c.get("/api/gruppen/suche", params={"q": "tim"}).json()["kontakte"]] == ["13"]
    r = c.post("/api/gruppen/antwort", json={"kennung": "Person_1001", "art": "name", "kontakt_id": "12"})
    assert r.json()["gespeichert"]["name"] == "Lea Schulz"
    assert c.get("/api/gruppen/suche", params={"q": "x" * 61}).status_code == 422


# ── Alle Gesichter eines Vorschlags + Ausschliessen (02.10.2026) ────────────

def _gesichter_datei(basis):
    zeilen = []
    for i in range(60):                                    # 60 Gesichter von Person_1001
        zeilen.append({"bild_id": str(100 + i), "index": 0, "kennung": "Person_1001",
                       "bbox": [10, 20, 30, 40], "breite": 1000, "hoehe": 750,
                       "anteil": 0.01 + i / 1000, "score": 0.9, "aufnahme": "2022-06-18T11:00:00"})
    zeilen.append({"bild_id": "9#t=2", "video_id": "9", "index": 0, "kennung": "Person_1001",
                   "bbox": [1, 1, 1, 1]})                  # Video-Standbild: nicht in der Liste
    zeilen.append({"bild_id": "500", "index": 1, "kennung": "Person_1003", "bbox": [1, 1, 5, 5]})
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")


def test_gesichter_seitenweise_beste_zuerst_ohne_videos(basis):
    _gesichter_datei(basis)
    s1 = gq.gesichter("Person_1001", 1)
    assert s1["ok"] and s1["gesamt"] == 60 and s1["seiten"] == 2 and len(s1["gesichter"]) == 48
    assert s1["gesichter"][0]["gid"] == "159:0"            # groesster Anteil zuerst
    assert all("_guete" not in g for g in s1["gesichter"])
    assert len(gq.gesichter("Person_1001", 2)["gesichter"]) == 12
    assert gq.gesichter("Person_9999")["gesamt"] == 0


def test_ausschliessen_wirkt_sofort_und_im_format_des_gruppierers(basis):
    _gesichter_datei(basis)
    pg = _werkzeug("personen_gruppieren")
    r = gq.ausschliessen("Person_1001", ["100:0", "159:0", "100:0"])
    assert r["ok"] and r["ausgeschlossen"] == 2 and r["gesamt"] == 58
    gids = {g["gid"] for s in (1, 2) for g in gq.gesichter("Person_1001", s)["gesichter"]}
    assert "100:0" not in gids and "159:0" not in gids
    assert pg.vorgaben_lesen(str(basis / gq.VORGABEN_DATEINAME))["ausgeschlossen"] == \
        {("Person_1001", "100", 0), ("Person_1001", "159", 0)}
    # Beispielbild 100 der Gruppe wird nicht mehr gezeigt
    assert "100" not in [b["fileid"] for b in gq.naechste()["gruppe"]["beispiele"]]
    # ein zweites Mal: nichts Neues
    assert gq.ausschliessen("Person_1001", ["100:0"])["ausgeschlossen"] == 0


def test_ausschluss_aendert_bilder_mit(basis):
    _gesichter_datei(basis)
    gq.antworten("Person_1001", "name", "Leon")
    vorher = gq.bilder_mit(["Leon"])["bilder"]
    gq.ausschliessen("Person_1001", ["101:0", "102:0"])
    assert gq.bilder_mit(["Leon"])["bilder"] == vorher - 2


def test_ausschliessen_rueckgaengig(basis):
    _gesichter_datei(basis)
    gq.ausschliessen("Person_1001", ["120:0"])
    r = gq.rueckgaengig()
    assert r["ok"] and r["zurueckgenommen"] == {"kennung": "Person_1001", "art": "ausschliessen", "gesichter": 1}
    assert gq.gesichter("Person_1001")["gesamt"] == 60
    assert gq.ausgeschlossen_lesen() == {}


@pytest.mark.parametrize("gids, teil", [
    ([], "antippen"), (["abc"], "Ungültige"), (["500:1"], "gehört nicht"),
    (["1:0"] * (gq.AUSSCHLUSS_MAX + 1), "Höchstens"),
])
def test_ausschliessen_ungueltig_schreibt_nichts(basis, gids, teil):
    _gesichter_datei(basis)
    r = gq.ausschliessen("Person_1001", gids)
    assert r["ok"] is False and teil in r["fehler"]
    assert not (basis / gq.VORGABEN_DATEINAME).exists()


def test_ausschluss_routen(basis):
    _gesichter_datei(basis)
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    assert c.get("/api/gruppen/gesichter", params={"kennung": "Person_1001", "seite": 2}).json()["seite"] == 2
    r = c.post("/api/gruppen/ausschliessen", json={"kennung": "Person_1001", "gesichter": ["130:0"]})
    assert r.status_code == 200 and r.json()["gesamt"] == 59


# ── Benannte Personen wieder oeffnen und bearbeiten (02.10.2026) ────────────

def _benannt(basis):
    gq.antworten("Person_1001", "name", "Leon", beziehung="Bruder", notiz="Hurricane 2022")
    gq.antworten("Person_1002", "name", "Leon")              # zweiter Vorschlag derselben Person
    gq.antworten("Person_1004", "name", "Tim")


def test_personen_liste_fasst_vorschlaege_zusammen(basis):
    _benannt(basis)
    r = gq.personen()
    assert r["ok"] and [p["name"] for p in r["personen"]] == ["Leon", "Tim"]
    leon = r["personen"][0]
    assert leon["vorschlaege"] == 2 and leon["gesichter"] == 160
    assert leon["beziehung"] == "Bruder" and leon["erinnerungen"] == 1 and leon["kontakt"] is False
    assert leon["beispiel"]["fileid"] == "100"               # aus dem groessten Vorschlag
    assert r["personen"][1]["gesichter"] == 5


def test_personen_liste_ohne_namen_und_ohne_datei(basis, tmp_path, monkeypatch):
    assert gq.personen() == {"ok": True, "personen": []}
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path / "leer"))
    gq._CACHE.clear()
    assert gq.personen()["ok"] is False


def test_person_zeigt_vorschlaege_und_profil(basis):
    _benannt(basis)
    r = gq.person("leon")                                   # Gross/Klein egal
    assert r["ok"] and r["name"] == "Leon"
    assert [v["kennung"] for v in r["vorschlaege"]] == ["Person_1001", "Person_1002"]
    assert len(r["vorschlaege"][1]["beispiele"]) == 8
    assert r["profil"]["beziehung"] == "Bruder"
    assert gq.person("Unbekannt")["ok"] is False


def test_person_ohne_ausgeschlossene_beispiele(basis):
    _benannt(basis)
    _gesichter_datei(basis)
    gq.ausschliessen("Person_1001", ["100:0"])
    v = gq.person("Leon")["vorschlaege"][0]
    assert v["groesse"] == 119 and "100" not in [b["fileid"] for b in v["beispiele"]]


def test_umbenennen_aendert_alle_vorschlaege_und_das_profil(basis):
    _benannt(basis)
    r = gq.umbenennen("Leon", "Leon Maier")
    assert r["ok"] and r["name"] == "Leon Maier" and r["zusammengefuehrt"] is False
    namen = _json(basis / gq.BESTAETIGT_DATEINAME)["bestaetigt"]
    assert namen["Person_1001"] == namen["Person_1002"] == "Leon Maier"
    profile = _json(basis / gq.PROFILE_DATEINAME)["profile"]
    assert "Leon" not in profile and profile["Leon Maier"]["beziehung"] == "Bruder"


def test_umbenennen_auf_vorhandenen_namen_fuehrt_zusammen(basis):
    _benannt(basis)
    gq.profil_ergaenzen("Tim", notiz="Schulfreund")
    r = gq.umbenennen("Tim", "Leon")
    assert r["ok"] and r["zusammengefuehrt"] is True and len(r["vorschlaege"]) == 3
    assert ["Person_1001", "Person_1004"] in _json(basis / gq.VORGABEN_DATEINAME)["gleich"]
    leon = _json(basis / gq.PROFILE_DATEINAME)["profile"]["Leon"]
    assert [n["text"] for n in leon["notizen"]] == ["Hurricane 2022", "Schulfreund"]
    assert leon["beziehung"] == "Bruder"
    assert "Tim" not in _json(basis / gq.PROFILE_DATEINAME)["profile"]


def test_umbenennen_rueckgaengig_stellt_namen_und_profile_her(basis):
    _benannt(basis)
    gq.profil_ergaenzen("Tim", notiz="Schulfreund")
    namen_vorher = _json(basis / gq.BESTAETIGT_DATEINAME)["bestaetigt"]
    profile_vorher = _json(basis / gq.PROFILE_DATEINAME)["profile"]
    gq.umbenennen("Tim", "Leon")
    r = gq.rueckgaengig()
    assert r["ok"] and r["zurueckgenommen"]["art"] == "umbenennen" and r["zurueckgenommen"]["name"] == "Tim"
    assert _json(basis / gq.BESTAETIGT_DATEINAME)["bestaetigt"] == namen_vorher
    assert _json(basis / gq.PROFILE_DATEINAME)["profile"] == profile_vorher
    assert ["Person_1001", "Person_1004"] not in _json(basis / gq.VORGABEN_DATEINAME)["gleich"]


def test_umbenennen_nur_gross_klein_und_rueckgaengig(basis):
    gq.antworten("Person_1004", "name", "tim", beziehung="Freund")
    assert gq.umbenennen("tim", "Tim")["name"] == "Tim"
    assert list(_json(basis / gq.PROFILE_DATEINAME)["profile"]) == ["Tim"]
    gq.rueckgaengig()
    assert list(_json(basis / gq.PROFILE_DATEINAME)["profile"]) == ["tim"]


@pytest.mark.parametrize("alt, neu, teil", [
    ("Leon", "Leon", "unverändert"), ("Niemand", "X", "Keine benannte"), ("Leon", "  ", "Namen"),
])
def test_umbenennen_ungueltig_schreibt_nichts(basis, alt, neu, teil):
    _benannt(basis)
    vorher = (basis / gq.BESTAETIGT_DATEINAME).read_bytes()
    r = gq.umbenennen(alt, neu)
    assert r["ok"] is False and teil in r["fehler"]
    assert (basis / gq.BESTAETIGT_DATEINAME).read_bytes() == vorher


def test_loesen_macht_vorschlag_wieder_offen_und_rueckgaengig(basis):
    _benannt(basis)
    assert ["Person_1001", "Person_1002"] in _json(basis / gq.VORGABEN_DATEINAME)["gleich"]
    r = gq.loesen("Person_1002")
    assert r == {"ok": True, "kennung": "Person_1002", "name": "Leon"}
    assert "Person_1002" not in _json(basis / gq.BESTAETIGT_DATEINAME)["bestaetigt"]
    assert ["Person_1001", "Person_1002"] not in _json(basis / gq.VORGABEN_DATEINAME)["gleich"]
    assert gq.naechste()["gruppe"]["kennung"] == "Person_1002"
    assert len(gq.person("Leon")["vorschlaege"]) == 1
    gq.rueckgaengig()
    assert _json(basis / gq.BESTAETIGT_DATEINAME)["bestaetigt"]["Person_1002"] == "Leon"
    assert ["Person_1001", "Person_1002"] in _json(basis / gq.VORGABEN_DATEINAME)["gleich"]
    assert gq.loesen("Person_1003")["ok"] is False


def test_benannt_routen(basis):
    _benannt(basis)
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    assert [p["name"] for p in c.get("/api/gruppen/personen").json()["personen"]] == ["Leon", "Tim"]
    assert c.get("/api/gruppen/person", params={"name": "Tim"}).json()["vorschlaege"][0]["kennung"] == "Person_1004"
    assert c.get("/api/gruppen/person", params={"name": ""}).status_code == 422
    r = c.post("/api/gruppen/umbenennen", json={"alt": "Tim", "neu": "Timo"})
    assert r.status_code == 200 and r.json()["name"] == "Timo"
    r = c.post("/api/gruppen/loesen", json={"kennung": "Person_1004"})
    assert r.status_code == 200 and r.json()["ok"]


def test_profil_aus_benannt_mit_kontakt_und_rueckgaengig(basis):
    _benannt(basis)
    _kontakte(basis)
    r = gq.profil_ergaenzen("Tim", kontakt_id="13")
    assert r["ok"] and r["kontakt"]["id"] == "13"
    assert gq.personen()["personen"][1]["kontakt"] is True
    assert gq.profil_ergaenzen("Tim", kontakt_id="99")["ok"] is False
    gq.profil_ergaenzen("Leon", beziehung="großer Bruder", notiz="Zelten")
    gq.rueckgaengig()                                        # nimmt die Leon-Aenderung zurueck
    leon = gq.profil("Leon")
    assert leon["beziehung"] == "Bruder" and [n["text"] for n in leon["notizen"]] == ["Hurricane 2022"]
    r = gq.rueckgaengig()                                    # dann die Verknuepfung
    assert r["zurueckgenommen"]["art"] == "profil" and gq.profil("Tim")["kontakt"] is None


# ── Alle Gesichter einer Person ueber alle Vorschlaege (07.10.2026) ─────────

def _person_daten(basis):
    zeilen = []
    for i in range(5):                                    # Leon, Vorschlag 1001
        zeilen.append({"bild_id": str(100 + i), "index": 0, "kennung": "Person_1001",
                       "bbox": [1, 1, 5, 5], "anteil": 0.01 + i / 1000, "score": 0.9})
    for i in range(3):                                    # Leon, Vorschlag 1002 (bessere Gesichter)
        zeilen.append({"bild_id": str(200 + i), "index": 1, "kennung": "Person_1002",
                       "bbox": [1, 1, 5, 5], "anteil": 0.05 + i / 100, "score": 0.9})
    for i in range(2):                                    # Tim
        zeilen.append({"bild_id": str(300 + i), "index": 0, "kennung": "Person_1004",
                       "bbox": [1, 1, 5, 5], "anteil": 0.02, "score": 0.9})
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    gq.antworten("Person_1001", "name", "Leon")
    gq.antworten("Person_1002", "name", "Leon")
    gq.antworten("Person_1004", "name", "Tim")


def test_gesichter_person_ueber_alle_vorschlaege_beste_zuerst(basis):
    _person_daten(basis)
    r = gq.gesichter_person("leon")                        # Gross/Klein egal
    assert r["ok"] and r["name"] == "Leon" and r["kennungen"] == ["Person_1001", "Person_1002"]
    assert r["gesamt"] == 8 and r["seiten"] == 1
    assert [g["gid"] for g in r["gesichter"][:3]] == ["202:1", "201:1", "200:1"]   # beste zuerst
    assert {g["kennung"] for g in r["gesichter"]} == {"Person_1001", "Person_1002"}
    assert all("_guete" not in g for g in r["gesichter"])
    seite2 = gq.gesichter_person("Leon", 2, je_seite=5)
    assert seite2["seiten"] == 2 and len(seite2["gesichter"]) == 3
    assert gq.gesichter_person("Niemand")["ok"] is False


def test_ausschliessen_person_ueber_zwei_vorschlaege_und_rueckgaengig_in_einem_schritt(basis):
    _person_daten(basis)
    r = gq.ausschliessen_person("Leon", [{"kennung": "Person_1001", "gid": "100:0"},
                                         {"kennung": "Person_1002", "gid": "201:1"}])
    assert r["ok"] and r["ausgeschlossen"] == 2 and r["gesamt"] == 6
    assert gq.ausgeschlossen_lesen() == {"Person_1001": {"100:0"}, "Person_1002": {"201:1"}}
    pg = _werkzeug("personen_gruppieren")                 # Format des Gruppierers
    assert pg.vorgaben_lesen(str(basis / gq.VORGABEN_DATEINAME))["ausgeschlossen"] == \
        {("Person_1001", "100", 0), ("Person_1002", "201", 1)}
    z = gq.rueckgaengig()
    assert z["ok"] and z["zurueckgenommen"]["art"] == "ausschliessen" and z["zurueckgenommen"]["gesichter"] == 2
    assert gq.ausgeschlossen_lesen() == {} and gq.gesichter_person("Leon")["gesamt"] == 8


@pytest.mark.parametrize("eintraege, teil", [
    ([], "antippen"),
    ([{"kennung": "Person_1004", "gid": "300:0"}], "nicht zu dieser Person"),   # Tims Gesicht
    ([{"kennung": "Person_1001", "gid": "200:1"}], "nicht (mehr)"),            # falscher Vorschlag
    ([{"kennung": "Person_1001", "gid": "kaputt"}], "Ungültige"),
])
def test_ausschliessen_person_ungueltig_schreibt_nichts(basis, eintraege, teil):
    _person_daten(basis)
    vorher = (basis / gq.VORGABEN_DATEINAME).read_text(encoding="utf-8") \
        if (basis / gq.VORGABEN_DATEINAME).exists() else None
    r = gq.ausschliessen_person("Leon", eintraege)
    assert r["ok"] is False and teil in r["fehler"]
    nachher = (basis / gq.VORGABEN_DATEINAME).read_text(encoding="utf-8") \
        if (basis / gq.VORGABEN_DATEINAME).exists() else None
    assert vorher == nachher


def test_person_routen(basis):
    _person_daten(basis)
    app = FastAPI()
    app.include_router(gruppen_router.router)
    c = TestClient(app)
    r = c.get("/api/gruppen/gesichter", params={"name": "Leon"}).json()
    assert r["ok"] and r["gesamt"] == 8
    assert c.get("/api/gruppen/gesichter").json()["ok"] is False                 # weder kennung noch name
    a = c.post("/api/gruppen/person/ausschliessen",
               json={"name": "Leon", "gesichter": [{"kennung": "Person_1002", "gid": "202:1"}]})
    assert a.status_code == 200 and a.json()["gesamt"] == 7
