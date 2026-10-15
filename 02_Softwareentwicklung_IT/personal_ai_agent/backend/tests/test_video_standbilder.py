"""Tests fuer tools/foto_sortierung/video_standbilder.py (Plan video-gesichter-im-quiz, V1).

Offline: erfundene Kennungen, Attrappen fuer pCloud, Hochladen und Frame-Entnahme.
Ein Test baut ein kleines kuenstliches Video und laeuft echt durch cv2 (falls vorhanden).
"""
import importlib.util
import json
import os
import sys

import pytest

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
WERKZEUG = os.path.join(PROJEKT, "tools", "foto_sortierung", "video_standbilder.py")


def _laden():
    spez = importlib.util.spec_from_file_location("video_standbilder_test", WERKZEUG)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


vs = _laden()


def _video(kennung, vid, zeit, *, anteil=0.01, score=0.9, breite=1920, hoehe=1080, index=0):
    return {"kennung": kennung, "video_id": vid, "zeit_s": zeit, "bild_id": f"{vid}#t={zeit:.1f}",
            "index": index, "bbox": [100, 100, 200, 200], "breite": breite, "hoehe": hoehe,
            "anteil": anteil, "score": score}


def _foto(kennung, fid):
    return {"kennung": kennung, "bild_id": str(fid), "fileid": fid, "index": 0,
            "bbox": [1, 1, 5, 5], "breite": 10, "hoehe": 10, "anteil": 0.1, "score": 0.9}


# ── Auswahl ───────────────────────────────────────────────────────────────

def test_nur_video_laesst_gruppen_mit_fotos_aus():
    zeilen = [_video("A", "11", 2.0), _foto("A", 5), _video("B", "12", 4.0)]
    a = vs.auswaehlen(zeilen, "nur_video")
    assert a["gruppen"] == 1 and a["frames"] == {"12": {"4.0": {"breite": 1920, "hoehe": 1080}}}


def test_alle_nimmt_auch_gemischte_gruppen():
    zeilen = [_video("A", "11", 2.0), _foto("A", 5), _video("B", "12", 4.0)]
    a = vs.auswaehlen(zeilen, "alle")
    assert a["gruppen"] == 2 and set(a["frames"]) == {"11", "12"}


def test_beste_je_gruppe_nach_anteil_mal_score():
    zeilen = [_video("A", "11", float(t), anteil=t / 100) for t in range(0, 20, 2)]
    a = vs.auswaehlen(zeilen, max_je_gruppe=3)
    assert set(a["frames"]["11"]) == {"18.0", "16.0", "14.0"} and a["gesichter"] == 3


def test_ein_frame_je_gruppe_nur_einmal():
    zeilen = [_video("A", "11", 2.0, index=0), _video("A", "11", 2.0, index=1, anteil=0.5)]
    a = vs.auswaehlen(zeilen)
    assert a["gesichter"] == 1 and list(a["frames"]["11"]) == ["2.0"]


def test_null_je_gruppe_nimmt_alle_frames_der_gruppe():
    # 0 = alle (15.10.2026): Die Gesamtansicht des Quiz soll ALLE Video-Gesichter
    # einer Gruppe zeigen; dafuer braucht es ein Standbild zu jedem Frame.
    zeilen = [_foto("A", 5)] + [_video("A", "11", float(t)) for t in range(0, 24, 2)]
    assert vs.auswaehlen(zeilen, "alle")["gesichter"] == 8              # Standard bleibt 8
    voll = vs.auswaehlen(zeilen, "alle", 0)
    assert voll["gesichter"] == 12 and len(voll["frames"]["11"]) == 12


def test_unbekannter_umfang_wird_abgelehnt():
    with pytest.raises(vs.StandbildFehler):
        vs.auswaehlen([], "irgendwas")


def test_kaputte_zeilen_werden_uebersprungen(tmp_path):
    p = tmp_path / "z.jsonl"
    p.write_text("kaputt\n" + json.dumps(_video("A", "11", 2.0)) + "\n[]\n", encoding="utf-8")
    assert len(vs.zeilen_lesen(str(p))) == 1


