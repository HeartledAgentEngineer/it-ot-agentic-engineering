"""Tests: Phasen und Vorbilder (tools/foto_sortierung/personen_phasen.py, G2, 15.10.2026).

Alles offline mit ERFUNDENEN Vektoren (numpy, fester Seed): Personen sind
Richtungen im 128-dim Raum, Gesichter liegen mit kleinem Rauschen darum. Keine
echten Gesichter, keine Namen, kein Netz.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_phasen.py -q
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tracemalloc

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


ph = _laden("personen_phasen")
D = 128


def _basis(rng, anzahl):
    """``anzahl`` paarweise senkrechte Einheitsrichtungen."""
    q, _ = np.linalg.qr(rng.normal(size=(D, anzahl)))
    return [q[:, i] for i in range(anzahl)]


def _gesichter(rng, mitte, anzahl, rausch=0.3):
    """Gesichter um ``mitte`` (Cosinus zur Mitte ~0,96)."""
    out = []
    for _ in range(anzahl):
        r = rng.normal(size=D)
        r /= np.linalg.norm(r)
        v = mitte + rausch * r
        out.append(v / np.linalg.norm(v))
    return np.array(out)


def _kind(rng, jahre=10, je_jahr=25, schritt=0.12):
    """Ein Vektor, der Jahr fuer Jahr wandert: Winkel ``schritt`` je Jahr."""
    a, b = _basis(rng, 2)
    vektoren, jahreliste = [], []
    for t in range(jahre):
        mitte = np.cos(schritt * t) * a + np.sin(schritt * t) * b
        vektoren.append(_gesichter(rng, mitte, je_jahr))
        jahreliste += [2010 + t] * je_jahr
    return np.vstack(vektoren), jahreliste, (a, b)


# ── Konstanten ─────────────────────────────────────────────────────────────────

def test_konstanten_sind_gesetzt_und_sauber_kommt_aus_dem_messwerkzeug():
    assert ph.PHASE_BRUCH == 0.10 and ph.PHASE_MIN == 10 and ph.PHASE_TOLERANZ == 2
    assert ph.PHASE_MAX == 8 and ph.ANDOCK_SCHWELLE == 0.65 and ph.ANDOCK_ABSTAND == 0.05
    assert ph.SAUBER_SCORE == ph._messer.MIN_SCORE
    assert ph.SAUBER_BREITE == ph._messer.MIN_BREITE
    # Die Grenzen werden nicht doppelt geschrieben: im Modul steht keine 0.90/64 als Zahl.
    quelle = open(os.path.join(WERKZEUGE, "personen_phasen.py"), encoding="utf-8").read()
    code = quelle.split('"""', 2)[2]
    assert "SAUBER_SCORE = _messer.MIN_SCORE" in code
    assert "SAUBER_BREITE = _messer.MIN_BREITE" in code


def test_jahr_aus():
    assert ph.jahr_aus("2019-06-18T11:21:00") == 2019
    assert ph.jahr_aus("2019") == 2019
    assert ph.jahr_aus(None) is None
    assert ph.jahr_aus("") is None
    assert ph.jahr_aus("abcd-01-01") is None
    assert ph.jahr_aus("0000-01-01") is None


# ── phasen_bilden ──────────────────────────────────────────────────────────────

def test_wanderndes_kind_bildet_mehrere_phasen():
    rng = np.random.default_rng(1)
    v, jahre, _ = _kind(rng)
    phasen = ph.phasen_bilden(v, jahre)
    assert 2 <= len(phasen) <= ph.PHASE_MAX
    # lueckenlos, ueberlappungsfrei, aufsteigend; Summe aller Gesichter stimmt
    assert phasen[0][0] == 2010 and phasen[-1][1] == 2019
    for (_v1, bis1, _m1, _a1), (von2, _b2, _m2, _a2) in zip(phasen, phasen[1:]):
        assert von2 == bis1 + 1
    assert sum(p[3] for p in phasen) == len(jahre)
    assert all(p[3] >= ph.PHASE_MIN for p in phasen)
    # Mittelpunkte haben Laenge 1
    for _v, _b, mitte, _a in phasen:
        assert abs(float(np.linalg.norm(mitte)) - 1.0) < 1e-5
    # Die erste und die letzte Phase sind weit auseinander - ein einziger Mittelpunkt
    # waere ein schlechter Vergleich fuer beide Enden.
    erste, letzte = phasen[0][2], phasen[-1][2]
    assert 1.0 - float(np.dot(erste, letzte)) > ph.PHASE_BRUCH


