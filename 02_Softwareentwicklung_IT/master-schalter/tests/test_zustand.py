"""Tests für den Master-Zustand (`master.json`) und seine Betriebssystem-Sperre."""
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from master_schalter import zustand

SRC = str(Path(__file__).resolve().parents[1] / "src")


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


def _umgebung(daten: Path) -> dict:
    env = dict(os.environ)
    env["MASTER_SCHALTER_DATEN"] = str(daten)
    env["PYTHONPATH"] = SRC
    return env


def test_lesen_ohne_datei_ist_nicht_gesetzt(daten):
    z = zustand.lesen()
    assert z.master is None and z.seit is None and z.uebergabe is None


@pytest.mark.parametrize("inhalt", ["{kaputt", "[]", '"text"', '{"master": "gemini"}', '{"master": 5}', ""])
def test_lesen_kaputt_stuerzt_nie_ab(daten, inhalt):
    daten.mkdir(parents=True)
    (daten / "master.json").write_text(inhalt, encoding="utf-8")
    assert zustand.lesen().master is None


def test_roundtrip_ueber_aendern(daten):
    neu = zustand.aendern(lambda z: replace(z, master="codex", seit="2026-10-14T21:50:00+02:00",
                                            uebergabe="C:/x/paket.md"))
    assert neu.master == "codex"
    gelesen = zustand.lesen()
    assert (gelesen.master, gelesen.seit, gelesen.uebergabe) == ("codex", "2026-10-14T21:50:00+02:00", "C:/x/paket.md")
    roh = json.loads((daten / "master.json").read_text(encoding="utf-8"))
    assert set(roh) == {"master", "seit", "uebergabe"}


def test_fehler_in_der_funktion_schreibt_nichts(daten):
    zustand.aendern(lambda z: replace(z, master="claude"))

    def kaputt(z):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        zustand.aendern(kaputt)
    assert zustand.lesen().master == "claude"


def test_ungueltiger_master_wird_abgelehnt(daten):
    with pytest.raises(ValueError):
        zustand.aendern(lambda z: replace(z, master="gemini"))
    assert not (daten / "master.json").exists()


def test_schreiben_ist_atomar_keine_tmp_reste(daten):
    zustand.aendern(lambda z: replace(z, master="claude"))
    namen = sorted(p.name for p in daten.iterdir())
    assert namen == ["master.json", "master.json.lock"]


def test_sperrdatei_bleibt_dauerhaft(daten):
    zustand.aendern(lambda z: replace(z, master="claude"))
    zustand.aendern(lambda z: replace(z, master="codex"))
    assert (daten / "master.json.lock").exists()


def test_belegte_sperre_fuehrt_nach_frist_zum_fehler(daten):
    with zustand.sperre(frist=1.0):
        start = time.monotonic()
        with pytest.raises(zustand.SperrFehler):
            zustand.aendern(lambda z: replace(z, master="codex"), frist=0.3)
        assert 0.25 <= time.monotonic() - start < 3
    assert zustand.lesen().master is None


def test_aendern_ruft_funktion_bei_belegter_sperre_nicht_auf(daten):
    aufrufe = []
    with zustand.sperre(frist=1.0):
        with pytest.raises(zustand.SperrFehler):
            zustand.aendern(lambda z: aufrufe.append(1) or z, frist=0.2)
    assert aufrufe == []


def test_sperre_wieder_frei_nach_ende_des_halters(daten):
    code = (
        "import sys, time\n"
        "from master_schalter import zustand\n"
        "with zustand.sperre(frist=2.0):\n"
        "    print('bereit', flush=True)\n"
        "    time.sleep(60)\n"
    )
    halter = subprocess.Popen([sys.executable, "-c", code], env=_umgebung(daten),
                              stdout=subprocess.PIPE, text=True)
    try:
        assert halter.stdout.readline().strip() == "bereit"
        with pytest.raises(zustand.SperrFehler):
            zustand.aendern(lambda z: replace(z, master="codex"), frist=0.3)
    finally:
        halter.kill()
        halter.wait(timeout=10)
    neu = zustand.aendern(lambda z: replace(z, master="codex"), frist=2.0)
    assert neu.master == "codex"


def test_zwei_prozesse_aendern_verschiedene_felder_beide_bleiben(daten):
    """Ohne Sperre ginge eine der beiden Änderungen verloren (beide lesen den leeren Zustand)."""
    code = (
        "import sys, time\n"
        "from dataclasses import replace\n"
        "from master_schalter import zustand\n"
        "start, feld, wert = float(sys.argv[1]), sys.argv[2], sys.argv[3]\n"
        "time.sleep(max(0, start - time.time()))\n"
        "def f(z):\n"
        "    time.sleep(0.4)\n"
        "    return replace(z, **{feld: wert})\n"
        "zustand.aendern(f, frist=5.0)\n"
    )
    start = str(time.time() + 1.5)
    prozesse = [
        subprocess.Popen([sys.executable, "-c", code, start, "master", "codex"], env=_umgebung(daten)),
        subprocess.Popen([sys.executable, "-c", code, start, "uebergabe", "C:/x/paket.md"], env=_umgebung(daten)),
    ]
    for p in prozesse:
        assert p.wait(timeout=30) == 0
    z = zustand.lesen()
    assert z.master == "codex"
    assert z.uebergabe == "C:/x/paket.md"
