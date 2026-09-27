"""Pruefungen fuer ``personen_cluster.py`` (Nachtlauf-Schritt N9a).

Alles OHNE Netz und OHNE echte Daten: keine pCloud, kein Download, kein
Bild aus dem Bestand, keine echten Ordner- oder Personennamen. Die Vektoren
sind **synthetisch** und deterministisch aus einem Seed erzeugt
(``numpy.random.default_rng``); Dateien gehen nach ``tmp_path``. Katalog-
Kennungen sind ``Person_001`` … , ``bild_id`` sind erfundene Ziffern.

Die eine Attrappe (``kachel_holen``) liegt im Test selbst: sie liefert Bytes
aus einem im Speicher gebauten 1x1-PNG bzw. ``None`` — genau die Steckdose,
die im Betrieb spaeter pCloud/Handy fuellt.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_personen_cluster.py -q
"""

from __future__ import annotations

import importlib.util
import io
import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "personen_cluster.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pc = _laden(WERKZEUG, "personen_cluster")

# Die beiden Nachbarmodule liegen im selben Ordner: das Messwerkzeug (N9e) und
# die Verkettung (N9f). Sie werden fuer die Delegations-Pruefungen geladen —
# nicht nachgebaut.
VERKETTUNG_DATEI = REPO / "tools" / "foto_sortierung" / "personen_verkettung.py"
SCHWELLE_DATEI = REPO / "tools" / "foto_sortierung" / "personen_schwelle.py"
pv = _laden(VERKETTUNG_DATEI, "personen_verkettung_fuer_cluster")
ps = _laden(SCHWELLE_DATEI, "personen_schwelle_fuer_cluster")

# Ein 12-MP-Handyfoto — die Bezugsflaeche der Schwellen.
BREITE = 4032
HOEHE = 3024
FLAECHE = BREITE * HOEHE

# Erfundene pCloud-Kennungen (nur Ziffern, keine Pfade/Ordner).
BILD_A = "1234567"
BILD_B = "1234568"
BILD_C = "1234569"

# Die Pflichtfunktionen des Feinauftrags (Namen sind Vorgabe).
VORGABE_FUNKTIONEN = (
    "gesichts_anteil", "bild_art", "vordergrund_gesichter", "katalog_treffer",
    "bild_entscheidung", "vektoren_clustern", "gruppen_kennungen",
    "referenzseiten_bauen", "bericht_bauen", "main",
)


# ── Synthetische Vektoren (deterministisch, offline) ───────────────────────

def _basis(seed: int, laenge: int = pc.MERKMAL_LAENGE):
    """Ein Basis-Merkmal aus einem Seed (128 Werte)."""
    return np.random.default_rng(seed).normal(size=laenge)


def _nahe(basis, seed: int, streuung: float = 0.03) -> list[float]:
    """Ein Vektor DICHT an ``basis`` — dieselbe Person, ein anderes Foto."""
    rauschen = np.random.default_rng(seed).normal(size=len(basis))
    return [float(wert) for wert in basis + streuung * rauschen]


def _fern(seed: int) -> list[float]:
    """Ein Vektor ohne Bezug (im 128-dim Raum fast orthogonal) — Rauschen."""
    return [float(wert) for wert in np.random.default_rng(seed).normal(
        size=pc.MERKMAL_LAENGE)]


def _gesicht(bbox, score=0.9, embedding=None, seed=1):
    """Ein Gesichts-Eintrag im Eingabe-Format (``bbox``, ``score``, ``embedding``)."""
    return {"bbox": list(bbox), "score": score,
            "embedding": embedding if embedding is not None else _fern(seed)}


def _klein(anzahl: int, embedding=None, score=0.9) -> list[dict]:
    """``anzahl`` nutzbare, aber NICHT erkennbare Gesichter (100x100 Pixel)."""
    return [_gesicht([float(10 * nummer), 10.0, 100.0, 100.0], score=score,
                     embedding=embedding, seed=nummer)
            for nummer in range(anzahl)]


def _gross(embedding=None, score=0.9, kante=300.0) -> dict:
    """Ein erkennbares Gesicht (``kante`` x ``kante`` Pixel im 12-MP-Foto)."""
    return _gesicht([100.0, 100.0, kante, kante], score=score,
                    embedding=embedding, seed=99)


def _bild(bild_id=BILD_A, gesichter=(), breite=BREITE, hoehe=HOEHE) -> dict:
    return {"bild_id": bild_id, "breite": breite, "hoehe": hoehe,
            "gesichter": list(gesichter)}


def _katalog(*personen) -> dict:
    """Katalog aus ``(kennung, vektor)``-Paaren; ``name`` bleibt ``None``."""
    return {"personen": [{"kennung": kennung, "name": None,
                          "vektoren": [vektor]}
                         for kennung, vektor in personen]}


def _png_bytes(farbe=(10, 120, 200), groesse=(24, 24)) -> bytes:
    """Ein kleines synthetisches PNG als Bytes (die Attrappe eines Downloads)."""
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, format="PNG")
    return puffer.getvalue()


def _holen_immer(rohdaten=None):
    """Eine ``kachel_holen``-Attrappe, die immer dieselben Bytes liefert."""
    daten = _png_bytes() if rohdaten is None else rohdaten

    def holen(_eintrag):
        return daten

    return holen


def _vektoren_schreiben(pfad: Path, bilder) -> str:
    """Bilder als JSONL ablegen (so kommt die Datei aus ``face_infer.py``)."""
    with open(pfad, "w", encoding="utf-8") as datei:
        for bild in bilder:
            datei.write(json.dumps(bild) + "\n")
    return str(pfad)


def _gruppen_vektoren(anzahl_gruppen=3, je_gruppe=5, streuung=0.03) -> tuple:
    """``(vektoren, gruppen)``: klar getrennte Gruppen — die bekannte Wahrheit."""
    vektoren: list[list] = []
    gruppen: list[list[int]] = []
    for gruppe in range(anzahl_gruppen):
        basis = _basis(1000 + gruppe)
        indizes = []
        for nummer in range(je_gruppe):
            indizes.append(len(vektoren))
            vektoren.append(_nahe(basis, seed=2000 + gruppe * 10 + nummer,
                                  streuung=streuung))
        gruppen.append(indizes)
    return vektoren, gruppen


def _gruppen_eintraege(kennung=("Person_001",), je_gruppe=1) -> list[dict]:
    """``[{kennung, eintraege}]`` mit Kachel-Eintraegen (anteil/score/bild_id)."""
    ergebnis = []
    for nummer, einzelkennung in enumerate(kennung):
        ergebnis.append({"kennung": einzelkennung,
                         "eintraege": [
                             {"bild_id": f"{9000000 + nummer * 10 + lauf}",
                              "score": 0.8 + 0.01 * lauf,
                              "anteil": 0.02 + 0.001 * lauf,
                              "bbox": [1.0, 2.0, 300.0, 300.0]}
                             for lauf in range(je_gruppe)]})
    return ergebnis


# ── 1. gesichts_anteil ────────────────────────────────────────────────────

def test_gesichts_anteil_rechnet_flaeche_durch_bildfläche():
    assert pc.gesichts_anteil([0.0, 0.0, 420.0, 420.0], 4032, 3024) == \
        pytest.approx(420 * 420 / FLAECHE)


def test_gesichts_anteil_ganzes_bild_ist_eins():
    assert pc.gesichts_anteil([0.0, 0.0, 100.0, 100.0], 100, 100) == 1.0


def test_gesichts_anteil_zu_grosse_bbox_wird_gedeckelt():
    assert pc.gesichts_anteil([0.0, 0.0, 9000.0, 9000.0], 100, 100) == 1.0


def test_gesichts_anteil_breite_null_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0, 10.0], 0, 100) == 0.0


def test_gesichts_anteil_hoehe_null_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0, 10.0], 100, 0) == 0.0


def test_gesichts_anteil_negative_bildmasse_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0, 10.0], -100, -100) == 0.0


def test_gesichts_anteil_bbox_breite_null_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 0.0, 10.0], 100, 100) == 0.0


def test_gesichts_anteil_bbox_hoehe_negativ_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0, -10.0], 100, 100) == 0.0


def test_gesichts_anteil_bbox_falsche_laenge_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0], 100, 100) == 0.0


def test_gesichts_anteil_bbox_none_ist_null():
    assert pc.gesichts_anteil(None, 100, 100) == 0.0


def test_gesichts_anteil_nicht_numerisch_ist_null():
    assert pc.gesichts_anteil(["a", 2.0, 10.0, 10.0], 100, 100) == 0.0


def test_gesichts_anteil_bildmasse_nicht_numerisch_ist_null():
    assert pc.gesichts_anteil([1.0, 2.0, 10.0, 10.0], "4032", 3024) == 0.0


def test_gesichts_anteil_wahrheitswert_zaehlt_nicht_als_zahl():
    assert pc.gesichts_anteil([1.0, 2.0, True, 10.0], 100, 100) == 0.0


# ── 2. bild_art: die Mengen-Entscheidung ──────────────────────────────────

def test_bild_art_ohne_gesichter_ist_leer():
    assert pc.bild_art([], BREITE, HOEHE) == pc.ART_LEER


def test_bild_art_gesichter_none_ist_leer():
    assert pc.bild_art(None, BREITE, HOEHE) == pc.ART_LEER


def test_bild_art_ein_grosses_gesicht_ist_gruppe():
    assert pc.bild_art([_gross()], BREITE, HOEHE) == pc.ART_GRUPPE


def test_bild_art_drei_kleine_gesichter_sind_unklar():
    assert pc.bild_art(_klein(3), BREITE, HOEHE) == pc.ART_UNKLAR


def test_bild_art_fuenf_kleine_gesichter_sind_unklar():
    assert pc.bild_art(_klein(5), BREITE, HOEHE) == pc.ART_UNKLAR


def test_bild_art_sechs_kleine_gesichter_sind_menge():
    assert pc.bild_art(_klein(6), BREITE, HOEHE) == pc.ART_MENGE


def test_bild_art_vierzig_kleine_gesichter_sind_menge():
    assert pc.bild_art(_klein(40), BREITE, HOEHE) == pc.ART_MENGE


def test_bild_art_grosses_gesicht_gewinnt_gegen_menge():
    gesichter = _klein(40) + [_gross()]
    assert pc.bild_art(gesichter, BREITE, HOEHE) == pc.ART_GRUPPE


