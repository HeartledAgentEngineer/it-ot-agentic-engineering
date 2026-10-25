"""Tests für `modi.master_uebergeben_gesperrt` und den Parameter `vorgang_id` (Wechselassistent, G1/G3)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from master_schalter import besitz, modi, vorgaenge, zustand

THEMA = "engineering"


def test_assistentenmarke_wird_als_einziger_zielschreibvorgang_geschrieben(umgebung, monkeypatch):
    geschrieben: list[str] = []
    original = besitz.schreiben

    def merken(datei, text):
        geschrieben.append(text)
        original(datei, text)

    modi.worker_setzen(THEMA, "codex", repo=umgebung.repo)          # Worker/Modell sollen erhalten bleiben
    monkeypatch.setattr(besitz, "schreiben", merken)

    profil = umgebung.uebergeben("v-eins", "hermes")

    assert profil.master == "hermes" and profil.worker == "codex"
    assert modi.profil(THEMA) == profil
    assert besitz.assistent_marke(umgebung.marke()) == ("hermes", THEMA, "v-eins")
    assert besitz.besitzer(umgebung.marke()) == besitz.HERMES
    assert len(geschrieben) == 2                                    # Zwischenmarke + Assistentenmarke
    assert modi.ist_zwischenmarke(geschrieben[0], THEMA)
    assert geschrieben[1] == umgebung.marke()
    assert " modus " not in geschrieben[1]                          # nie eine fertige Modusmarke ohne ID


def test_zielrolle_besitzt_schon_marke_wird_trotzdem_mit_vorgangs_id_neu_geschrieben(umgebung):
    modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)
    alt = umgebung.marke()
    assert besitz.assistent_marke(alt) is None

    umgebung.uebergeben("v-zwei", "hermes")

    assert umgebung.marke() != alt
    assert besitz.assistent_marke(umgebung.marke()) == ("hermes", THEMA, "v-zwei")


def test_gleicher_vorgang_zweimal_aendert_die_fertige_marke_nicht(umgebung):
    umgebung.uebergeben("v-drei", "codex")
    fertig = umgebung.marke()

    umgebung.uebergeben("v-drei", "codex")

    assert umgebung.marke() == fertig


def test_ohne_vorgang_id_bleibt_v040_verhalten_marke_bytegleich(umgebung):
    modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)
    alt = umgebung.marke()

    modi.master_setzen(THEMA, "hermes", repo=umgebung.repo)

    assert umgebung.marke() == alt
    assert " modus " in alt


def test_kapsel_nimmt_die_themensperre_nicht_selbst(umgebung):
    # Hielte die Kapsel die Sperre selbst erneut an, scheiterte sie hier an der eigenen Sperre.
    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        modi.master_uebergeben_gesperrt(THEMA, "claude", vorgang_id="v-vier", repo=umgebung.repo)
    assert besitz.assistent_marke(umgebung.marke()) == ("claude", THEMA, "v-vier")


@pytest.mark.parametrize("ungueltig", ["", "../x", "a b", "a\\b", "x\n", "a" * 81, "/abs", "ä"])
def test_ungueltige_vorgangs_id_wird_abgelehnt_ohne_nebenwirkung(umgebung, ungueltig):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    vorher = umgebung.marke()
    with pytest.raises(modi.ModusFehler):
        umgebung.uebergeben(ungueltig, "hermes")
    assert umgebung.marke() == vorher
    assert modi.lesen() == {}


@pytest.mark.parametrize("ziel", ["kontingent", "gemini", ""])
def test_nur_zielrollen_claude_codex_hermes(umgebung, ziel):
    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0):
        with pytest.raises(modi.ModusFehler):
            modi.master_uebergeben_gesperrt(THEMA, ziel, vorgang_id="v-fuenf", repo=umgebung.repo)
    assert modi.lesen() == {}


def test_offene_mastervorgaenge_werden_entwertet(umgebung):
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "synthetisch-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    umgebung.uebergeben("v-sechs", "hermes")

    assert vorgaenge.finden("synthetisch-1").phase == "entwertet"


def test_absturz_vor_dem_markenschreiben_laesst_marke_alt(umgebung, monkeypatch):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    alt = umgebung.marke()

    def absturz(datei, text):
        raise RuntimeError("synthetischer Absturz vor jeder Marke")

    monkeypatch.setattr(besitz, "schreiben", absturz)
    with pytest.raises(RuntimeError):
        umgebung.uebergeben("v-sieben", "hermes")

    assert umgebung.marke() == alt
    assert modi.lesen() == {}


def test_absturz_unmittelbar_vor_der_assistentenmarke_hinterlaesst_zwischenmarke(umgebung, monkeypatch):
    original = besitz.schreiben

    def absturz_vor_final(datei, text):
        if besitz.assistent_marke(text) is not None:
            raise RuntimeError("synthetischer Absturz vor der Assistentenmarke")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", absturz_vor_final)
    with pytest.raises(RuntimeError):
        umgebung.uebergeben("v-acht", "hermes")

    assert modi.ist_zwischenmarke(umgebung.marke(), THEMA)
    assert besitz.assistent_marke(umgebung.marke()) is None
    assert modi.geschuetzt(THEMA, repo=umgebung.repo)               # fail-closed geschützt

    monkeypatch.setattr(besitz, "schreiben", original)              # Wiederholung vervollständigt
    umgebung.uebergeben("v-acht", "hermes")
    assert besitz.assistent_marke(umgebung.marke()) == ("hermes", THEMA, "v-acht")


def test_absturz_unmittelbar_nach_der_assistentenmarke_hinterlaesst_fertige_marke(umgebung, monkeypatch):
    original = besitz.schreiben

    def absturz_nach_final(datei, text):
        original(datei, text)
        if besitz.assistent_marke(text) is not None:
            raise RuntimeError("synthetischer Absturz nach der Assistentenmarke")

    monkeypatch.setattr(besitz, "schreiben", absturz_nach_final)
    with pytest.raises(RuntimeError):
        umgebung.uebergeben("v-neun", "hermes")

    assert besitz.assistent_marke(umgebung.marke()) == ("hermes", THEMA, "v-neun")
    assert modi.profil(THEMA).master == "hermes"


def test_zwischenmarke_eines_abgebrochenen_wechsels_wird_vervollstaendigt(umgebung):
    umgebung.marke_setzen(modi.zwischenmarke(THEMA, "codex", datetime.now(timezone.utc).isoformat()))

    umgebung.uebergeben("v-zehn", "codex")

    assert besitz.assistent_marke(umgebung.marke()) == ("codex", THEMA, "v-zehn")
