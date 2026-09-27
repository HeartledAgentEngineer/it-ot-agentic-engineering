"""Pruefungen fuer ``personen_schwelle.py`` (Nachtlauf-Schritt N9e).

Alles OHNE Netz und OHNE echte Daten: keine pCloud, kein Download, kein Bild
aus dem Bestand, keine echten Ordner- oder Personennamen. Die Vektoren sind
**synthetisch** und deterministisch aus einem Seed erzeugt
(``numpy.random.default_rng``); Dateien gehen nach ``tmp_path``. Die
Beschriftungen der Messung sind erfundene Anlass-Kennungen (``Anlass-A`` …),
die Bild-Kennungen erfundene Ziffern.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_personen_schwelle.py -q
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "personen_schwelle.py"
N9A = REPO / "tools" / "foto_sortierung" / "personen_cluster.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


sw = _laden(WERKZEUG, "personen_schwelle")
pc = _laden(N9A, "personen_cluster")

# Ein 12-MP-Handyfoto — die Bezugsflaeche der Schwellen.
BREITE = 4032
HOEHE = 3024

# Die Pflichtfunktionen (Namen sind Vorgabe des Auftrags).
VORGABE_FUNKTIONEN = (
    "burst_familie", "cluster_beschriften", "falsche_cluster",
    "distanzpaare", "schwelle_messen", "verlauf_messen", "empfehlung_bauen",
    "bericht_bauen", "bericht_text", "messlauf", "main",
    # Bodenwahrheit (Bild-Paare erkennbarer Gesichter)
    "bild_paare", "verschmelzungsquote", "kettenmass", "gruppendurchmesser",
)


# ── Synthetische Vektoren und Bilder (deterministisch, offline) ────────────

def _basis(seed: int, laenge: int = pc.MERKMAL_LAENGE):
    """Ein Basis-Merkmal aus einem Seed (128 Werte)."""
    return np.random.default_rng(seed).normal(size=laenge)


def _nahe(basis, seed: int, streuung: float = 0.02) -> list[float]:
    """Ein Vektor DICHT an ``basis`` — dieselbe Person, ein anderes Foto."""
    rauschen = np.random.default_rng(seed).normal(size=len(basis))
    return [float(wert) for wert in basis + streuung * rauschen]


def _fern(seed: int) -> list[float]:
    """Ein Vektor ohne Bezug (im 128-dim Raum fast orthogonal)."""
    return [float(wert) for wert in np.random.default_rng(seed).normal(
        size=pc.MERKMAL_LAENGE)]


def _gross(embedding, score=0.9) -> dict:
    """Ein erkennbares Gesicht (300x300 Pixel im 12-MP-Foto)."""
    return {"bbox": [100.0, 100.0, 300.0, 300.0], "score": score,
            "embedding": list(embedding)}


def _bild(bild_id, embedding=(), breite=BREITE, hoehe=HOEHE) -> dict:
    return {"bild_id": bild_id, "breite": breite, "hoehe": hoehe,
            "gesichter": [_gross(v) for v in embedding]}


def _trennbares_paar(je_seite=4) -> tuple:
    """``(bilder, zuordnung)``: zwei klar getrennte Anlaesse — sauber trennbar.

    ``Anlass-A`` liegt um ``_basis(1)``, ``Anlass-B`` um ``_basis(2)`` — im
    128-dim Raum praktisch orthogonal, der Cross-Abstand also nahe 1,0.
    """
    a, b = _basis(1), _basis(2)
    bilder, zuordnung = [], {}
    for nummer in range(je_seite):
        kennung = f"10000{nummer}"
        bilder.append(_bild(kennung, [_nahe(a, 10 + nummer)]))
        zuordnung[kennung] = "Anlass-A"
    for nummer in range(je_seite):
        kennung = f"20000{nummer}"
        bilder.append(_bild(kennung, [_nahe(b, 20 + nummer)]))
        zuordnung[kennung] = "Anlass-B"
    return bilder, zuordnung


def _ueberlappendes_paar(je_seite=4) -> tuple:
    """``(bilder, zuordnung)``: zwei Anlaesse AM SELBEN Ort — nicht trennbar.

    Beide Anlaesse streuen um **dieselbe** Basis, nur mit verschiedenen Seeds.
    Innerhalb- und Zwischen-Abstaende liegen damit in derselben Groessenordnung
    — genau die Ueberlappung, die keine Schwelle trennen kann.
    """
    basis = _basis(5)
    bilder, zuordnung = [], {}
    for nummer in range(je_seite):
        kennung = f"30000{nummer}"
        bilder.append(_bild(kennung, [_nahe(basis, 30 + nummer)]))
        zuordnung[kennung] = "Anlass-A"
    for nummer in range(je_seite):
        kennung = f"40000{nummer}"
        bilder.append(_bild(kennung, [_nahe(basis, 40 + nummer)]))
        zuordnung[kennung] = "Anlass-B"
    return bilder, zuordnung


def _plan_schreiben(pfad: Path, zuege) -> str:
    pfad.write_text(json.dumps({"zuege": zuege}), encoding="utf-8")
    return str(pfad)


# ── 1. burst_familie ──────────────────────────────────────────────────────

def test_burst_familie_schneidet_den_burst_zusatz_ab():
    assert sw.burst_familie("IMG_20250609_015239666_BURST008.jpg") == \
        "IMG_20250609_015239666"


def test_burst_familie_schneidet_auch_die_cover_variante_ab():
    assert sw.burst_familie("IMG_20250606_185746027_BURST000_COVER.jpg") == \
        "IMG_20250606_185746027"


def test_burst_familie_kennt_das_kleine_burst_muster():
    assert sw.burst_familie("20190824_170646_Burst01.jpg") == "20190824_170646"


def test_burst_familie_ohne_zusatz_ist_der_name_selbst():
    assert sw.burst_familie("IMG-20220821-WA0050.jpg") == "IMG-20220821-WA0050.jpg"


def test_burst_familie_nimmt_nur_den_basename():
    assert sw.burst_familie("/pfad/zu/IMG_1_BURST002.jpg") == "IMG_1"


def test_burst_familie_ohne_text_ist_none():
    assert sw.burst_familie(None) is None


def test_burst_familie_leerer_text_ist_none():
    assert sw.burst_familie("   ") is None


# ── 2. plan_beschriftungen_lesen ──────────────────────────────────────────

def test_plan_beschriftungen_liest_den_anlass(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": 11, "thema_quelle": "Anlass-A"}])
    assert sw.plan_beschriftungen_lesen(pfad) == {"11": "Anlass-A"}


def test_plan_beschriftungen_liest_die_burst_familie(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": 11,
                             "von_name": "IMG_1_BURST003.jpg"}])
    assert sw.plan_beschriftungen_lesen(pfad, "von_name") == {"11": "IMG_1"}


def test_plan_beschriftungen_ueberspringt_ohne_fileid(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json",
                           [{"thema_quelle": "Anlass-A"},
                            {"fileid": 12, "thema_quelle": "Anlass-B"}])
    assert sw.plan_beschriftungen_lesen(pfad) == {"12": "Anlass-B"}


def test_plan_beschriftungen_ueberspringt_ohne_beschriftung(tmp_path):
    pfad = _plan_schreiben(tmp_path / "plan.json", [{"fileid": 11}])
    assert sw.plan_beschriftungen_lesen(pfad) == {}


def test_plan_beschriftungen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(sw.SchwelleFehler) as fehler:
        sw.plan_beschriftungen_lesen(str(tmp_path / "fehlt.json"))
    assert "nicht gefunden" in str(fehler.value)


def test_plan_beschriftungen_ohne_zuege_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "plan.json"
    pfad.write_text(json.dumps({"trocken": True}), encoding="utf-8")
    with pytest.raises(sw.SchwelleFehler):
        sw.plan_beschriftungen_lesen(str(pfad))


def test_plan_beschriftungen_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "plan.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(sw.SchwelleFehler):
        sw.plan_beschriftungen_lesen(str(pfad))


# ── 3. beschriftung_je_eintrag ────────────────────────────────────────────

def test_beschriftung_je_eintrag_ordnet_ueber_die_bild_id():
    eintraege = [{"bild_id": "1"}, {"bild_id": "2"}]
    assert sw.beschriftung_je_eintrag(eintraege, {"1": "A", "2": "B"}) == \
        ["A", "B"]


def test_beschriftung_je_eintrag_unbekannt_ist_none():
    assert sw.beschriftung_je_eintrag([{"bild_id": "9"}], {"1": "A"}) == [None]


def test_beschriftung_je_eintrag_ist_so_lang_wie_die_eintraege():
    eintraege = [{"bild_id": "1"}, {"bild_id": "2"}, {"bild_id": "3"}]
    assert len(sw.beschriftung_je_eintrag(eintraege, {"1": "A"})) == 3


# ── 4. cluster_beschriften / falsche_cluster ──────────────────────────────

def test_cluster_beschriften_zaehlt_ab_eins():
    beschrieben = sw.cluster_beschriften([[0, 1]], [{"bild_id": "1"},
                                                    {"bild_id": "2"}],
                                         ["A", "A"])
    assert beschrieben[0]["nummer"] == 1


def test_cluster_beschriften_groesse_und_beschriftungen():
    beschrieben = sw.cluster_beschriften([[0, 1, 2]], [{"bild_id": "1"},
                                                       {"bild_id": "2"},
                                                       {"bild_id": "3"}],
                                         ["A", "A", "A"])
    assert beschrieben[0]["groesse"] == 3
    assert beschrieben[0]["beschriftungen"] == {"A": 3}
    assert beschrieben[0]["rein"] is True


def test_cluster_beschriften_zwei_beschriftungen_sind_unrein():
    beschrieben = sw.cluster_beschriften([[0, 1]], [{"bild_id": "1"},
                                                    {"bild_id": "2"}],
                                         ["A", "B"])
    assert beschrieben[0]["rein"] is False
    assert beschrieben[0]["anzahl_beschriftungen"] == 2


def test_cluster_beschriften_ohne_beschriftung_zaehlt_nicht_als_widerspruch():
    beschrieben = sw.cluster_beschriften([[0, 1]], [{"bild_id": "1"},
                                                    {"bild_id": "2"}],
                                         ["A", None])
    assert beschrieben[0]["rein"] is True
    assert beschrieben[0]["ohne_beschriftung"] == 1


def test_falsche_cluster_beziffert_die_unreinen():
    beschrieben = sw.cluster_beschriften([[0, 1], [2, 3]],
                                         [{"bild_id": str(n)} for n in range(4)],
                                         ["A", "B", "C", "C"])
    falsche = sw.falsche_cluster(beschrieben)
    assert len(falsche) == 1
    assert falsche[0]["nummer"] == 1
    assert falsche[0]["anzahl_beschriftungen"] == 2


def test_falsche_cluster_sortiert_groessten_zuerst():
    beschrieben = [
        {"nummer": 1, "groesse": 2, "rein": False,
         "beschriftungen": {"A": 1, "B": 1}, "anzahl_beschriftungen": 2},
        {"nummer": 2, "groesse": 9, "rein": False,
         "beschriftungen": {"A": 5, "B": 4}, "anzahl_beschriftungen": 2},
        {"nummer": 3, "groesse": 4, "rein": True, "beschriftungen": {"C": 4},
         "anzahl_beschriftungen": 1}]
    falsche = sw.falsche_cluster(beschrieben)
    assert [eintrag["nummer"] for eintrag in falsche] == [2, 1]


def test_falsche_cluster_ohne_unreine_ist_leer():
    beschrieben = sw.cluster_beschriften([[0, 1]], [{"bild_id": "1"},
                                                    {"bild_id": "2"}],
                                         ["A", "A"])
    assert sw.falsche_cluster(beschrieben) == []


# ── 5. distanzpaare / Trennschaerfe ───────────────────────────────────────

def test_distanzpaare_trennt_gleich_und_fremd():
    bilder, zuordnung = _trennbares_paar()
    eintraege = sw.messlauf(bilder, zuordnung)["eintraege"]
    labels = sw.beschriftung_je_eintrag(eintraege, zuordnung)
    trenn = sw.distanzpaare(eintraege, labels)
    assert trenn["fremd"]["min"] > trenn["gleich"]["median"]


def test_distanzpaare_erkennt_ueberlappung():
    bilder, zuordnung = _ueberlappendes_paar()
    eintraege = sw.messlauf(bilder, zuordnung)["eintraege"]
    labels = sw.beschriftung_je_eintrag(eintraege, zuordnung)
    trenn = sw.distanzpaare(eintraege, labels)
    assert trenn["fremd"]["min"] <= trenn["gleich"]["median"]


def test_distanzpaare_hat_die_kennzahlen():
    bilder, zuordnung = _trennbares_paar()
    eintraege = sw.messlauf(bilder, zuordnung)["eintraege"]
    labels = sw.beschriftung_je_eintrag(eintraege, zuordnung)
    trenn = sw.distanzpaare(eintraege, labels)
    for name in ("gleich", "fremd"):
        for feld in ("min", "p05", "median", "p90", "max", "anzahl"):
            assert feld in trenn[name]


def test_distanzpaare_ohne_beschriftung_zaehlt_keine_paare():
    trenn = sw.distanzpaare([{"embedding": _fern(1)}, {"embedding": _fern(2)}],
                            [None, None])
    assert trenn["gleich"] is None and trenn["fremd"] is None


# ── 6. schwelle_messen / verlauf_messen ───────────────────────────────────

def test_schwelle_messen_trennt_sauber():
    bilder, zuordnung = _trennbares_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    messung = sw.schwelle_messen(lauf["eintraege"], lauf["beschriftungen"], 0.45)
    assert messung["gruppen"] == 2
    assert messung["falsche_cluster"] == 0


def test_schwelle_messen_legt_bei_weiter_schwelle_zusammen():
    bilder, zuordnung = _ueberlappendes_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    messung = sw.schwelle_messen(lauf["eintraege"], lauf["beschriftungen"], 0.45)
    assert messung["gruppen"] == 1
    assert messung["falsche_cluster"] == 1
    assert messung["groesste"] == len(lauf["eintraege"])


def test_schwelle_messen_zaehlt_gesichter_in_falschen():
    bilder, zuordnung = _ueberlappendes_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    messung = sw.schwelle_messen(lauf["eintraege"], lauf["beschriftungen"], 0.45)
    assert messung["gesichter_in_falschen"] == messung["gesichter"]
    assert messung["anteil_in_falschen"] == pytest.approx(1.0)


def test_schwelle_messen_unbrauchbare_schwelle_ist_klartextfehler():
    with pytest.raises(sw.SchwelleFehler):
        sw.schwelle_messen([{"embedding": _fern(1)}], ["A"], "streng")


def test_verlauf_messen_haelt_die_reihenfolge():
    bilder, zuordnung = _trennbares_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    verlauf = sw.verlauf_messen(lauf["eintraege"], lauf["beschriftungen"],
                                [0.5, 0.3, 0.1])
    assert [eintrag["schwelle"] for eintrag in verlauf] == [0.5, 0.3, 0.1]


def test_verlauf_messen_entdoppelt_schwellen():
    bilder, zuordnung = _trennbares_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    verlauf = sw.verlauf_messen(lauf["eintraege"], lauf["beschriftungen"],
                                [0.4, 0.4, 0.4])
    assert len(verlauf) == 1


def test_verlauf_messen_wirft_unbrauchbare_werte_weg():
    bilder, zuordnung = _trennbares_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    verlauf = sw.verlauf_messen(lauf["eintraege"], lauf["beschriftungen"],
                                [0.4, "x", None])
    assert [eintrag["schwelle"] for eintrag in verlauf] == [0.4]


# ── 7. empfehlung_bauen ───────────────────────────────────────────────────

def test_empfehlung_erkennt_die_fehlende_trennbarkeit():
    bilder, zuordnung = _ueberlappendes_paar()
    lauf = sw.messlauf(bilder, zuordnung)
    empfehlung = lauf["empfehlung"]
    assert empfehlung["trennbar"] is False
    assert "NICHT" in empfehlung["kernaussage"]


def test_empfehlung_nennt_bei_ueberlappung_die_verkettung():
    bilder, zuordnung = _ueberlappendes_paar()
    empfehlung = sw.messlauf(bilder, zuordnung)["empfehlung"]
    assert "Verkettung" in empfehlung["vorschlag"]


def test_empfehlung_erkennt_die_trennbarkeit():
    bilder, zuordnung = _trennbares_paar()
    empfehlung = sw.messlauf(bilder, zuordnung)["empfehlung"]
    assert empfehlung["trennbar"] is True


def test_empfehlung_nennt_den_heutigen_wert():
    bilder, zuordnung = _trennbares_paar()
    empfehlung = sw.messlauf(bilder, zuordnung)["empfehlung"]
    assert empfehlung["heute_schwelle"] == pc.CLUSTER_SCHWELLE


def test_empfehlung_ohne_paare_ist_ehrlich():
    empfehlung = sw.empfehlung_bauen([], {"gleich": None, "fremd": None}, 0.45)
    assert empfehlung["trennbar"] is None


# ── 8. bericht_bauen / bericht_text ───────────────────────────────────────

def test_bericht_bauen_hat_alle_felder():
    bilder, zuordnung = _trennbares_paar()
    bericht = sw.messlauf(bilder, zuordnung)["bericht"]
    assert {"beschriftung", "zeilen_gesamt", "ungueltige_zeilen", "eintraege",
            "gesichter", "beschriftungen", "verlauf", "trennschaerfe",
            "empfehlung", "stand"} <= set(bericht)


def test_bericht_bauen_zaehlt_die_beschriftungen():
    bilder, zuordnung = _trennbares_paar()
    bericht = sw.messlauf(bilder, zuordnung)["bericht"]
    assert bericht["beschriftungen"] == 2


def test_bericht_text_nennt_die_schwellen():
    bilder, zuordnung = _trennbares_paar()
    bericht = sw.messlauf(bilder, zuordnung, schwellen=[0.45, 0.1])["bericht"]
    text = sw.bericht_text(bericht)
    assert "0.45000" in text and "0.10000" in text


def test_bericht_text_nennt_die_empfehlung():
    bilder, zuordnung = _ueberlappendes_paar()
    text = sw.bericht_text(sw.messlauf(bilder, zuordnung)["bericht"])
    assert "Empfehlung:" in text
    assert "Vorschlag:" in text


def test_bericht_text_ohne_daten_kippt_nicht():
    assert isinstance(sw.bericht_text({}), str)


# ── 9. messlauf ───────────────────────────────────────────────────────────

def test_messlauf_sammelt_nur_clustern_bilder():
    basis = _basis(7)
    bilder = [_bild("1", [_nahe(basis, 1)]),
              _bild("2", [list(_fern(3))], breite=0, hoehe=0)]
    lauf = sw.messlauf(bilder, {"1": "A"})
    assert len(lauf["eintraege"]) == 1
    assert lauf["eintraege"][0]["bild_id"] == "1"


def test_messlauf_hat_den_heutigen_wert_im_verlauf():
    bilder, zuordnung = _trennbares_paar()
    lauf = sw.messlauf(bilder, zuordnung, schwellen=[0.1])
    assert pc.CLUSTER_SCHWELLE in [eintrag["schwelle"]
                                   for eintrag in lauf["verlauf"]]


def test_messlauf_ist_deterministisch():
    bilder, zuordnung = _trennbares_paar()
    erster = sw.messlauf(bilder, zuordnung)["verlauf"]
    zweiter = sw.messlauf(bilder, zuordnung)["verlauf"]
    assert [e["falsche_cluster"] for e in erster] == \
        [e["falsche_cluster"] for e in zweiter]


# ── 9b. Bodenwahrheit: Bild-Paare erkennbarer Gesichter ───────────────────

def _erkennbar(bild_id, embedding, anteil=0.02) -> dict:
    """Ein erkennbares Gesicht im Bild (Flaechenanteil >= ANTEIL_ERKENNBAR)."""
    return {"bild_id": bild_id, "embedding": list(embedding), "anteil": anteil}


def test_anteil_erkennbar_ist_der_n9a_wert():
    assert pc.ANTEIL_ERKENNBAR == 0.005


def test_bild_paare_ein_paar_je_bild():
    a, b = _fern(1), _fern(2)
    paare = sw.bild_paare([_erkennbar("1", a), _erkennbar("1", b)])
    assert len(paare) == 1
    assert paare[0]["bild_id"] == "1"
    assert paare[0]["a"] == 0 and paare[0]["b"] == 1
    assert 0.0 <= paare[0]["distanz"] <= 2.0


def test_bild_paare_drei_gesichter_geben_drei_paare():
    eintraege = [_erkennbar("1", _fern(i)) for i in range(3)]
    assert len(sw.bild_paare(eintraege)) == 3


def test_bild_paare_kleines_gesicht_zaehlt_nicht():
    """Unter ANTEIL_ERKENNBAR ist es kein Vordergrund-Gesicht."""
    a, b = _fern(1), _fern(2)
    paare = sw.bild_paare([_erkennbar("1", a, anteil=0.001),
                           _erkennbar("1", b)])
    assert paare == []


def test_bild_paare_verschiedene_bilder_geben_kein_paar():
    paare = sw.bild_paare([_erkennbar("1", _fern(1)),
                           _erkennbar("2", _fern(2))])
    assert paare == []


def test_bild_paare_ohne_vektor_ergeben_kein_paar():
    eintraege = [{"bild_id": "1", "anteil": 0.02},
                 {"bild_id": "1", "anteil": 0.02}]
    assert sw.bild_paare(eintraege) == []


def test_bild_paare_ist_rein():
    assert sw.bild_paare([]) == []
    assert sw.bild_paare(None) == []


def test_verschmelzungsquote_zaehlt_die_gleiche_gruppe():
    a = _fern(1)
    eintraege = [_erkennbar("1", a), _erkennbar("1", a),
                 _erkennbar("2", a), _erkennbar("2", a)]
    paare = sw.bild_paare(eintraege)
    assert len(paare) == 2
    quote = sw.verschmelzungsquote(paare, [[0, 1, 2, 3]])
    assert quote["paare"] == 2
    assert quote["verschmolzen"] == 2
    assert quote["quote"] == pytest.approx(1.0)


def test_verschmelzungsquote_ohne_gruppen_ist_null():
    a = _fern(1)
    paare = sw.bild_paare([_erkennbar("1", a), _erkennbar("1", a)])
    quote = sw.verschmelzungsquote(paare, [])
    assert quote["verschmolzen"] == 0
    assert quote["quote"] == pytest.approx(0.0)


def test_gruppendurchmesser_misst_den_groessten_abstand():
    a, b = _fern(1), _fern(2)
    eintraege = [_erkennbar("1", a), _erkennbar("2", b)]
    durchmesser = sw.gruppendurchmesser([[0, 1]], eintraege)
    assert durchmesser["groesste"] > 0.5     # praktisch orthogonale Vektoren
    assert durchmesser["max"] == durchmesser["groesste"]


def test_gruppendurchmesser_ohne_gruppen_ist_leer():
    assert sw.gruppendurchmesser([], []) == {"je_gruppe": [], "groesste": None,
                                             "max": None}


def test_kettenmass_belegt_das_transitive_verketten():
    """Ein Paar INNERHALB einer Gruppe, das weiter als die Schwelle liegt."""
    a, b = _fern(1), _fern(2)
    eintraege = [_erkennbar("1", a), _erkennbar("1", b)]
    paare = [{"bild_id": "1", "a": 0, "b": 1, "distanz": 0.9}]
    ketten = sw.kettenmass(paare, [[0, 1]], eintraege, 0.45)
    assert ketten["paare_innerhalb"] == 1
    assert ketten["paare_weit"] == 1
    assert ketten["anteil_weit"] == pytest.approx(1.0)
    assert ketten["durchmesser"]["max"] > 0.45


def test_kettenmass_ohne_verschmelzung_ist_null():
    a = _fern(1)
    eintraege = [_erkennbar("1", a), _erkennbar("1", a)]
    paare = [{"bild_id": "1", "a": 0, "b": 1, "distanz": 0.0}]
    ketten = sw.kettenmass(paare, [], eintraege, 0.45)
    assert ketten["paare_innerhalb"] == 0
    assert ketten["anteil_weit"] == pytest.approx(0.0)


def test_schwelle_messen_bringt_die_bodenwahrheit_mit():
    a = _fern(1)
    eintraege = [_erkennbar("1", a), _erkennbar("1", a),
                 _erkennbar("2", a), _erkennbar("2", a)]
    messung = sw.schwelle_messen(eintraege, ["A"] * 4, 0.45)
    assert messung["personen_paare"] == 2
    assert messung["verschmolzene_paare"] == 2
    assert messung["verschmelzungsquote"] == pytest.approx(1.0)
    assert messung["kettenmass"]["paare_innerhalb"] == 2
    assert messung["strukturmass"]["hinweis"]
    assert "STRUKTURMASS" in messung["strukturmass"]["hinweis"]


def test_bericht_text_trennt_wahrheit_und_strukturmass():
    a = _fern(1)
    bilder = [_bild("1", [a, a]), _bild("2", [a, a])]
    text = sw.bericht_text(sw.messlauf(bilder, {"1": "A", "2": "A"})["bericht"])
    assert "BODENWAHRHEIT" in text
    assert "STRUKTURMASS" in text
    assert "Bild-Paare" in text
    assert "Verschmolzen" in text or "verschmolzen" in text


def test_empfehlung_nennt_die_verschmelzung():
    a = _fern(1)
    bilder = [_bild("1", [a, a]), _bild("2", [a, a])]
    empfehlung = sw.messlauf(bilder, {})["empfehlung"]
    assert empfehlung["heute_verschmelzungsquote"] == pytest.approx(1.0)
    assert empfehlung["heute_paare"] == 2
    assert "Bodenwahrheit" in empfehlung["kernaussage"]
    assert "STRUKTURMASS" in empfehlung["struktur_hinweis"]


def test_empfehlung_ist_ohne_paare_ehrlich():
    empfehlung = sw.empfehlung_bauen(
        [{"schwelle": 0.45, "personen_paare": 0, "verschmolzene_paare": 0,
          "verschmelzungsquote": 0.0}], {"gleich": None, "fremd": None}, 0.45)
    assert "keine Identitaetsaussage" in empfehlung["kernaussage"]


# ── 10. Schutz: nur ausserhalb des Repos schreiben ────────────────────────

def test_pruefe_ausserhalb_repo_laesst_tmp_zu(tmp_path):
    assert sw.pruefe_ausserhalb_repo(str(tmp_path)) == str(tmp_path)


def test_pruefe_ausserhalb_repo_lehnt_repo_ab():
    with pytest.raises(SystemExit):
        sw.pruefe_ausserhalb_repo(str(REPO / "irgendwas"))


def test_bericht_schreiben_im_repo_wird_abgelehnt():
    with pytest.raises(SystemExit):
        sw.bericht_schreiben(str(REPO / "bericht_probe.json"), {})


def test_bericht_schreiben_und_lesen_ist_ein_kreis(tmp_path):
    pfad = tmp_path / "bericht.json"
    sw.bericht_schreiben(str(pfad), {"a": 1})
    assert json.loads(pfad.read_text(encoding="utf-8")) == {"a": 1}


# ── 11. Kommandozeile ─────────────────────────────────────────────────────

def _vektoren_schreiben(pfad: Path, bilder) -> str:
    with open(pfad, "w", encoding="utf-8") as datei:
        for bild in bilder:
            datei.write(json.dumps(bild) + "\n")
    return str(pfad)


def _lauf(tmp_path, bilder, zuordnung, zusatz=()):
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl", bilder)
    plan = _plan_schreiben(
        tmp_path / "plan.json",
        [{"fileid": kennung, "thema_quelle": label}
         for kennung, label in zuordnung.items()])
    argv = ["--vektoren", vektoren, "--plan", plan,
            "--ausgabe", str(tmp_path / "bericht.json")]
    return sw.main(argv + list(zusatz))


def test_main_laeuft_ohne_schreiben_durch(tmp_path):
    bilder, zuordnung = _trennbares_paar()
    assert _lauf(tmp_path, bilder, zuordnung) == 0


def test_main_schreibt_standardmaessig_nichts(tmp_path):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung)
    assert not (tmp_path / "bericht.json").exists()


def test_main_sagt_dass_nichts_geschrieben_wurde(tmp_path, capsys):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung)
    assert "NICHTS geschrieben" in capsys.readouterr().out


def test_main_zeigt_die_messtabelle(tmp_path, capsys):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung)
    ausgabe = capsys.readouterr().out
    assert "Schwelle" in ausgabe
    # Die Tabelle nennt jetzt die Bodenwahrheit (Bild-Paare) UND das
    # Strukturmass getrennt — der alte Anlass-Text allein war irrefuehrend.
    assert "Bild-Paare" in ausgabe
    assert "BODENWAHRHEIT" in ausgabe
    assert "STRUKTURMASS" in ausgabe


def test_main_nennt_die_unveraenderte_schwelle(tmp_path, capsys):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung)
    assert "unveraendert" in capsys.readouterr().out


def test_main_mit_schreiben_legt_den_bericht_an(tmp_path):
    bilder, zuordnung = _trennbares_paar()
    assert _lauf(tmp_path, bilder, zuordnung, ["--schreiben"]) == 0
    assert (tmp_path / "bericht.json").is_file()


def test_main_mit_schreiben_beziffert_die_falschen_cluster(tmp_path):
    bilder, zuordnung = _ueberlappendes_paar()
    _lauf(tmp_path, bilder, zuordnung, ["--schreiben"])
    bericht = json.loads((tmp_path / "bericht.json").read_text(encoding="utf-8"))
    assert bericht["empfehlung"]["trennbar"] is False


def test_main_trocken_hat_vorrang_vor_schreiben(tmp_path):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung, ["--schreiben", "--trocken"])
    assert not (tmp_path / "bericht.json").exists()


def test_main_erlaubt_eigene_schwellen(tmp_path, capsys):
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung, ["--schwellen", "0.45,0.2"])
    assert "0.20000" in capsys.readouterr().out


def test_main_beschriftung_aus_dem_dateinamen(tmp_path):
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl",
                                   [_bild("1", [_fern(1)])])
    plan = _plan_schreiben(tmp_path / "plan.json",
                           [{"fileid": "1",
                             "von_name": "IMG_1_BURST002.jpg"}])
    assert sw.main(["--vektoren", vektoren, "--plan", plan,
                    "--beschriftung", "von_name",
                    "--ausgabe", str(tmp_path / "b.json")]) == 0


def test_main_meldet_fehlende_vektordatei(tmp_path, capsys):
    plan = _plan_schreiben(tmp_path / "plan.json", [])
    assert sw.main(["--vektoren", str(tmp_path / "gibtsnicht.jsonl"),
                    "--plan", plan,
                    "--ausgabe", str(tmp_path / "b.json")]) == 2
    assert "Fehler" in capsys.readouterr().out


def test_main_ausgabe_im_repo_wird_abgelehnt(tmp_path):
    bilder, zuordnung = _trennbares_paar()
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl", bilder)
    plan = _plan_schreiben(tmp_path / "plan.json", [])
    with pytest.raises(SystemExit):
        sw.main(["--vektoren", vektoren, "--plan", plan,
                 "--ausgabe", str(REPO / "bericht_probe.json"), "--schreiben"])


def test_main_aendert_keine_schwelle(tmp_path):
    """Zusage des Schritts: messen, nicht stellen — die N9a-Werte bleiben."""
    vorher = (pc.CLUSTER_SCHWELLE, pc.CLUSTER_MIN_NACHBAR, pc.ANTEIL_MIN)
    bilder, zuordnung = _trennbares_paar()
    _lauf(tmp_path, bilder, zuordnung, ["--schreiben"])
    assert (pc.CLUSTER_SCHWELLE, pc.CLUSTER_MIN_NACHBAR, pc.ANTEIL_MIN) == vorher


# ── 12. Schutz: Quelltext (keine Schwellenaenderung, kein Loeschen) ───────

def test_quelltext_setzt_keine_schwelle():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("pc.CLUSTER_SCHWELLE =", "pc.CLUSTER_MIN_NACHBAR =",
                     "pc.ANTEIL_MIN =", "pc.MIN_SCORE ="):
        assert verboten not in quelle, f"Schwelle gesetzt: {verboten}"


def test_quelltext_hat_keine_loeschfunktion():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("deletefile", "deletefolder", "os.remove", "os.unlink",
                     "shutil.rmtree"):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_hat_keinen_pcloud_aufruf():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("requests", "httpx", "e.pcloud"):
        assert verboten not in quelle, f"pCloud-Aufruf im Quelltext: {verboten}"


def test_quelltext_hat_keinen_netzaufruf():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "urllib" not in quelle and "socket" not in quelle


def test_quelltext_print_zeigt_keine_vektorwerte():
    zeilen = WERKZEUG.read_text(encoding="utf-8").splitlines()
    for nummer, zeile in enumerate(zeilen, start=1):
        if "print(" not in zeile:
            continue
        for verboten in ("embedding", "mittelpunkt", ".tolist()", "bbox",
                         "token", "np."):
            assert verboten not in zeile.lower(), \
                f"Zeile {nummer} gibt '{verboten}' aus: {zeile}"
    assert [zeile for zeile in zeilen if "print(" in zeile]


def test_quelltext_hat_die_vorgabefunktionen():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for name in VORGABE_FUNKTIONEN:
        assert f"def {name}(" in quelle, f"Vorgabefunktion fehlt: {name}"


def test_quelltext_ist_python_lesbar():
    assert isinstance(sw.STANDARD_BASIS, str)
    assert sw.REPO == str(REPO)


def test_modul_haengt_keine_datei_an_das_manifest():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "manifest" not in quelle.lower()


def test_unrein_ab_ist_zwei():
    assert sw.UNREIN_AB == 2


def test_schwellen_standard_enthaelt_den_heutigen_wert():
    assert pc.CLUSTER_SCHWELLE in sw.SCHWELLEN_STANDARD
