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


# ── fotos_mit_person: Trefferliste aus der Quiz-Quelle (Teil B, 10.10.2026) ──
#
# Befund: Der alte Weg tippte lokale Bildpfade ab und liess die Gesichtserkennung
# live laufen; auf dem Handy liegen die Fotos aber nicht. Jetzt kommt die Liste aus
# ``gruppen_quiz.bilder_mit`` und die Kennung -> Datei/Ordner aus dem
# Beschreibungs-Index (``bild_beschreibungen.jsonl`` ueber ERZAEHL_EREIGNISSE_PFAD).

ZUORDNUNG = [
    {"bild_id": "5001", "index": 0, "kennung": "Person_1001", "bbox": [10.0, 20.0, 30.0, 40.0],
     "anteil": 0.01, "score": 0.90, "aufnahme": "2019-07-01T12:00:00", "video_id": None},
    {"bild_id": "5002", "index": 0, "kennung": "Person_1001", "bbox": [10.0, 20.0, 30.0, 40.0],
     "anteil": 0.02, "score": 0.95, "aufnahme": "2021-03-05T09:30:00", "video_id": None},
    {"bild_id": "5003", "index": 0, "kennung": "Person_1003", "bbox": [1.0, 2.0, 3.0, 4.0],
     "anteil": 0.02, "score": 0.95, "aufnahme": "2020-01-01T00:00:00", "video_id": None},
]
BESCHREIBUNGEN = [
    {"fileid": 5001, "datei": "IMG_5001.jpg", "ordner": "P:/Fotos/Urlaub", "beschreibung": "Strand"},
    {"fileid": 5002, "datei": "IMG_5002.jpg", "ordner": "P:/Fotos/Urlaub", "beschreibung": "Berg"},
    {"fileid": 5003, "datei": "IMG_5003.jpg", "ordner": "P:/Fotos/Zuhause", "beschreibung": "Kueche"},
]


def _mit_fotos(basis, monkeypatch):
    """Zuordnung (Gesicht->Bild) und Beschreibungs-Index in die Quiz-Basis legen."""
    _schreibe(basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME, ZUORDNUNG)
    _schreibe(basis / "ereignisse.jsonl", [])
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(basis / "ereignisse.jsonl"))
    _schreibe(basis / "bild_beschreibungen.jsonl", BESCHREIBUNGEN)
    gq._CACHE.clear()
    wz._BILD_DATEIEN.clear()


def _fotos(**args):
    return wz.REGISTER["fotos_mit_person"].ausfuehren(args)


def test_fotos_mit_person_kommt_aus_dem_quiz(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)
    e = _fotos(person="Testperson A")
    assert e.ok is True
    assert "2 Foto(s)/Video(s) mit Testperson A" in e.text
    # Datei, Aufnahmedatum und Ordner stammen aus dem Beschreibungs-Index.
    assert "IMG_5002.jpg" in e.text and "2021-03-05" in e.text
    assert "IMG_5001.jpg" in e.text and "2019-07-01" in e.text
    assert "P:/Fotos/Urlaub" in e.text
    # Eine andere Person taucht nicht auf; keine Innereien (bbox, Kennung).
    assert "IMG_5003.jpg" not in e.text
    assert "bbox" not in e.text and "Person_1001" not in e.text


def test_fotos_mit_person_unbekannter_name_ist_ehrlich(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)
    e = _fotos(person="Gibt-es-nicht")
    assert e.ok is False and "bestätigte Person" in e.text


def test_fotos_mit_person_tage_grenze(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)
    e = _fotos(person="Testperson A", tage=30)
    # Die Aufnahmen liegen 2019/2021 — weit ausserhalb der letzten 30 Tage.
    assert "Keine Fotos" in e.text


# ── person_auskunft: Anlässe einer Person (Schritt 7, 10.10.2026) ────────────
# Verknüpfung Gesicht -> Anlass: die Bild-Kennungen der Person (Quiz-Zuordnung)
# treffen die ``datei_kennungen`` der Ereignisse (``erzaehl_service``).

EREIGNISSE = [
    {"kennung": "E-2019-07-01_Anlass-01", "datum": "2019-07-01", "jahr": 2019,
     "event": "2019-07-01 Urlaub am Meer", "kategorie": "Urlaub",
     "anzahl_dateien": 1, "datei_kennungen": [5001]},
    {"kennung": "E-2021-03-05_Anlass-01", "datum": "2021-03-05", "jahr": 2021,
     "event": "2021-03-05 Wanderung", "kategorie": "Reise",
     "anzahl_dateien": 2, "datei_kennungen": [5002, 9999]},
    {"kennung": "E-2020-01-01_Anlass-01", "datum": "2020-01-01", "jahr": 2020,
     "event": "2020-01-01 In der Kueche", "kategorie": "Alltag",
     "anzahl_dateien": 1, "datei_kennungen": [5003]},
]


def test_person_auskunft_zeigt_anlaesse(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)
    _schreibe(basis / "ereignisse.jsonl", EREIGNISSE)
    r = _auskunft(person="Testperson A")
    assert r.ok is True
    assert "Anlässe (2)" in r.text
    assert "2019-07-01 Urlaub am Meer" in r.text
    assert "2021-03-05 Wanderung" in r.text
    # Der Anlass von Testperson B gehoert nicht dazu; keine Innereien.
    assert "In der Kueche" not in r.text
    assert "Anlass-01" not in r.text and "bbox" not in r.text


def test_person_auskunft_ohne_ereignisquelle_bleibt_ruhig(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)   # schreibt ereignisse.jsonl als leere Liste
    r = _auskunft(person="Testperson A")
    assert r.ok is True and "Anlässe" not in r.text


def test_person_auskunft_anlaesse_ohne_treffer_ist_leer(basis, monkeypatch):
    _mit_fotos(basis, monkeypatch)
    _schreibe(basis / "ereignisse.jsonl", [
        {"kennung": "E-2000-01-01_Anlass-01", "datum": "2000-01-01", "jahr": 2000,
         "event": "2000-01-01 Fremd", "kategorie": "Alltag",
         "anzahl_dateien": 1, "datei_kennungen": [424242]},
    ])
    r = _auskunft(person="Testperson A")
    assert r.ok is True and "Anlässe" not in r.text
