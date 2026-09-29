"""Tests: Beziehungen an einem Tag (Nachtlauf-Schritt N28, 29.09.2026).

Prüft den Dienst ``app/services/beziehungen_service.py``, den Router
``app/router/beziehungen.py``, den Selbsttest-Block ``beziehungen`` und das
Chat-Werkzeug ``_beziehungen_tool``.

Alles läuft **offline**: Die Aussagen-Datei (JSONL) und die Übersicht (JSON)
werden für jeden Test in ``tmp_path`` **erfunden** — erfundene Namen
(``Person_001``, „Musterperson"), erfundene Themen und Kategorien, kein echter
Bestand, kein Netz, kein pCloud-Aufruf, keine Bilddatei. Die Pfade kommen über
``monkeypatch`` auf die Modulkonstanten ``STANDARD_PFAD``/``STANDARD_UEBERSICHT``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_beziehungen_service.py -q
"""

from __future__ import annotations

import ast
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import beziehungen_service as b  # noqa: E402

UEBERSICHT_PFAD = "/api/beziehungen/uebersicht"
TAG_PFAD = "/api/beziehungen/tag"
DIENST_DATEI = os.path.join(BACKEND, "app", "services", "beziehungen_service.py")
ROUTER_DATEI = os.path.join(BACKEND, "app", "router", "beziehungen.py")

# Die Felder, die jede Übersichts-Antwort IMMER liefert.
UEBERSICHT_FELDER = {
    "ok", "pfad", "existiert", "stand", "anzahl", "anzahl_gesamt", "datum_von",
    "datum_bis", "anzahl_personen_kennungen", "anzahl_namen_bestaetigt",
    "anzahl_kontakte", "error",
}

# Die Felder, die jede Tag-Antwort IMMER liefert.
TAG_FELDER = {
    "ok", "quelle", "stand", "datum", "gueltig", "anzahl", "anzahl_je_unterart",
    "aussagen", "gekuerzt", "error",
}

# Die Schlüssel des Selbsttest-Blocks — immer dieselben.
STATUS_FELDER = {
    "quelle", "pfad", "existiert", "stand", "aussagen", "personen_kennungen",
    "namen_bestaetigt", "kontakte", "datum_von", "datum_bis", "error",
}

# Erfundene Beispiel-Hinweise (je Unterart verschieden, damit man erkennt, dass
# ein Hinweis nur EINMAL genannt wird).
HINWEIS_FOTOS = "Erfundener Foto-Hinweis."
HINWEIS_CHAT = "Erfundener Chat-Hinweis."
HINWEIS_KREUZ = "Erfundener Kreuz-Hinweis."


# ── Erfundene Beispieldaten ──────────────────────────────────────────────────

def _person(kennung="Person_001", name=None) -> dict:
    return {"bestaetigt": False, "bilder": 1, "gesichter": 1,
            "kennung": kennung, "name": name}


def _zeile(datum, unterart, anlass_id, personen=None, hinweis="Erfundener Hinweis.",
           thema="Beispielthema", kategorie="Beispiel-Kategorie") -> dict:
    """Eine erfundene Aussagezeile im eingefrorenen Schema."""
    return {
        "anlass_id": anlass_id,
        "art": "beziehung",
        "beleg": {"bilder": 1, "gesichter": 1},
        "datum": datum,
        "ereignis_kennung": "E-" + anlass_id,
        "hinweis": hinweis,
        "kategorie": kategorie,
        "personen": personen if personen is not None
                    else [_person("Person_001"), _person("Person_002")],
        "quellen": {"andockung": "beispiel_andockung.jsonl:1"},
        "stand": "2026-09-29T01:42:52+02:00",
        "thema": thema,
        "unterart": unterart,
        "ziel_ordner": "Beispiel/Ordner",
    }


