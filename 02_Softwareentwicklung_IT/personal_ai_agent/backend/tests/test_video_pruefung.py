"""Tests fuer tools/foto_sortierung/video_pruefung.py (To-do Punkt 5, 18.10.2026).

Offline: erfundene Kennungen und kleine Attrappen-Dateien in ``tmp_path``.
Der pCloud-Leser wird injiziert — kein Test greift ins Netz.
"""
import importlib.util
import json
import os
import sys

import pytest

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
WERKZEUG = os.path.join(PROJEKT, "tools", "foto_sortierung", "video_pruefung.py")


def _laden():
    spez = importlib.util.spec_from_file_location("video_pruefung_test", WERKZEUG)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


vp = _laden()


def _jsonl(pfad, zeilen):
    with open(pfad, "w", encoding="utf-8") as f:
        for z in zeilen:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    return str(pfad)


def _plan(pfad, videos, bilder=0):
    zuege = [{"fileid": v, "art": "video", "von_name": "x.mp4"} for v in videos]
    zuege += [{"fileid": 9000000 + i, "art": "bild", "von_name": "y.jpg"}
              for i in range(bilder)]
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump({"zuege": zuege}, f)
    return str(pfad)


def _standbild(vid, zeit, fid, breite=1600, hoehe=900, skala=1.0):
    return {"bild_id": f"{vid}#t={zeit:.1f}", "video_id": str(vid), "zeit_s": zeit,
            "standbild_fileid": fid, "breite": breite, "hoehe": hoehe, "skala": skala,
            "stand": "2026-10-14T19:43:46+00:00"}


def _gesicht(vid, zeit, kennung, index=0):
    return {"bild_id": f"{vid}#t={zeit:.1f}", "video_id": str(vid), "zeit_s": zeit,
            "index": index, "kennung": kennung, "bbox": [1, 2, 3, 4],
            "breite": 1920.0, "hoehe": 1080.0, "anteil": 0.01, "score": 0.9}


def _foto_gesicht(fid, kennung):
    return {"bild_id": str(fid), "video_id": None, "index": 0, "kennung": kennung,
            "bbox": [1, 2, 3, 4]}


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------

def test_plan_liest_nur_videos(tmp_path):
    p = _plan(tmp_path / "plan.json", ["111", "222"], bilder=3)
    assert vp.video_ids_aus_plan(p) == ["111", "222"]


def test_fehlende_datei_ist_leer_und_wirft_nicht(tmp_path):
    assert vp.video_ids_aus_plan(str(tmp_path / "gibtsnicht.json")) == []
    assert list(vp.zeilen_lesen(str(tmp_path / "gibtsnicht.jsonl"))) == []
    assert vp.standbilder_lesen(str(tmp_path / "gibtsnicht.jsonl")) == {}


def test_kaputte_zeilen_werden_uebersprungen(tmp_path):
    pfad = tmp_path / "s.jsonl"
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(json.dumps(_standbild("111", 4, 5001)) + "\n")
        f.write("kein json\n")
        f.write("\n")
        f.write(json.dumps(_standbild("111", 8, 5002)) + "\n")
    s = vp.standbilder_lesen(str(pfad))
    assert sorted(s) == ["111"]
    assert len(s["111"]) == 2


def test_nur_video_gesichter_zaehlen(tmp_path):
    p = _jsonl(tmp_path / "z.jsonl", [
        _gesicht("111", 4, "Person_1"),
        _foto_gesicht(999, "Person_1"),      # Foto: darf nicht mitzaehlen
        _gesicht("222", 10, None),
    ])
    e = vp.einzeln_kennungen_lesen(p)
    assert sorted(e) == ["111#t=4.0", "222#t=10.0"]
    je_video = vp.kennungen_zum_video(e)
    assert sorted(je_video) == ["111", "222"]


# --------------------------------------------------------------------------
# Wiederholungen
# --------------------------------------------------------------------------

