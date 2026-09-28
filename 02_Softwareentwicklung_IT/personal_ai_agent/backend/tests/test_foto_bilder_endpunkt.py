"""Tests: Bilder am Handy — Dienst + Endpunkt (N13a, Teil B, 28.09.2026).

Prüft den Dienst ``app/services/foto_bilder.py`` und den Endpunkt
``GET /api/fotos/bilder``.

Alles läuft offline: Die Kennungsdatei wird für jeden Test in ``tmp_path``
erfunden (erfundene Event-Namen und erfundene Kennungen, kein echter Bestand),
der Pfad kommt über die Umgebungsvariable ``FOTO_DATEIEN_PFAD``. Kein Netz,
kein pCloud-Aufruf, keine Bilddatei. Ein Test ersetzt ``socket.socket`` durch
eine Stolperfalle, die jeden echten Ausgeh-Versuch sofort scheitern lässt.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_bilder_endpunkt.py -q
"""
from __future__ import annotations

import ast
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app.services import foto_bilder  # noqa: E402

PFAD = "/api/fotos/bilder"
DIENST_DATEI = os.path.join(BACKEND, "app", "services", "foto_bilder.py")
ROUTER_DATEI = os.path.join(BACKEND, "app", "router", "fotos.py")

# Die Felder, die der Endpunkt IMMER liefern muss.
ANTWORT_FELDER = {"ok", "quelle", "stand", "zahlen", "events", "anzahl", "error"}

# Die Schlüssel einer Event-Zeile und eines Datei-Eintrags — immer dieselben.
EVENT_FELDER = {"jahr", "kategorie", "event", "anzahl", "dateien"}
DATEI_FELDER = {"datei_id", "name"}

# Die Schlüssel des Selbsttest-Blocks — immer dieselben.
STATUS_FELDER = {"ok", "quelle", "stand", "events", "dateien", "error"}

# Die Schlüssel der Kennungsdatei (Vorgabe des Schemas).
DATEIEN_SCHLUESSEL = {"art", "version", "stand", "plan_stand", "zahlen", "events"}

STAND = "2026-09-28T09:40:00+02:00"

# Erfundene Event-Namen.
EVENT_KONZERT = "2020-05-01 Konzert Beispiel"
EVENT_URLAUB_2020 = "2020-08-01 Urlaub Beispiel"
EVENT_PRUEFUNG = "2021-03-01 Prüfung Beispiel"
EVENT_URLAUB_2021 = "2021-07-01 Urlaub Beispiel"


def _dateien(prefix: str, anzahl: int, ab: int) -> list:
    """Erfundene Datei-Einträge: Kennung und Name, sonst nichts."""
    return [{"datei_id": 900000000 + ab + i,
             "name": f"Beispiel-{prefix}-{i + 1:02d}.jpg"} for i in range(anzahl)]


# Eine ERFUNDENE Kennungsdatei: erfundene Event-Namen, erfundene Kennungen,
# kein echter Ordner, keine Bilddatei. Die Zahlen sind untereinander stimmig
# (4 Events, 12 Dateien, 2 Kategorien, 2 Jahre).
DATEIEN = {
    "art": "foto_dateien",
    "version": 1,
    "stand": STAND,
    "plan_stand": "2026-09-27T13:49:46+02:00",
    "zahlen": {"events": 4, "dateien": 12, "ohne_kennung": 0,
               "kategorien": 2, "jahre": 2},
    "events": [
        {"jahr": 2020, "kategorie": "WG", "event": EVENT_KONZERT,
         "anzahl": 3, "dateien": _dateien("konzert", 3, 0)},
        {"jahr": 2020, "kategorie": "Reisen", "event": EVENT_URLAUB_2020,
         "anzahl": 3, "dateien": _dateien("urlaub-2020", 3, 10)},
        {"jahr": 2021, "kategorie": "WG", "event": EVENT_PRUEFUNG,
         "anzahl": 3, "dateien": _dateien("pruefung", 3, 20)},
        {"jahr": 2021, "kategorie": "Reisen", "event": EVENT_URLAUB_2021,
         "anzahl": 3, "dateien": _dateien("urlaub-2021", 3, 30)},
    ],
}


# ── Aufbau ───────────────────────────────────────────────────────────────────