def test_namen_und_kennungen():
    assert vs.frame_kennung("11", 4) == "11#t=4.0"
    assert vs.standbild_name("11", 4.04) == "11_t4.0.jpg"


def test_offen_ohne_erledigte_und_ohne_fertige_videos():
    frames = {"11": {"2.0": {}, "4.0": {}}, "12": {"6.0": {}}}
    offen = vs.offen_rechnen(frames, {"11#t=2.0": {}, "12#t=6.0": {}})
    assert offen == {"11": {"4.0": {}}}


def test_massstab():
    assert vs.massstab(1920, 1080, 1600) == pytest.approx(1600 / 1920)
    assert vs.massstab(800, 600, 1600) == 1.0


# ── Lauf mit Attrappen ────────────────────────────────────────────────────

class Dienst:
    def __init__(self, fehler=None):
        self.geholt, self.fehler = [], fehler or {}

    def datei_bytes(self, fileid, max_bytes):
        self.geholt.append(fileid)
        if fileid in self.fehler:
            raise self.fehler[fileid]
        return b"videodaten"


def _entnehmen(mass=(1920, 1080)):
    def entnehmen(pfad, zeiten, max_seite):
        assert os.path.isfile(pfad)
        entnehmen.pfade.append(pfad)
        for zt in zeiten:
            yield zt, mass[0], mass[1], vs.massstab(*mass, max_seite), b"jpeg"
    entnehmen.pfade = []
    return entnehmen


def _lauf(tmp_path, offen, **kw):
    hochgeladen = []

    def hoch(name, daten):
        hochgeladen.append(name)
        return 1000 + len(hochgeladen)
    werte = dict(dienst=Dienst(), vorhandene={}, hochladen=hoch,
                 ergebnis=str(tmp_path / "erg.jsonl"), max_bytes=10, entnehmen=_entnehmen())
    werte.update(kw)
    return vs.Lauf(offen, **werte), hochgeladen, werte


def test_lauf_laedt_jedes_video_einmal_und_schreibt_zeilen(tmp_path):
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}, "4.0": {"breite": 1920, "hoehe": 1080}}}
    lauf, hoch, w = _lauf(tmp_path, offen)
    z = lauf.ausfuehren()
    assert w["dienst"].geholt == [11] and z["hochgeladen"] == 2 and z["zeilen"] == 2
    zeilen = [json.loads(x) for x in open(w["ergebnis"], encoding="utf-8")]
    assert zeilen[0]["bild_id"] == "11#t=2.0" and zeilen[0]["breite"] == 1600
    assert zeilen[0]["hoehe"] == 900 and zeilen[0]["skala"] == pytest.approx(0.833333)
    assert hoch == ["11_t2.0.jpg", "11_t4.0.jpg"]
    assert all(not os.path.exists(p) for p in w["entnehmen"].pfade)


def test_vorhandenes_standbild_wird_wiederverwendet(tmp_path):
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}}}
    lauf, hoch, w = _lauf(tmp_path, offen, vorhandene={"11_t2.0.jpg": 77})
    z = lauf.ausfuehren()
    assert hoch == [] and z["wiederverwendet"] == 1
    assert json.loads(open(w["ergebnis"], encoding="utf-8").read())["standbild_fileid"] == 77


def test_abweichendes_mass_wird_nicht_eingetragen(tmp_path):
    offen = {"11": {"2.0": {"breite": 1080, "hoehe": 1920}}}
    lauf, hoch, w = _lauf(tmp_path, offen)
    z = lauf.ausfuehren()
    assert z["mass_abweichend"] == 1 and hoch == [] and not os.path.exists(w["ergebnis"])


def test_zu_grosses_video_wird_gezaehlt(tmp_path):
    class PCloudZuGross(Exception):
        pass
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}}, "12": {"2.0": {"breite": 1920, "hoehe": 1080}}}
    lauf, hoch, w = _lauf(tmp_path, offen, dienst=Dienst({11: PCloudZuGross()}))
    z = lauf.ausfuehren()
    assert z["zu_gross"] == 1 and z["videos_geholt"] == 1 and hoch == ["12_t2.0.jpg"]