# Vier Aussagen am 2022-08-21 (2 fotos, 1 chat, 1 kreuz), eine am 2019-12-20.
# Absichtlich unsortiert abgelegt — die Reihenfolge macht der Dienst.
BEISPIEL_ZEILEN = [
    _zeile("2022-08-21", "fotos_und_chat", "2022-08-21_Anlass-01",
           hinweis=HINWEIS_KREUZ),
    _zeile("2022-08-21", "gemeinsam_im_chat", "2022-08-21_Anlass-01",
           hinweis=HINWEIS_CHAT),
    _zeile("2022-08-21", "fotos", "2022-08-21_Anlass-02", hinweis=HINWEIS_FOTOS),
    _zeile("2019-12-20", "fotos", "2019-12-20_Anlass-01", hinweis=HINWEIS_FOTOS),
    _zeile("2022-08-21", "fotos", "2022-08-21_Anlass-01", hinweis=HINWEIS_FOTOS),
]

BEISPIEL_UEBERSICHT = {
    "art": "beziehungen",
    "stand": "2026-09-29T01:42:52+02:00",
    "anzahl": {"fotos": 3, "gemeinsam_im_chat": 1, "fotos_und_chat": 1},
    "anzahl_personen_kennungen": 2,
    "anzahl_namen_bestaetigt": 0,
    "anzahl_kontakte": 1,
    "datum_von": "2019-12-20",
    "datum_bis": "2022-08-21",
    "hinweis": "Erfundener Hinweis.",
    "quellen": {"andockung": "beispiel_andockung.jsonl"},
}


# ── Aufbau ───────────────────────────────────────────────────────────────────

def _jsonl(pfad, zeilen) -> str:
    """Zeilen als JSONL schreiben (str bleibt roh — für kaputte Zeilen)."""
    with open(str(pfad), "w", encoding="utf-8") as datei:
        for eintrag in zeilen:
            if isinstance(eintrag, str):
                datei.write(eintrag + "\n")
            else:
                datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    return str(pfad)


def _json(pfad, daten) -> str:
    with open(str(pfad), "w", encoding="utf-8") as datei:
        json.dump(daten, datei, ensure_ascii=False)
    return str(pfad)