def test_bild_art_fuenf_kleine_plus_ein_grosses_ist_gruppe():
    assert pc.bild_art(_klein(5) + [_gross()], BREITE, HOEHE) == pc.ART_GRUPPE


def test_bild_art_score_unter_min_score_ist_leer():
    assert pc.bild_art([_gross(score=0.59)], BREITE, HOEHE) == pc.ART_LEER


def test_bild_art_score_genau_min_score_zaehlt():
    assert pc.bild_art([_gross(score=pc.MIN_SCORE)], BREITE, HOEHE) == \
        pc.ART_GRUPPE


def test_bild_art_bbox_breite_null_ist_leer():
    assert pc.bild_art([_gesicht([0.0, 0.0, 0.0, 300.0])], BREITE, HOEHE) == \
        pc.ART_LEER


def test_bild_art_bildmasse_null_wirft_nichts():
    assert pc.bild_art(_klein(40), 0, 0) == pc.ART_LEER


def test_bild_art_entartete_boxen_zaehlen_nicht_als_gesicht():
    """Boxen **unter** dem Flaechen-Tor zaehlen nicht — als Regel, nicht als Zahl.

    Die Kantenlaenge wird aus ``ANTEIL_MIN`` und der Bildflaeche gerechnet
    (``sqrt(ANTEIL_MIN * Flaeche) - 1``); der Test haengt damit am Verhaeltnis,
    nicht an einem festgenagelten Zahlenwert. So bleibt er gueltig, wenn das
    Tor aus einem neuen Messergebnis nachgezogen wird.
    """
    kante = max(1.0, math.sqrt(pc.ANTEIL_MIN * FLAECHE) - 1.0)
    entartet = [_gesicht([float(nummer), 0.0, kante, kante], seed=nummer)
                for nummer in range(40)]
    assert pc.gesichts_anteil(entartet[0]["bbox"], BREITE, HOEHE) < pc.ANTEIL_MIN
    assert pc.bild_art(entartet, BREITE, HOEHE) == pc.ART_LEER


def test_bild_art_sieht_nur_noch_entartete_boxen_als_zu_klein():
    """Was das Tor verwirft, ist eine Box ohne Flaeche — nicht ein Fund.

    Der alte Wert 0,0005 verwarf 20x20-Boxen (400 px von 12,2 MP). Ueber
    ``params`` ist er noch abrufbar (der Test nagelt also nicht den alten
    Zahlenwert im Modul fest, sondern rechnet ihn gegen): damals ``leer``,
    heute sind genau dieselben Boxen nutzbar -> Menschenmenge.
    """
    boxen = [_gesicht([float(nummer), 0.0, 20.0, 20.0], seed=nummer)
             for nummer in range(40)]
    assert pc.gesichts_anteil(boxen[0]["bbox"], BREITE, HOEHE) > pc.ANTEIL_MIN
    assert pc.bild_art(boxen, BREITE, HOEHE, {"anteil_min": 0.0005}) == \
        pc.ART_LEER
    assert pc.bild_art(boxen, BREITE, HOEHE) == pc.ART_MENGE


def test_anteil_min_verwirft_keinen_echten_fund_mehr():
    """Das Tor liegt unter der **kleinsten echten** Detektion (Regel + Beleg).

    Beleg-Zahlen der Vormessung: kleinste echte Detektion 0,000145 (13 kleine
    Gesichter), kleinste echte Detektion des Nachtlaufs N9b 0,000022
    (16x22 px). Beide muessen **ueber** dem Tor liegen, sonst verwirft es
    echte Gesichter — und der Zweig ``menge`` wird nie erreicht.
    """
    assert 0.0 < pc.ANTEIL_MIN <= 0.000022
    assert pc.ANTEIL_MIN <= 0.000145
    assert pc.ANTEIL_MIN < 0.0005, "das Tor ist gesenkt, nicht angehoben"


def test_bild_art_nutzt_die_benannten_konstanten():
    assert pc.MENGEN_PARAMS["min_score"] == pc.MIN_SCORE
    assert pc.MENGEN_PARAMS["anteil_min"] == pc.ANTEIL_MIN
    assert pc.MENGEN_PARAMS["anteil_erkennbar"] == pc.ANTEIL_ERKENNBAR
    assert pc.MENGEN_PARAMS["menge_anzahl"] == pc.MENGE_ANZAHL


def test_nur_das_flaechen_tor_wurde_gesenkt():
    """Zusage des Schritts: **keine andere** Schwelle angefasst.

    Die Zahlen stehen hier bewusst als Werte — genau das ist die Zusage
    (``MENGE_ANZAHL`` bleibt 6; das ist ein N9a-Beschluss und braucht eine
    eigene Messung). ``MENGEN_PARAMS`` zieht ``ANTEIL_MIN`` automatisch nach.
    """
    assert pc.MIN_SCORE == 0.6
    assert pc.ANTEIL_ERKENNBAR == 0.005
    assert pc.MENGE_ANZAHL == 6
    assert pc.KATALOG_SCHWELLE == 0.363
    assert pc.CLUSTER_SCHWELLE == 0.45
    assert pc.CLUSTER_MIN_NACHBAR == 3
    assert pc.ALT_SCHWELLE == pc.KATALOG_SCHWELLE
    assert pc.MENGEN_PARAMS["anteil_min"] == pc.ANTEIL_MIN == 0.00001


def test_bild_art_params_ueberschreibt_menge_anzahl():
    params = {"menge_anzahl": 3}
    assert pc.bild_art(_klein(3), BREITE, HOEHE, params) == pc.ART_MENGE


def test_bild_art_params_ueberschreibt_die_erkennbarkeit():
    params = {"anteil_erkennbar": 0.0001}
    assert pc.bild_art(_klein(40), BREITE, HOEHE, params) == pc.ART_GRUPPE


def test_bild_art_unbrauchbare_params_fallen_auf_die_vorgabe():
    params = {"menge_anzahl": "viele", "min_score": None}
    assert pc.bild_art(_klein(40), BREITE, HOEHE, params) == pc.ART_MENGE


def test_bild_art_nennt_alle_vier_arten():
    assert pc.ARTEN == ("leer", "gruppe", "menge", "unklar")


# ── 3. Das Massenfoto (Pflichtpruefung des Plans) ─────────────────────────

def test_massenfoto_erzeugt_keine_gruppe():
    bild = _bild(gesichter=_klein(40))
    assert pc.bild_art(bild["gesichter"], BREITE, HOEHE) == pc.ART_MENGE
    assert pc.bild_entscheidung(bild)["clustern"] is False


def test_massenfoto_grund_ist_menge_ohne_bekannte_person():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=_klein(40)))
    assert entscheidung["grund"] == "menge_ohne_bekannte_person"
    assert entscheidung["personen"] == []


def test_massenfoto_mit_bekannter_person_wird_geclustert():
    katalog = _katalog(("Person_007", _fern(4242)))
    bild = _bild(gesichter=_klein(40) + [_gross(embedding=_fern(4242))])
    entscheidung = pc.bild_entscheidung(bild, katalog)
    assert entscheidung["clustern"] is True
    assert entscheidung["personen"] == ["Person_007"]


def test_massenfoto_mit_bekannter_person_hat_den_richtigen_grund():
    """Ein erkennbares Vordergrund-Gesicht macht aus der Menge eine Gruppe.

    Das ist die Regel von ``bild_art``: ein erkennbar grosses Gesicht gewinnt
    gegen die Menge. Der ``grund`` heisst dann ``"gruppe"``.
    """
    katalog = _katalog(("Person_007", _fern(4242)))
    bild = _bild(gesichter=_klein(40) + [_gross(embedding=_fern(4242))])
    entscheidung = pc.bild_entscheidung(bild, katalog)
    assert entscheidung["art"] == pc.ART_GRUPPE
    assert entscheidung["grund"] == "gruppe"


def test_menge_mit_bekannter_kleiner_person_wird_geclustert():
    """Die Vordergrund-Pruefung der Menge: bekannte Person erkannt -> anlernen."""
    katalog = _katalog(("Person_007", _fern(4242)))
    gesichter = _klein(39) + [_gesicht([10.0, 10.0, 100.0, 100.0],
                                       embedding=_fern(4242))]
    bild = _bild(gesichter=gesichter)
    entscheidung = pc.bild_entscheidung(bild, katalog)
    assert entscheidung["art"] == pc.ART_MENGE
    assert entscheidung["clustern"] is True
    assert entscheidung["grund"] == "menge_mit_bekannter_person"
    assert entscheidung["personen"] == ["Person_007"]


def test_menge_mit_unbekannten_gesichtern_bleibt_ungelernt():
    katalog = _katalog(("Person_007", _fern(4242)))
    bild = _bild(gesichter=_klein(40))
    entscheidung = pc.bild_entscheidung(bild, katalog)
    assert entscheidung["art"] == pc.ART_MENGE
    assert entscheidung["clustern"] is False


def test_grosses_unbekanntes_gesicht_ergibt_gruppe():
    """Ein grosses Gesicht ist ein Personen-Foto — auch ohne Katalog-Treffer."""
    bild = _bild(gesichter=_klein(40) + [_gross(embedding=_fern(777))])
    entscheidung = pc.bild_entscheidung(bild, _katalog(("Person_007", _fern(4242))))
    assert entscheidung["art"] == pc.ART_GRUPPE
    assert entscheidung["clustern"] is True
    assert entscheidung["personen"] == []


# ── 4. vordergrund_gesichter ──────────────────────────────────────────────

def test_vordergrund_gesichter_ohne_gesichter_ist_leer():
    assert pc.vordergrund_gesichter([], BREITE, HOEHE) == []


def test_vordergrund_gesichter_laesst_kleine_weg():
    assert pc.vordergrund_gesichter(_klein(40), BREITE, HOEHE) == []


def test_vordergrund_gesichter_nimmt_erkennbare():
    assert len(pc.vordergrund_gesichter([_gross()], BREITE, HOEHE)) == 1


def test_vordergrund_gesichter_sortiert_groesstes_zuerst():
    klein_gross = _gesicht([0.0, 0.0, 300.0, 300.0], seed=1)
    gross_gross = _gesicht([0.0, 0.0, 600.0, 600.0], seed=2)
    ergebnis = pc.vordergrund_gesichter([klein_gross, gross_gross], BREITE, HOEHE)
    assert ergebnis[0]["anteil"] > ergebnis[1]["anteil"]
    assert ergebnis[0]["anteil"] == pytest.approx(600 * 600 / FLAECHE)


