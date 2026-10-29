"""Tests für die Vorgänge des Wechselassistenten (`assistent.json`): Speicher, Wiederaufnahme, Quittung."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import replace
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


def test_abgabe_sende_ohne_ergebnis_wird_abgabe_unklar_und_es_wird_nie_gesendet(umgebung, monkeypatch):
    umgebung.vorbereiten("v-1")
    av.abgabe_beginnen("v-1")
    seit = av.finden("v-1").abgabe_seit

    def verboten(*args, **kwargs):
        raise AssertionError("Wiederaufnahme darf nie senden")

    monkeypatch.setattr(subprocess, "run", verboten)
    monkeypatch.setattr(subprocess, "Popen", verboten)

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "unklar")]
    vorgang = av.finden("v-1")
    assert vorgang.phase == "abgabe_unklar" and vorgang.abgabe_seit == seit      # Frist läuft weiter
    assert vorgang.fehler == "Absturz während der Abgabe-Zustellung – nicht automatisch erneut gesendet"
    assert [(e.id, e.status) for e in _wiederaufnehmen(umgebung)] == [("v-1", "abgabe_offen")]


@pytest.mark.parametrize("phase", ["abgabe_angefragt", "abgabe_unklar"])
def test_offene_abgabe_bleibt_stehen_status_abgabe_offen(umgebung, phase):
    umgebung.vorbereiten("v-1", phase=phase)
    av.aktualisieren("v-1", abgabe_seit="2026-10-21T09:00:00+00:00")

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "abgabe_offen")]
    assert erg[0].hinweis == "Abgabe offen – Frist läuft seit 2026-10-21T09:00:00+00:00"
    assert av.finden("v-1").phase == phase


@pytest.mark.parametrize("phase", ["abgegeben", "abgabe_uebersprungen"])
def test_erledigte_abgabe_ohne_rolle_ist_nachholbar(umgebung, phase):
    umgebung.vorbereiten("v-1", phase=phase)
    erg = _wiederaufnehmen(umgebung)
    assert [(e.id, e.status) for e in erg] == [("v-1", "nachholbar")]
    assert av.finden("v-1").phase == phase


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


@pytest.mark.parametrize("phase", ["abgabe_sende", "abgabe_angefragt", "abgabe_unklar"])
def test_quittieren_abgabe_ist_in_jeder_offenen_abgabephase_gueltig(umgebung, phase):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1", phase=phase)                         # Marke gehört noch dem alten Master
    av.aktualisieren("v-1", fehler="alter Hinweis")

    erg = av.quittieren("v-1", "abgabe", umgebung.repo)

    assert erg.phase == "abgegeben" and erg.abgabe == "abgegeben" and erg.fehler is None
    assert av.finden("v-1") == erg


@pytest.mark.parametrize("phase", ["vorbereitet", "abgegeben", "abgabe_uebersprungen", "abgabe_fehler",
                                   "rolle_gesetzt"])
def test_quittieren_abgabe_in_anderen_phasen_wird_abgelehnt(umgebung, phase):
    umgebung.vorbereiten("v-1", phase=phase)
    vorher = av.datei().read_text(encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="Abgabe ist nicht offen"):
        av.quittieren("v-1", "abgabe", umgebung.repo)

    assert av.datei().read_text(encoding="utf-8") == vorher


def test_quittieren_abgabe_bei_geaenderter_marke_wird_abgelehnt(umgebung):
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1", phase="abgabe_angefragt")
    umgebung.marke_setzen("codex v-9 2026-10-20T11:00:00+00:00")     # später anders gesetzt
    vorher = av.datei().read_text(encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="Marke hat sich geändert"):
        av.quittieren("v-1", "abgabe", umgebung.repo)

    assert av.datei().read_text(encoding="utf-8") == vorher


def test_quittieren_abgabe_gilt_auch_bei_fehlender_markendatei(umgebung):
    umgebung.vorbereiten("v-1", phase="abgabe_angefragt")            # Vorzustand: Datei fehlte = ""
    assert av.quittieren("v-1", "abgabe", umgebung.repo).phase == "abgegeben"


def test_quittung_bei_veralteter_marke_wird_abgelehnt(umgebung):
    _uebergeben(umgebung)
    modi.master_setzen(THEMA, "codex", repo=umgebung.repo)         # späterer Wechsel überschreibt die Marke
    vorher = av.datei().read_text(encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="veraltet"):
        av.quittieren("v-1", "neu", umgebung.repo)
    with pytest.raises(av.AssistentFehler, match="nicht offen"):    # Phase rolle_gesetzt: keine Abgabe mehr
        av.quittieren("v-1", "abgabe", umgebung.repo)

    assert av.datei().read_text(encoding="utf-8") == vorher


def test_quittung_neu_verlangt_die_zielrolle_in_der_marke(umgebung):
    umgebung.vorbereiten("v-1", ziel="hermes")
    umgebung.marke_setzen(f"claude 2026-10-20T10:00:00+00:00 assistent {THEMA} v-1")
    with pytest.raises(av.AssistentFehler, match="Marke gehört nicht mehr zu diesem Vorgang") as info:
        av.quittieren("v-1", "neu", umgebung.repo)
    assert "claude" not in str(info.value)          # fester Text, kein Markeninhalt (P4 R7)
    assert av.finden("v-1").phase != "bestaetigt"


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


# --- Phasenwechsel und Abgabe-Helfer (G8) ---------------------------------------------

def test_phase_wechseln_greift_nur_aus_einer_der_vonphasen(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang("v-1"), _vorgang("v-2")])

    erg = av.phase_wechseln("v-1", ("vorbereitet", "sende"), "gesendet", fehler="x")
    assert erg.phase == "gesendet" and erg.fehler == "x" and erg.zeit != _vorgang().zeit
    assert av.finden("v-2") == _vorgang("v-2")                      # andere Vorgänge unberührt

    vorher = av.datei().read_text(encoding="utf-8")
    nicht = av.phase_wechseln("v-1", ("vorbereitet",), "verworfen", fehler="y")
    assert nicht.phase == "gesendet" and nicht.fehler == "x"        # unverändert zurückgegeben
    assert av.datei().read_text(encoding="utf-8") == vorher
    assert av.phase_wechseln("gibtsnicht", ("vorbereitet",), "sende") is None


def test_phase_wechseln_lehnt_unbekannte_zielphase_ab(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang()])
    with pytest.raises(av.AssistentFehler):
        av.phase_wechseln("v-1", ("vorbereitet",), "erfunden")


def test_abgabe_beginnen_setzt_phase_und_fristbeginn_nur_aus_vorbereitet(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang("v-1"), _vorgang("v-2", phase="rolle_gesetzt")])

    erg = av.abgabe_beginnen("v-1")
    assert erg.phase == "abgabe_sende" and erg.abgabe_seit is not None
    assert av.abgabe_beginnen("v-1").abgabe_seit == erg.abgabe_seit  # zweiter Aufruf ändert nichts
    assert av.abgabe_beginnen("v-2").phase == "rolle_gesetzt"
    assert av.finden("v-2").abgabe_seit is None


@pytest.mark.parametrize("ergebnis", ["abgabe_angefragt", "abgabe_fehler", "abgabe_unklar"])
def test_abgabe_ergebnis_nur_aus_abgabe_sende(umgebung, ergebnis):
    av.aendern(lambda alt: [*alt, _vorgang("v-1", phase="abgabe_sende"), _vorgang("v-2")])
    assert av.abgabe_ergebnis("v-1", ergebnis).phase == ergebnis
    assert av.abgabe_ergebnis("v-2", ergebnis).phase == "vorbereitet"


def test_abgabe_ergebnis_nach_quittung_laesst_abgegeben_stehen(umgebung):
    umgebung.vorbereiten("v-1")
    av.abgabe_beginnen("v-1")
    av.quittieren("v-1", "abgabe", umgebung.repo)                    # Quittung vor dem Transportergebnis

    erg = av.abgabe_ergebnis("v-1", "abgabe_angefragt")

    assert erg.phase == "abgegeben" and erg.abgabe == "abgegeben"


def test_abgabe_ergebnis_mit_ungueltigem_wert_wirft(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang("v-1", phase="abgabe_sende")])
    for falsch in ("abgegeben", "sende", "", "erfunden"):
        with pytest.raises(av.AssistentFehler):
            av.abgabe_ergebnis("v-1", falsch)
    assert av.finden("v-1").phase == "abgabe_sende"


@pytest.mark.parametrize("phase", ["vorbereitet", "abgabe_sende", "abgabe_angefragt", "abgabe_unklar",
                                   "abgabe_fehler"])
def test_abgabe_ueberspringen_aus_vorbereitet_und_offenen_phasen(umgebung, phase):
    av.aendern(lambda alt: [*alt, _vorgang("v-1", phase=phase)])

    erg = av.abgabe_ueberspringen("v-1", "10-Minuten-Frist abgelaufen")

    assert erg.phase == "abgabe_uebersprungen" and erg.abgabe == "uebersprungen"
    assert erg.fehler == "10-Minuten-Frist abgelaufen"


@pytest.mark.parametrize("phase", ["abgegeben", "rolle_gesetzt", "verworfen"])
def test_abgabe_ueberspringen_aus_anderen_phasen_aendert_nichts(umgebung, phase):
    av.aendern(lambda alt: [*alt, _vorgang("v-1", phase=phase)])
    assert av.abgabe_ueberspringen("v-1", "egal") == _vorgang("v-1", phase=phase)


def test_abgabefelder_werden_tolerant_gelesen_und_ueberleben_spaetere_phasen(umgebung):
    gut = {"id": "v-gut", "thema": THEMA, "ziel": "hermes", "von": "claude", "phase": "rolle_gesetzt",
           "zeit": "z", "vorzustand_profil": {}, "vorzustand_marke": "", "abgabe": "abgegeben",
           "abgabe_seit": "2026-10-21T09:00:00+00:00", "abgabe_zugestellt": "2026-10-21T09:01:00+00:00"}
    kaputt = {**gut, "id": "v-kaputt", "abgabe": "vielleicht", "abgabe_seit": 5, "abgabe_zugestellt": ["x"]}
    alt = {k: v for k, v in gut.items() if not k.startswith("abgabe")}
    register = [gut, kaputt, {**alt, "id": "v-alt", "abgabe_bestaetigt": True}]
    av.datei().write_text(json.dumps(register), encoding="utf-8")

    vorgaenge = {v.id: v for v in av.lesen()}

    assert (vorgaenge["v-gut"].abgabe, vorgaenge["v-gut"].abgabe_seit, vorgaenge["v-gut"].abgabe_zugestellt) == (
        "abgegeben", "2026-10-21T09:00:00+00:00", "2026-10-21T09:01:00+00:00")
    assert "v-kaputt" not in vorgaenge
    assert vorgaenge["v-alt"].abgabe is None                          # altes Feld wird nicht mehr gedeutet
    vor_mutation = av.datei().read_bytes()
    with pytest.raises(av.AssistentFehler):
        av.aktualisieren("v-gut", phase="sende")
    assert av.datei().read_bytes() == vor_mutation
    av.datei().write_text(json.dumps([gut, {**alt, "id": "v-alt", "abgabe_bestaetigt": True}]), encoding="utf-8")
    assert av.aktualisieren("v-gut", phase="sende").abgabe == "abgegeben"


# --- Chat-Referenzen und Wettlauf-Meldung (P4) ------------------------------------------

def test_alte_dateien_ohne_chatfelder_lesen_weiter(umgebung):
    alt = {"id": "v-alt", "thema": THEMA, "ziel": "hermes", "von": "claude", "phase": "vorbereitet",
           "zeit": "z", "vorzustand_profil": {}, "vorzustand_marke": ""}
    av.datei().write_text(json.dumps([alt]), encoding="utf-8")
    vorgang = av.finden("v-alt")
    assert vorgang.von_chat is None and vorgang.nach_chat is None


def test_chatfelder_ueberleben_den_roundtrip(umgebung):
    ref = {"werkzeug": "codex", "kennung": "abc-123_X"}
    av.aendern(lambda alt: [*alt, replace(_vorgang("v-1"), von_chat=ref, nach_chat={"werkzeug": "claude", "kennung": "k2"})])
    vorgang = av.finden("v-1")
    assert vorgang.von_chat == ref and vorgang.nach_chat == {"werkzeug": "claude", "kennung": "k2"}


@pytest.mark.parametrize("falsch", [
    "text", {"werkzeug": "codex"}, {"werkzeug": "gemini", "kennung": "k"}, {"werkzeug": "codex", "kennung": "../x"},
    {"werkzeug": "codex", "kennung": "k\n"}, {"werkzeug": "codex", "kennung": "k", "extra": 1},
    {"werkzeug": "codex", "kennung": "k" * 81}, {"werkzeug": 1, "kennung": "k"}])
def test_ungueltige_chatreferenzen_blockieren_strenge_leser(umgebung, falsch):
    roh = {"id": "v-1", "thema": THEMA, "ziel": "hermes", "von": "claude", "phase": "vorbereitet", "zeit": "z",
           "vorzustand_profil": {}, "vorzustand_marke": "", "von_chat": falsch, "nach_chat": falsch}
    av.datei().write_text(json.dumps([roh]), encoding="utf-8")
    with pytest.raises(av.AssistentFehler):
        av.finden("v-1")


def test_phase_gewinnen_meldet_nur_dem_gewinner_den_wechsel(umgebung):
    av.aendern(lambda alt: [*alt, _vorgang("v-1", phase="rolle_gesetzt")])
    erst, gewonnen1 = av.phase_gewinnen("v-1", ("rolle_gesetzt",), "sende")
    zweit, gewonnen2 = av.phase_gewinnen("v-1", ("rolle_gesetzt",), "sende")
    assert (erst.phase, gewonnen1) == ("sende", True)
    assert (zweit.phase, gewonnen2) == ("sende", False)
    assert av.phase_gewinnen("gibtsnicht", ("sende",), "unklar") == (None, False)
    with pytest.raises(av.AssistentFehler):
        av.phase_gewinnen("v-1", ("sende",), "erfunden")


def test_abgabe_fehler_ist_abgabe_offen_mit_fristhinweis_und_bleibt_unveraendert(umgebung):
    umgebung.vorbereiten("v-1", phase="abgabe_fehler")
    av.aktualisieren("v-1", abgabe_seit="2026-10-22T10:00:00+00:00")
    vorher = av.datei().read_text(encoding="utf-8")

    erg = _wiederaufnehmen(umgebung)

    assert [(e.id, e.status) for e in erg] == [("v-1", "abgabe_offen")]
    assert "Frist läuft seit 2026-10-22T10:00:00+00:00" in erg[0].hinweis and "übersprungen" in erg[0].hinweis
    assert av.datei().read_text(encoding="utf-8") == vorher


def test_wechsel_blockierend_und_ueberholbar_ueberschneiden_sich_nicht(umgebung):
    assert not set(av.WECHSEL_BLOCKIEREND) & set(av.UEBERHOLBAR)
    assert set(av.WECHSEL_BLOCKIEREND) == {"vorbereitet", "abgabe_sende", "abgabe_angefragt", "abgabe_unklar",
                                           "abgabe_fehler", "abgegeben", "abgabe_uebersprungen", "sende"}


# --- Abbrechen von Hand (Fenster, P7a) ------------------------------------------------

@pytest.mark.parametrize("phase", ["vorbereitet", "abgabe_sende", "abgabe_angefragt", "abgabe_unklar",
                                   "abgabe_fehler", "abgegeben", "abgabe_uebersprungen"])
def test_abbrechen_verwirft_vor_rolle_gesetzt_und_protokolliert(umgebung, phase):
    from master_schalter import protokoll
    umgebung.vorbereiten("v-1", phase=phase)
    umgebung.vorbereiten("v-2", phase=phase)

    erg = av.abbrechen("v-1")

    assert erg.phase == "verworfen" and erg.fehler == av.ABBRUCH_GRUND == "von Hand abgebrochen"
    assert av.finden("v-1").phase == "verworfen"
    assert av.finden("v-2").phase == phase                       # andere Vorgänge bleiben unberührt
    eintrag = protokoll.lesen()[-1]
    assert (eintrag["vorgang"], eintrag["thema"], eintrag["entscheidung"], eintrag["grund"]) == \
        ("v-1", THEMA, "verworfen", "von Hand abgebrochen")


def test_abbrechbare_phasen_sind_genau_die_blockierenden_vor_rolle_gesetzt():
    assert set(av.ABBRECHBAR) == set(av.WECHSEL_BLOCKIEREND) - {"sende"}
    assert not set(av.ABBRECHBAR) & set(av.UEBERHOLBAR)
    assert not set(av.ABBRECHBAR) & set(av.ENDGUELTIG)


@pytest.mark.parametrize("phase", ["rolle_gesetzt", "sende", "gesendet", "im_postfach", "im_chat", "fehler",
                                   "unklar", "bestaetigt", "verworfen"])
def test_abbrechen_ab_rolle_gesetzt_lehnt_ab_und_aendert_nichts(umgebung, phase):
    from master_schalter import protokoll
    umgebung.vorbereiten("v-1", phase=phase)
    vorher = av.datei().read_text(encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="nicht mehr möglich"):
        av.abbrechen("v-1")

    assert av.datei().read_text(encoding="utf-8") == vorher
    assert protokoll.lesen() == []


def test_abbrechen_unbekannt_und_ungueltige_kennung_ohne_echo(umgebung):
    with pytest.raises(av.AssistentFehler, match="Vorgang unbekannt"):
        av.abbrechen("v-9")
    with pytest.raises(av.AssistentFehler) as ausnahme:
        av.abbrechen("../PRIVAT_4711")
    assert "PRIVAT_4711" not in str(ausnahme.value) and "Vorgangskennung unzulässig" in str(ausnahme.value)


def test_abbrechen_ist_vergleich_und_setzen_gegen_einen_schnelleren_takt(umgebung, monkeypatch):
    """Ist der Vorgang beim Abbrechen schon weiter (anderer Takt gewann), ändert der Abbruch nichts."""
    umgebung.vorbereiten("v-1", phase="abgegeben")
    echt = av.phase_gewinnen

    def zu_spaet(vorgang_id, von, nach, *args, **felder):
        av.aktualisieren(vorgang_id, phase="rolle_gesetzt")      # der Takt war schneller
        return echt(vorgang_id, von, nach, *args, **felder)

    monkeypatch.setattr(av, "phase_gewinnen", zu_spaet)

    with pytest.raises(av.AssistentFehler, match="Phase rolle_gesetzt"):
        av.abbrechen("v-1")
    assert av.finden("v-1").phase == "rolle_gesetzt"


def test_abbrechen_bei_belegter_themensperre_meldet_ohne_aenderung(umgebung):
    from master_schalter import zustand
    umgebung.vorbereiten("v-1", phase="abgabe_angefragt")
    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        with pytest.raises(av.AssistentFehler, match="gleich erneut"):
            av.abbrechen("v-1")
    assert av.finden("v-1").phase == "abgabe_angefragt"


def test_abgebrochener_vorgang_wird_von_fortsetzen_nicht_mehr_angefasst(umgebung):
    from master_schalter import assistent
    umgebung.marke_setzen("claude 2026-10-20T10:00:00+00:00")
    umgebung.vorbereiten("v-1", phase="abgegeben")
    av.abbrechen("v-1")

    erg = assistent.fortsetzen("v-1", repo=umgebung.repo)

    assert erg.phase == "verworfen"
    assert umgebung.marke() == "claude 2026-10-20T10:00:00+00:00"   # Rolle und Marke nicht gesetzt
