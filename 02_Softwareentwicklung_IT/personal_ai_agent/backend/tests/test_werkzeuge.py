"""Tests: Werkzeug-Register fuer Tool Use (Spec docs/spec-tool-use-v1.md, 30.09.2026).

Offline: alle Dienste werden per monkeypatch ersetzt, Dateien entstehen nur in
``tmp_path`` (erfundene Namen), kein Netz, kein Handy, kein Archiv.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_werkzeuge.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import werkzeuge as wz  # noqa: E402
from app.services import datei_suche  # noqa: E402


@pytest.fixture
def speicher(tmp_path, monkeypatch):
    """Erfundene Handy-Ablage als einzige erlaubte Wurzel."""
    wurzel = tmp_path / "shared"
    (wurzel / "DCIM").mkdir(parents=True)
    monkeypatch.setattr(datei_suche, "_STORAGE_WURZEL", str(wurzel))
    monkeypatch.setattr(datei_suche, "_FALLBACK_WURZELN", [str(wurzel)])
    return wurzel


# ── Register und Schemata ──────────────────────────────────────────────────

def test_schemata_sind_gueltiges_openai_format():
    schemata = wz.schemata()
    assert len(schemata) == len(wz.REGISTER) == 8
    for s in schemata:
        assert s["type"] == "function"
        f = s["function"]
        assert f["name"] in wz.REGISTER
        assert len(f["description"]) > 30, "Beschreibung muss sagen, WANN das Werkzeug passt"
        assert f["parameters"]["type"] == "object"
        for pflicht in f["parameters"]["required"]:
            assert pflicht in f["parameters"]["properties"]
    json.dumps(schemata)  # muss serialisierbar sein


def test_nur_lesende_werkzeuge():
    verboten = ("loesch", "lösch", "schreib", "send", "speicher", "merke", "verschieb", "kauf")
    for name in wz.REGISTER:
        assert not any(v in name for v in verboten), name


def test_unbekanntes_werkzeug_wirft_nicht():
    e = wz.ausfuehren("gibt_es_nicht", "{}")
    assert not e.ok and "Unbekanntes Werkzeug" in e.text


def test_kaputte_argumente_werfen_nicht():
    e = wz.ausfuehren("dateien_suchen", "{kein json")
    assert not e.ok and "JSON" in e.text
    e = wz.ausfuehren("dateien_suchen", "[1, 2]")
    assert not e.ok


def test_werkzeugfehler_kommt_als_text(monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("geheim/pfad/zum/fehler")
    monkeypatch.setattr(datei_suche, "suche_dateien", kaputt)
    e = wz.ausfuehren("dateien_suchen", "{}")
    assert not e.ok and "RuntimeError" in e.text
    assert "geheim" not in e.text  # nur der Fehlertyp, keine Innereien


def test_ergebnis_wird_gekuerzt(monkeypatch):
    monkeypatch.setattr(wz.REGISTER["personen_liste"], "ausfuehren",
                        lambda args: wz.Ergebnis("x" * (wz.MAX_ZEICHEN + 500)))
    e = wz.ausfuehren("personen_liste", {})
    assert len(e.text) < wz.MAX_ZEICHEN + 100 and "gekürzt" in e.text


# ── dateien_suchen ─────────────────────────────────────────────────────────

def test_dateien_suchen_reicht_filter_durch(monkeypatch):
    gesehen = {}

    def fake(stichwort, **kw):
        gesehen.update(kw, stichwort=stichwort)
        return [{"pfad": "/x/IMG_20260930_0925.jpg", "name": "IMG_20260930_0925.jpg",
                 "groesse_byte": 2048, "erweiterung": ".jpg", "mtime": 0}]
    monkeypatch.setattr(datei_suche, "suche_dateien", fake)
    e = wz.ausfuehren("dateien_suchen", {"art": "bild", "ordner": "kamera", "tag": "heute"})
    assert e.ok and "IMG_20260930_0925.jpg" in e.text and "pfad=/x/" in e.text
    assert gesehen["stichwort"] == ""
    assert gesehen["neueste_zuerst"] is True  # ohne Stichwort: neueste zuerst
    assert gesehen["ordner_hinweis"] == "kamera"
    assert gesehen["aufnahme_am"] == "heute"
    assert ".jpg" in gesehen["nur_erweiterungen"] and ".pdf" not in gesehen["nur_erweiterungen"]


def test_dateien_suchen_ohne_treffer_gibt_tipp(monkeypatch):
    monkeypatch.setattr(datei_suche, "suche_dateien", lambda *a, **k: [])
    e = wz.ausfuehren("dateien_suchen", {"stichwort": "tabelle"})
    assert "nur im Dateinamen" in e.text


# ── datei_ansehen: Pfad-Schutz ─────────────────────────────────────────────

def test_datei_ansehen_liest_text_innerhalb_der_wurzel(speicher):
    datei = speicher / "notiz.txt"
    datei.write_text("Einkaufsliste: Brot", encoding="utf-8")
    e = wz.ausfuehren("datei_ansehen", {"pfad": str(datei)})
    assert e.ok and "Einkaufsliste" in e.text


def test_datei_ansehen_bild_geht_als_bild(speicher):
    bild = speicher / "DCIM" / "IMG_20260930_0925.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    e = wz.ausfuehren("datei_ansehen", {"pfad": str(bild)})
    assert e.ok and len(e.bilder) == 1
    assert e.bilder[0]["data_url"].startswith("data:image/")
    assert "base64" not in e.text  # das Bild steckt nicht im Text


@pytest.mark.parametrize("name", [".env", "config.yaml", "geheim.py", "schluessel.json"])
def test_datei_ansehen_verweigert_fremde_endungen(speicher, name):
    datei = speicher / name
    datei.write_text("API_KEY=sk-geheim", encoding="utf-8")
    e = wz.ausfuehren("datei_ansehen", {"pfad": str(datei)})
    assert not e.ok and "sk-geheim" not in e.text


def test_datei_ansehen_verweigert_pfad_ausserhalb(speicher, tmp_path):
    draussen = tmp_path / "backend" / "notiz.txt"
    draussen.parent.mkdir()
    draussen.write_text("geheimer Inhalt", encoding="utf-8")
    e = wz.ausfuehren("datei_ansehen", {"pfad": str(draussen)})
    assert not e.ok and "geheimer" not in e.text


def test_datei_ansehen_verweigert_ausbruch_mit_punktpunkt(speicher, tmp_path):
    draussen = tmp_path / "geheim.txt"
    draussen.write_text("geheimer Inhalt", encoding="utf-8")
    e = wz.ausfuehren("datei_ansehen", {"pfad": str(speicher / ".." / "geheim.txt")})
    assert not e.ok and "geheimer" not in e.text


def test_datei_ansehen_ohne_pfad():
    assert not wz.ausfuehren("datei_ansehen", {}).ok


# ── Archiv, Erinnerungen, Personen, Tage ───────────────────────────────────

def test_archiv_suchen_nennt_quelle_und_datum(monkeypatch):
    from app.services import archiv_service as modul

    class FakeArchiv:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return [{"source": "ChatGPT", "beginn": "2024-03-01T10:00", "text": "Über Momo gesprochen"}]
    monkeypatch.setattr(modul, "archiv_service", FakeArchiv())
    e = wz.ausfuehren("archiv_suchen", {"frage": "Momo"})
    assert e.ok and "[ChatGPT, 2024-03-01]" in e.text and "Momo" in e.text


def test_archiv_nicht_erreichbar(monkeypatch):
    from app.services import archiv_service as modul

    class Weg:
        is_available = False
    monkeypatch.setattr(modul, "archiv_service", Weg())
    e = wz.ausfuehren("archiv_suchen", {"frage": "x"})
    assert not e.ok and "nicht erreichbar" in e.text


def test_erinnerungen_suchen(monkeypatch):
    from app.services import memory_service as modul

    class FakeMem:
        def retrieve_relevant_memories(self, query, top_k=5):
            return [{"content": "Mag Windsurfen", "art": "vorliebe"}, {"content": ""}]
    monkeypatch.setattr(modul, "memory_service", FakeMem())
    e = wz.ausfuehren("erinnerungen_suchen", {"frage": "Hobby"})
    assert "Mag Windsurfen" in e.text and e.text.count("\n- ") == 1


def test_personen_liste_gibt_keine_vektoren_oder_bilder_heraus(monkeypatch):
    from app.services import gesichter_service
    monkeypatch.setattr(gesichter_service, "liste_personen", lambda: [{
        "name": "Musterperson", "rolle": "Bruder", "embedding": [0.1] * 128,
        "referenz_bild_miniatur": "data:image/jpeg;base64,AAAA",
        "referenz_bild_pfad": "/sdcard/DCIM/x.jpg",
    }])
    e = wz.ausfuehren("personen_liste", {})
    assert "Musterperson" in e.text and "Bruder" in e.text
    for verboten in ("0.1", "base64", "/sdcard", "embedding"):
        assert verboten not in e.text


def test_fotos_mit_person(monkeypatch):
    from app.services import gesicht_fotos
    monkeypatch.setattr(gesicht_fotos, "suche_bilder_mit_person", lambda p, tage=None: {
        "gefunden": [{"name": "Musterperson", "pfad": "/sdcard/DCIM/IMG_1.jpg", "sicher": True}]})
    e = wz.ausfuehren("fotos_mit_person", {"person": "Musterperson", "tage": "7"})
    assert "1 Foto(s)" in e.text and "IMG_1.jpg" in e.text and "sicher" in e.text


def test_wer_war_wann_prueft_datum(monkeypatch):
    from app.services import beziehungen_service
    monkeypatch.setattr(beziehungen_service, "text_antwort", lambda d: f"Belege für {d}")
    assert "Belege für 2022-08-21" in wz.ausfuehren("wer_war_wann", {"datum": "2022-08-21"}).text
    assert not wz.ausfuehren("wer_war_wann", {"datum": "31.02.2020"}).ok


def test_fotos_uebersicht_fehlt(monkeypatch):
    from app.services import foto_uebersicht
    monkeypatch.setattr(foto_uebersicht, "text_antwort", lambda **k: "")
    assert not wz.ausfuehren("fotos_uebersicht", {}).ok