def _netz_sperren(monkeypatch, *, nur_aussen: bool = False) -> None:
    """Jeden echten Verbindungsaufbau scheitern lassen.

    ``nur_aussen`` sperrt ausschließlich Namensauflösung und
    Verbindungsaufbau nach draußen. Das braucht der TestClient: Er läuft
    zwar in-process, legt unter Windows aber für seine Ereignisschleife ein
    lokales Socket-Paar an. Ein echter Ausgeh-Versuch (auch ein LLM- oder
    pCloud-Aufruf) würde in beiden Fällen sofort auffliegen.
    """
    import socket

    def kein_ausgang(*args, **kwargs):
        raise AssertionError("Echter Netz-Call versucht (Verbindungsaufbau)")

    if not nur_aussen:
        monkeypatch.setattr(socket.socket, "connect", kein_ausgang)
        monkeypatch.setattr(socket.socket, "connect_ex", kein_ausgang)
    monkeypatch.setattr(socket, "create_connection", kein_ausgang, raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", kein_ausgang, raising=False)


def _schreiben(pfad: str, daten) -> str:
    """Testdatei anlegen (dict -> JSON, str -> roh) und den Pfad zurückgeben."""
    with open(str(pfad), "w", encoding="utf-8") as datei:
        if isinstance(daten, str):
            datei.write(daten)
        else:
            json.dump(daten, datei, ensure_ascii=False)
    return str(pfad)


@pytest.fixture()
def pfad(tmp_path, monkeypatch) -> str:
    """Umgebungsvariable auf einen (noch leeren) temporären Pfad zeigen lassen."""
    ziel = tmp_path / "fotos_dateien.json"
    monkeypatch.setenv("FOTO_DATEIEN_PFAD", str(ziel))
    return str(ziel)


@pytest.fixture()
def mit_dateien(pfad) -> str:
    """Die erfundene Kennungsdatei liegt bereit; die Umgebungsvariable zeigt darauf."""
    return _schreiben(pfad, DATEIEN)


@pytest.fixture()
def client(monkeypatch):
    """TestClient gegen die echte App, ohne API-Key-Schutz der .env."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


def _route(gesucht: str):
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == gesucht and "GET" in getattr(route, "methods", set()):
            return route
    return None


# ── Pfad ─────────────────────────────────────────────────────────────────────

def test_pfad_vorgabe_ist_der_sortierordner(monkeypatch):
    """Ohne Umgebungsvariable gilt ``~/foto_sortierung/fotos_dateien.json``."""
    monkeypatch.delenv("FOTO_DATEIEN_PFAD", raising=False)
    erwartet = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                            "fotos_dateien.json")
    assert foto_bilder.dateien_pfad() == erwartet


def test_pfad_ist_ueber_umgebungsvariable_uebersteuerbar(monkeypatch, tmp_path):
    """Für Tests (und ein anderes Gerät) lässt sich der Ort umbiegen."""
    ziel = tmp_path / "anders.json"
    monkeypatch.setenv("FOTO_DATEIEN_PFAD", str(ziel))
    assert foto_bilder.dateien_pfad() == str(ziel)


def test_leere_umgebungsvariable_zaehlt_nicht(monkeypatch):
    """Ein leerer Wert ist kein Pfad — dann gilt die Vorgabe."""
    monkeypatch.setenv("FOTO_DATEIEN_PFAD", "   ")
    assert foto_bilder.dateien_pfad().endswith("fotos_dateien.json")
    assert "foto_sortierung" in foto_bilder.dateien_pfad()


def test_konstanten_passen_zum_schema():
    assert foto_bilder.DATEIEN_DATEINAME == "fotos_dateien.json"
    assert foto_bilder.DATEIEN_ORDNER == "foto_sortierung"
    assert foto_bilder.ERWARTETE_VERSION == 1
    assert foto_bilder.ERWARTETE_ART == "foto_dateien"


def test_grenzen_sind_fest():
    assert (foto_bilder.LIMIT_MIN, foto_bilder.LIMIT_MAX) == (1, 50)
    assert (foto_bilder.PRO_EVENT_MIN, foto_bilder.PRO_EVENT_MAX) == (1, 200)


# ── Laden: Erfolg ────────────────────────────────────────────────────────────

def test_laden_liefert_immer_dieselben_schluessel(mit_dateien):
    assert set(foto_bilder.dateien_laden().keys()) == {
        "existiert", "pfad", "stand", "zahlen", "events", "error"}


def test_laden_liefert_immer_dieselben_schluessel_auch_ohne_datei(pfad):
    assert set(foto_bilder.dateien_laden().keys()) == {
        "existiert", "pfad", "stand", "zahlen", "events", "error"}


def test_laden_liefert_inhalt_und_existiert(mit_dateien):
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is True
    assert daten["error"] is None
    assert daten["stand"] == STAND
    assert daten["zahlen"]["events"] == 4
    assert daten["zahlen"]["dateien"] == 12
    assert len(daten["events"]) == 4
    assert daten["pfad"] == mit_dateien


def test_laden_mit_explizitem_pfad_ignoriert_umgebung(pfad, tmp_path, monkeypatch):
    """Der ``pfad``-Parameter hat Vorrang vor der Umgebungsvariable."""
    anderer = _schreiben(tmp_path / "zweite.json", DATEIEN)
    monkeypatch.setenv("FOTO_DATEIEN_PFAD", pfad)     # zeigt auf die leere Datei
    daten = foto_bilder.dateien_laden(anderer)
    assert daten["existiert"] is True
    assert daten["pfad"] == anderer


def test_laden_nennt_stand_und_zahlen_getrennt(mit_dateien):
    daten = foto_bilder.dateien_laden()
    assert daten["zahlen"]["kategorien"] == 2
    assert daten["zahlen"]["jahre"] == 2
    assert daten["zahlen"]["ohne_kennung"] == 0


def test_laden_ohne_zahlenblock_bleibt_stabil(pfad):
    _schreiben(pfad, {"art": "foto_dateien", "version": 1, "stand": STAND,
                      "events": []})
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is True
    assert daten["zahlen"] == {}
    assert daten["events"] == []


def test_laden_ohne_event_liste_bleibt_stabil(pfad):
    _schreiben(pfad, {"art": "foto_dateien", "version": 1, "stand": STAND,
                      "zahlen": {"events": 0, "dateien": 0}, "events": "kaputt"})
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is True
    assert daten["events"] == []


def test_laden_ohne_stand_ist_none(pfad):
    _schreiben(pfad, {"art": "foto_dateien", "version": 1, "events": []})
    assert foto_bilder.dateien_laden()["stand"] is None


# ── Laden: Fehlerfälle (immer ohne Wurf) ─────────────────────────────────────

def test_fehlende_datei_gibt_existiert_false_und_deutschen_text(pfad):
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is False
    assert isinstance(daten["error"], str) and daten["error"].strip()
    assert "nicht gefunden" in daten["error"]
    assert daten["events"] == [] and daten["zahlen"] == {}


def test_fehlendes_verzeichnis_wirft_nicht(tmp_path, monkeypatch):
    monkeypatch.setenv("FOTO_DATEIEN_PFAD", str(tmp_path / "gibtsnicht" / "x.json"))
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is False
    assert daten["error"]


def test_kaputtes_json_gibt_fehlertext_statt_wurf(pfad):
    _schreiben(pfad, "{kein json")
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is False
    assert "JSON" in daten["error"]


def test_json_liste_statt_objekt_wird_gemeldet(pfad):
    _schreiben(pfad, [1, 2, 3])
    daten = foto_bilder.dateien_laden()
    assert daten["existiert"] is False
    assert "Format" in daten["error"]


def test_fremde_art_wird_gemeldet(pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["art"] = "etwas_anderes"
    _schreiben(pfad, daten_roh)
    ergebnis = foto_bilder.dateien_laden()
    assert ergebnis["existiert"] is False
    assert "Art" in ergebnis["error"]
    assert ergebnis["events"] == []


def test_fehlende_art_wird_gemeldet(pfad):
    _schreiben(pfad, {"version": 1, "events": []})
    ergebnis = foto_bilder.dateien_laden()
    assert ergebnis["existiert"] is False
    assert "Art" in ergebnis["error"]


def test_fremde_schema_version_wird_gemeldet(pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["version"] = 99
    _schreiben(pfad, daten_roh)
    ergebnis = foto_bilder.dateien_laden()
    assert ergebnis["existiert"] is False
    assert "Version" in ergebnis["error"]


def test_fehlende_schema_version_wird_gemeldet(pfad):
    _schreiben(pfad, {"art": "foto_dateien", "events": []})
    assert foto_bilder.dateien_laden()["existiert"] is False


def test_version_als_text_wird_gelesen(pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["version"] = "1"
    _schreiben(pfad, daten_roh)
    assert foto_bilder.dateien_laden()["existiert"] is True


def test_leere_datei_gibt_fehlertext(pfad):
    _schreiben(pfad, "")
    ergebnis = foto_bilder.dateien_laden()
    assert ergebnis["existiert"] is False
    assert ergebnis["error"]


def test_ordner_statt_datei_ist_kein_wurf(pfad):
    os.makedirs(pfad, exist_ok=True)
    ergebnis = foto_bilder.dateien_laden()
    assert ergebnis["existiert"] is False


# ── status_block ─────────────────────────────────────────────────────────────

def test_status_block_hat_im_erfolgsfall_alle_schluessel(mit_dateien):
    assert set(foto_bilder.status_block().keys()) == STATUS_FELDER


def test_status_block_hat_im_fehlerfall_alle_schluessel(pfad):
    assert set(foto_bilder.status_block().keys()) == STATUS_FELDER


def test_status_block_ist_ok_und_nennt_quelle(mit_dateien):
    block = foto_bilder.status_block()
    assert block["ok"] is True
    assert block["error"] is None
    assert block["quelle"] == "fotos_dateien.json"
    assert os.sep not in (block["quelle"] or "")


def test_status_block_quelle_steht_auch_wenn_die_datei_fehlt(pfad):
    """Der Selbsttest soll die Quelle nennen können, auch wenn sie fehlt."""
    block = foto_bilder.status_block()
    assert block["ok"] is False
    assert block["quelle"] == "fotos_dateien.json"
    assert block["error"]
    assert block["events"] is None and block["dateien"] is None


def test_status_block_uebernimmt_zahlen_und_stand(mit_dateien):
    block = foto_bilder.status_block()
    assert block["stand"] == STAND
    assert block["events"] == 4
    assert block["dateien"] == 12


def test_status_block_zaehlt_events_aus_der_liste_wenn_die_zahl_fehlt(pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    del daten_roh["zahlen"]["events"]
    del daten_roh["zahlen"]["dateien"]
    _schreiben(pfad, daten_roh)
    block = foto_bilder.status_block()
    assert block["events"] == 4
    assert block["dateien"] == 12      # Summe der `anzahl`-Felder


def test_status_block_wirft_auch_bei_kaputter_datei_nicht(pfad):
    _schreiben(pfad, "@@@")
    block = foto_bilder.status_block()
    assert set(block.keys()) == STATUS_FELDER
    assert block["ok"] is False
    assert block["error"]


# ── bilder_finden: Filter ────────────────────────────────────────────────────

def test_bilder_ohne_filter_kommen_alle(mit_dateien):
    treffer = foto_bilder.bilder_finden()
    assert len(treffer) == 4
    assert [t["event"] for t in treffer] == [t["event"] for t in DATEIEN["events"]]


def test_trefferzeile_hat_immer_dieselben_schluessel(mit_dateien):
    for treffer in foto_bilder.bilder_finden():
        assert set(treffer.keys()) == EVENT_FELDER


def test_dateieintrag_hat_immer_dieselben_schluessel(mit_dateien):
    for treffer in foto_bilder.bilder_finden():
        for datei in treffer["dateien"]:
            assert set(datei.keys()) == DATEI_FELDER


def test_bilder_jahr_filter(mit_dateien):
    treffer = foto_bilder.bilder_finden(jahr=2021)
    assert len(treffer) == 2
    assert all(t["jahr"] == 2021 for t in treffer)


def test_bilder_jahr_als_text_ist_lesbar(mit_dateien):
    assert len(foto_bilder.bilder_finden(jahr="2020")) == 2


def test_bilder_kategorie_ignoriert_gross_klein(mit_dateien):
    treffer = foto_bilder.bilder_finden(kategorie="reisen")
    assert len(treffer) == 2
    assert all(t["kategorie"] == "Reisen" for t in treffer)


def test_bilder_suche_ignoriert_gross_klein(mit_dateien):
    assert len(foto_bilder.bilder_finden(suche="URLAUB")) == 2


def test_bilder_event_filter_sucht_im_eventnamen(mit_dateien):
    treffer = foto_bilder.bilder_finden(event="Konzert")
    assert len(treffer) == 1
    assert treffer[0]["event"] == EVENT_KONZERT


def test_bilder_suche_toleriert_umlaut_auf_der_suchseite(mit_dateien):
    """„prüfung" findet „Prüfung" (Umlaut identisch)."""
    assert len(foto_bilder.bilder_finden(suche="prüfung")) == 1


def test_bilder_suche_toleriert_umlaut_als_ae_oe_ue(mit_dateien):
    """„pruefung" findet ebenfalls „Prüfung"."""
    treffer = foto_bilder.bilder_finden(suche="pruefung")
    assert len(treffer) == 1
    assert treffer[0]["event"].endswith("Prüfung Beispiel")


def test_bilder_event_hat_vorrang_vor_suche(mit_dateien):
    """Beide filtern denselben Namen — ``event`` gewinnt."""
    treffer = foto_bilder.bilder_finden(event="Urlaub", suche="Pruefung")
    assert len(treffer) == 2
    assert all("Urlaub" in t["event"] for t in treffer)


def test_bilder_jahr_und_kategorie_kombiniert(mit_dateien):
    treffer = foto_bilder.bilder_finden(jahr=2021, kategorie="WG")
    assert len(treffer) == 1
    assert treffer[0]["event"] == EVENT_PRUEFUNG


def test_bilder_jahr_und_ereignis_kombiniert(mit_dateien):
    treffer = foto_bilder.bilder_finden(jahr=2020, suche="urlaub")
    assert len(treffer) == 1
    assert treffer[0]["event"] == EVENT_URLAUB_2020


def test_bilder_unbekannte_kategorie_ergibt_leere_liste(mit_dateien):
    assert foto_bilder.bilder_finden(kategorie="GibtEsNicht") == []


def test_bilder_unbekanntes_jahr_ergibt_leere_liste(mit_dateien):
    assert foto_bilder.bilder_finden(jahr=1999) == []


def test_bilder_leerer_suchtext_filtert_nicht(mit_dateien):
    assert len(foto_bilder.bilder_finden(suche="   ")) == 4


def test_bilder_limit_null_wird_auf_eins_angehoben(mit_dateien):
    assert len(foto_bilder.bilder_finden(limit=0)) == 1


def test_bilder_limit_negativ_wird_auf_eins_angehoben(mit_dateien):
    assert len(foto_bilder.bilder_finden(limit=-7)) == 1


def test_bilder_limit_oben_bei_50_begrenzt(mit_dateien):
    """500 ist erlaubt, wird aber auf 50 gekappt — hier sind es nur 4 Treffer."""
    assert len(foto_bilder.bilder_finden(limit=500)) == 4


def test_bilder_limit_unsinn_faellt_auf_standard_zurueck(mit_dateien):
    assert len(foto_bilder.bilder_finden(limit="quatsch")) == 4


def test_bilder_standard_limit_ist_fuenf(mit_dateien):
    assert foto_bilder.LIMIT_STANDARD == 5
    assert len(foto_bilder.bilder_finden()) == 4


def test_bilder_limit_begrenzt_auf_die_trefferzahl(mit_dateien):
    assert len(foto_bilder.bilder_finden(limit=2)) == 2


def test_bilder_ohne_datei_ergibt_leere_liste(pfad):
    assert foto_bilder.bilder_finden() == []


def test_bilder_liefert_kopien_nicht_die_dateiobjekte(mit_dateien):
    treffer = foto_bilder.bilder_finden()
    treffer[0]["event"] = "geaendert"
    assert foto_bilder.bilder_finden()[0]["event"] != "geaendert"


def test_bilder_finden_wirft_bei_kaputter_datei_nicht(pfad):
    _schreiben(pfad, "{{")
    assert foto_bilder.bilder_finden() == []


# ── bilder_finden: pro_event ─────────────────────────────────────────────────

def test_pro_event_kuerzt_die_dateiliste(mit_dateien):
    treffer = foto_bilder.bilder_finden(event="Urlaub", pro_event=1)
    assert len(treffer) == 2
    for zeile in treffer:
        assert len(zeile["dateien"]) == 1
        assert zeile["anzahl"] == 3          # Gesamtzahl bleibt die echte


def test_pro_event_null_wird_auf_eins_angehoben(mit_dateien):
    assert len(foto_bilder.bilder_finden(pro_event=0)[0]["dateien"]) == 1


def test_pro_event_negativ_wird_auf_eins_angehoben(mit_dateien):
    assert len(foto_bilder.bilder_finden(pro_event=-3)[0]["dateien"]) == 1


def test_pro_event_oben_bei_200_begrenzt(mit_dateien):
    assert len(foto_bilder.bilder_finden(pro_event=999)[0]["dateien"]) == 3


def test_pro_event_unsinn_faellt_auf_standard_zurueck(mit_dateien):
    assert foto_bilder.PRO_EVENT_STANDARD == 40
    assert len(foto_bilder.bilder_finden(pro_event="viel")[0]["dateien"]) == 3


def test_pro_event_gibt_die_ersten_dateien_in_dateireihenfolge(mit_dateien):
    zeile = foto_bilder.bilder_finden(event="Konzert", pro_event=1)[0]
    assert zeile["dateien"] == [DATEIEN["events"][0]["dateien"][0]]


def test_anzahl_ohne_anzahlfeld_ist_die_listenlaenge(pfad):
    """Fehlt ``anzahl``, zählt die echte Länge — keine erfundene Zahl."""
    daten_roh = json.loads(json.dumps(DATEIEN))
    del daten_roh["events"][0]["anzahl"]
    _schreiben(pfad, daten_roh)
    assert foto_bilder.bilder_finden(event="Konzert")[0]["anzahl"] == 3


def test_datei_ohne_kennung_wird_verworfen(pfad):
    """Ein Eintrag ohne verwertbare Kennung ist kein Bild und fliegt raus."""
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["events"][0]["dateien"].append({"name": "ohne-kennung.jpg"})
    _schreiben(pfad, daten_roh)
    zeile = foto_bilder.bilder_finden(event="Konzert")[0]
    assert len(zeile["dateien"]) == 3
    assert all(isinstance(d["datei_id"], int) for d in zeile["dateien"])


# ── Endpunkt ─────────────────────────────────────────────────────────────────

def test_route_ist_eingehaengt():
    assert _route(PFAD) is not None, f"{PFAD} fehlt in der App"


def test_route_haengt_am_api_key_schutz():
    route = _route(PFAD)
    assert route is not None
    namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
    assert "require_api_key" in namen, f"Key-Schutz fehlt (Abhängigkeiten: {namen})"


def test_endpunkt_antwortet_200_mit_erfundenen_kennungen(client, mit_dateien):
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is True
    assert daten["error"] is None
    assert daten["stand"] == STAND
    assert daten["zahlen"] == {"events": 4, "dateien": 12}
    assert daten["anzahl"] == 4
    assert len(daten["events"]) == 4


def test_endpunkt_traegt_immer_alle_felder(client, pfad):
    """Auch im Fehlerfall: dieselben Schlüssel, kein 500er."""
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert set(antwort.json().keys()) == ANTWORT_FELDER


def test_endpunkt_traegt_mit_datei_alle_felder(client, mit_dateien):
    assert set(client.get(PFAD).json().keys()) == ANTWORT_FELDER


def test_endpunkt_eventzeile_hat_immer_dieselben_felder(client, mit_dateien):
    for treffer in client.get(PFAD).json()["events"]:
        assert set(treffer.keys()) == EVENT_FELDER


def test_endpunkt_dateieintrag_hat_immer_dieselben_felder(client, mit_dateien):
    daten = client.get(PFAD).json()
    for treffer in daten["events"]:
        assert treffer["dateien"], "jeder Event soll Dateien zeigen"
        for datei in treffer["dateien"]:
            assert set(datei.keys()) == DATEI_FELDER


def test_endpunkt_fehlerfall_ok_falsch_und_deutscher_text(client, pfad):
    daten = client.get(PFAD).json()
    assert daten["ok"] is False
    assert daten["error"]
    assert "nicht gefunden" in daten["error"]
    assert daten["events"] == []
    assert daten["anzahl"] == 0
    assert daten["zahlen"] == {}


def test_endpunkt_nennt_die_quelle_als_dateinamen(client, mit_dateien):
    assert client.get(PFAD).json()["quelle"] == "fotos_dateien.json"


def test_endpunkt_nennt_die_quelle_auch_wenn_die_datei_fehlt(client, pfad):
    assert client.get(PFAD).json()["quelle"] == "fotos_dateien.json"


def test_endpunkt_jahresfilter_greift(client, mit_dateien):
    daten = client.get(PFAD, params={"jahr": 2020}).json()
    assert daten["ok"] is True
    assert daten["anzahl"] == 2
    assert all(e["jahr"] == 2020 for e in daten["events"])


def test_endpunkt_kategoriefilter_greift(client, mit_dateien):
    daten = client.get(PFAD, params={"kategorie": "reisen"}).json()
    assert daten["anzahl"] == 2
    assert all(e["kategorie"] == "Reisen" for e in daten["events"])


def test_endpunkt_ignoriert_unbekannte_parameter(client, mit_dateien):
    """Nur die eingefrorenen Parameter wirken — dieser Endpunkt hat kein ``suche``.

    Die Volltextsuche gibt es im Dienst (``bilder_finden(suche=…)``); der
    Endpunkt reicht laut Auftrag nur ``jahr``, ``kategorie``, ``event``,
    ``limit`` und ``pro_event`` durch. Ein ``suche``-Parameter wird deshalb
    (wie bei FastAPI üblich) still ignoriert, nicht als Fehler behandelt.
    """
    daten = client.get(PFAD, params={"suche": "pruefung"}).json()
    assert daten["anzahl"] == 4


def test_endpunkt_eventfilter_greift(client, mit_dateien):
    daten = client.get(PFAD, params={"event": "urlaub"}).json()
    assert daten["anzahl"] == 2
    assert all("Urlaub" in e["event"] for e in daten["events"])


def test_endpunkt_event_toleriert_umlaut(client, mit_dateien):
    daten = client.get(PFAD, params={"event": "pruefung"}).json()
    assert daten["anzahl"] == 1
    assert daten["events"][0]["event"].endswith("Prüfung Beispiel")


def test_endpunkt_limit_begrenzt_die_liste(client, mit_dateien):
    daten = client.get(PFAD, params={"limit": 1}).json()
    assert daten["anzahl"] == 1
    assert len(daten["events"]) == 1


def test_endpunkt_limit_unsinn_wird_vom_endpunkt_abgewiesen(client, mit_dateien):
    """Ein Text als ``limit`` ist kein Zahlwert: FastAPI antwortet 422.

    Das ist kein 500er — der Endpunkt bleibt ehrlich. Die Klemmung selbst
    prüft der Dienst (``test_bilder_limit_unsinn_faellt_auf_standard_zurueck``).
    """
    assert client.get(PFAD, params={"limit": "viel"}).status_code == 422


def test_endpunkt_pro_event_kuerzt_aber_anzahl_bleibt(client, mit_dateien):
    daten = client.get(PFAD, params={"event": "Urlaub", "pro_event": 1}).json()
    assert daten["anzahl"] == 2
    for zeile in daten["events"]:
        assert len(zeile["dateien"]) == 1
        assert zeile["anzahl"] == 3       # „3 Bilder, 1 gezeigt"


def test_endpunkt_anzahl_ist_die_zahl_der_events(client, mit_dateien):
    daten = client.get(PFAD, params={"pro_event": 2}).json()
    assert daten["anzahl"] == len(daten["events"]) == 4


def test_endpunkt_uebernimmt_limit_und_pro_event_standard(client, mit_dateien):
    daten = client.get(PFAD).json()
    assert daten["anzahl"] == 4
    assert all(len(e["dateien"]) == 3 for e in daten["events"])


def test_endpunkt_kaputte_datei_gibt_200_und_fehlertext(client, pfad):
    _schreiben(pfad, "kein json")
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is False
    assert daten["events"] == []
    assert "JSON" in daten["error"]


def test_endpunkt_fremde_version_gibt_200_und_fehlertext(client, pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["version"] = 99
    _schreiben(pfad, daten_roh)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert antwort.json()["ok"] is False
    assert "Version" in antwort.json()["error"]


def test_endpunkt_fremde_art_gibt_200_und_fehlertext(client, pfad):
    daten_roh = json.loads(json.dumps(DATEIEN))
    daten_roh["art"] = "foto_uebersicht"
    _schreiben(pfad, daten_roh)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert "Art" in antwort.json()["error"]


def test_endpunkt_listen_sind_kopien_der_datei(client, mit_dateien):
    """Der Endpunkt reicht die Listen weiter, ohne sie zu verändern."""
    erste = client.get(PFAD).json()
    zweite = client.get(PFAD).json()
    assert erste["events"] == zweite["events"]
    assert erste["events"] is not zweite["events"]


def test_endpunkt_liefert_keine_bilddaten_und_keine_ablageorte(client, mit_dateien):
    """Nur Kennung und Name — keine Bilddaten, keine Pfade."""
    text = client.get(PFAD).text
    for verboten in ("ziel_pfad", "von_ordner", "vorbuchung", "base64",
                     "thumbnail", "\"bild\"", "data:"):
        assert verboten not in text, verboten


def test_dienst_macht_keinen_netz_call(mit_dateien, monkeypatch):
    """Der Dienst liest nur die lokale Datei: kein Ausgeh-Versuch.

    Hier ist der volle Riegel gesetzt (auch ``connect``): Die Dienst-Funktionen
    laufen ohne TestClient, brauchen also keine lokalen Sockets.
    """
    _netz_sperren(monkeypatch)
    assert foto_bilder.dateien_laden()["existiert"] is True
    assert foto_bilder.status_block()["ok"] is True
    assert foto_bilder.bilder_finden(jahr=2021)


def test_dienst_macht_ohne_datei_keinen_netz_call(pfad, monkeypatch):
    _netz_sperren(monkeypatch)
    assert foto_bilder.dateien_laden()["existiert"] is False
    assert foto_bilder.status_block()["ok"] is False
    assert foto_bilder.bilder_finden() == []


def test_endpunkt_macht_keinen_netz_call(client, mit_dateien, monkeypatch):
    """Kein Ausgeh-Versuch: Namensauflösung und Verbindungsaufbau sind gesperrt."""
    _netz_sperren(monkeypatch, nur_aussen=True)
    antwort = client.get(PFAD, params={"jahr": 2021, "event": "urlaub"})
    assert antwort.status_code == 200
    assert antwort.json()["ok"] is True


def test_endpunkt_ohne_datei_macht_keinen_netz_call(client, pfad, monkeypatch):
    _netz_sperren(monkeypatch, nur_aussen=True)
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert antwort.json()["ok"] is False


def test_endpunkt_schluessel_schutz_verlangt_key(pfad):
    """Mit gesetztem API-Key: ohne Header 401 (wie die übrigen /api-Routen)."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    alt = settings.api_key
    settings.api_key = "test-key-nicht-echt"
    try:
        pruefer = TestClient(app)
        assert pruefer.get(PFAD).status_code == 401
        assert pruefer.get(PFAD, headers={"X-API-Key": "test-key-nicht-echt"}).status_code == 200
    finally:
        settings.api_key = alt


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
            "subprocess", "chmod", "move"}


