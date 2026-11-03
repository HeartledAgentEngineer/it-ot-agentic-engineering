"""Alltagsprotokoll S2: Schlaf auswerten (rein, ohne Modell, 03.11.2026). Daten erfunden."""
from __future__ import annotations

from app.services import alltag_rechnen as rr


def _p(stufe, beginn, ende):
    return {"stufe": stufe, "beginn": beginn, "ende": ende}


NACHT = {
    "quelle_kennung": "hc-1",
    "beginn": "2026-11-02T23:10:00+01:00",
    "ende": "2026-11-03T06:40:00+01:00",
    "phasen": [
        _p("leicht", "2026-11-02T23:10:00+01:00", "2026-11-03T01:00:00+01:00"),
        _p("tief", "2026-11-03T01:00:00+01:00", "2026-11-03T02:30:00+01:00"),
        _p("wach", "2026-11-03T02:30:00+01:00", "2026-11-03T02:45:00+01:00"),
        _p("rem", "2026-11-03T02:45:00+01:00", "2026-11-03T04:00:00+01:00"),
        _p("leicht", "2026-11-03T04:00:00+01:00", "2026-11-03T06:30:00+01:00"),
        _p("wach", "2026-11-03T06:30:00+01:00", "2026-11-03T06:40:00+01:00"),
    ],
}


def test_nacht_auswerten_zaehlt_phasen():
    a = rr.nacht_auswerten(NACHT)
    assert a["nacht_zum"] == "2026-11-03"
    assert a["dauer_min"] == 450
    assert a["wach_min"] == 25 and a["tief_min"] == 90 and a["rem_min"] == 75 and a["leicht_min"] == 260
    assert a["schlaf_min"] == 425
    assert a["wach_phasen"] == 1          # das Aufwachen am Ende zählt nicht als Wachphase
    assert a["einschlafen"] == "23:10" and a["aufwachen"] == "06:40"
    assert a["nickerchen"] is False


def test_ohne_phasen_ist_alles_schlaf():
    a = rr.nacht_auswerten({**NACHT, "phasen": []})
    assert a["schlaf_min"] == 450 and a["wach_min"] == 0 and a["phasen_bekannt"] is False


def test_ortszeit_der_uhr_bleibt():
    a = rr.nacht_auswerten({**NACHT, "beginn": "2026-07-01T22:00:00+02:00",
                            "ende": "2026-07-02T05:30:00+02:00", "phasen": []})
    assert a["einschlafen"] == "22:00" and a["nacht_zum"] == "2026-07-02"


def test_nickerchen_am_nachmittag():
    a = rr.nacht_auswerten({**NACHT, "beginn": "2026-11-03T14:00:00+01:00",
                            "ende": "2026-11-03T14:40:00+01:00", "phasen": []})
    assert a["nickerchen"] is True


def test_zusammenfassung_ueber_mehrere_naechte():
    zweite = {**NACHT, "quelle_kennung": "hc-2", "beginn": "2026-11-03T23:00:00+01:00",
              "ende": "2026-11-04T06:00:00+01:00", "phasen": []}
    nickerchen = {**NACHT, "quelle_kennung": "hc-3", "beginn": "2026-11-04T15:00:00+01:00",
                  "ende": "2026-11-04T15:30:00+01:00", "phasen": []}
    z = rr.zusammenfassung([NACHT, zweite, nickerchen])
    assert z["naechte"] == 2 and z["nickerchen"] == 1
    assert z["schnitt_schlaf_min"] == round((425 + 420) / 2)
    assert z["kuerzeste"]["nacht_zum"] == "2026-11-04"


def test_zusammenfassung_leer():
    assert rr.zusammenfassung([])["naechte"] == 0


def test_dauer_text():
    assert rr.dauer_text(425) == "7 Std. 5 Min." and rr.dauer_text(60) == "1 Std." and rr.dauer_text(5) == "5 Min."


def test_schlaf_text_fuer_den_chat():
    text = rr.schlaf_text([NACHT])
    assert "Nacht zum 03.11.2026" in text and "7 Std. 5 Min." in text and "Tiefschlaf" in text
    assert "1× wach" in text


def test_schlaf_text_ohne_daten_ist_ehrlich():
    assert "Keine Schlafdaten" in rr.schlaf_text([])
