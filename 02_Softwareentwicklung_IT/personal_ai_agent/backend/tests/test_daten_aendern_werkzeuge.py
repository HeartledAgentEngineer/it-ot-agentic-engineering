# test_daten_aendern_werkzeuge.py - Testet Datenänderung per Chat ohne Hermes (31.10. / 01.11.2026)
import pytest
from app.services import werkzeuge as wz
from app.services import faehigkeiten
from app.services import auftrags_erkennung


def test_neue_werkzeuge_registriert():
    assert "erinnerung_speichern" in wz.REGISTER
    assert "erinnerung_loeschen" in wz.REGISTER
    assert "person_profil_aendern" in wz.REGISTER
    assert "notiz_speichern" in wz.REGISTER
    assert len(wz.REGISTER) == 16  # + schlaf_abfragen (03.11.2026)
    # Parameter-Prüfung für person_profil_aendern
    props = wz.REGISTER["person_profil_aendern"].parameter["properties"]
    assert "geburtstag" in props
    assert "telefonnummer" in props
    assert "kontakt_id" in props


def test_faehigkeiten_grenze_erlaubt_persoenliche_daten():
    # Chat-Pflege persönlicher Daten soll NICHT als Hermes-Grenze eingestuft werden
    assert not faehigkeiten.stoesst_an_grenze("Ändere die Notiz von Julian")
    assert not faehigkeiten.stoesst_an_grenze("Lösche die Erinnerung an meinen alten Geburtstag")
    assert not faehigkeiten.stoesst_an_grenze("Passe das Profil von Papa an")
    assert not faehigkeiten.stoesst_an_grenze("Ergänze die Beziehung von Matthias als Bruder")
    assert not faehigkeiten.stoesst_an_grenze("Überschreibe das Telefonbuchfeld von Julian")
    assert not faehigkeiten.stoesst_an_grenze("Trage die Handynummer von Mama ein")
    # Echtes Coding / Git / Terminal bleibt Hermes vorbehalten
    assert faehigkeiten.stoesst_an_grenze("Führe einen git commit und push aus")
    assert faehigkeiten.stoesst_an_grenze("Code ändern im Projekt")


def test_auftrags_erkennung_ignoriert_persoenliche_daten():
    # Chat-Pflege persönlicher Daten ist KEIN Coding-Auftrag für Hermes
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Ändere meine Notiz zum Foto")
    assert not ist
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Passe das Personen-Profil an")
    assert not ist
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Lösche die Erinnerung")
    assert not ist
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Ändere den Geburtstag im Telefonbuch")
    assert not ist
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Setze die Telefonnummer von Julian")
    assert not ist
    # Echtes Coding bleibt Auftrag
    ist, _, _, _ = auftrags_erkennung.ist_auftrag("Schreibe einen neuen Endpoint im Backend und committe")
    assert ist


def test_notiz_speichern_ausfuehrung(monkeypatch):
    from app.services import erzaehl_service as es
    aufgerufen = {}

    def mock_speichern(text, datei_kennung=None, ereignis_kennung=None, quelle="ki"):
        aufgerufen["text"] = text
        aufgerufen["datei"] = datei_kennung
        aufgerufen["ereignis"] = ereignis_kennung
        return {"ok": True, "id": "test-123"}

    monkeypatch.setattr(es, "geschichte_speichern", mock_speichern)
    res = wz.REGISTER["notiz_speichern"].ausfuehren({"ereignis_kennung": "ev-1", "text": "Toller Tag", "datei_kennung": 12345})
    assert res.ok is True
    assert aufgerufen["text"] == "Toller Tag"
    assert aufgerufen["datei"] == 12345
    assert aufgerufen["ereignis"] == "ev-1"


def test_person_profil_aendern_ausfuehrung(monkeypatch):
    from app.services import gruppen_quiz as gq
    aufgerufen = {}

    def mock_profil(name, beziehung=None, notiz=None, vorname=None, nachname=None, spitznamen=None, geburtstag=None, telefonnummer=None, nummern=None, kontakt_id=None, **kwargs):
        aufgerufen["name"] = name
        aufgerufen["beziehung"] = beziehung
        aufgerufen["notiz"] = notiz
        aufgerufen["geburtstag"] = geburtstag
        aufgerufen["telefonnummer"] = telefonnummer
        return {"ok": True, "name": name, "geburtstag": geburtstag, "nummern": [telefonnummer] if telefonnummer else []}

    monkeypatch.setattr(gq, "profil_ergaenzen", mock_profil)
    res = wz.REGISTER["person_profil_aendern"].ausfuehren({
        "name": "Matthias",
        "beziehung": "Bruder",
        "notiz": "Familie",
        "geburtstag": "1995-05-12",
        "telefonnummer": "+491761234567"
    })
    assert res.ok is True
    assert aufgerufen["name"] == "Matthias"
    assert aufgerufen["beziehung"] == "Bruder"
    assert aufgerufen["notiz"] == "Familie"
    assert aufgerufen["geburtstag"] == "1995-05-12"
    assert aufgerufen["telefonnummer"] == "+491761234567"
    assert "Geburtstag: 1995-05-12" in res.text
    assert "Telefon: +491761234567" in res.text


def test_person_auskunft_zeigt_geburtstag_und_telefon(monkeypatch):
    from app.services import gruppen_quiz as gq

    def mock_person(name):
        return {
            "ok": True,
            "name": name,
            "profil": {
                "beziehung": "Zwillingsbruder",
                "geburtstag": "1998-01-19",
                "nummern": ["+4917687055198"],
                "notizen": [{"text": "Wohnt in Hamburg"}]
            },
            "vorschlaege": [{"groesse": 42}]
        }

    monkeypatch.setattr(gq, "person", mock_person)
    monkeypatch.setattr(gq, "bild_kennungen_person", lambda n: {"ok": True, "kennungen": []})
    
    res = wz.REGISTER["person_auskunft"].ausfuehren({"person": "Julian"})
    assert res.ok is True
    assert "Beziehung: Zwillingsbruder." in res.text
    assert "Geburtstag: 1998-01-19." in res.text
    assert "Telefon: +4917687055198." in res.text
    assert "Erkannt auf 42 Fotos." in res.text
    assert "Wohnt in Hamburg." in res.text
