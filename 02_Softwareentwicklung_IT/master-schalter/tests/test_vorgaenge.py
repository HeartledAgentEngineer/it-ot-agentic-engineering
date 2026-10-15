"""Tests für den Vorgangsspeicher (`vorgaenge.json`)."""
from dataclasses import replace

import pytest

from master_schalter import vorgaenge


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


def _vorgang(ident="engineering@4102444800", phase="sende", lauf_id="lauf-1"):
    return vorgaenge.Vorgang(ident, "engineering", lauf_id, phase, "2026-10-15T12:00:00+00:00")


def test_ohne_datei_leer(daten):
    assert vorgaenge.lesen() == []


def test_roundtrip_ueber_aendern(daten):
    neu = vorgaenge.aendern(lambda alt: [*alt, _vorgang()])
    assert neu == [_vorgang()]
    assert vorgaenge.lesen() == [_vorgang()]


def test_fehler_in_der_funktion_schreibt_nichts(daten):
    vorgaenge.aendern(lambda alt: [*alt, _vorgang()])

    def kaputt(alt):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        vorgaenge.aendern(kaputt)
    assert vorgaenge.lesen() == [_vorgang()]


def test_unbekannte_phase_wird_verworfen(daten):
    daten.mkdir(parents=True)
    (daten / "vorgaenge.json").write_text(
        '[{"id": "x@1", "thema": "engineering", "lauf_id": "l", "phase": "erfunden", "zeit": "z"}]',
        encoding="utf-8")
    assert vorgaenge.lesen() == []


def test_finden_und_offene(daten):
    vorgaenge.aendern(lambda alt: [*alt, _vorgang("a@1", "sende"), _vorgang("b@2", "bestaetigt"),
                                   _vorgang("c@3", "entwertet")])
    assert vorgaenge.finden("b@2").phase == "bestaetigt"
    assert vorgaenge.finden("gibtsnicht") is None
    assert [v.id for v in vorgaenge.offene()] == ["a@1"]


def test_phase_setzen_erhaelt_andere_vorgaenge(daten):
    vorgaenge.aendern(lambda alt: [*alt, _vorgang("a@1", "sende"), _vorgang("b@2", "gesendet")])
    vorgaenge.aendern(lambda alt: [replace(v, phase="unklar") if v.id == "a@1" else v for v in alt])
    assert [v.phase for v in vorgaenge.lesen()] == ["unklar", "gesendet"]
