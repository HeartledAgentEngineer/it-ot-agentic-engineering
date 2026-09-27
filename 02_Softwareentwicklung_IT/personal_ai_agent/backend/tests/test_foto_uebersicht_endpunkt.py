"""Tests: Fotos-Übersicht am Handy (Nachtlauf-Schritt N11, Teil B, 27.09.2026).

Prüft den Dienst ``app/services/foto_uebersicht.py``, den Endpunkt
``GET /api/fotos/uebersicht`` und den Selbsttest-Block ``fotos``.

Alles läuft offline: Die Übersichtsdatei wird für jeden Test in ``tmp_path``
erfunden (erfundene Beispielnamen, kein echter Bestand), der Pfad kommt über
die Umgebungsvariable ``FOTO_UEBERSICHT_PFAD``. Kein Netz, kein pCloud-Aufruf,
keine Bilddatei. Ein Test ersetzt ``socket.socket`` durch eine Stolperfalle,
die jeden echten Ausgeh-Versuch sofort scheitern lässt.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_foto_uebersicht_endpunkt.py -q
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

from app.services import foto_uebersicht  # noqa: E402

PFAD = "/api/fotos/uebersicht"
DIENST_DATEI = os.path.join(BACKEND, "app", "services", "foto_uebersicht.py")
ROUTER_DATEI = os.path.join(BACKEND, "app", "router", "fotos.py")

# Die Felder, die der Endpunkt IMMER liefern muss.
ANTWORT_FELDER = {"ok", "quelle", "stand", "zahlen", "jahre", "themen",
                  "kategorien", "events", "error"}

# Die Schlüssel des Selbsttest-Blocks — immer dieselben.
STATUS_FELDER = {"quelle", "pfad", "existiert", "stand", "anlaesse", "events",
                 "dateien", "jahre", "error"}

# Eine ERFUNDENE Übersicht: erfundene Event-Namen, kein echter Ordner, kein
# echter Personenname, keine Bilddatei. Zahlen sind untereinander stimmig
# (4 verschiedene Events, 5 Anlässe, 40 Dateien, 2 Jahre).
UEBERSICHT = {
    "version": 1,
    "art": "foto_uebersicht",
    "stand": "2026-09-27T22:30:00+02:00",
    "quelle": {"plan_stand": "2026-09-27T13:49:46+02:00", "trocken": True},
    "zahlen": {
        "zeilen": 40, "anlaesse": 5, "zuege": 30,
        "events": 4, "events_neu": 3, "events_wiederverwendet": 1,
        "ordner_neu": 6, "ordner_vorhanden": 2,
        "themen": 3, "kategorien": 2,
        "doppelung_gesamt": 8, "doppelung_ohne_anlass": 5,
        "doppelung_uebersprungen": 4, "ohne_thema": 0, "ohne_jahr": 0,
        "ohne_datum": 6, "jahre": 2,
    },
    "jahre": [
        {"jahr": 2020, "anlaesse": 2, "dateien": 16, "events": 2},
        {"jahr": 2021, "anlaesse": 3, "dateien": 24, "events": 2},
    ],
    "themen": [
        {"thema": "Haus und Garten", "anlaesse": 3, "dateien": 20},
        {"thema": "Prüfungen", "anlaesse": 2, "dateien": 20},
    ],
    "kategorien": [
        {"kategorie": "WG", "anlaesse": 3, "dateien": 24, "events": 2},
        {"kategorie": "Reisen", "anlaesse": 2, "dateien": 16, "events": 2},
    ],
    "events": [
        {"jahr": 2020, "kategorie": "WG", "name": "2020-05-01 Konzert Beispiel",
         "dateien": 8, "quelle": "neu"},
        {"jahr": 2020, "kategorie": "Reisen", "name": "2020-08-01 Urlaub Beispiel",
         "dateien": 8, "quelle": "neu"},
        {"jahr": 2021, "kategorie": "WG", "name": "2021-03-01 Prüfung Beispiel",
         "dateien": 12, "quelle": "wiederverwendet"},
        {"jahr": 2021, "kategorie": "Reisen", "name": "2021-07-01 Urlaub Beispiel",
         "dateien": 12, "quelle": "neu"},
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
    ziel = tmp_path / "fotos_uebersicht.json"
    monkeypatch.setenv("FOTO_UEBERSICHT_PFAD", str(ziel))
    return str(ziel)


@pytest.fixture()
def mit_uebersicht(pfad) -> str:
    """Die erfundene Übersicht liegt bereit; die Umgebungsvariable zeigt darauf."""
    return _schreiben(pfad, UEBERSICHT)


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
    """Selbsttest ohne pCloud-Netzweg: Der Dienst ist nicht eingerichtet.

    In ``backend/.env`` kann ein echter pCloud-Schlüssel stehen — der
    Selbsttest darf in Tests niemals wirklich ins Netz greifen.
    """
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


# ── Pfad ─────────────────────────────────────────────────────────────────────

def test_pfad_vorgabe_ist_der_sortierordner(monkeypatch):
    """Ohne Umgebungsvariable gilt ``~/foto_sortierung/fotos_uebersicht.json``."""
    monkeypatch.delenv("FOTO_UEBERSICHT_PFAD", raising=False)
    erwartet = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                            "fotos_uebersicht.json")
    assert foto_uebersicht.uebersicht_pfad() == erwartet


def test_pfad_ist_ueber_umgebungsvariable_uebersteuerbar(monkeypatch, tmp_path):
    """Für Tests (und ein anderes Gerät) lässt sich der Ort umbiegen."""
    ziel = tmp_path / "anders.json"
    monkeypatch.setenv("FOTO_UEBERSICHT_PFAD", str(ziel))
    assert foto_uebersicht.uebersicht_pfad() == str(ziel)


def test_leere_umgebungsvariable_zaehlt_nicht(monkeypatch):
    """Ein leerer Wert ist kein Pfad — dann gilt die Vorgabe."""
    monkeypatch.setenv("FOTO_UEBERSICHT_PFAD", "   ")
    assert foto_uebersicht.uebersicht_pfad().endswith("fotos_uebersicht.json")
    assert "foto_sortierung" in foto_uebersicht.uebersicht_pfad()


# ── Laden: Erfolg ────────────────────────────────────────────────────────────

def test_laden_liefert_inhalt_und_existiert(mit_uebersicht):
    daten = foto_uebersicht.uebersicht_laden()
    assert daten["existiert"] is True
    assert daten["error"] is None
    assert daten["zahlen"]["anlaesse"] == 5
    assert len(daten["events"]) == 4
    assert daten["pfad"] == mit_uebersicht


def test_laden_mit_explizitem_pfad_ignoriert_umgebung(pfad, tmp_path, monkeypatch):
    """Der ``pfad``-Parameter hat Vorrang vor der Umgebungsvariable."""
    anderer = _schreiben(tmp_path / "zweite.json", UEBERSICHT)
    monkeypatch.setenv("FOTO_UEBERSICHT_PFAD", pfad)  # zeigt auf die leere Datei
    daten = foto_uebersicht.uebersicht_laden(anderer)
    assert daten["existiert"] is True
    assert daten["pfad"] == anderer


# ── Laden: Fehlerfälle (immer ohne Wurf) ─────────────────────────────────────

def test_fehlende_datei_gibt_existiert_false_und_deutschen_text(pfad):
    daten = foto_uebersicht.uebersicht_laden()
    assert daten["existiert"] is False
    assert isinstance(daten["error"], str) and daten["error"].strip()
    assert "nicht gefunden" in daten["error"]


def test_fehlendes_verzeichnis_wirft_nicht(tmp_path, monkeypatch):
    monkeypatch.setenv("FOTO_UEBERSICHT_PFAD", str(tmp_path / "gibtsnicht" / "x.json"))
    daten = foto_uebersicht.uebersicht_laden()
    assert daten["existiert"] is False
    assert daten["error"]


def test_kaputtes_json_gibt_fehlertext_statt_wurf(pfad):
    _schreiben(pfad, "{kein json")
    daten = foto_uebersicht.uebersicht_laden()
    assert daten["existiert"] is False
    assert "JSON" in daten["error"]


def test_json_liste_statt_objekt_wird_gemeldet(pfad):
    _schreiben(pfad, [1, 2, 3])
    daten = foto_uebersicht.uebersicht_laden()
    assert daten["existiert"] is False
    assert "Format" in daten["error"]


def test_fremde_art_wird_gemeldet(pfad):
    daten_roh = dict(UEBERSICHT)
    daten_roh["art"] = "etwas_anderes"
    _schreiben(pfad, daten_roh)
    ergebnis = foto_uebersicht.uebersicht_laden()
    assert ergebnis["existiert"] is False
    assert "Art" in ergebnis["error"]


def test_fremde_schema_version_wird_gemeldet(pfad):
    daten_roh = dict(UEBERSICHT)
    daten_roh["version"] = 99
    _schreiben(pfad, daten_roh)
    ergebnis = foto_uebersicht.uebersicht_laden()
    assert ergebnis["existiert"] is False
    assert "Version" in ergebnis["error"]


def test_leere_datei_gibt_fehlertext(pfad):
    _schreiben(pfad, "")
    ergebnis = foto_uebersicht.uebersicht_laden()
    assert ergebnis["existiert"] is False
    assert ergebnis["error"]


def test_ordner_statt_datei_ist_kein_wurf(pfad):
    os.makedirs(pfad, exist_ok=True)
    ergebnis = foto_uebersicht.uebersicht_laden()
    assert ergebnis["existiert"] is False


# ── status_block ─────────────────────────────────────────────────────────────

def test_status_block_hat_im_erfolgsfall_alle_schluessel(mit_uebersicht):
    assert set(foto_uebersicht.status_block().keys()) == STATUS_FELDER


def test_status_block_hat_im_fehlerfall_alle_schluessel(pfad):
    assert set(foto_uebersicht.status_block().keys()) == STATUS_FELDER


def test_status_block_quelle_ist_der_dateiname(mit_uebersicht):
    block = foto_uebersicht.status_block()
    assert block["quelle"] == "fotos_uebersicht.json"
    assert os.sep not in (block["quelle"] or "")


def test_status_block_quelle_steht_auch_wenn_die_datei_fehlt(pfad):
    """Der Selbsttest soll die Quelle nennen können, auch wenn sie fehlt."""
    block = foto_uebersicht.status_block()
    assert block["existiert"] is False
    assert block["quelle"] == "fotos_uebersicht.json"
    assert block["error"]


def test_status_block_uebernimmt_zahlen_und_stand(mit_uebersicht):
    block = foto_uebersicht.status_block()
    assert block["stand"] == "2026-09-27T22:30:00+02:00"
    assert block["anlaesse"] == 5
    assert block["events"] == 4
    assert block["dateien"] == 40      # Gesamtzahl der Zeilen/Dateien
    assert block["jahre"] == 2


def test_status_block_zaehlt_jahre_aus_der_liste_wenn_die_zahl_fehlt(pfad):
    daten_roh = json.loads(json.dumps(UEBERSICHT))
    del daten_roh["zahlen"]["jahre"]
    _schreiben(pfad, daten_roh)
    assert foto_uebersicht.status_block()["jahre"] == 2


def test_status_block_ohne_zahlenblock_bleibt_stabil(pfad):
    _schreiben(pfad, {"version": 1, "art": "foto_uebersicht",
                      "stand": "2026-01-01T00:00:00+01:00",
                      "jahre": [{"jahr": 2019, "anlaesse": 1, "dateien": 2, "events": 1}]})
    block = foto_uebersicht.status_block()
    assert block["existiert"] is True
    assert block["anlaesse"] is None
    assert block["events"] is None
    assert block["dateien"] is None
    assert block["jahre"] == 1


def test_status_block_wirft_auch_bei_kaputter_datei_nicht(pfad):
    _schreiben(pfad, "@@@")
    block = foto_uebersicht.status_block()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is False
    assert block["error"]


# ── events_finden: Filter ────────────────────────────────────────────────────

def test_events_ohne_filter_kommen_alle(mit_uebersicht):
    treffer = foto_uebersicht.events_finden()
    assert len(treffer) == 4
    assert {t["name"] for t in treffer} == {t["name"] for t in UEBERSICHT["events"]}


def test_events_jahr_filter(mit_uebersicht):
    treffer = foto_uebersicht.events_finden(jahr=2021)
    assert len(treffer) == 2
    assert all(t["jahr"] == 2021 for t in treffer)


def test_events_jahr_als_text_ist_lesbar(mit_uebersicht):
    assert len(foto_uebersicht.events_finden(jahr="2020")) == 2


def test_events_kategorie_ignoriert_gross_klein(mit_uebersicht):
    treffer = foto_uebersicht.events_finden(kategorie="reisen")
    assert len(treffer) == 2
    assert all(t["kategorie"] == "Reisen" for t in treffer)


def test_events_suche_ignoriert_gross_klein(mit_uebersicht):
    treffer = foto_uebersicht.events_finden(suche="URLAUB")
    assert len(treffer) == 2


def test_events_suche_toleriert_umlaut_auf_der_suchseite(mit_uebersicht):
    """„prüfung" findet „Prüfung" (Umlaut identisch)."""
    assert len(foto_uebersicht.events_finden(suche="prüfung")) == 1


def test_events_suche_toleriert_umlaut_als_ae_oe_ue(mit_uebersicht):
    """„pruefung" findet ebenfalls „Prüfung"."""
    treffer = foto_uebersicht.events_finden(suche="pruefung")
    assert len(treffer) == 1
    assert treffer[0]["name"].endswith("Prüfung Beispiel")


def test_events_jahr_und_kategorie_kombiniert(mit_uebersicht):
    treffer = foto_uebersicht.events_finden(jahr=2021, kategorie="WG")
    assert len(treffer) == 1
    assert treffer[0]["name"] == "2021-03-01 Prüfung Beispiel"


def test_events_unbekannte_kategorie_ergibt_leere_liste(mit_uebersicht):
    assert foto_uebersicht.events_finden(kategorie="GibtEsNicht") == []


def test_events_unbekanntes_jahr_ergibt_leere_liste(mit_uebersicht):
    assert foto_uebersicht.events_finden(jahr=1999) == []


def test_events_leerer_suchtext_filtert_nicht(mit_uebersicht):
    assert len(foto_uebersicht.events_finden(suche="   ")) == 4


def test_events_limit_null_wird_auf_eins_angehoben(mit_uebersicht):
    assert len(foto_uebersicht.events_finden(limit=0)) == 1


def test_events_limit_negativ_wird_auf_eins_angehoben(mit_uebersicht):
    assert len(foto_uebersicht.events_finden(limit=-7)) == 1


def test_events_limit_oben_bei_200_begrenzt(mit_uebersicht):
    """500 ist erlaubt, wird aber auf 200 gekappt — hier sind es nur 4 Treffer."""
    assert len(foto_uebersicht.events_finden(limit=500)) == 4


def test_events_limit_unsinn_faellt_auf_standard_zurueck(mit_uebersicht):
    assert len(foto_uebersicht.events_finden(limit="quatsch")) == 4


def test_events_limit_begrenzt_auf_die_trefferzahl(mit_uebersicht):
    treffer = foto_uebersicht.events_finden(limit=2)
    assert len(treffer) == 2


def test_events_ohne_datei_ergibt_leere_liste(pfad):
    assert foto_uebersicht.events_finden() == []


def test_events_liefert_kopien_nicht_die_dateiobjekte(mit_uebersicht):
    treffer = foto_uebersicht.events_finden()
    treffer[0]["name"] = "geaendert"
    assert foto_uebersicht.events_finden()[0]["name"] != "geaendert"


def test_events_finden_wirft_bei_kaputter_datei_nicht(pfad):
    _schreiben(pfad, "{{")
    assert foto_uebersicht.events_finden() == []


# ── text_antwort ─────────────────────────────────────────────────────────────

def test_text_antwort_ist_leer_ohne_datei(pfad):
    """Der Chat bleibt still, statt Zahlen zu raten."""
    assert foto_uebersicht.text_antwort() == ""


def test_text_antwort_nennt_quelle_und_stand(mit_uebersicht):
    text = foto_uebersicht.text_antwort()
    assert "fotos_uebersicht.json" in text
    assert "2026-09-27T22:30:00+02:00" in text


def test_text_antwort_nennt_alle_kennzahlen(mit_uebersicht):
    text = foto_uebersicht.text_antwort()
    assert "5 Anlässe" in text
    assert "4 Events" in text
    assert "40 Dateien" in text
    assert "2 Jahre" in text


def test_text_antwort_nennt_gezeigte_und_gesamtzahl(mit_uebersicht):
    text = foto_uebersicht.text_antwort(limit=2)
    assert "2 von 4 Events" in text


def test_text_antwort_mit_jahr_filter(mit_uebersicht):
    text = foto_uebersicht.text_antwort(jahr=2021)
    assert "Gefiltert (Jahr 2021)" in text
    assert "2 von 4 Events" in text
    assert "2020-05-01 Konzert Beispiel" not in text


def test_text_antwort_mit_suchwort_zeigt_passende_events(mit_uebersicht):
    text = foto_uebersicht.text_antwort(suche="urlaub")
    assert "2021-07-01 Urlaub Beispiel" in text
    assert "2021-03-01 Prüfung Beispiel" not in text


def test_text_antwort_ohne_treffer_sagt_das_ehrlich(mit_uebersicht):
    text = foto_uebersicht.text_antwort(kategorie="GibtEsNicht")
    assert "0 von 4 Events" in text
    assert "erfinde keine Events" in text


def test_text_antwort_ist_ein_anhang_fuer_den_chat(mit_uebersicht):
    """Die Notiz beginnt als Anhang (zwei Zeilenumbrüche + eckige Klammer)."""
    assert foto_uebersicht.text_antwort().startswith("\n\n[Fotos-Übersicht")


# ── Endpunkt ─────────────────────────────────────────────────────────────────

def test_route_ist_eingehaengt():
    assert _route(PFAD) is not None, f"{PFAD} fehlt in der App"


def test_route_haengt_am_api_key_schutz():
    route = _route(PFAD)
    assert route is not None
    namen = [getattr(d.call, "__name__", "") for d in route.dependant.dependencies]
    assert "require_api_key" in namen, f"Key-Schutz fehlt (Abhängigkeiten: {namen})"


def test_endpunkt_antwortet_200_mit_erfundener_uebersicht(client, mit_uebersicht):
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is True
    assert daten["error"] is None
    assert daten["stand"] == "2026-09-27T22:30:00+02:00"
    assert daten["zahlen"]["anlaesse"] == 5
    assert len(daten["jahre"]) == 2
    assert len(daten["themen"]) == 2
    assert len(daten["kategorien"]) == 2
    assert len(daten["events"]) == 4


def test_endpunkt_traegt_immer_alle_felder(client, pfad):
    """Auch im Fehlerfall: dieselben Schlüssel, kein 500er."""
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    assert set(antwort.json().keys()) == ANTWORT_FELDER


def test_endpunkt_fehlerfall_ok_falsch_und_deutscher_text(client, pfad):
    daten = client.get(PFAD).json()
    assert daten["ok"] is False
    assert daten["error"]
    assert daten["jahre"] == [] and daten["themen"] == []
    assert daten["kategorien"] == [] and daten["events"] == []
    assert daten["zahlen"] == {}


def test_endpunkt_nennt_die_quelle_als_dateinamen(client, mit_uebersicht):
    daten = client.get(PFAD).json()
    assert daten["quelle"] == "fotos_uebersicht.json"


def test_endpunkt_jahresfilter_greift(client, mit_uebersicht):
    daten = client.get(PFAD, params={"jahr": 2020}).json()
    assert daten["ok"] is True
    assert len(daten["events"]) == 2
    assert all(e["jahr"] == 2020 for e in daten["events"])


def test_endpunkt_kategoriefilter_greift(client, mit_uebersicht):
    daten = client.get(PFAD, params={"kategorie": "reisen"}).json()
    assert len(daten["events"]) == 2
    assert all(e["kategorie"] == "Reisen" for e in daten["events"])


def test_endpunkt_suche_toleriert_umlaut(client, mit_uebersicht):
    daten = client.get(PFAD, params={"suche": "pruefung"}).json()
    assert len(daten["events"]) == 1
    assert daten["events"][0]["name"].endswith("Prüfung Beispiel")


def test_endpunkt_limit_begrenzt_die_liste(client, mit_uebersicht):
    daten = client.get(PFAD, params={"limit": 1}).json()
    assert len(daten["events"]) == 1


def test_endpunkt_kaputte_datei_gibt_200_und_fehlertext(client, pfad):
    _schreiben(pfad, "kein json")
    antwort = client.get(PFAD)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["ok"] is False
    assert daten["events"] == []
    assert "JSON" in daten["error"]


def test_endpunkt_listen_sind_kopien_der_datei(client, mit_uebersicht):
    """Der Endpunkt reicht die Listen weiter, ohne sie zu verändern."""
    erste = client.get(PFAD).json()
    zweite = client.get(PFAD).json()
    assert erste["themen"] == zweite["themen"]
    assert erste["themen"] is not zweite["themen"]


def test_dienst_macht_keinen_netz_call(mit_uebersicht, monkeypatch):
    """Der Dienst liest nur die lokale Datei: kein Ausgeh-Versuch.

    Hier ist der volle Riegel gesetzt (auch ``connect``): Die Dienst-Funktionen
    laufen ohne TestClient, brauchen also keine lokalen Sockets.
    """
    _netz_sperren(monkeypatch)
    assert foto_uebersicht.uebersicht_laden()["existiert"] is True
    assert foto_uebersicht.status_block()["anlaesse"] == 5
    assert foto_uebersicht.events_finden(jahr=2021)
    assert foto_uebersicht.text_antwort(suche="urlaub")


def test_dienst_macht_ohne_datei_keinen_netz_call(pfad, monkeypatch):
    _netz_sperren(monkeypatch)
    assert foto_uebersicht.uebersicht_laden()["existiert"] is False
    assert foto_uebersicht.status_block()["existiert"] is False
    assert foto_uebersicht.events_finden() == []
    assert foto_uebersicht.text_antwort() == ""


def test_endpunkt_macht_keinen_netz_call(client, mit_uebersicht, monkeypatch):
    """Kein Ausgeh-Versuch: Namensauflösung und Verbindungsaufbau sind gesperrt."""
    _netz_sperren(monkeypatch, nur_aussen=True)
    antwort = client.get(PFAD, params={"jahr": 2021, "suche": "urlaub"})
    assert antwort.status_code == 200
    assert antwort.json()["ok"] is True


def test_endpunkt_ohne_uebersichtsdatei_macht_keinen_netz_call(client, pfad, monkeypatch):
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


# ── Selbsttest-Block ─────────────────────────────────────────────────────────

def test_selbsttest_enthaelt_den_fotos_block(client, mit_uebersicht, selbsttest_ohne_netz):
    daten = client.get("/api/selbsttest").json()
    assert "fotos" in daten
    assert set(daten["fotos"].keys()) == STATUS_FELDER


def test_selbsttest_fotos_zeigt_zahlen_und_quelle(client, mit_uebersicht, selbsttest_ohne_netz):
    block = client.get("/api/selbsttest").json()["fotos"]
    assert block["existiert"] is True
    assert block["anlaesse"] == 5
    assert block["events"] == 4
    assert block["dateien"] == 40
    assert block["jahre"] == 2
    assert block["quelle"] == "fotos_uebersicht.json"
    assert block["stand"] == "2026-09-27T22:30:00+02:00"


def test_selbsttest_fotos_fehlerfall_ist_ein_text_kein_absturz(client, pfad, selbsttest_ohne_netz):
    antwort = client.get("/api/selbsttest")
    assert antwort.status_code == 200
    block = antwort.json()["fotos"]
    assert block["existiert"] is False
    assert block["error"]
    assert block["anlaesse"] is None


def test_fotos_info_faengt_einen_internen_fehler(monkeypatch):
    """Ein defekter Dienst darf den Selbsttest nicht mitreißen."""
    import app.router.selbsttest as st

    from app.services import foto_uebersicht as modul

    def kaputt():
        raise RuntimeError("absichtlich kaputt")

    monkeypatch.setattr(modul, "status_block", kaputt)
    block = st._fotos_info()
    assert set(block.keys()) == STATUS_FELDER
    assert block["existiert"] is False
    assert "RuntimeError" in block["error"]


# ── Chat-Anschluss ───────────────────────────────────────────────────────────

def _tool(frage: str) -> str:
    from app.router.chat import _fotos_uebersicht_tool

    return _fotos_uebersicht_tool(frage)


def test_chat_tool_erkennt_wie_viele_events(mit_uebersicht):
    """„wie viele Events gab's?" — die Frage aus dem Auftrag."""
    antwort = _tool("wie viele Events gab's?")
    assert antwort
    assert "4 Events" in antwort