def test_vordergrund_gesichter_sortiert_bei_gleicher_flaeche_nach_score():
    schwach = _gesicht([0.0, 0.0, 400.0, 400.0], score=0.7, seed=1)
    stark = _gesicht([0.0, 0.0, 400.0, 400.0], score=0.95, seed=2)
    ergebnis = pc.vordergrund_gesichter([schwach, stark], BREITE, HOEHE)
    assert ergebnis[0]["score"] == 0.95


def test_vordergrund_gesichter_tragen_anteil_und_index():
    ergebnis = pc.vordergrund_gesichter(_klein(5) + [_gross()], BREITE, HOEHE)
    assert len(ergebnis) == 1
    assert "anteil" in ergebnis[0] and "index" in ergebnis[0]


# ── 5. katalog_treffer ────────────────────────────────────────────────────

def test_katalog_treffer_findet_die_person():
    basis = _basis(7)
    treffer = pc.katalog_treffer([_gesicht([0.0, 0.0, 300.0, 300.0],
                                           embedding=_nahe(basis, 1))],
                                 _katalog(("Person_001", list(basis))))
    assert [eintrag["kennung"] for eintrag in treffer] == ["Person_001"]


def test_katalog_treffer_score_ist_hoch_bei_gleichem_vektor():
    basis = list(_basis(7))
    treffer = pc.katalog_treffer([{"embedding": basis}],
                                 _katalog(("Person_001", basis)))
    assert treffer[0]["score"] == pytest.approx(1.0, abs=1e-6)


def test_katalog_treffer_fremder_vektor_ist_kein_treffer():
    assert pc.katalog_treffer([_gesicht([0.0, 0.0, 300.0, 300.0],
                                        embedding=_fern(1))],
                              _katalog(("Person_001", _fern(2)))) == []


def test_katalog_treffer_schwelle_wird_beachtet():
    basis = _basis(7)
    treffer = pc.katalog_treffer([{"embedding": basis}],
                                 _katalog(("Person_001", basis)), schwelle=1.5)
    assert treffer == []


def test_katalog_treffer_nimmt_den_besten_vektor_je_person():
    basis = _basis(7)
    person = {"kennung": "Person_001", "name": None,
              "vektoren": [list(_fern(1)), _nahe(basis, 3)]}
    treffer = pc.katalog_treffer([{"embedding": _nahe(basis, 4)}],
                                 {"personen": [person]})
    assert treffer[0]["score"] > 0.9


def test_katalog_treffer_entdoppelt_je_kennung():
    basis = _basis(7)
    person = {"kennung": "Person_001", "name": None,
              "vektoren": [list(basis), list(basis)]}
    treffer = pc.katalog_treffer([{"embedding": list(basis)}],
                                 {"personen": [person, person]})
    assert len(treffer) == 1


def test_katalog_treffer_sortiert_aehnlichstes_zuerst():
    personen = [{"kennung": "Person_001", "name": None,
                 "vektoren": [_nahe(_basis(7), 5)]},
                {"kennung": "Person_002", "name": None,
                 "vektoren": [list(_basis(7))]}]
    treffer = pc.katalog_treffer([{"embedding": list(_basis(7))}],
                                 {"personen": personen})
    assert [eintrag["kennung"] for eintrag in treffer][0] == "Person_002"


def test_katalog_treffer_gibt_den_namen_mit_aber_nie_leer_zurueck():
    basis = list(_basis(7))
    treffer = pc.katalog_treffer([{"embedding": basis}],
                                 {"personen": [{"kennung": "Person_001",
                                                "name": None,
                                                "vektoren": [basis]}]})
    assert treffer[0]["name"] is None


def test_katalog_treffer_ohne_katalog_ist_leer():
    assert pc.katalog_treffer([_gross()], {}) == []


def test_katalog_treffer_ohne_gesichter_ist_leer():
    assert pc.katalog_treffer([], _katalog(("Person_001", _fern(1)))) == []


def test_katalog_treffer_falsche_merkmalslaenge_ist_kein_treffer():
    assert pc.katalog_treffer([{"embedding": [0.1, 0.2]}],
                              _katalog(("Person_001", _fern(1)))) == []


def test_katalog_personen_akzeptiert_eine_liste():
    assert len(pc.katalog_personen([{"kennung": "Person_001",
                                     "vektoren": [_fern(1)]}])) == 1


def test_katalog_personen_ohne_vektoren_fallen_weg():
    assert pc.katalog_personen({"personen": [{"kennung": "Person_001",
                                              "vektoren": []}]}) == []


def test_katalog_personen_ohne_kennung_fallen_weg():
    assert pc.katalog_personen({"personen": [{"vektoren": [_fern(1)]}]}) == []


def test_katalog_personen_einzelfeld_vektor_zaehlt():
    personen = pc.katalog_personen({"personen": [{"kennung": "Person_001",
                                                  "vektor": _fern(1)}]})
    assert len(personen[0]["vektoren"]) == 1


# ── 6. bild_entscheidung ──────────────────────────────────────────────────

def test_bild_entscheidung_hat_alle_felder():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=[_gross()]))
    assert set(entscheidung) == {"bild_id", "art", "anzahl_nutzbar",
                                 "anzahl_erkennbar", "clustern", "personen",
                                 "grund"}


def test_bild_entscheidung_gruppe_clustert():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=[_gross()]))
    assert entscheidung["clustern"] is True
    assert entscheidung["grund"] == "gruppe"


def test_bild_entscheidung_leer_clustert_nicht():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=[]))
    assert entscheidung["clustern"] is False
    assert entscheidung["grund"] == "leer"


def test_bild_entscheidung_unklar_clustert_nicht():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=_klein(3)))
    assert entscheidung["clustern"] is False
    assert entscheidung["grund"] == "unklar"


def test_bild_entscheidung_zaehlt_nutzbar_und_erkennbar():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=_klein(40) + [_gross()]))
    assert entscheidung["anzahl_nutzbar"] == 41
    assert entscheidung["anzahl_erkennbar"] == 1


def test_bild_entscheidung_uebernimmt_die_bild_id_als_text():
    assert pc.bild_entscheidung({"bild_id": 1234567})["bild_id"] == "1234567"


def test_bild_entscheidung_ohne_bild_id_ist_leerzeichenkette():
    assert pc.bild_entscheidung({})["bild_id"] == ""


def test_bild_entscheidung_vertraegt_none():
    assert pc.bild_entscheidung(None)["art"] == pc.ART_LEER


def test_bild_entscheidung_ist_deterministisch():
    bild = _bild(gesichter=_klein(40))
    assert pc.bild_entscheidung(bild) == pc.bild_entscheidung(bild)


def test_bild_entscheidung_ohne_katalog_clustert_die_gruppe():
    entscheidung = pc.bild_entscheidung(_bild(gesichter=[_gross()]))
    assert entscheidung["personen"] == []


def test_bild_entscheidung_ohne_dateizugriff(monkeypatch):
    """Nebenwirkungsfrei: selbst ohne ``open`` laeuft die Entscheidung."""
    def verboten(*_args, **_kwargs):
        raise AssertionError("bild_entscheidung hat eine Datei angefasst!")

    monkeypatch.setattr("builtins.open", verboten)
    katalog = _katalog(("Person_007", _fern(4242)))
    bild = _bild(gesichter=_klein(40) + [_gross(embedding=_fern(4242))])
    assert pc.bild_entscheidung(bild, katalog)["clustern"] is True


# ── 7. vektoren_clustern ──────────────────────────────────────────────────

def test_vektoren_clustern_findet_drei_gruppen():
    vektoren, _ = _gruppen_vektoren()
    assert len(pc.vektoren_clustern(vektoren, 0.45, 3)) == 3


def test_vektoren_clustern_trifft_die_eingebauten_gruppen():
    vektoren, wahrheit = _gruppen_vektoren()
    gefunden = [sorted(gruppe) for gruppe in pc.vektoren_clustern(vektoren, 0.45, 3)]
    assert gefunden == [sorted(gruppe) for gruppe in wahrheit]


def test_vektoren_clustern_verwirft_das_rauschen():
    vektoren, _ = _gruppen_vektoren()
    rauschen = [_fern(seed) for seed in (9001, 9002, 9003, 9004)]
    alle = vektoren + rauschen
    gefunden = pc.vektoren_clustern(alle, 0.45, 3)
    drin = {index for gruppe in gefunden for index in gruppe}
    assert len(gefunden) == 3
    assert not (drin & {len(vektoren) + nummer for nummer in range(4)})


def test_vektoren_clustern_nur_rauschen_ergibt_nichts():
    assert pc.vektoren_clustern([_fern(seed) for seed in range(8)], 0.45, 3) == []


def test_vektoren_clustern_leerer_eingang_ist_leer():
    assert pc.vektoren_clustern([], 0.45, 3) == []


def test_vektoren_clustern_ist_deterministisch():
    vektoren, _ = _gruppen_vektoren()
    assert pc.vektoren_clustern(vektoren, 0.45, 3) == \
        pc.vektoren_clustern(vektoren, 0.45, 3)


def test_vektoren_clustern_gruppen_stehen_in_eingabereihenfolge():
    vektoren, wahrheit = _gruppen_vektoren()
    gefunden = pc.vektoren_clustern(vektoren, 0.45, 3)
    assert [gruppe[0] for gruppe in gefunden] == [gruppe[0] for gruppe in wahrheit]


def test_vektoren_clustern_identische_vektoren_sind_eine_gruppe():
    vektor = list(_basis(11))
    gefunden = pc.vektoren_clustern([vektor for _ in range(4)], 0.45, 3)
    assert gefunden == [[0, 1, 2, 3]]


def test_vektoren_clustern_zu_wenige_punkte_ergeben_nichts():
    assert pc.vektoren_clustern([list(_basis(11)), list(_basis(11))], 0.45, 3) == []


def test_vektoren_clustern_min_nachbarn_zwei_findet_paare():
    assert pc.vektoren_clustern([list(_basis(11)), list(_basis(11))], 0.45, 2) == \
        [[0, 1]]


