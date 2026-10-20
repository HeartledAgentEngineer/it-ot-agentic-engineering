"""Tests: Vorname / Nachname / Spitznamen je Person (20.10.2026).

Wunsch Sebastian (20.10.2026): Personenbuch mit Vorname / Nachname /
Spitznamen. Der NAME bleibt die Kennung; fehlende Felder werden beim LESEN
abgeleitet (``gruppen_quiz.name_zerlegen``) und von Hand gesetzte Felder im
Profil haben Vorrang. Diese Tests halten die Regeln und die Verdrahtung fest.

Offline, ERFUNDENE Namen in ``tmp_path`` (``GRUPPEN_QUIZ_BASIS``) — keine echten
Namen, keine Gesichtsvektoren, keine Bilder, kein Netz.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_name_zerlegen.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402

GRUPPEN = [
    {"kennung": "Person_1001", "groesse": 120, "bilder": 90, "videos": 3,
     "von": "2015-01-01", "bis": "2025-09-01", "zwilling_kandidaten": [], "beispiele": []},
    {"kennung": "Person_1003", "groesse": 7, "bilder": 7, "videos": 0,
     "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []},
]
BESTAETIGT = {"bestaetigt": {"Person_1001": "Anna Beispiel", "Person_1003": "Kollege Beispiel"}}
PROFILE = {"profile": {
    # Von Hand gesetzt: alle drei Felder, dazu unbrauchbarer Inhalt in der Liste.
    "Anna Beispiel": {"beziehung": "Beispiel-Beziehung", "notizen": [], "kontakt": None,
                      "vorname": "Anni", "nachname": "Beispiel",
                      "spitznamen": ["Beispielchen", "", 7, None]},
    # Ohne Namensfelder: hier muss abgeleitet werden.
    "Kollege Beispiel": {"beziehung": "", "notizen": [], "kontakt": None},
}}


def _schreibe(pfad, inhalt):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(inhalt, list):
        pfad.write_text("\n".join(json.dumps(z) for z in inhalt) + "\n", encoding="utf-8")
    else:
        pfad.write_text(json.dumps(inhalt), encoding="utf-8")


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    _schreibe(ordner / gq.BEISPIELE_DATEINAME,
              {"stand": "2026-10-20T00:00:00", "verfahren": "mittelpunkt", "gruppen": GRUPPEN})
    _schreibe(tmp_path / gq.BESTAETIGT_DATEINAME, BESTAETIGT)
    _schreibe(tmp_path / gq.PROFILE_DATEINAME, PROFILE)
    _schreibe(tmp_path / gq.VORGABEN_DATEINAME, {"gleich": [], "verschieden": []})
    yield tmp_path
    gq._CACHE.clear()


# ── Die Regeln der reinen Funktion (erfundene Namen) ────────────────────────

def test_zwei_woerter_letztes_wort_ist_der_nachname():
    assert gq.name_zerlegen("Anna Beispiel") == {"vorname": "Anna", "nachname": "Beispiel"}


def test_einzelnes_wort_ist_der_vorname():
    assert gq.name_zerlegen("Test2") == {"vorname": "Test2", "nachname": ""}


def test_klammerzusatz_ist_kein_nachname():
    r = gq.name_zerlegen("Oma (Test)")
    assert r["nachname"] == ""
    assert r["vorname"] == "Oma (Test)"       # der Name bleibt vollstaendig erhalten


def test_rollenwort_ohne_familie_ergibt_keinen_nachnamen():
    assert gq.name_zerlegen("Kollege Beispiel")["nachname"] == ""


def test_namenszusatz_gehoert_zum_nachnamen():
    assert gq.name_zerlegen("Jan van den Berg") == {"vorname": "Jan",
                                                    "nachname": "van den Berg"}
    assert gq.name_zerlegen("Anna de la Cruz") == {"vorname": "Anna",
                                                   "nachname": "de la Cruz"}


def test_namenszusatz_am_ende_ergibt_keinen_nachnamen():
    assert gq.name_zerlegen("Jan van")["nachname"] == ""


def test_zusatz_allein_ist_ein_nachname():
    assert gq.name_zerlegen("van den Berg") == {"vorname": "",
                                                "nachname": "van den Berg"}


def test_kuerzel_am_ende_ist_der_nachname():
    assert gq.name_zerlegen("Anna M.") == {"vorname": "Anna", "nachname": "M."}


def test_kuerzel_am_anfang_ist_ein_vorname_kuerzel():
    assert gq.name_zerlegen("M. Beispiel") == {"vorname": "M.", "nachname": "Beispiel"}


def test_familiensignal_macht_ein_wort_zum_nachnamen():
    """Dasselbe Wort steht bei einer anderen Person am Ende -> Nachname."""
    r = gq.name_zerlegen("Meier", alle_namen=["Meier", "Anna Meier"])
    assert r == {"vorname": "", "nachname": "Meier"}


def test_familiensignal_schlaegt_das_rollenwort():
    """'Kollege Beispiel' + 'Anna Beispiel': das letzte Wort ist ein Nachname."""
    r = gq.name_zerlegen("Kollege Beispiel", alle_namen=["Anna Beispiel"])
    assert r["nachname"] == "Beispiel"


def test_familiensignal_schlaegt_die_ziffernregel():
    r = gq.name_zerlegen("Anna2 Beispiel2", alle_namen=["Anna Beispiel"])
    assert r["nachname"] == "Beispiel2"
    # ohne Familienbezug bleibt die Ziffer ein Zusatz (kein Nachname)
    assert gq.name_zerlegen("Anna2 Beispiel2")["nachname"] == ""


def test_name_stuetzt_sich_nicht_selbst():
    """Ein Einwort-Name darf sich nicht aus dem eigenen Vorkommen ableiten."""
    assert gq.name_zerlegen("Meier", alle_namen=["Meier"])["nachname"] == ""


def test_upper_umlaut_und_klein_egal():
    assert gq.name_zerlegen("  anna   beispiel  ") == {"vorname": "anna", "nachname": "beispiel"}
    assert gq.name_zerlegen("Änne Beispüll") == {"vorname": "Änne", "nachname": "Beispüll"}


@pytest.mark.parametrize("kaputt", [None, "", "   ", 5, [], {}, "x" * 200, "\x07"])
def test_kaputte_eingaben_werfen_nie(kaputt):
    r = gq.name_zerlegen(kaputt)
    assert set(r) == {"vorname", "nachname"}
    assert r["vorname"] == "" and r["nachname"] == ""


def test_familienwoerter_kennt_nur_mehrteilige_namen():
    menge = gq.familienwoerter(["Anna Beispiel", "Meier", 7, "Kollege Beispiel"], ohne="Anna Beispiel")
    assert menge == {"beispiel"}


# ── Verdrahtung: Profil und Personenliste ──────────────────────────────────

def test_profil_liefert_abgeleitete_felder(basis):
    r = gq.profil("Kollege Beispiel")
    assert r["ok"] is True
    assert r["vorname"] == "Kollege" and r["nachname"] == "Beispiel"
    assert r["spitznamen"] == []
    assert r["namensfelder_quelle"] == "abgeleitet"

def test_von_hand_gesetzte_felder_haben_vorrang(basis):
    r = gq.profil("Anna Beispiel")
    assert r["vorname"] == "Anni"              # nicht "Anna" (Profil gewinnt)
    assert r["nachname"] == "Beispiel"
    assert r["spitznamen"] == ["Beispielchen"]  # leere und unbrauchbare Werte fallen weg
    assert r["namensfelder_quelle"] == "profil"


def test_spitznamen_sind_begrenzt(basis):
    from app.services import gruppen_quiz
    eintrag = {"spitznamen": [f"Spitz{i}" for i in range(50)]}
    felder = gruppen_quiz._namensfelder(eintrag, "Anna Beispiel")
    assert len(felder["spitznamen"]) == gruppen_quiz.SPITZNAMEN_MAX


def test_personenliste_traegt_die_namensfelder(basis):
    r = gq.personen()
    assert r["ok"] is True
    nach_name = {p["name"]: p for p in r["personen"]}
    assert nach_name["Anna Beispiel"]["vorname"] == "Anni"
    assert nach_name["Anna Beispiel"]["spitznamen"] == ["Beispielchen"]
    assert nach_name["Kollege Beispiel"]["nachname"] == "Beispiel"
    assert nach_name["Kollege Beispiel"]["namensfelder_quelle"] == "abgeleitet"


def test_das_profil_wird_beim_lesen_nicht_veraendert(basis):
    """Ableitung ist nur Anzeige: die Profildatei bleibt Byte fuer Byte gleich."""
    pfad = basis / gq.PROFILE_DATEINAME
    vorher = pfad.read_bytes()
    gq.profil("Kollege Beispiel")
    gq.personen()
    assert pfad.read_bytes() == vorher