def test_chat_tool_erkennt_urlaub_mit_jahr(mit_uebersicht):
    """„zeig mir die Urlaube 2021" — Jahr als Filter, Urlaub als Suche."""
    antwort = _tool("zeig mir die Urlaube 2021")
    assert "Gefiltert (Jahr 2021" in antwort
    assert "2021-07-01 Urlaub Beispiel" in antwort


def test_chat_tool_erkennt_konzert_als_suche(mit_uebersicht):
    antwort = _tool("welche Konzerte gibt es?")
    assert "2020-05-01 Konzert Beispiel" in antwort
    assert "Suche \u201ekonzert\u201c" in antwort


def test_chat_tool_ohne_foto_wort_bleibt_still(mit_uebersicht):
    """Keine Fehltreffer: Eine Frage ohne Foto-Bezug löst nichts aus."""
    assert _tool("wie viele Termine gab's?") == ""


def test_chat_tool_ohne_fragewort_bleibt_still(mit_uebersicht):
    assert _tool("ich mag Fotos") == ""


def test_chat_tool_loest_nicht_bei_aufgabe_aus(mit_uebersicht):
    """'gab' zählt nur als eigenes Wort — 'Aufgabe' öffnet das Tor NICHT."""
    assert _tool("was war die Aufgabe mit den Fotos") == ""