def test_vektoren_clustern_gruppen_tragen_indizes():
    vektoren, _ = _gruppen_vektoren(anzahl_gruppen=1, je_gruppe=4)
    gruppe = pc.vektoren_clustern(vektoren, 0.45, 3)[0]
    assert all(isinstance(index, int) for index in gruppe)
    assert gruppe == sorted(gruppe)


def test_vektoren_clustern_nimmt_dicts_mit_embedding():
    basis = _basis(21)
    eintraege = [{"embedding": _nahe(basis, seed)} for seed in range(5)]
    assert pc.vektoren_clustern(eintraege, 0.45, 3) == [[0, 1, 2, 3, 4]]


def test_vektoren_clustern_verwirft_unbrauchbare_eintraege():
    basis = _basis(21)
    eintraege = [{"embedding": _nahe(basis, seed)} for seed in range(4)]
    eintraege.append({"ohne": "embedding"})
    assert pc.vektoren_clustern(eintraege, 0.45, 3) == [[0, 1, 2, 3]]


def test_vektoren_clustern_strenge_schwelle_trennt():
    basis = _basis(31)
    vektoren = [_nahe(basis, seed, streuung=0.9) for seed in range(6)]
    assert pc.vektoren_clustern(vektoren, 0.001, 3) == []


def test_vektoren_clustern_weite_schwelle_legt_zusammen():
    vektoren = [_fern(seed) for seed in range(4)]
    assert len(pc.vektoren_clustern(vektoren, 2.5, 3)) == 1


def test_vektoren_clustern_unbrauchbare_schwelle_faellt_auf_vorgabe():
    vektoren, _ = _gruppen_vektoren()
    assert len(pc.vektoren_clustern(vektoren, "streng", 3)) == 3


def test_vektoren_clustern_gruppenform_ist_liste_von_listen():
    vektoren, _ = _gruppen_vektoren()
    gefunden = pc.vektoren_clustern(vektoren, 0.45, 3)
    assert isinstance(gefunden, list)
    assert all(isinstance(gruppe, list) for gruppe in gefunden)


# ── 7b. Verfahren: vollstaendige Verknuepfung als Produktionsstandard ─────

# Die drei Punkte der Kette im 3-dim Unterraum: A-B 0.4, B-C 0.4, A-C 0.8.
# Das Dichte-Verfahren verschmilzt sie transitiv (Verkettung), die
# vollstaendige Verknuepfung nicht — der kleinste Fall des Auftrags.
def _vektor_kurz(werte) -> list[float]:
    """Ein 128er Vektor: nur die ersten Werte tragen, der Rest ist 0 (normiert)."""
    a = np.zeros(pc.MERKMAL_LAENGE)
    a[:len(werte)] = werte
    return (a / float(np.linalg.norm(a))).tolist()


KETTE_A = _vektor_kurz((1.0, 0.0, 0.0))
KETTE_B = _vektor_kurz((0.6, 0.8, 0.0))
KETTE_C = _vektor_kurz((0.2, 0.6, 0.7746))

# Die Schwellen-Stufen der Invarianten-Pruefung (10 bis 45 in 5er-Schritten).
SCHWELLEN_STUFEN = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45)


def _kette() -> list[list[float]]:
    """Die drei Punkte der Kette in Eingabereihenfolge."""
    return [list(KETTE_A), list(KETTE_B), list(KETTE_C)]


def _haufen(saat: int, je_haufen: int = 4, streuung: float = 0.03) -> list[list]:
    """Drei **dichte** Haufen entlang der Kette — der Bestandsfall.

    Je Haufen liegen die Gesichter nah (gleiche Person), zwischen den Haufen
    gilt der Kettenabstand 0.4 / 0.4 / 0.8. Das Dichte-Verfahren verschmilzt
    das zu einer Gruppe mit Durchmesser weit ueber der Schwelle — genau der
    Befund, der die Umstellung auf die vollstaendige Verknuepfung begruendet.
    """
    rng = np.random.default_rng(saat)
    eintraege: list[list] = []
    for basis in (KETTE_A, KETTE_B, KETTE_C):
        for _ in range(je_haufen):
            a = np.asarray(basis, dtype=float) \
                + streuung * rng.normal(size=pc.MERKMAL_LAENGE)
            eintraege.append((a / float(np.linalg.norm(a))).tolist())
    return eintraege


def _durchmesser_je_gruppe(gruppen, eintraege) -> list[float]:
    """Der Durchmesser jeder Gruppe — ueber ``cosinus_matrix`` nachgerechnet."""
    matrix = pc.cosinus_matrix(eintraege)
    assert matrix is not None, "Vorbedingung: die Matrix ist rechenbar"
    abstand = 1.0 - matrix
    return [max(float(abstand[i, j]) for i in gruppe for j in gruppe)
            for gruppe in gruppen]


def test_verfahrensnamen_sind_die_zwei():
    assert pc.VERFAHREN == ("dichte", "vollstaendig")
    assert pc.VERFAHREN_DICHTE == "dichte"
    assert pc.VERFAHREN_VOLLSTAENDIG == "vollstaendig"


def test_produktionsstandard_ist_die_vollstaendige_verknuepfung():
    assert pc.CLUSTER_VERFAHREN == pc.VERFAHREN_VOLLSTAENDIG


def test_standard_verknuepft_die_kette_nicht_mehr():
    """Ohne ``verfahren`` gilt der Standard: A und C kommen nur zusammen, wenn
    auch ihre eigene Distanz (0.8) unter der Schwelle liegt."""
    assert pc.vektoren_clustern(_kette(), 0.45, 1) == [[0, 1], [2]]
    assert pc.vektoren_clustern(_kette(), 0.45, 2) == [[0, 1]]


def test_standard_durchmesser_der_kette_unter_der_schwelle():
    gruppen = pc.vektoren_clustern(_kette(), 0.45, 1)
    for wert in _durchmesser_je_gruppe(gruppen, _kette()):
        assert wert <= 0.45 + 1e-9


def test_standard_reisst_den_durchmesser_beim_haufen_nicht():
    """Derselbe Haufen, den das Dichte-Verfahren zu einer Gruppe mit
    Durchmesser ueber 0.45 verschmilzt — der Standard reisst die Schwelle nicht."""
    eintraege = _haufen(1)
    dichte = pc.vektoren_clustern(eintraege, 0.45, 2, verfahren="dichte")
    assert len(dichte) == 1
    assert max(_durchmesser_je_gruppe(dichte, eintraege)) > 0.45
    gruppen = pc.vektoren_clustern(eintraege, 0.45, 2)
    assert len(gruppen) > 1
    for wert in _durchmesser_je_gruppe(gruppen, eintraege):
        assert wert <= 0.45 + 1e-9


def test_invariante_gilt_ueber_schwellen_und_saatgueter():
    """Durchmesser jeder Gruppe <= Schwelle — ueber viele Stufen und Saatgueter."""
    for saat in (1, 2, 3, 4, 5):
        for eintraege in (_haufen(saat), _kette()):
            for schwelle in SCHWELLEN_STUFEN:
                gruppen = pc.vektoren_clustern(eintraege, schwelle, 1)
                for wert in _durchmesser_je_gruppe(gruppen, eintraege):
                    assert wert <= schwelle + 1e-9, \
                        f"Durchmesser {wert} > Schwelle {schwelle} (Saatgut {saat})"


def test_dichte_verfahren_ist_explizit_erhalten():
    """Das Bestandsverfahren bleibt abrufbar — es verschmilzt die Kette."""
    gruppen = pc.vektoren_clustern(_kette(), 0.45, 1, verfahren="dichte")
    assert gruppen == [[0, 1, 2]]
    assert max(_durchmesser_je_gruppe(gruppen, _kette())) > 0.45
    assert pc.vektoren_clustern(_kette(), 0.45, 3, verfahren="dichte") == [[0, 1, 2]]


def test_vollstaendig_verwirft_gruppen_unter_der_mindestgroesse():
    """``min_nachbarn``/``min_groesse`` ist die Mindestgruppengroesse."""
    assert pc.vektoren_clustern(_kette(), 0.45, 1) == [[0, 1], [2]]
    assert pc.vektoren_clustern(_kette(), 0.45, 2) == [[0, 1]]
    assert pc.vektoren_clustern(_kette(), 0.45, 3) == []
    # Drei Haufen zu vier Gesichtern: mit Mindestgroesse 5 bleibt nichts uebrig.
    assert pc.vektoren_clustern(_haufen(1), 0.45, 5) == []


def test_unbekanntes_verfahren_ist_ein_klartextfehler():
    with pytest.raises(ValueError) as fehler:
        pc.vektoren_clustern(_kette(), 0.45, 1, verfahren="quatsch")
    text = str(fehler.value)
    assert "quatsch" in text
    assert "dichte" in text and "vollstaendig" in text


def test_unbekanntes_verfahren_kippt_auch_bei_leerem_eingang():
    with pytest.raises(ValueError):
        pc.vektoren_clustern([], 0.45, 1, verfahren="quatsch")


def test_standard_ist_deterministisch():
    eintraege = _haufen(3)
    assert pc.vektoren_clustern(eintraege, 0.45, 2) == \
        pc.vektoren_clustern(eintraege, 0.45, 2)


def test_vollstaendig_leerer_eingang_ist_leer():
    assert pc.vollstaendig_clustern([], 0.45, 2) == []
    assert pc.vollstaendig_clustern(None, 0.45, 2) == []
    assert pc.vektoren_clustern([], 0.45, 2) == []


def test_vollstaendig_ohne_brauchbare_vektoren_ist_leer():
    assert pc.vollstaendig_clustern([None, "Text", 7, {"ohne": "vektor"}],
                                    0.45, 1) == []
    assert pc.vollstaendig_clustern([list(KETTE_A)], 0.45, 2) == []
    assert pc.vektoren_clustern([None, "Text", 7], 0.45, 1) == []


# ── 7c. Delegation: eine Rechnung, zwei Werkzeuge ─────────────────────────

def test_verkettung_delegiert_die_vollstaendige_verknuepfung():
    """``personen_verkettung.vollstaendig_clustern`` liefert dieselben Gruppen."""
    for schwelle in (0.20, 0.30, 0.45):
        assert pv.vollstaendig_clustern(_haufen(2), schwelle, 2) == \
            pc.vollstaendig_clustern(_haufen(2), schwelle, 2)
    assert pv.vollstaendig_clustern(_kette(), 0.45, 2) == [[0, 1]]
    assert pv.vollstaendig_clustern(_kette(), 0.45, 1) == [[0, 1], [2]]
    assert pv.vollstaendig_clustern([], 0.45, 2) == []


