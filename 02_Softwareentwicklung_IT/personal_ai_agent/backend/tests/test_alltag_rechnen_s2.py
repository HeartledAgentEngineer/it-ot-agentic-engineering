"""Alltagsprotokoll S2, Rest (03.11.2026): Stunden, Schlaf-Knöpfe, offene Stunden, Lücken.

Plan ``.hermes/plans/alltagsprotokoll.md`` S2: „2 bis 5 geschlafen, um 3 kurz wach" ergibt die
richtigen Stunden und die richtige Dauer; über Mitternacht und Zeitumstellung getestet.
Alle Daten erfunden.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone, tzinfo

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import alltag_rechnen as ar  # noqa: E402

MEZ = timezone(timedelta(hours=1))
MESZ = timezone(timedelta(hours=2))


class Berlin2026(tzinfo):
    """Nur die Rückstellung am 25.10.2026 (01:00 UTC): vorher +2, danach +1."""
    _WECHSEL = datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)

    def utcoffset(self, dt):
        return timedelta(hours=1)  # wird über fromutc nie für die Rechnung gebraucht

    def dst(self, dt):
        return timedelta(0)

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=timezone.utc)
        ziel = MESZ if utc < self._WECHSEL else MEZ
        return utc.astimezone(ziel)


# ── Stunden verteilen ──────────────────────────────────────────────────────

def test_stundenbereich_ergibt_angebrochene_stunden():
    assert ar.stunden_verteilen("2026-11-02T14:30:00+01:00", "2026-11-02T16:10:00+01:00", MEZ) == [
        "2026-11-02T14:00+01:00", "2026-11-02T15:00+01:00", "2026-11-02T16:00+01:00"]


def test_volle_stunden_ohne_ueberhang():
    assert ar.stunden_verteilen("2026-11-02T14:00:00+01:00", "2026-11-02T16:00:00+01:00", MEZ) == [
        "2026-11-02T14:00+01:00", "2026-11-02T15:00+01:00"]


def test_ueber_mitternacht():
    assert ar.stunden_verteilen("2026-11-02T23:00:00+01:00", "2026-11-03T01:00:00+01:00", MEZ) == [
        "2026-11-02T23:00+01:00", "2026-11-03T00:00+01:00"]


def test_zeitumstellung_zaehlt_die_doppelte_stunde_zweimal():
    stunden = ar.stunden_verteilen("2026-10-25T01:00:00+02:00", "2026-10-25T04:00:00+01:00", Berlin2026())
    assert stunden == ["2026-10-25T01:00+02:00", "2026-10-25T02:00+02:00",
                       "2026-10-25T02:00+01:00", "2026-10-25T03:00+01:00"]


def test_unbrauchbarer_bereich_ist_leer():
    assert ar.stunden_verteilen("2026-11-02T16:00:00+01:00", "2026-11-02T14:00:00+01:00", MEZ) == []
    assert ar.stunden_verteilen("quatsch", "2026-11-02T14:00:00+01:00", MEZ) == []


# ── Schlaf aus Knopf-Ereignissen ───────────────────────────────────────────

def _e(zeit, ereignis):
    return {"art": "schlaf", "zeit": zeit, "ereignis": ereignis}


def test_zwei_bis_fuenf_geschlafen_um_drei_kurz_wach():
    naechte = ar.schlaf_aus_ereignissen([
        _e("2026-11-03T02:00:00+01:00", "schlafen"),
        _e("2026-11-03T03:00:00+01:00", "wach_liegen"),
        _e("2026-11-03T03:10:00+01:00", "wieder_schlafen"),
        _e("2026-11-03T05:00:00+01:00", "aufwachen"),
    ])
    assert len(naechte) == 1
    n = naechte[0]
    assert (n["dauer_min"], n["wach_min"], n["schlaf_min"], n["wach_phasen"]) == (180, 10, 170, 1)
    assert n["nacht_zum"] == "2026-11-03" and n["offen"] is False


def test_reihenfolge_egal_und_ueber_mitternacht():
    naechte = ar.schlaf_aus_ereignissen([
        _e("2026-11-03T06:30:00+01:00", "aufwachen"),
        _e("2026-11-02T23:15:00+01:00", "schlafen"),
    ])
    assert [(n["dauer_min"], n["nacht_zum"]) for n in naechte] == [(435, "2026-11-03")]


def test_noch_schlafend_ist_offen():
    n = ar.schlaf_aus_ereignissen([_e("2026-11-03T23:00:00+01:00", "schlafen")])[0]
    assert n["offen"] is True and n["ende"] is None and n["dauer_min"] == 0


def test_wach_liegen_bis_zum_aufstehen_zaehlt_als_wach():
    n = ar.schlaf_aus_ereignissen([
        _e("2026-11-03T01:00:00+01:00", "schlafen"),
        _e("2026-11-03T05:00:00+01:00", "wach_liegen"),
        _e("2026-11-03T06:00:00+01:00", "aufwachen"),
    ])[0]
    assert (n["dauer_min"], n["wach_min"], n["wach_phasen"]) == (300, 60, 1)


def test_doppeldruck_und_verirrte_knoepfe_werden_ignoriert():
    n = ar.schlaf_aus_ereignissen([
        _e("2026-11-03T00:50:00+01:00", "aufwachen"),          # ohne Schlaf: ignoriert
        _e("2026-11-03T01:00:00+01:00", "schlafen"),
        _e("2026-11-03T01:02:00+01:00", "schlafen"),           # Doppeldruck
        _e("2026-11-03T02:00:00+01:00", "wieder_schlafen"),    # nicht wach gewesen
        _e("2026-11-03T07:00:00+01:00", "aufwachen"),
    ])
    assert len(n) == 1 and (n[0]["dauer_min"], n[0]["wach_phasen"]) == (360, 0)


def test_vergessenes_aufwachen_schliesst_nach_24_stunden():
    naechte = ar.schlaf_aus_ereignissen([
        _e("2026-11-01T23:00:00+01:00", "schlafen"),
        _e("2026-11-02T23:30:00+01:00", "schlafen"),           # neue Nacht, alte bleibt offen
        _e("2026-11-03T07:00:00+01:00", "aufwachen"),
    ])
    assert [n["offen"] for n in naechte] == [True, False]
    assert naechte[1]["dauer_min"] == 450


# ── Stand und offene Stunden ───────────────────────────────────────────────

def test_stand_aus_stunden_und_schlaf():
    stand = ar.letzter_stand([
        {"art": "stunde", "von": "2026-11-03T08:00:00+01:00", "bis": "2026-11-03T09:00:00+01:00"},
        _e("2026-11-03T22:30:00+01:00", "schlafen"),
    ], jetzt=datetime(2026, 11, 3, 23, 0, tzinfo=MEZ))
    assert stand == {"letzter_eintrag": "2026-11-03T22:30:00+01:00", "schlaeft": True}


def test_stand_spaeterer_eintrag_beendet_schlaf_und_alter_schlaf_verfaellt():
    eintraege = [_e("2026-11-03T13:00:00+01:00", "schlafen"),
                 {"art": "stunde", "von": "2026-11-03T14:00:00+01:00", "bis": "2026-11-03T15:00:00+01:00"}]
    assert ar.letzter_stand(eintraege, jetzt=datetime(2026, 11, 3, 16, 0, tzinfo=MEZ))["schlaeft"] is False
    alt = [_e("2026-11-01T23:00:00+01:00", "schlafen")]
    assert ar.letzter_stand(alt, jetzt=datetime(2026, 11, 3, 9, 0, tzinfo=MEZ))["schlaeft"] is False
    assert ar.letzter_stand([], jetzt=datetime(2026, 11, 3, 9, 0, tzinfo=MEZ)) == {
        "letzter_eintrag": None, "schlaeft": False}


def test_offene_stunden():
    jetzt = datetime(2026, 11, 3, 15, 40, tzinfo=MEZ)
    assert ar.offene_stunden("2026-11-03T12:00:00+01:00", jetzt, schlaeft=False) == 3
    assert ar.offene_stunden("2026-11-03T15:10:00+01:00", jetzt, schlaeft=False) == 0
    assert ar.offene_stunden("2026-11-03T12:00:00+01:00", jetzt, schlaeft=True) == 0
    assert ar.offene_stunden(None, jetzt, schlaeft=False) == 1          # erster Eintrag fehlt
    assert ar.offene_stunden("2026-11-03T18:00:00+01:00", jetzt, schlaeft=False) == 0  # Zukunft


# ── Fehlende Felder ────────────────────────────────────────────────────────

def test_fehlende_felder():
    voll = {"art": "stunde", "stimmung": 4, "anspannung": 30, "gefuehle": ["Freude"], "aktivitaet": "Wäsche"}
    assert ar.fehlende_felder(voll) == []
    assert ar.fehlende_felder({"art": "stunde", "aktivitaet": "Lesen"}) == ["stimmung", "anspannung", "gefuehle"]
    kaputt = {"art": "stunde", "stimmung": 9, "anspannung": -5, "gefuehle": [], "aktivitaet": "  "}
    assert ar.fehlende_felder(kaputt) == ["stimmung", "anspannung", "gefuehle", "aktivitaet"]
    assert ar.fehlende_felder({"art": "stunde", "stimmung": True, "anspannung": 0,
                               "gefuehle": ["Ruhe"], "aktivitaet": "Schlaf"}) == ["stimmung"]
    assert ar.fehlende_felder(_e("2026-11-03T22:00:00+01:00", "schlafen")) == []
