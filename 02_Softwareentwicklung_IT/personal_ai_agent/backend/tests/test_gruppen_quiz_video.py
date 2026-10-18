"""Tests: Video-Gesichter im Quiz (Plan video-gesichter-im-quiz, V2, 14.10.2026).

Offline, erfundene Dateien in ``tmp_path``. Die Standbild-Karte
(``video_standbilder.jsonl``, geschrieben von tools/foto_sortierung/video_standbilder.py)
macht Video-Gesichter sichtbar: Standbild-``fileid``, ``bbox × skala``.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402


def _foto(fid, kennung, anteil=0.01, aufnahme="2020-01-01T10:00:00"):
    return {"bild_id": str(fid), "index": 0, "kennung": kennung, "bbox": [10, 20, 30, 40],
            "breite": 1000, "hoehe": 750, "anteil": anteil, "score": 0.9, "aufnahme": aufnahme}


def _vzeile(vid, zeit, kennung, index=0, anteil=0.02, aufnahme=None):
    z = {"bild_id": f"{vid}#t={zeit:.1f}", "video_id": str(vid), "zeit_s": zeit, "index": index,
         "kennung": kennung, "bbox": [100, 200, 300, 400], "breite": 1920, "hoehe": 1080,
         "anteil": anteil, "score": 0.9}
    if aufnahme:
        z["aufnahme"] = aufnahme
    return z


def _karte_zeile(vid, zeit, fileid, skala=0.5):
    return {"bild_id": f"{vid}#t={zeit:.1f}", "video_id": str(vid), "zeit_s": zeit,
            "standbild_fileid": fileid, "breite": round(1920 * skala), "hoehe": round(1080 * skala),
            "skala": skala, "stand": "2026-10-14T18:00:00+00:00"}


GRUPPEN = [
    {"kennung": "Person_2001", "groesse": 50, "bilder": 0, "videos": 2, "zwilling_kandidaten": [
        {"kennung": "Person_2002", "aehnlich": 0.5, "gemeinsame_bilder": 0}], "beispiele": []},
    {"kennung": "Person_2002", "groesse": 10, "bilder": 2, "videos": 1, "zwilling_kandidaten": [],
     "beispiele": [{"bild_id": "700", "index": 0, "bbox": [1, 2, 3, 4], "breite": 10, "hoehe": 10}]},
    {"kennung": "Person_2003", "groesse": 5, "bilder": 0, "videos": 1, "zwilling_kandidaten": [],
     "beispiele": []},
]


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({"stand": "x", "gruppen": GRUPPEN}), encoding="utf-8")
    zeilen = [_vzeile(11, 2.0, "Person_2001", anteil=0.05),
              _vzeile(11, 4.0, "Person_2001", anteil=0.03, aufnahme="2019-05-01T10:00:00"),
              _vzeile(12, 6.0, "Person_2001", anteil=0.01),
              _foto(700, "Person_2002"), _foto(701, "Person_2002", anteil=0.02),
              _vzeile(13, 2.0, "Person_2002", anteil=0.5),
              _vzeile(14, 2.0, "Person_2003")]
    (ordner / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    yield tmp_path
    gq._CACHE.clear()


def _karte(basis, zeilen, roh=None):
    pfad = basis / gq.UNTERORDNER / gq.VIDEO_STANDBILDER_DATEINAME
    pfad.write_text(roh if roh is not None else
                    "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    return pfad


def _volle_karte(basis):
    return _karte(basis, [_karte_zeile(11, 2.0, 9001), _karte_zeile(11, 4.0, 9002),
                          _karte_zeile(12, 6.0, 9003), _karte_zeile(13, 2.0, 9004),
                          _karte_zeile(14, 2.0, 9005)])


def test_ohne_karte_bleibt_alles_wie_bisher(basis):
    r = gq.gesichter("Person_2001")
    assert r["ok"] and r["gesamt"] == 0 and r["videos"] == 3
    assert gq.gesichter("Person_2002")["gesamt"] == 2
    assert gq.naechste()["gruppe"]["beispiele"] == []


def test_mit_karte_erscheinen_video_gesichter_umgerechnet(basis):
    _volle_karte(basis)
    r = gq.gesichter("Person_2001")
    assert r["gesamt"] == 3 and r["videos"] == 0
    erstes = r["gesichter"][0]
    assert erstes["gid"] == "9001:0" and erstes["fileid"] == "9001"
    assert erstes["bbox"] == [50, 100, 150, 200] and (erstes["breite"], erstes["hoehe"]) == (960, 540)
    assert erstes["video"] is True and erstes["zeit_s"] == 2.0
    assert all("_guete" not in g for g in r["gesichter"])


def test_teilkarte_zaehlt_den_rest(basis):
    _karte(basis, [_karte_zeile(11, 2.0, 9001)])
    r = gq.gesichter("Person_2001")
    assert r["gesamt"] == 1 and r["videos"] == 2


def test_karte_nachtraeglich_wird_beim_naechsten_aufruf_gesehen(basis):
    assert gq.gesichter("Person_2001")["gesamt"] == 0
    _volle_karte(basis)
    assert gq.gesichter("Person_2001")["gesamt"] == 3


def test_kaputte_karte_wirft_nicht(basis, caplog):
    _karte(basis, None, roh="kaputt\n{\"bild_id\": \"11#t=2.0\"}\n[]\n"
           + json.dumps(_karte_zeile(11, 4.0, "keinezahl")) + "\n")
    r = gq.gesichter("Person_2001")
    assert r["ok"] and r["gesamt"] == 0 and r["videos"] == 3


def test_karte_als_ordner_wirft_nicht_und_warnt(basis, caplog):
    (basis / gq.UNTERORDNER / gq.VIDEO_STANDBILDER_DATEINAME).mkdir()
    (basis / gq.VIDEO_STANDBILDER_DATEINAME).mkdir()
    r = gq.gesichter("Person_2001")
    assert r["ok"] and r["gesamt"] == 0


def test_karte_am_handy_im_basisordner(basis):
    pfad = _volle_karte(basis)
    os.replace(pfad, basis / gq.VIDEO_STANDBILDER_DATEINAME)
    assert gq.gesichter("Person_2001")["gesamt"] == 3


def test_ordnung_zeit_video_ohne_datum_hinten(basis):
    _volle_karte(basis)
    r = gq.gesichter("Person_2002", ordnung="zeit")
    assert [g["gid"] for g in r["gesichter"]] == ["700:0", "701:0", "9004:0"]
    r = gq.gesichter("Person_2001", ordnung="zeit")
    assert r["gesichter"][0]["gid"] == "9002:0" and r["gesichter"][0]["aufnahme"] == "2019-05-01"


def test_reine_videogruppe_hat_beispiele_beste_zuerst(basis):
    _volle_karte(basis)
    g = gq.naechste()["gruppe"]
    assert g["kennung"] == "Person_2001"
    assert [b["fileid"] for b in g["beispiele"]] == ["9001", "9002", "9003"]
    assert g["beispiele"][0]["video"] is True and g["beispiele"][0]["bbox"] == [50, 100, 150, 200]


def test_mischgruppe_wird_aufgefuellt_fotogruppe_bleibt(basis):
    _volle_karte(basis)
    gq.antworten("Person_2001", "spaeter")
    g = gq.naechste()["gruppe"]
    assert g["kennung"] == "Person_2002"
    assert [b["fileid"] for b in g["beispiele"]] == ["700", "9004"]


def test_fotogruppe_ohne_videos_unveraendert(basis):
    _volle_karte(basis)
    gq.antworten("Person_2001", "unbekannt")
    gq.antworten("Person_2002", "unbekannt")
    g = gq.naechste()["gruppe"]
    assert g["kennung"] == "Person_2003" and [b["fileid"] for b in g["beispiele"]] == ["9005"]


def test_zwilling_nur_aus_videos_hat_vergleichsbild(basis):
    _volle_karte(basis)
    gq._CACHE.clear()
    daten = json.loads((basis / gq.UNTERORDNER / gq.BEISPIELE_DATEINAME).read_text(encoding="utf-8"))
    daten["gruppen"][1]["zwilling_kandidaten"] = [{"kennung": "Person_2001", "aehnlich": 0.5}]
    daten["gruppen"][1]["groesse"] = 999
    (basis / gq.UNTERORDNER / gq.BEISPIELE_DATEINAME).write_text(json.dumps(daten), encoding="utf-8")
    g = gq.naechste()["gruppe"]
    assert g["kennung"] == "Person_2002"
    assert g["zwillinge"][0]["beispiel"]["fileid"] == "9001"


def test_ausgeschlossene_video_beispiele_fehlen_nicht_versehentlich(basis):
    _volle_karte(basis)
    g = gq.naechste()["gruppe"]
    assert len({b["fileid"] for b in g["beispiele"]}) == len(g["beispiele"])


@pytest.mark.parametrize("aufruf", [
    lambda: gq.ausschliessen("Person_2002", ["9001:0"]),          # fremder Vorschlag
    lambda: gq.ausschliessen("Person_2002", ["9999:0"]),          # kein Gesicht dieser Gruppe
])
def test_video_gesicht_fremder_vorschlag_wird_abgelehnt(basis, aufruf):
    """Die Prüfung „gehört das Gesicht zu diesem Vorschlag?" gilt auch für Standbilder."""
    _volle_karte(basis)
    vorher = _vorgaben_text(basis)
    r = aufruf()
    assert r["ok"] is False and "gehört nicht" in r["fehler"]
    assert _vorgaben_text(basis) == vorher