def test_ruhiges_gesicht_ohne_wanderung_bleibt_eine_phase():
    rng = np.random.default_rng(2)
    mitte = _basis(rng, 1)[0]
    v = _gesichter(rng, mitte, 60)
    jahre = [2015 + (i % 6) for i in range(60)]
    phasen = ph.phasen_bilden(v, jahre)
    assert len(phasen) == 1
    assert phasen[0][:2] == (2015, 2020) and phasen[0][3] == 60


def test_gesichter_ohne_datum_zaehlen_zur_gesamtphase():
    rng = np.random.default_rng(3)
    mitte = _basis(rng, 1)[0]
    v = _gesichter(rng, mitte, 30)
    # gar kein Datum: genau eine Gesamtphase
    nur = ph.phasen_bilden(v, [None] * 30)
    assert len(nur) == 1 and nur[0][0] is None and nur[0][1] is None and nur[0][3] == 30
    # gemischt: datierte Phase(n) plus Gesamtphase ueber ALLE Gesichter
    jahre = [2018] * 20 + [None] * 10
    gemischt = ph.phasen_bilden(v, jahre)
    assert gemischt[-1][0] is None and gemischt[-1][3] == 30
    assert gemischt[0][:2] == (2018, 2018) and gemischt[0][3] == 20
    # nur datierte: keine Gesamtphase
    assert all(p[0] is not None for p in ph.phasen_bilden(v, [2018] * 30))


def test_zu_kleine_phase_wird_dem_aehnlicheren_nachbarn_zugeschlagen():
    rng = np.random.default_rng(4)
    a, b = _basis(rng, 2)
    zwischen = (a + 0.35 * b) / np.linalg.norm(a + 0.35 * b)        # naeher an a
    v = np.vstack([_gesichter(rng, a, 25), _gesichter(rng, zwischen, 3),
                   _gesichter(rng, b, 25)])
    jahre = [2010] * 25 + [2012] * 3 + [2014] * 25
    phasen = ph.phasen_bilden(v, jahre)
    assert [(p[0], p[1], p[3]) for p in phasen] == [(2010, 2012, 28), (2014, 2014, 25)]


def test_kleine_gruppe_behaelt_eine_kleine_phase():
    rng = np.random.default_rng(5)
    a, b = _basis(rng, 2)
    v = np.vstack([_gesichter(rng, a, 3), _gesichter(rng, b, 3)])
    phasen = ph.phasen_bilden(v, [2010] * 3 + [2020] * 3)
    assert len(phasen) == 1 and phasen[0][3] == 6               # nichts zum Aufteilen


def test_phasendeckel_wird_eingehalten():
    rng = np.random.default_rng(6)
    anzahl = 30
    richtungen = _basis(rng, anzahl)                            # alle senkrecht: jedes Jahr bricht
    v = np.vstack([_gesichter(rng, r, 12) for r in richtungen])
    jahre = [1990 + t for t in range(anzahl) for _ in range(12)]
    ungedeckelt = ph.phasen_bilden(v, jahre, maximum=100)
    assert len(ungedeckelt) == anzahl
    gedeckelt = ph.phasen_bilden(v, jahre)
    assert len(gedeckelt) == ph.PHASE_MAX
    assert sum(p[3] for p in gedeckelt) == 12 * anzahl


def test_leere_eingabe_und_falsche_laenge():
    assert ph.phasen_bilden(np.zeros((0, D)), []) == []
    with pytest.raises(ValueError):
        ph.phasen_bilden(np.ones((3, D)), [2010, 2011])


