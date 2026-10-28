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


# --- erneuern: `claude auth status` ohne Konsole, ohne Ausgabe, wirft nie ----------------------------------------

class _ErneuernProzess:
    pid = 777

    def __init__(self, code=0, timeout=False):
        self.code, self.timeout, self.wait_aufrufe = code, timeout, []

    def wait(self, timeout=None):
        self.wait_aufrufe.append(timeout)
        if self.timeout:
            raise subprocess.TimeoutExpired("synthetisch", timeout)
        return self.code

    def kill(self):
        self.wait_aufrufe.append("kill")


def _popen_fuer(monkeypatch, prozess):
    aufrufe = []

    def fake_popen(args, **kwargs):
        aufrufe.append((args, kwargs))
        return prozess

    monkeypatch.setattr(claude_anmeldung.subprocess, "Popen", fake_popen)
    return aufrufe


@pytest.mark.parametrize("code, erwartet", [(0, True), (1, False)])
def test_erneuern_startet_auth_status_ohne_konsole_und_ohne_ausgabe(monkeypatch, code, erwartet):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ("C:/synthetisch/claude.exe",))
    prozess = _ErneuernProzess(code)
    aufrufe = _popen_fuer(monkeypatch, prozess)

    assert claude_anmeldung.erneuern({"PATH": "synthetisch", "CLAUDE_CONFIG_DIR": ""}) is erwartet

    args, kwargs = aufrufe[0]
    assert args == ["C:/synthetisch/claude.exe", "auth", "status"]
    assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert not kwargs["creationflags"] & getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    assert "CLAUDE_CONFIG_DIR" not in kwargs["env"] and kwargs["env"]["PATH"] == "synthetisch"
    assert prozess.wait_aufrufe == [30]          # Frist 30 s, keine Ausgabe gelesen (kein communicate)


def test_erneuern_nutzt_die_uebergebene_frist(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ("claude",))
    prozess = _ErneuernProzess(0)
    _popen_fuer(monkeypatch, prozess)

    assert claude_anmeldung.erneuern(frist=7)

    assert prozess.wait_aufrufe == [7]


def test_erneuern_beendet_bei_timeout_den_prozessbaum_und_meldet_false(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ("claude",))
    prozess = _ErneuernProzess(timeout=True)
    _popen_fuer(monkeypatch, prozess)
    beendet = []
    monkeypatch.setattr(claude_anmeldung, "prozessbaum_beenden", beendet.append)

    assert claude_anmeldung.erneuern(frist=1) is False

    assert beendet == [prozess]


def test_erneuern_bei_timeout_und_fehler_beim_beenden_kill_und_wirft_nicht(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ("claude",))
    prozess = _ErneuernProzess(timeout=True)
    _popen_fuer(monkeypatch, prozess)

    def kaputt(_prozess):
        raise OSError("synthetisch")

    monkeypatch.setattr(claude_anmeldung, "prozessbaum_beenden", kaputt)

    assert claude_anmeldung.erneuern(frist=1) is False
    assert "kill" in prozess.wait_aufrufe


def test_erneuern_ohne_cli_startet_nichts(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: None)
    aufrufe = _popen_fuer(monkeypatch, _ErneuernProzess())

    assert claude_anmeldung.erneuern() is False
    assert aufrufe == []


def test_erneuern_wirft_nie(monkeypatch):
    monkeypatch.setattr(modelle, "claude_programm", lambda: ("claude",))
    monkeypatch.setattr(claude_anmeldung.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("synthetisch")))

    assert claude_anmeldung.erneuern() is False

    def kaputtes_programm():
        raise RuntimeError("synthetisch")

    monkeypatch.setattr(modelle, "claude_programm", kaputtes_programm)
    assert claude_anmeldung.erneuern() is False