def _vorgaben_text(basis):
    pfad = basis / gq.VORGABEN_DATEINAME
    return pfad.read_text(encoding="utf-8") if pfad.exists() else None


def test_video_gesicht_ausschliessen_wirkt_sofort_und_als_regel(basis):
    """S2 (18.10.2026): ein Standbild lässt sich einzeln markieren wie ein Foto."""
    _volle_karte(basis)
    r = gq.ausschliessen("Person_2001", ["9001:0"])
    assert r["ok"] and r["ausgeschlossen"] == 1 and r["gesamt"] == 2
    gids = {g["gid"] for g in gq.gesichter("Person_2001")["gesichter"]}
    assert "9001:0" not in gids and gids == {"9002:0", "9003:0"}
    # In der Datei steht das Standbild als ``bild_id`` — dieselbe Form wie bei Fotos.
    assert gq.ausgeschlossen_lesen()["Person_2001"] == {"9001:0"}
    eintrag = json.loads(_vorgaben_text(basis) or "{}")["ausgeschlossen"][0]
    assert eintrag == {"kennung": "Person_2001", "bild_id": "9001", "index": 0}
    # Ein zweites Mal ist nichts neu (idempotent).
    assert gq.ausschliessen("Person_2001", ["9001:0"])["ausgeschlossen"] == 0


