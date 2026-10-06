"""Tests: Sebastians eigene Notizen durchsuchbar machen (07.10.2026).

Alles offline und mit **erfundenen** Daten: eine Personen-Profil-Datei mit
Testpersonen (Beziehung „Bruder", Notiz „Arbeitet als Tischler") und eine
Geschichten-Datei mit erfundenen Erzählungen. Keine echten Namen, keine
echten Notizen, kein Netz, keine pCloud — beide Dateien liegen in ``tmp_path``.

Geprueft werden die Kernregeln: Notiz einer Person wird gefunden (auch über
das Stichwort), zurückgenommene Notizen zählen nicht, Wortanfang genügt
(„Urlaub" findet „Urlaubsbilder"), Umlaute werden vereinheitlicht, eine Suche
ohne Treffer sagt das ehrlich statt zu erfinden, fehlende/defekte Dateien
werfen nicht, ersetzte Geschichten zählen nicht, die Dateien werden nur
gelesen (Zeichen für Zeichen gleich, keine temp-Datei) und das Chat-Werkzeug
ist angemeldet und antwortet.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_notizen_service.py -q
"""
from __future__ import annotations

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import notizen_service as ns  # noqa: E402
from app.services import werkzeuge  # noqa: E402

PROFILE = {
    "profile": {
        "Testperson A": {
            "beziehung": "Bruder",
            "notizen": [
                {"id": "n1", "zeit": "2026-10-01T10:00:00", "text": "Arbeitet als Tischler."},
                {"id": "n2", "zeit": "2026-10-02T10:00:00", "text": "Mag keinen Kaffee.",
                 "zurueckgenommen": True},
            ],
        },
        "Testperson B": {
            "beziehung": "Freundin",
            "notizen": [{"id": "n3", "zeit": "2026-09-30T09:00:00",
                         "text": "Urlaubsbilder sortiert, war in der Türkei."}],
        },
        "Testperson C": {"beziehung": "", "notizen": []},
    }
}

GESCHICHTEN = [
    {"id": "g1", "ereignis_kennung": "E-2015-10-03_Test", "text": "Buße war ein schöner Abend.",
     "zeit": "2026-10-01T12:00:00", "quelle": "mensch"},
    {"id": "g2", "ereignis_kennung": "E-2015-10-03_Test", "text": "Alte Fassung.", "zeit": "x"},
    {"id": "g3", "ereignis_kennung": "E-2015-10-03_Test", "text": "Neue Fassung.", "zeit": "y",
     "ersetzt": "g2"},
]


def dateien_bauen(tmp_path):
    profil = tmp_path / "personen_profile.json"
    profil.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    geschichten = tmp_path / "geschichten.jsonl"
    geschichten.write_text("\n".join(json.dumps(z, ensure_ascii=False) for z in GESCHICHTEN),
                           encoding="utf-8")
    return str(profil), str(geschichten)


def pfade_setzen(monkeypatch, profil, geschichten):
    """Die Pfade injizierbar machen — über dieselben Funktionen, die auch der
    Dienst benutzt (kein Monkeypatch im Inneren, kein echter Bestand)."""
    from app.services import erzaehl_service

    monkeypatch.setattr(ns, "profile_pfad", lambda: profil)
    monkeypatch.setattr(erzaehl_service, "geschichten_pfad", lambda: geschichten)


# --- Personen-Notizen ------------------------------------------------------

