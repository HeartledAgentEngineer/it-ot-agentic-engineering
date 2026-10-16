from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from master_schalter import besitz, modi, paare, vorgaenge


THEMA = "personal-ai-agent"
THREAD = "00000000-0000-4000-8000-000000000001"


def _paar(repo: Path) -> None:
    paare.setzen(THEMA, THREAD, paare.laufend_bilden(THEMA), aktiv=True)


def test_fehlt_modusdatei_ist_kontingent(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    assert modi.lesen(datei) == {}
    assert modi.modus(THEMA, datei) == modi.KONTINGENT


def test_modus_roundtrip_erhaelt_andere_themen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.modus(THEMA) == modi.HERMES_CODEX
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    assert besitz.besitzer(besitz.lesen(master)) == besitz.HERMES
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-000000000002",
                 paare.laufend_bilden("anderes-thema"), aktiv=True)
    modi.setzen("anderes-thema", modi.HERMES_CODEX, repo=repo)
    assert modi.lesen() == {THEMA: modi.HERMES_CODEX, "anderes-thema": modi.HERMES_CODEX}


def test_hermes_kontingent_rundreise_entwertet_offenen_vorgang(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "synthetisch-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)

    v = vorgaenge.finden("synthetisch-1")
    assert v is not None and v.phase == "entwertet"
    assert modi.modus(THEMA) == modi.KONTINGENT
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    assert besitz.besitzer(besitz.lesen(master)) == besitz.CLAUDE
    assert "modus-reset" in besitz.lesen(master)
    assert not modi.geschuetzt(THEMA, repo=repo)


def test_wiederholung_von_hermesmodus_repariert_fehlende_besitzmarke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    modi._speichern(modi.datei(), THEMA, modi.HERMES_CODEX)

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert besitz.besitzer(besitz.lesen(master)) == besitz.HERMES
    assert modi.geschuetzt(THEMA, repo=repo)


def test_aktivierung_nach_markenfehler_bleibt_geschuetzt_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    original = modi._speichern
    fehler = True

    def einmalig(datei_pfad: Path, thema: str, wert: str) -> None:
        nonlocal fehler
        if fehler:
            fehler = False
            raise OSError("synthetischer Schreibfehler")
        original(datei_pfad, thema, wert)

    monkeypatch.setattr(modi, "_speichern", einmalig)
    with pytest.raises(modi.ModusFehler, match="Umschaltung unvollständig"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.geschuetzt(THEMA, repo=repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.modus(THEMA) == modi.HERMES_CODEX


def test_aktivierung_bei_fehler_beim_entwerten_hat_keine_nebenwirkung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")

    def fehler(*_args, **_kwargs):
        raise OSError("synthetischer Fehler beim Entwerten")

    monkeypatch.setattr(modi, "_offene_entwerten", fehler)
    with pytest.raises(modi.ModusFehler, match="offene Vorgänge nicht entwertet"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}
    assert besitz.lesen(master) == "codex vorgang-1 2026-10-16"


def test_aktivierung_nach_besitzmarken_schreibfehler_bleibt_unveraendert_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")
    original = besitz.schreiben
    fehler = True

    def einmalig(datei: Path, text: str) -> None:
        nonlocal fehler
        if fehler and text.startswith("hermes "):
            fehler = False
            raise OSError("synthetischer Hermes-Markenfehler")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", einmalig)
    with pytest.raises(modi.ModusFehler, match="Hermes-Besitzmarke nicht gespeichert"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}
    assert besitz.lesen(master) == "codex vorgang-1 2026-10-16"
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.geschuetzt(THEMA, repo=repo)


def test_parallele_moduswechsel_verschiedener_themen_verlieren_keinen_eintrag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-000000000002",
                 paare.laufend_bilden("anderes-thema"), aktiv=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [
            executor.submit(modi.setzen, THEMA, modi.HERMES_CODEX, repo=repo),
            executor.submit(modi.setzen, "anderes-thema", modi.HERMES_CODEX, repo=repo),
        ]
        for job in jobs:
            job.result(timeout=10)

    assert modi.lesen() == {THEMA: modi.HERMES_CODEX, "anderes-thema": modi.HERMES_CODEX}


def test_rueckstellung_nach_source_reset_fehler_bleibt_geschuetzt_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    original = besitz.schreiben
    fehler = True

    def einmalig(datei: Path, text: str) -> None:
        nonlocal fehler
        if fehler and text.startswith("claude ") and "modus-reset" in text:
            fehler = False
            raise OSError("synthetischer Resetfehler")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", einmalig)
    with pytest.raises(modi.ModusFehler, match="Besitzmarke noch nicht zurückgesetzt"):
        modi.setzen(THEMA, modi.KONTINGENT, repo=repo)
    assert modi.modus(THEMA) == modi.KONTINGENT
    assert modi.geschuetzt(THEMA, repo=repo)
    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)
    assert not modi.geschuetzt(THEMA, repo=repo)


@pytest.mark.parametrize("stufe,erwarteter_modus,erwarteter_besitzer,meldung", [
    ("hermes-marke", modi.KONTINGENT, besitz.CLAUDE, "Hermes-Besitzmarke nicht gespeichert"),
    ("hermes-modus", modi.KONTINGENT, besitz.HERMES, "Hermes-Besitzmarke steht"),
    ("kontingent-modus", modi.HERMES_CODEX, besitz.HERMES, "Kontingentmodus nicht gespeichert"),
    ("besitz-reset", modi.KONTINGENT, besitz.HERMES, "Besitzmarke noch nicht zurückgesetzt"),
])
def test_spaeter_schreibfehler_meldet_auch_dauerhafte_entwertung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    stufe: str, erwarteter_modus: str, erwarteter_besitzer: str, meldung: str,
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    if stufe in ("kontingent-modus", "besitz-reset"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "offen-vor-fehler", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    if stufe in ("hermes-marke", "besitz-reset"):
        original = besitz.schreiben

        def besitz_fehler(datei: Path, text: str) -> None:
            if stufe == "hermes-marke" and text.startswith("hermes "):
                raise OSError("synthetischer Besitzfehler")
            if stufe == "besitz-reset" and text.startswith("claude ") and "modus-reset" in text:
                raise OSError("synthetischer Besitzfehler")
            original(datei, text)

        monkeypatch.setattr(besitz, "schreiben", besitz_fehler)
    else:
        monkeypatch.setattr(modi, "_speichern", lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetischer Modusfehler")))

    ziel = modi.HERMES_CODEX if stufe in ("hermes-marke", "hermes-modus") else modi.KONTINGENT
    with pytest.raises(modi.ModusFehler) as fehler:
        modi.setzen(THEMA, ziel, repo=repo)

    text = str(fehler.value)
    assert "offene Vorgänge entwertet" in text
    assert meldung in text
    assert vorgaenge.finden("offen-vor-fehler").phase == "entwertet"
    assert modi.modus(THEMA) == erwarteter_modus
    assert besitz.besitzer(besitz.lesen(master)) == erwarteter_besitzer


def test_kontingent_noop_beruehrt_offenen_codex_vorgang_nicht(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "vorgang-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)

    assert vorgaenge.finden("vorgang-1").phase == "gesendet"
    assert besitz.besitzer(besitz.lesen(master)) == besitz.CODEX


def test_fremde_reservierung_wird_vor_jeder_nebenwirkung_abgelehnt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    fremd = "reserviert fremder-lauf 2026-10-16"
    besitz.schreiben(master, fremd)

    with pytest.raises(modi.ModusFehler, match="fremd reserviert"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}
    assert besitz.lesen(master) == fremd


def test_unlesbare_besitzdatei_ist_keine_fehlende_claude_marke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    original = Path.read_text

    def nicht_lesbar(datei: Path, *args, **kwargs):
        if datei == master:
            raise PermissionError("synthetisch nicht lesbar")
        return original(datei, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", nicht_lesbar)
    with pytest.raises(modi.ModusFehler, match="Besitzstatus nicht lesbar"):
        modi.geschuetzt(THEMA, repo=repo)
    with pytest.raises(modi.ModusFehler, match="Besitzstatus nicht lesbar"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert not modi.datei().exists()
    assert vorgaenge.lesen() == []


@pytest.mark.parametrize("thema", ["../privat", "Upper", "", "a" * 81])
def test_ungueltiges_thema_wird_abgelehnt(tmp_path: Path, thema: str) -> None:
    with pytest.raises((modi.ModusFehler, paare.PaarFehler)):
        modi.modus(thema, tmp_path / "themenmodi.json")


def test_beschaedigtes_schema_wird_nicht_als_kontingent_verschluckt(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    datei.write_text(json.dumps({"version": 2, "themen": {}}), encoding="utf-8")
    with pytest.raises(modi.ModusFehler):
        modi.lesen(datei)


def test_setzen_unbekanntes_thema_ohne_paar_wird_abgelehnt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(modi.ModusFehler):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

