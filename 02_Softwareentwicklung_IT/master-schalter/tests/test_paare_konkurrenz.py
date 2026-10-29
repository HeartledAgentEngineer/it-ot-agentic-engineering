"""Konkurrenztests für den gemeinsamen Schreibvertrag von paare.json."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from master_schalter import paare

THREAD_A = "01a12557-3bb3-7171-a021-53e6ac879534"
THREAD_B = "01a0a68e-5041-7610-a528-38d42f66bed3"


@pytest.fixture
def daten(tmp_path, monkeypatch):
    pfad = tmp_path / "daten"
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(pfad))
    return pfad


def _paar_setzen(thema: str, thread: str, aktiv: bool = False) -> None:
    paare.setzen(thema, thread, paare.laufend_bilden(thema), aktiv=aktiv)


def test_zwei_gleichzeitige_auto_freigaben_verlieren_keine_aenderung(daten, monkeypatch):
    _paar_setzen("thema-a", THREAD_A)
    _paar_setzen("thema-b", THREAD_B)
    echte_lesen = paare.lesen
    erste_lesung = threading.Event()
    zweite_lesung = threading.Event()
    fortsetzen = threading.Event()
    aufrufe = 0
    aufrufe_sperre = threading.Lock()

    def instrumentierte_lesung(*args, **kwargs):
        nonlocal aufrufe
        with aufrufe_sperre:
            aufrufe += 1
            nummer = aufrufe
        ergebnis = echte_lesen(*args, **kwargs)
        if nummer == 1:
            erste_lesung.set()
            # Bei korrekter Sperre wird der zweite Aufruf hier warten; nach kurzer
            # Beobachtungsfrist lösen wir den ersten immer frei.
            fortsetzen.wait(timeout=0.4)
        elif nummer == 2:
            zweite_lesung.set()
        return ergebnis

    monkeypatch.setattr(paare, "lesen", instrumentierte_lesung)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(paare.aktiv_setzen, "thema-a", True)
        assert erste_lesung.wait(timeout=2)
        b = pool.submit(paare.aktiv_setzen, "thema-b", True)
        try:
            # Unverriegelte Implementierung erreicht die zweite Lesung mit altem
            # Snapshot; verriegelte Implementierung wartet am Eingang.
                zweite_lesung.wait(timeout=1.5)
        finally:
            fortsetzen.set()
        a.result(timeout=7)
        b.result(timeout=7)

    assert {p.thema: p.aktiv for p in echte_lesen()} == {"thema-a": True, "thema-b": True}


def test_paaranlage_waehrend_umschaltung_bleibt_erhalten(daten, monkeypatch):
    _paar_setzen("thema-a", THREAD_A)
    echte_lesen = paare.lesen
    erste_lesung = threading.Event()
    zweite_lesung = threading.Event()
    fortsetzen = threading.Event()
    aufrufe = 0
    aufrufe_sperre = threading.Lock()

    def instrumentierte_lesung(*args, **kwargs):
        nonlocal aufrufe
        with aufrufe_sperre:
            aufrufe += 1
            nummer = aufrufe
        ergebnis = echte_lesen(*args, **kwargs)
        if nummer == 1:
            erste_lesung.set()
            fortsetzen.wait(timeout=2)
        elif nummer == 2:
            zweite_lesung.set()

        return ergebnis

    monkeypatch.setattr(paare, "lesen", instrumentierte_lesung)
    with ThreadPoolExecutor(max_workers=2) as pool:
        umschalten = pool.submit(paare.aktiv_setzen, "thema-a", True)
        assert erste_lesung.wait(timeout=2)
        anlegen = pool.submit(_paar_setzen, "thema-b", THREAD_B, True)
        try:
            # Die zweite Lesung tritt im alten Code mit veraltetem Snapshot ein;
            # unter der Sperre wird der erste Zyklus nach kurzer Frist freigegeben.
            zweite_lesung.wait(timeout=1.5)
        finally:
            fortsetzen.set()
        umschalten.result(timeout=7)
        anlegen.result(timeout=7)

    assert {p.thema: p.aktiv for p in paare.lesen()} == {"thema-a": True, "thema-b": True}


@pytest.mark.parametrize("schreibaufruf", [
    "paare.aktiv_setzen('thema-a', True)",
    "paare.setzen('thema-b', '01a0a68e-5041-7610-a528-38d42f66bed3', "
    "paare.laufend_bilden('thema-b'))",
    "paare.schreiben(paare.lesen())",
])
def test_os_sperre_in_zweitprozess_uebersetzt_fehler_und_laesst_daten_unveraendert(
        daten, schreibaufruf):
    _paar_setzen("thema-a", THREAD_A)
    vorzustand = (daten / "paare.json").read_bytes()
    python = sys.executable
    kind_code = (
        "from master_schalter import zustand; "
        "with_sperre = zustand.sperre(); with_sperre.__enter__(); "
        "print('READY', flush=True); input(); with_sperre.__exit__(None, None, None)"
    )
    env = os.environ.copy()
    env["MASTER_SCHALTER_DATEN"] = str(daten)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    halter = subprocess.Popen([python, "-c", kind_code], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    bereit = threading.Event()
    bereit_zeile: list[str] = []

    def bereit_lesen() -> None:
        try:
            assert halter.stdout is not None
            bereit_zeile.append(halter.stdout.readline())
        finally:
            bereit.set()

    leser = threading.Thread(target=bereit_lesen, daemon=True)
    leser.start()
    try:
        assert bereit.wait(timeout=5), f"Kindprozess meldete READY nicht; exit={halter.poll()}"
        assert bereit_zeile == ["READY\n"], f"unerwartete Kindprozessmeldung: {bereit_zeile!r}"
        code = f"""from master_schalter import paare
try:
    {schreibaufruf}
except paare.PaarFehler:
    raise SystemExit(0)
raise SystemExit(3)
"""
        ergebnis = subprocess.run([python, "-c", code], capture_output=True, text=True,
                                  timeout=20, env=env)
        assert ergebnis.returncode == 0, ergebnis.stderr
        assert (daten / "paare.json").read_bytes() == vorzustand
    finally:
        if halter.poll() is None:
            try:
                if halter.stdin is not None:
                    halter.stdin.write("\n")
                    halter.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            try:
                halter.wait(timeout=2)
            except subprocess.TimeoutExpired:
                halter.terminate()
                try:
                    halter.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    halter.kill()
                    halter.wait(timeout=2)
        else:
            halter.wait(timeout=2)
