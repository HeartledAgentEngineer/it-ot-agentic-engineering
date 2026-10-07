"""Tests: Orte aus OpenStreetMap-Karten (06.10.2026).

Alles offline und mit **erfundenen** Kartendaten: eine winzige ``.osm``-Datei
im Testordner (XML, das liest dieselbe Bibliothek wie die echten ``.pbf``) mit
einer Adresse, einem Restaurant, einem Dorf, einem Berg, einem Wald und einer
Adresse an einem Weg. Kein Netz, keine echten Karten, keine Bilder.

Geprueft werden die Kernregeln: mehrere Karten-Schluessel je Art (Wald unter
``natural`` UND ``landuse`` — als dict wuerde eine der beiden Zeilen
stillschweigend verschwinden), Adressen an Punkten UND an Wegen,
Naechster-Nachbar-Suche mit Umkreisgrenze, GPS-Lesen aus den Vektorzeilen,
der Zuordnungs-Lauf mit ``bild_orte.csv`` (eine Zeile je Bild, ohne GPS
ehrlich als „ohne GPS"), Trockenlauf schreibt nichts und das Repo-Ziel bleibt
gesperrt (Exit 2).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_orte_aus_karte.py -q
"""
from __future__ import annotations

import csv
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)

import orte_aus_karte as oak  # noqa: E402


@pytest.fixture(autouse=True)
def _keine_echten_daten(tmp_path, monkeypatch):
    """Standardpfade (Fotos mit GPS, eigene Orte) zeigen in jedem Test ins Leere —
    ohne ausdrueckliches ``--vektoren`` liest kein Test Sebastians Daten (07.10.2026)."""
    monkeypatch.setattr(oak, "STANDARD_VEKTOREN", [str(tmp_path / "keine_vektoren.jsonl")])
    monkeypatch.setattr(oak, "STANDARD_EIGENE_ORTE", str(tmp_path / "keine_eigenen_orte.json"))

KARTE = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
  <node id="1" lat="53.700000" lon="10.750000">
    <tag k="addr:street" v="Lauenburger Strasse"/>
    <tag k="addr:housenumber" v="41"/>
    <tag k="addr:city" v="Teststadt"/>
  </node>
  <node id="2" lat="53.700500" lon="10.750500">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Gasthaus am See"/>
  </node>
  <node id="3" lat="53.701000" lon="10.751000">
    <tag k="place" v="village"/>
    <tag k="name" v="Testdorf"/>
  </node>
  <node id="4" lat="53.702000" lon="10.752000">
    <tag k="natural" v="peak"/>
    <tag k="name" v="Testberg"/>
  </node>
  <node id="5" lat="53.703000" lon="10.753000">
    <tag k="landuse" v="forest"/>
    <tag k="name" v="Testwald"/>
  </node>
  <node id="20" lat="53.704000" lon="10.754000"/>
  <node id="21" lat="53.704200" lon="10.754200"/>
  <way id="10">
    <nd ref="20"/>
    <nd ref="21"/>
    <tag k="addr:street" v="Waldweg"/>
    <tag k="addr:housenumber" v="7"/>
  </way>