# ── vergleichen ──────────────────────────────────────────────────────────────

def _zwei_phasen():
    rng = np.random.default_rng(7)
    a, b = _basis(rng, 2)
    phasen = [(2010, 2012, a.astype(np.float32), 30), (2018, 2020, b.astype(np.float32), 30)]
    return phasen, a, b


def test_vergleichen_nimmt_die_phase_zum_aufnahmejahr():
    phasen, a, b = _zwei_phasen()
    assert ph.vergleichen(a, 2011, phasen) == pytest.approx(1.0, abs=1e-5)
    assert ph.vergleichen(b, 2019, phasen) == pytest.approx(1.0, abs=1e-5)
    # a-aehnliches Gesicht aus der b-Zeit: die a-Phase liegt 6 Jahre daneben -> nicht passend
    assert ph.vergleichen(a, 2019, phasen) == pytest.approx(0.0, abs=1e-5)


def test_vergleichen_toleranz_in_jahren():
    phasen, a, _b = _zwei_phasen()
    assert ph.vergleichen(a, 2012 + ph.PHASE_TOLERANZ, phasen) == pytest.approx(1.0, abs=1e-5)
    # drei Jahre nach der a-Phase und fuenf vor der b-Phase: gar keine Phase passt
    assert ph.vergleichen(a, 2015, phasen, toleranz=2) is None
    assert ph.vergleichen(a, 2015, phasen, toleranz=3) == pytest.approx(1.0, abs=1e-5)


def test_vergleichen_ohne_datum_nimmt_die_beste_aller_phasen():
    phasen, a, b = _zwei_phasen()
    assert ph.vergleichen(a, None, phasen) == pytest.approx(1.0, abs=1e-5)
    assert ph.vergleichen(b, None, phasen) == pytest.approx(1.0, abs=1e-5)


def test_gesamtphase_zaehlt_fuer_datierte_nur_ohne_datierte_phasen():
    rng = np.random.default_rng(8)
    a, b = _basis(rng, 2)
    nur_gesamt = [(None, None, a.astype(np.float32), 20)]
    assert ph.vergleichen(a, 2015, nur_gesamt) == pytest.approx(1.0, abs=1e-5)
    gemischt = [(2010, 2011, b.astype(np.float32), 20), (None, None, a.astype(np.float32), 30)]
    # a liegt nur in der Gesamtphase: ein DATIERTES a-Gesicht sieht sie nicht ...
    assert ph.vergleichen(a, 2010, gemischt) == pytest.approx(0.0, abs=1e-5)
    # ... ein UNDATIERTES schon
    assert ph.vergleichen(a, None, gemischt) == pytest.approx(1.0, abs=1e-5)


# ── Satz: blockweise, gleiche Antwort wie die Einzelrechnung ─────────────────

def _zufalls_gruppen(rng, k=7):
    gruppen = []
    for _ in range(k):
        n = int(rng.integers(5, 60))
        v = rng.normal(size=(n, D))
        jahre = [None if rng.random() < 0.2 else int(2008 + rng.integers(0, 14))
                 for _ in range(n)]
        gruppen.append(ph.phasen_bilden(v, jahre, minimum=4))
    return gruppen


def test_blockweiser_vergleich_gleicht_der_einzelrechnung(monkeypatch):
    monkeypatch.setattr(ph, "BLOCK", 7)                       # viele kleine Bloecke
    rng = np.random.default_rng(9)
    gruppen = _zufalls_gruppen(rng)
    satz = ph.phasen_satz(gruppen)
    n = 50
    gesichter = rng.normal(size=(n, D))
    gesichter /= np.linalg.norm(gesichter, axis=1, keepdims=True)
    jahre = [None if rng.random() < 0.25 else int(2006 + rng.integers(0, 18)) for _ in range(n)]
    matrix = ph.gruppen_vergleich(gesichter.astype(np.float32), ph.jahre_als_zahlen(jahre), satz)
    assert matrix.shape == (n, len(gruppen))
    for i in range(n):
        for g, phasen in enumerate(gruppen):
            soll = ph.vergleichen(gesichter[i], jahre[i], phasen)
            if soll is None:
                assert matrix[i, g] == ph._NICHT_VERGLEICHBAR
            else:
                assert matrix[i, g] == pytest.approx(soll, abs=1e-4)
    # beste_gruppen liefert dieselbe Rangfolge
    idx, werte = ph.beste_gruppen(gesichter.astype(np.float32), jahre, satz, top=3)
    for i in range(n):
        assert werte[i, 0] == pytest.approx(matrix[i].max(), abs=1e-6)
        assert idx[i, 0] == int(np.argmax(matrix[i])) or matrix[i, idx[i, 0]] == matrix[i].max()