def test_video_gesicht_ausschluss_rueckgaengig_und_beispiel_wieder_da(basis):
    _volle_karte(basis)
    assert "9001" in [b["fileid"] for b in gq.naechste()["gruppe"]["beispiele"]]
    gq.ausschliessen("Person_2001", ["9001:0"])
    assert "9001" not in [b["fileid"] for b in gq.naechste()["gruppe"]["beispiele"]]
    r = gq.rueckgaengig()
    assert r["ok"] and r["zurueckgenommen"] == {"kennung": "Person_2001",
                                                "art": "ausschliessen", "gesichter": 1}
    assert gq.gesichter("Person_2001")["gesamt"] == 3
    assert gq.ausgeschlossen_lesen() == {}


def test_video_gesicht_ueber_die_person_ausschliessen(basis):
    _volle_karte(basis)
    gq.antworten("Person_2002", "name", "Leon")
    gq.antworten("Person_2001", "name", "Leon")
    r = gq.ausschliessen_person("Leon", [{"kennung": "Person_2001", "gid": "9001:0"}])
    assert r["ok"] and r["ausgeschlossen"] == 1
    assert {g["gid"] for g in gq.gesichter_person("Leon")["gesichter"]}.isdisjoint({"9001:0"})


def test_video_gesicht_zuordnen_und_in_der_personenansicht(basis):
    _volle_karte(basis)
    gq.antworten("Person_2002", "name", "Leon")          # Zielperson
    r = gq.zuordnen("Leon", [{"kennung": "Person_2001", "gid": "9001:0"}])
    assert r["ok"] and r["zugeordnet"] == 1
    assert "9001:0" not in {g["gid"] for g in gq.gesichter("Person_2001")["gesichter"]}
    person = gq.gesichter_person("Leon")
    dazu = [g for g in person["gesichter"] if g["gid"] == "9001:0"]
    assert len(dazu) == 1 and dazu[0]["video"] is True and dazu[0]["zugeordnet"] is True
    z = gq.rueckgaengig()
    assert z["ok"] and z["zurueckgenommen"]["art"] == "zuordnen"
    assert "9001:0" in {g["gid"] for g in gq.gesichter("Person_2001")["gesichter"]}