def test_dienst_hat_keine_loesch_und_netz_namen():
    treffer = _namen_im_quelltext(DIENST_DATEI) & VERBOTEN
    assert not treffer, f"verbotene Namen im Dienst: {sorted(treffer)}"


def test_router_hat_keine_loesch_und_netz_namen():
    treffer = _namen_im_quelltext(ROUTER_DATEI) & VERBOTEN
    assert not treffer, f"verbotene Namen im Router: {sorted(treffer)}"


def test_dienst_oeffnet_dateien_nur_lesend():
    """Kein ``open(..., "w")``, kein Schreiben — die Kennungen sind nur Quelle."""
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert '"w"' not in quelltext and "'w'" not in quelltext
    assert '"a"' not in quelltext and "'a'" not in quelltext


def test_dienst_wirft_nicht_und_faengt_breit():
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert "except Exception" in quelltext
    assert "Wirft nie" in quelltext


def test_router_nutzt_den_dienst_statt_eigener_dateizugriffe():
    with open(ROUTER_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert "foto_bilder.dateien_laden" in quelltext
    assert "foto_bilder.bilder_finden" in quelltext
    assert "open(" not in quelltext


def test_dienst_traegt_keine_bilddatei_endungen():
    """Es werden keine Bilder gelesen — keine Bild-Endungen im Modul."""
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read().lower()
    for endung in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
        assert endung not in quelltext
