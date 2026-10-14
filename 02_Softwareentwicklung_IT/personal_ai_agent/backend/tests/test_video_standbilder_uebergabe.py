"""V4 (Plan video-gesichter-im-quiz): die Ergebnisdatei kommt ohne Kabel ans Handy.

Zwei Belege, offline:
  1. Echte Kette ``video_standbilder.main(--schreiben --uebergeben)`` -> echtes
     ``uebergabe_hochladen`` (``planen`` -> ``hochladen_lauf``), nur ``httpx`` ist Attrappe.
     Die Ergebnisdatei kommt ohne Typfehler bis zum Hochlade-Aufruf.
  2. Sandkastenlauf von ``termux/pcloud-uebernehmen.sh`` mit dem echten Standard-Ziel
     ``$HOME/foto_sortierung``: ``gruppen_quiz._lesepfad`` findet die Datei dort.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import httpx

from test_pcloud_uebergabe import (FakeGet, FakePost, _bash, _ok, _ohne_msys,  # noqa: F401
                                   _posix, _sandkasten)

PROJEKT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJEKT / "backend"))

from app.services import gruppen_quiz as gq  # noqa: E402

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"


def _laden(name, pfad):
    spez = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


vs = _laden("vs_uebergabe_test", PROJEKT / "tools" / "foto_sortierung" / "video_standbilder.py")


class ListenDienst:
    def __init__(self):
        self.geholt = []

    def datei_bytes(self, fileid, max_bytes):
        self.geholt.append(fileid)
        return b"videodaten"

    def liste(self, folderid):
        return []


def _entnehmen(pfad, zeiten, max_seite):
    for zt in zeiten:
        yield zt, 1920, 1080, vs.massstab(1920, 1080, max_seite), b"\xff\xd8jpeg"


def _ordner(folderid):
    return _ok(metadata={"folderid": folderid, "path": "/Agent/x"})


def test_echte_kette_bis_zum_hochladen(tmp_path, monkeypatch):
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", HOST)
    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setenv("PCLOUD_UEBERGABE_MANIFEST", str(manifest))
    uebergabe = _laden("uebergabe_hochladen_v4", PROJEKT / "tools" / "pcloud" / "uebergabe_hochladen.py")
    monkeypatch.setattr(uebergabe, "ENV_DATEI", tmp_path / "keine.env")
    fake_get = FakeGet(_ordner(11), _ordner(22))      # Standbild-Ordner, dann Uebergabe-Ordner
    fake_post = FakePost(_ok(fileids=[901]), _ok(fileids=[902]))
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    zuordnung = tmp_path / "z.jsonl"
    zuordnung.write_text(json.dumps({
        "kennung": "Person_3001", "video_id": "55", "zeit_s": 4.0, "bild_id": "55#t=4.0",
        "index": 0, "bbox": [10, 10, 50, 50], "breite": 1920, "hoehe": 1080,
        "anteil": 0.01, "score": 0.9}) + "\n", encoding="utf-8")
    ergebnis = tmp_path / gq.VIDEO_STANDBILDER_DATEINAME

    code = vs.main(["--zuordnung", str(zuordnung), "--ergebnis", str(ergebnis),
                    "--schreiben", "--uebergeben"],
                   dienst=ListenDienst(), uebergabe=uebergabe, entnehmen=_entnehmen)

    assert code == 0
    assert [a["params"]["path"] for a in fake_get.aufrufe] == [vs.ZIELORDNER, "/Agent/uebergabe"]
    namen = [a["files"]["file"][0] for a in fake_post.aufrufe]
    assert namen == ["55_t4.0.jpg", gq.VIDEO_STANDBILDER_DATEINAME]
    assert fake_post.aufrufe[1]["params"]["folderid"] == 22
    assert fake_post.aufrufe[1]["files"]["file"][1] == ergebnis.read_bytes()
    zeile = json.loads(ergebnis.read_text(encoding="utf-8"))
    assert zeile["standbild_fileid"] == 901
    eintraege = [json.loads(z) for z in manifest.read_text(encoding="utf-8").splitlines()]
    assert [e["name"] for e in eintraege] == [gq.VIDEO_STANDBILDER_DATEINAME]
    assert TOKEN not in manifest.read_text(encoding="utf-8")


def test_handy_uebernahme_legt_karte_wo_das_quiz_sucht(tmp_path, monkeypatch):
    import subprocess
    sb = _sandkasten(tmp_path)
    heim = tmp_path / "heim"
    heim.mkdir()
    vorlage = tmp_path / "vorlage"
    vorlage.mkdir()
    inhalt = json.dumps({"bild_id": "55#t=4.0", "video_id": "55", "zeit_s": 4.0,
                         "standbild_fileid": 901, "breite": 1600, "hoehe": 900, "skala": 0.8}) + "\n"
    (vorlage / gq.VIDEO_STANDBILDER_DATEINAME).write_text(inhalt, encoding="utf-8")
    # Kein PCLOUD_UEBERGABE_ZIEL: das echte Standard-Ziel $HOME/foto_sortierung gilt.
    umgebung = dict(os.environ, HOME=_posix(heim),
                    PCLOUD_UEBERGABE_STAGING=_posix(heim / "staging"),
                    PCLOUD_UEBERGABE_PROTOKOLL=_posix(heim / "proto.log"),
                    BH_VORLAGE=_posix(vorlage),
                    PATH=_posix(tmp_path / "bin") + os.pathsep + os.environ.get("PATH", ""))
    for name in ("PROJEKT", "PCLOUD_UEBERGABE_ZIEL"):
        umgebung.pop(name, None)
    lauf = subprocess.run([_bash(), _posix(sb / "termux" / "pcloud-uebernehmen.sh"), _posix(sb)],
                          env=_ohne_msys(umgebung), capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    basisordner = heim / "foto_sortierung"
    assert (basisordner / gq.VIDEO_STANDBILDER_DATEINAME).read_text(encoding="utf-8") == inhalt
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(basisordner))
    gq._CACHE.clear()
    try:
        gefunden = gq._lesepfad(gq.VIDEO_STANDBILDER_DATEINAME)
        assert gefunden and Path(gefunden) == basisordner / gq.VIDEO_STANDBILDER_DATEINAME
        assert gq._video_karte() == {"55#t=4.0": {"fileid": "901", "breite": 1600, "hoehe": 900,
                                                  "skala": 0.8}}
    finally:
        gq._CACHE.clear()
