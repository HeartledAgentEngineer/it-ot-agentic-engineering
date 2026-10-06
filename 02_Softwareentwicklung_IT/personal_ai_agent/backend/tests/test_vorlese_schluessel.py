"""Tests: eigener OpenRouter-Schluessel fuers Vorlesen (06.10.2026).

Agent (Rueckfall auf den Hauptschluessel), Selbsttest (nur die Art, nie der
Wert), gemeinsames Uebernahme-Skript am Handy, alle drei Startwege und das
PC-Werkzeug ``tools/handy/vorlese_schluessel_senden.py``. Offline, erfundene
Werte — nie ein echter Schluessel.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import llm_service as llm_modul

PROJEKT = Path(__file__).resolve().parents[2]
SKRIPT = PROJEKT / "termux" / "schluessel-uebernehmen.sh"
STARTWEGE = {
    "start-termux.sh": PROJEKT / "start-termux.sh",
    "agent-start": PROJEKT / "termux" / "agent-start",
    "agent-ensure.sh": PROJEKT / "termux" / "agent-ensure.sh",
}
FALSCH = "sk-or-v1-erfundenerTestwert/mit+Sonder=zeichen&und|strich"


def _werkzeug():
    pfad = PROJEKT / "tools" / "handy" / "vorlese_schluessel_senden.py"
    spez = importlib.util.spec_from_file_location("vorlese_schluessel_senden", pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# ── Agent: welcher Schluessel liest vor ─────────────────────────────────────

def test_ohne_eigenen_schluessel_liest_der_hauptclient(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_tts_key", "")
    dienst = llm_modul.LLMService()
    client, art = dienst._vorlese_client()
    assert client is dienst.client and art == "haupt"


def test_eigener_schluessel_eigener_client_einmal_gebaut(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_tts_key", FALSCH)
    dienst = llm_modul.LLMService()
    client, art = dienst._vorlese_client()
    assert art == "eigener" and client is not dienst.client
    assert client.api_key == FALSCH
    assert dienst._vorlese_client()[0] is client                  # wiederverwendet


def test_speak_nutzt_den_vorlese_client_und_loggt_den_wert_nicht(monkeypatch, caplog):
    monkeypatch.setattr(settings, "openrouter_tts_key", FALSCH)
    dienst = llm_modul.LLMService()
    aufrufe = []

    def erzeugen(**kw):
        aufrufe.append(kw)
        return SimpleNamespace(read=lambda: b"mp3")

    tts, _ = dienst._vorlese_client()
    monkeypatch.setattr(tts.audio.speech, "create", erzeugen)
    if dienst.client is not None:
        monkeypatch.setattr(dienst.client.audio.speech, "create",
                            lambda **kw: pytest.fail("Hauptclient darf nicht vorlesen"))
    caplog.set_level("INFO")
    assert dienst.speak("Auf diesem Bild: Testperson") == b"mp3"
    assert aufrufe and aufrufe[0]["input"] == "Auf diesem Bild: Testperson"
    assert "Schlüssel: eigener" in caplog.text and FALSCH not in caplog.text


def test_selbsttest_zeigt_nur_die_art(monkeypatch):
    from app.router import selbsttest

    monkeypatch.setattr(settings, "openrouter_tts_key", "")
    assert selbsttest._sprache_info()["vorlese_schluessel"] == "haupt"
    monkeypatch.setattr(settings, "openrouter_tts_key", FALSCH)
    info = selbsttest._sprache_info()
    assert info["vorlese_schluessel"] == "eigener"
    assert FALSCH not in json.dumps(info)


# ── Handy: gemeinsames Uebernahme-Skript ────────────────────────────────────

def _lauf(env: Path, quelle: Path, *namen):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash nicht vorhanden")
    return subprocess.run([bash, str(SKRIPT).replace("\\", "/"), str(env).replace("\\", "/"),
                           str(quelle).replace("\\", "/"), "Vorlese-Schlüssel", *namen],
                          capture_output=True, text=True, encoding="utf-8")


def test_vorlese_schluessel_wird_uebernommen_und_uebergabe_geloescht(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=bleibt\nPCLOUD_TOKEN=bleibt-auch\n", encoding="utf-8")
    quelle = tmp_path / "vorlese_schluessel.txt"
    quelle.write_bytes(f"OPENROUTER_TTS_KEY={FALSCH}\r\nPCLOUD_TOKEN=fremd\r\n".encode())
    lauf = _lauf(env, quelle, "OPENROUTER_TTS_KEY")
    assert lauf.returncode == 0
    zeilen = env.read_text(encoding="utf-8").splitlines()
    assert f"OPENROUTER_TTS_KEY={FALSCH}" in zeilen
    assert "OPENROUTER_API_KEY=bleibt" in zeilen and "PCLOUD_TOKEN=bleibt-auch" in zeilen  # nur erlaubte Namen
    assert (tmp_path / ".env.vorher").exists()
    assert not quelle.exists(), "Geheimnis darf nicht im Download-Ordner liegen bleiben"
    assert FALSCH not in lauf.stdout + lauf.stderr


def test_ohne_pflichtzeile_bleibt_die_uebergabe_liegen(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=bleibt\n", encoding="utf-8")
    quelle = tmp_path / "vorlese_schluessel.txt"
    quelle.write_text("ANDERES=x\n", encoding="utf-8")
    assert _lauf(env, quelle, "OPENROUTER_TTS_KEY").returncode == 0
    assert quelle.exists() and "OPENROUTER_TTS_KEY" not in env.read_text(encoding="utf-8")


def test_skript_gibt_keine_werte_aus():
    for zeile in SKRIPT.read_text(encoding="utf-8").splitlines():
        if "echo" in zeile:
            assert "$wert" not in zeile and "$ersatz" not in zeile


@pytest.mark.parametrize("name", sorted(STARTWEGE))
def test_jeder_startweg_uebernimmt_den_vorlese_schluessel(name):
    text = STARTWEGE[name].read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines()
              if "vorlese_schluessel.txt" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) == 1, f"{name}: genau ein Aufruf erwartet"
    assert "schluessel-uebernehmen.sh" in zeilen[0] and "OPENROUTER_TTS_KEY" in zeilen[0]
    assert zeilen[0].rstrip().endswith("|| true"), f"{name}: darf den Start nie verhindern"
    aufruf = text.index(zeilen[0])
    assert text.index("pull --ff-only") < aufruf < text.index("python -m uvicorn app.main:app")


# ── PC-Werkzeug ─────────────────────────────────────────────────────────────

def _hermes_env(tmp_path, wert=FALSCH):
    pfad = tmp_path / "hermes.env"
    pfad.write_text(f"OPENROUTER_API_KEY=sk-or-v1-anderer\nOPENROUTER_TTS_KEY=\"{wert}\"\n", encoding="utf-8")
    return pfad


class _Adb:
    """Attrappe fuer adb: merkt Aufrufe und den Inhalt der Push-Datei zum Zeitpunkt des Pushs."""

    def __init__(self, push_rc=0, liegen_bleiben=0):
        self.aufrufe, self.gepusht, self.push_rc, self.ls_rest = [], None, push_rc, liegen_bleiben

    def __call__(self, befehl, **_kw):
        self.aufrufe.append(befehl[1:])
        art = befehl[1:]
        if art[0] == "push":
            self.gepusht = Path(art[1]).read_text(encoding="utf-8")
            return SimpleNamespace(returncode=self.push_rc, stdout="", stderr="")
        if art[:2] == ["shell", "stat"]:
            return SimpleNamespace(returncode=0, stdout=f"{len(self.gepusht.encode())}\n", stderr="")
        if art[:2] == ["shell", "ls"]:
            self.ls_rest -= 1
            return SimpleNamespace(returncode=0 if self.ls_rest >= 0 else 1, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_trockenlauf_zeigt_nie_den_wert(tmp_path, capsys):
    adb = _Adb()
    assert _werkzeug().main(["--quelle", str(_hermes_env(tmp_path))], ausfuehren=adb) == 0
    aus = capsys.readouterr().out
    assert "gefunden" in aus and FALSCH not in aus and adb.aufrufe == []


def test_fehlende_oder_unplausible_quelle_exit_2(tmp_path):
    w = _werkzeug()
    assert w.main(["--quelle", str(tmp_path / "fehlt.env")], ausfuehren=_Adb()) == 2
    leer = tmp_path / "leer.env"
    leer.write_text("OPENROUTER_API_KEY=sk-or-v1-x\n", encoding="utf-8")
    assert w.main(["--quelle", str(leer)], ausfuehren=_Adb()) == 2
    assert w.main(["--quelle", str(_hermes_env(tmp_path, "kein schluessel"))], ausfuehren=_Adb()) == 2


def test_senden_legt_genau_eine_zeile_ab_und_raeumt_auf(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    adb = _Adb()
    assert _werkzeug().main(["--quelle", str(_hermes_env(tmp_path)), "--senden"], ausfuehren=adb) == 0
    assert adb.gepusht == f"OPENROUTER_TTS_KEY={FALSCH}\n"
    assert adb.aufrufe[0][2] == "/sdcard/Download/vorlese_schluessel.txt"
    assert list((tmp_path / "tmp").iterdir()) == [], "lokale Zwischendatei muss weg sein"
    assert FALSCH not in capsys.readouterr().out


def test_push_fehler_exit_1_und_trotzdem_aufgeraeumt(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    assert _werkzeug().main(["--quelle", str(_hermes_env(tmp_path)), "--senden"], ausfuehren=_Adb(push_rc=1)) == 1
    assert list((tmp_path / "tmp").iterdir()) == []


def test_neustart_wartet_bis_die_uebergabe_weg_ist(tmp_path):
    adb = _Adb(liegen_bleiben=2)
    rc = _werkzeug().main(["--quelle", str(_hermes_env(tmp_path)), "--senden", "--neustart"],
                          ausfuehren=adb, schlafen=lambda _s: None)
    assert rc == 0
    assert ["shell", "am", "force-stop", "com.termux"] in adb.aufrufe
    assert sum(1 for a in adb.aufrufe if a[:2] == ["shell", "ls"]) == 3