def test_wiederholung_zaehlt_person_auf_mehreren_bildstellen():
    je_video = {
        "111": [_gesicht("111", 4, "Person_1"), _gesicht("111", 8, "Person_1"),
                _gesicht("111", 8, "Person_2", index=1), _gesicht("111", 12, None)],
        "222": [_gesicht("222", 2, "Person_3")],
    }
    w = vp.wiederholungen(je_video)
    assert w["videos"] == 2
    assert w["personen_mehrfach_summe"] == 1          # nur Person_1 zweimal
    assert w["videos_mit_wiederholung"] == 1
    assert w["hoechste_wiederholung"] == 2
    assert w["je_video"]["111"]["bildstellen"] == 3    # 4.0 / 8.0 / 12.0
    assert w["je_video"]["111"]["gesichter"] == 4
    assert w["je_video"]["111"]["mit_person"] == 3
    assert w["je_video"]["111"]["personen"] == 2
    assert w["verteilung"] == {0: 1, 1: 1}
    assert w["videos_mit_einer_bildstelle"] == 1     # Video 222
    assert w["videos_ueber_zehn_personen"] == 0


def test_dieselbe_person_zweimal_auf_einer_bildstelle_wird_gezaehlt():
    je_video = {"111": [_gesicht("111", 4, "Person_1"),
                        _gesicht("111", 4, "Person_1", index=1)]}
    w = vp.wiederholungen(je_video)
    assert w["doppel_je_bildstelle"] == 1
    # dieselbe Person auf nur EINER Bildstelle ist keine Mehrfach-Wiederholung
    assert w["personen_mehrfach_summe"] == 0


def test_leere_zuordnung_ergibt_nullen():
    w = vp.wiederholungen({})
    assert w["videos"] == 0 and w["hoechste_wiederholung"] == 0
    assert w["verteilung"] == {}


# --------------------------------------------------------------------------
# Standbilder
# --------------------------------------------------------------------------

def test_doppelte_standbilder_werden_erkannt():
    stand = {
        "111": [_standbild("111", 4, 5001), _standbild("111", 8, 5002)],
        "222": [_standbild("222", 2, 5002)],          # dieselbe Kennung nochmal
    }
    s = vp.standbild_zahlen(stand)
    assert s["videos"] == 2
    assert s["standbilder"] == 3
    assert s["verschiedene_fids"] == 2
    assert s["doppelte_fids"] == 1


def test_standbild_ohne_mass_wird_gezaehlt():
    stand = {"111": [_standbild("111", 4, 5001, breite=0, hoehe=0)]}
    s = vp.standbild_zahlen(stand)
    assert s["ohne_mass"] == 1
    assert s["min_je_video"] == s["max_je_video"] == 1


# --------------------------------------------------------------------------
# Helligkeit / Probe (nur mit PIL und injiziertem Leser)
# --------------------------------------------------------------------------

def _png(grauwert):
    pil = pytest.importorskip("PIL.Image")
    import io
    buf = io.BytesIO()
    pil.new("L", (8, 8), grauwert).save(buf, "PNG")
    return buf.getvalue()


def test_helligkeit_schwarz_und_weiss():
    if vp.helligkeit_messen(_png(0)) is None:
        pytest.skip("PIL nicht verfuegbar")
    schwarz = vp.helligkeit_messen(_png(0))
    weiss = vp.helligkeit_messen(_png(255))
    assert schwarz["mittel"] < vp.DUNKEL_SCHWELLE
    assert weiss["mittel"] > 250
    assert weiss["streuung"] == 0


def test_helligkeit_kaputter_bytes_liefert_none():
    assert vp.helligkeit_messen(b"kein bild") is None


def test_probe_zaehlt_dunkel_und_grenze_ein():
    stand = {"111": [_standbild("111", 4, 5001), _standbild("111", 8, 5002)],
             "222": [_standbild("222", 2, 5003)]}
    bilder = {5001: _png(0), 5002: _png(255), 5003: _png(200)}
    p = vp.standbild_probe(stand, 2, lambda fid: bilder[fid])
    assert p["geprueft"] == 2 and p["dunkel"] == 1 and p["nicht_lesbar"] == 0