def test_satz_markiert_gesamtphase_nur_bei_gruppen_mit_datierten_phasen():
    rng = np.random.default_rng(10)
    a, b, c = _basis(rng, 3)
    g0 = [(2010, 2011, a.astype(np.float32), 20), (None, None, a.astype(np.float32), 25)]
    g1 = [(None, None, b.astype(np.float32), 15)]
    satz = ph.phasen_satz([g0, g1])
    assert satz["k"] == 2 and list(satz["starts"]) == [0, 2]
    assert list(satz["nur_undatiert"]) == [False, True, False]
    assert list(satz["gruppe"]) == [0, 0, 1]
    with pytest.raises(ValueError):
        ph.phasen_satz([g0, []])


def test_speicher_bleibt_blockweise_begrenzt(monkeypatch):
    """Kein n x n: 6000 Gesichter gegen 60 Gruppen und 5000 Phasen gegen sich selbst."""
    monkeypatch.setattr(ph, "BLOCK", 128)
    rng = np.random.default_rng(11)
    n, k = 6000, 60
    v = rng.normal(size=(n, D)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    gruppen = [[(2010, 2012, v[g], 30)] for g in range(k)]
    satz = ph.phasen_satz(gruppen)
    jahre = [2011] * n
    voll_n_mal_n = n * n * 4                                   # 144 MB
    tracemalloc.start()
    try:
        ph.beste_gruppen(v, jahre, satz, top=5)
        _, spitze_gesichter = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        gross = ph.phasen_satz([[(2010 + (g % 10), 2012 + (g % 10), v[g], 12)]
                                for g in range(5000)])
        tracemalloc.reset_peak()
        ph.verschmelz_paare(gross, 0.99)
        _, spitze_phasen = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert spitze_gesichter < voll_n_mal_n / 4, spitze_gesichter
    assert spitze_phasen < 5000 * 5000 * 4 / 4, spitze_phasen


# ── Verschmelzen Phase gegen Phase ─────────────────────────────────────────────

def _gruppe(mitte, von, bis, anzahl=30):
    return [(von, bis, np.asarray(mitte, dtype=np.float32), anzahl)]


def _aehnliche_paar(rng, cos=0.8):
    a = _basis(rng, 1)[0]
    r = rng.normal(size=D)
    r -= r.dot(a) * a
    r /= np.linalg.norm(r)
    return a, cos * a + np.sqrt(1 - cos ** 2) * r


def test_geschwister_mit_verschiedenen_jahrgaengen_werden_nicht_vereint():
    rng = np.random.default_rng(12)
    a, b = _aehnliche_paar(rng)                 # sehr aehnlich (Cosinus 0,8)
    getrennt = ph.phasen_satz([_gruppe(a, 2010, 2013), _gruppe(b, 2020, 2023)])
    assert ph.verschmelz_paare(getrennt, 0.60) == []
    gleiche_jahre = ph.phasen_satz([_gruppe(a, 2010, 2013), _gruppe(b, 2011, 2014)])
    paare = ph.verschmelz_paare(gleiche_jahre, 0.60)
    assert len(paare) == 1 and paare[0][1:] == (0, 1) and paare[0][0] == pytest.approx(0.8, abs=1e-4)


def test_kindheit_und_erwachsene_finden_ueber_die_jahre_dazwischen_zusammen():
    rng = np.random.default_rng(13)
    a, b = _aehnliche_paar(rng, 0.85)
    c = (a + b) / np.linalg.norm(a + b)
    satz = ph.phasen_satz([_gruppe(a, 2010, 2012), _gruppe(c, 2013, 2016),
                           _gruppe(b, 2017, 2019)])
    paare = {(a_, b_) for _w, a_, b_ in ph.verschmelz_paare(satz, 0.60)}
    assert (0, 1) in paare and (1, 2) in paare          # Nachbarn finden sich
    assert (0, 2) not in paare                           # 2012 -> 2017: fuenf Jahre, ueber Toleranz


def test_toleranz_grenze_beim_verschmelzen():
    rng = np.random.default_rng(14)
    a, b = _aehnliche_paar(rng)
    gleich = ph.phasen_satz([_gruppe(a, 2010, 2012), _gruppe(b, 2014, 2016)])      # Luecke 2
    assert len(ph.verschmelz_paare(gleich, 0.60)) == 1
    zu_weit = ph.phasen_satz([_gruppe(a, 2010, 2012), _gruppe(b, 2015, 2016)])     # Luecke 3
    assert ph.verschmelz_paare(zu_weit, 0.60) == []


def test_gesamtphase_verschmilzt_mit_jeder_phase_aber_nie_die_einer_gemischten_gruppe():
    rng = np.random.default_rng(15)
    a, b = _aehnliche_paar(rng)
    ohne_datum = ph.phasen_satz([_gruppe(a, None, None), _gruppe(b, 2015, 2018)])
    assert len(ph.verschmelz_paare(ohne_datum, 0.60)) == 1
    # Gruppe 0 hat datierte Phase (weit weg) UND eine aehnliche Gesamtphase:
    gemischt = [(2000, 2001, _basis(rng, 1)[0].astype(np.float32), 30),
                (None, None, a.astype(np.float32), 40)]
    satz = ph.phasen_satz([gemischt, _gruppe(b, 2015, 2018)])
    assert ph.verschmelz_paare(satz, 0.60) == []


def test_paare_sind_nach_aehnlichkeit_geordnet():
    rng = np.random.default_rng(16)
    a, b = _aehnliche_paar(rng, 0.9)
    _a2, c = _aehnliche_paar(rng, 0.7)
    satz = ph.phasen_satz([_gruppe(a, 2010, 2012), _gruppe(b, 2010, 2012),
                           _gruppe(a * 0.7 + c * 0.3, 2010, 2012)])
    werte = [w for w, _a, _b in ph.verschmelz_paare(satz, 0.0)]
    assert werte == sorted(werte, reverse=True)


# ── Andocken ──────────────────────────────────────────────────────────────────────

def _andock_szene(rng):
    """Drei Gruppen: A (Name X), B (Name X, zweite Kennung), C (Name Y)."""
    a, b, c = _basis(rng, 3)
    gruppen = [_gruppe(a, 2010, 2020), _gruppe(b, 2010, 2020), _gruppe(c, 2010, 2020)]
    return a, b, c, ph.phasen_satz(gruppen)


def test_andocken_an_klar_beste_gruppe_und_sonst_nicht():
    rng = np.random.default_rng(17)
    a, b, c, satz = _andock_szene(rng)
    nah_a = _gesichter(rng, a, 1, rausch=0.2)[0]
    fern = _basis(rng, 8)[7]                                   # gehoert zu niemandem
    v = np.array([nah_a, fern], dtype=np.float32)
    erg = ph.andocken(v, [2015, 2015], ["b1", "b2"], satz, [set(), set(), set()],
                      ["X", "X2", "Y"])
    assert list(erg["gruppe"]) == [0, -1]
    assert erg["zaehler"]["angedockt"] == 1 and erg["zaehler"]["unter_schwelle"] == 1


def test_andocken_verlangt_abstand_zum_zweitbesten_namen():
    rng = np.random.default_rng(18)
    a, b, c, satz = _andock_szene(rng)
    mitte = (a + 0.95 * c) / np.linalg.norm(a + 0.95 * c)            # fast gleich nah an A und C
    v = np.array([mitte], dtype=np.float32)
    knapp = ph.andocken(v, [2015], ["b1"], satz, [set()] * 3, ["X", "X2", "Y"],
                        schwelle=0.60, abstand=0.05)
    assert knapp["gruppe"][0] == -1 and knapp["zaehler"]["zu_knapp"] == 1
    # Ohne Abstandsforderung dockt es an (die Aehnlichkeit selbst reicht)
    locker = ph.andocken(v, [2015], ["b1"], satz, [set()] * 3, ["X", "X2", "Y"],
                         schwelle=0.60, abstand=0.0)
    assert locker["gruppe"][0] in (0, 2)


def test_gleichnamige_kennungen_konkurrieren_nicht_gegeneinander():
    rng = np.random.default_rng(19)
    a, b, c, satz = _andock_szene(rng)
    mitte = (a + 0.95 * b) / np.linalg.norm(a + 0.95 * b)            # fast gleich nah an A und B
    v = np.array([mitte], dtype=np.float32)
    # A und B tragen denselben Namen: der Abstand wird zu C gemessen, nicht zu B
    gleicher_name = ph.andocken(v, [2015], ["b1"], satz, [set()] * 3, ["X", "X", "Y"],
                                schwelle=0.60, abstand=0.05)
    assert gleicher_name["gruppe"][0] == 0                            # beste der beiden Kennungen
    # Mit verschiedenen Namen waere es ein knappes Rennen -> kein Andocken
    verschieden = ph.andocken(v, [2015], ["b1"], satz, [set()] * 3, ["X", "X2", "Y"],
                              schwelle=0.60, abstand=0.05)
    assert verschieden["gruppe"][0] == -1


def test_andocken_nie_zwei_gesichter_desselben_bildes_in_eine_gruppe():
    rng = np.random.default_rng(20)
    a, _b, _c, satz = _andock_szene(rng)
    zwei = _gesichter(rng, a, 2, rausch=0.2).astype(np.float32)
    erg = ph.andocken(zwei, [2015, 2015], ["bild", "bild"], satz, [set()] * 3,
                      ["X", "X2", "Y"])
    assert sorted(erg["gruppe"].tolist()) == [-1, 0]
    assert erg["zaehler"]["gleiches_bild"] == 1
    belegt = ph.andocken(zwei[:1], [2015], ["bild"], satz, [{"bild"}, set(), set()],
                         ["X", "X2", "Y"])
    assert belegt["gruppe"][0] == -1                                  # Bild schon in der Gruppe


def test_andocken_beachtet_verbotene_gruppen_und_jahre():
    rng = np.random.default_rng(21)
    a, b, c, satz = _andock_szene(rng)
    v = _gesichter(rng, a, 1, rausch=0.2).astype(np.float32)
    verboten = ph.andocken(v, [2015], ["b"], satz, [set()] * 3, ["X", "X2", "Y"],
                           verboten=[{0}])
    assert verboten["gruppe"][0] == -1
    # Aufnahmejahr weit ausserhalb aller Phasen: keine passende Phase
    zu_frueh = ph.andocken(v, [1990], ["b"], satz, [set()] * 3, ["X", "X2", "Y"])
    assert zu_frueh["gruppe"][0] == -1 and zu_frueh["zaehler"]["keine_passende_phase"] == 1
    # ohne Datum zaehlt der beste aller Phasen
    ohne = ph.andocken(v, [None], ["b"], satz, [set()] * 3, ["X", "X2", "Y"])
    assert ohne["gruppe"][0] == 0


def test_andocken_ohne_gruppen_oder_gesichter():
    leer = ph.phasen_satz([])
    erg = ph.andocken(np.zeros((2, D), dtype=np.float32), [2015, 2015], ["a", "b"], leer, [], [])
    assert list(erg["gruppe"]) == [-1, -1]
    erg2 = ph.andocken(np.zeros((0, D), dtype=np.float32), [], [], leer, [], [])
    assert len(erg2["gruppe"]) == 0
