"""Tests: Die Personen-Werkzeuge des Chats lesen die QUIZ-Quelle (10.10.2026).

Befund: Der Chat fand Personen nicht, weil ``personen_liste`` und Co. auf dem
alten Gesichtskatalog (``gesichter_katalog.json``) bauten, das Quiz aber eine
ganz andere Sammlung führt (``personen_bestaetigt.json`` /
``personen_profile.json``). Diese Tests halten die Verdrahtung fest: die
Werkzeug-Ausgabe muss den Inhalt der QUIZ-Dateien widerspiegeln.

Offline, erfundene Daten in ``tmp_path`` (``GRUPPEN_QUIZ_BASIS``) — keine echten
Namen, keine Gesichtsvektoren, keine Bilder.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_werkzeuge_quiz.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402
from app.services import werkzeuge as wz  # noqa: E402

GRUPPEN = [
    {"kennung": "Person_1001", "groesse": 120, "bilder": 90, "videos": 3,
     "von": "2015-01-01", "bis": "2025-09-01", "zwilling_kandidaten": [], "beispiele": []},
    {"kennung": "Person_1003", "groesse": 7, "bilder": 7, "videos": 0,
     "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []},
]
BESTAETIGT = {"bestaetigt": {"Person_1001": "Testperson A", "Person_1003": "Testperson B"}}
PROFILE = {"profile": {
    "Testperson A": {"beziehung": "Beispiel-Beziehung", "notizen": [
        {"id": "n1", "zeit": "2026-10-01T00:00:00", "text": "Mag Beispielhaftes", "quelle": "profil"},
        {"id": "n2", "zeit": "2026-10-01T00:00:00", "text": "zurueckgenommen", "zurueckgenommen": True},
    ], "kontakt": {"id": "k1", "name": "Testperson A", "geburtstag": "1990-01-02"}},
    "Testperson B": {"beziehung": "", "notizen": [], "kontakt": None},
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
    _schreibe(ordner / gq.BEISPIELE_DATEINAME, {"stand": "2026-10-10T00:00:00",
                                                "verfahren": "mittelpunkt", "gruppen": GRUPPEN})
    _schreibe(tmp_path / gq.BESTAETIGT_DATEINAME, BESTAETIGT)
    _schreibe(tmp_path / gq.PROFILE_DATEINAME, PROFILE)
    _schreibe(tmp_path / gq.VORGABEN_DATEINAME, {"gleich": [], "verschieden": []})
    yield tmp_path
    gq._CACHE.clear()


def _liste(**args):
    return wz.REGISTER["personen_liste"].ausfuehren(args)


def _auskunft(**args):
    return wz.REGISTER["person_auskunft"].ausfuehren(args)


# ── Verdrahtung gegen die Quiz-Datei ────────────────────────────────────────

def test_personen_liste_kommt_aus_dem_quiz(basis):
    r = _liste()
    assert r.ok is True
    # Beide Quiz-Namen erscheinen — die Zahl stammt aus der Gruppengroesse.
    assert "2 bekannte Personen" in r.text
    assert "Testperson A" in r.text and "Testperson B" in r.text
    assert "120 Gesichter" in r.text and "7 Gesichter" in r.text


def test_personen_liste_ohne_quiz_nennt_keine_erfundenen_personen(tmp_path, monkeypatch):
    """Fehlen die Quiz-Dateien, darf die Liste keine Personen behaupten."""
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path / "leer"))
    gq._CACHE.clear()
    r = _liste()
    # Kein Bestand -> ehrlicher Hinweis (kein erfundener Name).
    assert "Testperson" not in r.text


def test_person_auskunft_liest_profil_und_notizen(basis):
    r = _auskunft(person="Testperson A")
    assert r.ok is True
    assert "Person: Testperson A" in r.text
    assert "Beziehung: Beispiel-Beziehung" in r.text
    assert "Geburtstag: 1990-01-02" in r.text          # aus dem Telefonbuch-Auszug
    assert "Fotos (erkannte Gesichter): 120" in r.text
    assert "Mag Beispielhaftes" in r.text
    assert "zurueckgenommen" not in r.text             # zurueckgenommene Notiz zaehlt nicht


def test_person_auskunft_ohne_namen_ist_ehrlich(basis):
    r = _auskunft(person="")
    assert r.ok is False and "Namen" in r.text


def test_person_auskunft_unbekannter_name(basis):
    r = _auskunft(person="Gibt-es-nicht")
    assert r.ok is False and "Keine benannte Person" in r.text


def test_person_auskunft_nimmt_nie_vektoren_oder_pfade(basis):
    r = _auskunft(person="Testperson A")
    assert "bbox" not in r.text and ".json" not in r.text and "/" not in r.text