def test_verkettung_reicht_durch_und_baut_die_rechnung_nicht_noch_einmal():
    quelle = VERKETTUNG_DATEI.read_text(encoding="utf-8")
    assert "_personen_cluster().vollstaendig_clustern(" in quelle
    assert "np.argmin" not in quelle, "die Verschmelzung darf dort nicht doppelt stehen"


def test_schwelle_misst_weiter_das_dichte_verfahren():
    """Das Messwerkzeug beschreibt den Bestand — nicht den neuen Standard."""
    quelle = SCHWELLE_DATEI.read_text(encoding="utf-8")
    assert 'verfahren="dichte"' in quelle
    messung = ps.schwelle_messen(_kette(), None, 0.45, 1)
    assert messung["gruppen"] == 1
    assert messung["groessen"] == [3]
    assert messung["kettenmass"]["durchmesser"]["max"] > 0.45


# ── 8. gruppen_kennungen ──────────────────────────────────────────────────

def test_gruppen_kennungen_vergeben_person_001():
    basis = _basis(41)
    kennungen = pc.gruppen_kennungen([[0, 1, 2]], [_nahe(basis, seed)
                                                  for seed in range(3)], [])
    assert kennungen[0]["kennung"] == "Person_001"


def test_gruppen_kennungen_markieren_neue_kennungen():
    basis = _basis(41)
    kennungen = pc.gruppen_kennungen([[0, 1, 2]], [_nahe(basis, seed)
                                                   for seed in range(3)], [])
    assert kennungen[0]["neu"] is True


def test_gruppen_kennungen_zaehlen_hoch():
    vektoren, gruppen = _gruppen_vektoren()
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    assert [eintrag["kennung"] for eintrag in kennungen] == \
        ["Person_001", "Person_002", "Person_003"]


def test_gruppen_kennungen_sind_idempotent():
    vektoren, gruppen = _gruppen_vektoren()
    erster = pc.gruppen_kennungen(gruppen, vektoren, [])
    zweiter = pc.gruppen_kennungen(gruppen, vektoren, erster)
    assert [eintrag["kennung"] for eintrag in zweiter] == \
        [eintrag["kennung"] for eintrag in erster]


def test_gruppen_kennungen_halten_die_kennung_bei_altbestand():
    vektoren, gruppen = _gruppen_vektoren()
    alt = pc.altbestand_bauen(pc.gruppen_kennungen(gruppen, vektoren, []))
    erneut = pc.gruppen_kennungen(gruppen, vektoren, alt)
    assert all(eintrag["neu"] is False for eintrag in erneut)


def test_gruppen_kennungen_neue_gruppe_bekommt_die_naechste_freie_nummer():
    vektoren, gruppen = _gruppen_vektoren(anzahl_gruppen=2, je_gruppe=4)
    alt = pc.altbestand_bauen(pc.gruppen_kennungen(gruppen, vektoren, []))
    neu = _nahe(_basis(999), seed=1)
    weitere = [neu for _ in range(4)]
    kennungen = pc.gruppen_kennungen([[0, 1, 2, 3]], weitere, alt)
    assert kennungen[0]["kennung"] == "Person_003"


def test_gruppen_kennungen_vergeben_verschwundene_kennung_nicht_neu():
    """``Person_002`` ist weg, ``Person_005`` da -> die naechste freie ist 006."""
    basis = _basis(51)
    alt = [{"kennung": "Person_001", "mittelpunkt": _fern(1)},
           {"kennung": "Person_002", "mittelpunkt": _fern(2)},
           {"kennung": "Person_005", "mittelpunkt": _fern(5)}]
    kennungen = pc.gruppen_kennungen([[0, 1, 2]],
                                     [_nahe(basis, seed) for seed in range(3)],
                                     alt)
    assert kennungen[0]["kennung"] == "Person_006"


def test_gruppen_kennungen_luecken_sind_erlaubt():
    alt = [{"kennung": "Person_004", "mittelpunkt": _fern(4)}]
    basis = _basis(52)
    kennungen = pc.gruppen_kennungen([[0, 1, 2]],
                                     [_nahe(basis, seed) for seed in range(3)],
                                     alt)
    assert kennungen[0]["kennung"] == "Person_005"


def test_gruppen_kennungen_behalten_die_alte_kennung_bei_treffer():
    basis = _basis(53)
    alt = [{"kennung": "Person_042", "mittelpunkt": list(basis)}]
    kennungen = pc.gruppen_kennungen([[0, 1, 2]],
                                     [_nahe(basis, seed) for seed in range(3)],
                                     alt)
    assert kennungen[0]["kennung"] == "Person_042"
    assert kennungen[0]["neu"] is False


def test_gruppen_kennungen_vergeben_eine_kennung_nur_einmal():
    basis = _basis(54)
    alt = [{"kennung": "Person_042", "mittelpunkt": list(basis)}]
    vektoren = [_nahe(basis, seed) for seed in range(6)]
    kennungen = pc.gruppen_kennungen([[0, 1, 2], [3, 4, 5]], vektoren, alt)
    assert kennungen[0]["kennung"] == "Person_042"
    assert kennungen[1]["kennung"] != "Person_042"


def test_gruppen_kennungen_schreiben_neue_auf_die_naechste_nummer():
    basis = _basis(55)
    alt = [{"kennung": "Person_042", "mittelpunkt": list(basis)}]
    vektoren = [_nahe(basis, seed) for seed in range(3)] + \
        [_nahe(_basis(56), seed) for seed in range(3)]
    kennungen = pc.gruppen_kennungen([[0, 1, 2], [3, 4, 5]], vektoren, alt)
    assert kennungen[1]["kennung"] == "Person_043"


def test_gruppen_kennungen_mittelpunkt_hat_merkmalslaenge():
    vektoren, gruppen = _gruppen_vektoren()
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    assert len(kennungen[0]["mittelpunkt"]) == pc.MERKMAL_LAENGE


def test_gruppen_kennungen_groesse_ist_die_gruppengroesse():
    vektoren, gruppen = _gruppen_vektoren(anzahl_gruppen=1, je_gruppe=7)
    assert pc.gruppen_kennungen(gruppen, vektoren, [])[0]["groesse"] == 7


def test_gruppen_kennungen_ohne_gruppen_sind_leer():
    assert pc.gruppen_kennungen([], [], []) == []


def test_gruppen_kennungen_leere_gruppe_wird_uebersprungen():
    basis = _basis(57)
    kennungen = pc.gruppen_kennungen([[], [0, 1, 2]],
                                     [_nahe(basis, seed) for seed in range(3)],
                                     [])
    assert len(kennungen) == 1
    assert kennungen[0]["kennung"] == "Person_001"


def test_gruppen_kennungen_unbrauchbare_indizes_ergeben_nichts():
    assert pc.gruppen_kennungen([[7, 8]], [list(_basis(1))], []) == []


def test_gruppen_kennungen_kennungsform_ist_person_drei_stellen():
    vektoren, gruppen = _gruppen_vektoren()
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    assert all(len(eintrag["kennung"]) == len("Person_001")
               for eintrag in kennungen)


def test_altbestand_bauen_und_lesen_ist_ein_kreis():
    vektoren, gruppen = _gruppen_vektoren()
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    alt = pc.altbestand_bauen(kennungen)
    assert len(pc.altbestand_lesen(alt)) == len(kennungen)


def test_altbestand_lesen_akzeptiert_die_huellform():
    alt = {"kennungen": [{"kennung": "Person_001", "mittelpunkt": _fern(1)}]}
    assert pc.altbestand_lesen(alt)[0]["kennung"] == "Person_001"


def test_altbestand_lesen_entdoppelt_kennungen():
    eintraege = [{"kennung": "Person_001", "mittelpunkt": _fern(1)},
                 {"kennung": "Person_001", "mittelpunkt": _fern(2)}]
    assert len(pc.altbestand_lesen(eintraege)) == 1


def test_altbestand_lesen_verwirft_unbrauchbare_eintraege():
    eintraege = [{"kennung": "Person_001"},
                 {"mittelpunkt": _fern(1)},
                 "kein Dict"]
    assert pc.altbestand_lesen(eintraege) == []


# ── 9. Referenzseiten ─────────────────────────────────────────────────────

def test_referenzseiten_bauen_schreibt_eine_datei(tmp_path):
    dateien = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=3),
                                      _holen_immer(), str(tmp_path))
    assert len(dateien) == 1
    assert Path(dateien[0]).is_file()


def test_referenzseiten_bauen_datei_hat_inhalt(tmp_path):
    dateien = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=3),
                                      _holen_immer(), str(tmp_path))
    assert Path(dateien[0]).stat().st_size > 0


def test_referenzseiten_bauen_dateiname_traegt_die_kennung(tmp_path):
    dateien = pc.referenzseiten_bauen(_gruppen_eintraege(("Person_007",)),
                                      _holen_immer(), str(tmp_path))
    assert Path(dateien[0]).name == "Person_007_seite_01.jpg"


def test_referenzseiten_bauen_seite_hat_die_kachelgroesse(tmp_path):
    daten = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=1),
                                    _holen_immer(), str(tmp_path),
                                    kachel_breite=50, kachel_hoehe=50, spalten=1)
    with Image.open(daten[0]) as seite:
        assert seite.width == 50
        assert seite.height == 50 + pc.BESCHRIFTUNG_HOEHE


def test_referenzseiten_bauen_beschriftung_ist_im_bild(tmp_path):
    """Die Beschriftung braucht Platz — die Seite ist hoeher als die Kachel."""
    daten = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=1),
                                    _holen_immer(), str(tmp_path),
                                    kachel_breite=40, kachel_hoehe=40, spalten=1)
    with Image.open(daten[0]) as seite:
        assert seite.height > 40


def test_referenzseiten_bauen_acht_kacheln_je_seite_standard(tmp_path):
    daten = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=20),
                                    _holen_immer(), str(tmp_path))
    assert len(daten) == 3                      # 8 + 8 + 4
    assert pc.KACHELN_JE_SEITE == 8


def test_referenzseiten_bauen_kacheln_je_seite_ist_einstellbar(tmp_path):
    daten = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=4),
                                    _holen_immer(), str(tmp_path),
                                    kacheln_je_seite=2)
    assert len(daten) == 2


