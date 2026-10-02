"""Tests: Personen gruppieren ueber alle Gesichter (Foto-Gedaechtnis Schritt 1, 30.09.2026).

Alles offline mit ERFUNDENEN Vektoren: Personen sind zufaellige Einheitsvektoren
im 128-dim Raum, ihre Gesichter liegen mit Cosinus ~0,8 um den Mittelpunkt.
Keine echten Gesichter, keine Namen, keine pCloud. Dateien nur in ``tmp_path``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_gruppieren.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

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


pg = _laden("personen_gruppieren")
D = 128


def _mitte(rng):
    v = rng.normal(size=D)
    return v / np.linalg.norm(v)


def _gesicht(rng, mitte, naehe=0.8):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


def _szene(personen=5, je_person=20, seed=1, zusammen=None):
    """Bilder mit 1–2 Personen; ``zusammen`` = Paare, die IMMER gemeinsam auf Bildern sind."""
    rng = np.random.default_rng(seed)
    mitten = [_mitte(rng) for _ in range(personen)]
    vektoren, bilder, wahr = [], [], []
    bild = 0
    for p in range(personen):
        for _ in range(je_person):
            bild += 1
            vektoren.append(_gesicht(rng, mitten[p]))
            bilder.append(f"b{bild}")
            wahr.append(p)
    for a, b in zusammen or []:
        for _ in range(je_person):
            bild += 1
            for p in (a, b):
                vektoren.append(_gesicht(rng, mitten[p]))
                bilder.append(f"b{bild}")
                wahr.append(p)
    return np.array(vektoren), bilder, np.array(wahr), mitten


def _reinheit(label, wahr):
    """Je gefundener Gruppe: stammen alle Gesichter von EINER Person?"""
    for c in set(label.tolist()) - {-1}:
        if len(set(wahr[label == c].tolist())) != 1:
            return False
    return True


# ── Verfahren ─────────────────────────────────────────────────────────────

def test_findet_die_personen_rein_und_vollstaendig():
    v, bilder, wahr, _ = _szene(personen=5, je_person=20)
    erg = pg.gruppieren(v, bilder)
    assert erg["k"] == 5
    assert (erg["label"] >= 0).all()
    assert _reinheit(erg["label"], wahr)


def test_labels_nach_groesse_absteigend():
    rng = np.random.default_rng(3)
    mitten = [_mitte(rng) for _ in range(3)]
    v, bilder = [], []
    for p, anzahl in enumerate((5, 30, 12)):
        for i in range(anzahl):
            v.append(_gesicht(rng, mitten[p]))
            bilder.append(f"p{p}_{i}")
    erg = pg.gruppieren(np.array(v), bilder)
    groessen = np.bincount(erg["label"][erg["label"] >= 0])
    assert list(groessen) == [30, 12, 5]


def test_selbes_bild_nie_in_einer_gruppe():
    rng = np.random.default_rng(5)
    m = _mitte(rng)
    # Dieselbe Person zweimal auf jedem Bild (Spiegel/Poster) + normale Bilder.
    v = [_gesicht(rng, m) for _ in range(20)]
    bilder = [f"b{i // 2}" for i in range(20)]
    erg = pg.gruppieren(np.array(v), bilder)
    for c in set(erg["label"].tolist()) - {-1}:
        auf_bild = [bilder[i] for i in np.nonzero(erg["label"] == c)[0]]
        assert len(auf_bild) == len(set(auf_bild)), "zwei Gesichter eines Bildes in einer Gruppe"


def test_zwillinge_die_zusammen_auf_bildern_sind_bleiben_getrennt_und_werden_markiert():
    rng = np.random.default_rng(7)
    a = _mitte(rng)
    b = 0.7 * a + np.sqrt(1 - 0.49) * _mitte(rng)       # Mittelpunkte Cosinus ~0,7
    b /= np.linalg.norm(b)
    v, bilder, wahr = [], [], []
    for i in range(25):                                   # immer gemeinsam auf dem Foto
        for p, m in ((0, a), (1, b)):
            v.append(_gesicht(rng, m, 0.85))
            bilder.append(f"z{i}")
            wahr.append(p)
    v, wahr = np.array(v), np.array(wahr)
    erg = pg.gruppieren(v, bilder)
    assert erg["k"] == 2 and _reinheit(erg["label"], wahr)
    paare = pg.zwillings_kandidaten(v, bilder, erg["label"], erg["k"])
    assert len(paare) == 1 and paare[0]["gemeinsame_bilder"] == 25


def test_einzelgaenger_sind_rauschen():
    v, bilder, _, _ = _szene(personen=2, je_person=10)
    rng = np.random.default_rng(9)
    fremde = np.array([_mitte(rng) for _ in range(6)])
    v2 = np.vstack([v, fremde])
    bilder2 = bilder + [f"f{i}" for i in range(6)]
    erg = pg.gruppieren(v2, bilder2)
    assert erg["k"] == 2
    assert (erg["label"][-6:] == -1).all()


def test_deterministisch():
    v, bilder, _, _ = _szene(personen=4, je_person=15, seed=11)
    a = pg.gruppieren(v, bilder)["label"]
    b = pg.gruppieren(v, bilder)["label"]
    assert (a == b).all()


def test_groessenprobe_6000_gesichter_ohne_vollmatrix():
    v, bilder, wahr, _ = _szene(personen=30, je_person=200, seed=13)
    start = time.monotonic()
    erg = pg.gruppieren(v, bilder)
    dauer = time.monotonic() - start
    assert erg["k"] == 30 and _reinheit(erg["label"], wahr)
    assert dauer < 60, f"zu langsam: {dauer:.1f} s"


# ── Kennungen und Vorgaben ────────────────────────────────────────────────

def _eingelesen(v, bilder, jahre=None):
    gesichter = [{"bild_id": b, "index": 0, "bbox": [0, 0, 100, 100], "breite": 1000,
                  "hoehe": 1000, "anteil": 0.01, "score": 0.9,
                  "aufnahme": (f"{jahre[i]}-06-01T12:00:00" if jahre else None),
                  "video_id": None, "zeit_s": None} for i, b in enumerate(bilder)]
    return {"gesichter": gesichter, "vektoren": pg.einheitsvektoren(v), "dateien": [],
            "bilder": len(set(bilder)), "bilder_gruppiert": len(set(bilder)),
            "je_grund": {}, "ungueltig": 0, "doppelt": 0}


def test_kennungen_bleiben_ueber_laeufe_stabil():
    v, bilder, _, _ = _szene(personen=4, je_person=15, seed=17)
    erst = pg.lauf_rechnen(_eingelesen(v, bilder))
    zweit = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"])
    assert [g["kennung"] for g in erst["gruppen"]] == [g["kennung"] for g in zweit["gruppen"]]
    assert all(not g["neu"] for g in zweit["gruppen"])


def test_kennung_ab_1000_und_nie_wiederverwendet():
    alt = [{"kennung": "Person_999", "mittelpunkt": [1.0] + [0.0] * (D - 1)}]
    rng = np.random.default_rng(19)
    mitte = np.array([_mitte(rng)])
    erg = pg.kennungen_vergeben(mitte, alt)
    assert erg[0]["kennung"] == "Person_1000" and erg[0]["neu"]


def _zwei_aehnliche(seed, aehnlich=0.45):
    rng = np.random.default_rng(seed)
    a = _mitte(rng)
    b = aehnlich * a + np.sqrt(1 - aehnlich ** 2) * _mitte(rng)
    b /= np.linalg.norm(b)
    v, bilder = [], []
    for p, m in ((0, a), (1, b)):
        for i in range(15):
            v.append(_gesicht(rng, m, 0.9))
            bilder.append(f"p{p}_{i}")
    return np.array(v), bilder


def test_vorgabe_verschieden_verhindert_verschmelzen():
    v, bilder = _zwei_aehnliche(23)
    locker = dict(verschmelzen=0.4)
    erst = pg.lauf_rechnen(_eingelesen(v, bilder), min_groesse=3, verschmelzen=0.99)
    assert len(erst["gruppen"]) == 2
    ka, kb = erst["gruppen"][0]["kennung"], erst["gruppen"][1]["kennung"]
    ohne = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"], **locker)
    assert len(ohne["gruppen"]) == 1                      # locker: wuerde verschmelzen
    mit = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"],
                          vorgaben={"gleich": set(), "verschieden": {tuple(sorted((ka, kb)))}},
                          **locker)
    assert len(mit["gruppen"]) == 2


def test_verschiedene_bestaetigte_namen_verschmelzen_nie():
    v, bilder = _zwei_aehnliche(29)
    erst = pg.lauf_rechnen(_eingelesen(v, bilder), verschmelzen=0.99)
    namen = {erst["gruppen"][0]["kennung"]: "Erste", erst["gruppen"][1]["kennung"]: "Zweite"}
    mit = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"],
                          bestaetigt=namen, verschmelzen=0.4)
    assert len(mit["gruppen"]) == 2
    assert {g["name"] for g in mit["gruppen"]} == {"Erste", "Zweite"}


def test_vorgabe_gleich_legt_zusammen():
    v, bilder, _, _ = _szene(personen=2, je_person=12, seed=31)
    erst = pg.lauf_rechnen(_eingelesen(v, bilder))
    ka, kb = erst["gruppen"][0]["kennung"], erst["gruppen"][1]["kennung"]
    mit = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"],
                          vorgaben={"gleich": {tuple(sorted((ka, kb)))}, "verschieden": set()})
    assert len(mit["gruppen"]) == 1


# ── Beispiele, Lesen, Schreiben ───────────────────────────────────────────

def test_beispiele_nur_fotos_je_bild_eins_und_ueber_jahre_gestreut():
    gesichter = []
    for jahr in (2015, 2018, 2022):
        for i in range(5):
            gesichter.append({"bild_id": f"{jahr}_{i}", "index": 0, "bbox": [0, 0, 1, 1],
                              "breite": 10, "hoehe": 10, "anteil": 0.01 * (i + 1), "score": 0.9,
                              "aufnahme": f"{jahr}-01-01T00:00:00", "video_id": None})
    gesichter.append({"bild_id": "v#t=2", "index": 0, "bbox": [0, 0, 1, 1], "breite": 10,
                      "hoehe": 10, "anteil": 0.9, "score": 1.0, "aufnahme": None, "video_id": "v"})
    gesichter.append(dict(gesichter[0], index=1))            # zweites Gesicht desselben Bildes
    b = pg.beispiele_waehlen(gesichter, 6)
    assert len(b) == 6
    assert all(not x["bild_id"].startswith("v") for x in b)
    assert len({x["bild_id"] for x in b}) == 6
    assert {x["aufnahme"][:4] for x in b} == {"2015", "2018", "2022"}
    assert "embedding" not in b[0]


def _zeile(bild_id, vektoren, klein=False, **extra):
    seite = 20 if klein else 200
    return json.dumps(dict({"bild_id": bild_id, "breite": 1000, "hoehe": 1000,
                            "gesichter": [{"bbox": [10 + 30 * i, 10, seite, seite], "score": 0.9,
                                           "embedding": [float(x) for x in vec]}
                                          for i, vec in enumerate(vektoren)]}, **extra))


def test_lesen_mehrere_dateien_doppelte_kaputte_und_menge(tmp_path):
    rng = np.random.default_rng(37)
    m = _mitte(rng)
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text("\n".join([
        _zeile("1", [_gesicht(rng, m)], metadaten={"aufnahme": "2019-06-21T20:00:00"}),
        "{kaputt",
        _zeile("2", [_gesicht(rng, m)]),
    ]) + "\n", encoding="utf-8")
    b.write_text("\n".join([
        _zeile("2", [_gesicht(rng, m)]),                                 # doppelt
        _zeile("3", [_mitte(rng) for _ in range(8)], klein=True),        # Menschenmenge
        _zeile("99#t=4", [_gesicht(rng, m)], video_id="99", zeit_s=4.0),
    ]) + "\n", encoding="utf-8")
    e = pg.gesichter_lesen([str(a), str(b)])
    assert e["bilder"] == 4 and e["doppelt"] == 1 and e["ungueltig"] == 1
    assert e["bilder_gruppiert"] == 3
    assert e["je_grund"].get("menge_ohne_bekannte_person") == 1
    assert e["vektoren"].shape == (3, D)
    assert e["gesichter"][0]["aufnahme"].startswith("2019")
    assert e["gesichter"][2]["video_id"] == "99" and e["gesichter"][2]["zeit_s"] == 4.0
    with pytest.raises(pg.PersonenFehler):
        pg.gesichter_lesen([str(tmp_path / "fehlt.jsonl")])


def test_main_trocken_schreibt_nichts_und_schreiben_ohne_vektoren(tmp_path, capsys):
    rng = np.random.default_rng(41)
    mitten = [_mitte(rng) for _ in range(2)]
    datei = tmp_path / "v.jsonl"
    zeilen = [_zeile(f"{p}_{i}", [_gesicht(rng, mitten[p])]) for p in range(2) for i in range(6)]
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    aus = tmp_path / "gruppen"
    leer = str(tmp_path / "keine.json")
    grund = ["--vektoren", str(datei), "--ausgabe", str(aus),
             "--bestaetigt", leer, "--vorgaben", leer]
    assert pg.main(grund) == 0
    assert not aus.exists()
    assert "NICHTS geschrieben" in capsys.readouterr().out
    assert pg.main(grund + ["--schreiben"]) == 0
    zuordnung = (aus / pg.DATEI_ZUORDNUNG).read_text(encoding="utf-8").splitlines()
    assert len(zuordnung) == 12
    zeile = json.loads(zuordnung[0])
    assert set(zeile) == set(pg.FELDER_ZUORDNUNG) and "embedding" not in zeile
    beispiele = json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert len(beispiele["gruppen"]) == 2
    assert '"mittelpunkt":' not in json.dumps(beispiele)
    assert (aus / pg.DATEI_KENNUNGEN).exists()
    # Zweiter Lauf: dieselben Kennungen, nichts neu.
    assert pg.main(grund + ["--schreiben"]) == 0
    zweit = json.loads((aus / pg.DATEI_BEISPIELE).read_text(encoding="utf-8"))
    assert [g["kennung"] for g in zweit["gruppen"]] == [g["kennung"] for g in beispiele["gruppen"]]
    assert all(not g["neu"] for g in zweit["gruppen"])


def test_ausgabe_im_repo_wird_verweigert():
    with pytest.raises(SystemExit) as ende:
        pg.main(["--ausgabe", os.path.join(BACKEND, "gruppen_test")])
    assert ende.value.code == 2


def test_bericht_nur_zahlen_keine_namen():
    v, bilder, _, _ = _szene(personen=2, je_person=6, seed=43)
    lauf = pg.lauf_rechnen(_eingelesen(v, bilder), bestaetigt={"Person_001": "Geheimname"})
    text = pg.bericht_text(lauf["bericht"])
    assert "Geheimname" not in text and "Person_" not in text


# ── Nutzer-Regel „dieses Gesicht ist nicht diese Person" (02.10.2026) ──────

def test_ausgeschlossenes_gesicht_kommt_nicht_mehr_in_den_vorschlag():
    v, bilder, _, _ = _szene(personen=2, je_person=12, seed=31)
    erst = pg.lauf_rechnen(_eingelesen(v, bilder))
    gruppe = erst["gruppen"][0]
    k = gruppe["kennung"]
    opfer = next(g for g in erst["gesichter"] if g["kennung"] == k)
    regel = (k, str(opfer["bild_id"]), int(opfer["index"]))
    mit = pg.lauf_rechnen(_eingelesen(v, bilder), altbestand=erst["altbestand"],
                          vorgaben={"gleich": set(), "verschieden": set(), "ausgeschlossen": {regel}})
    nachher = next(g for g in mit["gesichter"]
                   if g["bild_id"] == opfer["bild_id"] and g["index"] == opfer["index"])
    assert nachher["kennung"] != k
    assert mit["bericht"]["ausgeschlossen_nach_regel"] == 1
    assert next(g for g in mit["gruppen"] if g["kennung"] == k)["groesse"] == gruppe["groesse"] - 1
    assert "Nutzer-Regel" in pg.bericht_text(mit["bericht"])


def test_vorgaben_lesen_kennt_ausschluesse(tmp_path):
    pfad = tmp_path / "personen_vorgaben.json"
    pfad.write_text(json.dumps({"gleich": [["Person_1001", "Person_1002"]], "verschieden": [],
                                "ausgeschlossen": [{"kennung": "Person_1001", "bild_id": "123", "index": 2},
                                                   {"kennung": "", "bild_id": "1", "index": 0},
                                                   {"kennung": "Person_1001", "bild_id": "abc"}]}),
                    encoding="utf-8")
    v = pg.vorgaben_lesen(str(pfad))
    assert v["ausgeschlossen"] == {("Person_1001", "123", 2)}
    assert v["gleich"] == {("Person_1001", "Person_1002")}