def test_hochladefehler_bricht_das_video_nicht_ab(tmp_path):
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}, "4.0": {"breite": 1920, "hoehe": 1080}}}
    aufrufe = []

    def hoch(name, daten):
        aufrufe.append(name)
        if len(aufrufe) == 1:
            raise RuntimeError("netz")
        return 5
    lauf, _, w = _lauf(tmp_path, offen, hochladen=hoch)
    z = lauf.ausfuehren()
    assert z["fehler"] == 1 and z["hochgeladen"] == 1 and z["zeilen"] == 1


def test_nicht_lesbare_frames_werden_gezaehlt(tmp_path):
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}, "99.0": {"breite": 1920, "hoehe": 1080}}}

    def entnehmen(pfad, zeiten, max_seite):
        yield "2.0", 1920, 1080, 1.0, b"j"
    lauf, _, _ = _lauf(tmp_path, offen, entnehmen=entnehmen)
    assert lauf.ausfuehren()["nicht_lesbar"] == 1


def test_max_videos_begrenzt(tmp_path):
    offen = {str(v): {"2.0": {"breite": 1920, "hoehe": 1080}} for v in (11, 12, 13)}
    lauf, _, w = _lauf(tmp_path, offen, max_videos=2)
    lauf.ausfuehren()
    assert w["dienst"].geholt == [11, 12]


def test_vorhandene_lesen_nur_dateien():
    class D:
        def liste(self, folderid):
            return [{"name": "a.jpg", "ist_ordner": False, "fileid": 3},
                    {"name": "x", "ist_ordner": True, "folderid": 9}]
    assert vs.vorhandene_lesen(D(), 1) == {"a.jpg": 3}


# ── Kommandozeile ─────────────────────────────────────────────────────────

class Uebergabe:
    def __init__(self):
        self.ordner, self.hoch, self.main_args = [], [], None

    def ordner_holen_oder_anlegen(self, pfad):
        self.ordner.append(pfad)
        return 42

    def hochladen(self, name, daten, folderid):
        self.hoch.append((name, folderid))
        return 500 + len(self.hoch)

    def main(self, argv):
        self.main_args = argv
        return 0


class ListenDienst(Dienst):
    def liste(self, folderid):
        return []


def _zuordnung(tmp_path):
    p = tmp_path / "zuordnung.jsonl"
    p.write_text("\n".join(json.dumps(z) for z in [
        _video("A", "11", 2.0), _video("A", "11", 4.0), _video("B", "12", 6.0)]) + "\n",
        encoding="utf-8")
    return str(p)


def test_trockenlauf_beruehrt_nichts(tmp_path, capsys):
    erg = tmp_path / "erg.jsonl"
    dienst, ueb = ListenDienst(), Uebergabe()
    code = vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(erg)],
                   dienst=dienst, uebergabe=ueb, entnehmen=_entnehmen())
    aus = capsys.readouterr().out
    assert code == 0 and "Offen: 2 Videos, 3 Standbilder" in aus
    assert dienst.geholt == [] and ueb.ordner == [] and not erg.exists()


def test_schreiben_und_zweiter_lauf_ist_leer(tmp_path, capsys):
    erg = tmp_path / "erg.jsonl"
    argv = ["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(erg), "--schreiben"]
    ueb = Uebergabe()
    assert vs.main(argv, dienst=ListenDienst(), uebergabe=ueb, entnehmen=_entnehmen()) == 0
    assert ueb.ordner == [vs.ZIELORDNER] and len(ueb.hoch) == 3 and {f for _, f in ueb.hoch} == {42}
    assert len(erg.read_text(encoding="utf-8").splitlines()) == 3
    dienst2, ueb2 = ListenDienst(), Uebergabe()
    assert vs.main(argv, dienst=dienst2, uebergabe=ueb2, entnehmen=_entnehmen()) == 0
    assert dienst2.geholt == [] and ueb2.hoch == []
    assert "Offen: 0 Videos" in capsys.readouterr().out


def test_uebergeben_ruft_die_uebergabe_mit_schreiben(tmp_path):
    erg = tmp_path / "erg.jsonl"
    ueb = Uebergabe()
    vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(erg), "--schreiben",
             "--uebergeben"], dienst=ListenDienst(), uebergabe=ueb, entnehmen=_entnehmen())
    assert ueb.main_args == ["--dateien", str(erg), "--schreiben"]


