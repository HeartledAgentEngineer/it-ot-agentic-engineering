"""Tests für das Senden (Attrappe statt `codex.exe`) und den festen Prompt."""
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import besitz, codex_senden, uebergabe, vorgaenge
from master_schalter.auftrag import Auftrag

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"
JETZT = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
ENDE = JETZT + timedelta(hours=3)
PROGRAMM = "C:/werkzeuge/codex.exe"
GEHEIM = "GEHEIMER-BETREFF-INHALT"
DATEI = "geheime_datei.py"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX", PROGRAMM)
    return repo


def _git_attrappe(status=f" M {DATEI}\n"):
    def git(repo, args):
        if args[:2] == ["rev-parse", "--short"]:
            return "abc1234\n"
        if args[:2] == ["rev-list", "--count"]:
            return "99\n"
        if args[0] == "status":
            return status
        raise AssertionError(args)   # log/--oneline darf im Automatikweg nie kommen
    return git


def _auftrag(thema="engineering"):
    return Auftrag(thema, "lauf-1", f"{thema}@4102444800", THREAD,
                   f".hermes/uebergabe/laufend/{thema}.md",
                   f".hermes/uebergabe/laufend/{thema}.master", 95.0, 50.0, ENDE, "2A")


def _besitzdatei(repo, auftrag, inhalt=None):
    datei = besitz.pfad(repo, auftrag.laufend)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(inhalt if inhalt is not None else f"reserviert {auftrag.lauf_id} {JETZT.isoformat()}",
                     encoding="utf-8")
    return datei


def _senden(umgebung, auftrag, transport, **kw):
    datei = _besitzdatei(umgebung, auftrag)
    reservierung = besitz.lesen(datei)
    erg = codex_senden.senden(auftrag, umgebung, datei, reservierung, JETZT,
                              transport=transport, git=_git_attrappe(), **kw)
    return erg, datei


def test_sendet_und_setzt_phase_gesendet(umgebung):
    aufrufe = []

    def transport(liste, timeout):
        aufrufe.append((liste, timeout))
        return 0

    erg, datei = _senden(umgebung, _auftrag(), transport)

    assert erg.phase == "gesendet" and erg.paket.is_file()
    assert vorgaenge.finden("engineering@4102444800").phase == "gesendet"
    assert besitz.lesen(datei).startswith("codex engineering@4102444800 ")
    assert aufrufe[0][1] == codex_senden.TIMEOUT_SEKUNDEN


def test_argumentliste_genau(umgebung):
    gesehen = {}

    def transport(liste, timeout):
        gesehen["liste"] = liste
        return 0

    erg, _ = _senden(umgebung, _auftrag(), transport)

    assert gesehen["liste"][:5] == [PROGRAMM, "queue", "--thread", THREAD, "--message"]
    assert gesehen["liste"][5] == codex_senden.prompt(_auftrag(), umgebung, erg.paket)
    assert len(gesehen["liste"]) == 6


def test_startfehler_ohne_prozess_setzt_nur_eigenen_besitz_zurueck(umgebung):
    def transport(liste, timeout):
        raise FileNotFoundError("codex.exe fehlt")

    erg, datei = _senden(umgebung, _auftrag(), transport)

    assert erg.phase == "fehler"
    text = besitz.lesen(datei)
    assert text.startswith("claude ") and "fehlgeschlagen" in text and "engineering@4102444800" in text
    assert vorgaenge.finden("engineering@4102444800").phase == "fehler"


def test_zeitueberschreitung_nach_start_bleibt_unklar_und_codex_besitz(umgebung):
    def transport(liste, timeout):
        raise subprocess.TimeoutExpired(liste, timeout)

    erg, datei = _senden(umgebung, _auftrag(), transport)

    assert erg.phase == "unklar"
    assert besitz.lesen(datei).startswith("codex engineering@4102444800 ")
    assert vorgaenge.finden("engineering@4102444800").phase == "unklar"