def test_person_mit_notiz_wird_gefunden(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    p = ns.person_finden("Testperson A")
    assert p is not None, "Person muss gefunden werden"
    assert p["beziehung"] == "Bruder"
    assert [n["text"] for n in p["notizen"]] == ["Arbeitet als Tischler."]
    text = ns.text_antwort(person="Testperson A")
    assert "Tischler" in text and "Bruder" in text


def test_zurueckgenommene_notiz_zaehlt_nicht(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    p = ns.person_finden("Testperson A")
    assert p is not None
    assert p["anzahl"] == 1
    assert "Kaffee" not in ns.text_antwort(person="Testperson A")


def test_person_ohne_notiz_und_unbekannte_person(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    assert "Keine Notiz hinterlegt" in ns.text_antwort(person="Testperson C")
    assert "habe ich keine notiz" in ns.text_antwort(person="Testperson Z").lower()
    # Wortanfang genügt (wie im Quiz-Suchfeld)
    assert ns.person_finden("Testperson A")["name"] == "Testperson A"


# --- Suche ----------------------------------------------------------------

def test_suche_ueber_stichwort_in_der_notiz(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    stand = ns.suche("Tischler")
    assert [p["name"] for p in stand["personen"]] == ["Testperson A"]
    assert "Tischler" in ns.text_antwort(begriff="Tischler")


def test_suche_findet_wortanfang(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    assert [p["name"] for p in ns.suche("Urlaub")["personen"]] == ["Testperson B"]


def test_suche_ohne_treffer_sagt_das_ehrlich(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    stand = ns.suche("Fahrradtour")
    assert stand["personen"] == [] and stand["geschichten"] == []
    text = ns.text_antwort(begriff="Fahrradtour")
    assert "steht nichts" in text
    # nennt ehrlich, was durchsucht wurde (2 Personen-Notizen, 2 Geschichten —
    # die ersetzte Zeile zählt nicht mit)
    assert "durchsucht" in text and "2 Personen-Notizen" in text and "2 Geschichten" in text


def test_umlaute_werden_vereinheitlicht(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    assert ns.normalisiere("Buße") == "busse"
    assert [g["text"] for g in ns.suche("busse")["geschichten"]] == ["Buße war ein schöner Abend."]


def test_kurze_begriffe_werden_ignoriert(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    # „in", „am" o. ä. sind keine Suchbegriffe -> Bestandsaufnahme (Personen
    # MIT Notiz und die Geschichten), kein Zufallstreffer über Kurzwörter.
    stand = ns.suche("in am")
    assert [p["name"] for p in stand["personen"]] == ["Testperson A", "Testperson B"]
    assert stand["mit_notizen"] == 2 and stand["gesamt_personen"] == 3


# --- Robustheit ------------------------------------------------------------

def test_fehlende_dateien_werfen_nicht(tmp_path, monkeypatch):
    pfade_setzen(monkeypatch, str(tmp_path / "gibtsnicht.json"), str(tmp_path / "auchnicht.jsonl"))
    assert ns.personen_notizen() == [] and ns.geschichten() == []
    text = ns.text_antwort()
    assert "Personen haben eine Notiz" in text


def test_defekte_datei_zaehlt_als_leer(tmp_path, monkeypatch):
    kaputt = tmp_path / "personen_profile.json"
    kaputt.write_text("{das ist kein json", encoding="utf-8")
    geschichten = tmp_path / "geschichten.jsonl"
    geschichten.write_text("auch kein json\n", encoding="utf-8")
    pfade_setzen(monkeypatch, str(kaputt), str(geschichten))
    assert ns.personen_notizen() == [] and ns.geschichten() == []


def test_ersetzte_geschichte_zaehlt_nicht(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    texte = [g["text"] for g in ns.geschichten()]
    assert "Neue Fassung." in texte
    assert "Alte Fassung." not in texte          # über „ersetzt" verdrängt


def test_dateien_werden_nur_gelesen(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    vorher_p = open(profil, "rb").read()
    vorher_g = open(geschichten, "rb").read()
    pfade_setzen(monkeypatch, profil, geschichten)
    ns.personen_notizen()
    ns.suche("Tischler")
    ns.text_antwort(person="Testperson A")
    ns.text_antwort()
    assert open(profil, "rb").read() == vorher_p
    assert open(geschichten, "rb").read() == vorher_g
    # keine temp-Datei daneben (dort wird nie geschrieben)
    assert sorted(os.listdir(tmp_path)) == ["geschichten.jsonl", "personen_profile.json"]


# --- Chat-Werkzeug ---------------------------------------------------------

def test_werkzeug_ist_angemeldet(tmp_path, monkeypatch):
    namen = [w["function"]["name"] for w in werkzeuge.schemata()]
    assert "notizen_suchen" in namen


def test_werkzeug_antwortet_und_prueft_eingabe(tmp_path, monkeypatch):
    profil, geschichten = dateien_bauen(tmp_path)
    pfade_setzen(monkeypatch, profil, geschichten)
    ergebnis = werkzeuge.ausfuehren("notizen_suchen", json.dumps({"person": "Testperson A"}))
    assert ergebnis.ok is True and "Tischler" in ergebnis.text
    leer = werkzeuge.ausfuehren("notizen_suchen", json.dumps({}))
    assert leer.ok is False and "angeben" in leer.text
