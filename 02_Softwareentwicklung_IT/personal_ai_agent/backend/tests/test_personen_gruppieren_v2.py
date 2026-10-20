"""Tests: Gruppierung v2 (Plan "Gruppierung v2", G3, 15.10.2026).

Alles offline mit ERFUNDENEN Vektoren (numpy, fester Seed) und erfundenen
Kennungen/Namen ("Person A"). Keine echten Gesichter, keine echten Namen,
nichts unter ``~/foto_sortierung``. Dateien nur in ``tmp_path``.

Geprueft wird: v1 bleibt Standard, der Kern (nur saubere Gesichter), Phasen
(ein Kind bleibt EINE Gruppe, Geschwister mit verschiedenen Jahrgaengen nicht),
Vorbilder und Regeln (``gleich`` vereint, gleicher Name allein nicht,
``verschieden``/``ausgeschlossen``/feste Zuordnung), Andocken (Schwelle und
Abstand zwischen Namen, unsichere gruenden nie eine Gruppe), stabile Kennungen,
Trockenlauf ohne Schreiben, zwei Schreiblaeufe = zwei Sicherungen und die
Lesbarkeit der Ausgabe fuer ``gruppen_quiz``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_gruppieren_v2.py -q
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pg = _laden("personen_gruppieren")
D = 128


# ── Erfundene Szenen ───────────────────────────────────────────────────────

def _basis(rng, n):
    """``n`` zueinander senkrechte Einheitsvektoren (Zeilen)."""
    q, _ = np.linalg.qr(rng.normal(size=(D, n)))
    return q.T


def _gesicht(rng, mitte, naehe=0.85):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


def _drehung(e1, e2, winkel):
    return np.cos(winkel) * e1 + np.sin(winkel) * e2


class Szene:
    """Sammelt Gesichter und baut daraus das ``eingelesen`` des Gruppierers."""

    def __init__(self):
        self.zeilen = []
        self.zaehler = 0

    def dazu(self, vektor, jahr=2015, sauber=True, bild=None, index=0, score=None):
        self.zaehler += 1
        self.zeilen.append({
            "vektor": np.asarray(vektor), "bild": bild or f"b{self.zaehler}", "index": index,
            "jahr": jahr, "sauber": sauber, "score": score})
        return len(self.zeilen) - 1

    def person(self, rng, mitte, anzahl, jahre=(2015,), sauber=True, naehe=0.85, bild="p"):
        stellen = []
        for i in range(anzahl):
            stellen.append(self.dazu(_gesicht(rng, mitte, naehe), jahre[i % len(jahre)],
                                     sauber, bild=f"{bild}{self.zaehler + 1}"))
        return stellen

    def eingelesen(self):
        gesichter = []
        for z in self.zeilen:
            gesichter.append({
                "bild_id": z["bild"], "index": z["index"],
                "bbox": [0, 0, 100 if z["sauber"] else 30, 100], "breite": 1000, "hoehe": 1000,
                "anteil": 0.02,
                "score": z["score"] if z["score"] is not None else (0.95 if z["sauber"] else 0.7),
                "aufnahme": f"{z['jahr']}-06-01T12:00:00" if z["jahr"] else None,
                "video_id": None, "zeit_s": None})
        vektoren = pg.einheitsvektoren(np.array([z["vektor"] for z in self.zeilen]))
        return {"gesichter": gesichter, "vektoren": vektoren, "dateien": [],
                "bilder": len(gesichter), "bilder_gruppiert": len(gesichter),
                "je_grund": {}, "ungueltig": 0, "doppelt": 0}


def _gruppen_nach_kennung(lauf):
    return {g["kennung"]: g for g in lauf["gruppen"]}


def _mitglieder(lauf):
    """``{kennung: Menge der Stellen}``."""
    ergebnis = {}
    for i, g in enumerate(lauf["gesichter"]):
        if g["kennung"]:
            ergebnis.setdefault(g["kennung"], set()).add(i)
    return ergebnis


def _kind(rng, e, winkel, jahre, je_jahr=12):
    szene = Szene()
    for jahr in jahre:
        for _ in range(je_jahr):
            szene.dazu(_gesicht(rng, _drehung(e[0], e[1], (jahr - jahre[0]) * winkel)), jahr)
    return szene


# ── Phasen: Kind und Geschwister ───────────────────────────────────────────

def test_ein_kind_bleibt_eine_gruppe_mit_mehreren_phasen():
    rng = np.random.default_rng(1)
    e = _basis(rng, 2)
    szene = _kind(rng, e, 0.3, list(range(2010, 2019)))
    lauf = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(lauf["gruppen"]) == 1
    gruppe = lauf["gruppen"][0]
    assert gruppe["groesse"] == 108
    assert len(gruppe["phasen"]) >= 2                       # Lebensabschnitte
    assert sum(p["anzahl"] for p in gruppe["phasen"]) == 108
    # Die Phasen decken die Jahre lueckenlos ab, ohne Ueberlappung.
    for davor, danach in zip(gruppe["phasen"], gruppe["phasen"][1:]):
        assert davor["bis"] < danach["von"]
    assert gruppe["phasen"][0]["von"] == 2010 and gruppe["phasen"][-1]["bis"] == 2018


def test_v1_zerreisst_dasselbe_kind_v2_nicht():
    """Gegenprobe: dieselbe Szene, v1 braucht zwei Gruppen."""
    rng = np.random.default_rng(1)
    e = _basis(rng, 2)
    szene = _kind(rng, e, 0.3, list(range(2010, 2019)))
    v1 = pg.lauf_rechnen(szene.eingelesen())
    v2 = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(v1["gruppen"]) > 1
    assert len(v2["gruppen"]) == 1


def _geschwister(rng, cos, naehe=0.85):
    e = _basis(rng, 2)
    a = e[0]
    b = cos * e[0] + np.sqrt(1 - cos ** 2) * e[1]
    szene = Szene()
    szene.person(rng, a, 24, jahre=(2010, 2011, 2012, 2013), naehe=naehe, bild="a")
    szene.person(rng, b, 24, jahre=(2017, 2018, 2019, 2020), naehe=naehe, bild="b")
    return szene


def test_geschwister_mit_verschiedenen_jahrgaengen_werden_nicht_vereint():
    szene = _geschwister(np.random.default_rng(1), cos=0.65)
    v1 = pg.lauf_rechnen(szene.eingelesen())
    v2 = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(v1["gruppen"]) == 1                          # v1 haelt sie fuer einen Menschen
    assert sorted(g["groesse"] for g in v2["gruppen"]) == [24, 24]
    # Jede Gruppe enthaelt nur die Gesichter EINES Jahrgangs.
    for stellen in _mitglieder(v2).values():
        assert len({"a" if szene.zeilen[i]["bild"].startswith("a") else "b" for i in stellen}) == 1


def test_gesicht_ohne_datum_gruendet_nichts_und_dockt_an():
    rng = np.random.default_rng(5)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2014, 2015))
    ohne = szene.dazu(_gesicht(rng, e[0], 0.9), jahr=None, sauber=False)
    lauf = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(lauf["gruppen"]) == 1
    assert lauf["gesichter"][ohne]["kennung"] == lauf["gruppen"][0]["kennung"]


# ── Der Kern: nur saubere Gesichter gruenden ──────────────────────────────

def test_unsichere_gesichter_gruenden_nie_eine_gruppe():
    rng = np.random.default_rng(7)
    e = _basis(rng, 3)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2015, 2016))
    unsicher = szene.person(rng, e[1], 8, jahre=(2015, 2016), sauber=False)   # andere Person
    lauf = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(lauf["gruppen"]) == 1
    for i in unsicher:
        assert lauf["gesichter"][i]["kennung"] is None
    assert lauf["bericht"]["v2"]["gesichter_unsicher"] == 8
    assert lauf["bericht"]["v2"]["angedockt"] == 0


def test_unsichere_gesichter_derselben_person_docken_an():
    rng = np.random.default_rng(9)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2015, 2016))
    unsicher = szene.person(rng, e[0], 6, jahre=(2015, 2016), sauber=False, naehe=0.95)
    lauf = pg.lauf_rechnen_v2(szene.eingelesen())
    kennung = lauf["gruppen"][0]["kennung"]
    assert all(lauf["gesichter"][i]["kennung"] == kennung for i in unsicher)
    assert lauf["bericht"]["v2"]["angedockt"] == 6
    assert lauf["gruppen"][0]["groesse"] == 26
    # Die Phasen der Gruppe zaehlen nur die sauberen Gesichter.
    assert sum(p["anzahl"] for p in lauf["gruppen"][0]["phasen"]) == 20


def test_kleine_gruppe_wird_rauschen_und_ihre_gesichter_docken_nicht_blind_an():
    rng = np.random.default_rng(11)
    e = _basis(rng, 3)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2015,))
    fremd = szene.person(rng, e[1], 2, jahre=(2015,))         # unter MIN_GROESSE
    lauf = pg.lauf_rechnen_v2(szene.eingelesen())
    assert len(lauf["gruppen"]) == 1
    assert all(lauf["gesichter"][i]["kennung"] is None for i in fremd)


def _zwei_benannte_aehnliche(rng):
    """Zwei benannte Personen mit aehnlichen Gesichtern (Cosinus 0,7)."""
    e = _basis(rng, 2)
    a = e[0]
    b = 0.7 * e[0] + np.sqrt(1 - 0.49) * e[1]
    szene = Szene()
    stellen_a = szene.person(rng, a, 20, jahre=(2015, 2016), bild="a")
    stellen_b = szene.person(rng, b, 20, jahre=(2015, 2016), bild="b")
    return szene, a, b, stellen_a, stellen_b


def _alt(szene, stellen_a, stellen_b):
    eingelesen = szene.eingelesen()
    alt = {}
    for kennung, stellen in (("Person_001", stellen_a), ("Person_002", stellen_b)):
        for i in stellen:
            g = eingelesen["gesichter"][i]
            alt[(g["bild_id"], g["index"])] = kennung
    return alt


def test_andocken_verlangt_vorsprung_zwischen_namen():
    rng = np.random.default_rng(13)
    szene, a, b, sa, sb = _zwei_benannte_aehnliche(rng)
    mitte = (a + b) / np.linalg.norm(a + b)
    zwischen = szene.dazu(mitte, 2015, sauber=False)         # gleich nah an beiden
    nah_a = szene.dazu(_gesicht(rng, a, 0.97), 2015, sauber=False)
    lauf = pg.lauf_rechnen_v2(
        szene.eingelesen(), bestaetigt={"Person_001": "Person A", "Person_002": "Person B"},
        alte_zuordnung=_alt(szene, sa, sb))
    assert lauf["gesichter"][zwischen]["kennung"] is None
    assert lauf["gesichter"][nah_a]["kennung"] == "Person_001"
    assert lauf["bericht"]["v2"]["nicht_angedockt"]["zu_knapp"] >= 1


def test_gleichnamige_kennungen_konkurrieren_beim_andocken_nicht():
    """Zwei Kennungen DESSELBEN Namens: das Gesicht geht an die bessere, nicht ins Leere."""
    rng = np.random.default_rng(15)
    szene, a, b, sa, sb = _zwei_benannte_aehnliche(rng)
    zwischen = szene.dazu(_gesicht(rng, a, 0.97), 2015, sauber=False)
    lauf = pg.lauf_rechnen_v2(
        szene.eingelesen(), bestaetigt={"Person_001": "Person A", "Person_002": "Person A"},
        alte_zuordnung=_alt(szene, sa, sb))
    assert lauf["gesichter"][zwischen]["kennung"] == "Person_001"


# ── Namen, gleich, verschieden, ausgeschlossen, fest ───────────────────────

def _zwei_lebensabschnitte(rng, je=14):
    """Eine Person in zwei Abschnitten, die einander kaum aehneln (Kindheit/Erwachsene)."""
    e = _basis(rng, 2)
    szene = Szene()
    sa = szene.person(rng, e[0], je, jahre=(2005, 2006, 2007), bild="a")
    sb = szene.person(rng, e[1], je, jahre=(2020, 2021, 2022), bild="b")
    return szene, sa, sb


def test_gleicher_name_ohne_gleich_bleibt_zwei_gruppen():
    rng = np.random.default_rng(17)
    szene, sa, sb = _zwei_lebensabschnitte(rng)
    namen = {"Person_001": "Person A", "Person_002": "Person A"}
    lauf = pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt=namen,
                              alte_zuordnung=_alt(szene, sa, sb))
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_002"]
    assert all(g["name"] == "Person A" for g in lauf["gruppen"])
    assert lauf["bericht"]["v2"]["durch_gleich_vereint"] == 0


def test_gleich_vereint_und_der_name_bleibt_erhalten():
    rng = np.random.default_rng(17)
    szene, sa, sb = _zwei_lebensabschnitte(rng)
    namen = {"Person_001": "Person A", "Person_002": "Person A"}
    vorgaben = {"gleich": {("Person_001", "Person_002")}, "verschieden": set(),
                "ausgeschlossen": set(), "zugeordnet": {}}
    lauf = pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt=namen, vorgaben=vorgaben,
                              alte_zuordnung=_alt(szene, sa, sb))
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["gruppen"][0]["name"] == "Person A" and lauf["gruppen"][0]["groesse"] == 28
    assert lauf["bericht"]["v2"]["durch_gleich_vereint"] == 1
    # Nichts wurde geloescht: beide Namenseintraege bestehen, der Mittelpunkt der
    # zweiten Kennung bleibt im Altbestand.
    assert namen == {"Person_001": "Person A", "Person_002": "Person A"}
    assert lauf["bericht"]["v2"]["benannte_ohne_gruppe"] == 1


def test_verschiedene_namen_werden_auch_mit_gleich_nie_vereint():
    rng = np.random.default_rng(17)
    szene, sa, sb = _zwei_lebensabschnitte(rng)
    namen = {"Person_001": "Person A", "Person_002": "Person B"}
    vorgaben = {"gleich": {("Person_001", "Person_002")}, "verschieden": set(),
                "ausgeschlossen": set(), "zugeordnet": {}}
    lauf = pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt=namen, vorgaben=vorgaben,
                              alte_zuordnung=_alt(szene, sa, sb))
    assert len(lauf["gruppen"]) == 2


def test_name_allein_verschmilzt_nicht_aehnliche_unbenannte_gruppe_wird_nur_gezaehlt():
    """Unbenannt und benannt aehneln sich: kein Zusammenlegen, nur der Vorschlag."""
    rng = np.random.default_rng(19)
    szene, a, b, sa, sb = _zwei_benannte_aehnliche(rng)
    alt = _alt(szene, sa, sb)
    lauf = pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt={"Person_001": "Person A"},
                              alte_zuordnung=alt)
    kennungen = sorted(g["kennung"] for g in lauf["gruppen"])
    assert len(kennungen) == 2 and "Person_001" in kennungen
    unbenannt = [g for g in lauf["gruppen"] if g["kennung"] != "Person_001"][0]
    assert unbenannt["name"] is None
    assert lauf["bericht"]["v2"]["aehneln_benannten"] == 1


def test_verschieden_haelt_aehnliche_gruppen_getrennt():
    """Zwei aehnliche Gruppen (Cosinus 0,64) im selben Zeitraum: ohne Regel eine, mit Regel zwei."""
    rng = np.random.default_rng(1)
    e = _basis(rng, 2)
    a = e[0]
    b = 0.64 * e[0] + np.sqrt(1 - 0.64 ** 2) * e[1]
    szene = Szene()
    szene.person(rng, a, 20, jahre=(2015, 2016), bild="a")
    szene.person(rng, b, 20, jahre=(2015, 2016), bild="b")
    alt = [{"kennung": "Person_001", "mittelpunkt": [float(x) for x in a]},
           {"kennung": "Person_002", "mittelpunkt": [float(x) for x in b]}]
    ohne = pg.lauf_rechnen_v2(szene.eingelesen(), altbestand=alt)
    mit = pg.lauf_rechnen_v2(
        szene.eingelesen(), altbestand=alt,
        vorgaben={"gleich": set(), "verschieden": {("Person_001", "Person_002")},
                  "ausgeschlossen": set(), "zugeordnet": {}})
    assert len(ohne["gruppen"]) == 1
    assert sorted(g["kennung"] for g in mit["gruppen"]) == ["Person_001", "Person_002"]


def test_ausgeschlossenes_gesicht_bleibt_draussen():
    rng = np.random.default_rng(23)
    e = _basis(rng, 2)
    szene = Szene()
    stellen = szene.person(rng, e[0], 20, jahre=(2015, 2016))
    ein = szene.eingelesen()
    g = ein["gesichter"][stellen[0]]
    lauf1 = pg.lauf_rechnen_v2(szene.eingelesen())
    kennung = lauf1["gruppen"][0]["kennung"]
    vorgaben = {"gleich": set(), "verschieden": set(), "zugeordnet": {},
                "ausgeschlossen": {(kennung, g["bild_id"], g["index"])}}
    lauf2 = pg.lauf_rechnen_v2(szene.eingelesen(), altbestand=lauf1["altbestand"],
                               vorgaben=vorgaben)
    assert lauf2["gesichter"][stellen[0]]["kennung"] is None
    assert lauf2["bericht"]["ausgeschlossen_nach_regel"] == 1
    assert lauf2["gesichter"][stellen[1]]["kennung"] == kennung


def test_ausgeschlossenes_unsicheres_gesicht_dockt_dort_nicht_an():
    rng = np.random.default_rng(25)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 20, jahre=(2015, 2016))
    unsicher = szene.dazu(_gesicht(rng, e[0], 0.97), 2015, sauber=False)
    ein = szene.eingelesen()
    g = ein["gesichter"][unsicher]
    lauf1 = pg.lauf_rechnen_v2(szene.eingelesen())
    kennung = lauf1["gruppen"][0]["kennung"]
    vorgaben = {"gleich": set(), "verschieden": set(), "zugeordnet": {},
                "ausgeschlossen": {(kennung, g["bild_id"], g["index"])}}
    lauf2 = pg.lauf_rechnen_v2(szene.eingelesen(), altbestand=lauf1["altbestand"],
                               vorgaben=vorgaben)
    assert lauf2["gesichter"][unsicher]["kennung"] is None
    assert lauf2["bericht"]["v2"]["angedockt"] == 0


def test_feste_zuordnung_gewinnt_gegen_den_vektor():
    rng = np.random.default_rng(27)
    szene, a, b, sa, sb = _zwei_benannte_aehnliche(rng)
    ziel = szene.dazu(_gesicht(rng, a, 0.97), 2015, sauber=True)      # sieht aus wie Person A
    ein = szene.eingelesen()
    g = ein["gesichter"][ziel]
    vorgaben = {"gleich": set(), "verschieden": set(), "ausgeschlossen": set(),
                "zugeordnet": {(g["bild_id"], g["index"]): {"kennung": "Person_001",
                                                           "name": "Person B"}}}
    lauf = pg.lauf_rechnen_v2(
        szene.eingelesen(), bestaetigt={"Person_001": "Person A", "Person_002": "Person B"},
        vorgaben=vorgaben, alte_zuordnung=_alt(szene, sa, sb))
    assert lauf["gesichter"][ziel]["kennung"] == "Person_002"          # der Name bestimmt das Ziel


def test_feste_zuordnung_ohne_beleg_ist_ein_fehler():
    rng = np.random.default_rng(29)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 5)
    vorgaben = {"gleich": set(), "verschieden": set(), "ausgeschlossen": set(),
                "zugeordnet": {("gibt-es-nicht", 0): {"kennung": "Person_001", "name": "Person A"}}}
    with pytest.raises(pg.PersonenFehler):
        pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt={"Person_001": "Person A"},
                           vorgaben=vorgaben)


# ── Kennungen ─────────────────────────────────────────────────────────────

def test_kennungen_bleiben_ueber_laeufe_stabil():
    rng = np.random.default_rng(31)
    e = _basis(rng, 4)
    szene = Szene()
    for k in range(3):
        szene.person(rng, e[k], 15, jahre=(2015, 2016), bild=f"p{k}_")
    erst = pg.lauf_rechnen_v2(szene.eingelesen())
    zweit = pg.lauf_rechnen_v2(szene.eingelesen(), altbestand=erst["altbestand"])
    assert [g["kennung"] for g in erst["gruppen"]] == [g["kennung"] for g in zweit["gruppen"]]
    assert all(not g["neu"] for g in zweit["gruppen"])
    assert all(g["neu"] for g in erst["gruppen"])


def test_benannte_kennung_ohne_gruppe_bleibt_im_altbestand_und_zaehlt():
    rng = np.random.default_rng(33)
    e = _basis(rng, 3)
    szene = Szene()
    szene.person(rng, e[0], 15, jahre=(2015,))
    mitte_b = [float(x) for x in e[1]]
    lauf = pg.lauf_rechnen_v2(
        szene.eingelesen(), bestaetigt={"Person_010": "Person B"},
        altbestand=[{"kennung": "Person_010", "mittelpunkt": mitte_b}])
    kennungen = {e["kennung"]: e for e in lauf["altbestand"]}
    assert kennungen["Person_010"]["mittelpunkt"] == mitte_b          # unveraendert erhalten
    assert lauf["bericht"]["v2"]["benannte_ohne_gruppe"] == 1
    # Die neue Gruppe nimmt NICHT die benannte Kennung und setzt hinter ihr fort.
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_011"]


def test_unbenannte_gruppe_uebernimmt_nie_eine_benannte_kennung():
    rng = np.random.default_rng(35)
    e = _basis(rng, 2)
    szene = Szene()
    szene.person(rng, e[0], 15, jahre=(2015,))
    # Der Altbestand kennt eine BENANNTE Kennung mit genau diesem Mittelpunkt.
    lauf = pg.lauf_rechnen_v2(
        szene.eingelesen(), bestaetigt={"Person_001": "Person A"},
        altbestand=[{"kennung": "Person_001", "mittelpunkt": [float(x) for x in e[0]]}])
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_002"]
    assert lauf["gruppen"][0]["name"] is None


def test_vorbild_aus_alter_zuordnung_gibt_der_gruppe_die_benannte_kennung():
    rng = np.random.default_rng(37)
    e = _basis(rng, 2)
    szene = Szene()
    stellen = szene.person(rng, e[0], 15, jahre=(2015,))
    ein = szene.eingelesen()
    alt = {(ein["gesichter"][i]["bild_id"], 0): "Person_007" for i in stellen}
    lauf = pg.lauf_rechnen_v2(szene.eingelesen(), bestaetigt={"Person_007": "Person A"},
                              alte_zuordnung=alt)
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_007"]
    assert lauf["gruppen"][0]["name"] == "Person A"
    assert lauf["bericht"]["v2"]["vorbild_gruppen"] == 1


def test_v2_ist_deterministisch():
    rng = np.random.default_rng(45)
    e = _basis(rng, 3)
    szene = Szene()
    for k in range(3):
        szene.person(rng, e[k], 14, jahre=(2014, 2015, 2016), bild=f"d{k}_")
    szene.person(rng, e[0], 5, jahre=(2015,), sauber=False, naehe=0.95, bild="u")
    erst = pg.lauf_rechnen_v2(szene.eingelesen())
    zweit = pg.lauf_rechnen_v2(szene.eingelesen())
    for lauf in (erst, zweit):
        lauf["bericht"].pop("sekunden")
    assert json.dumps(erst, sort_keys=True, default=str) == json.dumps(zweit, sort_keys=True, default=str)


# ── Speicher: kein n x n ──────────────────────────────────────────────────

def test_v2_rechnet_blockweise_ohne_n_mal_n(monkeypatch):
    import tracemalloc
    rng = np.random.default_rng(39)
    e = _basis(rng, 6)
    szene = Szene()
    for k in range(6):
        szene.person(rng, e[k], 350, jahre=(2014, 2015, 2016, 2017), bild=f"q{k}_")
    ein = szene.eingelesen()                                 # 2.100 Gesichter
    n = len(ein["gesichter"])
    assert n * n * 4 > 16 * 1024 * 1024                      # eine n x n-Matrix waere > 16 MB
    tracemalloc.start()
    lauf = pg.lauf_rechnen_v2(ein)
    _, spitze = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(lauf["gruppen"]) == 6
    assert spitze < n * n * 4 // 2


# ── Schalter, Trockenlauf, Sicherung, Quiz ─────────────────────────────────

def _zeile(bild_id, vektor, jahr=2016, seite=200):
    return json.dumps({
        "bild_id": bild_id, "breite": 1000, "hoehe": 1000,
        "metadaten": {"aufnahme": f"{jahr}-06-01T12:00:00"},
        "gesichter": [{"bbox": [10, 10, seite, seite], "score": 0.95,
                       "embedding": [float(x) for x in vektor]}]})


def _vektordatei(tmp_path, personen=2, je=8, seed=41):
    rng = np.random.default_rng(seed)
    e = _basis(rng, personen)
    zeilen = [_zeile(str(1000 + 100 * p + i), _gesicht(rng, e[p]), 2015 + (i % 3))
              for p in range(personen) for i in range(je)]
    datei = tmp_path / "v.jsonl"
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return datei


def _pflichtdateien(tmp_path):
    """Die zwei PFLICHTDATEIEN (G0, Auflage 2) mit erfundenen Inhalten anlegen.

    Keine Namen, aber 50 Ausschlussregeln auf erfundene Kennungen/Bild-IDs
    (die auf kein Gesicht zeigen): damit ist die Grundwahrheit nach
    ``MIN_REGELN`` nicht "vorlaeufig" (G1) und der Schreibweg pruefbar.
    """
    b = tmp_path / "personen_bestaetigt.json"
    if not b.exists():
        b.write_text(json.dumps({"bestaetigt": {}}), encoding="utf-8")
    v = tmp_path / "personen_vorgaben.json"
    if not v.exists():
        v.write_text(json.dumps({
            "gleich": [], "verschieden": [], "zugeordnet": [],
            "ausgeschlossen": [{"kennung": f"Person_{i:03d}", "bild_id": str(900000 + i),
                                "index": 0} for i in range(50)]}), encoding="utf-8")
    return b, v


def _stand(tmp_path, pfade):
    """Einen Geraetestand bauen (unabhaengig: hashlib + eigene Zaehlung)."""
    import hashlib
    import time
    eintraege = {}
    for pfad in pfade:
        pfad = Path(pfad)
        roh = pfad.read_bytes()
        daten = json.loads(roh.decode("utf-8"))
        if pfad.name.endswith("bestaetigt.json"):
            roh_eintraege = daten.get("bestaetigt") or {}
            zaehler = {"benannte_kennungen": len(roh_eintraege),
                       "namen": sum(1 for w in roh_eintraege.values()
                                    if isinstance(w, str) and w.strip())}
        else:
            zaehler = {"gleich": len(daten.get("gleich") or []),
                       "verschieden": len(daten.get("verschieden") or []),
                       "ausgeschlossen": len(daten.get("ausgeschlossen") or []),
                       "fest": len(daten.get("zugeordnet") or [])}
        eintraege[pfad.name] = {"bytes": len(roh),
                                "sha256": hashlib.sha256(roh).hexdigest(),
                                "zaehler": zaehler}
    ziel = tmp_path / "geraetestand.json"
    ziel.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "quelle": "handy", "pflicht": list(pg.PFLICHTQUELLEN),
        "dateien": eintraege}), encoding="utf-8")
    return ziel


def _grund(tmp_path, datei, aus):
    """Argumente fuer den v1-Standardweg; fuer v2 kommt ``--ohne-geraetenachweis``
    dazu (eine Trockenmessung ohne Geraet, Auflage 2)."""
    b, v = _pflichtdateien(tmp_path)
    return ["--vektoren", str(datei), "--ausgabe", str(aus), "--bestaetigt", str(b),
            "--vorgaben", str(v), "--geraetestand", str(tmp_path / "kein_stand.json"),
            "--ohne-geraetenachweis"]


def _freigabe(tmp_path, datei, aus, bestaetigt, vorgaben, name="freigabe_v2.json"):
    """Eine gueltige Freigabedatei fuer die Voreinstellungen (Auflage 6, Schreib-Tor)."""

    class Args:
        zuordnung = pg.ZUORDNUNG_AEHNLICH
        verschmelzen = pg.VERSCHMELZ_AEHNLICH
        zwilling = pg.ZWILLING_AEHNLICH
        min_groesse = pg.MIN_GROESSE
        min_score = None

    parameter = pg.parameter_stand(Args())
    hash_ist = pg.eingabe_hash([str(datei)], bestaetigt, vorgaben,
                               os.path.join(str(aus), pg.DATEI_KENNUNGEN),
                               os.path.join(str(aus), pg.DATEI_ZUORDNUNG), parameter)
    ziel = tmp_path / name
    ziel.write_text(json.dumps({"snapshot_sha256": hash_ist, "parameter": parameter,
                                "urteil": "pass",
                                "werte": {feld: 0 for feld in pg.SPERRZAHLEN}}),
                    encoding="utf-8")
    return str(ziel)


def _schreiben_args(tmp_path, datei, aus, bestaetigt=None, vorgaben=None,
                    name="freigabe_v2.json"):
    """``--verfahren v2 --schreiben --produktiv`` samt frischer gueltiger Freigabe.

    Der produktive Ordner ist der einzige Weg, auf dem v2 in ``--ausgabe``
    schreibt (Auflage 1); der Kandidatenordner wird separat geprueft. Dazu der
    Geraetestand (G0/Auflage 2) — ohne ihn rechnet v2 nur als Trockenmessung.
    """
    b, v = _pflichtdateien(tmp_path)
    b = Path(bestaetigt) if bestaetigt else b
    v = Path(vorgaben) if vorgaben else v
    freigabe = _freigabe(tmp_path, datei, aus, str(b), str(v), name=name)
    stand = _stand(tmp_path, [b, v])
    return ["--verfahren", "v2", "--schreiben", "--produktiv", "--freigabe", freigabe,
            "--bestaetigt", str(b), "--vorgaben", str(v), "--geraetestand", str(stand)]


def test_standard_bleibt_v1(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + ["--schreiben"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Verfahren v2" not in ausgabe
    beispiele = json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert beispiele["verfahren"] == "mittelpunkt"
    assert all("phasen" not in g for g in beispiele["gruppen"])


def test_v2_trockenlauf_schreibt_nichts(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    grund = _grund(tmp_path, datei, aus) + ["--verfahren", "v2"]
    vorher = sorted(os.listdir(tmp_path))                    # inkl. der Pflichtdateien (G0)
    assert pg.main(grund) == 0
    ausgabe = capsys.readouterr().out
    assert "Verfahren v2" in ausgabe and "NICHTS geschrieben" in ausgabe
    assert not aus.exists()
    assert sorted(os.listdir(tmp_path)) == vorher             # nichts angelegt


def test_v2_trocken_hat_vorrang_vor_schreiben(tmp_path):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + ["--verfahren", "v2", "--schreiben",
                                                    "--trocken"]) == 0
    assert not aus.exists()


def test_v2_schreibt_dieselbe_form_plus_phasen_ohne_vektoren(tmp_path):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + _schreiben_args(tmp_path, datei, aus)) == 0
    zuordnung = (aus / pg.DATEI_ZUORDNUNG).read_text(encoding="utf-8").splitlines()
    assert len(zuordnung) == 16
    assert set(json.loads(zuordnung[0])) == set(pg.FELDER_ZUORDNUNG)
    beispiele = json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert beispiele["verfahren"] == "mittelpunkt_phasen"
    assert len(beispiele["gruppen"]) == 2
    for gruppe in beispiele["gruppen"]:
        assert set(gruppe["phasen"][0]) == {"von", "bis", "anzahl"}
        assert {"kennung", "neu", "name", "groesse", "bilder", "videos", "von", "bis",
                "zwilling_kandidaten", "beispiele"} <= set(gruppe)
    assert '"mittelpunkt":' not in (aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8")
    assert (aus / pg.DATEI_KENNUNGEN).exists()


def test_v2_zwei_schreiblaeufe_zwei_getrennte_sicherungen(tmp_path, monkeypatch, capsys):
    """Die Sicherung vor v2 laeuft ueber den Zeitstempel-Weg (nicht ``_vorher_sichern``).

    Vor jedem Lauf werden die Entscheidungen "frisch vom Handy geholt" (neue
    Aenderungszeit): sonst gilt die Grundwahrheit nach dem ersten Lauf als
    **veraltet** (aelter als die Zuordnung) und G1 sperrt das Schreiben — genau
    so, wie es die Auflage 2 verlangt.
    """
    zeiten = iter(datetime.datetime(2026, 10, 15, 12, 0, s) for s in range(10, 60))

    class Uhr(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return next(zeiten)

    monkeypatch.setattr(pg, "datetime", types.SimpleNamespace(datetime=Uhr))
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    basis = _grund(tmp_path, datei, aus)
    b, v = _pflichtdateien(tmp_path)
    assert pg.main(basis + _schreiben_args(tmp_path, datei, aus,
                                           name="freigabe_1.json")) == 0
    assert not list(aus.glob("*.vorher_*"))                   # erster Lauf: nichts zu sichern
    stand1 = {n: (aus / n).read_bytes() for n in
              (pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN)}
    capsys.readouterr()
    os.utime(b, None)
    os.utime(v, None)
    assert pg.main(basis + _schreiben_args(tmp_path, datei, aus,
                                           name="freigabe_2.json")) == 0
    stand2 = {n: (aus / n).read_bytes() for n in stand1}
    os.utime(b, None)
    os.utime(v, None)
    assert pg.main(basis + _schreiben_args(tmp_path, datei, aus,
                                           name="freigabe_3.json")) == 0
    for name in stand1:
        sicherungen = sorted(aus.glob(name + ".vorher_*"))
        assert len(sicherungen) == 2                          # zwei getrennte Sicherungen
        assert sicherungen[0].read_bytes() == stand1[name]
        assert sicherungen[1].read_bytes() == stand2[name]


def test_nachtragen_kennt_nur_v1(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + ["--nachtragen", str(datei),
                                                    "--verfahren", "v2"]) == 2
    assert "nur das Verfahren v1" in capsys.readouterr().out


def test_bewerten_zeigt_vorher_und_nachher_nur_zahlen(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + ["--schreiben"]) == 0          # v1 als Vorher
    capsys.readouterr()
    vorher = {n: (aus / n).read_bytes() for n in os.listdir(aus)}
    assert pg.main(_grund(tmp_path, datei, aus) + ["--verfahren", "v2", "--bewerten"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Bewertung an den eigenen Entscheidungen" in ausgabe
    assert "Person_" not in ausgabe.split("Bewertung an den eigenen Entscheidungen")[1]
    assert str(tmp_path) not in ausgabe
    assert {n: (aus / n).read_bytes() for n in os.listdir(aus)} == vorher        # nichts geschrieben


def test_bewerten_ohne_bestehende_zuordnung_bewertet_nur_diesen_lauf(tmp_path, capsys):
    datei = _vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    assert pg.main(_grund(tmp_path, datei, aus) + ["--verfahren", "v2", "--bewerten"]) == 0
    assert "Bewertung an den eigenen Entscheidungen" in capsys.readouterr().out
    assert not aus.exists()


def test_v2_ausgabe_geht_durch_die_lesefunktionen_des_quiz(tmp_path, monkeypatch):
    """Die v2-Dateien muessen vom Quiz genauso gelesen werden wie die von v1."""
    from app.services import gruppen_quiz as gq
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    datei = _vektordatei(tmp_path, personen=3, je=8)
    aus = tmp_path / gq.UNTERORDNER
    assert pg.main(_grund(tmp_path, datei, aus)
                   + _schreiben_args(tmp_path, datei, aus)) == 0
    stand = gq.stand()
    assert stand["ok"] is True and stand["gruppen"] == 3
    erste = gq.naechste()
    assert erste["ok"] and not erste["fertig"] and erste["gruppe"]["beispiele"]
    kennung = erste["gruppe"]["kennung"]
    seite = gq.gesichter(kennung)
    assert seite["ok"] and seite["gesamt"] == 8
    antwort = gq.antworten(kennung, "name", "Person A")
    assert antwort["ok"] and antwort["gespeichert"]["name"] == "Person A"
    bestaetigt = pg.bestaetigt_lesen(os.path.join(str(tmp_path), gq.BESTAETIGT_DATEINAME))
    assert bestaetigt == {kennung: "Person A"}
    gq._CACHE.clear()


def test_zweiter_v2_lauf_nach_dem_benennen_behaelt_die_benannte_kennung(tmp_path):
    """Roundtrip: v2 schreibt, der Nutzer benennt, v2 laeuft erneut - Kennung und Name bleiben."""
    datei = _vektordatei(tmp_path, personen=2, je=10)
    aus = tmp_path / "gruppen"
    basis = _grund(tmp_path, datei, aus)
    assert pg.main(basis + _schreiben_args(tmp_path, datei, aus,
                                           name="freigabe_1.json")) == 0
    erst = json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))["gruppen"]
    kennung = erst[0]["kennung"]
    namen = tmp_path / "personen_bestaetigt.json"
    namen.write_text(json.dumps({"bestaetigt": {kennung: "Person A"}}), encoding="utf-8")
    _, v = _pflichtdateien(tmp_path)
    os.utime(namen, None)
    os.utime(v, None)                       # die Entscheidungen kommen frisch vom Handy
    assert pg.main(basis + _schreiben_args(tmp_path, datei, aus, bestaetigt=namen,
                                           name="freigabe_2.json")) == 0
    zweit = {g["kennung"]: g for g in
             json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))["gruppen"]}
    assert zweit[kennung]["name"] == "Person A" and not zweit[kennung]["neu"]
    assert zweit[kennung]["groesse"] == erst[0]["groesse"]


# ── Reine Bausteine (geteilt von v1 und v2) ───────────────────────────────

def test_verschmelzen_gleich_ist_der_einzige_weg_ueber_den_namen():
    label = np.array([0, 0, 1, 1, 2, 2])
    bild = ["a", "b", "c", "d", "e", "f"]
    paare = [(0.9, 0, 1), (0.8, 1, 2), (0.7, 0, 2)]
    kennungen = ["Person_001", "Person_002", None]
    benannt = [{"Person_001"}, {"Person_002"}, set()]
    neu, info = pg._verschmelzen(label, 3, bild, paare, kennungen, benannt=benannt)
    assert len(set(neu.tolist())) == 3                       # Aehnlichkeit allein vereint nichts
    assert info["gleich_vereint"] == 0 and info["vorschlag_wurzeln"] == {2}
    neu, info = pg._verschmelzen(label, 3, bild, paare, kennungen, benannt=benannt,
                                 gleich={("Person_001", "Person_002")})
    assert len(set(neu.tolist())) == 2 and info["gleich_vereint"] == 1


def test_verschmelzen_ohne_benannt_verhaelt_sich_wie_v1():
    label = np.array([0, 0, 1, 1, 2, 2])
    bild = ["a", "b", "c", "d", "a", "f"]                    # Gruppe 0 und 2 teilen Bild "a"
    paare = [(0.9, 0, 1), (0.8, 1, 2), (0.7, 0, 2)]
    neu, info = pg._verschmelzen(label, 3, bild, paare, [None, None, None])
    assert neu[0] == neu[1] == neu[2] == neu[3]              # 0 und 1 sind vereint
    assert neu[4] == neu[5] != neu[0]                        # 2 darf nicht dazu: gleiches Bild
    assert info["gleich_vereint"] == 0 and info["vorschlag_wurzeln"] == set()


def test_aussortieren_behaelt_benannte_auch_unter_der_mindestgroesse():
    label = np.array([0, 0, 0, 1, 2, 2, 2, 2])
    neu, k, nummer = pg._aussortieren(label, 3, 3)
    assert k == 2 and neu.tolist() == [1, 1, 1, -1, 0, 0, 0, 0]
    neu, k, nummer = pg._aussortieren(label, 3, 3, behalten_immer={1})
    assert k == 3 and neu[3] == 2


def test_anlegen_mit_vorbild_startet_mit_dessen_mittelpunkt():
    rng = np.random.default_rng(43)
    e = _basis(rng, 2)
    v = pg.einheitsvektoren(np.array([_gesicht(rng, e[0]) for _ in range(6)]))
    bild = [f"b{i}" for i in range(6)]
    vorab = np.array([-1, -1, 0, 0, -1, -1])
    label = pg._anlegen(v, bild, np.arange(6), 0.55, vorab_label=vorab)
    assert label.tolist() == [0] * 6                         # alle schliessen sich dem Vorbild an
