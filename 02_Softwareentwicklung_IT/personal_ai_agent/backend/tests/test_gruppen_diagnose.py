"""Pruefungen fuer ``tools/foto_sortierung/gruppen_diagnose.py`` (08.10.2026).

Offline, erfundene Gesichter und Kennungen, keine echten Daten.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "gruppen_diagnose.py"

spez = importlib.util.spec_from_file_location("gruppen_diagnose", WERKZEUG)
assert spez is not None and spez.loader is not None
gd = importlib.util.module_from_spec(spez)
spez.loader.exec_module(gd)


def _g(kennung, bild_id, score=0.95, anteil=0.02, video_id=None):
    return {"kennung": kennung, "bild_id": bild_id, "index": 0, "score": score,
            "anteil": anteil, "video_id": video_id}


def _schreiben(pfad: Path, zeilen) -> Path:
    pfad.write_text("".join(json.dumps(z) + "\n" for z in zeilen) + "kaputt\n", encoding="utf-8")
    return pfad


def test_merkmale_gedreht_unsicher_klein_video():
    gesichter = [_g("Person_1001", "1", score=0.95), _g("Person_1001", "2", score=0.7),
                 _g("Person_1001", "3", score=0.8, anteil=0.001),
                 _g("Person_1001", "9#t=2", video_id="9")]
    m = gd.merkmale(gesichter, {"1": 1, "2": 6})
    assert m["gesichter"] == 4
    assert m["video"] == 0.25
    assert abs(m["orientierung_bekannt"] - 2 / 3) < 1e-9     # "3" unbekannt, Video zaehlt nicht
    assert m["gedreht"] == 0.5
    assert m["unsicher"] == 0.5                                # 0.7 und 0.8 (Video 0.95)
    assert m["klein"] == 0.25


def test_merkmale_ohne_orientierung_ist_unbekannt():
    m = gd.merkmale([_g("Person_1001", "1")], {})
    assert m["gedreht"] is None and m["orientierung_bekannt"] == 0.0


def test_gruppen_nach_groesse_und_rauschen():
    zuordnung = [_g("Person_1002", "1"), _g("Person_1001", "2"), _g("Person_1001", "3"),
                 _g(None, "4")]
    reihe, rauschen = gd.gruppen_bilden(zuordnung)
    assert [k for k, _ in reihe] == ["Person_1001", "Person_1002"]
    assert len(rauschen) == 1


def test_main_vergleicht_gute_und_schlechte_gruppen(tmp_path, capsys):
    zeilen = []
    for i in range(10):                      # grosse, saubere Gruppe
        zeilen.append(_g("Person_1001", f"5000{i:02d}", score=0.97))
    for i in range(4):                       # kleine Gruppe aus gedrehten, unsicheren Funden
        zeilen.append(_g("Person_1050", f"6000{i:02d}", score=0.65))
    zuordnung = _schreiben(tmp_path / "z.jsonl", zeilen)
    orient = _schreiben(tmp_path / "o.jsonl",
                        [{"bild_id": f"5000{i:02d}", "orientierung": 1} for i in range(10)]
                        + [{"bild_id": f"6000{i:02d}", "orientierung": 6} for i in range(4)]
                        + [{"bild_id": "7", "fehler": "RuntimeError"}])
    code = gd.main(["--zuordnung", str(zuordnung), "--orientierung", str(orient), "--oben", "1"])
    ausgabe = capsys.readouterr().out
    assert code == 0
    zeile_gut = next(z for z in ausgabe.splitlines() if z.startswith("Gruppen 1-1 "))
    zeile_rest = next(z for z in ausgabe.splitlines() if z.startswith("Gruppen 2-Ende"))
    assert "0 %" in zeile_gut and "100 %" in zeile_rest
    assert "Person_1050" in ausgabe
    for z in zeilen:                         # keine Bild-IDs in der Ausgabe
        assert z["bild_id"] not in ausgabe


def test_fehlende_zuordnung_ist_exit_1(tmp_path):
    assert gd.main(["--zuordnung", str(tmp_path / "fehlt.jsonl")]) == 1