def test_video_ausschluss_laesst_fotos_unberuehrt(basis):
    """Eine Video-Regel darf kein Foto treffen (Standbild-Kennung ≠ Foto-Kennung)."""
    _volle_karte(basis)
    gq.ausschliessen("Person_2002", ["9004:0"])
    r = gq.gesichter("Person_2002")
    assert r["gesamt"] == 2 and {g["gid"] for g in r["gesichter"]} == {"700:0", "701:0"}



def test_person_ansicht_zeigt_video_gesichter(basis):
    _volle_karte(basis)
    gq.antworten("Person_2001", "name", "Leon")
    r = gq.gesichter_person("Leon")
    assert r["gesamt"] == 3 and all(g["video"] for g in r["gesichter"])


def test_foto_aktionen_laufen_weiter(basis):
    _volle_karte(basis)
    r = gq.ausschliessen("Person_2002", ["701:0"])
    assert r["ok"] and r["ausgeschlossen"] == 1 and r["gesamt"] == 2


# ── Ergebnispruefung R1 (14.10.2026): Codex-Befund 4, Hermes-Hinweise A und B ──

@pytest.mark.parametrize("mass", [{"breite": None}, {"hoehe": 0}, {"breite": -5},
                                  {"hoehe": "540"}, {"breite": True}])
def test_karte_ohne_gueltiges_mass_zaehlt_als_ohne_standbild(basis, mass):
    zeile = _karte_zeile(11, 2.0, 9001)
    zeile.update(mass)
    _karte(basis, [zeile, _karte_zeile(11, 4.0, 9002)])
    r = gq.gesichter("Person_2001")
    assert r["gesamt"] == 1 and r["gesichter"][0]["fileid"] == "9002"
    assert r["videos"] == 2


def test_gruppenkopf_zaehlt_videos_wie_das_raster(basis):
    g = gq.naechste()["gruppe"]
    assert g["kennung"] == "Person_2001" and g["videos"] == 3   # ohne Karte: alle ohne Standbild
    gq._CACHE.clear()
    _karte(basis, [_karte_zeile(11, 2.0, 9001)])
    g = gq.naechste()["gruppe"]
    assert g["videos"] == gq.gesichter("Person_2001")["videos"] == 2
    _volle_karte(basis)
    assert gq.naechste()["gruppe"]["videos"] == 0


def test_gruppenkopf_ohne_gesichtsdatei_behaelt_alten_wert(basis):
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).unlink()
    gq._CACHE.clear()
    assert gq.naechste()["gruppe"]["videos"] == 2


def test_unlesbarer_score_verwirft_die_zeit_nicht(basis):
    zeilen = [_vzeile(11, 2.0, "Person_2001"), _vzeile(11, 4.0, "Person_2001", anteil=0.5)]
    zeilen[0]["score"] = "kaputt"
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    gq._CACHE.clear()
    _karte(basis, [_karte_zeile(11, 2.0, 9001), _karte_zeile(11, 4.0, 9002)])
    r = gq.gesichter("Person_2001")
    assert r["gesamt"] == 2 and r["videos"] == 0
    assert [g["fileid"] for g in r["gesichter"]] == ["9002", "9001"]   # Score 0 ans Ende