def test_chat_tool_leere_frage_bleibt_still(mit_uebersicht):
    assert _tool("") == ""
    assert _tool("   ") == ""


def test_chat_tool_ohne_datei_bleibt_still(pfad):
    """Fehlt die Übersicht, schweigt der Chat (statt zu raten)."""
    assert _tool("wie viele Events gab's?") == ""


def test_chat_tool_wirft_nie(monkeypatch, mit_uebersicht):
    """Ein defekter Dienst darf den Chat nicht mitreißen."""
    from app.services import foto_uebersicht as modul

    def kaputt(*args, **kwargs):
        raise RuntimeError("absichtlich kaputt")

    monkeypatch.setattr(modul, "text_antwort", kaputt)
    assert _tool("wie viele Events gab's?") == ""


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
    """Kein ``open(..., "w")``, kein Schreiben — die Übersicht ist nur Quelle."""
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert '"w"' not in quelltext and "'w'" not in quelltext
    assert '"a"' not in quelltext and "'a'" not in quelltext


def test_router_nutzt_den_dienst_statt_eigener_dateizugriffe():
    with open(ROUTER_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read()
    assert "foto_uebersicht.uebersicht_laden" in quelltext
    assert "open(" not in quelltext


def test_dienst_traegt_keine_bilddatei_endungen():
    """Es werden keine Bilder gelesen — keine Bild-Endungen im Modul."""
    with open(DIENST_DATEI, "r", encoding="utf-8") as datei_zeiger:
        quelltext = datei_zeiger.read().lower()
    for endung in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
        assert endung not in quelltext
