"""Tests für die Vorgänge des Wechselassistenten (`assistent.json`): Speicher, Wiederaufnahme, Quittung."""
from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from master_schalter import assistent_vorgaenge as av
from master_schalter import besitz, modi

THEMA = "engineering"
ANDERES = "anderes-thema"


def _vorgang(ident="v-1", thema=THEMA, phase="vorbereitet"):
    return av.Vorgang(ident, thema, "hermes", "claude", phase, "2026-10-20T10:00:00+00:00",
                      {"master": "kontingent", "worker": "workflow", "modell": None}, "")


# --- Speicher ---------------------------------------------------------------------

def test_ohne_datei_leer(umgebung):
    assert av.lesen() == []
    assert av.datei().name == "assistent.json"


def test_roundtrip_ueber_aendern_und_finden(umgebung):
    neu = av.aendern(lambda alt: [*alt, _vorgang()])
    assert neu == [_vorgang()]
    assert av.lesen() == [_vorgang()]
    assert av.finden("v-1") == _vorgang()
    assert av.finden("gibtsnicht") is None


def test_fehler_in_der_funktion_schreibt_nichts(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang()])

    def kaputt(alt):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        av.aendern(kaputt)
    assert av.lesen() == [_vorgang()]


def test_unbrauchbare_eintraege_werden_uebersprungen(umgebung):
    gut = {"id": "v-gut", "thema": THEMA, "ziel": "hermes", "von": "claude", "phase": "vorbereitet",
           "zeit": "z", "vorzustand_profil": {}, "vorzustand_marke": ""}
    roh = [gut, {**gut, "id": "../x"}, {**gut, "id": "v-p", "phase": "erfunden"},
           {**gut, "id": "v-z", "ziel": "gemini"}, {**gut, "id": "v-t", "thema": "Gross"}, "kein-objekt"]
    av.datei().write_text(json.dumps(roh), encoding="utf-8")
    assert [v.id for v in av.lesen()] == ["v-gut"]


def test_zwei_themen_aendern_parallel_beide_eintraege_bleiben(umgebung):
    def schreiber(thema):
        for nr in range(10):
            av.aendern(lambda alt, n=nr: [*alt, _vorgang(f"{thema}-{n}", thema)])

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(schreiber, THEMA), pool.submit(schreiber, ANDERES)]
        for job in jobs:
            job.result(timeout=30)

    ids = {v.id for v in av.lesen()}
    assert ids == {f"{t}-{n}" for t in (THEMA, ANDERES) for n in range(10)}


def test_neue_id_entspricht_dem_muster_und_ist_eindeutig(umgebung):
    ids = {av.neue_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(modi.VORGANG_ID_MUSTER.fullmatch(i) for i in ids)
    assert all(re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", i) for i in ids)


def test_aktualisieren_aendert_nur_den_genannten_vorgang(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang("v-1"), _vorgang("v-2")])
    neu = av.aktualisieren("v-1", phase="sende")
    assert neu.phase == "sende"
    assert av.finden("v-2") == _vorgang("v-2")
    assert av.aktualisieren("gibtsnicht", phase="sende") is None


# --- Wiederaufnahme ---------------------------------------------------------------

def _wiederaufnehmen(umgebung):
    return av.wiederaufnehmen(umgebung.repo)


def test_vorbereitet_und_marke_unveraendert_wird_verworfen(umgebung):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1")

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "verworfen")]
    assert av.finden("v-1").phase == "verworfen"
    assert umgebung.marke() == "claude 2026-10-20T10:00:00+00:00"


def test_vorbereitet_ohne_markendatei_und_marke_weiter_fehlend_wird_verworfen(umgebung):
    umgebung.vorbereiten("v-1")
    assert [e.status for e in _wiederaufnehmen(umgebung)] == ["verworfen"]


def test_vorbereitet_mit_eigener_zwischenmarke_ist_reparatur_und_nach_wiederholung_rolle_gesetzt(
        umgebung, monkeypatch):
    umgebung.vorbereiten("v-1")
    original = besitz.schreiben

    def absturz_vor_final(datei, text):
        if besitz.assistent_marke(text) is not None:
            raise RuntimeError("synthetischer Absturz")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", absturz_vor_final)
    with pytest.raises(RuntimeError):
        umgebung.uebergeben("v-1", "hermes")
    monkeypatch.setattr(besitz, "schreiben", original)

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "reparatur")]
    assert "Reparatur nötig" in erg[0].hinweis
    assert av.finden("v-1").phase == "vorbereitet"                  # nichts übersprungen
    umgebung.uebergeben("v-1", "hermes")                            # gleiche Wahl erneut = Reparaturweg
    assert [e.status for e in _wiederaufnehmen(umgebung)] == ["rolle_gesetzt"]
    assert av.finden("v-1").phase == "rolle_gesetzt"


def test_zwischenmarke_mit_anderem_ziel_ist_keine_eigene(umgebung):
    umgebung.vorbereiten("v-1", ziel="hermes")
    umgebung.marke_setzen(modi.zwischenmarke(THEMA, "codex", "2026-10-20T11:00:00+00:00"))
    assert [e.status for e in _wiederaufnehmen(umgebung)] == ["verworfen"]


def test_vorbereitet_mit_fertiger_assistentenmarke_wird_rolle_gesetzt(umgebung, monkeypatch):
    umgebung.vorbereiten("v-1")
    original = besitz.schreiben

    def absturz_nach_final(datei, text):
        original(datei, text)
        if besitz.assistent_marke(text) is not None:
            raise RuntimeError("synthetischer Absturz nach der Zielmarke")

    monkeypatch.setattr(besitz, "schreiben", absturz_nach_final)
    with pytest.raises(RuntimeError):
        umgebung.uebergeben("v-1", "hermes")

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "rolle_gesetzt")]
    assert av.finden("v-1").phase == "rolle_gesetzt"


