"""Pruefungen fuer ``personen_verkettung.py`` (Nachtlauf-Schritt N9f).

Alles OHNE Netz und OHNE echte Daten: kein Download, kein Bild aus dem Bestand,
keine echten Ordner- oder Personennamen. Die Vektoren sind **synthetisch** und
deterministisch aus einem Saatgut erzeugt (``numpy.random.default_rng``),
Dateien gehen nach ``tmp_path``.

Der Kern der Pruefung ist das **Ketten-Beispiel** des Auftrags: A-B 0.4,
B-C 0.4, A-C 0.8. Das Dichte-Verfahren (N9a) verschmilzt bei 0.45 alle drei
(transitiv), die vollstaendige Verknuepfung trennt A und C — ihr Durchmesser
bleibt garantiert unter der Schwelle.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_personen_verkettung.py -q
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "personen_verkettung.py"
N9A = REPO / "tools" / "foto_sortierung" / "personen_cluster.py"
N9E = REPO / "tools" / "foto_sortierung" / "personen_schwelle.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pk = _laden(WERKZEUG, "personen_verkettung")
pc = _laden(N9A, "personen_cluster")
ps = _laden(N9E, "personen_schwelle")

# Die Pflichtfunktionen (Namen sind Vorgabe des Auftrags).
VORGABE_FUNKTIONEN = (
    "vollstaendig_clustern", "mittelpunkt_clustern", "verfahren_messen",
    "vergleich_bericht", "bericht_text", "main",
    # Stuetzen, die die Messung tragen
    "gruppen_bilden", "gueltige_indizes", "bezugslaenge", "abstand_vektoren",
    "zahlen_je_gruppe", "pruefe_ausserhalb_repo", "bericht_schreiben",
)

# Die Schwellen des Auftrags.
SCHWELLEN = (0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10)

# Merkmalslaenge wie bei SFace — synthetische Vektoren, echte Dimension.
LAENGE = 128

# Ein 12-MP-Handyfoto — die Bezugsflaeche der Gesichts-Masse.
BREITE, HOEHE = 4032, 3024


# ── Synthetische Vektoren (deterministisch, offline) ──────────────────────

def _vektor(werte, laenge: int = LAENGE) -> list:
    """Ein normierter Vektor: die ersten Werte tragen, der Rest ist 0."""
    a = np.zeros(laenge)
    a[:len(werte)] = werte
    return (a / float(np.linalg.norm(a))).tolist()


def _nah(vektor, saat: int, streuung: float = 0.02) -> list:
    """Ein Vektor DICHT an ``vektor`` — dieselbe Person, ein anderes Foto."""
    rauschen = np.random.default_rng(saat).normal(size=len(vektor))
    a = np.asarray(vektor, dtype=float) + streuung * rauschen
    return (a / float(np.linalg.norm(a))).tolist()


def _fern(saat: int) -> list:
    """Ein Vektor ohne Bezug (im 128-dim Raum fast orthogonal)."""
    a = np.random.default_rng(saat).normal(size=LAENGE)
    return (a / float(np.linalg.norm(a))).tolist()


# Die drei Punkte der Kette: A-B 0.4, B-C 0.4, A-C 0.8 (im 3-dim Unterraum).
KETTE_A = _vektor((1.0, 0.0, 0.0))
KETTE_B = _vektor((0.6, 0.8, 0.0))
KETTE_C = _vektor((0.2, 0.6, 0.7746))


def _kette() -> list:
    """Die drei Punkte der Kette in Eingabereihenfolge."""
    return [list(KETTE_A), list(KETTE_B), list(KETTE_C)]


BASIS_HAUFEN = [KETTE_A, KETTE_B, KETTE_C]


def _haufen(saat: int, je_haufen: int = 4, streuung: float = 0.03) -> list:
    """Drei DICHTE Haufen entlang der Kette — der echte Bestandsfall.

    Jeder Haufen liegt um einen Kettenpunkt; innerhalb eines Haufens liegen die
    Gesichter nah (gleiche Person), zwischen den Haufen gilt der Kettenabstand
    (0.4 / 0.4 / 0.8). Ohne Verkettungs-Verbot verschmilzt das Dichte-Verfahren
    alles zu einer Gruppe — genau der Befund aus N9e.
    """
    rng = np.random.default_rng(saat)
    eintraege = []
    for basis in BASIS_HAUFEN:
        for _ in range(je_haufen):
            a = np.asarray(basis, dtype=float) + streuung * rng.normal(size=LAENGE)
            eintraege.append((a / float(np.linalg.norm(a))).tolist())
    return eintraege


def _durchmesser(gruppen, eintraege) -> float:
    """Der groesste Gruppendurchmesser (0.0, wenn es keine Gruppe gibt)."""
    wert = ps.gruppendurchmesser(gruppen, eintraege)["max"]
    return float(wert) if wert is not None else 0.0


def _je_gruppe(gruppen, eintraege) -> list:
    """Die Durchmesser aller Gruppen."""
    return [float(wert) for wert in ps.gruppendurchmesser(gruppen,
                                                          eintraege)["je_gruppe"]]


# ── 1. Aufbau des Moduls ──────────────────────────────────────────────────

def test_modul_hat_die_vorgabefunktionen():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    for name in VORGABE_FUNKTIONEN:
        assert f"def {name}(" in quelle, f"Vorgabefunktion fehlt: {name}"


def test_verfahrensnamen_sind_die_drei():
    assert pk.VERFAHREN == ("dichte", "vollstaendig", "mittelpunkt")


def test_schwellengitter_ist_das_des_auftrags():
    assert tuple(pk.SCHWELLEN_STANDARD) == SCHWELLEN


def test_vorgabeschwelle_ist_der_n9a_wert():
    assert pk.SCHWELLE_STANDARD == pc.CLUSTER_SCHWELLE


def test_min_groesse_vorgabe_ist_zwei():
    assert pk.MIN_GROESSE_STANDARD == 2


def test_modul_kennt_das_repo():
    assert pk.REPO == str(REPO)


# ── 2. Das Ketten-Beispiel des Auftrags ───────────────────────────────────

def test_kette_hat_die_abstaende_0_4_0_4_0_8():
    assert pk.abstand_vektoren(KETTE_A, KETTE_B) == pytest.approx(0.4, abs=1e-3)
    assert pk.abstand_vektoren(KETTE_B, KETTE_C) == pytest.approx(0.4, abs=1e-3)
    assert pk.abstand_vektoren(KETTE_A, KETTE_C) == pytest.approx(0.8, abs=1e-3)


def test_kette_dichte_verschmilzt_alle_drei():
    """Das Dichte-Verfahren (N9a) verknuepft transitiv — der Befund."""
    assert pc.vektoren_clustern(_kette(), 0.45, 1,
                                verfahren="dichte") == [[0, 1, 2]]


def test_kette_dichte_verschmilzt_auch_mit_zwei_nachbarn():
    assert pc.vektoren_clustern(_kette(), 0.45, 2,
                                verfahren="dichte") == [[0, 1, 2]]


def test_kette_dichte_durchmesser_ueber_der_schwelle():
    """0,8 > 0,45 — der Beleg der Verkettung."""
    assert _durchmesser([[0, 1, 2]], _kette()) > 0.45


def test_kette_vollstaendig_trennt_a_und_c():
    assert pk.vollstaendig_clustern(_kette(), 0.45, 2) == [[0, 1]]


def test_kette_vollstaendig_verwirft_das_einzelne_c():
    """C bleibt allein und ist damit Rauschen — nicht in eine Gruppe gedraengt."""
    gruppen = pk.vollstaendig_clustern(_kette(), 0.45, 2)
    assert all(2 not in gruppe for gruppe in gruppen)


def test_kette_vollstaendig_mit_min_groesse_eins_behaelt_c():
    assert pk.vollstaendig_clustern(_kette(), 0.45, 1) == [[0, 1], [2]]


def test_kette_vollstaendig_durchmesser_unter_der_schwelle():
    gruppen = pk.vollstaendig_clustern(_kette(), 0.45, 2)
    assert _durchmesser(gruppen, _kette()) <= 0.45 + pk.TOLERANZ


def test_kette_mittelpunkt_trennt_c_ab():
    assert pk.mittelpunkt_clustern(_kette(), 0.45, 2) == [[0, 1]]


def test_kette_mittelpunkt_verschmilzt_bei_weiter_schwelle_alles():
    assert pk.mittelpunkt_clustern(_kette(), 0.8, 2) == [[0, 1, 2]]


def test_kette_ist_der_auftragsfall_dichte_gegen_vollstaendig():
    """Die zwei Zahlen des Belegs stehen direkt nebeneinander."""
    dichte = pc.vektoren_clustern(_kette(), 0.45, 1, verfahren="dichte")
    vollstaendig = pk.vollstaendig_clustern(_kette(), 0.45, 2)
    assert len(dichte) == 1 and dichte[0] == [0, 1, 2]
    assert vollstaendig == [[0, 1]]
    assert _durchmesser(dichte, _kette()) > 0.45
    assert _durchmesser(vollstaendig, _kette()) <= 0.45 + pk.TOLERANZ


# ── 3. Der echte Bestandsfall: drei dichte Haufen entlang der Kette ───────

def test_haufen_dichte_verschmilzt_alle_zwoelf():
    gruppen = pk.gruppen_bilden(_haufen(1), "dichte", 0.45, 2)
    assert gruppen == [list(range(12))]


def test_haufen_dichte_durchmesser_ueber_der_schwelle():
    eintraege = _haufen(1)
    gruppen = pk.gruppen_bilden(eintraege, "dichte", 0.45, 2)
    assert _durchmesser(gruppen, eintraege) > 0.45


def test_haufen_vollstaendig_haelt_den_durchmesser_ein():
    eintraege = _haufen(1)
    gruppen = pk.gruppen_bilden(eintraege, "vollstaendig", 0.45, 2)
    assert len(gruppen) > 1
    assert _durchmesser(gruppen, eintraege) <= 0.45 + pk.TOLERANZ


def test_haufen_vollstaendig_zerfaellt_bei_0_40_in_drei_gruppen():
    gruppen = pk.gruppen_bilden(_haufen(1), "vollstaendig", 0.40, 2)
    assert gruppen == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]


def test_haufen_mittelpunkt_trennt_weniger_als_vollstaendig():
    """Das Mittelpunkt-Verfahren verknuepft schwaecher als das Dichte-Verfahren."""
    eintraege = _haufen(1)
    dichte = pk.gruppen_bilden(eintraege, "dichte", 0.45, 2)
    mittel = pk.gruppen_bilden(eintraege, "mittelpunkt", 0.45, 2)
    assert len(dichte) == 1
    assert len(mittel) >= 2


def test_haufen_mittelpunkt_ueberschreitet_die_schwelle():
    """Gemessen (Saatgut 2): 0,4881 > 0,45 — nur ``vollstaendig`` garantiert."""
    eintraege = _haufen(2)
    gruppen = pk.gruppen_bilden(eintraege, "mittelpunkt", 0.45, 2)
    assert _durchmesser(gruppen, eintraege) > 0.45


def test_haufen_mittelpunkt_hat_keine_durchmesser_garantie_ueber_saatgueter():
    """Ueber mehrere Saatgueter reisst der Durchmesser beim Mittelpunkt."""
    gerissen = 0
    for saat in (1, 2, 3, 4, 5):
        eintraege = _haufen(saat)
        gruppen = pk.gruppen_bilden(eintraege, "mittelpunkt", 0.45, 2)
        if _durchmesser(gruppen, eintraege) > 0.45:
            gerissen += 1
    assert gerissen >= 1


# ── 4. Die Invariante: Durchmesser <= Schwelle (nur vollstaendig) ─────────

def test_invariante_vollstaendig_ueber_saatgueter():
    for saat in (1, 2, 3, 4):
        eintraege = _haufen(saat)
        for grenze in (0.30, 0.40, 0.45):
            gruppen = pk.vollstaendig_clustern(eintraege, grenze, 2)
            for wert in _je_gruppe(gruppen, eintraege):
                assert wert <= grenze + pk.TOLERANZ, \
                    f"Durchmesser {wert} > Schwelle {grenze} (Saatgut {saat})"


def test_invariante_vollstaendig_auf_der_kette():
    for grenze in (0.10, 0.20, 0.30, 0.40, 0.45):
        gruppen = pk.vollstaendig_clustern(_kette(), grenze, 1)
        for wert in _je_gruppe(gruppen, _kette()):
            assert wert <= grenze + pk.TOLERANZ


def test_invariante_dichte_reisst_beim_haufen():
    """Gegenprobe: das Dichte-Verfahren darf die Schwelle ueberschreiten."""
    eintraege = _haufen(1)
    gruppen = pk.gruppen_bilden(eintraege, "dichte", 0.45, 2)
    assert _durchmesser(gruppen, eintraege) > 0.45


def test_invariante_vollstaendig_auch_bei_zufaelligen_vektoren():
    for saat in (11, 12, 13):
        rng = np.random.default_rng(saat)
        eintraege = []
        for _ in range(3):
            zentrum = rng.normal(size=LAENGE)
            zentrum = zentrum / float(np.linalg.norm(zentrum))
            for _ in range(5):
                a = zentrum + 0.2 * rng.normal(size=LAENGE)
                eintraege.append((a / float(np.linalg.norm(a))).tolist())
        for grenze in (0.25, 0.35, 0.45):
            gruppen = pk.vollstaendig_clustern(eintraege, grenze, 2)
            for wert in _je_gruppe(gruppen, eintraege):
                assert wert <= grenze + pk.TOLERANZ


# ── 5. Determinismus ──────────────────────────────────────────────────────

def test_vollstaendig_ist_deterministisch():
    eintraege = _haufen(3)
    assert pk.vollstaendig_clustern(eintraege, 0.45, 2) == \
        pk.vollstaendig_clustern(eintraege, 0.45, 2)


def test_mittelpunkt_ist_deterministisch():
    eintraege = _haufen(3)
    assert pk.mittelpunkt_clustern(eintraege, 0.45, 2) == \
        pk.mittelpunkt_clustern(eintraege, 0.45, 2)


def test_gruppen_bilden_ist_fuer_alle_verfahren_deterministisch():
    eintraege = _haufen(4)
    for name in pk.VERFAHREN:
        assert pk.gruppen_bilden(eintraege, name, 0.45, 2) == \
            pk.gruppen_bilden(eintraege, name, 0.45, 2)


def test_verfahren_messen_ist_deterministisch():
    eintraege = _haufen(2)
    assert pk.verfahren_messen(eintraege, "vollstaendig", SCHWELLEN, 2) == \
        pk.verfahren_messen(eintraege, "vollstaendig", SCHWELLEN, 2)


def test_vergleich_bericht_ist_deterministisch():
    a = pk.vergleich_bericht(_haufen(2), (0.45, 0.3), 2)
    b = pk.vergleich_bericht(_haufen(2), (0.45, 0.3), 2)
    a.pop("stand"), b.pop("stand")
    assert a == b


def test_indizes_sind_immer_aufsteigend():
    for name in pk.VERFAHREN:
        for gruppe in pk.gruppen_bilden(_haufen(1), name, 0.45, 2):
            assert gruppe == sorted(gruppe)


# ── 6. Rauschen, leere Eingabe, unbrauchbare Vektoren ─────────────────────

def test_vollstaendig_leere_eingabe_ist_leer():
    assert pk.vollstaendig_clustern([], 0.45, 2) == []


def test_vollstaendig_none_eingabe_ist_leer():
    assert pk.vollstaendig_clustern(None, 0.45, 2) == []


def test_mittelpunkt_leere_eingabe_ist_leer():
    assert pk.mittelpunkt_clustern([], 0.45, 2) == []
    assert pk.mittelpunkt_clustern(None, 0.45, 2) == []


def test_ein_einzelner_punkt_ist_rauschen():
    assert pk.vollstaendig_clustern([_fern(1)], 0.45, 2) == []
    assert pk.mittelpunkt_clustern([_fern(1)], 0.45, 2) == []


def test_min_groesse_eins_behaelt_den_einzelnen_punkt():
    assert pk.vollstaendig_clustern([_fern(1)], 0.45, 1) == [[0]]
    assert pk.mittelpunkt_clustern([_fern(1)], 0.45, 1) == [[0]]


def test_rauschen_wird_verworfen_nicht_gedraengt():
    """Vier nahe Gesichter plus ein fernes — das ferne bleibt draussen."""
    nah = [_nah(KETTE_A, saat) for saat in (1, 2, 3, 4)]
    fern = _fern(99)
    gruppen = pk.vollstaendig_clustern(nah + [fern], 0.45, 2)
    assert gruppen == [[0, 1, 2, 3]]


def test_rauschen_ist_auch_beim_mittelpunkt_draussen():
    nah = [_nah(KETTE_A, saat) for saat in (1, 2, 3, 4)]
    fern = _fern(99)
    gruppen = pk.mittelpunkt_clustern(nah + [fern], 0.45, 2)
    assert all(4 not in gruppe for gruppe in gruppen)


def test_ungueltige_vektoren_kippen_nicht():
    krumm = [None, "Text", [0.1, 0.2], KETTE_A, 7, [], KETTE_B]
    assert pk.vollstaendig_clustern(krumm, 0.45, 2) == [[3, 6]]
    assert pk.mittelpunkt_clustern(krumm, 0.45, 2) == [[3, 6]]


def test_ungueltige_vektoren_sind_in_keiner_gruppe():
    krumm = [None, "Text", KETTE_A, {"ohne": "vektor"}, KETTE_B, True]
    gueltig = pk.gueltige_indizes(krumm)
    assert gueltig == [2, 4]
    for name in pk.VERFAHREN:
        for gruppe in pk.gruppen_bilden(krumm, name, 0.45, 1):
            assert set(gruppe) <= set(gueltig)


def test_nur_ungueltige_vektoren_ergeben_nichts():
    assert pk.vollstaendig_clustern([None, "Text", 7], 0.45, 1) == []
    assert pk.mittelpunkt_clustern([None, "Text", 7], 0.45, 1) == []
    assert pk.gueltige_indizes([None, "Text", 7]) == []


def test_bezugslaenge_ist_die_mehrheit():
    krumm = [[0.1, 0.2], KETTE_A, KETTE_B, KETTE_C]
    assert pk.bezugslaenge(krumm) == LAENGE


def test_falsche_laenge_ist_unbrauchbar():
    krumm = [[0.1, 0.2], KETTE_A, KETTE_B]
    assert pk.gueltige_indizes(krumm) == [1, 2]


def test_bezugslaenge_ohne_vektor_ist_none():
    assert pk.bezugslaenge([None, "Text"]) is None


def test_abstand_vektoren_gleicher_vektor_ist_null():
    assert pk.abstand_vektoren(KETTE_A, KETTE_A) == pytest.approx(0.0, abs=1e-9)


def test_abstand_vektoren_ungleich_lang_ist_eins():
    assert pk.abstand_vektoren([1.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_abstand_vektoren_ohne_vektor_ist_eins():
    assert pk.abstand_vektoren(None, KETTE_A) == pytest.approx(1.0)
    assert pk.abstand_vektoren("Text", KETTE_A) == pytest.approx(1.0)


def test_abstand_vektoren_nullvektor_ist_eins():
    assert pk.abstand_vektoren([0.0] * 4, [1.0, 0.0, 0.0, 0.0]) == pytest.approx(1.0)


# ── 7. verfahren_messen ───────────────────────────────────────────────────

def _messzeile(*, bild_id="1", vektor=None, anteil=0.02) -> dict:
    """Ein Eintrag wie aus N9a (mit ``bild_id``/``anteil`` fuer die Paare)."""
    return {"bild_id": bild_id, "anteil": anteil,
            "embedding": list(vektor if vektor is not None else KETTE_A)}


def test_verfahren_messen_hat_die_felder():
    zeile = pk.verfahren_messen(_haufen(1), "vollstaendig", [0.45], 2)[0]
    for feld in ("verfahren", "schwelle", "min_groesse", "gruppen",
                 "groesste_gruppe", "gesichter_in_gruppen", "verworfen",
                 "groessen", "durchmesser_max", "durchmesser_mittel"):
        assert feld in zeile, f"Feld fehlt: {feld}"


def test_verfahren_messen_zaehlungen_sind_konsistent():
    eintraege = _haufen(1)
    gueltig = len(pk.gueltige_indizes(eintraege))
    for name in pk.VERFAHREN:
        for zeile in pk.verfahren_messen(eintraege, name, SCHWELLEN, 2):
            assert zeile["gesichter_in_gruppen"] + zeile["verworfen"] == gueltig


def test_verfahren_messen_gesichter_ist_die_summe_der_groessen():
    for name in pk.VERFAHREN:
        for zeile in pk.verfahren_messen(_haufen(2), name, (0.45, 0.3), 2):
            assert zeile["gesichter_in_gruppen"] == sum(zeile["groessen"])
            assert zeile["gruppen"] == len(zeile["groessen"])
            assert zeile["groesste_gruppe"] == max(zeile["groessen"] or [0])


def test_verfahren_messen_durchmesser_ordnung_stimmt():
    """min <= mittel <= max der Gruppendurchmesser."""
    for name in pk.VERFAHREN:
        for zeile in pk.verfahren_messen(_haufen(1), name, SCHWELLEN, 2):
            werte = zeile["durchmesser_je_gruppe"]
            if not werte:
                assert zeile["durchmesser_max"] == 0.0
                assert zeile["durchmesser_mittel"] == 0.0
                continue
            assert min(werte) <= zeile["durchmesser_mittel"] <= max(werte)
            assert zeile["durchmesser_max"] == pytest.approx(max(werte))


def test_verfahren_messen_haelt_die_schwellenreihenfolge():
    zeilen = pk.verfahren_messen(_haufen(1), "vollstaendig",
                                 (0.10, 0.45, 0.30), 1)
    assert [zeile["schwelle"] for zeile in zeilen] == [0.10, 0.45, 0.30]


def test_verfahren_messen_entdoppelt_schwellen():
    zeilen = pk.verfahren_messen(_haufen(1), "vollstaendig", (0.45, 0.45), 1)
    assert len(zeilen) == 1


def test_verfahren_messen_wirft_unbrauchbare_schwellen_weg():
    zeilen = pk.verfahren_messen(_haufen(1), "vollstaendig",
                                 (0.45, None, "Text", 0.3), 1)
    assert [zeile["schwelle"] for zeile in zeilen] == [0.45, 0.3]


def test_verfahren_messen_ohne_schwellen_nimmt_das_gitter():
    zeilen = pk.verfahren_messen(_haufen(1), "vollstaendig", [], 1)
    assert [zeile["schwelle"] for zeile in zeilen] == list(SCHWELLEN)
    assert len(pk.verfahren_messen(_haufen(1), "vollstaendig", None, 1)) == 8


def test_verfahren_messen_mit_beschriftungen_hat_die_paare():
    eintraege = [_messzeile(vektor=KETTE_A), _messzeile(vektor=KETTE_B),
                 _messzeile(vektor=KETTE_C)]
    zeilen = pk.verfahren_messen(eintraege, "vollstaendig", (0.45, 0.3), 2,
                                 beschriftungen=["Person_A"] * 3)
    # Drei Gesichter in EINEM Bild = drei Paare der Bodenwahrheit.
    assert zeilen[0]["personen_paare"] == 3
    assert zeilen[0]["verschmolzene_paare"] == 1
    assert zeilen[0]["verschmelzungsquote"] == pytest.approx(1 / 3)
    assert zeilen[1]["verschmolzene_paare"] == 0
    assert zeilen[1]["verschmelzungsquote"] == pytest.approx(0.0)
    assert zeilen[0]["mit_beschriftung"] == 3


def test_verfahren_messen_ohne_beschriftungen_hat_keine_paare():
    zeile = pk.verfahren_messen(_haufen(1), "vollstaendig", [0.45], 2)[0]
    assert "personen_paare" not in zeile
    assert "verschmelzungsquote" not in zeile


def test_verfahren_messen_dichte_ueberschreitet_die_schwelle():
    eintraege = _haufen(1)
    zeile = pk.verfahren_messen(eintraege, "dichte", [0.45], 2)[0]
    assert zeile["durchmesser_max"] > 0.45
    assert zeile["gruppen"] == 1


def test_verfahren_messen_vollstaendig_haelt_die_schwelle():
    eintraege = _haufen(1)
    zeile = pk.verfahren_messen(eintraege, "vollstaendig", [0.45], 2)[0]
    assert zeile["durchmesser_max"] <= 0.45 + pk.TOLERANZ


def test_verfahren_messen_min_groesse_wird_durchgereicht():
    zeile = pk.verfahren_messen(_haufen(1), "vollstaendig", [0.45], 5)[0]
    assert zeile["min_groesse"] == 5
    assert all(groesse >= 5 for groesse in zeile["groessen"])


def test_verfahren_messen_ohne_eintraege_ist_leer_aber_konsistent():
    zeilen = pk.verfahren_messen([], "vollstaendig", (0.45, 0.3), 2)
    assert len(zeilen) == 2
    assert all(zeile["gruppen"] == 0 for zeile in zeilen)
    assert all(zeile["verworfen"] == 0 for zeile in zeilen)


def test_gruppen_bilden_unbekanntes_verfahren_ist_klartextfehler():
    with pytest.raises(pk.VerkettungFehler):
        pk.gruppen_bilden(_kette(), "irgendein_verfahren", 0.45, 2)


def test_gruppen_bilden_liefert_fuer_alle_drei_gruppen():
    for name in pk.VERFAHREN:
        gruppen = pk.gruppen_bilden(_haufen(1), name, 0.45, 2)
        assert gruppen and all(gruppe for gruppe in gruppen)


def test_gruppen_bilden_achtet_die_mindestgroesse():
    gruppen = pk.gruppen_bilden(_haufen(1), "vollstaendig", 0.45, 5)
    assert all(len(gruppe) >= 5 for gruppe in gruppen)


# ── 8. zahlen_je_gruppe ───────────────────────────────────────────────────

def test_zahlen_je_gruppe_ohne_gruppen_ist_null():
    zahlen = pk.zahlen_je_gruppe([], _kette())
    assert zahlen["gruppen"] == 0
    assert zahlen["groesste_gruppe"] == 0
    assert zahlen["gesichter_in_gruppen"] == 0
    assert zahlen["durchmesser_max"] == 0.0
    assert zahlen["durchmesser_mittel"] == 0.0


def test_zahlen_je_gruppe_zaehlt_die_groessen():
    zahlen = pk.zahlen_je_gruppe([[0, 1, 2]], _kette())
    assert zahlen["gruppen"] == 1
    assert zahlen["groesste_gruppe"] == 3
    assert zahlen["gesichter_in_gruppen"] == 3
    assert zahlen["durchmesser_max"] == pytest.approx(0.8, abs=1e-3)


# ── 9. vergleich_bericht und bericht_text ─────────────────────────────────

def test_vergleich_bericht_hat_die_felder():
    bericht = pk.vergleich_bericht(_haufen(1), (0.45, 0.3), 2)
    for feld in ("verfahren", "schwellen", "min_groesse", "eintraege",
                 "gueltige_eintraege", "messungen", "vergleich", "hinweis",
                 "stand"):
        assert feld in bericht, f"Feld fehlt: {feld}"


def test_vergleich_bericht_hat_drei_verfahren():
    bericht = pk.vergleich_bericht(_haufen(1), [0.45], 2)
    assert list(bericht["verfahren"]) == list(pk.VERFAHREN)
    assert set(bericht["messungen"]) == set(pk.VERFAHREN)


def test_vergleich_bericht_stellt_die_verfahren_nebeneinander():
    bericht = pk.vergleich_bericht(_haufen(1), (0.45, 0.3), 2)
    assert len(bericht["vergleich"]) == 2
    for zeile in bericht["vergleich"]:
        for name in pk.VERFAHREN:
            assert zeile[name]["schwelle"] == zeile["schwelle"]


def test_vergleich_bericht_nennt_die_verkettung():
    bericht = pk.vergleich_bericht(_haufen(1), [0.45], 2)
    assert "TRANSITIV" in bericht["hinweis"]
    assert "garantiert" in bericht["hinweis"]


def test_vergleich_bericht_ist_json_faehig():
    bericht = pk.vergleich_bericht(_haufen(1), (0.45, 0.3), 2)
    assert json.loads(json.dumps(bericht))["schwellen"] == [0.45, 0.3]


def test_vergleich_bericht_zaehlt_die_brauchbaren():
    eintraege = _haufen(1) + [None, "Text"]
    bericht = pk.vergleich_bericht(eintraege, [0.45], 2)
    assert bericht["eintraege"] == 14
    assert bericht["gueltige_eintraege"] == 12


def test_bericht_text_nennt_die_drei_verfahren():
    text = pk.bericht_text(pk.vergleich_bericht(_haufen(1), [0.45], 2))
    for name in pk.VERFAHREN:
        assert name in text


def test_bericht_text_nennt_die_zahlen():
    text = pk.bericht_text(pk.vergleich_bericht(_haufen(1), (0.45, 0.3), 2))
    assert "0.45000" in text
    assert "0.30000" in text
    assert "0.8978" in text          # gemessener Durchmesser der Dichte-Gruppe


def test_bericht_text_zeigt_die_invariante():
    text = pk.bericht_text(pk.vergleich_bericht(_haufen(1), [0.45], 2))
    assert "Durchmesser <= Schwelle" in text
    assert "nein" in text and "ja" in text


def test_bericht_text_ohne_daten_kippt_nicht():
    for krumm in (None, {}, {"messungen": None}, {"messungen": []},
                  {"messungen": {"dichte": [None]}}):
        assert isinstance(pk.bericht_text(krumm), str)


def test_bericht_text_mit_einer_einzelnen_messung():
    messungen = pk.verfahren_messen(_haufen(1), "vollstaendig", [0.45], 2)
    text = pk.bericht_text({"verfahren": "vollstaendig", "eintraege": 12,
                            "gueltige_eintraege": 12, "min_groesse": 2,
                            "messungen": messungen})
    assert "vollstaendig" in text
    assert "0.45000" in text


def test_bericht_text_nennt_die_bodenwahrheit_wenn_paare_da_sind():
    eintraege = [_messzeile(vektor=KETTE_A), _messzeile(vektor=KETTE_B),
                 _messzeile(vektor=KETTE_C)]
    bericht = pk.vergleich_bericht(eintraege, [0.45], 2,
                                   beschriftungen=["Person_A"] * 3)
    text = pk.bericht_text(bericht)
    assert "Bodenwahrheit" in text
    assert "Bild-Paaren" in text


# ── 10. Schutz: nur ausserhalb des Repos schreiben ────────────────────────

def test_pruefe_ausserhalb_repo_laesst_tmp_zu(tmp_path):
    assert pk.pruefe_ausserhalb_repo(str(tmp_path)) == str(tmp_path)


def test_pruefe_ausserhalb_repo_lehnt_repo_ab():
    with pytest.raises(SystemExit):
        pk.pruefe_ausserhalb_repo(str(REPO / "irgendwas"))


def test_bericht_schreiben_im_repo_wird_abgelehnt():
    with pytest.raises(SystemExit):
        pk.bericht_schreiben(str(REPO / "n9f_probe.json"), {})


def test_bericht_schreiben_und_lesen_ist_ein_kreis(tmp_path):
    pfad = tmp_path / "bericht.json"
    pk.bericht_schreiben(str(pfad), {"schwellen": [0.45]})
    assert json.loads(pfad.read_text(encoding="utf-8")) == {"schwellen": [0.45]}


def test_bericht_schreiben_laesst_keine_tmp_datei_zurueck(tmp_path):
    pfad = tmp_path / "bericht.json"
    pk.bericht_schreiben(str(pfad), {"a": 1})
    assert not (tmp_path / "bericht.json.tmp").exists()
    assert pfad.is_file()


def test_bericht_schreiben_legt_nur_die_json_datei_an(tmp_path):
    pk.bericht_schreiben(str(tmp_path / "bericht.json"), {"a": 1})
    assert sorted(datei.name for datei in tmp_path.iterdir()) == ["bericht.json"]


# ── 11. Schutz: Quelltext (kein Loeschen, kein Netz, kein Bild) ───────────

def _quelle() -> str:
    return WERKZEUG.read_text(encoding="utf-8")


def test_quelltext_hat_keine_loeschfunktion():
    quelle = _quelle()
    for verboten in ("os.remove", "os.unlink", "unlink(", "shutil", "rmtree",
                     "os.rmdir", "remove(", "deletedatei"):
        assert verboten not in quelle, f"Loeschfunktion im Quelltext: {verboten}"


def test_quelltext_hat_keine_pfad_loeschmethode():
    quelle = _quelle()
    assert ".unlink(" not in quelle
    assert ".rmdir(" not in quelle


def test_quelltext_hat_keinen_netzaufruf():
    quelle = _quelle()
    for verboten in ("requests", "httpx", "socket", "urllib", "http.client",
                     "webbrowser"):
        assert verboten not in quelle, f"Netzaufruf im Quelltext: {verboten}"


def test_quelltext_hat_kein_cv2_und_kein_onnx():
    quelle = _quelle()
    for verboten in ("cv2", "onnx", "onnxruntime", "torch", "sklearn"):
        assert verboten not in quelle, f"Fremdbibliothek im Quelltext: {verboten}"


def test_quelltext_hat_keinen_pcloud_aufruf():
    quelle = _quelle().lower()
    for verboten in ("pcloud", "e.pcloud", "cloud"):
        assert verboten not in quelle, f"Cloud-Aufruf im Quelltext: {verboten}"


def test_quelltext_hat_kein_bildmodul():
    quelle = _quelle()
    for verboten in ("PIL", "Image", ".jpg", ".png", "imread", "imwrite"):
        assert verboten not in quelle, f"Bildzugriff im Quelltext: {verboten}"


def test_quelltext_hat_keine_schluesselwerte():
    quelle = _quelle().lower()
    for verboten in ("api_key", "apikey", "token", "secret", "password",
                     "authorization", "bearer"):
        assert verboten not in quelle, f"Schluesselwert im Quelltext: {verboten}"


def test_quelltext_setzt_keine_schwelle_und_keinen_pfad_in_n9a():
    quelle = _quelle()
    for verboten in ("pc.CLUSTER_SCHWELLE =", ".CLUSTER_MIN_NACHBAR =",
                     ".ANTEIL_MIN =", ".STANDARD_BASIS ="):
        assert verboten not in quelle, f"Fremdwert gesetzt: {verboten}"


def test_quelltext_nutzt_nur_erlaubte_module():
    erlaubt = {"argparse", "datetime", "importlib.util", "json", "math", "os",
               "numpy", "__future__"}
    namen = set()
    for knoten in ast.walk(ast.parse(_quelle())):
        if isinstance(knoten, ast.Import):
            for arg in knoten.names:
                namen.add(arg.name)
        elif isinstance(knoten, ast.ImportFrom):
            namen.add(knoten.module or "")
    assert namen <= erlaubt, f"Unerlaubte Importe: {namen - erlaubt}"


def test_quelltext_loescht_keine_datei_auf_der_platte():
    """Kein Loeschaufruf in ausfuehrbaren Zeilen (Docstrings ausgenommen)."""
    for nummer, zeile in enumerate(_quelle().splitlines(), start=1):
        nackt = zeile.split("#", 1)[0]
        assert "os.remove" not in nackt and "os.unlink" not in nackt, \
            f"Zeile {nummer} loescht: {zeile}"


# ── 12. Kommandozeile ─────────────────────────────────────────────────────

def _zeile(bild_id: str, embedding, bbox=(100.0, 100.0, 300.0, 300.0)) -> dict:
    """Eine Vektorzeile im Eingabeformat von N9a (ein grosses Gesicht je Bild)."""
    return {"bild_id": bild_id, "breite": BREITE, "hoehe": HOEHE,
            "gesichter": [{"bbox": list(bbox), "score": 0.9,
                           "embedding": list(embedding)}]}


def _vektordatei(tmp_path, eintraege) -> str:
    """Die Eintraege als JSONL schreiben (tmp_path, kein Bild, kein Netz)."""
    pfad = tmp_path / "vektoren.jsonl"
    with open(pfad, "w", encoding="utf-8") as datei:
        for nummer, vektor in enumerate(eintraege):
            datei.write(json.dumps(_zeile(str(100000 + nummer), vektor)) + "\n")
    return str(pfad)


def _lauf(tmp_path, eintraege, zusatz=()):
    """``main`` mit einer Vektordatei aus ``eintraege`` aufrufen."""
    vektoren = _vektordatei(tmp_path, eintraege)
    return pk.main(["--vektoren", vektoren] + list(zusatz))


def test_main_laeuft_im_trockenlauf_ohne_ausgabe(tmp_path):
    assert _lauf(tmp_path, _haufen(1)) == 0


def test_main_trockenlauf_schreibt_nichts(tmp_path):
    _lauf(tmp_path, _haufen(1))
    assert not (tmp_path / "bericht.json").exists()


def test_main_sagt_dass_nichts_geschrieben_wurde(tmp_path, capsys):
    _lauf(tmp_path, _haufen(1))
    assert "NICHTS geschrieben" in capsys.readouterr().out


def test_main_trockenlauf_zeigt_die_zahlen(tmp_path, capsys):
    _lauf(tmp_path, _haufen(1))
    ausgabe = capsys.readouterr().out
    assert "0.45000" in ausgabe
    for name in pk.VERFAHREN:
        assert name in ausgabe


def test_main_mit_schreiben_legt_den_bericht_an(tmp_path):
    assert _lauf(tmp_path, _haufen(1),
                 ["--ausgabe", str(tmp_path / "bericht.json"),
                  "--schreiben"]) == 0
    assert (tmp_path / "bericht.json").is_file()


def test_main_bericht_hat_die_erwarteten_felder(tmp_path):
    ziel = tmp_path / "bericht.json"
    _lauf(tmp_path, _haufen(1), ["--ausgabe", str(ziel), "--schreiben"])
    bericht = json.loads(ziel.read_text(encoding="utf-8"))
    assert bericht["schwellen"] == list(SCHWELLEN)
    assert bericht["min_groesse"] == 2
    assert bericht["eintraege"] == 12
    assert set(bericht["messungen"]) == set(pk.VERFAHREN)
    assert len(bericht["vergleich"]) == 8
    assert bericht["hinweis"]


def test_main_trockenlauf_mit_ausgabe_schreibt_nichts(tmp_path):
    ziel = tmp_path / "bericht.json"
    _lauf(tmp_path, _haufen(1), ["--ausgabe", str(ziel)])
    assert not ziel.exists()


def test_main_trocken_hat_vorrang_vor_schreiben(tmp_path):
    ziel = tmp_path / "bericht.json"
    _lauf(tmp_path, _haufen(1), ["--ausgabe", str(ziel), "--schreiben",
                                 "--trocken"])
    assert not ziel.exists()


def test_main_schreiben_ohne_ausgabe_ist_ein_fehler(tmp_path, capsys):
    assert _lauf(tmp_path, _haufen(1), ["--schreiben"]) == 2
    assert "Fehler" in capsys.readouterr().out


def test_main_ausgabe_im_repo_wird_abgelehnt(tmp_path):
    with pytest.raises(SystemExit):
        _lauf(tmp_path, _haufen(1),
              ["--ausgabe", str(REPO / "n9f_probe.json"), "--schreiben"])


def test_main_verfahren_einzeln(tmp_path, capsys):
    assert _lauf(tmp_path, _haufen(1), ["--verfahren", "vollstaendig"]) == 0
    ausgabe = capsys.readouterr().out
    assert "vollstaendig" in ausgabe
    assert "mittelpunkt" not in ausgabe


def test_main_verfahren_unbekannt_kippt(tmp_path):
    with pytest.raises(SystemExit):
        _lauf(tmp_path, _haufen(1), ["--verfahren", "quatsch"])


def test_main_erlaubt_eigene_schwellen(tmp_path):
    ziel = tmp_path / "bericht.json"
    _lauf(tmp_path, _haufen(1), ["--schwellen", "0.45,0.3",
                                 "--ausgabe", str(ziel), "--schreiben"])
    bericht = json.loads(ziel.read_text(encoding="utf-8"))
    assert bericht["schwellen"] == [0.45, 0.3]


def test_main_erlaubt_eigene_mindestgroesse(tmp_path):
    ziel = tmp_path / "bericht.json"
    _lauf(tmp_path, _haufen(1), ["--min-groesse", "5",
                                 "--ausgabe", str(ziel), "--schreiben"])
    bericht = json.loads(ziel.read_text(encoding="utf-8"))
    assert bericht["min_groesse"] == 5


def test_main_meldet_fehlende_vektordatei(tmp_path, capsys):
    assert pk.main(["--vektoren", str(tmp_path / "gibtsnicht.jsonl")]) == 2
    assert "Fehler" in capsys.readouterr().out


def test_main_ohne_vektoren_kippt(tmp_path):
    with pytest.raises(SystemExit):
        pk.main([])


def test_main_ungueltige_zeilen_kippen_nicht(tmp_path, capsys):
    pfad = tmp_path / "vektoren.jsonl"
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write("kein json\n")
        datei.write("{}\n")
        datei.write(json.dumps(_zeile("1", KETTE_A)) + "\n")
        datei.write(json.dumps(_zeile("2", KETTE_B)) + "\n")
    assert pk.main(["--vektoren", str(pfad)]) == 0
    ausgabe = capsys.readouterr().out
    assert "ungueltige Zeilen: 2" in ausgabe


def test_main_aendert_keine_n9a_schwelle(tmp_path):
    vorher = (pc.CLUSTER_SCHWELLE, pc.CLUSTER_MIN_NACHBAR, pc.ANTEIL_MIN)
    _lauf(tmp_path, _haufen(1), ["--verfahren", "alle"])
    assert (pc.CLUSTER_SCHWELLE, pc.CLUSTER_MIN_NACHBAR, pc.ANTEIL_MIN) == vorher


def test_main_nutzt_den_n9a_leser_fuer_die_vektoren(tmp_path, capsys):
    """Die Vektordatei kommt aus dem Bestand — gelesen mit N9a, nicht neu gebaut."""
    _lauf(tmp_path, _haufen(1))
    ausgabe = capsys.readouterr().out
    assert "geclusterte Gesichter: 12" in ausgabe
