"""Pruefungen fuer ``tools/foto_sortierung/orientierung_pruefen.py`` (08.10.2026).

Offline: erfundene Bild-IDs, kuenstliche JPEG-Koepfe, eingesteckter Kopf-Holer
statt pCloud. Kein Netz, keine echten Fotos.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "orientierung_pruefen.py"

spez = importlib.util.spec_from_file_location("orientierung_pruefen", WERKZEUG)
assert spez is not None and spez.loader is not None
op = importlib.util.module_from_spec(spez)
spez.loader.exec_module(op)


def _jpeg(orientierung: int) -> bytes:
    bild = Image.new("RGB", (40, 20), (10, 20, 30))
    exif = Image.Exif()
    exif[274] = orientierung
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", exif=exif)
    return puffer.getvalue()


# Erfundene Kennungen -> Orientierung
ORIENTIERUNG = {"1000001": 1, "1000002": 6, "1000003": 8, "1000004": 3, "1000005": 1}


def _vektoren(pfad: Path, zeilen) -> Path:
    pfad.write_text("".join(json.dumps(z) + "\n" for z in zeilen), encoding="utf-8")
    return pfad


def _standard_vektoren(tmp_path: Path) -> Path:
    return _vektoren(tmp_path / "v.jsonl", [
        {"bild_id": "1000001", "gesichter": [{"bbox": [1, 2, 3, 4]}]},
        {"bild_id": "1000002", "gesichter": [{"bbox": [1, 2, 3, 4]}]},
        {"bild_id": "1000003", "gesichter": []},
        {"bild_id": "1000004", "gesichter": [{"bbox": [1, 2, 3, 4]}]},
        {"bild_id": "1000005#t=4", "gesichter": [{"bbox": [1, 2, 3, 4]}]},  # Video
        {"bild_id": "1000002", "gesichter": []},                            # doppelt
    ])


class Holer:
    def __init__(self, kaputt=()):
        self.aufrufe = []
        self.kaputt = set(kaputt)

    def __call__(self, fileid):
        self.aufrufe.append(fileid)
        if fileid in self.kaputt:
            raise RuntimeError("Netz weg")
        return _jpeg(ORIENTIERUNG[fileid])[:4096]   # nur ein Kopfstueck


def _lauf(tmp_path, holer, *extra):
    ausgabe, plan = tmp_path / "o.jsonl", tmp_path / "plan.json"
    code = op.main(["--vektoren", str(_standard_vektoren(tmp_path)), "--ausgabe", str(ausgabe),
                    "--plan", str(plan), *extra], kopf_holen=holer)
    return code, ausgabe, plan


def test_bild_ids_ohne_video_und_ohne_doppelte(tmp_path):
    ids, mit = op.bild_ids_lesen([_standard_vektoren(tmp_path)])
    assert ids == ["1000001", "1000002", "1000003", "1000004"]
    assert mit == {"1000001", "1000002", "1000004"}


def test_trockenlauf_holt_nichts_und_schreibt_nichts(tmp_path, capsys):
    holer = Holer()
    code, ausgabe, plan = _lauf(tmp_path, holer)
    assert code == 0 and holer.aufrufe == []
    assert not ausgabe.exists() and not plan.exists()
    assert "offen: 4" in capsys.readouterr().out


def test_schreiben_liest_orientierung_und_plan_nur_gedrehte(tmp_path):
    code, ausgabe, plan = _lauf(tmp_path, Holer(), "--schreiben")
    assert code == 0
    zeilen = [json.loads(z) for z in ausgabe.read_text(encoding="utf-8").splitlines()]
    assert {z["bild_id"]: z["orientierung"] for z in zeilen} == {
        "1000001": 1, "1000002": 6, "1000003": 8, "1000004": 3}
    zuege = json.loads(plan.read_text(encoding="utf-8"))["zuege"]
    assert sorted(z["fileid"] for z in zuege) == ["1000002", "1000003", "1000004"]


def test_zweiter_lauf_holt_nichts_neu(tmp_path):
    _lauf(tmp_path, Holer(), "--schreiben")
    holer = Holer()
    code, ausgabe, _ = _lauf(tmp_path, holer, "--schreiben")
    assert code == 0 and holer.aufrufe == []
    assert len(ausgabe.read_text(encoding="utf-8").splitlines()) == 4


def test_fehler_bricht_nicht_ab_und_wird_wiederholt(tmp_path):
    code, ausgabe, _ = _lauf(tmp_path, Holer(kaputt={"1000002"}), "--schreiben")
    assert code == 3
    holer = Holer()
    code, ausgabe, plan = _lauf(tmp_path, holer, "--schreiben")
    assert code == 0 and holer.aufrufe == ["1000002"]
    zuege = json.loads(plan.read_text(encoding="utf-8"))["zuege"]
    assert "1000002" in [z["fileid"] for z in zuege]


def test_bericht_nur_zahlen(tmp_path, capsys):
    _lauf(tmp_path, Holer(), "--schreiben")
    ausgabe = capsys.readouterr().out
    assert "Betroffen (Orientierung != 1): 3" in ausgabe
    assert "davon mit Gesicht 2, ohne Gesicht 1" in ausgabe
    for kennung in ORIENTIERUNG:
        assert kennung not in ausgabe


def test_ziel_im_repo_ist_exit_2(tmp_path):
    code = op.main(["--vektoren", str(_standard_vektoren(tmp_path)),
                    "--ausgabe", str(REPO / "o.jsonl"), "--plan", str(tmp_path / "p.json"),
                    "--schreiben"], kopf_holen=Holer())
    assert code == 2
    assert not (REPO / "o.jsonl").exists()


def test_fehlende_vektordatei_ist_exit_1(tmp_path):
    code = op.main(["--vektoren", str(tmp_path / "fehlt.jsonl"), "--ausgabe",
                    str(tmp_path / "o.jsonl"), "--plan", str(tmp_path / "p.json")])
    assert code == 1
