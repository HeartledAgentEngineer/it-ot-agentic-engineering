"""Pruefungen fuer ``personen_register.py`` (E17, Personen-Register, 29.09.2026).

Alles OHNE Netz, ohne Bild und ohne echten Bestand: erfundene Vektorzeilen
(128-dim, je Person eine eigene Achse), ein erfundener Kennungs-Altbestand im
echten Format von ``personen_cluster`` (``kennungen.json``) und eine erfundene
Bestaetigungsdatei. **Nur erfundene Beispielnamen.**

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_register.py -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "personen_register.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pr = _laden(WERKZEUG, "personen_register")

BREITE, HOEHE = 1200, 800
GROSS = [100.0, 100.0, 200.0, 200.0]      # 40000 / 960000 = 0.0417
KLEIN = [10.0, 10.0, 40.0, 40.0]          # 1600 / 960000 = 0.0017


def emb(achse: int) -> list[float]:
    vektor = [0.001] * 128
    vektor[achse] = 1.0
    return vektor


def gesicht(achse: int, bbox=GROSS, score: float = 0.95) -> dict:
    return {"bbox": list(bbox), "score": score, "embedding": emb(achse)}


def zeile(bild_id: str, gesichter, aufnahme="2020-01-01T10:00:00") -> dict:
    daten = {"bild_id": bild_id, "breite": BREITE, "hoehe": HOEHE,
             "gesichter": gesichter}
    if aufnahme is not None:
        daten["metadaten"] = {"aufnahme": aufnahme}
    return daten


def schreibe(pfad: Path, zeilen) -> str:
    pfad.write_text("\n".join(json.dumps(z) for z in zeilen) + "\n",
                    encoding="utf-8")
    return str(pfad)


@pytest.fixture()
def bestand(tmp_path):
    """Sieben Bilder: A(Ich) auf allen, B(David) auf drei, C(unbenannt) auf drei."""
    hg = gesicht(5, KLEIN)                                   # Hintergrundgesicht
    zeilen = [
        zeile("b1", [gesicht(0), gesicht(1)], "2020-03-01T10:00:00"),
        zeile("b2", [gesicht(0), gesicht(1), hg], "2020-02-01T10:00:00"),
        zeile("b3", [gesicht(0), gesicht(1)], "2020-01-01T10:00:00"),
        zeile("b4", [gesicht(0), gesicht(2)], "2020-04-01T10:00:00"),
        zeile("b5", [gesicht(0), gesicht(2)], "2020-05-01T10:00:00"),
        zeile("b6", [gesicht(0), gesicht(2)], "2020-06-01T10:00:00"),
        zeile("b7", [gesicht(0)], None),
    ]
    alt = tmp_path / "kennungen.json"
    alt.write_text(json.dumps({"kennungen": [
        {"kennung": "Person_001", "mittelpunkt": emb(0)},
        {"kennung": "Person_002", "mittelpunkt": emb(1)},
        {"kennung": "Person_003", "mittelpunkt": emb(2)}]}), encoding="utf-8")
    best = tmp_path / "bestaetigt.json"
    best.write_text(json.dumps({"bestaetigt": {"Person_001": "Ich",
                                               "Person_002": "David"}}),
                    encoding="utf-8")
    return {"zeilen": zeilen, "alt": str(alt), "best": str(best),
            "tmp": tmp_path}


def rechnen(bestand, zeilen=None, **schwellen):
    bilder, _ = pr.bilder_vereinen(zeilen or bestand["zeilen"])
    altbestand = pr._cluster.altbestand_lesen_datei(bestand["alt"])
    lauf = pr._cluster.lauf_rechnen(bilder, altbestand=altbestand)
    namen = pr.namen_bauen(None, pr._andocken.bestaetigung_lesen(bestand["best"]))
    return pr.register_zeilen_bauen(bilder, pr.zuordnung_bauen(lauf), namen,
                                    **schwellen)


# -- Gesichtsanteil und Schwellen -------------------------------------------

def test_gesichtsanteil_ist_flaeche_durch_bildflaeche(bestand):
    zeilen = rechnen(bestand)
    gross = [z for z in zeilen if z["bild_id"] == "b1"][0]
    klein = [z for z in zeilen if z["bild_id"] == "b2" and z["cluster"] is None][0]
    assert gross["gesichtsanteil"] == 0.0417
    assert klein["gesichtsanteil"] == 0.0017


def test_zeilenformat_und_referenz(bestand):
    z = [z for z in rechnen(bestand) if z["bild_id"] == "b1"][0]
    assert set(z) == {"bild_id", "index", "person", "cluster", "bbox",
                      "gesichtsanteil", "score", "zaehlt_mit", "aufnahme"}
    assert z["aufnahme"] == "2020-03-01T10:00:00"
    assert z["cluster"] == "Person_001" and z["person"] == "Ich"


def test_zaehlt_mit_schwellen():
    bild = [zeile("s1", [gesicht(0, GROSS, 0.95), gesicht(1, GROSS, 0.79),
                         gesicht(2, KLEIN, 0.95)])]
    bilder, _ = pr.bilder_vereinen(bild)
    z = pr.register_zeilen_bauen(bilder, {})
    assert [x["zaehlt_mit"] for x in z] == [True, False, False]
    # Schwellen sind einstellbar
    z2 = pr.register_zeilen_bauen(bilder, {}, min_anteil=0.001, min_score=0.5)
    assert all(x["zaehlt_mit"] for x in z2)


# -- Abfrage ------------------------------------------------------------------

def test_hintergrundgesicht_zerstoert_genau_nicht(bestand):
    register = pr.register_bauen(rechnen(bestand))
    assert "b2" in pr.bilder_mit(register, {"Ich", "David"}, "genau")


def test_genau_gegen_mindestens(bestand):
    register = pr.register_bauen(rechnen(bestand))
    assert pr.bilder_mit(register, {"Ich", "David"}, "genau") == ["b3", "b2", "b1"]
    assert pr.bilder_mit(register, {"Ich"}, "genau") == ["b7"]
    assert len(pr.bilder_mit(register, {"Ich"}, "mindestens")) == 7
    assert pr.bilder_mit(register, {"David"}, "mindestens") == ["b3", "b2", "b1"]


def test_unbenannter_cluster_zaehlt_bei_genau_als_fremd(bestand):
    register = pr.register_bauen(rechnen(bestand))
    genau = pr.bilder_mit(register, {"Ich"}, "genau")
    assert "b4" not in genau and "b5" not in genau
    assert "b4" in pr.bilder_mit(register, {"Ich"}, "mindestens")


def test_gesicht_ohne_gruppe_ist_fremd_wenn_wichtig():
    bilder, _ = pr.bilder_vereinen([zeile("x", [gesicht(0), gesicht(9)])])
    z = pr.register_zeilen_bauen(bilder, {("x", 0): "Person_001"},
                                 {"Person_001": "Ich"})
    register = pr.register_bauen(z)
    assert pr.bilder_mit(register, {"Ich"}, "genau") == []
    assert pr.bilder_mit(register, {"Ich"}, "mindestens") == ["x"]


def test_chronologisch_fehlendes_datum_ans_ende(bestand):
    register = pr.register_bauen(rechnen(bestand))
    ergebnis = pr.bilder_mit(register, {"Ich"}, "mindestens")
    assert ergebnis == ["b3", "b2", "b1", "b4", "b5", "b6", "b7"]


def test_unbekannter_modus():
    with pytest.raises(ValueError):
        pr.bilder_mit({"bilder": {}}, {"Ich"}, "irgendwie")


# -- Dubletten, Begleiter, Verteilung -------------------------------------------

def test_dubletten_ueber_vektordateien_einmal(bestand):
    zeilen = bestand["zeilen"] + [bestand["zeilen"][0], bestand["zeilen"][1]]
    bilder, dubletten = pr.bilder_vereinen(zeilen)
    assert dubletten == 2 and len(bilder) == 7


def test_uebersicht_zahlen_begleiter_verteilung(bestand):
    u = pr.uebersicht_bauen(rechnen(bestand))
    je = {p["person"]: p for p in u["personen"]}
    ich = je["Ich"]
    assert ich["anzahl_bilder"] == 7 and ich["anzahl_bilder_wichtig"] == 7
    assert ich["erstes"] == "2020-01-01T10:00:00"
    assert ich["letztes"] == "2020-06-01T10:00:00"
    assert ich["haeufigste_begleiter"][0] == {"person": "David", "anzahl": 3}
    assert {"person": "Person_003", "anzahl": 3} in ich["haeufigste_begleiter"]
    assert je["David"]["haeufigste_begleiter"] == [{"person": "Ich", "anzahl": 3}]
    assert u["personen_wichtig"] == {"0": 0, "1": 1, "2": 6, "3": 0, "4+": 0}


# -- Kommandozeile --------------------------------------------------------------

def argumente(bestand, *extra):
    a = schreibe(bestand["tmp"] / "v1.jsonl", bestand["zeilen"][:4])
    b = schreibe(bestand["tmp"] / "v2.jsonl",
                 bestand["zeilen"][3:] + [bestand["zeilen"][0]])   # b4 + b1 doppelt
    return ["--vektoren", a, "--vektoren", b,
            "--alt-kennungen", bestand["alt"],
            "--bestaetigung", bestand["best"],
            "--ausgabe-bild-person", str(bestand["tmp"] / "aus" / "bp.jsonl"),
            "--ausgabe-uebersicht", str(bestand["tmp"] / "aus" / "u.json"),
            *extra]


def test_trockenlauf_schreibt_nichts(bestand, capsys):
    assert pr.main(argumente(bestand)) == 0
    assert not (bestand["tmp"] / "aus").exists()
    assert "NICHTS geschrieben" in capsys.readouterr().out


def test_schreiben_und_dubletten_und_konsole_ohne_namen(bestand, capsys):
    assert pr.main(argumente(bestand, "--schreiben")) == 0
    ausgabe = capsys.readouterr().out
    for name in ("Ich", "David", "Person_001"):
        assert name not in ausgabe
    assert "Dubletten: 2" in ausgabe
    zeilen = [json.loads(z) for z in
              (bestand["tmp"] / "aus" / "bp.jsonl").read_text("utf-8").splitlines()]
    assert {z["bild_id"] for z in zeilen} == {"b1", "b2", "b3", "b4", "b5", "b6", "b7"}
    assert sum(1 for z in zeilen if z["bild_id"] == "b1") == 2      # einmal gezaehlt
    uebersicht = json.loads((bestand["tmp"] / "aus" / "u.json").read_text("utf-8"))
    assert uebersicht["anzahl_bilder"] == 7
    assert not list((bestand["tmp"] / "aus").glob("*.tmp"))


def test_repo_pfad_ist_exit_2(bestand):
    args = argumente(bestand, "--schreiben")
    args[args.index("--ausgabe-bild-person") + 1] = str(REPO / "bp.jsonl")
    with pytest.raises(SystemExit) as fehler:
        pr.main(args)
    assert fehler.value.code == 2
    assert not (REPO / "bp.jsonl").exists()
    assert not (bestand["tmp"] / "aus").exists()


def test_fehlende_vektordatei_ist_exit_2(bestand):
    args = argumente(bestand)
    args[args.index("--vektoren") + 1] = str(bestand["tmp"] / "fehlt.jsonl")
    assert pr.main(args) == 2
