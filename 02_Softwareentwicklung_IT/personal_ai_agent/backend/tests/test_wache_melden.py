"""Wache im Modus 'melden' (29.09.2026): Benachrichtigung ohne Modellaufruf.

Befund: Jede Zustellung weckte die Hermes-Sitzung mit ihrem ganzen Verlauf
(~800k Tokens je Aufruf). Der neue Standard meldet nur per Windows-Hinweis,
laesst die Nachrichten ungelesen und meldet jede nur einmal.
"""
import importlib.util
from pathlib import Path

HIER = Path(__file__).resolve().parents[2] / "tools" / "agentbus"


def _lade(name, datei):
    spec = importlib.util.spec_from_file_location(name, HIER / datei)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _aufbau(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(tmp_path))
    monkeypatch.delenv("WACHE_MODUS", raising=False)
    bus = _lade("agentbus_test", "agentbus.py")
    wache = _lade("wache_test", "wache.py")
    monkeypatch.setattr(wache, "busmodul", lambda: bus)
    toasts, zustellungen = [], []
    monkeypatch.setattr(wache, "toast", lambda t, x: toasts.append((t, x)))
    monkeypatch.setattr(wache, "zustellen", lambda s, x: zustellungen.append(x) or True)
    bus.init(tmp_path)
    return bus, wache, toasts, zustellungen


def test_melden_ist_standard_und_ruft_kein_modell(tmp_path, monkeypatch):
    bus, wache, toasts, zustellungen = _aufbau(tmp_path, monkeypatch)
    bus.send(tmp_path, "claude", "hermes", "task", "bitte pruefen")
    assert wache.wache() == 0
    assert zustellungen == []
    assert len(toasts) == 1 and "1 Nachricht" in toasts[0][0]


def test_melden_laesst_nachrichten_ungelesen(tmp_path, monkeypatch):
    bus, wache, _, _ = _aufbau(tmp_path, monkeypatch)
    bus.send(tmp_path, "claude", "hermes", "task", "bitte pruefen")
    wache.wache()
    assert len(bus.read(tmp_path, "hermes")) == 1


def test_jede_nachricht_nur_einmal_gemeldet(tmp_path, monkeypatch):
    bus, wache, toasts, _ = _aufbau(tmp_path, monkeypatch)
    bus.send(tmp_path, "claude", "hermes", "task", "eins")
    wache.wache()
    wache.wache()
    assert len(toasts) == 1
    bus.send(tmp_path, "claude", "hermes", "info", "zwei")
    wache.wache()
    assert len(toasts) == 2 and "2 Nachricht" in toasts[1][0]


def test_ohne_nachricht_kein_hinweis(tmp_path, monkeypatch):
    _, wache, toasts, zustellungen = _aufbau(tmp_path, monkeypatch)
    assert wache.wache() == 0
    assert toasts == [] and zustellungen == []


def test_zustellen_nur_ausdruecklich(tmp_path, monkeypatch):
    bus, wache, toasts, zustellungen = _aufbau(tmp_path, monkeypatch)
    bus.send(tmp_path, "claude", "hermes", "task", "dringend")
    assert wache.wache(modus="zustellen") == 0
    assert len(zustellungen) == 1 and toasts == []
    assert bus.read(tmp_path, "hermes") == []
