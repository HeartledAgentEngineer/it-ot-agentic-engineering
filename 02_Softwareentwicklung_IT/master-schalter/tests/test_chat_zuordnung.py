"""Tests für Projekte, Zuordnung und Vorschläge – nur Attrappen unter `tmp_path`."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import chat_register, chat_zuordnung, paare
from master_schalter.chat_register import Chat
from master_schalter.chat_zuordnung import Projekt, ZuordnungFehler

UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
JETZT = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


def chat(werkzeug="claude", kennung="abc", titel="", ordner="") -> Chat:
    return Chat(werkzeug, kennung, titel, ordner, JETZT, "claude-desktop")


# --- Projekte ----------------------------------------------------------------------------

def test_projekte_fehlende_datei_ist_leere_liste():
    assert chat_zuordnung.projekte_lesen() == []


def test_projekt_setzen_und_lesen_ersetzt_dasselbe_thema():
    chat_zuordnung.projekt_setzen("typefree", ["C:/a"], ["tippen"])
    chat_zuordnung.projekt_setzen("engineering", ["C:/b"], [])
    chat_zuordnung.projekt_setzen("typefree", ["C:/neu"], ["diktat"])
    assert chat_zuordnung.projekte_lesen() == [
        Projekt("engineering", ("C:/b",), ()), Projekt("typefree", ("C:/neu",), ("diktat",))]


def test_projekt_setzen_prueft_eingaben():
    for thema in ("Gross", "mit leerzeichen", "", "ok\n"):
        with pytest.raises(ZuordnungFehler):
            chat_zuordnung.projekt_setzen(thema, [], [])
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.projekt_setzen("ok", "C:/ein-text", [])
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.projekt_setzen("ok", [""], [])
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.projekt_setzen("ok", [], [5])
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.projekt_setzen("ok", [], ["x" * 81])
    assert chat_zuordnung.projekte_lesen() == []


def test_projekte_kaputte_datei_und_kaputte_eintraege(daten):
    daten.mkdir()
    (daten / "projekte.json").write_text("{kaputt", encoding="utf-8")
    assert chat_zuordnung.projekte_lesen() == []
    (daten / "projekte.json").write_text(json.dumps([
        {"thema": "gut", "ordner": ["C:/a"], "stichwoerter": []}, {"thema": "BÖSE"}, 5,
        {"thema": "kaputt", "ordner": "kein-array"}]), encoding="utf-8")
    assert [p.thema for p in chat_zuordnung.projekte_lesen()] == ["gut"]


# --- Rangfolge der Vorschläge ----------------------------------------------------------------

def test_vorschlag_unbekannt_ohne_alles():
    assert chat_zuordnung.vorschlag(chat(), [], [], {}) == (None, "unbekannt")


def test_rangfolge_bestaetigt_vor_paar_vor_ordner_vor_stichwort():
    projekte = [Projekt("ordnerthema", ("C:/arbeit",), ()), Projekt("wortthema", (), ("roboter",))]
    paar = paare.Paar("paarthema", UUID_A, paare.laufend_bilden("paarthema"), True)
    codex = chat("codex", UUID_A, "Roboter bauen", "C:/arbeit/x")
    claude = chat("claude", UUID_B, "Roboter bauen", "C:/arbeit/x")

    assert chat_zuordnung.vorschlag(claude, projekte, [paar], {f"claude:{UUID_B}": "bestaetigtes-thema"}) == (
        "bestaetigtes-thema", "bestätigt")
    assert chat_zuordnung.vorschlag(claude, projekte, [paar], {}) == ("ordnerthema", "Ordner")
    assert chat_zuordnung.vorschlag(codex, projekte, [paar], {}) == ("paarthema", "Paar")
    assert chat_zuordnung.vorschlag(codex, projekte, [], {}) == ("ordnerthema", "Ordner")
    ohne_ordner = chat("codex", UUID_A, "Roboter bauen", "C:/anderswo")
    assert chat_zuordnung.vorschlag(ohne_ordner, projekte, [], {}) == ("wortthema", "Stichwort")


def test_paar_gilt_nur_fuer_codex_chats():
    paar = paare.Paar("paarthema", UUID_A, paare.laufend_bilden("paarthema"), False)
    assert chat_zuordnung.vorschlag(chat("claude", UUID_A), [], [paar], {}) == (None, "unbekannt")
    assert chat_zuordnung.vorschlag(chat("codex", UUID_A.upper()), [], [paar], {}) == ("paarthema", "Paar")


def test_bestaetigung_gilt_nur_fuer_dasselbe_werkzeug():
    zuordnung = {f"claude:{UUID_A}": "t"}
    assert chat_zuordnung.vorschlag(chat("claude", UUID_A), [], [], zuordnung) == ("t", "bestätigt")
    assert chat_zuordnung.vorschlag(chat("codex", UUID_A), [], [], zuordnung) == (None, "unbekannt")


def test_ordnerpraefix_nur_ganze_segmente():
    projekte = [Projekt("t", ("C:/a/b",), ())]
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/bc"), projekte, [], {}) == (None, "unbekannt")
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/b"), projekte, [], {}) == ("t", "Ordner")
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/b/c/d"), projekte, [], {}) == ("t", "Ordner")
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a"), projekte, [], {}) == (None, "unbekannt")


def test_ordnerpraefix_ignoriert_gross_klein_und_pfadtrenner():
    projekte = [Projekt("t", ("c:\\Users\\SEBAS\\Arbeit\\",), ())]
    assert chat_zuordnung.vorschlag(chat(ordner="C:/users/sebas/arbeit/projekt"), projekte, [], {}) == ("t", "Ordner")


def test_laengstes_praefix_gewinnt():
    projekte = [Projekt("breit", ("C:/a",), ()), Projekt("eng", ("C:/a/b",), ())]
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/b/c"), projekte, [], {}) == ("eng", "Ordner")
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/x"), projekte, [], {}) == ("breit", "Ordner")


def test_gleich_langes_praefix_zweier_themen_ist_mehrdeutig():
    projekte = [Projekt("eins", ("C:/a",), ()), Projekt("zwei", ("c:\\A",), ())]
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/x"), projekte, [], {}) == (None, "unbekannt")


def test_leerer_ordner_passt_nie():
    assert chat_zuordnung.vorschlag(chat(ordner=""), [Projekt("t", ("/",), ())], [], {}) == (None, "unbekannt")


def test_stichwort_ganzes_wort_ohne_gross_klein():
    projekte = [Projekt("t", (), ("tippen",))]
    assert chat_zuordnung.vorschlag(chat(titel="Das TIPPEN lernen"), projekte, [], {}) == ("t", "Stichwort")
    assert chat_zuordnung.vorschlag(chat(titel="Abtippen"), projekte, [], {}) == (None, "unbekannt")
    assert chat_zuordnung.vorschlag(chat(titel="tippen-test"), projekte, [], {}) == ("t", "Stichwort")


def test_stichwort_mehrdeutig_ist_none():
    projekte = [Projekt("eins", (), ("fenster",)), Projekt("zwei", (), ("fenster", "tabelle"))]
    assert chat_zuordnung.vorschlag(chat(titel="fenster"), projekte, [], {}) == (None, "unbekannt")
    assert chat_zuordnung.vorschlag(chat(titel="tabelle"), projekte, [], {}) == ("zwei", "Stichwort")
    # zwei Stichwörter desselben Projekts sind kein Konflikt
    eins = [Projekt("t", (), ("alpha", "beta"))]
    assert chat_zuordnung.vorschlag(chat(titel="alpha und beta"), eins, [], {}) == ("t", "Stichwort")


def test_stichwort_mit_sonderzeichen_wird_nicht_als_muster_gelesen():
    projekte = [Projekt("t", (), ("c++",))]
    assert chat_zuordnung.vorschlag(chat(titel="viel c++ heute"), projekte, [], {}) == ("t", "Stichwort")
    assert chat_zuordnung.vorschlag(chat(titel="cccc"), projekte, [], {}) == (None, "unbekannt")


def test_vorschlag_liest_dateien_wenn_nichts_uebergeben_wird():
    chat_zuordnung.projekt_setzen("t", ["C:/a"], [])
    assert chat_zuordnung.vorschlag(chat(ordner="C:/a/b")) == ("t", "Ordner")


# --- Bestätigen / Aufheben ------------------------------------------------------------------------

def test_bestaetigen_schreibt_und_aufheben_entfernt(daten):
    assert chat_zuordnung.bestaetigen("claude", "sitzung-1", "engineering") == "claude:sitzung-1"
    assert json.loads((daten / "zuordnung.json").read_text(encoding="utf-8")) == {"claude:sitzung-1": "engineering"}
    assert chat_zuordnung.vorschlag(chat("claude", "sitzung-1"), [], [], None) == ("engineering", "bestätigt")
    assert chat_zuordnung.aufheben("claude", "sitzung-1") is True
    assert chat_zuordnung.aufheben("claude", "sitzung-1") is False
    assert chat_zuordnung.zuordnung_lesen() == {}
    assert not list(daten.glob("*.tmp"))


def test_bestaetigen_ueberschreibt_und_erhaelt_andere(daten):
    chat_zuordnung.bestaetigen("claude", "a", "eins")
    chat_zuordnung.bestaetigen("hermes", "b", "zwei")
    chat_zuordnung.bestaetigen("claude", "a", "drei")
    assert chat_zuordnung.zuordnung_lesen() == {"claude:a": "drei", "hermes:b": "zwei"}


def test_bestaetigen_claude_oder_hermes_beruehrt_keine_paare():
    chat_zuordnung.bestaetigen("claude", UUID_A, "engineering")
    chat_zuordnung.bestaetigen("hermes", UUID_B, "engineering")
    assert paare.lesen() == []


def test_codex_bestaetigung_ersetzt_das_paar_und_erhaelt_aktiv():
    paare.setzen("engineering", UUID_A, paare.laufend_bilden("engineering"), aktiv=True)
    chat_zuordnung.bestaetigen("codex", UUID_B, "engineering")
    (paar,) = paare.lesen()
    assert (paar.thema, paar.codex_thread, paar.laufend, paar.aktiv) == (
        "engineering", UUID_B, paare.laufend_bilden("engineering"), True)
    assert chat_zuordnung.zuordnung_lesen() == {}               # für Codex ist das Paar die Bestätigung


def test_alter_codex_eintrag_in_der_zuordnung_wird_ignoriert():
    paar = paare.Paar("paarthema", UUID_A, paare.laufend_bilden("paarthema"), True)
    veraltet = {f"codex:{UUID_A}": "altes-thema"}
    assert chat_zuordnung.vorschlag(chat("codex", UUID_A), [], [paar], veraltet) == ("paarthema", "Paar")
    assert chat_zuordnung.vorschlag(chat("codex", UUID_B), [], [paar], {f"codex:{UUID_B}": "x"}) == (
        None, "unbekannt")


def test_codex_bestaetigung_legt_neues_paar_inaktiv_an():
    chat_zuordnung.bestaetigen("codex", UUID_A, "neu")
    (paar,) = paare.lesen()
    assert (paar.thema, paar.codex_thread, paar.aktiv) == ("neu", UUID_A, False)


def test_codex_bestaetigung_setzt_das_paar_unter_der_sperre(monkeypatch):
    from master_schalter import zustand
    sperren: list[int] = []
    echt = zustand.sperre

    from contextlib import contextmanager

    @contextmanager
    def zaehlend(*args, **kwargs):
        sperren.append(1)
        with echt(*args, **kwargs):
            yield
        sperren.pop()

    monkeypatch.setattr(zustand, "sperre", zaehlend)
    tiefen: list[int] = []
    echt_setzen = paare.setzen
    monkeypatch.setattr(paare, "setzen", lambda *a, **k: (tiefen.append(len(sperren)), echt_setzen(*a, **k))[1])
    chat_zuordnung.bestaetigen("codex", UUID_A, "engineering")
    assert tiefen == [1]


def test_codex_bestaetigung_schreibt_nichts_wenn_das_paar_scheitert(monkeypatch):
    def scheitert(*args, **kwargs):
        raise paare.PaarFehler("Attrappe")

    monkeypatch.setattr(paare, "setzen", scheitert)
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.bestaetigen("codex", UUID_A, "engineering")
    assert chat_zuordnung.zuordnung_lesen() == {}


def test_codex_bestaetigung_umgestellt_bleibt_stimmig(monkeypatch):
    """Chat A für `alt`, dann B für `alt`, dann A für `neu` – das Paar allein entscheidet, nichts widerspricht."""
    def nie(inhalt):
        raise AssertionError("Codex-Bestätigung darf zuordnung.json nicht schreiben")

    monkeypatch.setattr(chat_zuordnung, "_zuordnung_schreiben", nie)
    chat_zuordnung.bestaetigen("codex", UUID_A, "alt")
    chat_zuordnung.bestaetigen("codex", UUID_B, "alt")
    chat_zuordnung.bestaetigen("codex", UUID_A, "neu")
    assert {p.thema: p.codex_thread for p in paare.lesen()} == {"alt": UUID_B, "neu": UUID_A}
    assert chat_zuordnung.vorschlag(chat("codex", UUID_A)) == ("neu", "Paar")
    assert chat_zuordnung.vorschlag(chat("codex", UUID_B)) == ("alt", "Paar")


def test_codex_kennung_eines_fremden_paares_wird_vor_dem_schreiben_abgelehnt():
    paare.setzen("anderes", UUID_A, paare.laufend_bilden("anderes"), aktiv=True)
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.bestaetigen("codex", UUID_A, "engineering")
    assert chat_zuordnung.zuordnung_lesen() == {}
    assert [p.thema for p in paare.lesen()] == ["anderes"]


def test_codex_kennung_muss_uuid_sein_fuer_ein_paar():
    with pytest.raises(ZuordnungFehler):
        chat_zuordnung.bestaetigen("codex", "keine-uuid", "engineering")
    assert chat_zuordnung.zuordnung_lesen() == {}


def test_bestaetigen_ungueltige_eingaben(daten):
    for werkzeug, kennung, thema in [("gpt", "a", "t"), ("claude", "", "t"), ("claude", "a/b", "t"),
                                     ("claude", "a" * 81, "t"), ("claude", "a\n", "t"), ("claude", None, "t"),
                                     ("claude", "a", "GROSS"), ("claude", "a", ""), ("claude", "a", "x\n")]:
        with pytest.raises(ZuordnungFehler):
            chat_zuordnung.bestaetigen(werkzeug, kennung, thema)  # type: ignore[arg-type]
    for werkzeug, kennung in [("gpt", "a"), ("claude", "../x")]:
        with pytest.raises(ZuordnungFehler):
            chat_zuordnung.aufheben(werkzeug, kennung)
    assert not (daten / "zuordnung.json").exists()


def test_zuordnung_kaputte_datei_und_kaputte_eintraege(daten):
    daten.mkdir()
    (daten / "zuordnung.json").write_text("[1]", encoding="utf-8")
    assert chat_zuordnung.zuordnung_lesen() == {}
    (daten / "zuordnung.json").write_text(json.dumps(
        {"claude:gut": "t", "gpt:x": "t", "claude:y": "GROSS", "ohne-doppelpunkt": "t"}), encoding="utf-8")
    assert chat_zuordnung.zuordnung_lesen() == {"claude:gut": "t"}


# --- Übersicht -----------------------------------------------------------------------------------------

def test_uebersicht_verbindet_register_und_vorschlaege(tmp_path, monkeypatch):
    wurzel = tmp_path / "desktop"
    ordner = wurzel / "konto" / "claude-code-sessions"
    ordner.mkdir(parents=True)
    zeit = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000)
    (ordner / "local_a.json").write_text(json.dumps(
        {"cliSessionId": "sitzung-a", "title": "Etwas", "cwd": "C:/arbeit/x", "lastActivityAt": zeit}),
        encoding="utf-8")
    (ordner / "local_b.json").write_text(json.dumps(
        {"cliSessionId": "sitzung-b", "title": "Anderes", "cwd": "D:/sonst", "lastActivityAt": zeit - 1000}),
        encoding="utf-8")
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_DESKTOP", str(wurzel))
    chat_zuordnung.projekt_setzen("arbeit", ["C:/arbeit"], [])
    zeilen = chat_zuordnung.uebersicht()
    assert [(c.kennung, thema, grund) for c, thema, grund in zeilen] == [
        ("sitzung-a", "arbeit", "Ordner"), ("sitzung-b", None, "unbekannt")]
    ergebnis, _ = chat_zuordnung.uebersicht_mit_quellen()
    assert isinstance(ergebnis, chat_register.Ergebnis)
