"""Offline-Tests für den unterstützten Claude-Loginprozess mit synthetischen Prozessen."""
import os
import subprocess

import pytest

from master_schalter import claude_anmeldung, modelle


def test_login_befehl_verwendet_offizielles_cli_und_feste_argumente(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ["C:/synthetisch/claude.exe"])

    assert claude_anmeldung.login_befehl() == [
        "C:/synthetisch/claude.exe", "auth", "login", "--claudeai"]


def test_login_befehl_meldet_fehlende_cli_mit_festem_text(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: None)

    with pytest.raises(claude_anmeldung.Anmeldefehler) as fehler:
        claude_anmeldung.login_befehl()

    assert str(fehler.value) == "Claude-Code-CLI wurde nicht gefunden"


@pytest.mark.parametrize("wert, erwartet", [(None, None), ("", None), ("C:/synthetisch/config", "C:/synthetisch/config")])
def test_login_umgebung_leitet_config_dir_konsistent_weiter(monkeypatch, wert, erwartet):
    quelle = {"PATH": "synthetischer-pfad", "SYNTHETIC_AUTH": "unverändert"}
    if wert is not None:
        quelle["CLAUDE_CONFIG_DIR"] = wert

    ergebnis = claude_anmeldung.login_umgebung(quelle)

    assert ergebnis.get("CLAUDE_CONFIG_DIR") == erwartet
    assert ergebnis["PATH"] == "synthetischer-pfad"
    assert ergebnis["SYNTHETIC_AUTH"] == "unverändert"
    assert quelle.get("CLAUDE_CONFIG_DIR") == wert


def test_login_startet_sichtbaren_interaktiven_prozess_ohne_rohstreams(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ["claude"])
    monkeypatch.setattr(claude_anmeldung.os, "name", "nt")
    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(claude_anmeldung.subprocess, "Popen", fake_popen)
    proc = claude_anmeldung.login_starten({"PATH": "synthetisch", "CLAUDE_CONFIG_DIR": ""})

    assert proc is not None
    args, kwargs = calls[0]
    assert args == ["claude", "auth", "login", "--claudeai"]
    assert kwargs["creationflags"] == subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    assert "stdin" not in kwargs and "stdout" not in kwargs and "stderr" not in kwargs
    assert "CLAUDE_CONFIG_DIR" not in kwargs["env"]


def test_login_auf_nicht_windows_ist_klar_nicht_unterstuetzt(monkeypatch):
    monkeypatch.setattr(claude_anmeldung.os, "name", "posix")
    calls = []
    monkeypatch.setattr(claude_anmeldung.subprocess, "Popen", lambda *a, **k: calls.append(a))

    with pytest.raises(claude_anmeldung.Anmeldefehler):
        claude_anmeldung.login_starten({})

    assert calls == []


def test_timeout_bereinigt_nur_den_uebergebenen_pid_mit_begrenztem_warten(monkeypatch):
    prozess = type("Prozess", (), {"pid": 321, "wait": lambda self, timeout: calls.append(("wait", timeout))})()
    calls = []
    monkeypatch.setattr(claude_anmeldung.os, "name", "nt")
    monkeypatch.setattr(claude_anmeldung.subprocess, "run",
                        lambda args, **kw: calls.append((args, kw)))

    claude_anmeldung.prozessbaum_beenden(prozess)

    assert calls[0][0] == ["taskkill", "/PID", "321", "/T", "/F"]
    assert calls[0][1]["stdout"] == subprocess.DEVNULL
    assert calls[0][1]["stderr"] == subprocess.DEVNULL
    assert calls[1] == ("wait", 5)


def test_taskkill_fehler_fuehrt_trotzdem_ein_begrenztes_warten_aus(monkeypatch):
    calls = []

    class Prozess:
        pid = 456

        def wait(self, timeout):
            calls.append(("wait", timeout))
            raise subprocess.TimeoutExpired("synthetisch", timeout)

    monkeypatch.setattr(claude_anmeldung.os, "name", "nt")
    monkeypatch.setattr(claude_anmeldung.subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError("synthetisch")))

    with pytest.raises(subprocess.TimeoutExpired):
        claude_anmeldung.prozessbaum_beenden(Prozess())

    assert calls == [("wait", 5)]