def test_vorbereitet_mit_fremd_geaenderter_marke_wird_verworfen(umgebung):
    umgebung.vorbereiten("v-1")
    umgebung.marke_setzen("codex 2026-10-20T12:00:00+00:00 assistent " + THEMA + " v-anderer")
    assert [e.status for e in _wiederaufnehmen(umgebung)] == ["verworfen"]


def test_sende_ohne_ergebnis_wird_unklar_und_es_wird_nie_gesendet(umgebung, monkeypatch):
    umgebung.vorbereiten("v-1", phase="sende")

    def verboten(*args, **kwargs):
        raise AssertionError("Wiederaufnahme darf nie senden")

    monkeypatch.setattr(subprocess, "run", verboten)
    monkeypatch.setattr(subprocess, "Popen", verboten)

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "unklar")]
    assert av.finden("v-1").phase == "unklar"
    assert _wiederaufnehmen(umgebung) == []                         # zweiter Lauf: nichts mehr offen


def test_rolle_gesetzt_ohne_sende_bleibt_nachholbar_ohne_automatismus(umgebung):
    umgebung.vorbereiten("v-1", phase="rolle_gesetzt")
    erg = _wiederaufnehmen(umgebung)
    assert [(e.id, e.status) for e in erg] == [("v-1", "nachholbar")]
    assert av.finden("v-1").phase == "rolle_gesetzt"


@pytest.mark.parametrize("phase", ["gesendet", "im_postfach", "fehler", "unklar", "im_chat",
                                   "bestaetigt", "verworfen"])
def test_andere_phasen_werden_nicht_angefasst(umgebung, phase):
    umgebung.vorbereiten("v-1", phase=phase)
    vorher = av.datei().read_text(encoding="utf-8")
    assert _wiederaufnehmen(umgebung) == []
    assert av.datei().read_text(encoding="utf-8") == vorher


def test_nicht_lesbare_marke_laesst_den_vorgang_unveraendert(umgebung, monkeypatch):
    umgebung.vorbereiten("v-1")

    def unlesbar(datei):
        raise modi.ModusFehler("Besitzstatus nicht lesbar")

    monkeypatch.setattr(modi, "_besitz_text_lesen", unlesbar)
    erg = _wiederaufnehmen(umgebung)
    assert [e.status for e in erg] == ["nicht_pruefbar"]
    assert av.finden("v-1").phase == "vorbereitet"


# --- Quittung (G4/G5) -------------------------------------------------------------

def _uebergeben(umgebung, vorgang_id="v-1", ziel="hermes"):
    umgebung.vorbereiten(vorgang_id, ziel=ziel)
    umgebung.uebergeben(vorgang_id, ziel)


def test_quittieren_neu_setzt_bestaetigt(umgebung):
    _uebergeben(umgebung)
    erg = av.quittieren("v-1", "neu", umgebung.repo)
    assert erg.phase == "bestaetigt" and erg.fehler is None
    assert av.finden("v-1").phase == "bestaetigt"


def test_quittieren_abgabe_setzt_nur_die_abgabeflagge(umgebung):
    _uebergeben(umgebung)
    erg = av.quittieren("v-1", "abgabe", umgebung.repo)
    assert erg.abgabe_bestaetigt is True and erg.phase == "vorbereitet"


def test_quittung_bei_veralteter_marke_wird_abgelehnt(umgebung):
    _uebergeben(umgebung)
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)         # späterer Wechsel überschreibt die Marke
    vorher = av.datei().read_text(encoding="utf-8")

    for art in ("neu", "abgabe"):
        with pytest.raises(av.AssistentFehler, match="veraltet"):
            av.quittieren("v-1", art, umgebung.repo)

    assert av.datei().read_text(encoding="utf-8") == vorher


def test_quittung_neu_verlangt_die_zielrolle_in_der_marke(umgebung):
    umgebung.vorbereiten("v-1", ziel="hermes")
    umgebung.marke_setzen(f"claude 2026-10-20T10:00:00+00:00 assistent {THEMA} v-1")
    with pytest.raises(av.AssistentFehler, match="erwartet wurde hermes"):
        av.quittieren("v-1", "neu", umgebung.repo)
    assert av.quittieren("v-1", "abgabe", umgebung.repo).abgabe_bestaetigt is True


def test_quittung_fuer_unbekannten_oder_verworfenen_vorgang_und_schlechte_eingaben(umgebung):
    with pytest.raises(av.AssistentFehler, match="unbekannt"):
        av.quittieren("v-9", "neu", umgebung.repo)
    umgebung.vorbereiten("v-2", phase="verworfen")
    with pytest.raises(av.AssistentFehler, match="verworfen"):
        av.quittieren("v-2", "neu", umgebung.repo)
    with pytest.raises(av.AssistentFehler):
        av.quittieren("../x", "neu", umgebung.repo)
    with pytest.raises(av.AssistentFehler):
        av.quittieren("v-2", "beides", umgebung.repo)


def test_a_b_a_alte_quittung_ist_ungueltig(umgebung):
    _uebergeben(umgebung, "v-1", "hermes")
    _uebergeben(umgebung, "v-2", "claude")                         # zurück an Claude
    with pytest.raises(av.AssistentFehler, match="veraltet"):
        av.quittieren("v-1", "neu", umgebung.repo)
    assert av.quittieren("v-2", "neu", umgebung.repo).phase == "bestaetigt"
