"""Tests: Erzähl-Diashow (Auftrag E8a, 28.09.2026).

Prüft den Dienst ``app/services/erzaehl_service.py`` und die Endpunkte unter
``/api/erzaehlen``. Alles läuft offline: ``ereignisse.jsonl`` und
``geschichten.jsonl`` werden je Test in ``tmp_path`` erfunden (erfundene
Beispielnamen, keine echten Daten), die Pfade kommen über die Umgebungs-
variablen ``ERZAEHL_EREIGNISSE_PFAD`` / ``ERZAEHL_GESCHICHTEN_PFAD``. Kein
Netz, keine Bilddatei, kein echter Ordner ``~/foto_sortierung``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_erzaehlen.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import erzaehl_service  # noqa: E402

PFAD_EREIGNISSE = "/api/erzaehlen/ereignisse"
PFAD_GESCHICHTEN = "/api/erzaehlen/geschichten"

# Erfundene Ereignisse — eingefrorenes Schema aus
# tools/foto_sortierung/ereignisse_bauen.py.
EREIGNIS_A = {
    "anlass_id": "a1", "kennung": "E-a1", "anzahl_dateien": 3, "art": "anlass",
    "datei_kennungen": [101, 102, 103], "datum": "2021-08-01", "event": "Urlaub Beispiel",
    "event_quelle": "neu", "event_stufe": 1, "jahr": 2021, "kategorie": "Reisen",
    "quellen": ["cloud"], "stand": "2026-09-28T10:00:00+02:00", "thema": "Reisen",
    "ziel_ordner": "2021/Urlaub Beispiel",
}
EREIGNIS_B = {
    "anlass_id": "a2", "kennung": "E-a2", "anzahl_dateien": 1, "art": "anlass",
    "datei_kennungen": [201], "datum": None, "event": None,
    "event_quelle": None, "event_stufe": 0, "jahr": 2020, "kategorie": "WG",
    "quellen": ["cloud"], "stand": "2026-09-28T10:00:00+02:00", "thema": "Haus und Garten",
    "ziel_ordner": "2020/Sonstiges",
}
EREIGNIS_C = {
    "anlass_id": "a3", "kennung": "E-a3", "anzahl_dateien": 0, "art": "anlass",
    "datei_kennungen": [], "datum": None, "event": None, "event_quelle": None,
    "event_stufe": 0, "jahr": 2019, "kategorie": None, "quellen": [],
    "stand": "2026-09-28T10:00:00+02:00", "thema": None, "ziel_ordner": "2019/Sonstiges",
}


def _jsonl_schreiben(pfad: str, zeilen) -> None:
    ordner = os.path.dirname(str(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    with open(str(pfad), "w", encoding="utf-8") as datei:
        for zeile in zeilen:
            if isinstance(zeile, str):
                datei.write(zeile + "\n")
            else:
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")


@pytest.fixture()
def ereignisse_pfad(tmp_path, monkeypatch) -> str:
    ziel = tmp_path / "ereignisse.jsonl"
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ziel))
    return str(ziel)


@pytest.fixture()
def geschichten_pfad(tmp_path, monkeypatch) -> str:
    ziel = tmp_path / "geschichten.jsonl"
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(ziel))
    return str(ziel)


@pytest.fixture()
def mit_ereignissen(ereignisse_pfad) -> str:
    _jsonl_schreiben(ereignisse_pfad, [EREIGNIS_A, EREIGNIS_B, EREIGNIS_C])
    return ereignisse_pfad


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


# ── Pfade ────────────────────────────────────────────────────────────────────

def test_ereignisse_pfad_vorgabe(monkeypatch):
    monkeypatch.delenv("ERZAEHL_EREIGNISSE_PFAD", raising=False)
    erwartet = os.path.join(os.path.expanduser("~"), "foto_sortierung", "ereignisse.jsonl")
    assert erzaehl_service.ereignisse_pfad() == erwartet


def test_geschichten_pfad_vorgabe(monkeypatch):
    monkeypatch.delenv("ERZAEHL_GESCHICHTEN_PFAD", raising=False)
    erwartet = os.path.join(os.path.expanduser("~"), "foto_sortierung", "geschichten.jsonl")
    assert erzaehl_service.geschichten_pfad() == erwartet


def test_pfad_ueber_umgebungsvariable_uebersteuerbar(tmp_path, monkeypatch):
    ziel = tmp_path / "anders.jsonl"
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ziel))
    assert erzaehl_service.ereignisse_pfad() == str(ziel)


def test_leere_umgebungsvariable_zaehlt_nicht(monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", "   ")
    assert "foto_sortierung" in erzaehl_service.ereignisse_pfad()


# ── Dienst: Liste / Filter ───────────────────────────────────────────────────

def test_liste_ohne_datei_ist_leer(ereignisse_pfad):
    ergebnis = erzaehl_service.ereignisse_liste()
    assert ergebnis["eintraege"] == []
    assert ergebnis["gesamt"] == 0
    assert ergebnis["defekte_zeilen"] == 0


def test_liste_findet_alle_ereignisse_ab_min_bilder_1(mit_ereignissen):
    """min_bilder=1 (Standard) blendet das leere Ereignis C aus."""
    ergebnis = erzaehl_service.ereignisse_liste()
    kennungen = {e["kennung"] for e in ergebnis["eintraege"]}
    assert kennungen == {"E-a1", "E-a2"}
    assert ergebnis["gesamt"] == 2


def test_liste_min_bilder_0_zeigt_auch_leeres_ereignis(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(min_bilder=0)
    kennungen = {e["kennung"] for e in ergebnis["eintraege"]}
    assert "E-a3" in kennungen


def test_liste_filtert_nach_jahr(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(jahr=2021)
    assert [e["kennung"] for e in ergebnis["eintraege"]] == ["E-a1"]


def test_liste_filtert_nach_suche_umlauttolerant(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(suche="urlaub")
    assert [e["kennung"] for e in ergebnis["eintraege"]] == ["E-a1"]


def test_liste_titel_faellt_zurueck_auf_thema(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(min_bilder=0)
    eintrag = next(e for e in ergebnis["eintraege"] if e["kennung"] == "E-a2")
    assert eintrag["titel"] == "Haus und Garten"


def test_liste_titel_ohne_titel_faellt_zurueck(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(min_bilder=0)
    eintrag = next(e for e in ergebnis["eintraege"] if e["kennung"] == "E-a3")
    assert eintrag["titel"] == "Ohne Titel"


def test_liste_vorschau_kennungen_erste_vier(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste()
    eintrag = next(e for e in ergebnis["eintraege"] if e["kennung"] == "E-a1")
    assert eintrag["vorschau_kennungen"] == [101, 102, 103]


def test_liste_zaehlt_geschichten_je_ereignis(mit_ereignissen, geschichten_pfad):
    erzaehl_service.geschichte_speichern("E-a1", "Ein schöner Tag.", "tippen")
    erzaehl_service.geschichte_speichern("E-a1", "Noch eine.", "tippen")
    ergebnis = erzaehl_service.ereignisse_liste()
    eintrag = next(e for e in ergebnis["eintraege"] if e["kennung"] == "E-a1")
    assert eintrag["anzahl_geschichten"] == 2


def test_liste_defekte_zeilen_werden_gezaehlt_nicht_geworfen(ereignisse_pfad):
    _jsonl_schreiben(ereignisse_pfad, [EREIGNIS_A, "{kein json", "", "  ", "42"])
    ergebnis = erzaehl_service.ereignisse_liste(min_bilder=0)
    assert ergebnis["defekte_zeilen"] == 2  # "{kein json" + "42" (kein dict)
    assert ergebnis["gesamt"] == 1


def test_liste_limit_und_offset(mit_ereignissen):
    ergebnis = erzaehl_service.ereignisse_liste(min_bilder=0, limit=1, offset=1)
    assert len(ergebnis["eintraege"]) == 1
    assert ergebnis["gesamt"] == 3


# ── Dienst: Detail ───────────────────────────────────────────────────────────

def test_detail_liefert_alle_datei_kennungen(mit_ereignissen):
    detail = erzaehl_service.ereignis_detail("E-a1")
    assert detail is not None
    assert detail["datei_kennungen"] == [101, 102, 103]
    assert detail["titel"] == "Urlaub Beispiel"


def test_detail_unbekannte_kennung_ist_none(mit_ereignissen):
    assert erzaehl_service.ereignis_detail("E-unbekannt") is None


def test_detail_traegt_geschichten(mit_ereignissen, geschichten_pfad):
    erzaehl_service.geschichte_speichern("E-a1", "Wunderschöner Strand.", "tippen", datei_kennung=101)
    detail = erzaehl_service.ereignis_detail("E-a1")
    assert len(detail["geschichten"]) == 1
    assert detail["geschichten"][0]["text"] == "Wunderschöner Strand."


# ── Dienst: Speichern (Validierung) ──────────────────────────────────────────

def test_speichern_ok_schreibt_zeile(mit_ereignissen, geschichten_pfad):
    zeile = erzaehl_service.geschichte_speichern("E-a1", "Hallo Welt.", "tippen", datei_kennung=101)
    assert zeile["ereignis_kennung"] == "E-a1"
    assert zeile["datei_kennung"] == 101
    assert zeile["schicht"] == "mensch"
    assert zeile["ersetzt"] is None
    assert os.path.isfile(geschichten_pfad)
    with open(geschichten_pfad, "r", encoding="utf-8") as datei:
        zeilen = [l for l in datei if l.strip()]
    assert len(zeilen) == 1


def test_speichern_ohne_datei_kennung_ist_erlaubt(mit_ereignissen, geschichten_pfad):
    zeile = erzaehl_service.geschichte_speichern("E-a1", "Nur zum Ereignis.", "tippen")
    assert zeile["datei_kennung"] is None


def test_speichern_bild_nicht_im_ereignis_ist_fehler(mit_ereignissen, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="gehört nicht"):
        erzaehl_service.geschichte_speichern("E-a1", "Text.", "tippen", datei_kennung=999)


def test_speichern_leerer_text_ist_fehler(mit_ereignissen, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="leer"):
        erzaehl_service.geschichte_speichern("E-a1", "   ", "tippen")


def test_speichern_zu_langer_text_ist_fehler(mit_ereignissen, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="zu lang"):
        erzaehl_service.geschichte_speichern("E-a1", "x" * 20_001, "tippen")


def test_speichern_grenzwert_20000_ist_erlaubt(mit_ereignissen, geschichten_pfad):
    zeile = erzaehl_service.geschichte_speichern("E-a1", "x" * 20_000, "tippen")
    assert len(zeile["text"]) == 20_000


def test_speichern_unbekanntes_ereignis_ist_fehler(ereignisse_pfad, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="existiert nicht"):
        erzaehl_service.geschichte_speichern("E-unbekannt", "Text.", "tippen")


def test_speichern_ungueltige_quelle_ist_fehler(mit_ereignissen, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="Quelle"):
        erzaehl_service.geschichte_speichern("E-a1", "Text.", "video")


@pytest.mark.parametrize("quelle", ["tippen", "sprache", "import"])
def test_speichern_erlaubte_quellen(mit_ereignissen, geschichten_pfad, quelle):
    """Nachtrag Planer 28.09.2026: 'import' ist zusätzlich erlaubt (spätere
    Übernahme von Erzählungen aus Hermes). Die Oberfläche setzt weiterhin nur
    tippen/sprache — die Validierung akzeptiert aber auch 'import'."""
    zeile = erzaehl_service.geschichte_speichern("E-a1", "Text.", quelle)
    assert zeile["quelle"] == quelle


def test_speichern_ersetzt_unbekannte_id_ist_fehler(mit_ereignissen, geschichten_pfad):
    with pytest.raises(erzaehl_service.GeschichteValidierungsfehler, match="existiert nicht"):
        erzaehl_service.geschichte_speichern("E-a1", "Text.", "tippen", ersetzt="unbekannte-id")


def test_speichern_ersetzt_bekannte_id_ist_ok(mit_ereignissen, geschichten_pfad):
    alt = erzaehl_service.geschichte_speichern("E-a1", "Erste Fassung.", "tippen")
    neu = erzaehl_service.geschichte_speichern("E-a1", "Korrigierte Fassung.", "tippen", ersetzt=alt["id"])
    assert neu["ersetzt"] == alt["id"]


def test_speichern_ist_nur_anhaengend_alte_bytes_unveraendert(mit_ereignissen, geschichten_pfad):
    erzaehl_service.geschichte_speichern("E-a1", "Erste.", "tippen")
    with open(geschichten_pfad, "rb") as datei:
        alte_bytes = datei.read()
    erzaehl_service.geschichte_speichern("E-a1", "Zweite.", "tippen")
    with open(geschichten_pfad, "rb") as datei:
        neue_bytes = datei.read()
    assert neue_bytes.startswith(alte_bytes)
    assert len(neue_bytes) > len(alte_bytes)


def test_liste_zeigt_nur_neueste_fassung(mit_ereignissen, geschichten_pfad):
    alt = erzaehl_service.geschichte_speichern("E-a1", "Erste Fassung.", "tippen")
    erzaehl_service.geschichte_speichern("E-a1", "Korrigierte Fassung.", "tippen", ersetzt=alt["id"])
    aktuelle = erzaehl_service.geschichten(ereignis_kennung="E-a1")
    assert len(aktuelle) == 1
    assert aktuelle[0]["text"] == "Korrigierte Fassung."


def test_geschichten_filter_nach_datei_kennung(mit_ereignissen, geschichten_pfad):
    erzaehl_service.geschichte_speichern("E-a1", "Zu Bild 101.", "tippen", datei_kennung=101)
    erzaehl_service.geschichte_speichern("E-a1", "Zu Bild 102.", "tippen", datei_kennung=102)
    ergebnis = erzaehl_service.geschichten(datei_kennung=101)
    assert len(ergebnis) == 1
    assert ergebnis[0]["text"] == "Zu Bild 101."


# ── Router: GET /api/erzaehlen/ereignisse ────────────────────────────────────

def test_route_ereignisse_ohne_datei_meldet_ok_false(client, ereignisse_pfad):
    res = client.get(PFAD_EREIGNISSE)
    assert res.status_code == 200
    daten = res.json()
    assert daten["ok"] is False
    assert isinstance(daten["error"], str) and "noch nicht vorhanden" in daten["error"]
    assert daten["eintraege"] == []


def test_route_ereignisse_mit_datei(client, mit_ereignissen):
    res = client.get(PFAD_EREIGNISSE)
    assert res.status_code == 200
    daten = res.json()
    assert daten["ok"] is True
    assert daten["gesamt"] == 2
    assert daten["error"] is None


def test_route_ereignisse_filter_jahr(client, mit_ereignissen):
    res = client.get(PFAD_EREIGNISSE, params={"jahr": 2021})
    daten = res.json()
    assert [e["kennung"] for e in daten["eintraege"]] == ["E-a1"]


def test_route_ereignis_detail_unbekannt(client, mit_ereignissen):
    res = client.get(PFAD_EREIGNISSE + "/E-unbekannt")
    assert res.status_code == 200
    daten = res.json()
    assert daten["ok"] is False
    assert "nicht gefunden" in daten["error"]


def test_route_ereignis_detail_gefunden(client, mit_ereignissen):
    res = client.get(PFAD_EREIGNISSE + "/E-a1")
    assert res.status_code == 200
    daten = res.json()
    assert daten["ok"] is True
    assert daten["ereignis"]["kennung"] == "E-a1"
    assert daten["ereignis"]["datei_kennungen"] == [101, 102, 103]


def test_route_ereignis_detail_ohne_ereignisdatei(client, ereignisse_pfad):
    res = client.get(PFAD_EREIGNISSE + "/E-a1")
    daten = res.json()
    assert daten["ok"] is False
    assert "noch nicht vorhanden" in daten["error"]


# ── Router: POST/GET /api/erzaehlen/geschichten ──────────────────────────────

def test_route_post_geschichte_ok(client, mit_ereignissen, geschichten_pfad):
    res = client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "Ein toller Tag.", "quelle": "tippen",
        "datei_kennung": 101,
    })
    assert res.status_code == 200
    daten = res.json()
    assert daten["ok"] is True
    assert daten["geschichte"]["text"] == "Ein toller Tag."


def test_route_post_geschichte_bild_nicht_im_ereignis_400(client, mit_ereignissen, geschichten_pfad):
    res = client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "Text.", "quelle": "tippen", "datei_kennung": 999,
    })
    assert res.status_code == 400
    assert "gehört nicht" in res.json()["detail"]


def test_route_post_geschichte_leerer_text_400(client, mit_ereignissen, geschichten_pfad):
    res = client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "   ", "quelle": "tippen",
    })
    assert res.status_code == 400


def test_route_post_geschichte_zu_langer_text_400(client, mit_ereignissen, geschichten_pfad):
    res = client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "x" * 20_001, "quelle": "tippen",
    })
    assert res.status_code == 400


def test_route_post_geschichte_import_quelle_ok(client, mit_ereignissen, geschichten_pfad):
    """Nachtrag Planer: 'import' ist über die POST-Route ebenfalls gültig."""
    res = client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "Übernommen aus Hermes.", "quelle": "import",
    })
    assert res.status_code == 200
    assert res.json()["geschichte"]["quelle"] == "import"


def test_route_get_geschichten_gefiltert(client, mit_ereignissen, geschichten_pfad):
    client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a1", "text": "A", "quelle": "tippen", "datei_kennung": 101,
    })
    client.post(PFAD_GESCHICHTEN, json={
        "ereignis_kennung": "E-a2", "text": "B", "quelle": "sprache",
    })
    res = client.get(PFAD_GESCHICHTEN, params={"ereignis_kennung": "E-a1"})
    daten = res.json()
    assert daten["ok"] is True
    assert len(daten["geschichten"]) == 1
    assert daten["geschichten"][0]["text"] == "A"


def test_route_haengt_am_api_key_schutz():
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == PFAD_EREIGNISSE:
            namen = [getattr(d.dependency, "__name__", "") for d in route.dependencies]
            assert "require_api_key" in namen, f"Key-Schutz fehlt: {namen}"
            return
    pytest.fail("Route /api/erzaehlen/ereignisse nicht gefunden")


def test_route_ohne_api_key_401(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    alt = settings.api_key
    settings.api_key = "test-key-nicht-echt"
    try:
        pruefer = TestClient(app)
        res = pruefer.get(PFAD_EREIGNISSE)
        assert res.status_code == 401
    finally:
        settings.api_key = alt
