"""Pruefungen fuer ``orte_zuordnen.py`` (N-0929 Schritt 3 / E13c).

Alles OHNE Netz, ohne Bild und mit erfundenen Daten. Der Geocoder ist eine
Attrappe; nur ein Test nutzt das echte Paket ``reverse_geocoder`` (mit skip)
und dort nur oeffentliche Koordinaten (Split, Kroatien).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_orte_zuordnen.py -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "orte_zuordnen.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


oz = _laden(WERKZEUG, "orte_zuordnen")


def attrappe(koordinaten):
    """Erfundener Geocoder: lat < 50 -> Kroatien, sonst Deutschland."""
    out = []
    for lat, lon in koordinaten:
        cc = "HR" if lat < 50 else "DE"
        out.append({"cc": cc, "admin1": "Beispielregion", "name": "Beispielstadt",
                    "lat": str(lat + 0.01), "lon": str(lon)})
    return out


def _vektoren(pfad: Path, zeilen: list) -> Path:
    pfad.write_text("\n".join(z if isinstance(z, str) else json.dumps(z) for z in zeilen)
                    + "\n", encoding="utf-8")
    return pfad


def _meta(lat, lon, aufnahme="2020-05-01T10:00:00"):
    return {"aufnahme": aufnahme, "kamera_hersteller": "X", "kamera_modell": "Y",
            "gps": {"lat": lat, "lon": lon}}


@pytest.fixture
def eingabe(tmp_path):
    return _vektoren(tmp_path / "vektoren.jsonl", [
        {"bild_id": "b1", "metadaten": _meta(43.5, 16.4)},
        {"bild_id": "b2", "metadaten": _meta(52.5, 13.4)},
        {"bild_id": "b3", "metadaten": {"aufnahme": None, "gps": None}},
        {"bild_id": "b4"},
        "das ist kein json",
        {"bild_id": "b5", "metadaten": _meta(43.6, 16.5)},
    ])


def _ausgabe_zeilen(pfad: Path) -> list:
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z]


def test_zeilen_mit_und_ohne_gps_und_kaputte(eingabe, tmp_path):
    z = oz.orte_zuordnen(str(eingabe), str(tmp_path / "o.jsonl"), True, attrappe)
    assert (z["bilder"], z["mit_gps"], z["ohne_gps"], z["kaputt"]) == (5, 3, 2, 1)
    assert z["zugeordnet"] == 3 and z["laender"] == 2
    assert z["top_laender"][0] == ("Kroatien", 2)
    zeilen = _ausgabe_zeilen(tmp_path / "o.jsonl")
    assert [x["bild_id"] for x in zeilen] == ["b1", "b2", "b5"]
    erste = zeilen[0]
    assert erste["land_code"] == "HR" and erste["land"] == "Kroatien"
    assert erste["region"] == "Beispielregion" and erste["ort"] == "Beispielstadt"
    assert erste["quelle"] == "offline-geonames" and erste["version"] == 1
    assert erste["aufnahme"] == "2020-05-01T10:00:00"
    assert erste["abstand_km"] == pytest.approx(1.1, abs=0.1)


def test_idempotenz_zweiter_lauf_schreibt_nichts(eingabe, tmp_path):
    ziel = tmp_path / "o.jsonl"
    oz.orte_zuordnen(str(eingabe), str(ziel), True, attrappe)
    vorher = ziel.read_bytes()
    aufrufe = []
    z = oz.orte_zuordnen(str(eingabe), str(ziel), True,
                         lambda k: aufrufe.append(k) or attrappe(k))
    assert ziel.read_bytes() == vorher
    assert z["neu"] == 0 and z["bereits_vorhanden"] == 3 and aufrufe == []


def test_anhaengen_nur_neuer_bilder(eingabe, tmp_path):
    ziel = tmp_path / "o.jsonl"
    oz.orte_zuordnen(str(eingabe), str(ziel), True, attrappe)
    with open(eingabe, "a", encoding="utf-8") as f:
        f.write(json.dumps({"bild_id": "b6", "metadaten": _meta(48.0, 11.0)}) + "\n")
    oz.orte_zuordnen(str(eingabe), str(ziel), True, attrappe)
    assert [x["bild_id"] for x in _ausgabe_zeilen(ziel)] == ["b1", "b2", "b5", "b6"]


def test_trockenlauf_schreibt_nichts(eingabe, tmp_path, capsys):
    ziel = tmp_path / "o.jsonl"
    aufrufe = []
    rc = oz.haupt(["--eingabe", str(eingabe), "--ausgabe", str(ziel)],
                  suchen=lambda k: aufrufe.append(k) or [])
    assert rc == 0 and not ziel.exists() and aufrufe == []
    out = capsys.readouterr().out
    assert "Trockenlauf" in out and "mit GPS:             3" in out


def test_repo_pfad_wird_abgelehnt(eingabe):
    with pytest.raises(SystemExit) as e:
        oz.haupt(["--eingabe", str(eingabe), "--ausgabe", str(REPO / "orte.jsonl"),
                  "--schreiben"], suchen=attrappe)
    assert e.value.code == 2
    assert not (REPO / "orte.jsonl").exists()


def test_fehlende_eingabe_exit_2(tmp_path):
    with pytest.raises(SystemExit) as e:
        oz.haupt(["--eingabe", str(tmp_path / "gibts_nicht.jsonl"),
                  "--ausgabe", str(tmp_path / "o.jsonl")])
    assert e.value.code == 2


def test_ausgabe_ohne_koordinaten(eingabe, tmp_path):
    ziel = tmp_path / "o.jsonl"
    oz.orte_zuordnen(str(eingabe), str(ziel), True, attrappe)
    for zeile in _ausgabe_zeilen(ziel):
        assert not {"lat", "lon", "gps"} & set(zeile)
    text = ziel.read_text(encoding="utf-8")
    assert "43.5" not in text and "52.5" not in text


def test_konsole_ohne_orte_und_koordinaten(eingabe, tmp_path, capsys):
    rc = oz.haupt(["--eingabe", str(eingabe), "--ausgabe", str(tmp_path / "o.jsonl"),
                   "--schreiben"], suchen=attrappe)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Kroatien: 2" in out and "Deutschland: 1" in out
    assert "Beispielstadt" not in out and "43.5" not in out


def test_ungueltige_koordinaten_zaehlen_als_ohne_gps(tmp_path):
    p = _vektoren(tmp_path / "v.jsonl", [
        {"bild_id": "a", "metadaten": _meta(999, 5)},
        {"bild_id": "b", "metadaten": _meta("x", 5)},
        {"bild_id": "c", "metadaten": {"gps": {"lat": True, "lon": 1}}},
    ])
    kand, z = oz.eingabe_lesen(str(p))
    assert kand == [] and z["ohne_gps"] == 3 and z["bilder"] == 3


def test_echtes_paket_split_kroatien(tmp_path):
    pytest.importorskip("reverse_geocoder")
    p = _vektoren(tmp_path / "v.jsonl",
                  [{"bild_id": "s", "metadaten": _meta(43.508, 16.440)}])
    ziel = tmp_path / "o.jsonl"
    oz.orte_zuordnen(str(p), str(ziel), True)
    zeile = _ausgabe_zeilen(ziel)[0]
    assert zeile["land_code"] == "HR" and zeile["land"] == "Kroatien"
    assert zeile["abstand_km"] < 10
