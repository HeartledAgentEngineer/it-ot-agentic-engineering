"""Tests für die Gesichter-Chat-Integration (reaktiv merken + proaktiver Abgleich).

Sichert:
- `_gesichter_merke`: Nennt der Nutzer beim Betrachten eines Bildes eine
  Person ('das ist Pedi'), wird sie deterministisch in den Katalog übernommen
  und ein Hinweis an die user_message gehängt.
- Ohne aktives Bild (bild_aktiv=False) wird NICHTS gemerkt.
- Unpassende Phrasen ('das ist die beste Idee') ohne Personennamen lösen
  nichts aus.
"""

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _gesichter_merke  # noqa: E402
from app.services import gesichter_service  # noqa: E402


def _katalog_leeren():
    with open(gesichter_service.KATALOG_DATEI, "w", encoding="utf-8") as f:
        json.dump({"personen": []}, f)


def test_merke_person_mit_bild():
    _katalog_leeren()
    hinweis = _gesichter_merke("das ist Pedi", bild_aktiv=True)
    assert "Pedi" in hinweis
    assert gesichter_service.person_finden("Pedi") is not None


def test_merke_mit_rolle():
    _katalog_leeren()
    hinweis = _gesichter_merke("das ist meine Oma Helga", bild_aktiv=True)
    assert "Helga" in hinweis
    p = gesichter_service.person_finden("Helga")
    assert p is not None
    assert p["rolle"] == "Oma"


def test_merke_mit_referenzbild():
    """Beim reaktiven Merken wird das betrachtete Bild als Referenz-Miniatur
    an die Person gekoppelt (Bild-zu-Bild-Abgleich statt nur Namens-Kontext).
    Das beantwortet das Zwillings-Szenario: eine Person braucht ein echt
    vergleichbares Referenzbild."""
    _katalog_leeren()
    test_data_url = "data:image/jpeg;base64,AAAA"
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
    hinweis = _gesichter_merke("das ist Pedi", bild_aktiv=False)
    assert hinweis == ""
    assert gesichter_service.person_finden("Pedi") is None


def test_kein_merken_bei_phrase_ohne_person():
    _katalog_leeren()
    hinweis = _gesichter_merke("das ist die beste Idee", bild_aktiv=True)
    assert hinweis == ""
    assert gesichter_service.liste_personen() == []


def test_proaktiver_kontext_wuerde_gemeldet():
    """Der Katalog-Kontext ist an den Chat angehängt (via katalog_kontext)."""
    _katalog_leeren()
    gesichter_service.person_speichern("Pedi", "Mutter")
    kontext = gesichter_service.katalog_kontext()
    assert "Pedi" in kontext
    assert "Mutter" in kontext