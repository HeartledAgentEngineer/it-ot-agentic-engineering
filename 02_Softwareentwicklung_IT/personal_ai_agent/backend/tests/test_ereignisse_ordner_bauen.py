"""Tests: tools/foto_sortierung/ereignisse_ordner_bauen.py + Erzähl-Dienst (Issue #4 A1, 07.10.2026).

Erfundene Ordner, Dateinamen und Kennungen in ``tmp_path`` — keine echten Daten.
Geprüft: Datumsreihenfolge (EXIF > Dateiname > modified > Ordnerjahr > Planjahr),
Plausibilität (keine Unsinns-Jahre), Bündelung je Handordner, stabile Kennung,
Ausschluss schon vergebener Bilder, Ausgabe nur Zahlen, Schutz und Wiederholbarkeit,
und dass die Erzähl-Diashow die Datei chronologisch mitliest.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJEKT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.services import erzaehl_service  # noqa: E402

_spez = importlib.util.spec_from_file_location(
    "ereignisse_ordner_bauen", PROJEKT / "tools" / "foto_sortierung" / "ereignisse_ordner_bauen.py")
eob = importlib.util.module_from_spec(_spez)
_spez.loader.exec_module(eob)

HEUTE = datetime.date(2026, 10, 7)


def _jsonl(pfad: Path, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z if isinstance(z, str) else json.dumps(z) for z in zeilen) + "\n",
                    encoding="utf-8")


# ── 1. Datum je Datei ────────────────────────────────────────────────────────

def test_datum_aus_dateinamen_mit_und_ohne_uhrzeit():
    zeit, uhr = eob.datum_aus_name("IMG_20190705_143012.jpg")
    assert (zeit, uhr) == (datetime.datetime(2019, 7, 5, 14, 30, 12), True)
    zeit, uhr = eob.datum_aus_name("IMG-20190705-WA0001.jpg")            # WhatsApp: nur Datum
    assert zeit.date() == datetime.date(2019, 7, 5) and uhr is False
    zeit, uhr = eob.datum_aus_name("PXL_20210705_143012123.jpg")         # Millisekunden
    assert zeit == datetime.datetime(2021, 7, 5, 14, 30, 12) and uhr
    assert eob.datum_aus_name("2019-07-05 14.30.12.jpg")[0] == datetime.datetime(2019, 7, 5, 14, 30, 12)
    assert eob.datum_aus_name("DSC01234.JPG") is None
    assert eob.datum_aus_name("IMG_20191345_120000.jpg") is None         # Monat 13
    assert eob.datum_aus_name(None) is None


def test_datum_aus_exif_und_modified():
    assert eob.datum_aus_exif("2018-08-01T10:11:12") == (datetime.datetime(2018, 8, 1, 10, 11, 12), True)
    assert eob.datum_aus_exif("kaputt") is None and eob.datum_aus_exif(None) is None
    zeit, _ = eob.datum_aus_geaendert("Thu, 21 Feb 2019 10:00:00 +0000")
    assert zeit == datetime.datetime(2019, 2, 21, 10, 0, 0)
    assert eob.datum_aus_geaendert("2019-02-21T10:00:00Z")[0] == datetime.datetime(2019, 2, 21, 10, 0, 0)
    assert eob.datum_aus_geaendert("gestern") is None


def test_reihenfolge_exif_vor_dateiname_vor_modified():
    w = eob.datum_waehlen("2018-08-01T10:00:00", "IMG_20180802_100000.jpg", "Thu, 21 Feb 2019 10:00:00 +0000",
                          None, None, HEUTE)
    assert w["quelle"] == "exif" and w["zeit"].day == 1
    w = eob.datum_waehlen(None, "IMG_20180802_100000.jpg", "Thu, 21 Feb 2019 10:00:00 +0000", None, None, HEUTE)
    assert w["quelle"] == "dateiname" and w["zeit"].day == 2
    w = eob.datum_waehlen(None, "a.jpg", "Thu, 21 Feb 2019 10:00:00 +0000", None, None, HEUTE)
    assert w["quelle"] == "geaendert" and w["jahr"] == 2019


def test_unplausible_jahre_fallen_auf_die_naechste_quelle():
    # Kamera-Uhr auf 1970 und Unsinns-Jahr 1901 im Namen -> verworfen, Ordnerjahr bleibt
    w = eob.datum_waehlen("1970-01-01T00:00:00", "Bild_19010203_101010.jpg", None, 2005, None, HEUTE)
    assert w["quelle"] == "ordnerjahr" and w["jahr"] == 2005 and w["zeit"] is None and w["verworfen"] == 2
    w = eob.datum_waehlen("2031-01-01T00:00:00", "IMG_20140101_120000.jpg", None, None, None, HEUTE)
    assert w["quelle"] == "dateiname" and w["jahr"] == 2014              # Zukunft verworfen
    w = eob.datum_waehlen(None, "a.jpg", None, None, 1850, HEUTE)
    assert w["quelle"] == "ohne" and w["jahr"] is None


def test_ordnerjahr_gewinnt_bei_mehr_als_einem_jahr_abstand():
    # Scan von 1985 im Jahr 2013 (EXIF = Scan-Datum) im Ordner ".../1985"
    w = eob.datum_waehlen("2013-03-03T12:00:00", "scan.jpg", None, 1985, None, HEUTE)
    assert w["quelle"] == "ordnerjahr" and w["jahr"] == 1985 and w["ordnerjahr_gewinnt"]
    # Silvesterfoto nach Mitternacht im Ordner ".../2016" bleibt mit genauer Zeit
    w = eob.datum_waehlen("2017-01-01T00:30:00", "x.jpg", None, 2016, None, HEUTE)
    assert w["quelle"] == "exif" and w["jahr"] == 2017 and not w["ordnerjahr_gewinnt"]


def test_ordner_teile():
    assert eob.ordner_teile("/Bilder & Videos/Konzerte_Party/2016") == ("Konzerte Party", "Konzerte Party", 2016)
    assert eob.ordner_teile("Bilder & Videos/Urlaub/2000 Mallorca") == ("Urlaub", "2000 Mallorca", None)
    assert eob.ordner_teile("/Bilder & Videos/Familie") == ("Familie", "Familie", None)
    assert eob.ordner_teile("/Bilder & Videos") == (None, None, None)


# ── 2. Bündelung ─────────────────────────────────────────────────────────────

def _eintrag(fileid, ordner, zeit=None, jahr=None, quelle="exif", video=False):
    kategorie, name, _ = eob.ordner_teile(ordner)
    return {"fileid": fileid, "ordner": ordner, "kategorie": kategorie, "name": name, "video": video,
            "zeit": zeit, "mit_uhrzeit": zeit is not None, "jahr": zeit.year if zeit else jahr,
            "quelle": quelle if zeit else ("ordnerjahr" if jahr else "ohne"), "verworfen": 0,
            "ordnerjahr_gewinnt": False}


def test_reise_bleibt_ein_anlass_zwei_konzerte_werden_getrennt():
    d = datetime.datetime
    reise = "/Bilder & Videos/Urlaub/Testinsel"
    konzerte = "/Bilder & Videos/Konzerte_Party/2016"
    eintraege = [
        _eintrag(30, reise, d(2014, 7, 30, 18)), _eintrag(31, reise, d(2014, 7, 31, 9)),   # 15 h Nachtpause
        _eintrag(32, reise, d(2014, 8, 1, 8)),                                              # 23 h > 18 h -> neuer Anlass
        _eintrag(12, konzerte, d(2016, 6, 3, 21)), _eintrag(11, konzerte, d(2016, 6, 3, 22)),
        _eintrag(13, konzerte, d(2016, 6, 4, 21, 30)),                                      # nächster Abend
    ]
    knoten = eob.anlaesse_bilden(eintraege, luecke_stunden=18, stand="s")
    titel = [k["event"] for k in knoten]
    assert titel == ["Testinsel · Juli 2014", "Testinsel · August 2014",
                     "Konzerte Party · Juni 2016", "Konzerte Party · Juni 2016"]
    assert knoten[0]["datei_kennungen"] == [30, 31] and knoten[0]["datum"] == "2014-07-30" \
        and knoten[0]["bis"] == "2014-07-31"
    erstes_konzert = knoten[2]
    assert erstes_konzert["kennung"] == "O-11" and erstes_konzert["datei_kennungen"] == [12, 11]  # chronologisch
    assert erstes_konzert["kategorie"] == "Konzerte Party" and erstes_konzert["sammlung"] == "bilder_videos"
    # mit größerer Lücke bleibt die Reise zusammen, der Titel spannt beide Monate
    zusammen = eob.anlaesse_bilden(eintraege[:3], luecke_stunden=36)
    assert len(zusammen) == 1 and zusammen[0]["event"] == "Testinsel · Juli–August 2014"


def test_nur_jahr_und_ohne_datum_eigene_anlaesse_am_ende():
    d = datetime.datetime
    ordner = "/Bilder & Videos/Familie"
    knoten = eob.anlaesse_bilden([
        _eintrag(5, ordner, jahr=2010), _eintrag(6, ordner, jahr=2010), _eintrag(7, ordner),
        _eintrag(8, ordner, d(2010, 5, 1, 12)),
    ])
    assert [(k["datum"], k["jahr"], k["anzahl_dateien"]) for k in knoten] == [
        ("2010-05-01", 2010, 1), (None, 2010, 2), (None, None, 1)]
    assert knoten[1]["event"] == "Familie · 2010" and knoten[2]["event"] == "Familie"


def test_luecke_muss_positiv_sein():
    import pytest
    with pytest.raises(ValueError):
        eob.anlaesse_bilden([], luecke_stunden=0)


def test_eintraege_ueberspringen_vergebene_doppelte_und_ohne_kennung():
    zuege = [
        {"fileid": 1, "von_name": "IMG_20190705_143000.jpg", "von_ordner": "/Bilder & Videos/A"},
        {"fileid": 1, "von_name": "IMG_20190705_143000.jpg", "von_ordner": "/Bilder & Videos/A"},  # doppelt
        {"fileid": 2, "von_name": "b.jpg", "von_ordner": "/Bilder & Videos/A"},                    # Fotobuch
        {"von_name": "c.jpg"},                                                                      # ohne fileid
        {"fileid": 3, "von_name": "VID_20190706_100000.mp4", "von_ordner": "/Bilder & Videos/A"},
        {"fileid": 4, "von_name": "d.jpg", "von_ordner": "/Bilder & Videos/A", "jahr": 2019,
         "modified": "Sat, 06 Jul 2019 11:00:00 +0000"},
    ]
    eintraege, zahlen = eob.eintraege_bauen(zuege, {}, {}, {2}, HEUTE)
    assert [e["fileid"] for e in eintraege] == [1, 3, 4]
    assert (zahlen["doppelt"], zahlen["schon_in_anderen_anlaessen"], zahlen["ohne_fileid"]) == (1, 1, 1)
    assert (zahlen["fotos"], zahlen["videos"]) == (2, 1)
    assert (zahlen["quelle_dateiname"], zahlen["quelle_geaendert"]) == (2, 1)


# ── 3. Kommandozeile: Trockenlauf, Schreiben, Schutz, nur Zahlen ─────────────

GEHEIMER_ORDNER = "Geheimordner_Testperson"


def _bestand(tmp_path):
    (tmp_path / "sortierplan_bildervideos.json").write_text(json.dumps({"zuege": [
        {"fileid": 101, "von_name": "IMG_A.jpg", "von_ordner": f"/Bilder & Videos/{GEHEIMER_ORDNER}/2018"},
        {"fileid": 102, "von_name": "IMG_B.jpg", "von_ordner": f"/Bilder & Videos/{GEHEIMER_ORDNER}/2018"},
        {"fileid": 103, "von_name": "IMG-20180902-WA0001.jpg", "von_ordner": f"/Bilder & Videos/{GEHEIMER_ORDNER}/2018"},
        {"fileid": 104, "von_name": "seite.jpg", "von_ordner": "/Bilder & Videos/___Photobücher_Test"},
        {"fileid": 105, "von_name": "VID_20180901_120000.mp4", "von_ordner": f"/Bilder & Videos/{GEHEIMER_ORDNER}/2018"},
    ]}), encoding="utf-8")
    _jsonl(tmp_path / "personen_vektoren_n0929_bildervideos.jsonl", [
        {"bild_id": "101", "gesichter": [], "metadaten": {"aufnahme": "2018-09-01T10:00:00", "gps": None}},
        {"bild_id": "102", "gesichter": [{"embedding": [0.1]}], "metadaten": {"aufnahme": "2018-09-01T11:00:00"}},
        "kaputt",
    ])
    _jsonl(tmp_path / "video_vektoren_bildervideos.jsonl", [{"bild_id": "105#t=2", "gesichter": []}])
    _jsonl(tmp_path / "fotobuch_ereignisse.jsonl", [{"kennung": "fotobuch-1", "datei_kennungen": [104]}])
    return tmp_path / "sortierplan_bildervideos.json"


def test_trockenlauf_schreibt_nichts_und_zeigt_nur_zahlen(tmp_path, capsys):
    plan = _bestand(tmp_path)
    ziel = tmp_path / "ordner_ereignisse.jsonl"
    assert eob.main(["--plan", str(plan), "--ausgabe", str(ziel)], heute=HEUTE) == 0
    aus = capsys.readouterr().out
    assert not ziel.exists() and "Trockenlauf" in aus
    assert GEHEIMER_ORDNER not in aus and "IMG" not in aus and "O-" not in aus
    assert "schon in Anlässen" not in aus and "schon in anderen Anlässen 1" in aus
    assert "exif 2" in aus and "dateiname 2" in aus


def test_schreiben_wiederholbar_und_im_format_der_diashow(tmp_path, capsys):
    plan = _bestand(tmp_path)
    ziel = tmp_path / "ordner_ereignisse.jsonl"
    assert eob.main(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"], heute=HEUTE) == 0
    zeilen = [json.loads(z) for z in ziel.read_text(encoding="utf-8").splitlines()]
    # 1.9.: zwei EXIF-Fotos + Video (Name mit Uhrzeit); WhatsApp-Bild vom 2.9. nur mit Datum
    # (gilt als 12:00) -> 24 h Abstand > 18 h -> eigener Anlass
    assert [z["kennung"] for z in zeilen] == ["O-101", "O-103"]
    anlass = zeilen[0]
    assert anlass["datei_kennungen"] == [101, 102, 105]
    assert anlass["datum"] == "2018-09-01" and anlass["bis"] == "2018-09-01" and anlass["videos"] == 1
    assert anlass["quellen"]["datum"] == {"dateiname": 1, "exif": 2}
    assert anlass["event"] == f"{GEHEIMER_ORDNER.replace('_', ' ')} · September 2018"
    assert set(eob_knoten_schluessel()) <= set(anlass)
    vorher = ziel.read_bytes()
    capsys.readouterr()
    assert eob.main(["--plan", str(plan), "--ausgabe", str(ziel), "--schreiben"], heute=HEUTE) == 0
    assert "unverändert" in capsys.readouterr().out and ziel.read_bytes() == vorher


def eob_knoten_schluessel():
    """Die Schlüssel, die die Erzähl-Diashow und ereignisse.jsonl tragen."""
    return ("anlass_id", "anzahl_dateien", "art", "datei_kennungen", "datum", "event", "event_quelle",
            "event_stufe", "jahr", "kategorie", "kennung", "quellen", "stand", "thema", "ziel_ordner")


def test_schutz_repo_ziel_fehlender_plan_und_senden(tmp_path, capsys):
    plan = _bestand(tmp_path)
    assert eob.main(["--plan", str(plan), "--ausgabe", str(PROJEKT / "ordner_ereignisse.jsonl"),
                     "--schreiben"], heute=HEUTE) == 2
    assert not (PROJEKT / "ordner_ereignisse.jsonl").exists()
    assert eob.main(["--plan", str(tmp_path / "fehlt.json")], heute=HEUTE) == 3
    ziel = tmp_path / "ordner_ereignisse.jsonl"
    befehle = []

    def adb_ok(befehl):
        befehle.append(befehl)
        return 0, str(os.path.getsize(ziel)) if befehl[1] == "shell" else ""

    assert eob.main(["--plan", str(plan), "--ausgabe", str(ziel), "--senden"], heute=HEUTE, ausfuehren=adb_ok) == 0
    assert befehle[0][:2] == ["adb", "push"] and befehle[0][-1] == "/sdcard/Download/ordner_ereignisse.jsonl"
    assert eob.main(["--plan", str(plan), "--ausgabe", str(ziel), "--senden"], heute=HEUTE,
                    ausfuehren=lambda b: (1, "")) == 1


# ── 4. Erzähl-Diashow liest die Datei mit, chronologisch ─────────────────────

def test_diashow_fuehrt_ordner_anlaesse_chronologisch_zusammen(tmp_path, monkeypatch):
    ereignisse = tmp_path / "ereignisse.jsonl"
    _jsonl(ereignisse, [
        {"kennung": "E-1", "event": "Upload früh", "datum": "2015-03-01", "jahr": 2015, "datei_kennungen": [1]},
        {"kennung": "E-2", "event": "Upload spät", "datum": "2019-03-01", "jahr": 2019, "datei_kennungen": [2]},
    ])
    _jsonl(tmp_path / "fotobuch_ereignisse.jsonl", [{"kennung": "fotobuch-1", "titel": "Buch", "datei_kennungen": [9]}])
    _jsonl(tmp_path / "ordner_ereignisse.jsonl", [
        {"kennung": "O-30", "event": "Testinsel · Juli 2014", "datum": "2014-07-30", "jahr": 2014, "datei_kennungen": [30, 31]},
        {"kennung": "O-40", "event": "Familie · 2015", "datum": None, "jahr": 2015, "datei_kennungen": [40]},
        {"kennung": "O-50", "event": "Konzert · Juni 2016", "datum": "2016-06-03", "jahr": 2016, "datei_kennungen": [50]},
        "kaputt",
    ])
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    liste = erzaehl_service.ereignisse_liste()
    assert [e["kennung"] for e in liste["eintraege"]] == ["fotobuch-1", "O-30", "E-1", "O-40", "O-50", "E-2"]
    assert liste["defekte_zeilen"] == 1
    assert erzaehl_service.ereignis_detail("O-30")["datei_kennungen"] == [30, 31]
    assert [e["kennung"] for e in erzaehl_service.ereignisse_liste(jahr=2015)["eintraege"]] == ["E-1", "O-40"]


def test_ohne_ordner_datei_bleibt_die_reihenfolge_unveraendert(tmp_path, monkeypatch):
    ereignisse = tmp_path / "ereignisse.jsonl"
    _jsonl(ereignisse, [
        {"kennung": "E-2", "event": "b", "datum": "2019-03-01", "datei_kennungen": [2]},
        {"kennung": "E-1", "event": "a", "datum": "2015-03-01", "datei_kennungen": [1]},
    ])
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    assert [e["kennung"] for e in erzaehl_service.ereignisse_liste()["eintraege"]] == ["E-2", "E-1"]
    assert erzaehl_service.ereignisse_existiert()


def test_nur_ordner_datei_reicht_als_quelle(tmp_path, monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))   # fehlt
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    assert not erzaehl_service.ereignisse_existiert()
    _jsonl(tmp_path / "ordner_ereignisse.jsonl", [{"kennung": "O-1", "event": "x", "datei_kennungen": [1]}])
    assert erzaehl_service.ereignisse_existiert()
