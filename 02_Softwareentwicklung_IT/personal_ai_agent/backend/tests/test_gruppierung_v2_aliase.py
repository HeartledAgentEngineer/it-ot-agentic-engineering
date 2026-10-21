"""Tests: Aliasmengen und Konflikte (Plan-Fassung 5.3, Auflage 3, Schritt 3).

Alles offline mit ERFUNDENEN Vektoren (numpy, fester Seed), erfundenen Kennungen
und erfundenen Namen ("Person A"). Keine echten Gesichter, keine echten Namen,
nichts unter ``~/foto_sortierung``; Dateien nur in ``tmp_path``.

Geprueft wird Auflage 3 der Plan-Fassung 5.3:

* **Aliasmenge:** jede Vereinigung (``gleich``) fuehrt die Menge aller beteiligten
  Kennungen mit - auch ueber Ketten (A=B, B=C). ``_verschmelzen`` und
  ``gruppieren_v2`` geben sie heraus (``aliasmengen``), ``lauf_rechnen_v2`` reicht
  sie im Speicher an die Bewertung weiter, ``schreiben`` legt sie als Feld
  ``aliase`` je Gruppe und als flache ``aliasmengen.json`` ab - nur zusammen mit
  echtem Schreiben in den Kandidatenordner.
* **Sperrzahlen aliasfaehig:** ein ``gleich``-Merge zweier benannter Kennungen
  loest keine Sperre aus (``durch_gleich_vereint``), die weggemergte Kennung
  erscheint in ``aliase``.
* **Ausschluesse** gelten fuer die ganze Aliasmenge; ein Ausschluss, der ein
  Vorbild der vereinten Gruppe trifft, ist ein Regelkonflikt (fail-closed, Exit 2).
* **``gleich`` ohne sauberen Kern:** die Gruppe entsteht aus dem besten
  verfuegbaren (auch unsicheren) Gesicht; ganz ohne Gesicht zaehlt
  ``gleich_ohne_vorbild``.
* **Bewertung:** ``gruppierung_bewerten`` rechnet mit ``--aliase`` bzw. im
  Speicher aliasaequivalent (transitive Huelle ueber ``_gleiche_gruppe``); ohne
  Aliasangabe bleibt sie kennungsgenau und sagt das.
* **Quiz:** ``gruppen_quiz`` verdaut das Zusatzfeld ``aliase`` unveraendert.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppierung_v2_aliase.py -q
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
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
gb = _laden("gruppierung_bewerten")
D = 128


# ── Erfundene Szenen ───────────────────────────────────────────────────────

def _basis(rng, n):
    q, _ = np.linalg.qr(rng.normal(size=(D, n)))
    return q.T


def _gesicht(rng, mitte, naehe=0.85):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


class Szene:
    """Sammelt Gesichter und baut daraus das ``eingelesen`` des Gruppierers."""

    def __init__(self):
        self.zeilen = []
        self.zaehler = 0

    def dazu(self, vektor, jahr=2015, sauber=True, bild=None, index=0):
        self.zaehler += 1
        self.zeilen.append({"vektor": np.asarray(vektor), "bild": bild or f"b{self.zaehler}",
                            "index": index, "jahr": jahr, "sauber": sauber})
        return len(self.zeilen) - 1

    def person(self, rng, mitte, anzahl, jahre=(2015,), sauber=True, naehe=0.85, bild="p"):
        return [self.dazu(_gesicht(rng, mitte, naehe), jahre[i % len(jahre)], sauber,
                          bild=f"{bild}{self.zaehler + 1}") for i in range(anzahl)]

    def eingelesen(self):
        gesichter = []
        for z in self.zeilen:
            gesichter.append({
                "bild_id": z["bild"], "index": z["index"],
                "bbox": [0, 0, 100 if z["sauber"] else 30, 100], "breite": 1000, "hoehe": 1000,
                "anteil": 0.02, "score": 0.95 if z["sauber"] else 0.70,
                "aufnahme": f"{z['jahr']}-06-01T12:00:00", "video_id": None, "zeit_s": None})
        vektoren = pg.einheitsvektoren(np.array([z["vektor"] for z in self.zeilen]))
        return {"gesichter": gesichter, "vektoren": vektoren, "dateien": [],
                "bilder": len(gesichter), "bilder_gruppiert": len(gesichter),
                "je_grund": {}, "ungueltig": 0, "doppelt": 0}

    def schluessel(self, stelle):
        z = self.zeilen[stelle]
        return (z["bild"], z["index"])


def _abschnitte(rng, anzahl=2, je=14):
    """Eine Person in ``anzahl`` Lebensabschnitten, die einander nicht aehneln.

    Ohne ``gleich`` bleiben es getrennte Gruppen (Kennung ``Person_00N``).
    Rueckgabe ``(szene, basis, stellen)``; ``basis`` hat einen Vektor mehr.
    """
    e = _basis(rng, anzahl + 1)
    szene = Szene()
    stellen = []
    for p in range(anzahl):
        jahre = (2005 + 7 * p, 2006 + 7 * p, 2007 + 7 * p)
        stellen.append(szene.person(rng, e[p], je, jahre=jahre, bild=f"a{p}_"))
    return szene, e, stellen


def _alt(szene, stellen, kennungen=None):
    """Bestehende Zuordnung: Abschnitt ``p`` gehoert zu ``Person_00(p+1)``."""
    alt = {}
    for p, gruppe in enumerate(stellen):
        kennung = (kennungen or {}).get(p, f"Person_{p + 1:03d}")
        for i in gruppe:
            alt[szene.schluessel(i)] = kennung
    return alt


def _vorgaben(gleich=(), ausgeschlossen=(), zugeordnet=None, verschieden=()):
    return {"gleich": {tuple(sorted(p)) for p in gleich},
            "verschieden": {tuple(sorted(p)) for p in verschieden},
            "ausgeschlossen": set(ausgeschlossen), "zugeordnet": dict(zugeordnet or {})}


def _namen(anzahl=2, gleicher_name=True):
    return {f"Person_{p + 1:03d}": ("Person A" if gleicher_name else f"Person {chr(65 + p)}")
            for p in range(anzahl)}


def _lauf(szene, alt, namen, vorg):
    return pg.lauf_rechnen_v2(szene.eingelesen(), alte_zuordnung=alt, bestaetigt=namen,
                              vorgaben=vorg)


GLEICH_12 = (("Person_001", "Person_002"),)


# ── 1. Aliasmenge: Quelle, Kette, Datenweg ─────────────────────────────────

def test_verschmelzen_gibt_die_volle_beteiligtenmenge_heraus():
    label = np.array([0, 0, 1, 1, 2, 2])
    bild = ["a", "b", "c", "d", "e", "f"]
    kennungen = ["Person_001", "Person_002", "Person_003"]
    benannt = [{k} for k in kennungen]
    neu, info = pg._verschmelzen(label, 3, bild, [], kennungen, benannt=benannt,
                                 gleich={("Person_001", "Person_002"),
                                         ("Person_002", "Person_003")})
    assert len(set(neu.tolist())) == 1 and info["gleich_vereint"] == 2
    assert list(info["alias_je_wurzel"].values()) == [kennungen]      # transitiv, sortiert
    # Ohne Vereinigung gibt es keine Aliasmenge.
    neu, info = pg._verschmelzen(label, 3, bild, [], kennungen, benannt=benannt)
    assert info["alias_je_wurzel"] == {}


def test_gruppieren_v2_gibt_je_gruppe_die_aliasmenge_heraus():
    rng = np.random.default_rng(301)
    szene, e, stellen = _abschnitte(rng, 3)
    ein = szene.eingelesen()
    n = len(ein["gesichter"])
    erg = pg.gruppieren_v2(
        ein["vektoren"], [g["bild_id"] for g in ein["gesichter"]], None,
        [int(g["aufnahme"][:4]) for g in ein["gesichter"]], np.ones(n, dtype=bool),
        vorbilder={"Person_001": stellen[0], "Person_002": stellen[1],
                   "Person_003": stellen[2]},
        gleich={("Person_001", "Person_002"), ("Person_002", "Person_003")})
    assert erg["k"] == 1 and erg["benannt"] == ["Person_001"]
    assert erg["info"]["aliasmengen"] == {
        "Person_001": ["Person_001", "Person_002", "Person_003"]}
    assert erg["info"]["alias_je_gruppe"] == [["Person_001", "Person_002", "Person_003"]]


def test_gleich_zweier_benannter_kennungen_blockiert_nicht_und_steht_in_aliase():
    rng = np.random.default_rng(303)
    szene, e, stellen = _abschnitte(rng, 2)
    lauf = _lauf(szene, _alt(szene, stellen), _namen(2), _vorgaben(GLEICH_12))
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["gruppen"][0]["groesse"] == 28
    assert lauf["gruppen"][0]["aliase"] == ["Person_001", "Person_002"]
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_002"]}
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 1
    assert z["benannte_ohne_gruppe"] == 0 and z["leere_benannte_gruppe"] == 0
    assert z["wechsel_unerlaubt"] == 0 and z["benannte_erhalten"] == 2
    assert lauf["sperrzahlen"] == {"benannte_ohne_gruppe": 0, "leere_benannte_gruppe": 0,
                                   "wechsel_unerlaubt": 0}
    assert pg.freigabe_pruefen({"snapshot_sha256": "x", "parameter": {}, "urteil": "pass",
                                "werte": {f: 0 for f in pg.SPERRZAHLEN}},
                               "x", {}, lauf["sperrzahlen"]) == ""
    assert "Durch gleich vereint: 1" in pg.bericht_text(lauf["bericht"])


def test_gruppen_ohne_vereinigung_haben_leere_aliase():
    rng = np.random.default_rng(305)
    szene, e, stellen = _abschnitte(rng, 2)
    lauf = _lauf(szene, _alt(szene, stellen), _namen(2), _vorgaben())
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_002"]
    assert all(g["aliase"] == [] for g in lauf["gruppen"])
    assert lauf["aliasmengen"] == {}
    assert lauf["sperrzahlen"]["benannte_ohne_gruppe"] == 0


def test_kette_a_gleich_b_und_b_gleich_c_ist_eine_aliasmenge():
    rng = np.random.default_rng(307)
    szene, e, stellen = _abschnitte(rng, 3)
    vorg = _vorgaben((("Person_001", "Person_002"), ("Person_002", "Person_003")))
    lauf = _lauf(szene, _alt(szene, stellen), _namen(3), vorg)
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_002", "Person_003"]}
    assert lauf["bericht"]["v2"]["durch_gleich_vereint"] == 2
    assert lauf["bericht"]["v2"]["benannte_erhalten"] == 3
    assert lauf["sperrzahlen"] == {"benannte_ohne_gruppe": 0, "leere_benannte_gruppe": 0,
                                   "wechsel_unerlaubt": 0}


def test_gleich_laesst_eine_dritte_gruppe_ausserhalb_der_aliasmenge():
    rng = np.random.default_rng(309)
    szene, e, stellen = _abschnitte(rng, 3)
    lauf = _lauf(szene, _alt(szene, stellen), _namen(3, gleicher_name=False)
                 | {"Person_001": "Person A", "Person_002": "Person A"},
                 _vorgaben(GLEICH_12))
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_003"]
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_002"]}
    dritte = [g for g in lauf["gruppen"] if g["kennung"] == "Person_003"][0]
    assert dritte["aliase"] == []


def test_aliasmenge_ist_deterministisch():
    erste = []
    for _ in range(2):
        rng = np.random.default_rng(311)
        szene, e, stellen = _abschnitte(rng, 3)
        vorg = _vorgaben((("Person_002", "Person_003"), ("Person_001", "Person_002")))
        erste.append(_lauf(szene, _alt(szene, stellen), _namen(3), vorg)["aliasmengen"])
    assert erste[0] == erste[1]


# ── 1b. Kette ueber eine gesichtslose Kennung (Nachbesserung) ──────────────

KETTE_ABC = (("Person_001", "Person_002"), ("Person_002", "Person_003"))


def _kette_ohne_b(rng):
    """Person_001 und Person_003 haben Gesichter, Person_002 (dazwischen) keines."""
    szene, e, stellen = _abschnitte(rng, 2)
    alt = _alt(szene, stellen, kennungen={0: "Person_001", 1: "Person_003"})
    return szene, e, stellen, alt


def test_kette_ueber_gesichtslose_kennung_vereint_die_enden():
    rng = np.random.default_rng(371)
    szene, e, stellen, alt = _kette_ohne_b(rng)
    lauf = _lauf(szene, alt, _namen(3), _vorgaben(KETTE_ABC))
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["gruppen"][0]["groesse"] == 28
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_002", "Person_003"]}
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 1 and z["gleich_ohne_vorbild"] == 1
    assert z["benannte_ohne_gruppe"] == 0 and z["benannte_erhalten"] == 3
    assert lauf["sperrzahlen"] == {"benannte_ohne_gruppe": 0, "leere_benannte_gruppe": 0,
                                   "wechsel_unerlaubt": 0}


def test_ausschluss_auf_gesichtslose_kennung_trifft_vorbild_der_kette_mit_exit_2():
    rng = np.random.default_rng(373)
    szene, e, stellen, alt = _kette_ohne_b(rng)
    bild, index = szene.schluessel(stellen[1][0])                      # Vorbild von Person_003
    regel = {("Person_002", bild, index)}
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, alt, _namen(3), _vorgaben(KETTE_ABC, ausgeschlossen=regel))
    assert "Regelkonflikte: 1" in str(fehler.value) and "Person_" not in str(fehler.value)


def test_ausschluss_auf_gesichtslose_kennung_sperrt_fremdes_gesicht_der_kette():
    rng = np.random.default_rng(375)
    szene, e, stellen, alt = _kette_ohne_b(rng)
    x = szene.dazu(_gesicht(rng, e[0], 0.97), 2006, bild="x")
    kontrolle = _lauf(szene, alt, _namen(3), _vorgaben(KETTE_ABC))
    assert kontrolle["gesichter"][x]["kennung"] == "Person_001"
    lauf = _lauf(szene, alt, _namen(3),
                 _vorgaben(KETTE_ABC, ausgeschlossen={("Person_002", "x", 0)}))
    assert lauf["gesichter"][x]["kennung"] is None


@pytest.mark.parametrize("ende", ["name", "verschieden"])
def test_kette_mit_unvereinbaren_enden_bleibt_getrennt_und_sperrt(ende):
    rng = np.random.default_rng(377)
    szene, e, stellen, alt = _kette_ohne_b(rng)
    namen = _namen(3)
    vorg = _vorgaben(KETTE_ABC)
    if ende == "name":
        namen["Person_003"] = "Person C"                               # verschiedene Namen
    else:
        vorg["verschieden"].add(("Person_001", "Person_003"))
    lauf = _lauf(szene, alt, namen, vorg)
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_003"]
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 0
    # Person_002 gehoert nicht eindeutig zu einer Gruppe: es bleibt "ohne Gruppe" -> Sperre.
    assert z["benannte_ohne_gruppe"] == 1 and lauf["sperrzahlen"]["benannte_ohne_gruppe"] == 1
    assert lauf["aliasmengen"] == {}


# ── 1c. Konflikt INNERHALB einer gleich-Klasse (Nachbesserung 2) ───────────

KETTE_ABCD = (("Person_001", "Person_002"), ("Person_002", "Person_003"),
              ("Person_003", "Person_004"))


def _kette_vier(rng):
    """Person_001 und Person_004 haben Gesichter; Person_002 und Person_003 keines."""
    szene, e, stellen = _abschnitte(rng, 2)
    alt = _alt(szene, stellen, kennungen={0: "Person_001", 1: "Person_004"})
    return szene, alt


def _pruefe_klasse_bleibt_ungemerged(lauf, gruppen=("Person_001", "Person_004")):
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == list(gruppen)
    assert lauf["aliasmengen"] == {}                                  # auch keine Teilvereinigung
    assert all(g["aliase"] == [] for g in lauf["gruppen"])
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 0 and z["gleich_klassen_mit_konflikt"] == 1
    assert z["benannte_ohne_gruppe"] == 2                             # B und C: gesichtslos
    assert lauf["sperrzahlen"]["benannte_ohne_gruppe"] == 2           # Freigabe gesperrt
    assert "gleich-Klassen mit Konflikt: 1" in pg.bericht_text(lauf["bericht"])


def test_kette_mit_verschieden_zwischen_gesichtslosem_b_und_d_bleibt_getrennt():
    rng = np.random.default_rng(381)
    szene, alt = _kette_vier(rng)
    lauf = _lauf(szene, alt, _namen(4),
                 _vorgaben(KETTE_ABCD, verschieden=[("Person_002", "Person_004")]))
    _pruefe_klasse_bleibt_ungemerged(lauf)


def test_kette_mit_verschiedenen_namen_an_gesichtslosem_b_und_d_bleibt_getrennt():
    rng = np.random.default_rng(383)
    szene, alt = _kette_vier(rng)
    namen = _namen(4)
    namen["Person_002"] = "Person B"                                  # B und D: verschiedene Namen
    lauf = _lauf(szene, alt, namen, _vorgaben(KETTE_ABCD))
    _pruefe_klasse_bleibt_ungemerged(lauf)


def test_kette_ohne_konflikt_mit_gesichtslosen_kennungen_wird_weiter_vereint():
    rng = np.random.default_rng(385)
    szene, alt = _kette_vier(rng)
    lauf = _lauf(szene, alt, _namen(4), _vorgaben(KETTE_ABCD))
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["aliasmengen"] == {"Person_001": [f"Person_00{i}" for i in range(1, 5)]}
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 1 and z["gleich_klassen_mit_konflikt"] == 0
    assert z["benannte_ohne_gruppe"] == 0


@pytest.mark.parametrize("zuordnung", [{0: "Person_001", 1: "Person_002", 2: "Person_003"},
                                       {0: "Person_003", 1: "Person_002", 2: "Person_001"},
                                       {0: "Person_002", 1: "Person_003", 2: "Person_001"}])
def test_klasse_mit_konflikt_und_lauter_gesichtern_vereint_nichts_reihenfolgeunabhaengig(
        zuordnung):
    rng = np.random.default_rng(387)
    szene, e, stellen = _abschnitte(rng, 3)
    alt = _alt(szene, stellen, kennungen=zuordnung)
    # Person_001 und Person_003 sind verschieden; die Kette laeuft ueber Person_002.
    vorg = _vorgaben(KETTE_ABC[::-1],
                     verschieden=[("Person_003", "Person_001")])
    lauf = _lauf(szene, alt, _namen(3), vorg)
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_002",
                                                             "Person_003"]
    assert sorted(g["groesse"] for g in lauf["gruppen"]) == [14, 14, 14]
    assert lauf["aliasmengen"] == {}
    z = lauf["bericht"]["v2"]
    assert z["durch_gleich_vereint"] == 0 and z["gleich_klassen_mit_konflikt"] == 1
    assert z["benannte_ohne_gruppe"] == 0 and z["wechsel_unerlaubt"] == 0


def test_gruppieren_v2_gibt_auch_unbenannte_vereinte_gruppen_heraus():
    rng = np.random.default_rng(379)
    szene, e, stellen = _abschnitte(rng, 2)
    ein = szene.eingelesen()
    n = len(ein["gesichter"])
    erg = pg.gruppieren_v2(
        ein["vektoren"], [g["bild_id"] for g in ein["gesichter"]], None,
        [int(g["aufnahme"][:4]) for g in ein["gesichter"]], np.ones(n, dtype=bool),
        vorbilder={}, vorab_kennung=lambda mitte: ["Person_007", "Person_009"][:len(mitte)],
        gleich={("Person_007", "Person_009")})
    assert erg["k"] == 1 and erg["benannt"] == [None]
    # Schluessel = kleinste beteiligte Kennung (die endgueltige steht erst nach der Vergabe).
    assert erg["info"]["aliasmengen"] == {"Person_007": ["Person_007", "Person_009"]}
    assert erg["info"]["alias_je_gruppe"] == [["Person_007", "Person_009"]]


# ── 2. Ausschluesse gelten fuer die ganze Aliasmenge ───────────────────────

def _mit_zusatzgesicht(sauber, naehe=0.97):
    """Zwei per ``gleich`` vereinte Abschnitte + ein Zusatzgesicht nahe Abschnitt 1."""
    rng = np.random.default_rng(321)
    szene, e, stellen = _abschnitte(rng, 2)
    x = szene.dazu(_gesicht(rng, e[0], naehe), 2006, sauber=sauber, bild="x")
    return szene, stellen, x


@pytest.mark.parametrize("sauber", [True, False], ids=["sauberes", "unsicheres"])
def test_regel_auf_die_finale_kennung_sperrt_das_gesicht(sauber):
    szene, stellen, x = _mit_zusatzgesicht(sauber)
    alt = _alt(szene, stellen)
    kontrolle = _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12))
    assert kontrolle["gesichter"][x]["kennung"] == "Person_001"       # Beweis: sonst gruppiert
    regel = {("Person_001", "x", 0)}
    lauf = _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12, ausgeschlossen=regel))
    assert lauf["gesichter"][x]["kennung"] is None
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


@pytest.mark.parametrize("sauber", [True, False], ids=["sauberes", "unsicheres"])
def test_regel_auf_die_herkunftskennung_wirkt_nach_der_vereinigung(sauber):
    szene, stellen, x = _mit_zusatzgesicht(sauber)
    alt = _alt(szene, stellen)
    kontrolle = _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12))
    assert kontrolle["gesichter"][x]["kennung"] == "Person_001"
    # Die Regel nennt Person_002 - die weggemergte Herkunftskennung.
    regel = {("Person_002", "x", 0)}
    lauf = _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12, ausgeschlossen=regel))
    assert lauf["gesichter"][x]["kennung"] is None
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_002"]}
    assert lauf["sperrzahlen"]["wechsel_unerlaubt"] == 0
    # Ohne gleich gibt es keine Aliasmenge: dieselbe Regel sperrt dann nur Person_002.
    ohne = _lauf(szene, alt, _namen(2), _vorgaben(ausgeschlossen=regel))
    assert ohne["gesichter"][x]["kennung"] == "Person_001"


def test_ausschluss_eines_alten_gesichts_ueber_die_herkunftskennung_bleibt_draussen():
    """Gesicht war in Person_002 und ist dort ausgeschlossen: es bleibt draussen."""
    rng = np.random.default_rng(323)
    szene, e, stellen = _abschnitte(rng, 2)
    alt = _alt(szene, stellen)
    ziel = stellen[1][0]
    bild, index = szene.schluessel(ziel)
    lauf = _lauf(szene, alt, _namen(2),
                 _vorgaben(GLEICH_12, ausgeschlossen={("Person_002", bild, index)}))
    assert lauf["gesichter"][ziel]["kennung"] is None
    z = lauf["bericht"]["v2"]
    assert z["ausschluss_genehmigt"] == 1 and z["wechsel_unerlaubt"] == 0


def test_regelkonflikt_ausschluss_trifft_ein_vorbild_der_vereinten_gruppe():
    rng = np.random.default_rng(325)
    szene, e, stellen = _abschnitte(rng, 2)
    alt = _alt(szene, stellen)
    bild, index = szene.schluessel(stellen[0][0])                  # Vorbild von Person_001
    regel = {("Person_002", bild, index)}                           # Ausschluss in der Alias-Kennung
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12, ausgeschlossen=regel))
    text = str(fehler.value)
    assert "Regelkonflikte: 1" in text
    assert "Person_" not in text and bild not in text                # nur die Zahl
    # Ohne gleich ist dieselbe Regel kein Konflikt (zwei getrennte Personen).
    _lauf(szene, alt, _namen(2), _vorgaben(ausgeschlossen=regel))


def test_regelkonflikt_trifft_auch_ein_festes_vorbild():
    rng = np.random.default_rng(327)
    szene, e, stellen = _abschnitte(rng, 2)
    y = szene.dazu(_gesicht(rng, e[1]), 2013, bild="y")
    fest = {("y", 0): {"name": "Person A", "kennung": "Person_001"}}
    # Fest in Person_001; Ausschluss in Person_002, das per gleich dieselbe Gruppe ist.
    vorg = _vorgaben(GLEICH_12, ausgeschlossen={("Person_002", "y", 0)}, zugeordnet=fest)
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, _alt(szene, stellen), _namen(2), vorg)
    assert "Regelkonflikte: 1" in str(fehler.value)


# ── 3. gleich + feste Einzelzuordnung ──────────────────────────────────────

def test_gleich_plus_feste_zuordnung_landet_in_der_vereinten_gruppe():
    rng = np.random.default_rng(331)
    szene, e, stellen = _abschnitte(rng, 2)
    y = szene.dazu(_gesicht(rng, e[1]), 2013, bild="y")
    # Fest in die Herkunftskennung Person_002 - nach gleich ist das Person_001.
    fest = {("y", 0): {"name": "Person A", "kennung": "Person_002"}}
    lauf = _lauf(szene, _alt(szene, stellen), _namen(2), _vorgaben(GLEICH_12, zugeordnet=fest))
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]   # keine Restgruppe
    assert lauf["gesichter"][y]["kennung"] == "Person_001"
    assert lauf["gruppen"][0]["groesse"] == 29
    assert lauf["gruppen"][0]["aliase"] == ["Person_001", "Person_002"]
    assert lauf["sperrzahlen"] == {"benannte_ohne_gruppe": 0, "leere_benannte_gruppe": 0,
                                   "wechsel_unerlaubt": 0}


def test_gleich_plus_feste_zuordnung_ist_kein_wechsel():
    """Das Gesicht stand schon in Person_001 und wird fest Person_002 zugeordnet."""
    rng = np.random.default_rng(333)
    szene, e, stellen = _abschnitte(rng, 2)
    y = szene.dazu(_gesicht(rng, e[0]), 2006, bild="y")
    alt = _alt(szene, stellen)
    alt[("y", 0)] = "Person_001"
    fest = {("y", 0): {"name": "Person A", "kennung": "Person_002"}}
    lauf = _lauf(szene, alt, _namen(2), _vorgaben(GLEICH_12, zugeordnet=fest))
    assert lauf["gesichter"][y]["kennung"] == "Person_001"
    z = lauf["bericht"]["v2"]
    assert z["wechsel_genehmigt"] == 0 and z["wechsel_unerlaubt"] == 0


def test_gleich_plus_feste_zuordnung_in_fremde_kennung_bleibt_genehmigter_wechsel():
    rng = np.random.default_rng(335)
    szene, e, stellen = _abschnitte(rng, 3)
    y = szene.dazu(_gesicht(rng, e[2]), 2020, bild="y")
    alt = _alt(szene, stellen)
    alt[("y", 0)] = "Person_001"                                    # stand in der vereinten Gruppe
    fest = {("y", 0): {"name": "Person C", "kennung": "Person_003"}}
    namen = {"Person_001": "Person A", "Person_002": "Person A", "Person_003": "Person C"}
    lauf = _lauf(szene, alt, namen, _vorgaben(GLEICH_12, zugeordnet=fest))
    assert lauf["gesichter"][y]["kennung"] == "Person_003"
    z = lauf["bericht"]["v2"]
    assert z["wechsel_genehmigt"] == 1 and z["wechsel_unerlaubt"] == 0


# ── 4. gleich ohne sauberen Kern ───────────────────────────────────────────

def _mit_unsicherer_kennung(rng, gesichter=3):
    """Abschnitt 1+2 sauber; Person_003 hat NUR unsichere Gesichter (bestehende Zuordnung)."""
    szene, e, stellen = _abschnitte(rng, 2)
    unsicher = szene.person(rng, e[2], gesichter, jahre=(2010,), sauber=False, bild="u")
    alt = _alt(szene, stellen)
    for i in unsicher:
        alt[szene.schluessel(i)] = "Person_003"
    return szene, stellen, unsicher, alt


def test_benannte_kennung_ohne_sauberen_kern_mit_gesicht_bildet_die_gruppe():
    rng = np.random.default_rng(341)
    szene, stellen, unsicher, alt = _mit_unsicherer_kennung(rng)
    namen = {"Person_001": "Person A", "Person_002": "Person B", "Person_003": "Person A"}
    vorg = _vorgaben((("Person_001", "Person_003"),))
    lauf = _lauf(szene, alt, namen, vorg)
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_002"]
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_003"]}
    for i in unsicher:                                               # alle drei bleiben in der Person
        assert lauf["gesichter"][i]["kennung"] == "Person_001"
    z = lauf["bericht"]["v2"]
    assert z["gleich_ohne_vorbild"] == 0 and z["gleich_unsicheres_vorbild"] == 1
    assert z["benannte_ohne_gruppe"] == 0 and z["wechsel_unerlaubt"] == 0
    assert lauf["sperrzahlen"]["benannte_ohne_gruppe"] == 0
    assert z["gesichter_sauber"] == 28                               # die Zaehlung bleibt ehrlich
    assert z["kern_ohne_gruppe"] == 0


def test_benannte_kennung_ohne_sauberen_kern_ohne_gleich_bleibt_fail_closed():
    """Ohne gleich gilt die alte Regel: kein Kern, aber geschuetzte Gesichter -> Exit-2-Fehler."""
    rng = np.random.default_rng(343)
    szene, stellen, unsicher, alt = _mit_unsicherer_kennung(rng)
    namen = {"Person_001": "Person A", "Person_002": "Person B", "Person_003": "Person C"}
    with pytest.raises(pg.PersonenFehler) as fehler:
        _lauf(szene, alt, namen, _vorgaben())
    assert "Regel-B-Konflikte: 1" in str(fehler.value)


def test_benannte_kennung_ohne_jedes_gesicht_zaehlt_gleich_ohne_vorbild():
    rng = np.random.default_rng(345)
    szene, e, stellen = _abschnitte(rng, 2)
    namen = {"Person_001": "Person A", "Person_002": "Person B", "Person_003": "Person A"}
    vorg = _vorgaben((("Person_001", "Person_003"),))
    lauf = _lauf(szene, _alt(szene, stellen), namen, vorg)
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_002"]
    z = lauf["bericht"]["v2"]
    assert z["gleich_ohne_vorbild"] == 1
    assert z["benannte_ohne_gruppe"] == 0                           # die Partnergruppe fuehrt sie
    assert lauf["aliasmengen"] == {"Person_001": ["Person_001", "Person_003"]}
    assert namen["Person_003"] == "Person A"                        # der Name bleibt stehen
    assert "gleich ohne Vorbild: 1" in pg.bericht_text(lauf["bericht"])


def test_zwei_gleiche_kennungen_ohne_jedes_gesicht_blockieren_ehrlich():
    rng = np.random.default_rng(347)
    szene, e, stellen = _abschnitte(rng, 2)
    namen = {"Person_001": "Person A", "Person_002": "Person B",
             "Person_003": "Person C", "Person_004": "Person C"}
    vorg = _vorgaben((("Person_003", "Person_004"),))
    lauf = _lauf(szene, _alt(szene, stellen), namen, vorg)
    z = lauf["bericht"]["v2"]
    assert z["gleich_ohne_vorbild"] == 2
    assert z["benannte_ohne_gruppe"] == 2 and lauf["sperrzahlen"]["benannte_ohne_gruppe"] == 2
    assert {k for k in namen} == {"Person_001", "Person_002", "Person_003", "Person_004"}


def test_unsicheres_vorbild_ist_das_beste_verfuegbare_gesicht():
    rng = np.random.default_rng(349)
    szene, e, stellen = _abschnitte(rng, 2)
    schwach = szene.dazu(_gesicht(rng, e[2], 0.9), 2010, sauber=False, bild="s1")
    stark = szene.dazu(_gesicht(rng, e[2], 0.9), 2010, sauber=False, bild="s2")
    ein = szene.eingelesen()
    ein["gesichter"][schwach]["score"] = 0.55                        # unsicherer als das andere
    alt = _alt(szene, stellen)
    alt[("s1", 0)] = alt[("s2", 0)] = "Person_003"
    namen = {"Person_001": "Person A", "Person_002": "Person B", "Person_003": "Person A"}
    lauf = pg.lauf_rechnen_v2(ein, alte_zuordnung=alt, bestaetigt=namen,
                              vorgaben=_vorgaben((("Person_001", "Person_003"),)))
    assert lauf["bericht"]["v2"]["gleich_unsicheres_vorbild"] == 1
    assert lauf["gesichter"][stark]["kennung"] == "Person_001"
    assert lauf["gesichter"][schwach]["kennung"] == "Person_001"
    assert lauf["bericht"]["v2"]["wechsel_unerlaubt"] == 0


# ── 5. Bewertung: transitive Huelle, --aliase, Hinweiszeile ────────────────

def test_gleiche_gruppe_ist_die_transitive_huelle():
    huelle = gb.aliase_huelle({"A": ["A", "B"], "C": ["B", "C"], "X": ["X", "Y"]})
    assert gb._gleiche_gruppe("A", "A", huelle)
    assert gb._gleiche_gruppe("A", "B", huelle) and gb._gleiche_gruppe("B", "A", huelle)
    assert gb._gleiche_gruppe("A", "C", huelle)                       # Kette A-B, B-C
    assert gb._gleiche_gruppe("Y", "X", huelle)
    assert not gb._gleiche_gruppe("A", "X", huelle)
    assert not gb._gleiche_gruppe("A", None, huelle) and not gb._gleiche_gruppe(None, None, huelle)
    # Ohne Aliasangabe: nur dieselbe Kennung ist dieselbe Gruppe.
    assert gb._gleiche_gruppe("A", "A") and not gb._gleiche_gruppe("A", "B")
    assert not gb._gleiche_gruppe("A", "B", {})


def _z(bild, kennung, sauber=True):
    return {"bild_id": str(bild), "index": 0, "kennung": kennung, "score": 0.95,
            "bbox": [0, 0, 100 if sauber else 30, 100], "breite": 1000, "hoehe": 1000,
            "anteil": 0.02}


def _vorher_nachher():
    vorher = gb.zuordnung_aus_zeilen([_z(1, "Person_001"), _z(2, "Person_001"),
                                      _z(3, "Person_002"), _z(4, "Person_002"),
                                      _z(5, "Person_003")])[0]
    nachher = gb.zuordnung_aus_zeilen([_z(1, "Person_001"), _z(2, "Person_001"),
                                       _z(3, "Person_001"), _z(4, "Person_001"),
                                       _z(5, "Person_003")])[0]
    return vorher, nachher


def test_wechsel_ist_ohne_aliasangabe_kennungsgenau_und_mit_alias_nicht():
    vorher, nachher = _vorher_nachher()
    ohne = gb.wechsel(vorher, nachher)
    assert ohne["gruppe_gewechselt"] == 2 and ohne["gleiche_gruppe"] == 3
    mit = gb.wechsel(vorher, nachher, {"Person_001": ["Person_001", "Person_002"]})
    assert mit["gruppe_gewechselt"] == 0 and mit["gleiche_gruppe"] == 5


def test_vergleichsbericht_sagt_ob_er_aliasaequivalent_rechnet():
    vorher, nachher = _vorher_nachher()
    bestaetigt = {"Person_001": "Person A", "Person_002": "Person A"}
    ohne = gb.vergleich_bericht(vorher, nachher, bestaetigt, {})
    assert "kennungsgenau" in ohne and "Gruppe gewechselt: 2" in ohne
    mit = gb.vergleich_bericht(vorher, nachher, bestaetigt, {},
                               aliase={"Person_001": ["Person_001", "Person_002"]})
    assert "kennungsgenau" not in mit and "Gruppe gewechselt: 0" in mit
    assert "Aliasmengen: 1 Gruppen mit 2 Kennungen" in mit
    einzel = gb.einzel_bericht(nachher, bestaetigt, {})
    assert "kennungsgenau" in einzel
    for text in (ohne, mit, einzel):
        assert "Person_" not in text and "/" not in text and "\\" not in text


def test_bewerten_zaehlt_verschieden_und_ausschluss_aliasaequivalent():
    vorher, nachher = _vorher_nachher()
    vorgaben = {"verschieden": {("Person_002", "Person_003")},
                "ausgeschlossen": {("Person_002", "3", 0)}}
    ohne = gb.bewerten(nachher, {}, vorgaben, vorher=vorher)
    assert ohne["verschieden_kennung_fehlt"] == 1                     # Person_002 gibt es nicht mehr
    assert ohne["ausgeschlossen_bruch"] == 0
    mit = gb.bewerten(nachher, {}, vorgaben, vorher=vorher,
                      aliase={"Person_001": ["Person_001", "Person_002"]})
    assert mit["verschieden_kennung_fehlt"] == 0                      # lebt in der Aliasmenge weiter
    assert mit["ausgeschlossen_bruch"] == 1                           # Gesicht 3 liegt wieder dort


def test_aliase_lesen_prueft_die_form(tmp_path):
    gut = tmp_path / "aliasmengen.json"
    gut.write_text(json.dumps({"Person_001": ["Person_001", "Person_002"]}), encoding="utf-8")
    assert gb.aliase_lesen(str(gut)) == {"Person_001": ["Person_001", "Person_002"]}
    for inhalt in ("[]", '{"A": "B"}', '{"A": [1]}', "kein json"):
        schlecht = tmp_path / "schlecht.json"
        schlecht.write_text(inhalt, encoding="utf-8")
        with pytest.raises(ValueError):
            gb.aliase_lesen(str(schlecht))
    with pytest.raises(ValueError):
        gb.aliase_lesen(str(tmp_path / "gibtsnicht.json"))


def _bewerten_main(argv):
    ausgabe, fehler = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(ausgabe), contextlib.redirect_stderr(fehler):
        code = gb.main(argv)
    return code, ausgabe.getvalue(), fehler.getvalue()


def test_bewerten_kommandozeile_mit_aliase_datei(tmp_path):
    vorher_zeilen = [_z(1, "Person_001"), _z(2, "Person_002"), _z(3, "Person_002")]
    nachher_zeilen = [_z(1, "Person_001"), _z(2, "Person_001"), _z(3, "Person_001")]
    v, n = tmp_path / "vorher.jsonl", tmp_path / "nachher.jsonl"
    v.write_text("\n".join(json.dumps(x) for x in vorher_zeilen) + "\n", encoding="utf-8")
    n.write_text("\n".join(json.dumps(x) for x in nachher_zeilen) + "\n", encoding="utf-8")
    b, g = tmp_path / "personen_bestaetigt.json", tmp_path / "personen_vorgaben.json"
    b.write_text(json.dumps({"bestaetigt": {"Person_001": "Person A",
                                            "Person_002": "Person A"}}), encoding="utf-8")
    g.write_text(json.dumps({"gleich": [["Person_001", "Person_002"]]}), encoding="utf-8")
    alias = tmp_path / "aliasmengen.json"
    alias.write_text(json.dumps({"Person_001": ["Person_001", "Person_002"]}), encoding="utf-8")
    grund = ["--vorher", str(v), "--nachher", str(n), "--bestaetigt", str(b),
             "--vorgaben", str(g)]
    vorher_dateien = sorted(os.listdir(tmp_path))

    code, ohne, _ = _bewerten_main(grund)
    assert code == 0 and "kennungsgenau" in ohne and "Gruppe gewechselt: 2" in ohne
    code, mit, fehler = _bewerten_main(grund + ["--aliase", str(alias)])
    assert code == 0, fehler
    assert "Gruppe gewechselt: 0" in mit and "kennungsgenau" not in mit
    assert "Aliasmengen: 1 Gruppen mit 2 Kennungen" in mit
    assert sorted(os.listdir(tmp_path)) == vorher_dateien             # schreibt nichts

    code, _, fehler = _bewerten_main(grund + ["--aliase", str(tmp_path / "fehlt.json")])
    assert code == 2 and str(tmp_path) not in fehler
    (tmp_path / "kaputt.json").write_text("[1]", encoding="utf-8")
    code, _, fehler = _bewerten_main(grund + ["--aliase", str(tmp_path / "kaputt.json")])
    assert code == 2 and str(tmp_path) not in fehler


# ── 6. Kommandozeile: Trockenlauf, Schreiben, Konflikt ─────────────────────

def _zeile(bild_id, vektor, jahr=2016, seite=200):
    return json.dumps({
        "bild_id": bild_id, "breite": 1000, "hoehe": 1000,
        "metadaten": {"aufnahme": f"{jahr}-06-01T12:00:00"},
        "gesichter": [{"bbox": [10, 10, seite, seite], "score": 0.95,
                       "embedding": [float(x) for x in vektor]}]})


class _Args:
    def __init__(self):
        self.zuordnung = pg.ZUORDNUNG_AEHNLICH
        self.verschmelzen = pg.VERSCHMELZ_AEHNLICH
        self.zwilling = pg.ZWILLING_AEHNLICH
        self.min_groesse = pg.MIN_GROESSE
        self.min_score = None


def _szene_cli(tmp_path, ausschluss_extra=(), gleich=True):
    """Zwei Lebensabschnitte einer Person (Person_001/002), bestehende Zuordnung, Pflichtdateien.

    Rueckgabe ``(vektordatei, ausgabe, kandidat, bestaetigt, vorgaben, stand, ids)``.
    Die Bild-IDs sind Ziffern (``vorgaben_lesen`` verlangt das fuer Ausschluesse).
    """
    rng = np.random.default_rng(351)
    e = _basis(rng, 2)
    zeilen, ids = [], {0: [], 1: []}
    for p in range(2):
        for i in range(8):
            bild = str(1000 + 100 * p + i)
            ids[p].append(bild)
            zeilen.append(_zeile(bild, _gesicht(rng, e[p]), 2005 + 7 * p + (i % 3)))
    datei = tmp_path / "v.jsonl"
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    aus, kandidat = tmp_path / "gruppen", tmp_path / "kandidat"
    aus.mkdir()
    (aus / pg.DATEI_ZUORDNUNG).write_text(
        "\n".join(json.dumps({"bild_id": bild, "index": 0, "kennung": f"Person_00{p + 1}"})
                  for p in range(2) for bild in ids[p]) + "\n", encoding="utf-8")

    b = tmp_path / "personen_bestaetigt.json"
    b.write_text(json.dumps({"bestaetigt": {"Person_001": "Person A",
                                            "Person_002": "Person A"}}), encoding="utf-8")
    ausschluesse = [{"kennung": f"Person_{i + 10:03d}", "bild_id": str(900000 + i), "index": 0}
                    for i in range(50)]
    ausschluesse += [{"kennung": k, "bild_id": bild, "index": 0}
                     for k, bild in ausschluss_extra]
    v = tmp_path / "personen_vorgaben.json"
    v.write_text(json.dumps({
        "gleich": [["Person_001", "Person_002"]] if gleich else [], "verschieden": [],
        "zugeordnet": [], "ausgeschlossen": ausschluesse}), encoding="utf-8")
    stand = _geraetestand(tmp_path, [b, v])
    # Die Entscheidungen sind "frischer" als die bestehende Zuordnung (G1).
    jetzt = time.time() + 60
    os.utime(b, (jetzt, jetzt))
    os.utime(v, (jetzt, jetzt))
    return datei, aus, kandidat, b, v, stand, ids


def _geraetestand(tmp_path, pfade):
    eintraege = {}
    for pfad in pfade:
        roh = pfad.read_bytes()
        daten = json.loads(roh.decode("utf-8"))
        if pfad.name.endswith("bestaetigt.json"):
            roh_eintraege = daten.get("bestaetigt") or {}
            zaehler = {"benannte_kennungen": len(roh_eintraege),
                       "namen": sum(1 for w in roh_eintraege.values() if w.strip())}
        else:
            zaehler = {"gleich": len(daten.get("gleich") or []),
                       "verschieden": len(daten.get("verschieden") or []),
                       "ausgeschlossen": len(daten.get("ausgeschlossen") or []),
                       "fest": len(daten.get("zugeordnet") or [])}
        eintraege[pfad.name] = {"bytes": len(roh), "sha256": hashlib.sha256(roh).hexdigest(),
                                "zaehler": zaehler}
    ziel = tmp_path / "geraetestand.json"
    ziel.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 120)),
        "quelle": "handy", "pflicht": list(pg.PFLICHTQUELLEN), "dateien": eintraege}),
        encoding="utf-8")
    return ziel


def _cli(datei, aus, kandidat, b, v, stand, *zusatz):
    return ["--vektoren", str(datei), "--ausgabe", str(aus), "--ausgabe-kandidat",
            str(kandidat), "--bestaetigt", str(b), "--vorgaben", str(v),
            "--geraetestand", str(stand), "--verfahren", "v2", *zusatz]


def _freigabe(tmp_path, datei, aus, b, v):
    parameter = pg.parameter_stand(_Args())
    hash_ist = pg.eingabe_hash([str(datei)], str(b), str(v),
                               os.path.join(str(aus), pg.DATEI_KENNUNGEN),
                               os.path.join(str(aus), pg.DATEI_ZUORDNUNG), parameter)
    ziel = tmp_path / "freigabe.json"
    ziel.write_text(json.dumps({"snapshot_sha256": hash_ist, "parameter": parameter,
                                "urteil": "pass",
                                "werte": {feld: 0 for feld in pg.SPERRZAHLEN}}),
                    encoding="utf-8")
    return str(ziel)


def _dateien_unter(ordner):
    return sorted(os.listdir(ordner)) if os.path.isdir(ordner) else None


def test_trockenlauf_mit_bewertung_schreibt_nichts_rechnet_aber_aliasfaehig(tmp_path, capsys):
    datei, aus, kandidat, b, v, stand, ids = _szene_cli(tmp_path)
    vorher = {n: (aus / n).read_bytes() for n in os.listdir(aus)}
    alle_vorher = _dateien_unter(tmp_path)
    assert pg.main(_cli(datei, aus, kandidat, b, v, stand, "--bewerten")) == 0
    ausgabe = capsys.readouterr().out
    bewertung = ausgabe.split("Bewertung an den eigenen Entscheidungen")[1]
    assert "Gruppe gewechselt: 0" in bewertung                        # aliasaequivalent
    assert "Aliasmengen: 1 Gruppen mit 2 Kennungen" in bewertung
    assert "kennungsgenau" not in bewertung
    assert "Person_" not in bewertung and str(tmp_path) not in bewertung
    assert "Durch gleich vereint: 1" in ausgabe
    # Trockenlauf: keine Datei, kein Kandidatenordner, bestehende Zuordnung unveraendert.
    assert not kandidat.exists() and not (aus / "aliasmengen.json").exists()
    assert {n: (aus / n).read_bytes() for n in os.listdir(aus)} == vorher
    assert _dateien_unter(tmp_path) == alle_vorher


def test_schreiben_legt_aliase_und_aliasmengen_nur_im_kandidatenordner_an(tmp_path, capsys):
    datei, aus, kandidat, b, v, stand, ids = _szene_cli(tmp_path)
    freigabe = _freigabe(tmp_path, datei, aus, b, v)
    zuordnung_vorher = (aus / pg.DATEI_ZUORDNUNG).read_bytes()
    # Der gleich-Merge zweier benannter Kennungen blockiert die Freigabe NICHT (Exit 0, nicht 3).
    assert pg.main(_cli(datei, aus, kandidat, b, v, stand, "--schreiben",
                        "--freigabe", freigabe)) == 0
    assert "Freigabe gueltig" in capsys.readouterr().out
    beispiele = json.loads((kandidat / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert [g["kennung"] for g in beispiele["gruppen"]] == ["Person_001"]
    assert beispiele["gruppen"][0]["aliase"] == ["Person_001", "Person_002"]
    flach = json.loads((kandidat / "aliasmengen.json").read_text(encoding="utf-8"))
    assert flach == {"Person_001": ["Person_001", "Person_002"]}
    assert (aus / pg.DATEI_ZUORDNUNG).read_bytes() == zuordnung_vorher
    assert not (aus / "aliasmengen.json").exists()                    # produktiv unberuehrt
    # Die Datei laesst sich fuer die spaetere Bewertung eines Stands wieder lesen.
    assert gb.aliase_lesen(str(kandidat / "aliasmengen.json")) == flach


def test_schreiben_ohne_vereinigung_legt_eine_leere_aliasmengen_datei_an(tmp_path):
    datei, aus, kandidat, b, v, stand, ids = _szene_cli(tmp_path, gleich=False)
    freigabe = _freigabe(tmp_path, datei, aus, b, v)
    assert pg.main(_cli(datei, aus, kandidat, b, v, stand, "--schreiben",
                        "--freigabe", freigabe)) == 0
    assert json.loads((kandidat / "aliasmengen.json").read_text(encoding="utf-8")) == {}
    beispiele = json.loads((kandidat / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert all(g["aliase"] == [] for g in beispiele["gruppen"])


def test_v1_schreibt_weder_aliase_noch_aliasmengen_datei(tmp_path):
    datei, aus, kandidat, b, v, stand, ids = _szene_cli(tmp_path)
    ziel = tmp_path / "v1"
    code = pg.main(["--vektoren", str(datei), "--ausgabe", str(ziel), "--bestaetigt", str(b),
                    "--vorgaben", str(v), "--schreiben"])
    assert code == 0
    assert not (ziel / "aliasmengen.json").exists()
    beispiele = json.loads((ziel / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert all("aliase" not in g for g in beispiele["gruppen"])


def test_regelkonflikt_endet_mit_exit_2_und_schreibt_nichts(tmp_path, capsys):
    datei, aus, kandidat, b, v, stand, ids = _szene_cli(
        tmp_path, ausschluss_extra=[("Person_002", "1000")])           # Vorbild von Person_001
    alle_vorher = _dateien_unter(tmp_path)
    assert pg.main(_cli(datei, aus, kandidat, b, v, stand)) == 2
    ausgabe = capsys.readouterr().out
    assert "Regelkonflikte: 1" in ausgabe
    assert "Person_" not in ausgabe.split("Regelkonflikte")[1] and "1000" not in ausgabe
    assert _dateien_unter(tmp_path) == alle_vorher and not kandidat.exists()


# ── 7. Quiz: das Zusatzfeld ``aliase`` ist rueckwaertsvertraeglich ──────────

def test_quiz_verdaut_eine_ausgabe_mit_aliase_unveraendert(tmp_path, monkeypatch):
    from app.services import gruppen_quiz as gq
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    rng = np.random.default_rng(361)
    szene, e, stellen = _abschnitte(rng, 3)
    namen = {"Person_001": "Person A", "Person_002": "Person A"}
    lauf = _lauf(szene, _alt(szene, stellen), namen, _vorgaben(GLEICH_12))
    assert len(lauf["gruppen"]) == 2                                   # vereinte Gruppe + dritte
    assert "Person_001" in {g["kennung"] for g in lauf["gruppen"]}
    ziel = tmp_path / gq.UNTERORDNER
    pg.schreiben(lauf, str(ziel))
    roh = json.loads((ziel / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert any(g["aliase"] for g in roh["gruppen"])                    # das Zusatzfeld ist da
    kennungen = {g["kennung"] for g in roh["gruppen"]}

    stand = gq.stand()
    assert stand["ok"] is True and stand["gruppen"] == len(kennungen) == 2   # keine Zusatzperson
    gelistet = {g["kennung"] for g in gq.liste("offen")["gruppen"]}
    gelistet |= {g["kennung"] for g in gq.liste("benannt")["gruppen"]}
    assert gelistet == kennungen
    assert not any("aliase" in g for g in gq.liste("offen")["gruppen"])
    # Eine weggemergte Kennung wird NICHT als eigene Person gelesen.
    assert "Person_002" not in kennungen | gelistet
    # Die flache Datei neben den Beispielen wird vom Quiz nicht angefasst.
    assert json.loads((ziel / pg.DATEI_ALIASE).read_text(encoding="utf-8")) == lauf["aliasmengen"]
    gq._CACHE.clear()


# ── 8. v1 bleibt wie vor Schritt 3 (Nachbesserung 3) ───────────────────────
#
# Die transitive Klassenbildung ueber gesichtslose Kennungen und die Konflikt-
# pruefung je Klasse gehoeren NUR zu v2. v1 nimmt den alten Paar-Weg und muss
# sich in jedem Fall verhalten wie in HEAD (vor Schritt 3).
# Fester Bezug: letzter Commit von personen_gruppieren.py VOR Schritt 3. Mit "HEAD"
# wuerde der Vergleich nach dem Commit trivial (neue Fassung gegen sich selbst).
V1_BEZUG = "80a4c69"

def _v1_lauf(modul, szene, e, kennungen, gleich=(), verschieden=(), namen=None):
    """v1-Lauf mit Altbestand: Abschnitt ``p`` bekommt ``kennungen[p]`` ueber den Mittelpunkt."""
    altbestand = [{"kennung": k, "mittelpunkt": e[p].tolist()} for p, k in kennungen.items()]
    return modul.lauf_rechnen(szene.eingelesen(), altbestand=altbestand,
                              bestaetigt=dict(namen or {}),
                              vorgaben=_vorgaben(gleich, verschieden=verschieden))


def _v1_kurz(lauf):
    """Der Teil eines v1-Laufs, der vergleichbar ist (ohne Laufzeit)."""
    gruppen = sorted((g["kennung"], g["neu"], g["name"], g["groesse"], g["bilder"], g["videos"],
                      g["von"], g["bis"], "aliase" in g) for g in lauf["gruppen"])
    gesichter = [g.get("kennung") for g in lauf["gesichter"]]
    altbestand = sorted((a["kennung"], [round(x, 5) for x in a["mittelpunkt"]])
                        for a in lauf["altbestand"])
    bericht = {k: w for k, w in lauf["bericht"].items() if k != "sekunden"}
    return {"gruppen": gruppen, "gesichter": gesichter, "altbestand": altbestand,
            "bericht": bericht}


def test_v1_kette_mit_gesichtslosen_mitgliedern_vereint_nicht_a_und_d():
    # A=B=C=D, nur A und D haben ein Gesicht: v1 hat nie ueber B und C hinweg
    # vereint (Paarweg: kein Paar hat zwei Gruppen) - zwei Gruppen, nichts vereint.
    rng = np.random.default_rng(401)
    szene, e, stellen = _abschnitte(rng, 2)
    kennungen = {0: "Person_001", 1: "Person_004"}
    lauf = _v1_lauf(pg, szene, e, kennungen, gleich=KETTE_ABCD)
    assert sorted(g["kennung"] for g in lauf["gruppen"]) == ["Person_001", "Person_004"]
    assert sorted(g["groesse"] for g in lauf["gruppen"]) == [14, 14]
    # Auch das direkte Ergebnis des geteilten Schritts: v1 (``benannt=None``) meldet 0.
    label = np.array([0] * 14 + [1] * 14)
    bild = [f"b{i}" for i in range(28)]
    _, info = pg._verschmelzen(label, 2, bild, [], ["Person_001", "Person_004"],
                               gleich={tuple(sorted(p)) for p in KETTE_ABCD})
    assert info["gleich_vereint"] == 0 and info["gleich_klassen_mit_konflikt"] == 0
    assert info["alias_je_wurzel"] == {}


def test_v1_gleich_zwischen_zwei_gruppen_vereint_weiterhin():
    rng = np.random.default_rng(402)
    szene, e, stellen = _abschnitte(rng, 2)
    lauf = _v1_lauf(pg, szene, e, {0: "Person_001", 1: "Person_002"}, gleich=GLEICH_12)
    assert [g["kennung"] for g in lauf["gruppen"]] == ["Person_001"]
    assert lauf["gruppen"][0]["groesse"] == 28
    assert "aliase" not in lauf["gruppen"][0]


def _head_modul(tmp_path):
    """Die Fassung von ``personen_gruppieren.py`` aus HEAD (vor Schritt 3), nur lesend geholt."""
    try:
        roh = subprocess.run(["git", "show", f"{V1_BEZUG}:./personen_gruppieren.py"], cwd=WERKZEUGE,
                             capture_output=True, check=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git show " + V1_BEZUG + " ist hier nicht verfuegbar")
    ziel = tmp_path / "personen_gruppieren_head.py"
    ziel.write_bytes(roh)
    spez = importlib.util.spec_from_file_location("personen_gruppieren_head", str(ziel))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# (Name, Abschnitte, Kennung je Abschnitt, gleich, verschieden, Namen, Soll: Kennungen, Groessen)
V1_FAELLE = [
    ("kette_mit_luecken", 2, {0: "Person_001", 1: "Person_004"}, KETTE_ABCD, (), {},
     ["Person_001", "Person_004"], [14, 14]),
    ("kette_ueber_gesichtsloses_b", 2, {0: "Person_001", 1: "Person_003"}, KETTE_ABC, (), {},
     ["Person_001", "Person_003"], [14, 14]),
    ("direktes_gleich", 3, {0: "Person_001", 1: "Person_002", 2: "Person_003"}, GLEICH_12, (),
     {}, ["Person_001", "Person_003"], [14, 28]),
    # verschieden(A, C) blockiert das SPAETERE Paar: A+B werden vereint, C bleibt - die
    # Reihenfolge der gleich-Paare zaehlt in v1 weiterhin (kein "alles oder nichts").
    ("verschieden_blockiert_spaeteres_paar", 3,
     {0: "Person_001", 1: "Person_002", 2: "Person_003"}, KETTE_ABC,
     (("Person_001", "Person_003"),), {}, ["Person_002", "Person_003"], [14, 28]),
    ("verschiedene_namen_trotz_gleich", 2, {0: "Person_001", 1: "Person_002"}, GLEICH_12, (),
     {"Person_001": "Person A", "Person_002": "Person B"},
     ["Person_001", "Person_002"], [14, 14]),
    ("gleiche_namen_ohne_gleich", 2, {0: "Person_001", 1: "Person_002"}, (), (),
     {"Person_001": "Person A", "Person_002": "Person A"},
     ["Person_001", "Person_002"], [14, 14]),
    ("ohne_regeln", 3, {0: "Person_001", 1: "Person_002", 2: "Person_003"}, (), (), {},
     ["Person_001", "Person_002", "Person_003"], [14, 14, 14]),
]


@pytest.mark.parametrize("fall", V1_FAELLE, ids=[f[0] for f in V1_FAELLE])
def test_v1_verhaelt_sich_wie_vor_schritt_3(fall, tmp_path):
    name, anzahl, kennungen, gleich, verschieden, namen, soll_kennungen, soll_groessen = fall
    rng = np.random.default_rng(410 + len(name))
    szene, e, stellen = _abschnitte(rng, anzahl)
    neu = _v1_lauf(pg, szene, e, kennungen, gleich, verschieden, namen)
    # Festgehaltene Sollwerte (gelten auch dann, wenn HEAD einmal die neue Fassung ist).
    assert sorted(g["kennung"] for g in neu["gruppen"]) == soll_kennungen
    assert sorted(g["groesse"] for g in neu["gruppen"]) == soll_groessen
    assert not any("aliase" in g for g in neu["gruppen"])
    # Vergleich mit der HEAD-Fassung, Wert fuer Wert.
    alt = _v1_lauf(_head_modul(tmp_path), szene, e, kennungen, gleich, verschieden, namen)
    assert _v1_kurz(neu) == _v1_kurz(alt)


# --- 9. Sicherung: aliasmengen.json nur im v2-Weg (Codex Runde 4) -----------------

def test_v1_sicherung_laesst_aliasmengen_aus_v2_sichert_sie_mit(tmp_path):
    """v1 sichert wie vor Schritt 3 genau drei Dateien; nur der v2-Schreibweg nimmt
    eine vorhandene ``aliasmengen.json`` mit (sonst waere v1 nicht verhaltensgleich)."""
    for name in (pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN, pg.DATEI_ALIASE):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    v1 = pg._stempel_sichern(str(tmp_path), stempel="eins")
    assert sorted(os.path.basename(p).split(".vorher_")[0] for p in v1) == sorted(
        [pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN])
    v2 = pg._stempel_sichern(str(tmp_path), stempel="zwei", mit_aliasen=True)
    assert pg.DATEI_ALIASE in [os.path.basename(p).split(".vorher_")[0] for p in v2]
    assert len(v2) == 4


# --- 10. Bewertungsbericht: Hinweiszeile nur fuer v2 (Codex Runde 5) -------------

def test_bewertungsbericht_v1_ohne_aliaszeile_v2_mit(tmp_path):
    """Der v1-Bericht mit ``--bewerten`` bleibt wie vor Schritt 3 (keine
    Aliasmengen-Zeile); ein v2-Lauf nennt kennungsgenau/aliasaequivalent."""
    nachher_v1 = {"gesichter": [{"bild_id": "b1", "index": 0, "kennung": "Person_001",
                                 "bbox": None, "anteil": 0.1, "score": 0.9,
                                 "aufnahme": None}]}
    nachher_v2 = dict(nachher_v1, aliasmengen={})
    for lauf, erwartet in ((nachher_v1, False), (nachher_v2, True)):
        text = pg.bewertung_text(lauf, str(tmp_path), {}, {},
                                 str(tmp_path / "b.json"), str(tmp_path / "v.json"))
        assert ("Aliasmengen:" in text) is erwartet
