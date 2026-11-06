"""Tests für `agy_senden` und die Weck-Integration im Wechselassistenten (`assistent.py`)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import agy_senden, assistent, besitz, modi, paare, postfach, protokoll
from master_schalter import assistent_vorgaenge as av
from master_schalter.assistent import ChatRef

THEMA = "engineering"
LAUFEND = paare.laufend_bilden(THEMA)
KENNUNG_AGY = "12345678-1234-4234-8234-1234567890ab"
KENNUNG_CODEX = "GEHEIM-CODEX-1234"
THREAD_CODEX = "019a2de5-bb88-71d2-8522-91ba62a9f4b2"
CODEX_MARKE = besitz.zeile(besitz.CODEX, "20261001T000000Z-abcd1234", "2026-10-01T00:00:00+00:00")


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    daten = tmp_path / "daten"
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen(THEMA, THREAD_CODEX, LAUFEND, aktiv=True)
    marke_datei = repo / besitz.pfad(repo, LAUFEND)
    marke_datei.parent.mkdir(parents=True, exist_ok=True)
    marke_datei.write_text(CODEX_MARKE, encoding="utf-8")
    modi.master_setzen(THEMA, "codex", repo=repo)
    return repo


# --- agy_senden Tests -----------------------------------------------------------------

def test_verbindungsstatus_leer(tmp_path):
    datei = tmp_path / "agy-server.json"
    status = agy_senden.verbindungsstatus(datei)
    assert status["konfiguriert"] is False
    assert status["adresse"] == ""
    assert status["token_vorhanden"] is False


def test_verbindungsstatus_vollstaendig(tmp_path):
    datei = tmp_path / "agy-server.json"
    exe = tmp_path / "language_server.exe"
    exe.write_text("stub", encoding="utf-8")
    env = {
        "ANTIGRAVITY_AGENTAPI_EXE": str(exe),
        "ANTIGRAVITY_LS_ADDRESS": "127.0.0.1:4295",
        "ANTIGRAVITY_CSRF_TOKEN": "geheim-token-123",
    }
    agy_senden.umgebung_merken(env, datei)
    status = agy_senden.verbindungsstatus(datei)
    assert status["konfiguriert"] is True
    assert status["adresse"] == "127.0.0.1:4295"
    assert status["token_vorhanden"] is True
    assert status["exe_vorhanden"] is True


def test_nachricht_senden_ohne_verbindung_liefert_verbindung_fehlt(tmp_path):
    datei = tmp_path / "nicht-existent.json"
    erg = agy_senden.nachricht_senden(KENNUNG_AGY, "Hallo", datei=datei)
    assert erg == "verbindung_fehlt"


def test_nachricht_senden_mit_attrappe_ok():
    aufrufe = []

    def lauf(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        aufrufe.append(befehl)
        return 0, "{}"

    erg = agy_senden.nachricht_senden(KENNUNG_AGY, "Hallo Welt", titel="Test", lauf=lauf)
    assert erg == "ok"
    assert len(aufrufe) == 1
    assert aufrufe[0][:3] == ["agentapi", "send-message", "--title"]
    assert aufrufe[0][3] == "Test"
    assert aufrufe[0][4] == KENNUNG_AGY
    assert aufrufe[0][5] == "Hallo Welt"


def test_nachricht_senden_timeout_liefert_unklar():
    def lauf(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        raise subprocess.TimeoutExpired(cmd=befehl, timeout=timeout)

    erg = agy_senden.nachricht_senden(KENNUNG_AGY, "Hallo Welt", lauf=lauf)
    assert erg == "unklar"


def test_nachricht_senden_oserror_liefert_nicht_erreichbar():
    def lauf(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        raise OSError("Verbindungsaufbau fehlgeschlagen")

    erg = agy_senden.nachricht_senden(KENNUNG_AGY, "Hallo Welt", lauf=lauf)
    assert erg == "nicht_erreichbar"


# --- Integration im Assistenten -------------------------------------------------------

def test_assistent_uebergabe_an_agy_mit_erfolgreichem_wecken(umgebung):
    weck_aufrufe = []

    def agy_lauf(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        weck_aufrufe.append(befehl)
        return 0, "{}"

    # Abgabe durch alten Master Codex überspringen (kein alter Chat übergeben)
    vorgang = assistent.uebergeben(
        THEMA, "agy", nach_chat=ChatRef("agy", KENNUNG_AGY),
        repo=umgebung, agy_transport=agy_lauf
    )

    assert vorgang.phase == "im_postfach"
    assert len(weck_aufrufe) == 1
    assert KENNUNG_AGY in weck_aufrufe[0]

    # Protokoll prüfen
    eintraege = protokoll.lesen()
    weck_eintrag = [e for e in eintraege if e.get("vorgang") == vorgang.id and e.get("entscheidung") == "weckversuch"]
    assert len(weck_eintrag) == 1
    assert weck_eintrag[0]["grund"] == "agy:ok"


def test_assistent_uebergabe_an_agy_wenn_wecken_nicht_erreichbar(umgebung):
    def agy_lauf_fehler(befehl: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
        raise OSError("Port geschlossen")

    vorgang = assistent.uebergeben(
        THEMA, "agy", nach_chat=ChatRef("agy", KENNUNG_AGY),
        repo=umgebung, agy_transport=agy_lauf_fehler
    )

    # Postfach liegt bereit, aber der Fehler im Weckversuch ist transparent dokumentiert
    assert vorgang.phase == "im_postfach"
    assert vorgang.fehler == "Chat-Wecken: nicht_erreichbar (Postfach bereit)"

    eintraege = protokoll.lesen()
    weck_eintrag = [e for e in eintraege if e.get("vorgang") == vorgang.id and e.get("entscheidung") == "weckversuch"]
    assert len(weck_eintrag) == 1
    assert weck_eintrag[0]["grund"] == "agy:nicht_erreichbar"