def test_referenzseiten_bauen_zweiter_lauf_ueberspringt(tmp_path):
    gruppen = _gruppen_eintraege(je_gruppe=3)
    pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path))
    assert pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path)) == []


def test_referenzseiten_bauen_erneut_schreibt_wieder(tmp_path):
    gruppen = _gruppen_eintraege(je_gruppe=3)
    pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path))
    erneut = pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path),
                                     erneut=True)
    assert len(erneut) == 1


def test_referenzseiten_bauen_ohne_kachelquelle_platzhalter(tmp_path):
    dateien = pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=2), None,
                                      str(tmp_path))
    assert len(dateien) == 1
    assert Path(dateien[0]).stat().st_size > 0


def test_referenzseiten_bauen_kachel_holen_none_kein_absturz(tmp_path):
    def holen(_eintrag):
        return None

    assert len(pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=2), holen,
                                       str(tmp_path))) == 1


def test_referenzseiten_bauen_kachel_holen_wirft_kein_absturz(tmp_path):
    def holen(_eintrag):
        raise RuntimeError("kaputte Kachel")

    assert len(pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=2), holen,
                                       str(tmp_path))) == 1


def test_referenzseiten_bauen_kaputte_bytes_ergeben_platzhalter(tmp_path):
    assert len(pc.referenzseiten_bauen(_gruppen_eintraege(je_gruppe=2),
                                       _holen_immer(b"kein Bild"),
                                       str(tmp_path))) == 1


def test_referenzseiten_bauen_ohne_gruppen_schreibt_nichts(tmp_path):
    assert pc.referenzseiten_bauen([], _holen_immer(), str(tmp_path)) == []


def test_referenzseiten_bauen_ohne_kennung_wird_uebersprungen(tmp_path):
    gruppen = [{"kennung": "", "eintraege": [{"anteil": 0.02, "score": 0.9}]}]
    assert pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path)) == []


def test_referenzseiten_bauen_ohne_ausgabeordner_ist_klartextfehler():
    with pytest.raises(pc.PersonenFehler) as fehler:
        pc.referenzseiten_bauen(_gruppen_eintraege(), _holen_immer(), None)
    assert "Ausgabeordner" in str(fehler.value)


def test_referenzseiten_bauen_im_repo_wird_abgelehnt():
    ziel = REPO / "personen_probe_probe"
    with pytest.raises(SystemExit):
        pc.referenzseiten_bauen(_gruppen_eintraege(), _holen_immer(), str(ziel))


def test_referenzseiten_planen_nennt_die_dateien(tmp_path):
    geplant = pc.referenzseiten_planen(_gruppen_eintraege(je_gruppe=3),
                                      str(tmp_path))
    assert len(geplant) == 1
    assert geplant[0].endswith("Person_001_seite_01.jpg")


