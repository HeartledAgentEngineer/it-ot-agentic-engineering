import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from master_schalter import assistent_vorgaenge as av
from master_schalter import abgabe_nachweis, assistent, automatik, modi


def _eintrag(**felder):
    basis = asdict(av.Vorgang(
        "v-1", "engineering", "hermes", "codex", "vorbereitet",
        "2026-10-29T00:00:00+00:00", {"master": "codex", "worker": "codex", "modell": "gpt-6-luna"}, "codex",
    ))
    basis.update(felder)
    return basis


def test_legacy_ohne_version_und_modus_bleibt_fristsicher_serialisierbar(tmp_path):
    roh = _eintrag()
    roh.pop("ablauf_version")
    roh.pop("abgabe_modus")
    roh.pop("abgabe_nachweis")
    pfad = tmp_path / "assistent.json"
    pfad.write_text(json.dumps([roh]), encoding="utf-8")

    vorgang = av.lesen_geprueft(pfad)[0]
    assert (vorgang.ablauf_version, vorgang.abgabe_modus, vorgang.abgabe_nachweis) == (0, "frist", None)

    av.aendern(lambda liste: liste, datei_pfad=pfad)
    erneut = av.lesen_geprueft(pfad)[0]
    assert (erneut.ablauf_version, erneut.abgabe_modus) == (0, "frist")


@pytest.mark.parametrize("felder", [
    {"abgabe_modus": None},
    {"abgabe_modus": "unbekannt"},
    {"abgabe_modus": 1},
    {"abgabe_nachweis": []},
])
def test_version1_ungueltiger_modus_oder_nachweis_blockiert_strenges_lesen(tmp_path, felder):
    pfad = tmp_path / "assistent.json"
    pfad.write_text(json.dumps([_eintrag(**felder)]), encoding="utf-8")

    with pytest.raises(av.AssistentFehler):
        av.lesen_geprueft(pfad)


def test_mutation_ueberschreibt_keine_beschaedigte_registerdatei(tmp_path):
    pfad = tmp_path / "assistent.json"
    original = b"[{kaputt"
    pfad.write_bytes(original)

    with pytest.raises(av.AssistentFehler):
        av.aendern(lambda _liste: [], datei_pfad=pfad)

    assert pfad.read_bytes() == original


def test_diagnose_zeigt_fingerprint_und_position_ohne_inhalt(tmp_path):
    pfad = tmp_path / "assistent.json"
    pfad.write_text(json.dumps([_eintrag(), None]), encoding="utf-8")

    diagnose = av.register_diagnose(pfad)

    assert diagnose.status == "beschädigt"
    assert diagnose.ungueltige_positionen == (2,)
    assert len(diagnose.sha256) == 64
    assert not hasattr(diagnose, "inhalt")


def test_wartemodus_kann_nicht_uebersprungen_werden(tmp_path):
    pfad = tmp_path / "assistent.json"
    pfad.write_text(json.dumps([_eintrag(phase="abgabe_fehler", abgabe_modus="warten")]), encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="nicht übersprungen"):
        av.abgabe_ueberspringen("v-1", "Frist", datei_pfad=pfad)

    assert av.lesen_geprueft(pfad)[0].phase == "abgabe_fehler"


def test_wartemodus_ueberlebt_abgelaufenen_fristschritt():
    alt = av.Vorgang("v-1", "engineering", "hermes", "codex", "abgabe_angefragt",
                     "2026-10-29T00:00:00+00:00", {}, "codex", abgabe_seit="2026-10-29T00:00:00+00:00",
                     abgabe_modus="warten")

    neu = assistent._frist(alt, repo=None, jetzt=datetime.now(timezone.utc) + timedelta(days=1), transport=None)

    assert neu == alt


def test_wartemodus_verlangt_beide_chatreferenzen_vor_pruefungen():
    with pytest.raises(assistent.AssistentFehler, match="alten und neuen Chat"):
        assistent.uebergeben("engineering", "hermes", abgabe_modus="warten")


def test_nachweis_bindet_frischen_kopf_head_und_datei(tmp_path, monkeypatch):
    datei = tmp_path / "engineering.md"
    datei.write_text("Übergabebereit: ja · 2026-10-29T00:00:00+00:00 · aaaaaaa\nStand", encoding="utf-8")
    kopfzeit = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(modi, "_paar_pruefen", lambda *_args, **_kwargs: (None, datei))
    monkeypatch.setattr(automatik, "kopfzeile_lesen", lambda _pfad: ("ja", kopfzeit, "aaaaaaa"))
    monkeypatch.setattr(automatik, "kopf_hash", lambda _repo, _git: "a" * 40)
    vorgang = SimpleNamespace(abgabe_seit="2026-10-28T23:59:00+00:00")

    beweis = abgabe_nachweis.pruefen("engineering", vorgang, tmp_path, kopfzeit + timedelta(minutes=1),
                                     git=lambda *_args: "a" * 40)

    assert beweis.head == "a" * 40
    assert beweis.datei_sha256
    assert abgabe_nachweis.passt(SimpleNamespace(abgabe_nachweis=beweis.als_dict()), beweis)


def test_nachweis_blockiert_kopf_vor_abgabeauftrag(tmp_path, monkeypatch):
    datei = tmp_path / "engineering.md"
    datei.write_text("synthetic", encoding="utf-8")
    kopfzeit = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(modi, "_paar_pruefen", lambda *_args, **_kwargs: (None, datei))
    monkeypatch.setattr(automatik, "kopfzeile_lesen", lambda _pfad: ("ja", kopfzeit, "aaaaaaa"))
    monkeypatch.setattr(automatik, "kopf_hash", lambda _repo, _git: "a" * 40)

    with pytest.raises(abgabe_nachweis.NachweisFehler, match="vor diesem Abgabeauftrag"):
        abgabe_nachweis.pruefen("engineering", SimpleNamespace(abgabe_seit="2026-10-29T00:01:00+00:00"),
                                 tmp_path, kopfzeit + timedelta(minutes=2), git=lambda *_args: "a" * 40)
