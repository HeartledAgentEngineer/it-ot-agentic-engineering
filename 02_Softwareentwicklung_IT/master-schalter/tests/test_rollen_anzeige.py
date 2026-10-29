"""Tests der aufgelösten Rollen (Master, Prüfer, Ausführer mit Modell) – reine Funktionen, kein Dateizugriff.

Maßgeblich ist die Matrix `rollen.BESETZUNG`; kein Test setzt einen Modellnamen voraus, der dort nicht steht.
"""
from __future__ import annotations

import itertools
import re

import pytest

from master_schalter import arbeitsweise, kurz, modi, pruefer_wahl, rollen, rollen_anzeige
from master_schalter.rollen_anzeige import aufloesen

LAGEN = ("1", "2A", "2B", "3", None)
P = arbeitsweise.PROTOKOLL


def _profil(master="kontingent", worker="workflow", modell=None):
    return modi.Profil(master, worker, modell)


def _auf(profil=None, lage="1", besitzer="claude", wahl="automatisch", weise=P, pk="claude"):
    return aufloesen(profil or _profil(), lage, besitzer, wahl, weise, pk)


# --- Master -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lage, erwartet", [
    ("1", "Claude · Opus 5.5 (nach Kontingent)"),
    ("2A", "Codex · GPT-6 Sol (nach Kontingent)"),
    ("2B", "Claude · Opus 5.5 (nach Kontingent)"),
    ("3", "Hermes · DeepSeek V4.1 Flash (nach Kontingent)"),
    (None, "nach Kontingent · Lage ?"),
])
def test_master_nach_kontingent_ist_der_thinker_der_lage(lage, erwartet):
    besitzer = {"1": "claude", "2A": "codex", "2B": "claude", "3": "hermes", None: "claude"}[lage]
    master = _auf(lage=lage, besitzer=besitzer)[0]
    assert master == (erwartet if lage else erwartet + " · Besitz Claude")


@pytest.mark.parametrize("fest, lage, erwartet", [
    ("claude", "1", "Claude · Opus 5.5 (fest)"),
    ("claude", "2A", "Claude (fest)"),             # Thinker der Lage ist Codex: kein Modell für den festen Claude
    ("codex", "2A", "Codex · GPT-6 Sol (fest)"),
    ("codex", "1", "Codex (fest)"),
    ("hermes", "1", "Hermes · DeepSeek V4.1 Flash"),
    ("hermes", None, "Hermes · DeepSeek V4.1 Flash"),
    ("claude", None, "Claude (fest)"),
])
def test_fester_master_zeigt_sein_werkzeug(fest, lage, erwartet):
    assert _auf(_profil(fest), lage=lage, besitzer=fest)[0] == erwartet


@pytest.mark.parametrize("besitzer, zusatz", [
    ("hermes", " · Besitz Hermes"),
    ("reserviert", " · Besitz reserviert (Zwischenmarke)"),
    ("codex", " · Besitz Codex"),
    (None, " · Besitz unbekannt"),
    ("claude", ""),
])
def test_abweichender_besitz_steht_beim_master(besitzer, zusatz):
    assert _auf(lage="1", besitzer=besitzer)[0] == "Claude · Opus 5.5 (nach Kontingent)" + zusatz


def test_fester_master_mit_fremdem_besitz():
    assert _auf(_profil("claude"), lage="1", besitzer="codex")[0] == "Claude · Opus 5.5 (fest) · Besitz Codex"


# --- Ausführer ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lage, erwartet", [
    ("1", "Workflow → GPT-6 Luna / Claude Sonnet 5.5"),
    ("2A", "Workflow → GPT-6 Luna"),
    ("2B", "Workflow → Claude Sonnet 5.5 / DeepSeek V4.1 Flash"),
    ("3", "Workflow → DeepSeek V4.1 Flash"),
    (None, "Workflow → Lage ?"),
])
def test_workflow_zeigt_den_worker_der_lage(lage, erwartet):
    assert _auf(lage=lage)[2] == erwartet


@pytest.mark.parametrize("worker, modell, erwartet", [
    ("claude", None, "Claude · Standard"),
    ("codex", None, "Codex · Standard"),
    ("codex", "gpt-6-luna", "Codex · gpt-6-luna"),
    ("claude", "claude-sonnet-x", "Claude · claude-sonnet-x"),
    ("hermes", modi.HERMES_MODELL, "Hermes · DeepSeek V4.1 Flash"),
    ("hermes", None, "Hermes · DeepSeek V4.1 Flash"),
])
def test_ausfuehrer_zeigt_provider_und_profilmodell(worker, modell, erwartet):
    assert _auf(_profil(worker=worker, modell=modell))[2] == erwartet


def test_vibe_mit_standardmodell_nennt_die_regel_des_profils():
    text = _auf(_profil(worker="claude"), weise=arbeitsweise.VIBE)[2]
    assert text == "Claude · Standard (Vibe: Sonnet oder Haiku)"
    assert "Sonnet oder Haiku" in arbeitsweise.VIBE_REGEL
    assert _auf(_profil(worker="claude", modell="m1"), weise=arbeitsweise.VIBE)[2] == "Claude · m1"


