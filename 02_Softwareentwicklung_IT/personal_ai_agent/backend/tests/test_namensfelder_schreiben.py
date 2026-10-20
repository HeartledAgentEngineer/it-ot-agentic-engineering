"""Tests: Namensfelder VON HAND setzen (20.10.2026, Namensfelder Schritt 2).

Schritt 1 (``test_name_zerlegen.py``) leitet fehlende Felder beim LESEN ab.
Hier geht es um den Schreibweg: ``profil_ergaenzen`` nimmt Vorname / Nachname /
Spitznamen an, speichert sie im Profil, leert sie auf Wunsch (dann greift die
Ableitung wieder), zieht sie beim Zusammenfuehren (``umbenennen``) mit und stellt
den genauen Vorher-Stand per ``rueckgaengig`` wieder her. Dazu findet die Suche
ueber Vorname, Nachname und Spitznamen.

Offline, ERFUNDENE Namen in ``tmp_path`` (``GRUPPEN_QUIZ_BASIS``) — keine echten
Namen, keine Gesichtsvektoren, keine Bilder, kein Netz, kein Modellaufruf.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_namensfelder_schreiben.py -q
"""
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

GRUPPEN = [
    {"kennung": "Person_1001", "groesse": 120, "bilder": 90, "videos": 3,
     "von": "2015-01-01", "bis": "2025-09-01", "zwilling_kandidaten": [], "beispiele": []},
    {"kennung": "Person_1004", "groesse": 5, "bilder": 5, "videos": 0,
     "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []},
]
BESTAETIGT = {"bestaetigt": {"Person_1001": "Anna Beispiel", "Person_1004": "Tim Beispiel"}}


def _schreibe(pfad, inhalt):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(inhalt, list):
        pfad.write_text("\n".join(json.dumps(z) for z in inhalt) + "\n", encoding="utf-8")
    else:
        pfad.write_text(json.dumps(inhalt), encoding="utf-8")


def _json(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    _schreibe(ordner / gq.BEISPIELE_DATEINAME,
              {"stand": "2026-10-20T00:00:00", "verfahren": "mittelpunkt", "gruppen": GRUPPEN})
    _schreibe(tmp_path / gq.BESTAETIGT_DATEINAME, BESTAETIGT)
    _schreibe(tmp_path / gq.PROFILE_DATEINAME, {"profile": {
        "Anna Beispiel": {"beziehung": "Beispiel-Beziehung", "notizen": [], "kontakt": None},
        "Tim Beispiel": {"beziehung": "", "notizen": [], "kontakt": None},
    }})
    _schreibe(tmp_path / gq.VORGABEN_DATEINAME, {"gleich": [], "verschieden": []})
    yield tmp_path
    gq._CACHE.clear()


def _profil_roh(basis, name):
    return _json(basis / gq.PROFILE_DATEINAME)["profile"][name]


def _klient():
    app = FastAPI()          # der Router bringt sein Praefix /api/gruppen selbst mit
    app.include_router(gruppen_router.router)
    return TestClient(app)


# ── Sauebern der Eingabe (reine Funktion) ───────────────────────────────────

def test_nur_uebergebene_felder_kommen_zurueck():
    assert gq.namensfelder_saeubern() == {}
    assert gq.namensfelder_saeubern(vorname="Anna") == {"vorname": "Anna"}
    assert gq.namensfelder_saeubern(spitznamen=[]) == {"spitznamen": []}


def test_spitznamen_als_liste_und_als_kommatext():
    assert gq.namensfelder_saeubern(spitznamen=["Anni", "Anne"])["spitznamen"] == ["Anni", "Anne"]
    r = gq.namensfelder_saeubern(spitznamen=" Anni , Anne ,, Anni ")
    assert r["spitznamen"] == ["Anni", "Anne"]      # leer weg, doppelt weg


def test_spitznamen_gross_klein_gilt_als_derselbe():
    assert gq.namensfelder_saeubern(spitznamen=["ANNI", "anni"])["spitznamen"] == ["ANNI"]


def test_zu_viele_spitznamen_werden_abgelehnt():
    viele = [f"Spitz{i}" for i in range(gq.SPITZNAMEN_MAX + 1)]
    with pytest.raises(gq.GruppenFehler):
        gq.namensfelder_saeubern(spitznamen=viele)


def test_unbrauchbare_spitznamen_werfen():
    with pytest.raises(gq.GruppenFehler):
        gq.namensfelder_saeubern(spitznamen=7)
    with pytest.raises(gq.GruppenFehler):
        gq.namensfelder_saeubern(spitznamen=["Anni", 7])


def test_zu_langer_vorname_wirft():
    with pytest.raises(gq.GruppenFehler):
        gq.namensfelder_saeubern(vorname="x" * (gq.NAMENSFELD_MAX + 1))


# ── Speichern im Profil ────────────────────────────────────────────────────

def test_vorname_nachname_spitznamen_werden_gespeichert(basis):
    r = gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", nachname="Beispiel",
                            spitznamen=["Anna", "Anni"])
    assert r["ok"] is True
    assert r["namensfelder_quelle"] == "profil"
    assert r["vorname"] == "Anni" and r["nachname"] == "Beispiel"
    assert r["spitznamen"] == ["Anna", "Anni"]
    roh = _profil_roh(basis, "Anna Beispiel")
    assert roh["vorname"] == "Anni" and roh["spitznamen"] == ["Anna", "Anni"]


def test_nur_ein_feld_laesst_die_anderen_unberuehrt(basis):
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", nachname="Beispiel")
    r = gq.profil_ergaenzen("Anna Beispiel", vorname="Anne")
    assert r["vorname"] == "Anne" and r["nachname"] == "Beispiel"
    assert [n["text"] for n in r["notizen"]] == []


def test_leeres_feld_gibt_die_ableitung_zurueck(basis):
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", nachname="Beispiel")
    r = gq.profil_ergaenzen("Anna Beispiel", vorname="")
    assert r["vorname"] == "Anna"                    # abgeleitet aus dem Namen
    assert r["namensfelder_quelle"] == "profil"       # der Nachname ist noch von Hand
    roh = _profil_roh(basis, "Anna Beispiel")
    assert "vorname" not in roh                       # Handfeld ist entfernt


def test_spitznamen_leeren(basis):
    gq.profil_ergaenzen("Tim Beispiel", spitznamen=["Timi"])
    r = gq.profil_ergaenzen("Tim Beispiel", spitznamen=[])
    assert r["spitznamen"] == []
    assert "spitznamen" not in _profil_roh(basis, "Tim Beispiel")


def test_ohne_jede_angabe_kein_schreiben(basis):
    pfad = basis / gq.PROFILE_DATEINAME
    vorher = pfad.read_bytes()
    r = gq.profil_ergaenzen("Anna Beispiel")
    assert r["ok"] is False and "Namen" in r["fehler"]
    assert pfad.read_bytes() == vorher


def test_unbrauchbare_eingabe_schreibt_nichts(basis):
    pfad = basis / gq.PROFILE_DATEINAME
    vorher = pfad.read_bytes()
    assert gq.profil_ergaenzen("Anna Beispiel", vorname="x" * 99)["ok"] is False
    assert gq.profil_ergaenzen("Anna Beispiel",
                               spitznamen=[f"S{i}" for i in range(50)])["ok"] is False
    assert pfad.read_bytes() == vorher


def test_mit_beziehung_zusammen_geht_beides(basis):
    r = gq.profil_ergaenzen("Tim Beispiel", beziehung="Bruder", vorname="Timo")
    assert r["ok"] is True and r["beziehung"] == "Bruder" and r["vorname"] == "Timo"


# ── Rueckgaengig: genauer Vorher-Stand ─────────────────────────────────────

def test_rueckgaengig_entfernt_das_neue_handfeld_wieder(basis):
    vorher = _json(basis / gq.PROFILE_DATEINAME)
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", spitznamen=["Anna"])
    r = gq.rueckgaengig()
    assert r["ok"] is True and r["zurueckgenommen"]["art"] == "profil"
    assert _json(basis / gq.PROFILE_DATEINAME) == vorher


def test_rueckgaengig_stellt_den_alten_wert_wieder_her(basis):
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni")
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anne")
    assert gq.profil_ergaenzen("Anna Beispiel", nachname="Beispiel")["ok"] is True
    assert gq.rueckgaengig()["ok"] is True
    r = gq.profil("Anna Beispiel")
    assert r["vorname"] == "Anne" and r["nachname"] == "Beispiel"   # Handfeld bleibt
    assert gq.rueckgaengig()["ok"] is True
    assert gq.profil("Anna Beispiel")["vorname"] == "Anni"


# ── Zusammenfuehren beim Umbenennen (Auflage aus der Gegenpruefung) ───────

def test_umbenennen_fuehrt_namensfelder_zusammen(basis):
    gq.profil_ergaenzen("Tim Beispiel", vorname="Timo", spitznamen=["Timi"])
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", spitznamen=["Anna", "Timi"])
    r = gq.umbenennen("Tim Beispiel", "Anna Beispiel")
    assert r["ok"] is True and r["zusammengefuehrt"] is True
    roh = _profil_roh(basis, "Anna Beispiel")
    assert roh["vorname"] == "Anni"                   # das Ziel behaelt Vorrang
    assert roh["spitznamen"] == ["Anna", "Timi"]      # vereinigt, ohne Dublette
    assert "Tim Beispiel" not in _json(basis / gq.PROFILE_DATEINAME)["profile"]


def test_zusammenfuehren_holt_fehlende_felder_vom_alten_namen(basis):
    gq.profil_ergaenzen("Tim Beispiel", nachname="Beispiel", vorname="Timo")
    gq.umbenennen("Tim Beispiel", "Anna Beispiel")
    roh = _profil_roh(basis, "Anna Beispiel")
    assert roh["vorname"] == "Timo" and roh["nachname"] == "Beispiel"


def test_umbenennen_rueckgaengig_stellt_auch_namensfelder_her(basis):
    gq.profil_ergaenzen("Tim Beispiel", vorname="Timo", spitznamen=["Timi"])
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni")
    vorher = _json(basis / gq.PROFILE_DATEINAME)      # Stand direkt vor dem Umbenennen
    gq.umbenennen("Tim Beispiel", "Anna Beispiel")
    assert gq.rueckgaengig()["ok"] is True
    assert _json(basis / gq.PROFILE_DATEINAME) == vorher


# ── Suche findet ueber die Felder ──────────────────────────────────────────

def test_suche_findet_ueber_spitznamen(basis):
    gq.profil_ergaenzen("Anna Beispiel", spitznamen=["Mausi"])
    namen = [p["name"] for p in gq.suche("Mausi")["personen"]]
    assert namen == ["Anna Beispiel"]


def test_suche_findet_ueber_vorname_und_nachname(basis):
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni")
    assert [p["name"] for p in gq.suche("Anni")["personen"]] == ["Anna Beispiel"]
    assert [p["name"] for p in gq.suche("Beispiel")["personen"]] == ["Anna Beispiel",
                                                                     "Tim Beispiel"]


def test_suche_liefert_die_felder_mit(basis):
    gq.profil_ergaenzen("Anna Beispiel", vorname="Anni", spitznamen=["Mausi"])
    p = gq.suche("Anni")["personen"][0]
    assert p["vorname"] == "Anni" and p["nachname"] == "Beispiel"
    assert p["spitznamen"] == ["Mausi"] and p["namensfelder_quelle"] == "profil"


def test_suche_ohne_feld_bleibt_wie_vorher(basis):
    namen = [p["name"] for p in gq.suche("Be")["personen"]]
    assert namen == ["Anna Beispiel", "Tim Beispiel"]
    assert gq.suche("Unbekannt")["personen"] == []


# ── Route (ProfilEingabe) ─────────────────────────────────────────────────

def test_route_nimmt_die_namensfelder_an(basis):
    with _klient() as client:
        r = client.post("/api/gruppen/profil", json={
            "name": "Anna Beispiel", "vorname": "Anni", "nachname": "Beispiel",
            "spitznamen": ["Anna"]})
        assert r.status_code == 200
        daten = r.json()
        assert daten["ok"] is True and daten["vorname"] == "Anni"
        assert daten["spitznamen"] == ["Anna"]


def test_route_ohne_namensfelder_bleibt_unveraendert(basis):
    with _klient() as client:
        r = client.post("/api/gruppen/profil", json={"name": "Tim Beispiel",
                                                     "beziehung": "Bruder"})
        assert r.json()["ok"] is True
        assert "vorname" not in _profil_roh(basis, "Tim Beispiel")
        assert r.json()["nachname"] == "Beispiel"      # abgeleitet, nicht gespeichert