def test_referenzseiten_planen_schreibt_nichts(tmp_path):
    pc.referenzseiten_planen(_gruppen_eintraege(je_gruppe=3), str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_referenzseiten_planen_ueberspringt_vorhandenes(tmp_path):
    gruppen = _gruppen_eintraege(je_gruppe=3)
    pc.referenzseiten_bauen(gruppen, _holen_immer(), str(tmp_path))
    assert pc.referenzseiten_planen(gruppen, str(tmp_path)) == []


def test_seiten_dateiname_ist_fest():
    assert pc.seiten_dateiname("Person_012", 2) == "Person_012_seite_02.jpg"


def test_kacheln_sortieren_groesster_anteil_zuerst():
    eintraege = [{"anteil": 0.01, "score": 0.9, "bild_id": "1"},
                 {"anteil": 0.05, "score": 0.5, "bild_id": "2"}]
    assert pc.kacheln_sortieren(eintraege)[0]["bild_id"] == "2"


def test_kacheln_sortieren_score_entscheidet_bei_gleicher_flaeche():
    eintraege = [{"anteil": 0.05, "score": 0.6, "bild_id": "1"},
                 {"anteil": 0.05, "score": 0.9, "bild_id": "2"}]
    assert pc.kacheln_sortieren(eintraege)[0]["bild_id"] == "2"


# ── 10. Eingabe lesen (JSONL und Katalog) ─────────────────────────────────

def test_zeile_pruefen_nimmt_eine_gueltige_zeile():
    zeile = _bild(gesichter=[_gesicht([0.0, 0.0, 300.0, 300.0],
                                      embedding=_fern(1))])
    assert pc.zeile_pruefen(zeile)["bild_id"] == BILD_A


def test_zeile_pruefen_ohne_gesichter_ist_gueltig():
    assert pc.zeile_pruefen(_bild(gesichter=[]))["gesichter"] == []


def test_zeile_pruefen_falsche_merkmalslaenge_ist_ungueltig():
    zeile = _bild(gesichter=[{"bbox": [0.0, 0.0, 10.0, 10.0], "score": 0.9,
                              "embedding": [0.1, 0.2]}])
    assert pc.zeile_pruefen(zeile) is None


def test_zeile_pruefen_ohne_bild_id_ist_ungueltig():
    zeile = _bild(gesichter=[])
    zeile.pop("bild_id")
    assert pc.zeile_pruefen(zeile) is None


def test_zeile_pruefen_ohne_masse_ist_ungueltig():
    zeile = _bild(gesichter=[])
    zeile.pop("hoehe")
    assert pc.zeile_pruefen(zeile) is None


def test_zeile_pruefen_mit_nullmasse_ist_ungueltig():
    assert pc.zeile_pruefen(_bild(gesichter=[], breite=0, hoehe=0)) is None


def test_zeile_pruefen_mit_kaputter_bbox_ist_ungueltig():
    zeile = _bild(gesichter=[{"bbox": [0.0, 0.0, 0.0, 10.0], "score": 0.9,
                              "embedding": _fern(1)}])
    assert pc.zeile_pruefen(zeile) is None


def test_zeile_pruefen_mit_fehlendem_score_ist_ungueltig():
    zeile = _bild(gesichter=[{"bbox": [0.0, 0.0, 10.0, 10.0],
                              "embedding": _fern(1)}])
    assert pc.zeile_pruefen(zeile) is None


def test_zeilen_lesen_liest_gueltige_zeilen(tmp_path):
    pfad = _vektoren_schreiben(tmp_path / "v.jsonl",
                               [_bild(), _bild(bild_id=BILD_B)])
    assert len(pc.zeilen_lesen(pfad)["bilder"]) == 2


def test_zeilen_lesen_zaehlt_kaputte_zeilen(tmp_path):
    pfad = tmp_path / "v.jsonl"
    pfad.write_text('{"bild_id": "1"}\nkein json\n', encoding="utf-8")
    gelesen = pc.zeilen_lesen(str(pfad))
    assert gelesen["ungueltige_zeilen"] == 2
    assert gelesen["bilder"] == []


def test_zeilen_lesen_bricht_bei_kaputter_zeile_nicht_ab(tmp_path):
    pfad = _vektoren_schreiben(tmp_path / "v.jsonl", [_bild()])
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write("{kaputt\n")
        datei.write(json.dumps(_bild(bild_id=BILD_B)) + "\n")
    gelesen = pc.zeilen_lesen(pfad)
    assert len(gelesen["bilder"]) == 2
    assert gelesen["ungueltige_zeilen"] == 1


def test_zeilen_lesen_zaehlt_alle_zeilen(tmp_path):
    pfad = _vektoren_schreiben(tmp_path / "v.jsonl", [_bild(), _bild(bild_id=BILD_B)])
    assert pc.zeilen_lesen(pfad)["zeilen_gesamt"] == 2


def test_zeilen_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(pc.PersonenFehler) as fehler:
        pc.zeilen_lesen(str(tmp_path / "gibtsnicht.jsonl"))
    assert "nicht gefunden" in str(fehler.value)


def test_zeilen_lesen_ohne_pfad_ist_klartextfehler():
    with pytest.raises(pc.PersonenFehler):
        pc.zeilen_lesen("")


def test_katalog_lesen_liest_personen(tmp_path):
    pfad = tmp_path / "katalog.json"
    pfad.write_text(json.dumps(_katalog(("Person_001", _fern(1)))),
                    encoding="utf-8")
    assert len(pc.katalog_lesen(str(pfad))["personen"]) == 1


def test_katalog_lesen_vertraegt_eine_liste(tmp_path):
    pfad = tmp_path / "katalog.json"
    pfad.write_text(json.dumps([{"kennung": "Person_001",
                                 "vektoren": [_fern(1)]}]), encoding="utf-8")
    assert len(pc.katalog_lesen(str(pfad))["personen"]) == 1


def test_katalog_lesen_fehlende_datei_ist_klartextfehler(tmp_path):
    with pytest.raises(pc.PersonenFehler):
        pc.katalog_lesen(str(tmp_path / "fehlt.json"))


def test_katalog_lesen_kaputtes_json_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "katalog.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(pc.PersonenFehler):
        pc.katalog_lesen(str(pfad))


def test_altbestand_lesen_datei_fehlend_ist_leer(tmp_path):
    assert pc.altbestand_lesen_datei(str(tmp_path / "keins.json")) == []


def test_altbestand_lesen_datei_liest_den_bestand(tmp_path):
    pfad = tmp_path / "kennungen.json"
    pfad.write_text(json.dumps({"kennungen": [{"kennung": "Person_001",
                                               "mittelpunkt": _fern(1)}]}),
                    encoding="utf-8")
    assert pc.altbestand_lesen_datei(str(pfad))[0]["kennung"] == "Person_001"


def test_altbestand_lesen_datei_kaputt_ist_klartextfehler(tmp_path):
    pfad = tmp_path / "kennungen.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(pc.PersonenFehler):
        pc.altbestand_lesen_datei(str(pfad))


# ── 11. Bericht ───────────────────────────────────────────────────────────

def test_bericht_bauen_zaehlt_die_bilder():
    entscheidungen = [pc.bild_entscheidung(_bild(gesichter=[_gross()])),
                      pc.bild_entscheidung(_bild(gesichter=[]))]
    assert pc.bericht_bauen(entscheidungen)["bilder_gelesen"] == 2


def test_bericht_bauen_zaehlt_je_art():
    entscheidungen = [pc.bild_entscheidung(_bild(gesichter=[_gross()])),
                      pc.bild_entscheidung(_bild(gesichter=[])),
                      pc.bild_entscheidung(_bild(gesichter=_klein(40))),
                      pc.bild_entscheidung(_bild(gesichter=_klein(3)))]
    je_art = pc.bericht_bauen(entscheidungen)["je_art"]
    assert je_art == {"leer": 1, "gruppe": 1, "menge": 1, "unklar": 1}


def test_bericht_bauen_zaehlt_geclusterte_bilder():
    entscheidungen = [pc.bild_entscheidung(_bild(gesichter=[_gross()])),
                      pc.bild_entscheidung(_bild(gesichter=_klein(40)))]
    assert pc.bericht_bauen(entscheidungen)["geclusterte_bilder"] == 1


def test_bericht_bauen_nennt_gruppen_und_groessen():
    vektoren, gruppen = _gruppen_vektoren(anzahl_gruppen=2, je_gruppe=4)
    bericht = pc.bericht_bauen([], gruppen=gruppen)
    assert bericht["gruppen"] == 2
    assert bericht["gruppen_groessen"] == [4, 4]


def test_bericht_bauen_zaehlt_neu_und_wiederverwendet():
    vektoren, gruppen = _gruppen_vektoren()
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    kennungen[0]["neu"] = False
    bericht = pc.bericht_bauen([], kennungen=kennungen)
    assert bericht["kennungen_neu"] == 2
    assert bericht["kennungen_wiederverwendet"] == 1


def test_bericht_bauen_zaehlt_bilder_mit_bekannter_person():
    katalog = _katalog(("Person_007", _fern(4242)))
    entscheidungen = [
        pc.bild_entscheidung(_bild(gesichter=_klein(40) + [_gross(embedding=_fern(4242))]),
                             katalog),
        pc.bild_entscheidung(_bild(bild_id=BILD_B, gesichter=_klein(40)), katalog)]
    assert pc.bericht_bauen(entscheidungen)["bilder_mit_bekannter_person"] == 1


def test_bericht_bauen_zaehlt_kacheln():
    assert pc.bericht_bauen([], kacheln=["a", "b"])["kacheln_geschrieben"] == 2


def test_bericht_bauen_zaehlt_ungueltige_zeilen():
    bericht = pc.bericht_bauen([], ungueltige_zeilen=3)
    assert bericht["ungueltige_zeilen"] == 3
    assert bericht["zeilen_gesamt"] == 3


def test_bericht_bauen_hat_alle_vier_arten_auch_bei_null():
    assert pc.bericht_bauen([])["je_art"] == {"leer": 0, "gruppe": 0,
                                              "menge": 0, "unklar": 0}


def test_bericht_bauen_zaehlt_die_gruende():
    entscheidungen = [pc.bild_entscheidung(_bild(gesichter=_klein(40)))]
    assert pc.bericht_bauen(entscheidungen)["je_grund"] == \
        {"menge_ohne_bekannte_person": 1}


def test_bericht_bauen_ohne_dateizugriff(monkeypatch):
    def verboten(*_args, **_kwargs):
        raise AssertionError("bericht_bauen hat eine Datei angefasst!")

    monkeypatch.setattr("builtins.open", verboten)
    assert pc.bericht_bauen([])["bilder_gelesen"] == 0


def test_bericht_bauen_ist_deterministisch():
    entscheidungen = [pc.bild_entscheidung(_bild(gesichter=[_gross()]))]
    erster = pc.bericht_bauen(entscheidungen)
    zweiter = pc.bericht_bauen(entscheidungen)
    assert erster["je_art"] == zweiter["je_art"]


def test_bericht_text_nennt_die_zahlen():
    text = pc.bericht_text(pc.bericht_bauen([], ungueltige_zeilen=2,
                                            gruppen=[[0, 1]],
                                            kacheln=["a"]))
    assert "Bilder gelesen:" in text
    assert "ungueltige Zeilen: 2" in text
    assert "Gruppen: 1" in text
    assert "Kacheln geschrieben: 1" in text


def test_bericht_text_nennt_die_arten():
    text = pc.bericht_text(pc.bericht_bauen([]))
    for art in pc.ARTEN:
        assert art in text


# ── 12. Der ganze Lauf (rein) ─────────────────────────────────────────────

def test_lauf_rechnen_entscheidet_je_bild():
    bilder = [_bild(), _bild(bild_id=BILD_B, gesichter=[_gross()])]
    lauf = pc.lauf_rechnen(bilder)
    assert [eintrag["art"] for eintrag in lauf["entscheidungen"]] == \
        ["leer", "gruppe"]


def test_lauf_rechnen_sammelt_nur_freigegebene_gesichter():
    bilder = [_bild(gesichter=_klein(40)),
              _bild(bild_id=BILD_B, gesichter=[_gross()])]
    lauf = pc.lauf_rechnen(bilder)
    assert len(lauf["eintraege"]) == 1
    assert lauf["eintraege"][0]["bild_id"] == BILD_B


def test_lauf_rechnen_bildet_gruppen_und_kennungen():
    basis = _basis(61)
    bilder = [_bild(bild_id=f"90000{nummer}",
                    gesichter=[_gesicht([0.0, 0.0, 300.0, 300.0],
                                        embedding=_nahe(basis, nummer))])
              for nummer in range(4)]
    lauf = pc.lauf_rechnen(bilder)
    assert len(lauf["gruppen"]) == 1
    assert lauf["kennungen"][0]["kennung"] == "Person_001"


def test_lauf_rechnen_massenfoto_bleibt_draussen():
    lauf = pc.lauf_rechnen([_bild(gesichter=_klein(40))])
    assert lauf["gruppen"] == []
    assert lauf["eintraege"] == []


def test_lauf_rechnen_gibt_die_gruppen_eintraege_mit():
    basis = _basis(62)
    bilder = [_bild(bild_id=f"90001{nummer}",
                    gesichter=[_gesicht([0.0, 0.0, 300.0, 300.0],
                                        embedding=_nahe(basis, nummer))])
              for nummer in range(4)]
    lauf = pc.lauf_rechnen(bilder)
    assert lauf["gruppen_eintraege"][0]["kennung"] == "Person_001"
    assert len(lauf["gruppen_eintraege"][0]["eintraege"]) == 4


def test_lauf_rechnen_ohne_bilder_ist_leer():
    lauf = pc.lauf_rechnen([])
    assert lauf["gruppen"] == []
    assert lauf["bericht"]["bilder_gelesen"] == 0


def test_lauf_rechnen_nutzt_den_altbestand():
    basis = _basis(63)
    alt = [{"kennung": "Person_099", "mittelpunkt": list(basis)}]
    bilder = [_bild(bild_id=f"90002{nummer}",
                    gesichter=[_gesicht([0.0, 0.0, 300.0, 300.0],
                                        embedding=_nahe(basis, nummer))])
              for nummer in range(4)]
    lauf = pc.lauf_rechnen(bilder, altbestand=alt)
    assert lauf["kennungen"][0]["kennung"] == "Person_099"


# ── 13. Kommandozeile ─────────────────────────────────────────────────────

def _lauf(tmp_path, bilder, zusatz=(), katalog=None):
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl", bilder)
    argv = ["--vektoren", vektoren, "--ausgabe", str(tmp_path / "ausgabe")]
    if katalog is not None:
        pfad = tmp_path / "katalog.json"
        pfad.write_text(json.dumps(katalog), encoding="utf-8")
        argv += ["--katalog", str(pfad)]
    return pc.main(argv + list(zusatz))


def _gruppen_bilder(anzahl=4, basis_seed=71, bbox=(0.0, 0.0, 300.0, 300.0)):
    basis = _basis(basis_seed)
    return [_bild(bild_id=f"80000{nummer}",
                  gesichter=[_gesicht(list(bbox), embedding=_nahe(basis, nummer))])
            for nummer in range(anzahl)]


def test_main_laeuft_ohne_schreiben_durch(tmp_path):
    assert _lauf(tmp_path, _gruppen_bilder()) == 0


def test_main_schreibt_standardmaessig_nichts(tmp_path):
    _lauf(tmp_path, _gruppen_bilder())
    assert not (tmp_path / "ausgabe").exists()


def test_main_sagt_dass_nichts_geschrieben_wurde(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder())
    assert "NICHTS geschrieben" in capsys.readouterr().out


def test_main_zeigt_die_berichtszahlen(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder())
    ausgabe = capsys.readouterr().out
    assert "Bilder gelesen:" in ausgabe
    assert "Gruppen:" in ausgabe


def test_main_zeigt_die_kennungen(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder())
    assert "Person_001" in capsys.readouterr().out


def test_main_zeigt_die_geplanten_dateien(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder())
    ausgabe = capsys.readouterr().out
    assert "Person_001_seite_01.jpg" in ausgabe
    assert "Geplante Referenzseiten" in ausgabe


def test_main_mit_schreiben_legt_die_seite_an(tmp_path):
    assert _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"]) == 0
    assert (tmp_path / "ausgabe" / "Person_001_seite_01.jpg").is_file()


def test_main_mit_schreiben_legt_die_kennungen_an(tmp_path):
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"])
    pfad = tmp_path / "ausgabe" / pc.KENNUNGEN_DATEI
    assert pfad.is_file()
    assert json.loads(pfad.read_text(encoding="utf-8"))["kennungen"][0]["kennung"] \
        == "Person_001"


def test_main_zweiter_lauf_haelt_die_kennung(tmp_path):
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"])
    assert _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"]) == 0
    pfad = tmp_path / "ausgabe" / pc.KENNUNGEN_DATEI
    kennungen = json.loads(pfad.read_text(encoding="utf-8"))["kennungen"]
    assert [eintrag["kennung"] for eintrag in kennungen] == ["Person_001"]


def test_main_zweiter_lauf_schreibt_die_seite_nicht_neu(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"])
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"])
    assert "Referenzseiten geschrieben: 0" in capsys.readouterr().out


def test_main_erneut_schreibt_die_seite_wieder(tmp_path, capsys):
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben"])
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben", "--erneut"])
    assert "Referenzseiten geschrieben: 1" in capsys.readouterr().out


def test_main_trocken_hat_vorrang_vor_schreiben(tmp_path):
    _lauf(tmp_path, _gruppen_bilder(), ["--schreiben", "--trocken"])
    assert not (tmp_path / "ausgabe").exists()


def test_main_massenfoto_wird_nicht_geclustert(tmp_path, capsys):
    _lauf(tmp_path, [_bild(gesichter=_klein(40))], ["--schreiben"])
    ausgabe = capsys.readouterr().out
    assert "menge: 1" in ausgabe
    assert not (tmp_path / "ausgabe" / "Person_001_seite_01.jpg").exists()


def test_main_massenfoto_mit_bekannter_person_wird_geclustert(tmp_path):
    """Die bekannte Person im Vordergrund gibt die Bilder zum Clustern frei."""
    katalog = _katalog(("Person_007", _fern(4242)))
    bilder = [_bild(bild_id=f"70000{nummer}",
                    gesichter=_klein(40) + [_gross(embedding=_fern(4242))])
              for nummer in range(3)]
    _lauf(tmp_path, bilder, ["--schreiben"], katalog=katalog)
    assert (tmp_path / "ausgabe" / "Person_001_seite_01.jpg").is_file()


def test_main_massenfoto_mit_bekannter_person_zaehlt_sie(tmp_path, capsys):
    katalog = _katalog(("Person_007", _fern(4242)))
    bild = _bild(gesichter=_klein(40) + [_gross(embedding=_fern(4242))])
    _lauf(tmp_path, [bild], katalog=katalog)
    assert "mit bekannter Person: 1" in capsys.readouterr().out


def test_main_massenfoto_ohne_bekannte_person_zaehlt_null(tmp_path, capsys):
    _lauf(tmp_path, [_bild(gesichter=_klein(40))], katalog={})
    assert "mit bekannter Person: 0" in capsys.readouterr().out


def test_main_katalogname_wird_nie_ausgegeben(tmp_path, capsys):
    """Ein Name aus dem Katalog darf gelesen, aber nie gezeigt werden.

    Belegt ueber die Ausgabe selbst: derselbe Lauf mit und ohne Namen im
    Katalog ergibt **dieselbe** Konsolenausgabe — der Name kann also in keiner
    Zeile stehen.
    """
    basis = _basis(72)
    vektoren = _vektoren_schreiben(
        tmp_path / "v.jsonl",
        [_bild(gesichter=[_gross(embedding=_nahe(basis, 1))])])
    ohne_pfad = tmp_path / "katalog_ohne.json"
    ohne_pfad.write_text(json.dumps({"personen": [{"kennung": "Person_007",
                                                   "name": None,
                                                   "vektoren": [list(basis)]}]}),
                         encoding="utf-8")
    mit_pfad = tmp_path / "katalog_mit.json"
    mit_pfad.write_text(json.dumps({"personen": [{"kennung": "Person_007",
                                                  "name": "Person_007",
                                                  "vektoren": [list(basis)]}]}),
                        encoding="utf-8")

    def lauf(katalog_pfad):
        return pc.main(["--vektoren", vektoren,
                        "--ausgabe", str(tmp_path / "ausgabe"),
                        "--katalog", str(katalog_pfad)])

    assert lauf(ohne_pfad) == 0
    ohne = capsys.readouterr().out
    assert lauf(mit_pfad) == 0
    mit = capsys.readouterr().out
    assert "mit bekannter Person: 1" in mit
    assert ohne == mit


def test_main_erlaubt_das_aendern_der_schwelle(tmp_path):
    assert _lauf(tmp_path, _gruppen_bilder(), ["--schwelle", "0.9"]) == 0


def test_main_erlaubt_min_nachbarn(tmp_path):
    assert _lauf(tmp_path, _gruppen_bilder(), ["--min-nachbarn", "2"]) == 0


def test_main_meldet_fehlende_vektordatei(tmp_path, capsys):
    assert pc.main(["--vektoren", str(tmp_path / "gibtsnicht.jsonl"),
                    "--ausgabe", str(tmp_path / "ausgabe")]) == 2
    assert "Fehler" in capsys.readouterr().out


def test_main_zaehlt_kaputte_zeilen(tmp_path, capsys):
    pfad = tmp_path / "v.jsonl"
    pfad.write_text("kein json\n", encoding="utf-8")
    pc.main(["--vektoren", str(pfad), "--ausgabe", str(tmp_path / "ausgabe")])
    assert "ungueltige Zeilen: 1" in capsys.readouterr().out


def test_main_ausgabe_im_repo_wird_abgelehnt(tmp_path):
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl", _gruppen_bilder())
    with pytest.raises(SystemExit):
        pc.main(["--vektoren", vektoren, "--ausgabe", str(REPO / "probe")])


def test_main_ausgabe_im_repo_wird_abgelehnt_mit_meldung(tmp_path, capsys):
    vektoren = _vektoren_schreiben(tmp_path / "v.jsonl", _gruppen_bilder())
    with pytest.raises(SystemExit):
        pc.main(["--vektoren", vektoren, "--ausgabe", str(REPO / "probe")])
    assert "IM Repo" in capsys.readouterr().out


def test_prufe_ausserhalb_repo_laesst_tmp_zu(tmp_path):
    assert pc.pruefe_ausserhalb_repo(str(tmp_path)) == str(tmp_path)


# ── 14. Schutz: Quelltext und Verbote ────────────────────────────────────

def test_quelltext_hat_keine_loeschfunktion():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("deletefile", "deletefolder", "os.remove", "os.unlink",
                     "shutil.rmtree"):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_hat_keinen_pcloud_aufruf():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("requests", "httpx", "e.pcloud"):
        assert verboten not in quelle, f"pCloud-Aufruf im Quelltext: {verboten}"


def test_quelltext_print_zeigt_keine_vektorwerte():
    """Keine ``print``-Zeile darf Vektoren/Mittelpunkte ausgeben.

    Verboten sind die Namen der Wertfelder, nicht das Wort "Vektordatei" (das
    ist die Bezeichnung der Eingabedatei und nennt nur ihren Pfad).
    """
    zeilen = WERKZEUG.read_text(encoding="utf-8").splitlines()
    for nummer, zeile in enumerate(zeilen, start=1):
        if "print(" not in zeile:
            continue
        for verboten in ("embedding", "mittelpunkt", ".tolist()", "merkmale",
                         "bbox", "token", "np."):
            assert verboten not in zeile.lower(), \
                f"Zeile {nummer} gibt '{verboten}' aus: {zeile}"
    gerufen = [zeile for zeile in zeilen if "print(" in zeile]
    assert gerufen, "Vorbedingung: das Modul gibt etwas aus"


def test_quelltext_hat_die_vorgabefunktionen():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for name in VORGABE_FUNKTIONEN:
        assert f"def {name}(" in quelle, f"Vorgabefunktion fehlt: {name}"


def test_quelltext_hat_alle_schwellen_im_modul():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for name in ("MIN_SCORE", "ANTEIL_MIN", "ANTEIL_ERKENNBAR", "MENGE_ANZAHL",
                 "KATALOG_SCHWELLE", "MENGEN_PARAMS", "CLUSTER_SCHWELLE",
                 "CLUSTER_MIN_NACHBAR"):
        assert name in quelle, f"Schwelle fehlt: {name}"


def test_quelltext_ist_python_lesbar():
    assert isinstance(pc.STANDARD_BASIS, str)
    assert pc.REPO == str(REPO)


def test_modul_anhaengt_keine_datei_an_das_manifest():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert "manifest" not in quelle.lower()


def test_pruefe_ausserhalb_repo_lehnt_repo_ab():
    with pytest.raises(SystemExit):
        pc.pruefe_ausserhalb_repo(str(REPO / "irgendwas"))


def test_pruefe_ausserhalb_repo_leerer_pfad_ist_klartextfehler():
    with pytest.raises(pc.PersonenFehler):
        pc.pruefe_ausserhalb_repo("")


def test_kennungen_schreiben_im_repo_wird_abgelehnt():
    with pytest.raises(SystemExit):
        pc.kennungen_schreiben(str(REPO / "kennungen_probe.json"), [])


def test_kennungen_schreiben_und_lesen_ist_ein_kreis(tmp_path):
    vektoren, gruppen = _gruppen_vektoren(anzahl_gruppen=1, je_gruppe=4)
    kennungen = pc.gruppen_kennungen(gruppen, vektoren, [])
    pfad = tmp_path / "kennungen.json"
    pc.kennungen_schreiben(str(pfad), kennungen)
    assert pc.altbestand_lesen_datei(str(pfad))[0]["kennung"] == "Person_001"


def test_cosinus_identischer_vektoren_ist_eins():
    vektor = list(_basis(81))
    assert pc.cosinus(vektor, vektor) == pytest.approx(1.0, abs=1e-9)


def test_cosinus_unbrauchbarer_eingabe_ist_null():
    assert pc.cosinus(None, [1.0, 2.0]) == 0.0


def test_cosinus_ungleicher_laenge_ist_null():
    assert pc.cosinus([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_cosinus_distanz_identischer_vektoren_ist_null():
    vektor = list(_basis(82))
    assert pc.cosinus_distanz(vektor, vektor) == pytest.approx(0.0, abs=1e-9)


def test_geclusterte_eintraege_ueberspringt_nicht_geclustert():
    bilder = [_bild(gesichter=[_gross()]), _bild(bild_id=BILD_B,
                                                 gesichter=_klein(40))]
    entscheidungen = [pc.bild_entscheidung(bild) for bild in bilder]
    eintraege = pc.geclusterte_eintraege(bilder, entscheidungen)
    assert len(eintraege) == 1
    assert eintraege[0]["bild_id"] == BILD_A


def test_geclusterte_eintraege_tragen_anteil_und_embedding():
    bilder = [_bild(gesichter=[_gross()])]
    entscheidungen = [pc.bild_entscheidung(bilder[0])]
    eintrag = pc.geclusterte_eintraege(bilder, entscheidungen)[0]
    assert eintrag["anteil"] > 0
    assert len(eintrag["embedding"]) == pc.MERKMAL_LAENGE


def test_gruppen_eintraege_bauen_ordnet_ueber_die_gruppennummer():
    gruppen = [[0, 1], [2, 3]]
    eintraege = [{"bild_id": f"10000{nummer}"} for nummer in range(4)]
    kennungen = [{"kennung": "Person_001", "gruppe": 0},
                 {"kennung": "Person_002", "gruppe": 1}]
    gebaut = pc.gruppen_eintraege_bauen(gruppen, eintraege, kennungen)
    assert [eintrag["kennung"] for eintrag in gebaut] == ["Person_001",
                                                          "Person_002"]
    assert len(gebaut[1]["eintraege"]) == 2
