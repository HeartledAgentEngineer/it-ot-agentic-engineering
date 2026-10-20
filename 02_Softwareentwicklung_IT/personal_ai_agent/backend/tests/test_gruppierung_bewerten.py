"""Tests: Messlatte der Gruppierung (tools/foto_sortierung/gruppierung_bewerten.py, G1, 15.10.2026).

Alles offline, mit ERFUNDENEN Zuordnungen und Regeln in ``tmp_path``. Jede
Kennzahl wird an einem Fall mit bekannter Loesung geprueft. Keine echten
Gesichter, Namen oder Pfade; die Namen sind frei erfunden ("Name Eins").

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppierung_bewerten.py -q
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


gb = _laden("gruppierung_bewerten")
pg = _laden("personen_gruppieren")


def _z(bild, index, kennung, score=0.95, breite=100):
    """Eine Zuordnungszeile (Form wie ``gesicht_zuordnung.jsonl``)."""
    return {"bild_id": str(bild), "index": index, "kennung": kennung,
            "bbox": [0, 0, breite, breite], "score": score}


def _zuordnung(zeilen):
    erg, ungueltig = gb.zuordnung_aus_zeilen(zeilen)
    assert ungueltig == 0
    return erg


# ── Die Szene mit bekannter Loesung ───────────────────────────────────────
#
# Person_A  "Name Eins"  4 Gesichter, 3 sauber (1002:0 unsicher)
# Person_B  "Name Zwei"  2 Gesichter, beide sauber
# Person_C  unbenannt    2 Gesichter, 0 sauber (eins unsicher, eins zu klein)
# Person_D  "Name Eins"  1 Gesicht (derselbe Name in zweiter Gruppe)
# ohne Kennung: 2 Gesichter

SZENE = [
    _z(1000, 0, "Person_A"), _z(1001, 0, "Person_A"),
    _z(1002, 0, "Person_A", score=0.5), _z(1003, 0, "Person_A"),
    _z(2000, 0, "Person_B"), _z(2001, 0, "Person_B"),
    _z(3000, 0, "Person_C", score=0.7), _z(3001, 0, "Person_C", breite=40),
    _z(4000, 0, "Person_D"),
    _z(5000, 0, None), _z(5001, 0, None),
]
BESTAETIGT = {"Person_A": "Name Eins", "Person_B": "Name Zwei", "Person_D": "Name Eins"}
VORGABEN = {
    "gleich": {("Person_A", "Person_D")},
    "verschieden": {("Person_A", "Person_B"), ("Person_A", "Person_Z")},
    "ausgeschlossen": {("Person_A", "1002", 0), ("Person_B", "2001", 0),
                       ("Person_A", "9000", 0)},
    "zugeordnet": {
        ("1000", 0): {"name": "Name Eins", "kennung": "Person_A"},   # richtig
        ("2000", 0): {"name": "Name Eins", "kennung": "Person_A"},   # liegt bei Name Zwei
        ("3000", 0): {"name": "Name Zwei", "kennung": "Person_B"},   # liegt unbenannt
        ("5000", 0): {"name": "Name Eins", "kennung": "Person_A"},   # ohne Kennung
        ("9999", 0): {"name": "Name Eins", "kennung": "Person_A"},   # nicht in der Zuordnung
    },
}


@pytest.fixture
def szene():
    return _zuordnung(SZENE)


# ── sauber: Grenzen kommen aus dem Messwerkzeug ──────────────────────────────

def test_sauber_nutzt_die_grenzen_des_messwerkzeugs():
    phasen = gb._phasen
    messer = phasen._messer
    assert phasen.SAUBER_SCORE == messer.MIN_SCORE == 0.90
    assert phasen.SAUBER_BREITE == messer.MIN_BREITE == 64
    assert phasen.sauber({"score": 0.90, "bbox": [0, 0, 64, 64]})
    assert not phasen.sauber({"score": 0.899, "bbox": [0, 0, 64, 64]})
    assert not phasen.sauber({"score": 0.99, "bbox": [0, 0, 63, 64]})
    assert not phasen.sauber({"score": None, "bbox": [0, 0, 100, 100]})
    assert not phasen.sauber({"score": 0.99})                     # keine Breite
    assert phasen.sauber({"score": 0.95, "breite_px": 70})


# ── Lesen ────────────────────────────────────────────────────────────────

def test_zuordnung_lesen_zaehlt_kaputte_zeilen_und_nimmt_die_erste_bei_doppelt(tmp_path):
    pfad = tmp_path / "z.jsonl"
    pfad.write_text("\n".join([
        json.dumps(_z(1, 0, "Person_A")),
        "das ist kein json",
        json.dumps(_z(1, 0, "Person_B")),                      # doppelt: erste gewinnt
        json.dumps({"kennung": "Person_A"}),                    # ohne bild_id
        json.dumps(_z(2, 0, None)),
    ]) + "\n", encoding="utf-8")
    zuordnung, ungueltig = gb.zuordnung_lesen(str(pfad))
    assert ungueltig == 2
    assert zuordnung[("1", 0)] == ("Person_A", True)
    assert zuordnung[("2", 0)] == (None, True)


# ── Grundwahrheit (Kopfzeile) ───────────────────────────────────────────────

def test_grundwahrheit_zaehlt_namen_und_regeln():
    g = gb.grundwahrheit(BESTAETIGT, VORGABEN)
    assert g["namen"] == 2                    # "Name Eins" zaehlt einmal
    assert g["benannte_kennungen"] == 3
    assert g["regeln"] == {"gleich": 1, "verschieden": 2, "ausgeschlossen": 3, "fest": 5}
    assert g["regeln_gesamt"] == 11
    assert g["vorlaeufig"] is True


def test_grundwahrheit_vorlaeufig_faellt_weg_mit_zehn_namen_oder_fuenfzig_regeln():
    viele_namen = {f"K{i}": f"Name {i}" for i in range(gb.MIN_NAMEN)}
    assert gb.grundwahrheit(viele_namen, {})["vorlaeufig"] is False
    zu_wenige = {f"K{i}": f"Name {i}" for i in range(gb.MIN_NAMEN - 1)}
    assert gb.grundwahrheit(zu_wenige, {})["vorlaeufig"] is True
    viele_regeln = {"verschieden": {(f"A{i}", f"B{i}") for i in range(gb.MIN_REGELN)}}
    assert gb.grundwahrheit({}, viele_regeln)["vorlaeufig"] is False
    assert gb.grundwahrheit({}, {"verschieden": {("A", "B")}})["vorlaeufig"] is True


def test_grundwahrheit_warnt_vor_aelteren_regeldateien():
    assert gb.grundwahrheit({}, {}, 100.0, 300.0, 200.0)["veraltet"] is True
    assert gb.grundwahrheit({}, {}, 300.0, 100.0, 200.0)["veraltet"] is True
    assert gb.grundwahrheit({}, {}, 300.0, 400.0, 200.0)["veraltet"] is False
    assert gb.grundwahrheit({}, {}, None, None, 200.0)["veraltet"] is False
    assert gb.grundwahrheit({}, {}, 100.0, 100.0, None)["veraltet"] is False


def test_kopf_zeigt_vorlaeufig_und_warnung_nur_wenn_zutreffend():
    text = "\n".join(gb.kopf_text(gb.grundwahrheit(BESTAETIGT, VORGABEN, 100.0, 100.0, 200.0)))
    assert "VORLAEUFIG - zu wenig Entscheidungen" in text
    assert "Entscheidungen vom Handy holen (G0)" in text
    assert "2 Namen in 3 benannten Kennungen" in text
    assert "gleich 1 - verschieden 2 - ausgeschlossen 3 - fest 5" in text
    viele = {f"K{i}": f"Name {i}" for i in range(12)}
    ruhig = "\n".join(gb.kopf_text(gb.grundwahrheit(viele, {}, 300.0, 300.0, 200.0)))
    assert "VORLAEUFIG" not in ruhig and "Handy holen" not in ruhig


# ── Kennzahlen an der Szene ────────────────────────────────────────────────

def test_gruppen_groessen_und_ohne_kennung(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    assert e["gesichter"] == 11
    assert e["in_gruppen"] == 9 and e["ohne_kennung"] == 2
    assert e["gruppen"] == 4
    assert e["groessen_top5"] == [4, 2, 2, 1]
    assert e["gruppen_ab_10"] == 0 and e["gruppen_ab_50"] == 0
    assert e["in_benannten_gruppen"] == 7


def test_gruppen_ohne_sauberes_gesicht(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    assert e["gruppen_ohne_sauberes"] == 1          # nur Person_C


def test_namens_reinheit_an_festen_zuordnungen(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    r = e["reinheit"]
    assert r == {"geprueft": 4, "richtig": 1, "anderer_name": 1, "unbenannt": 1,
                 "ohne_kennung": 1, "nicht_in_zuordnung": 1}


def test_streuung_der_namen_ueber_gruppen(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    assert e["streuung"] == {"eine": 1, "zwei": 1, "drei_oder_mehr": 0}
    assert e["streuung_max"] == 2
    assert e["namen_mit_gruppe"] == 2 and e["namen_ohne_gruppe"] == 0


def test_streuung_zaehlt_namen_ohne_vorhandene_gruppe(szene):
    bestaetigt = dict(BESTAETIGT, Person_X="Name Drei")           # Person_X gibt es nicht
    e = gb.bewerten(szene, bestaetigt, VORGABEN)
    assert e["namen_ohne_gruppe"] == 1


def test_regelbruch_ausgeschlossen(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    assert e["ausgeschlossen_regeln"] == 3
    assert e["ausgeschlossen_bruch"] == 2      # 1002:0 in A, 2001:0 in B; 9000:0 gibt es nicht


def test_regelbruch_verschieden_ohne_vergleich(szene):
    e = gb.bewerten(szene, BESTAETIGT, VORGABEN)
    assert e["verschieden_regeln"] == 2
    assert e["verschieden_kennung_fehlt"] == 1          # Person_Z fehlt
    assert e["verschieden_vereint"] is None             # ohne Vorher nicht pruefbar


def test_verschieden_vereint_im_vergleich():
    vorher = _zuordnung([_z(1, 0, "X"), _z(2, 0, "X"), _z(3, 0, "Y"), _z(4, 0, "Y"),
                         _z(5, 0, "W"), _z(6, 0, "W")])
    nachher = _zuordnung([_z(1, 0, "Q"), _z(2, 0, "X"), _z(3, 0, "Q"), _z(4, 0, "Y"),
                          _z(5, 0, "R"), _z(6, 0, "R")])
    vorgaben = {"verschieden": {("X", "Y"), ("X", "W")}}
    e = gb.bewerten(nachher, {}, vorgaben, vorher=vorher)
    assert e["verschieden_vereint"] == 1                # X und Y laufen in Q zusammen
    assert gb.bewerten(vorher, {}, vorgaben, vorher=vorher)["verschieden_vereint"] == 0


# ── Wechsel ─────────────────────────────────────────────────────────────────

def test_wechsel_der_sauberen_gesichter():
    vorher = _zuordnung([
        _z(1, 0, "A"), _z(2, 0, "A"), _z(3, 0, "A", score=0.5),
        _z(4, 0, "B"), _z(5, 0, None), _z(6, 0, None), _z(7, 0, "B"),
    ])
    nachher = _zuordnung([
        _z(1, 0, "A"),                      # gleiche Gruppe
        _z(2, 0, "B"),                      # gewechselt
        _z(3, 0, "B", score=0.5),           # war unsicher: zaehlt nicht
        _z(4, 0, None),                     # Kennung verloren
        _z(5, 0, "A"),                      # Kennung gewonnen
        _z(6, 0, None),                     # bleibt ohne
        _z(8, 0, "A"),                      # nur in nachher
    ])
    w = gb.wechsel(vorher, nachher)
    assert w == {"saubere_in_beiden": 5, "gleiche_gruppe": 1, "gruppe_gewechselt": 1,
                 "kennung_verloren": 1, "kennung_gewonnen": 1, "bleibt_ohne": 1,
                 "nur_vorher": 1, "nur_nachher": 1}


# ── Namens-Reinheit im Vergleich: Wahrheit aus der Vorher-Benennung ──────────

def test_wahrheit_enthaelt_benannte_gruppen_der_vorher_zuordnung_und_feste_gewinnen():
    vorher = _zuordnung([_z(1, 0, "Person_A"), _z(2, 0, "Person_B"), _z(3, 0, "Person_C")])
    wahrheit = gb.wahrheit_bauen(
        {"zugeordnet": {("2", 0): {"name": "Name Eins", "kennung": "Person_A"}}},
        {"Person_A": "Name Eins", "Person_B": "Name Zwei"}, vorher=vorher)
    assert wahrheit == {("1", 0): "name eins",       # aus der benannten Gruppe
                        ("2", 0): "name eins"}       # feste Zuordnung gewinnt gegen Person_B
    assert ("3", 0) not in wahrheit                   # Person_C ist unbenannt


def test_reinheit_im_vergleich_zeigt_erhalt_der_benannten():
    bestaetigt = {"Person_A": "Name Eins"}
    vorher = _zuordnung([_z(1, 0, "Person_A"), _z(2, 0, "Person_A"), _z(3, 0, "Person_A"),
                         _z(4, 0, "Person_A")])
    nachher = _zuordnung([_z(1, 0, "Person_A"), _z(2, 0, "Person_Q"), _z(3, 0, None)])
    wahrheit = gb.wahrheit_bauen({}, bestaetigt, vorher=vorher)
    r_vorher = gb.bewerten(vorher, bestaetigt, {}, wahrheit, vorher=vorher)["reinheit"]
    r_nachher = gb.bewerten(nachher, bestaetigt, {}, wahrheit, vorher=vorher)["reinheit"]
    assert r_vorher["richtig"] == 4 and r_vorher["geprueft"] == 4
    assert r_nachher == {"geprueft": 3, "richtig": 1, "anderer_name": 0, "unbenannt": 1,
                         "ohne_kennung": 1, "nicht_in_zuordnung": 1}


# ── Bericht: nur Zahlen ──────────────────────────────────────────────────────

GEHEIME_TEXTE = ("Name Eins", "Name Zwei", "Person_A", "Person_B", "Person_C", "Person_D",
                 "7770001", "7770002")


def _geheime_szene():
    zeilen = [_z(7770001, 0, "Person_A"), _z(7770002, 0, "Person_A"),
              _z(7770003, 0, "Person_B"), _z(7770004, 0, None)]
    return _zuordnung(zeilen)


def test_bericht_enthaelt_keine_bild_ids_namen_oder_pfade(tmp_path):
    zuordnung = _geheime_szene()
    nachher = _zuordnung([_z(7770001, 0, "Person_A"), _z(7770002, 0, "Person_B"),
                          _z(7770003, 0, "Person_B"), _z(7770004, 0, None)])
    bestaetigt = {"Person_A": "Name Eins", "Person_B": "Name Zwei"}
    vorgaben = {"zugeordnet": {("7770001", 0): {"name": "Name Eins", "kennung": "Person_A"}},
                "ausgeschlossen": {("Person_A", "7770002", 0)},
                "verschieden": {("Person_A", "Person_B")}}
    texte = [
        gb.einzel_bericht(zuordnung, bestaetigt, vorgaben, 1.0, 1.0, 2.0),
        gb.vergleich_bericht(zuordnung, nachher, bestaetigt, vorgaben, 1.0, 1.0, 2.0),
    ]
    for text in texte:
        for verboten in GEHEIME_TEXTE + (str(tmp_path), "gesicht_zuordnung", ".jsonl", "\\", "/"):
            assert verboten not in text, f"{verboten!r} im Bericht"
        assert any(ziffer.isdigit() for ziffer in text)


# ── Vergleichsbericht: beide Spalten ───────────────────────────────────────────

def test_vergleichsbericht_zeigt_vorher_und_nachher_nebeneinander():
    vorher = _zuordnung([_z(1, 0, "A"), _z(2, 0, "A"), _z(3, 0, None)])
    nachher = _zuordnung([_z(1, 0, "A"), _z(2, 0, None), _z(3, 0, None)])
    text = gb.vergleich_bericht(vorher, nachher, {}, {})
    kopfzeile = [z for z in text.splitlines() if z.startswith("Kennzahl")]
    assert kopfzeile and "vorher" in kopfzeile[0] and "nachher" in kopfzeile[0]
    ohne = [z for z in text.splitlines() if z.lstrip().startswith("ohne Kennung")][0]
    assert "33.3 %" in ohne and "66.7 %" in ohne                     # 1 von 3 / 2 von 3
    assert "Wechsel der sauberen Gesichter gegenueber vorher" in text
    assert "Kennung verloren: 1" in text


# ── Kommandozeile ──────────────────────────────────────────────────────────────

def _lauf(argv):
    ausgabe, fehler = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(ausgabe), contextlib.redirect_stderr(fehler):
        code = gb.main(argv)
    return code, ausgabe.getvalue(), fehler.getvalue()


def _dateien(tmp_path, zeilen=SZENE):
    z = tmp_path / "zuordnung.jsonl"
    z.write_text("\n".join(json.dumps(x) for x in zeilen) + "\n", encoding="utf-8")
    b = tmp_path / "personen_bestaetigt.json"
    b.write_text(json.dumps({"bestaetigt": BESTAETIGT}), encoding="utf-8")
    v = tmp_path / "personen_vorgaben.json"
    v.write_text(json.dumps({
        "gleich": [["Person_A", "Person_D"]],
        "verschieden": [["Person_A", "Person_B"]],
        "ausgeschlossen": [{"kennung": "Person_A", "bild_id": "1002", "index": 0}],
        "zugeordnet": [{"bild_id": "1000", "index": 0, "kennung": "Person_A",
                        "name": "Name Eins"}],
    }), encoding="utf-8")
    return z, b, v


def test_kommandozeile_schreibt_nichts_und_zeigt_nur_zahlen(tmp_path):
    z, b, v = _dateien(tmp_path)
    vorher = sorted(os.listdir(tmp_path))
    code, aus, fehler = _lauf(["--zuordnung", str(z), "--bestaetigt", str(b),
                               "--vorgaben", str(v)])
    assert code == 0, fehler
    assert sorted(os.listdir(tmp_path)) == vorher, "das Werkzeug darf nichts schreiben"
    assert "Grundwahrheit: 2 Namen in 3 benannten Kennungen" in aus
    assert "Gesichter: 11" in aus
    for verboten in ("Name Eins", "Person_A", "1000", str(tmp_path)):
        assert verboten not in aus


def test_kommandozeile_vergleichsmodus(tmp_path):
    z, b, v = _dateien(tmp_path)
    n = tmp_path / "nachher.jsonl"
    n.write_text("\n".join(json.dumps(x) for x in SZENE[:5]) + "\n", encoding="utf-8")
    code, aus, fehler = _lauf(["--vorher", str(z), "--nachher", str(n),
                               "--bestaetigt", str(b), "--vorgaben", str(v)])
    assert code == 0, fehler
    assert "vorher" in aus and "nachher" in aus and "Wechsel" in aus


def test_kommandozeile_fehlende_datei_gibt_exit_2_ohne_pfad(tmp_path):
    z, b, v = _dateien(tmp_path)
    code, aus, fehler = _lauf(["--zuordnung", str(tmp_path / "gibtsnicht.jsonl"),
                               "--bestaetigt", str(b), "--vorgaben", str(v)])
    assert code == 2
    assert "gibtsnicht" not in fehler and str(tmp_path) not in fehler
    code2, _, fehler2 = _lauf(["--vorher", str(z)])
    assert code2 == 2 and "gehoeren zusammen" in fehler2


def test_kommandozeile_fehlende_regeldateien_sind_leere_grundwahrheit(tmp_path):
    z, _, _ = _dateien(tmp_path)
    code, aus, _ = _lauf(["--zuordnung", str(z),
                          "--bestaetigt", str(tmp_path / "nein1.json"),
                          "--vorgaben", str(tmp_path / "nein2.json")])
    assert code == 0
    assert "VORLAEUFIG" in aus and "0 Namen in 0 benannten Kennungen" in aus
    assert "Stand: Namen fehlt - Vorgaben fehlt" in aus
