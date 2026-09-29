"""Tests fuer tools/foto_sortierung/video_gesichter.py (E14b) — nur synthetisch.

Dienst, Modell und Frame-Entnahme sind Attrappen; kein cv2, kein Netz, keine
echten Videos oder Bilder.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
PFAD = PROJEKT / "tools" / "foto_sortierung" / "video_gesichter.py"


def _laden():
    spez = importlib.util.spec_from_file_location("vg_unter_test", PFAD)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


vg = _laden()
pc = vg._basis()._personen_cluster()


class PCloudZuGross(Exception):
    pass


class Dienst:
    def __init__(self, daten=None, fehler=None):
        self.daten = daten or {}
        self.fehler = fehler or {}
        self.gerufen = []

    def datei_bytes(self, fileid, max_bytes):
        self.gerufen.append((str(fileid), max_bytes))
        if str(fileid) in self.fehler:
            raise self.fehler[str(fileid)]
        return self.daten.get(str(fileid), b"VIDEO" + str(fileid).encode())


def _gesicht():
    return {"bbox": [10.0, 10.0, 40.0, 40.0], "score": 0.9,
            "embedding": [0.01 * i for i in range(128)]}


class Modell:
    """Liefert ein Gesicht, wenn die Frame-Bytes mit b'G' beginnen."""

    def gesichter(self, roh, bild_id=""):
        mit = roh.startswith(b"G")
        return {"bild_id": bild_id, "breite": 640, "hoehe": 480,
                "gesichter": [_gesicht()] if mit else []}


def frames_fn(zeiten_und_typ):
    """Attrappe: [(zeit, b'G'|b'N')]; merkt sich den Temp-Pfad."""
    spur = {"pfade": []}

    def erzeugen(pfad, abstand, maximum):
        spur["pfade"].append(pfad)
        assert os.path.isfile(pfad)          # Temp-Datei existiert waehrend der Nutzung
        for zeit, art in zeiten_und_typ:
            yield zeit, art + b"jpeg"

    erzeugen.spur = spur
    return erzeugen


def plan_schreiben(pfad, zuege):
    Path(pfad).write_text(json.dumps({"zuege": zuege}), encoding="utf-8")


PLAN = [
    {"fileid": 1, "jahr": 2020, "von_name": "a.MP4"},
    {"fileid": 2, "jahr": 2020, "von_name": "b.jpg"},
    {"fileid": 3, "jahr": 2021, "von_name": "c.mov"},
    {"fileid": 4, "jahr": 2021, "von_name": "d.png"},
    {"fileid": 5, "jahr": 2021, "von_name": "e.3gp"},
    {"fileid": 6, "jahr": None, "von_name": "f.mkv"},
    {"fileid": 7, "jahr": 2019, "von_name": "g.avi"},
    {"fileid": 8, "jahr": 2019, "von_name": "h.M4V"},
    {"fileid": 9, "jahr": 2019},                       # ohne Namen
]


def test_plan_nur_videos(tmp_path):
    p = tmp_path / "plan.json"
    plan_schreiben(p, PLAN)
    ids = [v["fileid"] for v in vg.video_plan_lesen(str(p))]
    assert ids == ["1", "3", "5", "6", "7", "8"]


def test_plan_fehlt():
    with pytest.raises(vg.VideoFehler):
        vg.video_plan_lesen("/gibt/es/nicht.json")


def test_zeitpunkte():
    assert vg.zeitpunkte_rechnen(5.0, 2.0, 60) == [0.0, 2.0, 4.0]
    z = vg.zeitpunkte_rechnen(1000.0, 2.0, 60)
    assert len(z) == 60 and z[0] == 0.0 and z[-1] > 900
    assert vg.zeitpunkte_rechnen(0, 2.0, 60) == []


def test_frame_ohne_gesicht_nicht_geschrieben_aber_gezaehlt_und_bild_id():
    f = frames_fn([(0.0, b"N"), (2.0, b"G"), (4.0, b"N"), (6.5, b"G")])
    lauf = vg.VideoLauf([{"fileid": "42", "endung": ".mp4"}], Dienst(),
                        Modell(), 10**6, frames_fn=f)
    zeilen = list(lauf)
    assert [z["bild_id"] for z in zeilen] == ["42#t=2.0", "42#t=6.5"]
    assert all(z["video_id"] == "42" for z in zeilen)
    assert zeilen[0]["zeit_s"] == 2.0
    assert zeilen[0]["metadaten"] == {"aufnahme": None, "kamera_hersteller": None,
                                      "kamera_modell": None, "gps": None}
    z = lauf.zaehler
    assert (z["videos_gesamt"], z["videos_geholt"]) == (1, 1)
    assert (z["frames_gesamt"], z["frames_mit_gesicht"]) == (4, 2)
    assert lauf.fertig == ["42"]


def test_zeilen_fuer_personen_cluster_lesbar():
    f = frames_fn([(0.0, b"G")])
    zeilen = list(vg.VideoLauf([{"fileid": "7"}], Dienst(), Modell(), 10**6,
                               frames_fn=f))
    ergebnis = pc.zeile_pruefen(json.loads(json.dumps(zeilen[0])))
    assert ergebnis is not None
    assert ergebnis["bild_id"] == "7#t=0.0"
    assert len(ergebnis["gesichter"]) == 1


def test_zu_grosse_videos_uebersprungen():
    dienst = Dienst(fehler={"1": PCloudZuGross("gross")},
                    daten={"2": b"x" * 100})
    f = frames_fn([(0.0, b"G")])
    lauf = vg.VideoLauf([{"fileid": "1"}, {"fileid": "2"}, {"fileid": "3"}],
                        dienst, Modell(), 50, frames_fn=f)
    zeilen = list(lauf)
    # 1: Dienst meldet zu gross; 2: Bytes groesser als Grenze; 3: ok
    assert lauf.zaehler["zu_gross"] == 2
    assert lauf.zaehler["videos_geholt"] == 1
    assert [z["video_id"] for z in zeilen] == ["3"]
    assert lauf.fertig == ["3"]           # zu grosse bleiben offen


def test_temp_datei_wird_entfernt_auch_bei_fehler():
    pfade = []

    def kaputt(pfad, abstand, maximum):
        pfade.append(pfad)
        assert os.path.isfile(pfad)
        yield 0.0, b"Gjpeg"
        raise RuntimeError("Decoder kaputt")

    lauf = vg.VideoLauf([{"fileid": "9", "endung": ".mov"}], Dienst(),
                        Modell(), 10**6, frames_fn=kaputt)
    zeilen = list(lauf)
    assert len(zeilen) == 1                  # Frame vor dem Fehler bleibt
    assert lauf.zaehler["fehler"] == 1
    assert lauf.fertig == []                 # nicht als fertig vermerkt
    assert pfade and not os.path.exists(pfade[0])
    assert pfade[0].endswith(".mov")
    assert os.path.normcase(os.path.dirname(pfade[0])) \
        == os.path.normcase(tempfile.gettempdir())


def test_temp_datei_wird_im_normalfall_entfernt():
    f = frames_fn([(0.0, b"N")])
    list(vg.VideoLauf([{"fileid": "1"}], Dienst(), Modell(), 10**6, frames_fn=f))
    assert not os.path.exists(f.spur["pfade"][0])


def test_fehler_beim_holen_zaehlt_und_laeuft_weiter():
    dienst = Dienst(fehler={"1": RuntimeError("Netz")})
    f = frames_fn([(0.0, b"G")])
    lauf = vg.VideoLauf([{"fileid": "1"}, {"fileid": "2"}], dienst, Modell(),
                        10**6, frames_fn=f)
    assert [z["video_id"] for z in lauf] == ["2"]
    assert lauf.zaehler["fehler"] == 1


# ── main ────────────────────────────────────────────────────────────────

class FakeModellKlasse:
    laden_ok = True

    def __init__(self, modelle_dir=None):
        pass

    def _laden(self):
        if not FakeModellKlasse.laden_ok:
            raise ImportError("kein cv2")

    def gesichter(self, roh, bild_id=""):
        return Modell().gesichter(roh, bild_id)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan_schreiben(plan, PLAN)
    dienst = Dienst()
    FakeModellKlasse.laden_ok = True
    monkeypatch.setattr(vg._basis(), "GesichtsModell", FakeModellKlasse)
    monkeypatch.setattr(vg, "_pcloud_dienst", lambda: dienst)

    # Video 3 hat ein Gesicht, alle anderen nicht.
    def fn(pfad, abstand, maximum):
        with open(pfad, "rb") as d:
            inhalt = d.read()
        art = b"G" if inhalt == b"VIDEO3" else b"N"
        yield 0.0, art + b"x"
        yield 2.0, b"N" + b"x"

    monkeypatch.setattr(vg, "frames_entnehmen", fn)
    return {"plan": str(plan), "ziel": str(tmp_path / "out" / "v.jsonl"),
            "dienst": dienst}


def _zeilen(pfad):
    text = Path(pfad).read_text(encoding="utf-8")
    return [json.loads(z) for z in text.splitlines() if z.strip()]


def test_trockenlauf_schreibt_nichts(umgebung, capsys):
    assert vg.main(["--plan", umgebung["plan"], "--vektoren", umgebung["ziel"]]) == 0
    out = capsys.readouterr().out
    assert "Videos im Plan (Auswahl): 6" in out
    assert "2021: 2 Video(s)" in out
    assert not os.path.exists(umgebung["ziel"])
    assert not os.path.exists(umgebung["ziel"] + ".videos_fertig")
    assert umgebung["dienst"].gerufen == []


def test_schreiben_und_fortsetzen_auch_ohne_gesichter(umgebung, capsys):
    a = ["--plan", umgebung["plan"], "--vektoren", umgebung["ziel"], "--schreiben"]
    assert vg.main(a + ["--max-videos", "2"]) == 0        # Videos 1 und 3
    zeilen = _zeilen(umgebung["ziel"])
    assert [z["bild_id"] for z in zeilen] == ["3#t=0.0"]
    fertig = Path(umgebung["ziel"] + ".videos_fertig").read_text().split()
    assert fertig == ["1", "3"]                # Video 1 ohne Gesicht ist fertig
    out = capsys.readouterr().out
    assert "Frames gesamt: 4" in out and "Frames mit Gesicht: 1" in out

    umgebung["dienst"].gerufen.clear()
    assert vg.main(a + ["--fortsetzen"]) == 0
    geholt = [g[0] for g in umgebung["dienst"].gerufen]
    assert geholt == ["5", "6", "7", "8"]      # 1 und 3 uebersprungen
    assert len(_zeilen(umgebung["ziel"])) == 1  # angehaengt, nichts doppelt


def test_max_mb_wird_durchgereicht(umgebung):
    vg.main(["--plan", umgebung["plan"], "--vektoren", umgebung["ziel"],
             "--schreiben", "--max-mb", "1", "--max-videos", "1"])
    assert umgebung["dienst"].gerufen[0][1] == 1024 * 1024


def test_modell_nicht_ladbar_exit2_ohne_datei(umgebung, capsys):
    FakeModellKlasse.laden_ok = False
    rc = vg.main(["--plan", umgebung["plan"], "--vektoren", umgebung["ziel"],
                  "--schreiben"])
    assert rc == 2
    assert "nicht ladbar" in capsys.readouterr().out
    assert not os.path.exists(umgebung["ziel"])
    assert not os.path.exists(umgebung["ziel"] + ".videos_fertig")
    assert umgebung["dienst"].gerufen == []


def test_repo_pfad_exit2(umgebung):
    repo_ziel = str(PROJEKT / "video_test_nicht_schreiben.jsonl")
    with pytest.raises(SystemExit) as ex:
        vg.main(["--plan", umgebung["plan"], "--vektoren", repo_ziel,
                 "--schreiben"])
    assert ex.value.code == 2
    assert not os.path.exists(repo_ziel)
    assert umgebung["dienst"].gerufen == []


def test_ohne_cv2_frames_meldet_klar():
    if importlib.util.find_spec("cv2") is not None:
        pytest.skip("cv2 vorhanden")
    with pytest.raises(vg.VideoFehler):
        list(vg.frames_entnehmen("x.mp4"))


def test_echter_frame_test_mit_cv2(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    pfad = str(tmp_path / "t.avi")
    schreiber = cv2.VideoWriter(pfad, cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (64, 48))
    for i in range(30):                        # 6 s
        schreiber.write(np.full((48, 64, 3), i * 8, dtype=np.uint8))
    schreiber.release()
    frames = list(vg.frames_entnehmen(pfad, 2.0, 60))
    assert len(frames) >= 3
    assert frames[0][1][:2] == b"\xff\xd8"