def test_rueckgabewert_ungleich_null_ist_unklar(umgebung):
    erg, datei = _senden(umgebung, _auftrag(), lambda liste, timeout: 3)

    assert erg.phase == "unklar" and "Rückgabewert 3" in erg.meldung
    assert besitz.lesen(datei).startswith("codex ")


def test_bestehende_kennung_wird_nicht_gesendet(umgebung):
    aufrufe = []
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang("engineering@4102444800", "engineering",
                                                           "lauf-0", "sende", JETZT.isoformat())])
    erg, _ = _senden(umgebung, _auftrag(), lambda liste, timeout: aufrufe.append(liste) or 0)

    assert erg.phase == "doppelt"
    assert aufrufe == []
    assert vorgaenge.finden("engineering@4102444800").lauf_id == "lauf-0"


def test_paketfehler_vor_dem_transport_loest_sicher_auf(umgebung, monkeypatch):
    aufrufe = []

    def kaputt(*a, **k):
        raise uebergabe.UebergabeFehler("Platte voll")

    monkeypatch.setattr(uebergabe, "paket_bauen", kaputt)
    erg, datei = _senden(umgebung, _auftrag(), lambda liste, timeout: aufrufe.append(liste) or 0)

    assert erg.phase == "fehler" and "Platte voll" in erg.meldung
    assert aufrufe == []
    assert "fehlgeschlagen" in besitz.lesen(datei)
    assert vorgaenge.finden("engineering@4102444800").phase == "fehler"


def test_automatikpaket_ohne_betreffzeilen_und_dateinamen(umgebung):
    erg, _ = _senden(umgebung, _auftrag(), lambda liste, timeout: 0)
    text = erg.paket.read_text(encoding="utf-8")

    assert DATEI not in text and GEHEIM not in text
    assert "Uncommittete Pfade: 1 (nur Anzahl, keine Dateinamen)" in text
    assert uebergabe.KEINE_PLANLISTE in text


def test_fremde_besitzmarke_verhindert_den_versand(umgebung):
    auftrag = _auftrag()
    datei = besitz.pfad(umgebung, auftrag.laufend)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("claude 2026-10-15T11:00:00+00:00", encoding="utf-8")
    aufrufe = []
    erg = codex_senden.senden(auftrag, umgebung, datei, "reserviert lauf-1 irgendwas", JETZT,
                             transport=lambda liste, timeout: aufrufe.append(liste) or 0,
                             git=_git_attrappe())

    assert erg.phase == "fehler" and aufrufe == []
    assert besitz.lesen(datei).startswith("claude 2026-10-15T11:00:00")


def test_prompt_enthaelt_besitzpruefung_und_keine_dateiinhalte(umgebung):
    auftrag = _auftrag()
    text = codex_senden.prompt(auftrag, umgebung, umgebung / "paket.md")

    assert f"ACK {auftrag.id}" in text and f"ABGELEHNT {auftrag.id}" in text
    assert "am Zeilenanfang" in text and "vor jedem weiteren Schritt erneut" in text
    assert "engineering.master" in text and "engineering.md" in text
    assert "95 %" in text and "50 %" in text and "Lage 2A" in text
    assert GEHEIM not in text


def test_programm_aus_der_umgebung(umgebung):
    assert codex_senden.programm() == PROGRAMM


def test_programm_sucht_neuestes_codex_exe(umgebung, monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_CODEX")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    alt = tmp_path / "appdata" / "OpenAI" / "Codex" / "bin" / "alt" / "codex.exe"
    neu = tmp_path / "appdata" / "OpenAI" / "Codex" / "bin" / "neu" / "codex.exe"
    for pfad, zeit in ((alt, 1_000_000), (neu, 2_000_000)):
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("x", encoding="utf-8")
        import os
        os.utime(pfad, (zeit, zeit))
    assert codex_senden.programm() == str(neu)
