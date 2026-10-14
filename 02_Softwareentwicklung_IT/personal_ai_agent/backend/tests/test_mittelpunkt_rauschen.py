"""Pruefungen fuer ``tools/foto_sortierung/mittelpunkt_rauschen_messen.py`` (14.10.2026).

Offline, erfundene Vektoren und Kennungen, keine echten Daten, kein Netz, kein Bild.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "mittelpunkt_rauschen_messen.py"

spez = importlib.util.spec_from_file_location("mittelpunkt_rauschen_messen", WERKZEUG)
assert spez is not None and spez.loader is not None
mr = importlib.util.module_from_spec(spez)
spez.loader.exec_module(mr)


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _vektor(winkel_grad: float = 0.0, masse: int = 4):
    """Ein einfacher Einheitsvektor in der Ebene (Rest Nullen) fuer klare Winkel."""
    rad = math.radians(winkel_grad)
    return [math.cos(rad), math.sin(rad)] + [0.0] * (masse - 2)


def _zeile(bild_id, index, kennung, score=0.95, breite=120.0, aufnahme=None, vektor=None):
    return {"bild_id": bild_id, "index": index, "kennung": kennung, "score": score,
            "bbox": [10.0, 10.0, breite, breite], "anteil": 0.02, "aufnahme": aufnahme,
            "video_id": None, "vektor": vektor}


def _zuordnungsdatei(pfad: Path, zeilen) -> Path:
    pfad.write_text("".join(json.dumps(z) + "\n" for z in zeilen) + "kaputt\n", encoding="utf-8")
    return pfad


def _vektordatei(pfad: Path, gesichter) -> Path:
    """``gesichter`` = [(bild_id, index, vektor)]; je Bild eine Zeile."""
    je_bild: dict = {}
    for bild_id, index, vektor in gesichter:
        je_bild.setdefault(bild_id, []).append((index, vektor))
    zeilen = []
    for bild_id, eintraege in je_bild.items():
        liste = [None] * (max(i for i, _ in eintraege) + 1)
        for index, vektor in eintraege:
            liste[index] = {"bbox": [1.0, 1.0, 120.0, 120.0], "score": 0.95,
                            "embedding": vektor}
        zeilen.append({"bild_id": bild_id, "breite": 100, "hoehe": 100, "gesichter": liste})
    pfad.write_text("".join(json.dumps(z) + "\n" for z in zeilen), encoding="utf-8")
    return pfad


# ── 1. Lesen ─────────────────────────────────────────────────────────────────

def test_zuordnung_liest_kennung_score_breite(tmp_path):
    pfad = _zuordnungsdatei(tmp_path / "z.jsonl", [
        _zeile("1", 0, "Person_001", score=0.93, breite=140.0),
        _zeile("1", 1, None, score=0.99, breite=200.0),
    ])
    gesichter, ohne = mr.zuordnung_lesen(str(pfad))
    assert ohne == 1
    assert list(gesichter) == [("1", 0)]
    eintrag = gesichter[("1", 0)]
    assert eintrag["kennung"] == "Person_001" and eintrag["score"] == 0.93
    assert eintrag["breite_px"] == 140.0 and eintrag["video"] is False


def test_vektoren_sammeln_nimmt_nur_gefragte_schluessel_und_erste_datei_gewinnt(tmp_path):
    a = _vektordatei(tmp_path / "a.jsonl", [("1", 0, _vektor(0)), ("2", 0, _vektor(10))])
    b = _vektordatei(tmp_path / "b.jsonl", [("1", 0, _vektor(20))])
    vektoren, statistik = mr.vektoren_sammeln([str(a), str(b)], schluessel={("1", 0)})
    assert list(vektoren) == [("1", 0)]
    assert vektoren[("1", 0)][1] == pytest.approx(0.0, abs=1e-6)     # Datei a gewinnt
    assert statistik["dateien"] == 2 and statistik["gelesen"] == 1
    assert statistik["masse"] == 4


def test_vektoren_sammeln_meldet_fehlende_datei_und_abweichende_laenge(tmp_path):
    fehlt = tmp_path / "gibtsnicht.jsonl"
    gemischt = tmp_path / "m.jsonl"
    gemischt.write_text(
        json.dumps({"bild_id": "1", "gesichter": [{"embedding": [1.0, 0.0, 0.0, 0.0]}]}) + "\n"
        + json.dumps({"bild_id": "2", "gesichter": [{"embedding": [1.0, 0.0]}]}) + "\n"
        + "{kaputt\n", encoding="utf-8")
    vektoren, statistik = mr.vektoren_sammeln([str(fehlt), str(gemischt)])
    assert statistik["fehlend"] == 1 and statistik["defekt"] == 1
    assert statistik["fremde_laenge"] == 1 and statistik["gelesen"] == 1


# ── 2. Rechnen ───────────────────────────────────────────────────────────────

def test_mittelpunkt_ist_richtung_und_winkel_ist_cosinus_distanz():
    punkt = mr.mittelpunkt([np.asarray(_vektor(0)), np.asarray(_vektor(0))])
    assert punkt is not None and float(np.linalg.norm(punkt)) == pytest.approx(1.0, abs=1e-6)
    assert mr.winkel(punkt, np.asarray(_vektor(0))) == pytest.approx(0.0, abs=1e-6)
    assert mr.winkel(np.asarray(_vektor(0)), np.asarray(_vektor(90))) == pytest.approx(1.0, abs=1e-6)
    assert mr.mittelpunkt([]) is None


def test_sauber_verlangt_score_und_breite():
    assert mr.sauber({"score": 0.95, "breite_px": 100.0})
    assert not mr.sauber({"score": 0.80, "breite_px": 100.0})
    assert not mr.sauber({"score": 0.95, "breite_px": 40.0})
    assert not mr.sauber({"score": None, "breite_px": 100.0})
    assert not mr.sauber({"score": 0.95, "breite_px": None})


def test_verschiebung_waechst_mit_unsicherem_ausreisser():
    gesichter = [(("1", 0), {"score": 0.95, "breite_px": 120.0, "kennung": "P"}),
                 (("2", 0), {"score": 0.95, "breite_px": 120.0, "kennung": "P"}),
                 (("3", 0), {"score": 0.70, "breite_px": 120.0, "kennung": "P"})]
    vektoren = {("1", 0): np.asarray(_vektor(0)), ("2", 0): np.asarray(_vektor(0)),
                ("3", 0): np.asarray(_vektor(90))}
    ohne = mr.mittelpunkt_verschiebung(vektoren, gesichter, art="unsicher")
    beide = mr.mittelpunkt_verschiebung(vektoren, gesichter, art="beide")
    assert ohne["sauber"] == 2 and ohne["winkel"] > 0.05
    assert beide["sauber"] == 2 and beide["winkel"] == pytest.approx(ohne["winkel"])


def test_verschiebung_ohne_saubere_gesichter_ist_none():
    gesichter = [(("1", 0), {"score": 0.5, "breite_px": 120.0, "kennung": "P"})]
    m = mr.mittelpunkt_verschiebung({("1", 0): np.asarray(_vektor(0))}, gesichter)
    assert m["sauber"] == 0 and m["winkel"] is None


def test_grobe_ausschnitte_zaehlen_eigenstaendig():
    gesichter = [(("1", 0), {"score": 0.95, "breite_px": 120.0, "kennung": "P"}),
                 (("2", 0), {"score": 0.95, "breite_px": 20.0, "kennung": "P"})]
    vektoren = {("1", 0): np.asarray(_vektor(0)), ("2", 0): np.asarray(_vektor(60))}
    nur_grob = mr.mittelpunkt_verschiebung(vektoren, gesichter, art="grob")
    nur_unsicher = mr.mittelpunkt_verschiebung(vektoren, gesichter, art="unsicher")
    assert nur_grob["sauber"] == 1 and nur_grob["winkel"] > 0.05
    assert nur_unsicher["sauber"] == 2 and nur_unsicher["winkel"] == pytest.approx(0.0)


def test_neuordnung_zaehlt_die_wechsel():
    alle = {"Person_A": [(("1", 0), {"kennung": "Person_A", "score": 0.95, "breite_px": 120.0}),
                         (("2", 0), {"kennung": "Person_A", "score": 0.95, "breite_px": 120.0})],
            "Person_B": [(("3", 0), {"kennung": "Person_B", "score": 0.95, "breite_px": 120.0})]}
    vektoren = {("1", 0): np.asarray(_vektor(0)), ("2", 0): np.asarray(_vektor(15)),
                ("3", 0): np.asarray(_vektor(80))}
    ka, za = mr.zentren_matrix(alle, vektoren, nur_sauber=False)
    kr, zr = mr.zentren_matrix(alle, vektoren, nur_sauber=True)
    assert ka == ["Person_A", "Person_B"] and len(za) == 2 and len(zr) == 2
    sauber_liste = [(s, g) for m in alle.values() for s, g in m]
    n = mr.neuordnung(vektoren, sauber_liste, ka, za, kr, zr)
    assert n == {"geprueft": 3, "gewechselt": 0}
    leer = mr.neuordnung(vektoren, sauber_liste, [], np.zeros((0, 0)), kr, zr)
    assert leer == {"geprueft": 0, "gewechselt": 0}


def test_jahresphasen_nur_mit_genug_gesichtern():
    gesichter = []
    vektoren = {}
    for i in range(4):
        gesichter.append((("2020", i), {"kennung": "P", "score": 0.95 if i < 3 else 0.70,
                                        "breite_px": 120.0,
                                        "aufnahme": f"2020-05-0{i + 1}T10:00:00"}))
        vektoren[("2020", i)] = np.asarray(_vektor(0 if i < 3 else 90))
    gesichter.append((("2021", 0), {"kennung": "P", "score": 0.95, "breite_px": 120.0,
                                    "aufnahme": "2021-01-01T00:00:00"}))
    vektoren[("2021", 0)] = np.asarray(_vektor(0))
    zuordnung = {s: g for s, g in gesichter}
    phasen = mr.jahresphasen(zuordnung, vektoren, "P", phasen_min=3)
    assert [p[0] for p in phasen] == ["2020"]          # 2021 hat nur ein Gesicht
    assert phasen[0][1] == 4 and phasen[0][2] == 3 and phasen[0][3] > 0.0


def test_jahresphasen_ohne_aufnahme_bleiben_weg():
    zuordnung = {("1", 0): {"kennung": "P", "score": 0.95, "breite_px": 120.0,
                            "aufnahme": None}}
    phasen = mr.jahresphasen(zuordnung, {("1", 0): np.asarray(_vektor(0))}, "P", phasen_min=1)
    assert phasen == []


# ── 3. Bericht und Aufruf ────────────────────────────────────────────────────

def _kleiner_bestand(tmp_path):
    zeilen = []
    for i in range(6):
        bild_id = f"9000{i:02d}"
        zeilen.append({"bild_id": bild_id, "index": 0, "kennung": "Person_001",
                       "score": 0.95 if i < 4 else 0.70, "bbox": [1.0, 1.0, 120.0, 120.0],
                       "anteil": 0.02, "aufnahme": "2015-06-01T10:00:00", "video_id": None})
    zeilen.append({"bild_id": "900099", "index": 0, "kennung": None, "score": 0.95,
                   "bbox": [1.0, 1.0, 120.0, 120.0], "anteil": 0.02, "aufnahme": None,
                   "video_id": None})
    zu = _zuordnungsdatei(tmp_path / "z.jsonl", zeilen)
    ve = _vektordatei(tmp_path / "v.jsonl", [
        (f"9000{i:02d}", 0, _vektor(0 if i < 4 else 80)) for i in range(6)])
    return zu, ve


def test_bericht_nennt_nur_zahlen_und_kennungen(tmp_path):
    zu, ve = _kleiner_bestand(tmp_path)
    zuordnung, ohne = mr.zuordnung_lesen(str(zu))
    vektoren, statistik = mr.vektoren_sammeln([str(ve)], schluessel=set(zuordnung))
    text = "\n".join(mr.bericht(zuordnung, ohne, vektoren, statistik, gruppe_min=3,
                                phasen_min=3, zeigen=2))
    assert "Person_001" in text
    assert "900001" not in text and "900000" not in text      # keine Bild-IDs
    assert ".jsonl" not in text                               # keine Pfade
    assert "Nicht sicher (score < 0.9)" in text
    assert "Verschiebung des Gruppenmittelpunkts" in text
    assert "Neuordnung" in text and "Lebensphasen" in text


def test_main_laeuft_und_zaehlt(tmp_path, capsys):
    zu, ve = _kleiner_bestand(tmp_path)
    code = mr.main(["--zuordnung", str(zu), "--vektoren", str(ve), "--gruppe-min", "3",
                    "--phasen-min", "3"])
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Gesichter in Gruppen: 6" in ausgabe
    assert "ohne Kennung (nicht gezaehlt): 1" in ausgabe


def test_main_bricht_bei_fehlender_zuordnung_und_ohne_vektoren_ab(tmp_path, capsys):
    assert mr.main(["--zuordnung", str(tmp_path / "nix.jsonl"),
                    "--vektoren", str(tmp_path / "auchnix.jsonl")]) == 2
    assert "Zuordnungsdatei nicht gefunden" in capsys.readouterr().out
    zu, _ = _kleiner_bestand(tmp_path)
    assert mr.main(["--zuordnung", str(zu),
                    "--vektoren", str(tmp_path / "auchnix.jsonl")]) == 2
    assert "keine der Vektordateien gefunden" in capsys.readouterr().out