</osm>
"""


def karte_schreiben(tmp_path) -> str:
    ziel = tmp_path / "probe.osm"
    ziel.write_text(KARTE, encoding="utf-8")
    return str(ziel)


# --- Karten-Regeln ---------------------------------------------------------

def test_klassen_findet_mehrere_schluessel_je_art():
    # Der haeufigste Fehler waere ein dict: dann greift nur eine der beiden
    # Wald-Zeilen. Beide Wege muessen „wald" ergeben.
    assert oak._klassen({"landuse": "forest"}) == ["wald"]
    assert oak._klassen({"natural": "wood"}) == ["wald"]
    assert oak._klassen({"amenity": "restaurant", "tourism": "museum"}) == ["restaurant",
                                                                           "sehenswuerdigkeit"]
    assert oak._klassen({"amenity": "restaurant", "shop": "bakery"}) == ["restaurant",
                                                                        "laden"]
    assert oak._klassen({"name": "Garten"}) == []


def test_regeln_haben_keine_doppelten_arten_verloren():
    arten = [a for a, _, _ in oak.REGELN]
    for pflicht in ("wald", "schutzgebiet", "restaurant", "berg", "fluss", "kirche",
                    "bahnhof", "flughafen", "ort_platzhalter_fehlt_bewusst"):
        if pflicht == "ort_platzhalter_fehlt_bewusst":
            continue
        assert pflicht in arten, f"Art fehlt in den Regeln: {pflicht}"


# --- Karten lesen ----------------------------------------------------------

def test_sammle_karte_adressen_an_punkt_und_weg(tmp_path):
    adressen, orte, zahlen = oak.sammle_karte(karte_schreiben(tmp_path))
    strassen = {(s, h) for (_b, _l, s, h, _o) in adressen}
    assert ("Lauenburger Strasse", "41") in strassen        # Adresse am Punkt
    assert ("Waldweg", "7") in strassen                     # Adresse am Weg (Mittelpunkt)
    assert zahlen["adresse"] == 2
    # Die Stadt wird mitgenommen, wenn sie am Objekt steht.
    assert [o for (*_r, o) in adressen] == ["Teststadt", ""]


def test_sammle_karte_orte_und_arten(tmp_path):
    _adressen, orte, zahlen = oak.sammle_karte(karte_schreiben(tmp_path))
    gefunden = {(art, name) for (_b, _l, art, name, _z) in orte}
    assert ("restaurant", "Gasthaus am See") in gefunden
    assert ("ort", "Testdorf") in gefunden
    assert ("berg", "Testberg") in gefunden
    assert ("wald", "Testwald") in gefunden
    assert zahlen["wald"] == 1
    # Das Dorf bekommt seine Sorte als Zusatz (village), damit die Erzaehlung
    # „Dorf/Stadt" unterscheiden kann.
    zusatz = [z for (*_r, z) in orte if _r[2] == "ort"]
    assert zusatz == ["village"]


# --- Naechster Nachbar ----------------------------------------------------

def test_nachbar_findet_naechste_adresse_und_grenze_greift(tmp_path):
    adressen, _orte, _z = oak.sammle_karte(karte_schreiben(tmp_path))
    index = oak.index_bauen([(b, l, "adresse", f"{s}|{h}|{o}", "")
                             for (b, l, s, h, o) in adressen])
    nah = oak.nachbar(index, 53.700020, 10.750020, "adresse", 2.0)
    assert nah is not None
    assert nah[2].startswith("Lauenburger Strasse|41")
    assert nah[0] < 0.05                       # wenige Meter
    assert oak.nachbar(index, 53.700020, 10.750020, "adresse", 0.001) is None


def test_nachbar_mit_art_filter(tmp_path):
    _adressen, orte, _z = oak.sammle_karte(karte_schreiben(tmp_path))
    index = oak.index_bauen(orte)
    assert oak.nachbar(index, 53.702010, 10.752010, "berg", 2.0)[2] == "Testberg"
    assert oak.nachbar(index, 53.702010, 10.752010, "restaurant", 0.05) is None
    # Ohne Filter kommt irgendetwas Nahes (nicht None).
    assert oak.nachbar(index, 53.702010, 10.752010, None, 0.05) is not None


# --- Schutzregeln ---------------------------------------------------------

def test_repo_ziel_ist_gesperrt(tmp_path):
    verboten = os.path.join(WERKZEUGE, "verboten.csv")
    with pytest.raises(SystemExit) as fehler:
        oak.csv_schreiben(verboten, ["a"], [["1"]])
    assert fehler.value.code == 2
    assert not os.path.exists(verboten)


def test_trockenlauf_schreibt_nichts(tmp_path):
    ordner = tmp_path / "csv"
    assert oak.main(["--karte", karte_schreiben(tmp_path),
                     "--ordner", str(ordner), "--alle", "--trocken"]) == 0
    assert not os.path.exists(ordner / "osm_adressen.csv")


def test_schreiben_legt_tabellen_an(tmp_path):
    ordner = tmp_path / "csv"
    assert oak.main(["--karte", karte_schreiben(tmp_path),
                     "--ordner", str(ordner), "--alle", "--schreiben"]) == 0
    adressen = oak.csv_lesen(str(ordner / "osm_adressen.csv"))
    orte = oak.csv_lesen(str(ordner / "osm_orte.csv"))
    assert len(adressen) == 2 and len(orte) == 4
    assert set(adressen[0]) == set(oak.ADRESS_SPALTEN)
    assert set(orte[0]) == set(oak.ORT_SPALTEN)


# --- Bilder zuordnen ------------------------------------------------------

def test_gps_aus_vektoren_liest_koordinaten_und_zeit(tmp_path):
    pfad = tmp_path / "vektoren.jsonl"
    zeilen = [
        {"bild_id": 4711, "metadaten": {"gps": {"lat": 53.70002, "lon": 10.75002},
                                        "aufnahme": "2015-10-03T16:14:46"}},
        {"bild_id": 4712, "metadaten": {"aufnahme": "2020-01-01T00:00:00"}},
        {"bild_id": 4713, "metadaten": {}},
    ]
    pfad.write_text("\n".join(json.dumps(z) for z in zeilen), encoding="utf-8")
    punkte = oak.gps_aus_vektoren(str(pfad))
    assert punkte["4711"][0] == 53.70002 and punkte["4711"][2] == "2015-10-03T16:14:46"
    assert punkte["4712"][0] is None and punkte["4713"][1] is None


def test_zuordnen_schreibt_eine_zeile_je_bild(tmp_path):
    # Karten auswerten und Tabellen in den Testordner legen
    ordner = tmp_path / "csv"
    assert oak.main(["--karte", karte_schreiben(tmp_path),
                     "--ordner", str(ordner), "--alle", "--schreiben"]) == 0
    # Zwei Bilder: eines am Haus, eines ohne GPS
    vektoren = tmp_path / "vektoren.jsonl"
    vektoren.write_text("\n".join(json.dumps(z) for z in [
        {"bild_id": 900, "metadaten": {"gps": {"lat": 53.700020, "lon": 10.750020},
                                       "aufnahme": "2015-10-03T16:14:46"}},
        {"bild_id": 901, "metadaten": {"aufnahme": "2019-08-01T10:00:00"}},
    ]), encoding="utf-8")
    ziel = tmp_path / "bild_orte.csv"
    assert oak.main(["--zuordnen", "--ordner", str(ordner),
                     "--vektoren", str(vektoren), "--bild-orte", str(ziel),
                     "--schreiben"]) == 0
    zeilen = {z["fileid"]: z for z in oak.csv_lesen(str(ziel))}
    assert set(zeilen) == {"900", "901"}
    nah = zeilen["900"]
    assert nah["adresse"] == "Lauenburger Strasse" and nah["hausnummer"] == "41"
    assert nah["ort_osm"] == "Testdorf"
    assert nah["landmarke"] == "Gasthaus am See"
    assert nah["landmarke_art"] == "restaurant"
    assert nah["aufnahme"] == "2015-10-03T16:14:46"
    assert "testberg" not in nah["hinweise"]
    fern = zeilen["901"]
    assert fern["hinweise"] == "ohne GPS" and fern["adresse"] == ""


def test_zuordnen_ohne_tabellen_meldet_fehler(tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    assert oak.main(["--zuordnen", "--ordner", str(leer), "--schreiben"]) == 2


def test_zusammenfassen_verbindet_gebiete_und_ist_wiederholbar(tmp_path):
    ordner = tmp_path / "csv"
    quelle = karte_schreiben(tmp_path)
    for gebiet in ("gebiet_a", "gebiet_b"):
        assert oak.main(["--karte", quelle, "--ordner", str(ordner / gebiet), "--alle",
                         "--schreiben"]) == 0
    assert oak.main(["--zusammenfassen", "--ordner", str(ordner), "--schreiben"]) == 0
    assert len(oak.csv_lesen(str(ordner / "osm_adressen.csv"))) == 4
    assert len(oak.csv_lesen(str(ordner / "osm_orte.csv"))) == 8
    # Zweiter Lauf baut neu aus den Einzeltabellen — nichts verdoppelt sich.
    assert oak.main(["--zusammenfassen", "--ordner", str(ordner), "--schreiben"]) == 0
    assert len(oak.csv_lesen(str(ordner / "osm_adressen.csv"))) == 4


def test_zusammenfassen_ohne_gebiete_meldet_fehler(tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    assert oak.main(["--zusammenfassen", "--ordner", str(leer), "--schreiben"]) == 2


# --- Nur Orte rund um die Fotos, keine Adressen (Standard seit 07.10.2026) ---

FERN = """  <node id="99" lat="54.000000" lon="11.200000">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Fernes Gasthaus"/>
  </node>