def test_probe_meldet_lesefehler_ehrlich():
    stand = {"111": [_standbild("111", 4, 5001)]}

    def kaputt(fid):
        raise RuntimeError("Netz weg")

    p = vp.standbild_probe(stand, 1, kaputt)
    assert p["geprueft"] == 1 and p["nicht_lesbar"] == 1 and p["dunkel"] == 0
    assert "Netz weg" in p["einzelwerte"][0]["fehler"]


def test_probe_null_prueft_nichts():
    stand = {"111": [_standbild("111", 4, 5001)]}
    p = vp.standbild_probe(stand, 0, lambda fid: b"x")
    assert p["geprueft"] == 0


# --------------------------------------------------------------------------
# Gesamtlauf
# --------------------------------------------------------------------------

def test_pruefen_trennt_die_drei_mengen_ehrlich(tmp_path):
    plan = _plan(tmp_path / "plan.json", ["111", "222", "333"])
    stand = _jsonl(tmp_path / "s.jsonl", [
        _standbild("111", 4, 5001),
        _standbild("444", 2, 5002),          # Standbild zu einem Video ohne Plan
    ])
    zuordnung = _jsonl(tmp_path / "z.jsonl", [
        _gesicht("111", 4, "Person_1"),
        _gesicht("222", 4, "Person_2"),      # Video mit Gesicht, ohne Standbild
        _foto_gesicht(999, "Person_1"),
    ])
    e = vp.pruefen(plan=plan, standbilder_datei=stand, zuordnung=zuordnung)
    m = e["mengen"]
    assert m["plan_videos"] == 3
    assert m["plan_videos_mit_standbild"] == 1
    assert m["plan_videos_ohne_standbild"] == 2
    assert m["videos_mit_gesichtern"] == 2
    assert m["videos_mit_gesichtern_ohne_standbild"] == 1
    assert m["standbild_videos_ohne_gesichter"] == 1
    assert m["gesichter_in_videos"] == 2
    assert m["gesichter_in_videos_mit_person"] == 2
    assert e["ohne_standbild"] == ["222"]
    assert e["plan_ohne_standbild"] == ["222", "333"]
    assert "probe" not in e           # ohne Schalter kein Netzzugriff


def test_bericht_nennt_zahlen_und_keine_namen(tmp_path):
    plan = _plan(tmp_path / "plan.json", ["111"])
    stand = _jsonl(tmp_path / "s.jsonl", [_standbild("111", 4, 5001)])
    zuordnung = _jsonl(tmp_path / "z.jsonl", [_gesicht("111", 4, "Person_1")])
    e = vp.pruefen(plan=plan, standbilder_datei=stand, zuordnung=zuordnung)
    text = vp.bericht(e)
    assert "Video-Pruefung" in text
    assert "Plan-Videos:                     1" in text
    assert "Person_1" not in text and "x.mp4" not in text


def test_main_trockenlauf_schreibt_nichts(tmp_path, monkeypatch, capsys):
    plan = _plan(tmp_path / "plan.json", ["111"])
    stand = _jsonl(tmp_path / "s.jsonl", [_standbild("111", 4, 5001)])
    zuordnung = _jsonl(tmp_path / "z.jsonl", [_gesicht("111", 4, "Person_1")])
    bericht_pfad = tmp_path / "bericht.json"
    liste_pfad = tmp_path / "liste.txt"
    monkeypatch.setattr(vp, "STANDARD_BERICHT", str(bericht_pfad))
    monkeypatch.setattr(vp, "STANDARD_LISTE", str(liste_pfad))
    assert vp.main(["--plan", plan, "--standbilder", stand,
                    "--zuordnung", zuordnung]) == 0
    assert not bericht_pfad.exists() and not liste_pfad.exists()
    # mit --schreiben und --liste entstehen beide Dateien
    assert vp.main(["--plan", plan, "--standbilder", stand, "--zuordnung", zuordnung,
                    "--schreiben", "--liste"]) == 0
    daten = json.loads(bericht_pfad.read_text(encoding="utf-8"))
    assert daten["mengen"]["plan_videos"] == 1
    assert liste_pfad.read_text(encoding="utf-8") == ""
    capsys.readouterr()
