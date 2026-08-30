"""Tests für die Gesichter-Chat-Integration (reaktiv merken + proaktiver Abgleich).

Sichert:
- `_gesichter_merke`: Nennt der Nutzer beim Betrachten eines Bildes eine
  Person ('das ist Pedi'), wird sie in den Katalog übernommen und ein Hinweis
  an die user_message gehängt.
- Mehrere Personen auf EINEM Bild ('das bin ich und das ist Julian').
- 'das bin ich' → Nutzer-Name.
- Ohne aktives Bild (bild_aktiv=False) wird NICHTS gemerkt.
- Unpassende Phrasen ('das ist die beste Idee') ohne Personennamen lösen
  nichts aus.

Die LLM-Erkennung `extrahiere_gesichts_anlernen` wird gemockt, damit die
Tests deterministisch und ohne echte API-Calls laufen.
"""

import json
import os
import sys
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _gesichter_merke  # noqa: E402
from app.services import gesichter_service  # noqa: E402


def _katalog_leeren():
    with open(gesichter_service.KATALOG_DATEI, "w", encoding="utf-8") as f:
        json.dump({"personen": []}, f)


def _mock_llm_erkannt(personen, wunsch=True):
    """Mockt die LLM-Erkennung, damit Tests ohne API-Calls auskommen."""
    return mock.patch(
        "app.router.chat.llm_service.extrahiere_gesichts_anlernen",
        return_value={"personen": personen, "ist_anlern_wunsch": wunsch},
    )


def test_merke_person_mit_bild():
    _katalog_leeren()
    with _mock_llm_erkannt([{"name": "Pedi", "rolle": "", "ist_nutzer": False}]):
        hinweis = _gesichter_merke("das ist Pedi", bild_aktiv=True)
    assert "Pedi" in hinweis
    assert gesichter_service.person_finden("Pedi") is not None


def test_merke_mit_rolle():
    _katalog_leeren()
    with _mock_llm_erkannt([{"name": "Helga", "rolle": "Oma", "ist_nutzer": False}]):
        hinweis = _gesichter_merke("das ist meine Oma Helga", bild_aktiv=True)
    assert "Helga" in hinweis
    p = gesichter_service.person_finden("Helga")
    assert p is not None
    assert p["rolle"] == "Oma"


def test_merke_zwei_personen_gruppenbild():
    """Zwillings-Szenario: 'das bin ich und das ist Julian' → beide lernen."""
    _katalog_leeren()
    personen = [
        {"name": "Sebastian", "rolle": "", "ist_nutzer": True},
        {"name": "Julian", "rolle": "Zwillingsbruder", "ist_nutzer": False},
    ]
    with _mock_llm_erkannt(personen):
        hinweis = _gesichter_merke(
            "das bin ich und das ist Julian, mein Zwillingsbruder",
            bild_aktiv=True,
        )
    assert "Sebastian" in hinweis and "Julian" in hinweis
    assert gesichter_service.person_finden("Sebastian") is not None
    assert gesichter_service.person_finden("Julian") is not None


def test_merke_mit_referenzbild():
    """Beim reaktiven Merken wird das betrachtete Bild als Referenz-Miniatur
    an die Person gekoppelt (Bild-zu-Bild-Abgleich statt nur Namens-Kontext)."""
    _katalog_leeren()
    test_data_url = "data:image/jpeg;base64,AAAA"
    with _mock_llm_erkannt([{"name": "Otto", "rolle": "", "ist_nutzer": False}]):
        hinweis = _gesichter_merke(
            "das ist mein Zwillingsbruder Otto", bild_aktiv=True,
            referenz_bild=test_data_url,
        )
    assert "Otto" in hinweis
    p = gesichter_service.person_finden("Otto")
    assert p is not None
    assert p.get("referenz_bild_miniatur") == test_data_url, "Referenzbild fehlt"


def test_kein_merken_ohne_bild():
    _katalog_leeren()
    with _mock_llm_erkannt([{"name": "Pedi", "rolle": "", "ist_nutzer": False}]):
        hinweis = _gesichter_merke("das ist Pedi", bild_aktiv=False)
    assert hinweis == ""
    assert gesichter_service.person_finden("Pedi") is None


def test_kein_merken_bei_phrase_ohne_person():
    _katalog_leeren()
    with _mock_llm_erkannt([]):
        hinweis = _gesichter_merke("das ist die beste Idee", bild_aktiv=True)
    assert hinweis == ""
    assert gesichter_service.liste_personen() == []


def test_kein_merken_wenn_llm_nein_sagt():
    """LLM erkennt KEINEN Anlern-Wunsch → nichts merken (Normalfrage)."""
    _katalog_leeren()
    with _mock_llm_erkannt([], wunsch=False):
        hinweis = _gesichter_merke("was siehst du auf dem bild", bild_aktiv=True)
    assert hinweis == ""
    assert gesichter_service.liste_personen() == []


def test_proaktiver_kontext_wuerde_gemeldet():
    """Der Katalog-Kontext ist an den Chat angehängt (via katalog_kontext)."""
    _katalog_leeren()
    gesichter_service.person_speichern("Pedi", "Mutter")
    kontext = gesichter_service.katalog_kontext()
    assert "Pedi" in kontext
    assert "Mutter" in kontext