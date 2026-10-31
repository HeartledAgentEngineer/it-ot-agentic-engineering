"""Wächtertests für Lebensabschnitte und belegbare Aussagen (On-Device)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.services import lebensabschnitte_service as ls
from app.services import gruppen_quiz as gq


def test_jahr_aus_gueltige_werte():
    assert ls.jahr_aus("2011-08-02") == 2011
    assert ls.jahr_aus("2019") == 2019
    assert ls.jahr_aus(1998) == 1998
    assert ls.jahr_aus("2026-10-30T13:00:00") == 2026


def test_jahr_aus_ungueltige_werte():
    assert ls.jahr_aus(None) is None
    assert ls.jahr_aus("") is None
    assert ls.jahr_aus("kein-datum") is None
    assert ls.jahr_aus(1850) is None
    assert ls.jahr_aus(2250) is None


def test_alter_in_jahr():
    assert ls.alter_in_jahr("1998-04-14", 2018) == 20
    assert ls.alter_in_jahr(1998, 2026) == 28
    assert ls.alter_in_jahr(None, 2020) is None
    assert ls.alter_in_jahr("2020-01-01", 2010) is None


def test_phasen_bilden_jahre():
    # Zusammenhängend
    assert ls.phasen_bilden_jahre([2011, 2012, 2013]) == [(2011, 2013)]
    # Mit Lücke > 2 Jahre
    assert ls.phasen_bilden_jahre([2011, 2012, 2016, 2017]) == [(2011, 2012), (2016, 2017)]
    # Einzeljahr
    assert ls.phasen_bilden_jahre([2019]) == [(2019, 2019)]
    # Leer / Duplikate / Unsortiert
    assert ls.phasen_bilden_jahre([]) == []
    assert ls.phasen_bilden_jahre([2015, 2011, 2011, 2015]) == [(2011, 2011), (2015, 2015)]


def test_lebensabschnitte_fuer_person_mit_beispielen(tmp_path: Path):
    vorschlaege = [
        {
            "kennung": "Person_100",
            "groesse": 5,
            "von": "2011-05-01",
            "bis": "2012-08-01",
            "beispiele": [
                {"fileid": "f1", "aufnahme": "2011-05-01"},
                {"fileid": "f2", "aufnahme": "2012-08-01"},
            ],
        },
        {
            "kennung": "Person_101",
            "groesse": 3,
            "von": "2018-03-15",
            "bis": "2019-11-20",
            "beispiele": [
                {"fileid": "f3", "aufnahme": "2018-03-15"},
                {"fileid": "f4", "aufnahme": "2019-11-20"},
            ],
        },
    ]
    profil = {
        "kontakt": {"geburtstag": "2000-01-01"},
        "beziehung": "Freund",
    }

    res = ls.lebensabschnitte_fuer_person(
        "Albrecht", vorschlaege=vorschlaege, profil_daten=profil, basis_pfad=str(tmp_path)
    )

    assert res["ok"] is True
    assert res["name"] == "Albrecht"
    assert res["anzahl_phasen"] == 2
    assert res["gesamt_gesichter"] == 8
    assert res["von_jahr"] == 2011
    assert res["bis_jahr"] == 2019

    p1, p2 = res["phasen"]
    assert p1["von_jahr"] == 2011 and p1["bis_jahr"] == 2012
    assert p1["titel"] == "2011 – 2012"
    assert "ca. 11–12 Jahre" in (p1["alters_hinweis"] or "")
    assert "2011 bis 2012" in p1["aussage"]
    assert p1["gruppen_anzahl"] == 1
    assert p1["gruppen_kennungen"] == ["Person_100"]

    assert p2["von_jahr"] == 2018 and p2["bis_jahr"] == 2019
    assert p2["titel"] == "2018 – 2019"
    assert "ca. 18–19 Jahre" in (p2["alters_hinweis"] or "")
    assert p2["gruppen_anzahl"] == 1
    assert p2["gruppen_kennungen"] == ["Person_101"]

    assert "Insgesamt 8 Fotos in 2 Lebensabschnitten von 2011 bis 2019." in res["aussage"]


def test_lebensabschnitte_begleiter_aus_beziehungen(tmp_path: Path):
    beziehungen_datei = tmp_path / "beziehungen.jsonl"
    zeilen = [
        {
            "datum": "2011-06-15",
            "personen": [
                {"kennung": "Person_100", "name": "Albrecht"},
                {"kennung": "Person_200", "name": "Caro"},
                {"kennung": "Person_300", "name": "Sebastian"},
            ],
        },
        {
            "datum": "2011-07-20",
            "personen": [
                {"kennung": "Person_100", "name": "Albrecht"},
                {"kennung": "Person_200", "name": "Caro"},
            ],
        },
        {
            "datum": "2018-09-01",
            "personen": [
                {"kennung": "Person_101", "name": "Albrecht"},
                {"kennung": "Person_400", "name": "Tim"},
            ],
        },
    ]
    with open(beziehungen_datei, "w", encoding="utf-8") as f:
        for z in zeilen:
            f.write(json.dumps(z) + "\n")

    begleiter_2011 = ls.begleiter_aus_beziehungen("Albrecht", 2011, 2012, basis_pfad=str(tmp_path))
    assert "Caro" in begleiter_2011
    assert "Sebastian" in begleiter_2011

    begleiter_2018 = ls.begleiter_aus_beziehungen("Albrecht", 2018, 2019, basis_pfad=str(tmp_path))
    assert begleiter_2018 == ["Tim"]


def test_vorschlag_fuer_offene_gruppe(tmp_path: Path):
    offene_gruppe = {
        "kennung": "Gruppe_999",
        "von": "2011-08-10",
        "bis": "2011-08-10",
        "groesse": 2,
    }
    katalog = {
        "Albrecht": [
            {
                "von": "2011-01-01",
                "bis": "2013-12-31",
                "groesse": 10,
                "beispiele": [{"aufnahme": "2011-05-01"}],
            }
        ]
    }

    vorschlag = ls.vorschlag_fuer_offene_gruppe(offene_gruppe, katalog=katalog, basis_pfad=str(tmp_path))
    assert vorschlag is not None
    assert vorschlag["name"] == "Albrecht"
    assert "2011" in vorschlag["titel"]
    assert "Albrecht" in vorschlag["grund"]


def test_person_ohne_angaben_liefert_robuste_struktur():
    res = ls.lebensabschnitte_fuer_person("Unbekannt", vorschlaege=[], profil_daten={})
    assert res["ok"] is True
    assert res["phasen"] == []
    assert res["anzahl_phasen"] == 0
    assert "0" in str(res["gesamt_gesichter"])


def test_gruppen_quiz_person_enthaelt_lebensabschnitte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))

    # Minimale Dateien anlegen
    bestaetigt = {"Person_10": "Testperson"}
    (tmp_path / gq.BESTAETIGT_DATEINAME).write_text(json.dumps({"bestaetigt": bestaetigt}), encoding="utf-8")
    (tmp_path / gq.VORGABEN_DATEINAME).write_text(json.dumps({"gleich": [], "verschieden": []}), encoding="utf-8")
    (tmp_path / gq.STAND_DATEINAME).write_text(json.dumps({"spaeter": [], "unbekannt": [], "aufgeloest": []}), encoding="utf-8")
    (tmp_path / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({
            "gruppen": [
                {
                    "kennung": "Person_10",
                    "groesse": 4,
                    "von": "2015-06-01",
                    "bis": "2015-06-01",
                    "beispiele": [{"fileid": "111", "aufnahme": "2015-06-01"}],
                }
            ]
        }),
        encoding="utf-8",
    )

    gq._CACHE.clear()
    antwort = gq.person("Testperson")

    assert antwort["ok"] is True
    assert antwort["name"] == "Testperson"
    assert "lebensabschnitte" in antwort
    assert len(antwort["lebensabschnitte"]) == 1
    assert antwort["lebensabschnitte"][0]["titel"] == "2015"
    assert "lebensabschnitte_aussage" in antwort
    assert "2015" in antwort["lebensabschnitte_aussage"]


def test_andocken_kandidaten(tmp_path: Path):
    gruppen = [
        {"kennung": "Gruppe_Offen_1", "von": "2011-04-10", "bis": "2011-04-10", "groesse": 3},
        {"kennung": "Gruppe_Offen_2", "von": "1995-01-01", "bis": "1995-01-01", "groesse": 5},
    ]
    katalog = {
        "Albrecht": [
            {
                "von": "2011-01-01",
                "bis": "2013-12-31",
                "groesse": 12,
                "beispiele": [{"aufnahme": "2011-06-01"}],
            }
        ]
    }
    kandidaten = ls.andocken_kandidaten(katalog=katalog, gruppen=gruppen, basis_pfad=str(tmp_path))
    assert len(kandidaten) == 1
    assert kandidaten[0]["kennung"] == "Gruppe_Offen_1"
    assert kandidaten[0]["name"] == "Albrecht"
    assert kandidaten[0]["groesse"] == 3


def test_gruppen_quiz_andocken_trocken_und_schreiben(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))

    # Testdaten
    (tmp_path / gq.BESTAETIGT_DATEINAME).write_text(
        json.dumps({"bestaetigt": {"Gruppe_Bekannt": "Albrecht"}}), encoding="utf-8"
    )
    (tmp_path / gq.VORGABEN_DATEINAME).write_text(json.dumps({"gleich": [], "verschieden": []}), encoding="utf-8")
    (tmp_path / gq.STAND_DATEINAME).write_text(
        json.dumps({"spaeter": [], "unbekannt": [], "aufgeloest": []}), encoding="utf-8"
    )
    (tmp_path / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({
            "gruppen": [
                {
                    "kennung": "Gruppe_Bekannt",
                    "groesse": 10,
                    "von": "2011-01-01",
                    "bis": "2013-12-31",
                    "beispiele": [{"fileid": "1", "aufnahme": "2011-06-01"}],
                },
                {
                    "kennung": "Gruppe_Offen_1",
                    "groesse": 4,
                    "von": "2012-05-10",
                    "bis": "2012-05-10",
                    "beispiele": [{"fileid": "2", "aufnahme": "2012-05-10"}],
                },
            ]
        }),
        encoding="utf-8",
    )

    gq._CACHE.clear()

    # 1. Trockenlauf
    res_trocken = gq.andocken(trocken=True)
    assert res_trocken["ok"] is True
    assert res_trocken["trocken"] is True
    assert res_trocken["anzahl"] == 1
    assert res_trocken["gesichter"] == 4
    # Noch nichts gespeichert
    assert "Gruppe_Offen_1" not in gq.bestaetigt_lesen()

    # 2. Schreiblauf
    res_schreiben = gq.andocken(trocken=False)
    assert res_schreiben["ok"] is True
    assert res_schreiben["trocken"] is False
    assert res_schreiben["anzahl"] == 1
    assert "Gruppe_Offen_1" in res_schreiben["zugeordnet"]

    # Jetzt bestätigt
    bestaetigt = gq.bestaetigt_lesen()
    assert bestaetigt.get("Gruppe_Offen_1") == "Albrecht"


def test_phasen_zentroide_und_cosinus_aehnlichkeit(tmp_path: Path):
    v1 = [0.1] * 128
    v2 = [-0.1] * 128
    v_norm1 = ls.cosinus_aehnlichkeit(v1, v1)
    assert abs(v_norm1 - 1.0) < 1e-5
    v_opp = ls.cosinus_aehnlichkeit(v1, v2)
    assert abs(v_opp - (-1.0)) < 1e-5

    kennungen_datei = tmp_path / "kennungen.json"
    kennungen_datei.write_text(json.dumps({
        "kennungen": [
            {"kennung": "Person_100", "mittelpunkt": [0.0] * 64 + [1.0] * 64},
            {"kennung": "Person_101", "mittelpunkt": [1.0] * 64 + [0.0] * 64},
        ]
    }), encoding="utf-8")

    vorschlaege = [
        {
            "kennung": "Person_100",
            "groesse": 10,
            "von": "2012-01-01",
            "bis": "2012-12-31",
            "beispiele": [{"fileid": "f1", "aufnahme": "2012-05-01"}],
        }
    ]
    res = ls.lebensabschnitte_fuer_person("TestPerson", vorschlaege=vorschlaege, basis_pfad=str(tmp_path))
    assert res["ok"] is True
    assert len(res["phasen"]) == 1
    phase = res["phasen"][0]
    assert phase["zentroid"] is not None
    assert len(phase["zentroid"]) == 128
    norm = sum(x*x for x in phase["zentroid"]) ** 0.5
    assert abs(norm - 1.0) < 1e-3


def test_zwillings_trennung_vektor_und_cannot_link(tmp_path: Path):
    seb_vec = [0.8] * 64 + [0.2] * 64
    jul_vec = [0.2] * 64 + [0.8] * 64
    offen_seb_nah = [0.75] * 64 + [0.25] * 64
    offen_jul_nah = [0.25] * 64 + [0.75] * 64

    kennungen_datei = tmp_path / "kennungen.json"
    kennungen_datei.write_text(json.dumps({
        "kennungen": [
            {"kennung": "Gruppe_Seb", "mittelpunkt": seb_vec},
            {"kennung": "Gruppe_Jul", "mittelpunkt": jul_vec},
            {"kennung": "Gruppe_Offen_Seb", "mittelpunkt": offen_seb_nah},
            {"kennung": "Gruppe_Offen_Jul", "mittelpunkt": offen_jul_nah},
        ]
    }), encoding="utf-8")

    personen_phasen = {
        "Sebastian": [{
            "phase_id": "phase-2010-2012",
            "titel": "2010 – 2012",
            "von_jahr": 2010,
            "bis_jahr": 2012,
            "zentroid": seb_vec,
            "aussage": "Sebastian in 2010-2012",
        }],
        "Julian": [{
            "phase_id": "phase-2010-2012",
            "titel": "2010 – 2012",
            "von_jahr": 2010,
            "bis_jahr": 2012,
            "zentroid": jul_vec,
            "aussage": "Julian in 2010-2012",
        }]
    }

    # 1. Vektor-Differenzierung: Offene Gruppe ist Sebastian ähnlicher
    gruppe_seb = {"kennung": "Gruppe_Offen_Seb", "von": "2011-06-01", "groesse": 5}
    v_seb = ls.vorschlag_fuer_offene_gruppe(gruppe_seb, personen_phasen=personen_phasen, basis_pfad=str(tmp_path))
    assert v_seb is not None
    assert v_seb["name"] == "Sebastian"
    assert v_seb["sicherheit"] == 0.85

    # 2. Vektor-Differenzierung: Offene Gruppe ist Julian ähnlicher
    gruppe_jul = {"kennung": "Gruppe_Offen_Jul", "von": "2011-06-01", "groesse": 5}
    v_jul = ls.vorschlag_fuer_offene_gruppe(gruppe_jul, personen_phasen=personen_phasen, basis_pfad=str(tmp_path))
    assert v_jul is not None
    assert v_jul["name"] == "Julian"
    assert v_jul["sicherheit"] == 0.85


def test_invalidiere_cache():
    ls._PHASEN_CACHE["test"] = ((), {})
    ls._BEZIEHUNGEN_CACHE["test"] = ((), {})
    ls._MITTELPUNKTE_CACHE["test"] = ((), {})
    ls.invalidiere_cache()
    assert len(ls._PHASEN_CACHE) == 0
    assert len(ls._BEZIEHUNGEN_CACHE) == 0
    assert len(ls._MITTELPUNKTE_CACHE) == 0