def test_unbekannter_provider_ist_fragezeichen():
    assert _auf(modi.Profil("kontingent", "gpt", None))[2] == "?"


# --- Prüfer ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("pk, erwartet", [
    ("claude", "Codex · App-Standard"),
    ("hermes", "Codex · App-Standard"),
    ("codex", "Hermes · DeepSeek V4.1 Flash"),
])
def test_pruefer_regel_folgt_dem_besitz(pk, erwartet):
    assert _auf(pk=pk)[1] == erwartet


def test_vibe_pruefer_ist_die_kurzpruefung():
    assert _auf(weise=arbeitsweise.VIBE, wahl="hermes", pk=None)[1] == rollen_anzeige.VIBE_PRUEFER_TEXT
    assert rollen_anzeige.VIBE_PRUEFER_TEXT.startswith("Master-Kurzprüfung")
    assert kurz.VIBE_PRUEFER == "Prüfer " + rollen_anzeige.VIBE_PRUEFER_TEXT


@pytest.mark.parametrize("wahl", ["automatisch", "codex", "hermes", "?"])
def test_pruefer_bei_unklarem_besitz_ist_fragezeichen_nie_codex(wahl):
    """Datei fehlt, unlesbar, ungültig oder Zwischenmarke ⇒ `pk_master=None` ⇒ pruefkreis bricht ab."""
    for besitzer in (None, "claude", "reserviert"):
        text = _auf(besitzer=besitzer, wahl=wahl, pk=None)[1]
        assert text == rollen_anzeige.BESITZ_UNKLAR
        assert text.startswith("? (Besitz unklar") and "Codex" not in text and "Hermes" not in text


@pytest.mark.parametrize("pk, wahl, erwartet", [
    ("claude", "codex", "Codex · App-Standard (gewählt)"),
    ("claude", "hermes", "Hermes · DeepSeek V4.1 Flash (gewählt)"),
    ("codex", "hermes", "Hermes · DeepSeek V4.1 Flash (gewählt)"),
    ("codex", "codex", "Codex · App-Standard (gewählt) – gleiche Familie wie Master"),
    ("hermes", "hermes", "Hermes · DeepSeek V4.1 Flash (gewählt) – gleiche Familie wie Master"),
])
def test_gewaehlter_pruefer_gilt_auch_in_der_familie_des_masters(pk, wahl, erwartet):
    assert _auf(pk=pk, wahl=wahl)[1] == erwartet
    assert rollen_anzeige.gleiche_familie(pk, wahl, P) == (pk == wahl)


def test_kaputte_pruefer_datei_zeigt_fragezeichen_mit_der_regel():
    text = _auf(pk="claude", wahl="?")[1]
    assert text.startswith("? (pruefer.json ungültig") and "Codex · App-Standard" in text
    assert rollen_anzeige.pruefer_werkzeug("claude", "?", P) is None
    assert not rollen_anzeige.gleiche_familie("claude", "?", P)


def test_die_regel_allein_ergibt_nie_dieselbe_familie():
    for pk in ("claude", "codex", "hermes"):
        assert not rollen_anzeige.gleiche_familie(pk, "automatisch", P)
    assert not rollen_anzeige.gleiche_familie(None, "codex", P)
    assert not rollen_anzeige.gleiche_familie("codex", "codex", arbeitsweise.VIBE)


# --- keine erfundenen Namen -----------------------------------------------------------------------------------------

def _erlaubt(profil: modi.Profil) -> set[str]:
    namen = {"Standard", "App-Standard", "DeepSeek V4.1 Flash", "Lage ?", "nach Kontingent"}
    for b in rollen.BESETZUNG.values():
        for zelle in (b.thinker, b.reviewer, b.worker):
            for teil in rollen_anzeige.ohne_klammern(zelle).split(" / "):
                namen.add(teil)
                namen.add(re.sub(r"^Claude ", "", teil))
    if profil.modell:
        namen.add(profil.modell)
    return namen


def test_jeder_modellname_stammt_aus_matrix_profil_oder_konstante():
    profile = [_profil(m, w, mod) for m, w, mod in itertools.product(
        ("kontingent", "claude", "codex", "hermes"), ("workflow", "claude", "codex", "hermes"), (None, "kennung-x"))
        if not (w == "workflow" and mod) and not (w == "hermes" and mod)]
    for profil, lage in itertools.product(profile, LAGEN):
        erlaubt = _erlaubt(profil)
        master, pruefer, ausfuehrer = _auf(profil, lage=lage, besitzer="claude", wahl="codex", pk="claude")
        for text in (master, pruefer, ausfuehrer):
            sauber = re.sub(r"\s*\([^)]*\)", "", text)                       # Klammerzusätze sind feste Wörter
            for teil in re.split(r" · | → | – ", sauber):
                teil = teil.strip()
                if not teil or teil in ("Claude", "Codex", "Hermes", "Workflow", "?", "gleiche Familie wie Master"):
                    continue
                for stuecke in teil.split(" / "):
                    assert stuecke.strip() in erlaubt or stuecke.strip().startswith("Besitz"), (text, stuecke)