def _netz_sperren(monkeypatch) -> None:
    """Jeden echten Verbindungsaufbau scheitern lassen (Namensauflösung etc.)."""
    import socket

    def kein_ausgang(*args, **kwargs):
        raise AssertionError("Echter Netz-Call versucht")

    monkeypatch.setattr(socket, "create_connection", kein_ausgang, raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", kein_ausgang, raising=False)


@pytest.fixture()
def pfade(tmp_path, monkeypatch) -> dict:
    """Beide Dienstpfade auf (noch leere) temporäre Dateien umbiegen."""
    aussagen = tmp_path / "beziehungen.jsonl"
    uebersicht = tmp_path / "beziehungen.json"
    monkeypatch.setattr(b, "STANDARD_PFAD", str(aussagen))
    monkeypatch.setattr(b, "STANDARD_UEBERSICHT", str(uebersicht))
    return {"aussagen": str(aussagen), "uebersicht": str(uebersicht),
            "tmp": tmp_path}


@pytest.fixture()
def bestand(pfade) -> dict:
    """Die erfundene Aussagen-Datei und Übersicht liegen bereit."""
    _jsonl(pfade["aussagen"], BEISPIEL_ZEILEN)
    _json(pfade["uebersicht"], BEISPIEL_UEBERSICHT)
    return pfade


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


@pytest.fixture()
def selbsttest_ohne_netz(monkeypatch):
    """Selbsttest ohne pCloud-Netzweg (der Dienst ist nicht eingerichtet)."""
    import app.router.selbsttest as st

    class FakePCloud:
        token = ""
        host = None

        def ist_konfiguriert(self):
            return False

        def status(self):
            raise AssertionError("pCloud darf im Test nicht gefragt werden")

    monkeypatch.setattr(st, "pcloud_service", FakePCloud())


def _route(gesucht: str):
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == gesucht and "GET" in getattr(route, "methods", set()):
            return route
    return None


# ── datum_erkennen ───────────────────────────────────────────────────────────

def test_datum_iso():
    assert b.datum_erkennen("2019-12-27") == "2019-12-27"


def test_datum_punkt_vierstellig():
    assert b.datum_erkennen("27.12.2019") == "2019-12-27"


def test_datum_punkt_zweistellig_wird_20xx():
    assert b.datum_erkennen("27.12.19") == "2019-12-27"


def test_datum_monatsname_ausgeschrieben():
    assert b.datum_erkennen("27. Dezember 2019") == "2019-12-27"


def test_datum_monatsname_maerz_und_maerz():
    assert b.datum_erkennen("31. März 2020") == "2020-03-31"
    assert b.datum_erkennen("31. Maerz 2020") == "2020-03-31"
    assert b.datum_erkennen("1. märz 2021") == "2021-03-01"


def test_datum_mit_am_davor():
    assert b.datum_erkennen("am 3.1.2022") == "2022-01-03"


def test_datum_einzelstellige_zahlen():
    assert b.datum_erkennen("am 3.1.2022 war was") == "2022-01-03"


def test_datum_zweistelliges_jahr_mit_monatsname():
    assert b.datum_erkennen("27. Dezember 19") == "2019-12-27"


def test_datum_ungueltiger_tag_31_02():
    assert b.datum_erkennen("31.02.2020") is None


def test_datum_unsinn_99_99():
    assert b.datum_erkennen("99.99.9999") is None


def test_datum_jahr_allein_ist_kein_tag():
    assert b.datum_erkennen("2019") is None


def test_datum_ohne_datum_ist_none():
    assert b.datum_erkennen("wie geht's dir?") is None


def test_datum_leer_und_falscher_typ():
    assert b.datum_erkennen("") is None
    assert b.datum_erkennen("   ") is None
    assert b.datum_erkennen(None) is None
    assert b.datum_erkennen(20191227) is None


def test_datum_im_satz():
    assert b.datum_erkennen("was war am 27.12.2019?") == "2019-12-27"


# ── beziehungen_laden ────────────────────────────────────────────────────────

def test_laden_alle_schluessel_immer_da(pfade):
    daten = b.beziehungen_laden()
    assert set(daten.keys()) == {
        "pfad", "existiert", "stand", "anzahl", "anzahl_gesamt", "datum_von",
        "datum_bis", "anzahl_personen_kennungen", "anzahl_namen_bestaetigt",
        "anzahl_kontakte", "error",
    }


def test_laden_fehlende_dateien_ist_false_mit_deutschem_fehler(pfade):
    daten = b.beziehungen_laden()
    assert daten["existiert"] is False
    assert isinstance(daten["error"], str) and daten["error"].strip()
    assert "PC" in daten["error"]


def test_laden_fehlende_uebersicht_ist_false_mit_deutschem_fehler(pfade):
    _jsonl(pfade["aussagen"], BEISPIEL_ZEILEN)  # Aussagen da, Übersicht fehlt
    daten = b.beziehungen_laden()
    assert daten["existiert"] is False
    assert daten["error"] and "Übersicht" in daten["error"]


def test_laden_vorhandene_uebersicht_liefert_kennzahlen(bestand):
    daten = b.beziehungen_laden()
    assert daten["existiert"] is True
    assert daten["error"] is None
    assert daten["stand"] == "2026-09-29T01:42:52+02:00"
    assert daten["datum_von"] == "2019-12-20"
    assert daten["datum_bis"] == "2022-08-21"
    assert daten["anzahl_personen_kennungen"] == 2
    assert daten["anzahl_namen_bestaetigt"] == 0
    assert daten["anzahl_kontakte"] == 1
    assert daten["anzahl"] == {"fotos": 3, "gemeinsam_im_chat": 1,
                               "fotos_und_chat": 1}


def test_laden_anzahl_gesamt_ist_die_summe(bestand):
    assert b.beziehungen_laden()["anzahl_gesamt"] == 5


def test_laden_liest_die_aussagen_nicht(bestand):
    """Die Aussagen selbst werden NICHT in dieses dict geladen."""
    assert "aussagen" not in b.beziehungen_laden()


def test_laden_kaputte_uebersicht_ist_kein_wurf(pfade):
    _jsonl(pfade["aussagen"], BEISPIEL_ZEILEN)
    with open(pfade["uebersicht"], "w", encoding="utf-8") as datei:
        datei.write("{kein json")
    daten = b.beziehungen_laden()
    assert daten["existiert"] is False
    assert "JSON" in daten["error"]


def test_laden_fremde_art_wird_gemeldet(pfade):
    _jsonl(pfade["aussagen"], BEISPIEL_ZEILEN)
    roh = dict(BEISPIEL_UEBERSICHT)
    roh["art"] = "etwas_anderes"
    _json(pfade["uebersicht"], roh)
    daten = b.beziehungen_laden()
    assert daten["existiert"] is False
    assert "Art" in daten["error"]


def test_laden_pfad_ist_die_aussagen_datei(bestand):
    assert b.beziehungen_laden()["pfad"] == bestand["aussagen"]


# ── aussagen_fuer_datum ──────────────────────────────────────────────────────

def test_tag_filter_trifft_genau_einen_tag(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21")
    assert daten["gueltig"] is True
    assert daten["error"] is None
    assert daten["anzahl"] == 4
    assert all(a["datum"] == "2022-08-21" for a in daten["aussagen"])


def test_tag_anzahl_ist_gesamtzahl_vor_dem_limit(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21", limit=2)
    assert daten["anzahl"] == 4
    assert len(daten["aussagen"]) == 2
    assert daten["gekuerzt"] is True


def test_tag_nicht_gekuerzt_wenn_alles_passt(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21", limit=50)
    assert daten["gekuerzt"] is False
    assert len(daten["aussagen"]) == 4


def test_tag_sortierung_nach_unterart_reihenfolge(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21", limit=50)
    unterarten = [a["unterart"] for a in daten["aussagen"]]
    assert unterarten == ["fotos", "fotos", "gemeinsam_im_chat",
                          "fotos_und_chat"]


def test_tag_sortierung_innerhalb_unterart_nach_anlass_id(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21", limit=50)
    fotos_ids = [a["anlass_id"] for a in daten["aussagen"]
                 if a["unterart"] == "fotos"]
    assert fotos_ids == ["2022-08-21_Anlass-01", "2022-08-21_Anlass-02"]


def test_tag_anzahl_je_unterart_hat_alle_drei(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21")
    assert daten["anzahl_je_unterart"] == {"fotos": 2, "gemeinsam_im_chat": 1,
                                           "fotos_und_chat": 1}


def test_tag_leerer_tag_ist_kein_fehler(bestand):
    daten = b.aussagen_fuer_datum("2020-01-01")
    assert daten["gueltig"] is True
    assert daten["anzahl"] == 0
    assert daten["aussagen"] == []
    assert daten["error"] is None


def test_tag_ungueltiges_datum_gueltig_false(bestand):
    daten = b.aussagen_fuer_datum("31.02.2020")
    assert daten["gueltig"] is False
    assert daten["anzahl"] == 0
    assert daten["error"]


def test_tag_punktform_wird_erkannt(bestand):
    daten = b.aussagen_fuer_datum("21.08.2022")
    assert daten["datum"] == "2022-08-21"
    assert daten["anzahl"] == 4


def test_tag_fehlende_datei_ergibt_deutschen_fehler(pfade):
    daten = b.aussagen_fuer_datum("2022-08-21")
    assert daten["gueltig"] is True
    assert daten["anzahl"] == 0
    assert daten["error"] and "PC" in daten["error"]


def test_tag_kaputte_json_zeile_ist_defekt_kein_wurf(pfade):
    _jsonl(pfade["aussagen"], BEISPIEL_ZEILEN + ["{das ist kein json", "[1,2,3]"])
    daten = b.aussagen_fuer_datum("2022-08-21")
    assert daten["anzahl"] == 4           # die zwei defekten Zeilen zählen nicht
    assert daten["error"] is None


def test_tag_limit_null_wird_auf_eins_angehoben(bestand):
    assert len(b.aussagen_fuer_datum("2022-08-21", limit=0)["aussagen"]) == 1


def test_tag_limit_unsinn_faellt_auf_standard(bestand):
    daten = b.aussagen_fuer_datum("2022-08-21", limit="quatsch")
    assert len(daten["aussagen"]) == 4


# ── text_antwort ─────────────────────────────────────────────────────────────

def test_text_enthaelt_datum_zahlen_hinweis_und_schluss(bestand):
    text = b.text_antwort("2022-08-21")
    assert "2022-08-21" in text
    assert "4 Aussagen" in text
    assert HINWEIS_FOTOS in text
    assert b.ABGRENZUNG in text


def test_text_hinweis_nur_einmal_je_unterart(bestand):
    """Der Hinweis ist je Unterart gleich — er wird EINMAL genannt."""
    text = b.text_antwort("2022-08-21")
    assert text.count(HINWEIS_FOTOS) == 1     # zwei fotos-Zeilen, ein Hinweis
    assert text.count(HINWEIS_CHAT) == 1
    assert text.count(HINWEIS_KREUZ) == 1


def test_text_enthaelt_keinen_namen_wenn_name_null(bestand):
    text = b.text_antwort("2022-08-21")
    assert "Person_001" in text
    assert "Musterperson" not in text


def test_text_nennt_den_namen_wenn_vorhanden(pfade):
    _jsonl(pfade["aussagen"], [
        _zeile("2022-08-21", "fotos", "2022-08-21_Anlass-01",
               personen=[_person("Person_001", "Musterperson")],
               hinweis=HINWEIS_FOTOS),
    ])
    _json(pfade["uebersicht"], BEISPIEL_UEBERSICHT)
    text = b.text_antwort("2022-08-21")
    assert "Musterperson" in text
    assert "Person_001" in text


def test_text_leerer_tag_sagt_keine_andockung(bestand):
    text = b.text_antwort("2020-01-01")
    assert "2020-01-01" in text
    assert "keine Andockung" in text
    assert b.ABGRENZUNG in text


def test_text_fehlende_datei_sagt_liegt_auf_pc(pfade):
    text = b.text_antwort("2022-08-21")
    assert "PC" in text
    assert b.ABGRENZUNG not in text or "PC" in text


def test_text_ungueltiges_datum_erfindet_nichts(bestand):
    text = b.text_antwort("31.02.2020")
    assert "Datum" in text


def test_text_ist_hoechstens_2000_zeichen(bestand):
    assert len(b.text_antwort("2022-08-21")) <= 2000


def test_text_wird_bei_vielen_zeilen_gekuerzt(pfade):
    zeilen = [
        _zeile("2022-08-21", "fotos", f"2022-08-21_Anlass-{i:02d}",
               hinweis=HINWEIS_FOTOS * 40)
        for i in range(30)
    ]
    _jsonl(pfade["aussagen"], zeilen)
    _json(pfade["uebersicht"], BEISPIEL_UEBERSICHT)
    text = b.text_antwort("2022-08-21")
    assert len(text) <= 2000


def test_text_ohne_netz_call(bestand, monkeypatch):
    _netz_sperren(monkeypatch)
    assert b.text_antwort("2022-08-21")


# ── status_block ─────────────────────────────────────────────────────────────

def test_status_block_alle_schluessel_erfolg(bestand):
    block = b.status_block()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is True
    assert block["quelle"] == "beziehungen.jsonl"
    assert block["aussagen"] == 5
    assert block["personen_kennungen"] == 2
    assert block["namen_bestaetigt"] == 0
    assert block["kontakte"] == 1
    assert block["datum_von"] == "2019-12-20"
    assert block["datum_bis"] == "2022-08-21"


def test_status_block_alle_schluessel_fehler(pfade):
    block = b.status_block()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is False
    assert block["quelle"] == "beziehungen.jsonl"
    assert block["error"]


def test_status_block_wirft_nicht_bei_kaputter_datei(pfade):
    with open(pfade["aussagen"], "w", encoding="utf-8") as datei:
        datei.write("nur Quatsch")
    with open(pfade["uebersicht"], "w", encoding="utf-8") as datei:
        datei.write("@@@")
    block = b.status_block()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is False


# ── Router ───────────────────────────────────────────────────────────────────

def test_routen_sind_eingehaengt():
    assert _route(UEBERSICHT_PFAD) is not None
    assert _route(TAG_PFAD) is not None


def test_routen_haengen_am_api_key_schutz():
    for pfad in (UEBERSICHT_PFAD, TAG_PFAD):
        route = _route(pfad)
        namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
        assert "require_api_key" in namen, f"Key-Schutz fehlt bei {pfad}"


def test_uebersicht_200_mit_daten(client, bestand):
    antwort = client.get(UEBERSICHT_PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is True
    assert daten["error"] is None
    assert daten["anzahl_gesamt"] == 5
    assert daten["datum_von"] == "2019-12-20"
    assert daten["anzahl_personen_kennungen"] == 2


def test_uebersicht_immer_alle_felder_im_fehlerfall(client, pfade):
    antwort = client.get(UEBERSICHT_PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert set(daten.keys()) == UEBERSICHT_FELDER
    assert daten["ok"] is False
    assert daten["error"]


def test_uebersicht_immer_alle_felder_mit_daten(client, bestand):
    assert set(client.get(UEBERSICHT_PFAD).json().keys()) == UEBERSICHT_FELDER


def test_tag_200_mit_daten(client, bestand):
    antwort = client.get(TAG_PFAD, params={"datum": "2022-08-21"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert set(daten.keys()) == TAG_FELDER
    assert daten["ok"] is True
    assert daten["quelle"] == "beziehungen.jsonl"
    assert daten["gueltig"] is True
    assert daten["anzahl"] == 4


def test_tag_ungueltiges_datum_200_gueltig_false(client, bestand):
    antwort = client.get(TAG_PFAD, params={"datum": "31.02.2020"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["gueltig"] is False
    assert daten["error"]


def test_tag_fehlerfall_ok_false(client, pfade):
    antwort = client.get(TAG_PFAD, params={"datum": "2022-08-21"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is False
    assert daten["error"]
    assert daten["aussagen"] == []


def test_tag_limit_wird_geklemmt(client, bestand):
    daten = client.get(TAG_PFAD, params={"datum": "2022-08-21", "limit": 1}).json()
    assert len(daten["aussagen"]) == 1
    assert daten["anzahl"] == 4
    assert daten["gekuerzt"] is True


def test_tag_ohne_datum_ok_false(client, bestand):
    daten = client.get(TAG_PFAD).json()
    assert daten["ok"] is False
    assert daten["gueltig"] is False


# ── Selbsttest-Block ─────────────────────────────────────────────────────────

def test_selbsttest_enthaelt_den_beziehungen_block(client, bestand, selbsttest_ohne_netz):
    daten = client.get("/api/selbsttest").json()
    assert "beziehungen" in daten
    assert set(daten["beziehungen"].keys()) == STATUS_FELDER


def test_selbsttest_beziehungen_zeigt_zahlen(client, bestand, selbsttest_ohne_netz):
    block = client.get("/api/selbsttest").json()["beziehungen"]
    assert block["existiert"] is True
    assert block["aussagen"] == 5
    assert block["personen_kennungen"] == 2
    assert block["namen_bestaetigt"] == 0
    assert block["kontakte"] == 1
    assert block["quelle"] == "beziehungen.jsonl"


def test_selbsttest_beziehungen_fehlerfall_kein_absturz(client, pfade, selbsttest_ohne_netz):
    antwort = client.get("/api/selbsttest")
    assert antwort.status_code == 200
    block = antwort.json()["beziehungen"]
    assert block["existiert"] is False
    assert block["error"]


def test_beziehungen_info_faengt_einen_internen_fehler(monkeypatch):
    import app.router.selbsttest as st

    from app.services import beziehungen_service as modul

    def kaputt():
        raise RuntimeError("absichtlich kaputt")

    monkeypatch.setattr(modul, "status_block", kaputt)
    block = st._beziehungen_info()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is False
    assert "RuntimeError" in block["error"]


# ── Chat-Werkzeug ────────────────────────────────────────────────────────────

def _tool(frage: str) -> str:
    from app.router.chat import _beziehungen_tool

    return _beziehungen_tool(frage)


def test_tool_loest_bei_was_war_am_datum_aus(bestand):
    antwort = _tool("was war am 27.12.2019?")
    assert antwort
    assert "2019-12-27" in antwort


def test_tool_loest_bei_kurzer_datum_form_aus(bestand):
    assert _tool("27.12.2019")


def test_tool_loest_bei_zeitbezug_aus(bestand):
    assert _tool("was war am 21.08.2022 los?")


def test_tool_loest_nicht_bei_plaudern(bestand):
    assert _tool("wie geht's dir?") == ""


def test_tool_loest_nicht_bei_zu_langer_frage_ohne_zeitbezug(bestand):
    langer_text = ("Ich habe ein langes Buch über Geschichte gelesen und sehr "
                   "viel daraus gelernt, am 27.12.2019 war es kalt in der Stadt.")
    assert _tool(langer_text) == ""


def test_tool_leere_frage_bleibt_still(bestand):
    assert _tool("") == ""
    assert _tool("   ") == ""


def test_tool_ohne_datei_bleibt_still(pfade):
    """Fehlt die Aussagen-Datei, schweigt der Chat (statt zu raten)."""
    assert _tool("was war am 27.12.2019?") == ""


def test_tool_wirft_nie(monkeypatch, bestand):
    from app.services import beziehungen_service as modul

    def kaputt(*args, **kwargs):
        raise RuntimeError("absichtlich kaputt")

    monkeypatch.setattr(modul, "text_antwort", kaputt)
    assert _tool("was war am 27.12.2019?") == ""


# ── Quelltext-Prüfungen (keine Löschung, kein Netz, kein pCloud) ─────────────

def _namen_im_quelltext(datei: str) -> set:
    """Alle Namen/Attribute/Importe einer Datei (ohne Zeichenketten)."""
    with open(datei, "r", encoding="utf-8") as datei_zeiger:
        baum = ast.parse(datei_zeiger.read())
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for alias in knoten.names:
                namen.add(alias.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.module:
                namen.add(knoten.module.split(".")[0])
        elif isinstance(knoten, ast.Attribute):
            namen.add(knoten.attr)
        elif isinstance(knoten, ast.Name):
            namen.add(knoten.id)
    return namen


VERBOTEN = {"rmtree", "remove", "unlink", "rmdir", "rename", "writelines",
            "httpx", "requests", "urllib", "socket", "pcloud_service",
            "subprocess", "chmod", "move", "deletefile", "deletefolder"}


def test_dienst_hat_keine_loesch_und_netz_namen():
    treffer = _namen_im_quelltext(DIENST_DATEI) & VERBOTEN
    assert not treffer, f"verbotene Namen im Dienst: {sorted(treffer)}"


def test_router_hat_keine_loesch_und_netz_namen():
    treffer = _namen_im_quelltext(ROUTER_DATEI) & VERBOTEN
    assert not treffer, f"verbotene Namen im Router: {sorted(treffer)}"


def test_dienst_oeffnet_dateien_nur_lesend():
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert '"w"' not in quelltext and "'w'" not in quelltext
    assert '"a"' not in quelltext and "'a'" not in quelltext


def test_router_nutzt_den_dienst_statt_eigener_dateizugriffe():
    with open(ROUTER_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert "beziehungen_service.beziehungen_laden" in quelltext
    assert "beziehungen_service.aussagen_fuer_datum" in quelltext
    assert "open(" not in quelltext


def test_dateien_tragen_keine_bilddatei_endungen():
    for datei in (DIENST_DATEI, ROUTER_DATEI):
        with open(datei, "r", encoding="utf-8") as datei_zeiger:
            quelltext = datei_zeiger.read().lower()
        for endung in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
            assert endung not in quelltext, f"{endung} in {datei}"