def test_ergebnis_im_repo_wird_abgelehnt(tmp_path):
    with pytest.raises(SystemExit) as e:
        vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis",
                 os.path.join(PROJEKT, "erg.jsonl")])
    assert e.value.code == 2


def test_konsole_nennt_keine_kennungen(tmp_path, capsys):
    zuordnung = tmp_path / "z.jsonl"
    zuordnung.write_text(json.dumps(_video("GRUPPE_XY", "987654321", 2.0)) + "\n", encoding="utf-8")
    erg = tmp_path / "erg.jsonl"
    vs.main(["--zuordnung", str(zuordnung), "--ergebnis", str(erg), "--schreiben"],
            dienst=ListenDienst(), uebergabe=Uebergabe(), entnehmen=_entnehmen())
    aus = capsys.readouterr().out
    assert "987654321" not in aus and "GRUPPE_XY" not in aus and "_t2.0" not in aus
    assert "zeilen 1" in aus


def test_gemeinsamer_dateiname_mit_dem_quiz():
    sys.path.insert(0, os.path.join(PROJEKT, "backend"))
    from app.services import gruppen_quiz
    assert vs.dateiname_ergebnis() == gruppen_quiz.VIDEO_STANDBILDER_DATEINAME


# ── echter cv2-Weg an einem kuenstlichen Video ────────────────────────────

def test_echte_entnahme_an_kuenstlichem_video(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    pfad = str(tmp_path / "v.avi")
    schreiber = cv2.VideoWriter(pfad, cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 200))
    if not schreiber.isOpened():
        pytest.skip("kein Video-Schreiber")
    for i in range(30):
        schreiber.write(np.full((200, 320, 3), i * 8, dtype=np.uint8))
    schreiber.release()
    teile = list(vs.standbilder_entnehmen(pfad, ["0.0", "2.0", "99.0"], max_seite=160))
    assert [t[0] for t in teile] == ["0.0", "2.0"]
    zt, b, h, skala, jpeg = teile[1]
    assert (b, h) == (320, 200) and skala == 0.5 and jpeg[:2] == b"\xff\xd8"
    bild = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert bild.shape[:2] == (100, 160)


# ── Ergebnispruefung R1 (14.10.2026): Codex-Befunde 1-3 ─────────────────────

def test_konsole_nennt_keinen_privaten_pfad(tmp_path, capsys):
    ordner = tmp_path / "PRIVATORDNER_XY"
    ordner.mkdir()
    erg = ordner / "erg.jsonl"
    vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(erg), "--schreiben"],
            dienst=ListenDienst(), uebergabe=Uebergabe(), entnehmen=_entnehmen())
    aus = capsys.readouterr().out
    assert "PRIVATORDNER_XY" not in aus and str(tmp_path) not in aus
    assert "<Ergebnisdatei>" in aus


def _verknuepfung(link, ziel):
    """Junction (Windows, ohne Adminrechte) oder Symlink; geht beides nicht -> skip."""
    try:
        import _winapi
        _winapi.CreateJunction(str(ziel), str(link))
        return
    except (ImportError, AttributeError, OSError):
        pass
    try:
        os.symlink(str(ziel), str(link), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("weder Junction noch Symlink moeglich")


def test_ergebnis_ueber_verknuepfung_ins_repo_wird_abgelehnt(tmp_path):
    link = tmp_path / "sieht_harmlos_aus"
    _verknuepfung(link, PROJEKT)
    try:
        with pytest.raises(SystemExit) as e:
            vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis",
                     str(link / "erg_verknuepft.jsonl")])
        assert e.value.code == 2
        assert not os.path.exists(os.path.join(PROJEKT, "erg_verknuepft.jsonl"))
    finally:
        # Nur die Verknuepfung selbst entfernen (nie ihr Ziel), damit das Aufraeumen
        # von tmp_path spaeter nicht ins Repo folgt.
        if os.path.islink(str(link)):
            os.unlink(str(link))
        elif os.path.isdir(str(link)):
            os.rmdir(str(link))       # Junction: rmdir loest nur den Verweis