</osm>
"""


def _karte_mit_fernem_ort(tmp_path) -> str:
    ziel = tmp_path / "fern.osm"
    ziel.write_text(KARTE.replace("</osm>\n", FERN), encoding="utf-8")
    return str(ziel)


def _fotos(tmp_path, punkte) -> str:
    pfad = tmp_path / "fotos.jsonl"
    pfad.write_text("\n".join(json.dumps({"bild_id": 800 + i, "metadaten": {
        "gps": {"lat": lat, "lon": lon} if lat is not None else None}})
        for i, (lat, lon) in enumerate(punkte)), encoding="utf-8")
    return str(pfad)


def test_foto_naehe_je_umkreis():
    naehe = oak.FotoNaehe([(53.70, 10.75)], [0.3, 5.0])
    assert naehe.nah(53.7005, 10.7505, 0.3)            # ~65 m
    assert not naehe.nah(53.75, 10.75, 0.3)            # ~5,5 km
    assert naehe.nah(53.73, 10.75, 5.0)                # ~3,3 km
    assert not naehe.nah(54.00, 11.20, 5.0)            # ~43 km


def test_sammle_karte_nur_um_fotos_und_ohne_adressen(tmp_path):
    naehe = oak.FotoNaehe([(53.70002, 10.75002)], list(oak.UMKREIS_KM.values()) + [oak.UMKREIS_ADRESSE_KM])
    adressen, orte, zahlen = oak.sammle_karte(_karte_mit_fernem_ort(tmp_path), fotos=naehe, mit_adressen=False)
    namen = {o[3] for o in orte}
    assert adressen == [] and "Fernes Gasthaus" not in namen
    assert {"Gasthaus am See", "Testdorf", "Testberg", "Testwald"} <= namen
    assert zahlen["ausser_umkreis"] == 1


def test_standard_ohne_fotos_bricht_ehrlich_ab(tmp_path):
    ordner = tmp_path / "csv"
    assert oak.main(["--karte", karte_schreiben(tmp_path), "--ordner", str(ordner), "--schreiben"]) == 2
    assert not os.path.exists(ordner / "osm_orte.csv")


def test_standard_schreibt_nur_nahe_orte_und_keine_adressen(tmp_path):
    ordner = tmp_path / "csv"
    fotos = _fotos(tmp_path, [(53.70002, 10.75002), (None, None)])
    assert oak.main(["--karte", _karte_mit_fernem_ort(tmp_path), "--ordner", str(ordner),
                     "--vektoren", fotos, "--schreiben"]) == 0
    assert oak.csv_lesen(str(ordner / "osm_adressen.csv")) == []       # nur Kopfzeile
    namen = {o["name"] for o in oak.csv_lesen(str(ordner / "osm_orte.csv"))}
    assert "Gasthaus am See" in namen and "Fernes Gasthaus" not in namen
    # mit --mit-adressen: nur die Hausnummer direkt am Foto, nicht der Waldweg (~500 m)
    ordner2 = tmp_path / "csv2"
    assert oak.main(["--karte", _karte_mit_fernem_ort(tmp_path), "--ordner", str(ordner2),
                     "--vektoren", fotos, "--mit-adressen", "--schreiben"]) == 0
    strassen = [a["strasse"] for a in oak.csv_lesen(str(ordner2 / "osm_adressen.csv"))]
    assert strassen == ["Lauenburger Strasse"]


def test_eigene_orte_lesen_ist_tolerant(tmp_path):
    pfad = tmp_path / "eigene_orte.json"
    pfad.write_text(json.dumps([
        {"name": "bei Testoma", "lat": 53.7, "lon": 10.75},
        {"name": "", "lat": 1, "lon": 1},
        {"name": "kaputt", "lat": "x", "lon": 1},
        {"name": "zu weit", "lat": 95, "lon": 1},
        "quatsch",
        {"name": "Nachbar Test", "lat": 53.71, "lon": 10.76, "radius_m": 50},
    ]), encoding="utf-8")
    orte = oak.eigene_orte_lesen(str(pfad))
    assert [(o[2], o[3]) for o in orte] == [("bei Testoma", 100.0), ("Nachbar Test", 50.0)]
    assert oak.eigene_orte_lesen(str(tmp_path / "fehlt.json")) == []
    assert oak.eigener_ort(orte, 53.7003, 10.75)[0] == "bei Testoma"          # ~33 m
    assert oak.eigener_ort(orte, 53.705, 10.75) is None                       # ~550 m


def test_zuordnen_eigener_ort_gewinnt_vor_der_karte(tmp_path):
    ordner = tmp_path / "csv"
    assert oak.main(["--karte", karte_schreiben(tmp_path), "--ordner", str(ordner),
                     "--alle", "--schreiben"]) == 0
    fotos = _fotos(tmp_path, [(53.700020, 10.750020), (53.702000, 10.752000)])
    eigene = tmp_path / "eigene_orte.json"
    eigene.write_text(json.dumps([{"name": "bei Testoma", "lat": 53.70001, "lon": 10.75001}]),
                      encoding="utf-8")
    ziel = tmp_path / "bild_orte.csv"
    assert oak.main(["--zuordnen", "--ordner", str(ordner), "--vektoren", fotos,
                     "--eigene-orte", str(eigene), "--bild-orte", str(ziel), "--schreiben"]) == 0
    zeilen = {z["fileid"]: z for z in oak.csv_lesen(str(ziel))}
    assert zeilen["800"]["landmarke"] == "bei Testoma" and zeilen["800"]["landmarke_art"] == "eigener_ort"
    assert zeilen["801"]["landmarke"] != "bei Testoma"                         # ~280 m weg: Karte
