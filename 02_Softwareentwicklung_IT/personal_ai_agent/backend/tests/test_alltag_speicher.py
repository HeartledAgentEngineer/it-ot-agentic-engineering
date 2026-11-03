"""Alltagsprotokoll S1: Speicher (append-only JSONL) inkl. Schlafnächte der Uhr (03.11.2026).

Alle Daten sind erfunden. Aufruf (aus backend/):
    .venv/Scripts/python.exe -m pytest tests/test_alltag_speicher.py -q
"""
from __future__ import annotations

import json

import pytest

from app.services import alltag_speicher as sp


@pytest.fixture(autouse=True)
def _pfad(tmp_path, monkeypatch):
    datei = tmp_path / "alltag" / "eintraege.jsonl"
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(datei))
    return datei


def _nacht(kennung="hc-1", beginn="2026-11-02T23:10:00+01:00", ende="2026-11-03T06:40:00+01:00",
           phasen=None):
    return {
        "quelle_kennung": kennung,
        "beginn": beginn,
        "ende": ende,
        "app": "com.beispiel.uhr",
        "phasen": phasen if phasen is not None else [
            {"stufe": "leicht", "beginn": "2026-11-02T23:10:00+01:00", "ende": "2026-11-03T01:00:00+01:00"},
            {"stufe": "tief", "beginn": "2026-11-03T01:00:00+01:00", "ende": "2026-11-03T02:30:00+01:00"},
            {"stufe": "wach", "beginn": "2026-11-03T02:30:00+01:00", "ende": "2026-11-03T02:45:00+01:00"},
            {"stufe": "rem", "beginn": "2026-11-03T02:45:00+01:00", "ende": "2026-11-03T06:40:00+01:00"},
        ],
    }


# ── Pfad ──────────────────────────────────────────────────────────────────

def test_pfad_aus_umgebung(_pfad):
    assert sp.speicher_pfad() == str(_pfad)


def test_standardpfad_im_home(monkeypatch):
    monkeypatch.delenv("ALLTAGSPROTOKOLL_PFAD", raising=False)
    pfad = sp.speicher_pfad()
    assert pfad.endswith("eintraege.jsonl") and "alltagsprotokoll" in pfad


# ── Schlafnächte übernehmen ───────────────────────────────────────────────

def test_neue_nacht_wird_gespeichert(_pfad):
    erg = sp.schlafnaechte_uebernehmen([_nacht()])
    assert erg == {"ok": True, "neu": 1, "aktualisiert": 0, "unveraendert": 0, "abgelehnt": 0}
    zeilen = [json.loads(z) for z in _pfad.read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 1 and zeilen[0]["art"] == "schlafnacht" and zeilen[0]["quelle"] == "uhr"
    assert zeilen[0]["id"] and zeilen[0]["erfasst_um"]


def test_zweiter_abgleich_ist_unveraendert(_pfad):
    sp.schlafnaechte_uebernehmen([_nacht()])
    erg = sp.schlafnaechte_uebernehmen([_nacht()])
    assert erg["neu"] == 0 and erg["unveraendert"] == 1
    assert len(_pfad.read_text(encoding="utf-8").splitlines()) == 1


def test_geaenderte_nacht_wird_korrektur(_pfad):
    sp.schlafnaechte_uebernehmen([_nacht()])
    erg = sp.schlafnaechte_uebernehmen([_nacht(ende="2026-11-03T07:00:00+01:00", phasen=[])])
    assert erg["aktualisiert"] == 1
    aktuell = sp.eintraege(art="schlafnacht")
    assert len(aktuell) == 1 and aktuell[0]["ende"] == "2026-11-03T07:00:00+01:00"
    assert aktuell[0]["ersetzt"]


@pytest.mark.parametrize("kaputt", [
    {"beginn": "2026-11-03T06:00:00+01:00", "ende": "2026-11-02T23:00:00+01:00"},   # Ende vor Beginn
    {"beginn": "kein Datum"},
    {"beginn": "2026-11-01T06:00:00+01:00", "ende": "2026-11-03T06:00:00+01:00"},    # länger als 24 h
    {"quelle_kennung": ""},
])
def test_ungueltige_nacht_wird_abgelehnt(kaputt):
    erg = sp.schlafnaechte_uebernehmen([{**_nacht(), **kaputt}, _nacht("hc-2")])
    assert erg["abgelehnt"] == 1 and erg["neu"] == 1


def test_unbekannte_phase_wird_unbekannt_und_fremde_felder_fallen_weg():
    nacht = _nacht(phasen=[{"stufe": "traumland", "beginn": "2026-11-02T23:10:00+01:00",
                            "ende": "2026-11-03T06:40:00+01:00", "geheim": 1}])
    nacht["fremd"] = "weg"
    sp.schlafnaechte_uebernehmen([nacht])
    gespeichert = sp.eintraege(art="schlafnacht")[0]
    assert "fremd" not in gespeichert
    assert gespeichert["phasen"] == [{"stufe": "unbekannt", "beginn": "2026-11-02T23:10:00+01:00",
                                      "ende": "2026-11-03T06:40:00+01:00"}]


def test_keine_liste_ist_ehrlicher_fehler():
    assert sp.schlafnaechte_uebernehmen("nix")["ok"] is False


# ── Lesen, Korrigieren, Löschen ───────────────────────────────────────────

def test_eintrag_anhaengen_und_lesen():
    e = sp.eintrag_anhaengen({"art": "stunde", "von": "2026-11-03T09:00:00+01:00",
                              "bis": "2026-11-03T10:00:00+01:00", "aktivitaet": "Wäsche"})
    assert e["ok"] and sp.eintraege(art="stunde")[0]["aktivitaet"] == "Wäsche"


def test_unbekannte_art_wird_abgelehnt():
    assert sp.eintrag_anhaengen({"art": "quatsch"})["ok"] is False


def test_korrigieren_und_loeschen():
    e = sp.eintrag_anhaengen({"art": "stunde", "von": "2026-11-03T09:00:00+01:00",
                              "bis": "2026-11-03T10:00:00+01:00", "aktivitaet": "Wäsche"})
    k = sp.korrigieren(e["eintrag"]["id"], {"aktivitaet": "Kochen"})
    assert k["ok"] and [x["aktivitaet"] for x in sp.eintraege()] == ["Kochen"]
    assert sp.loeschen(k["eintrag"]["id"])["ok"]
    assert sp.eintraege() == []


def test_loeschen_unbekannter_id():
    assert sp.loeschen("gibt-es-nicht")["ok"] is False


def test_kaputte_zeilen_werden_uebersprungen(_pfad):
    sp.schlafnaechte_uebernehmen([_nacht()])
    with open(_pfad, "a", encoding="utf-8") as f:
        f.write("{kaputt\n[1,2]\n\n")
    assert len(sp.eintraege()) == 1


def test_zeitraum_filter_nach_ende():
    sp.schlafnaechte_uebernehmen([
        _nacht("a", "2026-10-30T23:00:00+01:00", "2026-10-31T07:00:00+01:00", []),
        _nacht("b", "2026-11-02T23:00:00+01:00", "2026-11-03T07:00:00+01:00", []),
    ])
    treffer = sp.eintraege(art="schlafnacht", von="2026-11-01", bis="2026-11-03")
    assert [t["quelle_kennung"] for t in treffer] == ["b"]


def test_fehlende_datei_ist_leer():
    assert sp.eintraege() == []