def test_abgebrochene_halbe_zeile_verschluckt_die_naechste_nicht(tmp_path):
    erg = tmp_path / "erg.jsonl"
    erg.write_text('{"bild_id": "10#t=1.0", "standbild_fileid": 5}\n{"bild_id": "10#t=2',
                   encoding="utf-8")
    offen = {"11": {"2.0": {"breite": 1920, "hoehe": 1080}}}
    lauf, _, _ = _lauf(tmp_path, offen, ergebnis=str(erg))
    lauf.ausfuehren()
    zeilen = erg.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3 and zeilen[1] == '{"bild_id": "10#t=2'
    assert json.loads(zeilen[2])["bild_id"] == "11#t=2.0"
    assert vs.erledigte_lesen(str(erg)).keys() >= {"10#t=1.0", "11#t=2.0"}


def test_heile_datei_bekommt_keine_leerzeile(tmp_path):
    erg = tmp_path / "erg.jsonl"
    erg.write_text('{"bild_id": "10#t=1.0", "standbild_fileid": 5}\n', encoding="utf-8")
    lauf, _, _ = _lauf(tmp_path, {"11": {"2.0": {"breite": 1920, "hoehe": 1080}}},
                       ergebnis=str(erg))
    lauf.ausfuehren()
    assert "" not in erg.read_text(encoding="utf-8").splitlines()


def test_fortschritt_je_video_nur_zahlen(tmp_path):
    offen = {str(v): {"2.0": {"breite": 1920, "hoehe": 1080}} for v in (987654321, 987654322, 987654323)}
    zeilen = []
    lauf, _, _ = _lauf(tmp_path, offen, max_videos=2, melden=zeilen.append)
    lauf.ausfuehren()
    assert len(zeilen) == 2
    assert zeilen[0].startswith("Video 1/2 · Standbilder 1 · Fehler 0")
    assert zeilen[1] == "Video 2/2 · Standbilder 2 · Fehler 0"
    assert not any("98765432" in z or "_t2.0" in z for z in zeilen)


def test_fortschritt_zaehlt_fehler_und_zu_gross():
    z = {"zeilen": 3, "fehler": 1, "zu_gross": 2}
    assert vs.fortschritt_zeile(1, 4, z, 120.0) == "Video 1/4 · Standbilder 3 · Fehler 3 · noch ca. 6 min"
    assert vs.fortschritt_zeile(4, 4, z, 120.0) == "Video 4/4 · Standbilder 3 · Fehler 3"


def test_schreiblauf_zeigt_fortschritt_auf_der_konsole(tmp_path, capsys):
    erg = tmp_path / "erg.jsonl"
    vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(erg), "--schreiben"],
            dienst=ListenDienst(), uebergabe=Uebergabe(), entnehmen=_entnehmen())
    aus = capsys.readouterr().out
    assert "Video 1/2 ·" in aus and "Video 2/2 · Standbilder 3 · Fehler 0" in aus


def test_trockenlauf_nennt_die_begrenzung(tmp_path, capsys):
    vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(tmp_path / "e.jsonl"),
             "--max-videos", "1"], dienst=ListenDienst(), uebergabe=Uebergabe(),
            entnehmen=_entnehmen())
    assert "dieser Lauf nimmt 1 davon" in capsys.readouterr().out
    vs.main(["--zuordnung", _zuordnung(tmp_path), "--ergebnis", str(tmp_path / "e.jsonl")],
            dienst=ListenDienst(), uebergabe=Uebergabe(), entnehmen=_entnehmen())
    assert "--max-videos" not in capsys.readouterr().out
