"""Tests: Gruppierung v2, Schritt 4 - Sicherungen, transaktionales Schreiben, Rueckrollen.

Auflage 4 der Plan-Fassung 5.3 in der verbindlichen Fassung 4: statt ``*.vorher_<stempel>``
und ``ROLLEN.json`` legt jeder v2-Schreiblauf einen Bereitstellungsordner
``.v2_<stempel>/`` an (``vorher/``, ``neu/``, ``stand.json``, Richtungsmarke,
``fortschritt/``), spielt die vier Dateien (Zuordnung, Beispiele, Kennungen,
Aliasmengen) einzeln und wiederaufnehmbar ein und kennt ``--weiter`` und
``--rueckrollen <stempel>``. Nichts wird je geloescht, nur verschoben.

Alles offline, nur mit ERFUNDENEN Laeufen (kleine Woerterbuecher) in ``tmp_path``. Keine
echten Namen, keine echten Pfade, keine Vektoren. Der Standard-Manifestpfad wird nie
beruehrt: jeder Aufruf bekommt ein Manifest in ``tmp_path`` (und ``conftest.py`` lenkt den
Standard in einen tmp-Ordner um).

Abbruchtests nutzen die vier Naehte ``_ersetzen``, ``_kopieren``, ``_umbenennen`` und
``_marke_schreiben``: sie werfen an einer genau bezeichneten Stelle ``Abbruch``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_gruppierung_v2_transaktion.py -q
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
WERKZEUGE = os.path.join(os.path.dirname(BACKEND), "tools", "foto_sortierung")
sys.path.insert(0, WERKZEUGE)


def _laden(name):
    spez = importlib.util.spec_from_file_location(name, os.path.join(WERKZEUGE, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


pg = _laden("personen_gruppieren")
ZUO, BEI, KEN, ALI = pg.V2_DATEIEN


class Abbruch(Exception):
    """Der eingeschleuste Abbruch (Absturz) an einer Naht."""


# ── Hilfen ──────────────────────────────────────────────────────────────────

def ST(i):
    """Ein erfundener, aufsteigender Stempel."""
    return f"20261021_1200{i:02d}"


def _norm(pfad):
    return str(pfad).replace("\\", "/")


def _lauf(n):
    """Ein erfundener v2-Lauf; jede Zahl ``n`` gibt in allen vier Dateien anderen Inhalt."""
    kennung = f"Person_{n:03d}"
    gesichter = [{"bild_id": f"b{n}_{i}", "index": 0, "kennung": kennung, "bbox": [1, 2, 3, 4],
                  "breite": 100, "hoehe": 100, "anteil": 0.1, "score": 0.9,
                  "aufnahme": None, "video_id": None, "zeit_s": None} for i in range(2)]
    return {"verfahren": "v2", "gesichter": gesichter,
            "gruppen": [{"kennung": kennung, "groesse": n}],
            "altbestand": [{"kennung": kennung, "mittelpunkt": [float(n)]}],
            "aliasmengen": {kennung: [kennung, f"Person_{n + 100:03d}"]}}


def _ausgang(ziel, n=0, mit_aliase=False):
    """Einen vorhandenen Stand anlegen: drei Pflichtdateien (und optional ``aliasmengen.json``)."""
    lauf = _lauf(n)
    if not mit_aliase:
        lauf["verfahren"] = "v1"                 # schreibt nur die drei Dateien
    pg.schreiben(lauf, str(ziel), stand=f"S{n}")


def _szenario(ziel, art):
    if art == "gefuellt":                         # drei Pflichtdateien da, Aliasmengen fehlen
        _ausgang(ziel)
    return _inhalt(ziel)


def _schreibe(ziel, manifest, n, i, **kw):
    return pg.v2_schreiben(_lauf(n), str(ziel), str(manifest), stempel=ST(i), stand=f"S{n}", **kw)


def _inhalt(ziel):
    """Die Bytes der vier Zieldateien (``None`` = fehlt)."""
    erg = {}
    for name in pg.V2_DATEIEN:
        pfad = Path(ziel) / name
        erg[name] = pfad.read_bytes() if pfad.is_file() else None
    return erg


def _snap(wurzel):
    """Alles unter ``wurzel``: Pfad -> Hash bzw. ``"D"`` fuer Ordner."""
    erg = {}
    for ordner, ordner_namen, dateien in os.walk(wurzel):
        for n in ordner_namen:
            erg[os.path.relpath(os.path.join(ordner, n), wurzel)] = "D"
        for n in dateien:
            pfad = os.path.join(ordner, n)
            with open(pfad, "rb") as f:
                erg[os.path.relpath(pfad, wurzel)] = hashlib.sha256(f.read()).hexdigest()
    return erg


def _eintraege(ziel):
    return [(e["stempel"], e["art"]) for e in pg.v2_zustand(str(ziel))]


def _neu_inhalt(tmp_path, n):
    """Was ein sauberer Lauf in einen leeren Ordner schreibt (Referenz)."""
    ziel = tmp_path / "referenz"
    assert pg.v2_schreiben(_lauf(n), str(ziel), str(tmp_path / "referenz.jsonl"),
                           stempel=ST(1), stand=f"S{n}") == 0
    return _inhalt(ziel)


def _manifest_zeilen(pfad):
    if not Path(pfad).is_file():
        return []
    zeilen = []
    for roh in Path(pfad).read_bytes().split(b"\n"):
        if roh.strip():
            try:
                zeilen.append(json.loads(roh.decode("utf-8")))
            except ValueError:
                pass
    return zeilen


def _reste(ziel):
    """Alles im Zielordner, was weder eine der vier Dateien noch ein ``.v2_*``-Ordner ist."""
    erlaubt = set(pg.V2_DATEIEN)
    return [n for n in sorted(os.listdir(ziel)) if n not in erlaubt and not n.startswith(".v2_")]


@contextlib.contextmanager
def _abbruch(naht, endung, vorher=False):
    """Wirft ``Abbruch`` NACH (oder mit ``vorher=True`` VOR) dem Aufruf der Naht ``naht``,
    dessen Ziel auf ``/<endung>`` endet."""
    with pytest.MonkeyPatch.context() as mp:
        original = getattr(pg, naht)

        def huelle(*args, **kw):
            ziel = args[0] if naht == "_marke_schreiben" else args[-1]
            treffer = _norm(ziel).endswith("/" + endung)
            if treffer and vorher:
                raise Abbruch(naht)
            ergebnis = original(*args, **kw)
            if treffer:
                raise Abbruch(naht)
            return ergebnis

        mp.setattr(pg, naht, huelle)
        yield


def _einspiel_haken(name, schritt, i=1):
    return {"tmp": ("_kopieren", f"{name}.tmp_{ST(i)}"),
            "beginn": ("_marke_schreiben", f"fortschritt/{name}.beginn"),
            "ersetzt": ("_ersetzen", name),
            "eingespielt": ("_marke_schreiben", f"fortschritt/{name}.eingespielt")}[schritt]


def _abgebrochen_schreiben(ziel, manifest, naht, endung, n=1, i=1, vorher=False):
    with _abbruch(naht, endung, vorher=vorher):
        with pytest.raises(Abbruch):
            _schreibe(ziel, manifest, n, i)


# ── 1. Rundlauf und Grundverhalten ──────────────────────────────────────────

def test_rundlauf_schreiben_und_rueckrollen_stellt_inhalt_und_sha256_wieder_her(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel, mit_aliase=True)
    vorher = _inhalt(ziel)
    hashes = {n: hashlib.sha256(b).hexdigest() for n, b in vorher.items()}
    assert _schreibe(ziel, m, 1, 1) == 0
    nachher = _inhalt(ziel)
    assert all(nachher[n] != vorher[n] for n in pg.V2_DATEIEN)
    assert _eintraege(ziel) == [(ST(1), "FERTIG")]
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    zurueck = _inhalt(ziel)
    assert zurueck == vorher
    assert {n: hashlib.sha256(b).hexdigest() for n, b in zurueck.items()} == hashes
    assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]
    ordner = Path(ziel) / f".v2_{ST(1)}.zurueckgerollt"
    assert sorted(os.listdir(ordner / "neu")) == sorted(pg.V2_DATEIEN)        # neu/ bleibt
    assert sorted(os.listdir(ordner / "vorher")) == sorted(pg.V2_DATEIEN)
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt", "zurueckgerollt"]


def test_erster_lauf_in_leeren_ordner_dann_rueckrollen_laesst_nur_verworfenes(tmp_path):
    ziel, m = tmp_path / "gibt_es_noch_nicht", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    neu = _inhalt(ziel)
    assert all(b is not None for b in neu.values())
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == {n: None for n in pg.V2_DATEIEN}                  # nichts mehr im Ziel
    for name in pg.V2_DATEIEN:
        verworfen = Path(ziel) / f"{name}.verworfen_{ST(1)}"
        assert verworfen.read_bytes() == neu[name]                            # nur verschoben
    assert not [n for n in os.listdir(ziel) if ".tmp_" in n and not n.endswith(".verworfen")]


def test_vorher_allein_vorhandene_aliasmengen_sind_nach_dem_rueckrollen_exakt_wieder_da(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    ziel.mkdir()
    (ziel / ALI).write_bytes(b'{"Person_900": ["Person_900"]}\n')
    vorher = (ziel / ALI).read_bytes()
    assert _schreibe(ziel, m, 1, 1) == 0                       # erster Lauf: die drei fehlen alle
    assert (ziel / ALI).read_bytes() != vorher
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert (ziel / ALI).read_bytes() == vorher
    assert all(not (ziel / n).exists() for n in pg.V2_PFLICHT)


def test_unveraenderte_dateien_gelten_als_erledigt_und_werden_nicht_angefasst(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    assert _schreibe(ziel, m, 1, 2) == 0                        # gleicher Lauf, gleicher Stand
    ordner = Path(ziel) / f".v2_{ST(2)}.fertig"
    stand = json.loads((ordner / "stand.json").read_text(encoding="utf-8"))
    assert all(d["vorher_sha256"] == d["neu_sha256"] for d in stand["dateien"])
    assert not (ordner / "fortschritt").exists()                # kein einziger Schritt noetig
    assert not [n for n in os.listdir(ziel) if ".tmp_" in n or ".verworfen" in n]
    vorher = _inhalt(ziel)
    assert pg.v2_rueckrollen(str(ziel), ST(2), str(m)) == 0
    assert _inhalt(ziel) == vorher


def test_stempel_format_ordnernamen_und_stand_json(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    assert _schreibe(ziel, m, 1, 1) == 0
    ordner = Path(ziel) / f".v2_{ST(1)}.fertig"
    stand = json.loads((ordner / "stand.json").read_text(encoding="utf-8"))
    assert stand["stempel"] == ST(1)
    assert [d["name"] for d in stand["dateien"]] == list(pg.V2_DATEIEN)
    assert stand["dateien"][3]["vorher_sha256"] is None         # Aliasmengen fehlten vorher
    for d in stand["dateien"]:
        assert d["neu_sha256"] == hashlib.sha256((ordner / "neu" / d["name"]).read_bytes()).hexdigest()
    assert (ordner / "EINSPIELEN").is_file()
    assert (ordner / "fortschritt" / f"{ZUO}.eingespielt").is_file()


# ── 2. Vorpruefung: teilweise Pflichtdateien, Kollisionen, Stempel ──────────

@pytest.mark.parametrize("vorhanden", [(ZUO,), (BEI,), (KEN,), (ZUO, BEI), (ZUO, KEN), (BEI, KEN)])
def test_nur_ein_teil_der_pflichtdateien_ist_exit_2_und_legt_nichts_an(tmp_path, vorhanden, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    ziel.mkdir()
    for name in vorhanden:
        (ziel / name).write_text("x\n", encoding="utf-8")
    vorher = _snap(tmp_path)
    assert _schreibe(ziel, m, 1, 1) == 2
    assert _snap(tmp_path) == vorher
    assert not m.exists()


DIR_KOLLISIONEN = [f".v2_{ST(5)}", f".v2_{ST(5)}.fertig", f".v2_{ST(5)}.zurueckgerollt",
                   f".v2_{ST(5)}.unfertig"]
DATEI_KOLLISIONEN = [f"{n}{s}" for n in pg.V2_DATEIEN
                     for s in (f".tmp_{ST(5)}", f".tmp_{ST(5)}.verworfen", f".verworfen_{ST(5)}")]


@pytest.mark.parametrize("name", DIR_KOLLISIONEN + DATEI_KOLLISIONEN)
def test_kollision_bei_jedem_namen_ist_exit_2_ohne_aenderung(tmp_path, name):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    if name in DIR_KOLLISIONEN:
        (ziel / name).mkdir()
    else:
        (ziel / name).write_text("fremd\n", encoding="utf-8")
    vorher = _snap(tmp_path)
    assert _schreibe(ziel, m, 1, 5) == 2
    assert _snap(tmp_path) == vorher               # Ordnerliste und Ziel unveraendert
    assert not m.exists()


def test_ein_stempel_der_nicht_juenger_ist_wird_abgelehnt(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 5) == 0
    for i in (5, 4):                                # gleich und aelter
        vorher = _snap(tmp_path)
        assert _schreibe(ziel, m, 2, i) == 2
        assert _snap(tmp_path) == vorher
    assert _schreibe(ziel, m, 2, 6) == 0


def test_ungueltiger_stempel_und_unbekannter_v2_eintrag_sind_exit_2(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    ziel.mkdir()
    assert pg.v2_schreiben(_lauf(1), str(ziel), str(m), stempel="a.b") == 2
    assert pg.v2_schreiben(_lauf(1), str(ziel), str(m), stempel="a/b") == 2
    (ziel / ".v2_wirr.x.y").mkdir()
    vorher = _snap(tmp_path)
    assert _schreibe(ziel, m, 1, 1) == 2
    assert _snap(tmp_path) == vorher


# ── 3. Abbrueche beim Einspielen: --weiter UND --rueckrollen ────────────────

AUSGAENGE = ["leer", "gefuellt"]
EINSPIEL_FAELLE = [(a, n, s) for a in AUSGAENGE for n in (ZUO, BEI, ALI)
                   for s in ("tmp", "beginn", "ersetzt", "eingespielt")]
EINSPIEL_IDS = [f"{a}-{n.split('_')[0].split('.')[0]}-{s}" for a, n, s in EINSPIEL_FAELLE]


@pytest.mark.parametrize("fall", EINSPIEL_FAELLE, ids=EINSPIEL_IDS)
def test_abbruch_beim_einspielen_dann_weiter_ergibt_den_neuen_stand(tmp_path, fall):
    ausgang, name, schritt = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _szenario(ziel, ausgang)
    naht, endung = _einspiel_haken(name, schritt)
    _abgebrochen_schreiben(ziel, m, naht, endung)
    assert _eintraege(ziel) == [(ST(1), "BEREIT")]
    snap = _snap(tmp_path)
    assert _schreibe(ziel, m, 2, 2) == 2                        # ein neuer Lauf wird verweigert
    assert _snap(tmp_path) == snap
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert _eintraege(ziel) == [(ST(1), "FERTIG")]
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)            # nichts verloren, alles neu
    assert _reste(ziel) == []
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt"]
    assert pg.v2_weiter(str(ziel), str(m)) == 0                 # wiederholbar
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt"]


@pytest.mark.parametrize("fall", EINSPIEL_FAELLE, ids=EINSPIEL_IDS)
def test_abbruch_beim_einspielen_dann_rueckrollen_ergibt_den_ausgangsstand(tmp_path, fall):
    ausgang, name, schritt = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, ausgang)
    naht, endung = _einspiel_haken(name, schritt)
    _abgebrochen_schreiben(ziel, m, naht, endung)
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start                               # exakt der Ausgangsstand
    assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]
    assert not [n for n in os.listdir(ziel) if ".tmp_" in n and not n.endswith(".verworfen")]
    assert (Path(ziel) / f".v2_{ST(1)}.zurueckgerollt" / "neu").is_dir()
    assert [z["art"] for z in _manifest_zeilen(m)] == ["zurueckgerollt"]


SONST_FAELLE = [
    ("marker_einspielen", "_marke_schreiben", "EINSPIELEN", False),
    ("vor_fertig", "_umbenennen", f".v2_{ST(1)}.fertig", True),
    ("nach_fertig", "_umbenennen", f".v2_{ST(1)}.fertig", False),
]


@pytest.mark.parametrize("ausgang", AUSGAENGE)
@pytest.mark.parametrize("fall", SONST_FAELLE, ids=[f[0] for f in SONST_FAELLE])
def test_abbruch_an_den_raendern_weiter_und_rueckrollen(tmp_path, ausgang, fall):
    _, naht, endung, vorher = fall
    for weg in ("weiter", "rueckrollen"):
        ziel, m = tmp_path / weg / "ziel", tmp_path / weg / "m.jsonl"
        start = _szenario(ziel, ausgang)
        _abgebrochen_schreiben(ziel, m, naht, endung, vorher=vorher)
        if weg == "weiter":
            assert pg.v2_weiter(str(ziel), str(m)) == 0
            assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)
            assert _eintraege(ziel) == [(ST(1), "FERTIG")]
            assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt"]   # genau einmal
        else:
            assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
            assert _inhalt(ziel) == start
            assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]


# ── 4. Abbruch beim Bereitstellen (UNFERTIG) ────────────────────────────────

BEREITSTELL_FAELLE = [
    ("vor_der_ersten_kopie", "_kopieren", f"vorher/{ZUO}", True),
    ("nach_der_ersten_kopie", "_kopieren", f"vorher/{ZUO}", False),
    ("vor_stand_json", "_marke_schreiben", "stand.json", True),
]


@pytest.mark.parametrize("fall", BEREITSTELL_FAELLE, ids=[f[0] for f in BEREITSTELL_FAELLE])
def test_abbruch_beim_bereitstellen_unfertig_weiter_rueckrollen_und_naechster_lauf(
        tmp_path, fall, capsys):
    _, naht, endung, vorher = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, "gefuellt")
    _abgebrochen_schreiben(ziel, m, naht, endung, vorher=vorher)
    assert _eintraege(ziel) == [(ST(1), "UNFERTIG")]
    assert not (Path(ziel) / f".v2_{ST(1)}" / "stand.json").exists()
    snap = _snap(tmp_path)
    capsys.readouterr()
    # --weiter: Exit 0 mit Hinweiszeile, nichts verschoben, Ziele unveraendert
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert f"UNFERTIG {ST(1)}: Ziele unverändert, der nächste schreibende Lauf räumt ihn weg" \
        in capsys.readouterr().out
    assert _snap(tmp_path) == snap
    # --rueckrollen: Exit 2 mit derselben Hinweiszeile, nichts geaendert
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2
    assert "UNFERTIG" in capsys.readouterr().out
    assert _snap(tmp_path) == snap
    assert _inhalt(ziel) == start
    # der naechste schreibende Lauf raeumt den Ordner weg und schreibt
    assert _schreibe(ziel, m, 1, 2) == 0
    assert _eintraege(ziel) == [(ST(1), "VERSCHOBEN"), (ST(2), "FERTIG")]
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)


def test_unfertig_ziel_fremd_belegt_der_schreibende_lauf_endet_mit_exit_2(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    _abgebrochen_schreiben(ziel, m, "_marke_schreiben", "stand.json", vorher=True)
    (Path(ziel) / f".v2_{ST(1)}.unfertig").mkdir()              # fremd belegt
    snap = _snap(tmp_path)
    assert _schreibe(ziel, m, 1, 2) == 2
    assert _snap(tmp_path) == snap
    assert pg.v2_weiter(str(ziel), str(m)) == 2                 # Vorpruefung jedes Wegs
    assert _snap(tmp_path) == snap


def test_unfertig_und_bereit_gleichzeitig_schreibender_lauf_exit_2_unfertig_bleibt(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    _abgebrochen_schreiben(ziel, m, "_kopieren", f"{ZUO}.tmp_{ST(1)}")
    (Path(ziel) / f".v2_{ST(3)}").mkdir()                       # ein UNFERTIG-Ordner dazu
    snap = _snap(tmp_path)
    assert sorted(_eintraege(ziel)) == [(ST(1), "BEREIT"), (ST(3), "UNFERTIG")]
    assert _schreibe(ziel, m, 2, 4) == 2
    assert _snap(tmp_path) == snap                              # UNFERTIG nicht verschoben
    assert (Path(ziel) / f".v2_{ST(3)}").is_dir()


def test_zwei_bereit_ordner_weiter_ist_exit_2(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    _abgebrochen_schreiben(ziel, m, "_kopieren", f"{ZUO}.tmp_{ST(1)}")
    zweiter = Path(ziel) / f".v2_{ST(3)}"
    zweiter.mkdir()
    (zweiter / "stand.json").write_text("{}", encoding="utf-8")   # zaehlt als BEREIT
    snap = _snap(tmp_path)
    assert pg.v2_weiter(str(ziel), str(m)) == 2
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2
    assert _snap(tmp_path) == snap


# ── 5. Abbrueche beim Rueckrollen ───────────────────────────────────────────

def _rueck_haken(name, schritt, i=1):
    return {"tmp": ("_kopieren", f"{name}.tmp_{ST(i)}"),
            "rueck_beginn": ("_marke_schreiben", f"fortschritt/{name}.rueck_beginn"),
            "ersetzt": ("_ersetzen", name),
            "verworfen": ("_umbenennen", f"{name}.verworfen_{ST(i)}"),
            "tmp_verschoben": ("_umbenennen", f"{name}.tmp_{ST(i)}.verworfen"),
            "zurueckgerollt": ("_marke_schreiben", f"fortschritt/{name}.zurueckgerollt")}[schritt]


MIT_VORHER = ("tmp", "rueck_beginn", "ersetzt", "zurueckgerollt")
OHNE_VORHER = ("rueck_beginn", "verworfen", "zurueckgerollt")
RUECK_FAELLE = (
    [("gefuellt", n, s) for n in (ZUO, BEI, KEN) for s in MIT_VORHER]
    + [("gefuellt", ALI, s) for s in OHNE_VORHER]
    + [("leer", n, s) for n in (ZUO, ALI) for s in OHNE_VORHER])
RUECK_IDS = [f"{a}-{n.split('_')[0].split('.')[0]}-{s}" for a, n, s in RUECK_FAELLE]


@pytest.mark.parametrize("fall", RUECK_FAELLE, ids=RUECK_IDS)
def test_abbruch_beim_rueckrollen_erneutes_rueckrollen_vollendet(tmp_path, fall):
    ausgang, name, schritt = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, ausgang)
    assert _schreibe(ziel, m, 1, 1) == 0
    naht, endung = _rueck_haken(name, schritt)
    with _abbruch(naht, endung):
        with pytest.raises(Abbruch):
            pg.v2_rueckrollen(str(ziel), ST(1), str(m))
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start
    assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]
    assert not [n for n in os.listdir(ziel) if ".tmp_" in n and not n.endswith(".verworfen")]
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt", "zurueckgerollt"]


RTMP_FAELLE = [(a, n, s) for a, n in (("leer", ZUO), ("leer", ALI), ("gefuellt", ZUO),
                                      ("gefuellt", ALI))
               for s in ("rueck_beginn", "tmp_verschoben", "zurueckgerollt")]
RTMP_IDS = [f"{a}-{n.split('_')[0].split('.')[0]}-{s}" for a, n, s in RTMP_FAELLE]


@pytest.mark.parametrize("fall", RTMP_FAELLE, ids=RTMP_IDS)
def test_einspiel_tmp_wird_verschoben_abbruch_nach_jedem_schritt_vollendbar(tmp_path, fall):
    """Schritt R-tmp (und sein Gegenstueck bei vorher != null): die Einspiel-Zwischenkopie liegt,
    das Ziel wurde nie ersetzt; ein Abbruch nach jedem Teilschritt ist eindeutig."""
    ausgang, name, schritt = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, ausgang)
    _abgebrochen_schreiben(ziel, m, "_kopieren", f"{name}.tmp_{ST(1)}")      # nach 5.3 (a)
    assert (Path(ziel) / f"{name}.tmp_{ST(1)}").is_file()
    naht, endung = _rueck_haken(name, schritt)
    with _abbruch(naht, endung):
        with pytest.raises(Abbruch):
            pg.v2_rueckrollen(str(ziel), ST(1), str(m))
    if schritt == "tmp_verschoben":
        assert (Path(ziel) / f"{name}.tmp_{ST(1)}.verworfen").is_file()      # direkt danach
        assert not (Path(ziel) / f"{name}.tmp_{ST(1)}").exists()
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start
    assert (Path(ziel) / f"{name}.tmp_{ST(1)}.verworfen").is_file()
    assert not (Path(ziel) / f"{name}.tmp_{ST(1)}").exists()


RAND_RUECK = [
    ("marker_rueckrollen", "_marke_schreiben", "RUECKROLLEN", False),
    ("vor_zurueckgerollt_umbenennen", "_umbenennen", f".v2_{ST(1)}.zurueckgerollt", True),
    ("nach_zurueckgerollt_umbenennen", "_umbenennen", f".v2_{ST(1)}.zurueckgerollt", False),
]


@pytest.mark.parametrize("ausgang", AUSGAENGE)
@pytest.mark.parametrize("fall", RAND_RUECK, ids=[f[0] for f in RAND_RUECK])
def test_abbruch_am_ende_des_rueckrollens(tmp_path, ausgang, fall):
    _, naht, endung, vorher = fall
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, ausgang)
    assert _schreibe(ziel, m, 1, 1) == 0
    with _abbruch(naht, endung, vorher=vorher):
        with pytest.raises(Abbruch):
            pg.v2_rueckrollen(str(ziel), ST(1), str(m))
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start
    assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt", "zurueckgerollt"]


def test_richtung_rueckrollen_eines_bereit_ordners_sperrt_weiter(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, "gefuellt")
    _abgebrochen_schreiben(ziel, m, "_ersetzen", ZUO)                        # Zuordnung ersetzt
    with _abbruch("_marke_schreiben", f"fortschritt/{ZUO}.rueck_beginn"):
        with pytest.raises(Abbruch):
            pg.v2_rueckrollen(str(ziel), ST(1), str(m))
    assert (Path(ziel) / f".v2_{ST(1)}" / "RUECKROLLEN").is_file()
    snap = _snap(tmp_path)
    assert pg.v2_weiter(str(ziel), str(m)) == 2                              # Richtung gesperrt
    assert _snap(tmp_path) == snap
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0                  # vollendet
    assert _inhalt(ziel) == start


# ── 6. FREMD: Exit 2 ohne jede Aenderung (weiter und rueckrollen) ───────────

def _fremd_bereit(tmp_path, ausgang, naht, endung):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _szenario(ziel, ausgang)
    _abgebrochen_schreiben(ziel, m, naht, endung)
    return ziel, m, Path(ziel) / f".v2_{ST(1)}"


def _beide_wege_exit_2(ziel, m, tmp_path):
    snap = _snap(tmp_path)
    assert pg.v2_weiter(str(ziel), str(m)) == 2
    assert _snap(tmp_path) == snap
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2
    assert _snap(tmp_path) == snap


@pytest.mark.parametrize("name", [ZUO, BEI, KEN])
def test_fremd_geaenderte_zieldatei(tmp_path, name):
    # Zuordnung ist schon auf neu, Beispiele/Kennungen stehen noch auf vorher.
    ziel, m, _ = _fremd_bereit(tmp_path, "gefuellt", "_marke_schreiben",
                               f"fortschritt/{ZUO}.eingespielt")
    (Path(ziel) / name).write_text("von aussen geaendert\n", encoding="utf-8")
    _beide_wege_exit_2(ziel, m, tmp_path)


@pytest.mark.parametrize("wo", [f"vorher/{BEI}", f"neu/{KEN}", f"neu/{ALI}", f"neu/{ZUO}"])
def test_fremd_manipulierte_vorher_oder_neu_datei(tmp_path, wo):
    ziel, m, ordner = _fremd_bereit(tmp_path, "gefuellt", "_marke_schreiben",
                                    f"fortschritt/{ZUO}.eingespielt")
    (ordner / wo).write_bytes((ordner / wo).read_bytes() + b"manipuliert\n")
    _beide_wege_exit_2(ziel, m, tmp_path)


@pytest.mark.parametrize("ausgang,name", [("gefuellt", BEI), ("leer", ZUO), ("gefuellt", ALI)])
def test_fremd_fremde_tmp_kopie_mit_falschem_hash(tmp_path, ausgang, name):
    ziel, m, _ = _fremd_bereit(tmp_path, ausgang, "_kopieren", f"{name}.tmp_{ST(1)}")
    (Path(ziel) / f"{name}.tmp_{ST(1)}").write_text("fremde Kopie\n", encoding="utf-8")
    _beide_wege_exit_2(ziel, m, tmp_path)


def test_fremd_nach_dem_einspielen_von_aussen_geloeschte_vorher_null_datei(tmp_path):
    ziel, m, _ = _fremd_bereit(tmp_path, "leer", "_marke_schreiben",
                               f"fortschritt/{ZUO}.eingespielt")
    (Path(ziel) / ZUO).unlink()                  # vorher null, schon eingespielt, nun weg
    _beide_wege_exit_2(ziel, m, tmp_path)


def test_fremd_rueckroll_namen_beim_einspielen_und_fremder_verwerf_name(tmp_path):
    ziel, m, _ = _fremd_bereit(tmp_path, "leer", "_marke_schreiben",
                               f"fortschritt/{ZUO}.eingespielt")
    (Path(ziel) / f"{BEI}.verworfen_{ST(1)}").write_text("fremd\n", encoding="utf-8")
    _beide_wege_exit_2(ziel, m, tmp_path)


# ── 7. Manipulation zwischen Bereitstellen und Einspielen (Pruefung 5.2b) ───

def _nach_stand_json(aktion):
    """Fuehrt ``aktion`` aus, sobald ``stand.json`` geschrieben ist (eingeschleuster Haken)."""
    mp = pytest.MonkeyPatch()
    original = pg._marke_schreiben

    def huelle(pfad, *a, **kw):
        ergebnis = original(pfad, *a, **kw)
        if _norm(pfad).endswith("/stand.json"):
            aktion()
        return ergebnis

    mp.setattr(pg, "_marke_schreiben", huelle)
    return mp


@pytest.mark.parametrize("fall", ["ziel_geaendert", "null_datei_angelegt",
                                  "vorher_manipuliert", "neu_manipuliert"])
def test_manipulation_vor_dem_einspielen_exit_2_dann_rueckrollen(tmp_path, fall):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, "gefuellt")
    ordner = Path(ziel) / f".v2_{ST(1)}"
    ziel_datei = Path(ziel) / BEI
    original = ziel_datei.read_bytes()
    vorher_datei = ordner / "vorher" / ZUO
    neu_datei = ordner / "neu" / KEN
    manip = {}

    def einschleusen():
        if fall == "ziel_geaendert":
            ziel_datei.write_bytes(b"von aussen\n")
        elif fall == "null_datei_angelegt":
            (Path(ziel) / ALI).write_bytes(b"von aussen\n")
        elif fall == "vorher_manipuliert":
            manip["vorher"] = vorher_datei.read_bytes()
            vorher_datei.write_bytes(manip["vorher"] + b"x")
        else:
            manip["neu"] = neu_datei.read_bytes()
            neu_datei.write_bytes(manip["neu"] + b"x")

    mp = _nach_stand_json(einschleusen)
    try:
        assert _schreibe(ziel, m, 1, 1) == 2
    finally:
        mp.undo()
    assert _eintraege(ziel) == [(ST(1), "BEREIT")]
    assert not (ordner / "EINSPIELEN").exists()                  # nie gesetzt
    assert not (ordner / "fortschritt").exists()
    assert not [n for n in os.listdir(ziel) if ".tmp_" in n]
    # Die Zieldateien sind genau so, wie die Manipulation sie hinterliess (nichts eingespielt).
    erwartet = dict(start)
    if fall == "ziel_geaendert":
        erwartet[BEI] = b"von aussen\n"
    elif fall == "null_datei_angelegt":
        erwartet[ALI] = b"von aussen\n"
    assert _inhalt(ziel) == erwartet
    snap = _snap(tmp_path)
    # Solange die Aenderung besteht: --rueckrollen und --weiter sind Exit 2 ohne Aenderung.
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2
    assert pg.v2_weiter(str(ziel), str(m)) == 2
    assert _snap(tmp_path) == snap
    # Aenderung zuruecknehmen, dann loest --rueckrollen den Ordner ohne Zieländerung auf.
    if fall == "ziel_geaendert":
        ziel_datei.write_bytes(original)
    elif fall == "null_datei_angelegt":
        (Path(ziel) / ALI).unlink()
    elif fall == "vorher_manipuliert":
        vorher_datei.write_bytes(manip["vorher"])
    else:
        neu_datei.write_bytes(manip["neu"])
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _eintraege(ziel) == [(ST(1), "ZURUECKGEROLLT")]
    assert _inhalt(ziel) == start


def test_nach_rueckgenommener_manipulation_kann_weiter_einspielen(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _szenario(ziel, "gefuellt")
    datei = Path(ziel) / KEN
    original = datei.read_bytes()
    mp = _nach_stand_json(lambda: datei.write_bytes(b"von aussen\n"))
    try:
        assert _schreibe(ziel, m, 1, 1) == 2
    finally:
        mp.undo()
    datei.write_bytes(original)
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)


# ── 8. Reihenfolge der Staende ──────────────────────────────────────────────

def test_rueckrollen_nur_in_umgekehrter_reihenfolge(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel, mit_aliase=True)
    ursprung = _inhalt(ziel)
    assert _schreibe(ziel, m, 1, 1) == 0
    nach_eins = _inhalt(ziel)
    assert _schreibe(ziel, m, 2, 2) == 0
    snap = _snap(tmp_path)
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2                  # nicht der juengste
    assert _snap(tmp_path) == snap
    assert pg.v2_rueckrollen(str(ziel), ST(2), str(m)) == 0
    assert _inhalt(ziel) == nach_eins
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == ursprung                                         # der Ursprung ist da
    snap = _snap(tmp_path)
    assert pg.v2_rueckrollen(str(ziel), ST(2), str(m)) == 2                  # schon zurueckgerollt
    assert _snap(tmp_path) == snap
    assert [z["art"] for z in _manifest_zeilen(m)] == [
        "eingespielt", "eingespielt", "zurueckgerollt", "zurueckgerollt"]


def test_unbekannter_stempel_und_ungueltiger_stempel_beim_rueckrollen(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    snap = _snap(tmp_path)
    assert pg.v2_rueckrollen(str(ziel), ST(9), str(m)) == 2
    assert pg.v2_rueckrollen(str(ziel), "a/../b", str(m)) == 2
    assert pg.v2_rueckrollen(str(ziel), "", str(m)) == 2
    assert _snap(tmp_path) == snap


# ── 9. Manifest ─────────────────────────────────────────────────────────────

def test_manifest_eine_zeile_je_ereignis_mit_allen_feldern(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    assert _schreibe(ziel, m, 1, 1) == 0
    zeilen = _manifest_zeilen(m)
    assert len(zeilen) == 1 and Path(m).read_bytes().endswith(b"\n")
    z = zeilen[0]
    assert set(z) == {"art", "stempel", "ziel", "zeit", "dateien"}
    assert z["art"] == "eingespielt" and z["stempel"] == ST(1)
    assert z["ziel"] == os.path.normcase(os.path.realpath(str(ziel)))
    stand = json.loads((Path(ziel) / f".v2_{ST(1)}.fertig" / "stand.json").read_text(encoding="utf-8"))
    assert z["dateien"] == stand["dateien"] and len(z["dateien"]) == 4
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    zeilen = _manifest_zeilen(m)
    assert [x["art"] for x in zeilen] == ["eingespielt", "zurueckgerollt"]
    assert zeilen[1]["dateien"] == z["dateien"]


def test_halbe_letzte_manifestzeile_die_naechste_zeile_ist_trotzdem_gueltig(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    m.write_bytes(b'{"art": "eingespielt", "stempel": "x"')              # ohne Zeilenende
    assert _schreibe(ziel, m, 1, 1) == 0
    roh = m.read_bytes().split(b"\n")
    assert roh[0].startswith(b'{"art": "eingespielt", "stempel": "x"') and roh[-1] == b""
    assert len(_manifest_zeilen(m)) == 1                                     # die neue Zeile gilt
    assert "Warnung" in capsys.readouterr().out
    assert pg.v2_weiter(str(ziel), str(m)) == 0                              # keine Doppelzeile
    assert len(_manifest_zeilen(m)) == 1


def test_syntaktisch_gueltige_aber_unvollstaendige_zeile_verhindert_den_nachtrag_nicht(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    schluessel = os.path.normcase(os.path.realpath(str(ziel)))
    m.write_text(json.dumps({"art": "eingespielt", "stempel": ST(1), "ziel": schluessel}) + "\n",
                 encoding="utf-8")
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    vollstaendig = [z for z in _manifest_zeilen(m) if "dateien" in z]
    assert len(vollstaendig) == 1 and vollstaendig[0]["art"] == "eingespielt"
    assert len(vollstaendig[0]["dateien"]) == 4
    assert len(m.read_text(encoding="utf-8").splitlines()) == 2              # die kaputte bleibt
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert len(m.read_text(encoding="utf-8").splitlines()) == 2


def test_aelterer_fertig_ordner_ohne_zeile_wird_genau_einmal_nachgetragen(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    assert _schreibe(ziel, m, 2, 2) == 0
    zweite = [z for z in _manifest_zeilen(m) if z["stempel"] == ST(2)]
    m.write_text(json.dumps(zweite[0]) + "\n", encoding="utf-8")             # Zeile 1 fehlt
    for name in pg.V2_DATEIEN:                                               # Ziele nun anders
        (Path(ziel) / name).write_text("inzwischen anders\n", encoding="utf-8")
    capsys.readouterr()
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    ausgabe = capsys.readouterr().out
    assert "Zielzustand ungeprüft (Nachtrag nur Protokoll)" in ausgabe
    assert [(z["stempel"], z["art"]) for z in _manifest_zeilen(m)] == [
        (ST(2), "eingespielt"), (ST(1), "eingespielt")]
    snap = _snap(tmp_path)
    assert pg.v2_weiter(str(ziel), str(m)) == 0                              # genau einmal
    assert _snap(tmp_path) == snap
    assert "Zielzustand" not in capsys.readouterr().out


def test_zurueckgerollter_ordner_ohne_zeile_wird_per_rueckrollen_nachgetragen(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    erste = _manifest_zeilen(m)[0]
    m.write_text(json.dumps(erste) + "\n", encoding="utf-8")                 # nur 'eingespielt'
    vorher = _inhalt(ziel)
    capsys.readouterr()
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert "Zielzustand ungeprüft" in capsys.readouterr().out
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt", "zurueckgerollt"]
    assert _inhalt(ziel) == vorher                                           # Ziele ungeprueft/unberuehrt
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 2                  # nun ist die Zeile da


def test_zwei_zielordner_gleichen_namens_werden_getrennt_gefuehrt(tmp_path):
    m = tmp_path / "m.jsonl"
    a, b = tmp_path / "a" / "gruppen", tmp_path / "b" / "gruppen"
    assert _schreibe(a, m, 1, 1) == 0
    assert _schreibe(b, m, 1, 1) == 0                                        # gleicher Stempel
    zeilen = _manifest_zeilen(m)
    assert len(zeilen) == 2 and zeilen[0]["ziel"] != zeilen[1]["ziel"]
    m.write_text(json.dumps(zeilen[0]) + "\n", encoding="utf-8")             # Zeile von b fehlt
    assert pg.v2_weiter(str(a), str(m)) == 0
    assert len(_manifest_zeilen(m)) == 1                                     # a ist protokolliert
    assert pg.v2_weiter(str(b), str(m)) == 0
    zeilen = _manifest_zeilen(m)
    assert len(zeilen) == 2 and zeilen[1]["ziel"] == os.path.normcase(os.path.realpath(str(b)))


def test_fehlendes_oder_kaputtes_manifest_blockiert_keinen_weg(tmp_path, capsys):
    # fehlend (auch der Elternordner)
    ziel1, m1 = tmp_path / "z1", tmp_path / "gibt_es_nicht" / "m.jsonl"
    assert _schreibe(ziel1, m1, 1, 1) == 0
    assert "Warnung" in capsys.readouterr().out and len(_manifest_zeilen(m1)) == 1
    assert pg.v2_rueckrollen(str(ziel1), ST(1), str(m1)) == 0
    # kaputt (Muell)
    ziel2, m2 = tmp_path / "z2", tmp_path / "m2.jsonl"
    m2.write_bytes(b"\xff\xfe kein json\nnoch eins\n")
    assert _schreibe(ziel2, m2, 1, 1) == 0
    assert "Warnung" in capsys.readouterr().out and len(_manifest_zeilen(m2)) == 1
    assert pg.v2_rueckrollen(str(ziel2), ST(1), str(m2)) == 0
    # nicht beschreibbar (ein Ordner liegt dort)
    ziel3, m3 = tmp_path / "z3", tmp_path / "ein_ordner"
    m3.mkdir()
    assert _schreibe(ziel3, m3, 1, 1) == 0
    assert "Manifestzeile konnte nicht geschrieben werden" in capsys.readouterr().out
    assert _eintraege(ziel3) == [(ST(1), "FERTIG")]
    assert pg.v2_weiter(str(ziel3), str(m3)) == 0                            # blockiert nichts


# ── 10. Aufruf: Wartungswege ohne Eingaben und ohne Freigabe ────────────────

def _wartung(ziel, m, *zusatz):
    return pg.main(["--ausgabe-kandidat", str(ziel), "--manifest", str(m), *zusatz])


def test_weiter_und_rueckrollen_laufen_ohne_eingabedateien_und_ohne_freigabe(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, "gefuellt")
    _abgebrochen_schreiben(ziel, m, "_ersetzen", BEI)
    assert _wartung(ziel, m, "--weiter") == 0
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)
    assert _wartung(ziel, m, "--rueckrollen", ST(1)) == 0
    assert _inhalt(ziel) == start
    assert _wartung(ziel, m, "--rueckrollen", ST(1)) == 2                     # schon zurueckgerollt
    assert "Fehler" in capsys.readouterr().out


def test_wartung_mit_ausgabe_und_produktiv(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _abgebrochen_schreiben(ziel, m, "_ersetzen", ZUO)
    assert pg.main(["--ausgabe", str(ziel), "--produktiv", "--manifest", str(m), "--weiter"]) == 0
    assert _eintraege(ziel) == [(ST(1), "FERTIG")]
    assert pg.main(["--ausgabe", str(ziel), "--produktiv", "--manifest", str(m),
                    "--rueckrollen", ST(1)]) == 0


@pytest.mark.parametrize("argumente", [["--weiter", "--rueckrollen", "x"],
                                       ["--weiter", "--schreiben"],
                                       ["--rueckrollen", "x", "--schreiben"]])
def test_die_drei_wege_schliessen_sich_gegenseitig_aus(tmp_path, argumente):
    with pytest.raises(SystemExit) as fehler:
        pg.main(["--ausgabe-kandidat", str(tmp_path / "ziel"), "--manifest",
                 str(tmp_path / "m.jsonl"), *argumente])
    assert fehler.value.code == 2
    assert not (tmp_path / "ziel").exists() and not (tmp_path / "m.jsonl").exists()


@pytest.mark.parametrize("zusatz", [["--trocken"], ["--bewerten"], ["--nachtragen", "x.jsonl"]])
def test_wartung_ist_nicht_mit_trocken_bewerten_nachtragen_kombinierbar(tmp_path, zusatz):
    assert _wartung(tmp_path / "ziel", tmp_path / "m.jsonl", "--weiter", *zusatz) == 2
    assert not (tmp_path / "ziel").exists()


def test_wartung_mit_kandidatenordner_im_repo_ist_exit_2(tmp_path):
    im_repo = os.path.join(os.path.dirname(BACKEND), "kandidat_verboten")
    assert pg.main(["--ausgabe-kandidat", im_repo, "--manifest", str(tmp_path / "m.jsonl"),
                    "--weiter"]) == 2
    assert not os.path.exists(im_repo)


def test_wartung_auf_leerem_oder_fehlendem_ordner_tut_nichts(tmp_path, capsys):
    assert _wartung(tmp_path / "ziel", tmp_path / "m.jsonl", "--weiter") == 0
    assert "Nichts zu tun" in capsys.readouterr().out
    assert not (tmp_path / "ziel").exists() and not (tmp_path / "m.jsonl").exists()


def test_der_standard_manifestpfad_zeigt_in_tests_nie_ins_heimverzeichnis():
    standard = os.path.normcase(os.path.realpath(pg._standard_manifest()))
    heim = os.path.normcase(os.path.realpath(os.path.expanduser("~")))
    assert not standard.startswith(heim + os.sep) or "pytest" in standard
    assert pg.STANDARD_MANIFEST.endswith(os.path.join("foto_sortierung",
                                                      "sicherungen_manifest.jsonl"))
    assert pg._standard_manifest() != pg.STANDARD_MANIFEST


# ── 11. Ausgabe: nur Zahlen, Dateinamen ohne Pfad ───────────────────────────

def test_ausgabe_nennt_keinen_pfad_und_nennt_den_rueckrollbefehl(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    assert _schreibe(ziel, m, 1, 1) == 0
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    ausgabe = capsys.readouterr().out
    assert f"personen_gruppieren.py --ausgabe-kandidat <ordner> --rueckrollen {ST(1)}" in ausgabe
    assert str(tmp_path) not in ausgabe and _norm(tmp_path) not in ausgabe
    assert "Person_" not in ausgabe and "Marlene" not in ausgabe
    assert "gesichert: " + ZUO in ausgabe and "geschrieben: " + ZUO in ausgabe
    assert ".vorher_" not in ausgabe


def test_ausgabe_nennt_bei_produktiv_den_passenden_befehl(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1, produktiv=True) == 0
    assert f"personen_gruppieren.py --ausgabe <ordner> --produktiv --rueckrollen {ST(1)}" \
        in capsys.readouterr().out


# ── 12. Ende-zu-Ende ueber main() und v1 ────────────────────────────────────

def _v1_hilfen():
    import test_personen_gruppieren_v2 as tv2
    return tv2


def test_main_v2_schreibt_ueber_den_neuen_weg_und_main_rueckrollen_stellt_wieder_her(
        tmp_path, capsys):
    tv2 = _v1_hilfen()
    datei = tv2._vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    m = tmp_path / "manifest.jsonl"
    basis = tv2._grund(tmp_path, datei, aus)
    assert pg.main(basis + tv2._schreiben_args(tmp_path, datei, aus) + ["--manifest", str(m)]) == 0
    ausgabe = capsys.readouterr().out
    ordner = sorted(Path(aus).glob(".v2_*"))
    assert len(ordner) == 1 and ordner[0].name.endswith(".fertig")
    stempel = ordner[0].name[len(".v2_"):-len(".fertig")]
    assert f"--rueckrollen {stempel}" in ausgabe and "--ausgabe <ordner> --produktiv" in ausgabe
    assert not list(aus.glob("*.vorher_*"))
    for name in pg.V2_PFLICHT + (pg.DATEI_ALIASE,):
        assert (aus / name).is_file()
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt"]
    assert pg.main(["--ausgabe", str(aus), "--produktiv", "--manifest", str(m),
                    "--rueckrollen", stempel]) == 0
    assert all(not (aus / n).exists() for n in pg.V2_DATEIEN)
    assert [z["art"] for z in _manifest_zeilen(m)] == ["eingespielt", "zurueckgerollt"]


def test_v1_legt_weder_einen_v2_ordner_noch_eine_manifestzeile_an(tmp_path):
    tv2 = _v1_hilfen()
    datei = tv2._vektordatei(tmp_path)
    aus = tmp_path / "gruppen"
    m = tmp_path / "manifest.jsonl"
    assert pg.main(["--vektoren", str(datei), "--ausgabe", str(aus),
                    "--bestaetigt", str(tmp_path / "b.json"),
                    "--vorgaben", str(tmp_path / "v.json"), "--manifest", str(m),
                    "--schreiben"]) == 0
    assert sorted(os.listdir(aus)) == sorted(pg.V2_PFLICHT)
    assert not list(aus.glob(".v2_*")) and not m.exists()
    assert not pg.DATEI_ALIASE in os.listdir(aus)


def test_v1_signaturen_sind_unveraendert():
    # Das Modul hat ``from __future__ import annotations``: Annotationen sind Zeichenketten.
    assert str(inspect.signature(pg.schreiben)) == "(lauf, ausgabe, stand=None) -> 'list[str]'"
    assert str(inspect.signature(pg._stempel_sichern)) == \
        "(ausgabe, stempel=None, mit_aliasen: 'bool' = False) -> 'list[str]'"
    quelle = inspect.getsource(pg.main)
    assert "for pfad in _stempel_sichern(args.ausgabe):" in quelle
    assert "for pfad in schreiben(lauf, args.ausgabe):" in quelle


def test_v1_stempel_sichern_sichert_weiter_wie_vor_schritt_4(tmp_path):
    for name in pg.V2_PFLICHT:
        (tmp_path / name).write_text("alt\n", encoding="utf-8")
    sicherungen = pg._stempel_sichern(str(tmp_path), stempel="eins")
    assert sorted(os.path.basename(p) for p in sicherungen) == sorted(
        f"{n}.vorher_eins" for n in pg.V2_PFLICHT)
    assert pg._stempel_sichern(str(tmp_path), stempel="eins") == []          # nie ueberschreiben


# ── 13. Nachbesserung R1 / E1: Kopie ueber die Teilkopie ``.teil`` ───────────

@contextlib.contextmanager
def _teil_abbruch(name, anteile, i=1):
    """Bricht MITTEN in der Kopie auf ``<name>.tmp_<stempel>`` ab: ein Teil des Inhalts
    ist geschrieben, dann folgt die Ausnahme. ``anteile``: Bruchteile je Versuch."""
    with pytest.MonkeyPatch.context() as mp:
        original = pg._teil_schreiben
        zaehler = {"n": 0}

        def huelle(quelle, teil):
            if _norm(teil).endswith(f"/{name}.tmp_{ST(i)}.teil"):
                daten = Path(quelle).read_bytes()
                anteil = anteile[min(zaehler["n"], len(anteile) - 1)]
                zaehler["n"] += 1
                Path(teil).write_bytes(daten[: max(1, int(len(daten) * anteil))])
                raise Abbruch("mitten in der Kopie")
            return original(quelle, teil)

        mp.setattr(pg, "_teil_schreiben", huelle)
        yield


@pytest.mark.parametrize("ausgang", AUSGAENGE)
def test_abbruch_mitten_in_der_einspielkopie_weiter_vollendet(tmp_path, ausgang):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _szenario(ziel, ausgang)
    with _teil_abbruch(ZUO, [0.5]):
        with pytest.raises(Abbruch):
            _schreibe(ziel, m, 1, 1)
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").is_file()
    assert not (Path(ziel) / f"{ZUO}.tmp_{ST(1)}").exists()      # die Teilkopie ist kein tmp
    teil = (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes()
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)
    # der Abbruchrest wurde nie geloescht, nur verschoben
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil.verworfen_1").read_bytes() == teil
    assert not (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").exists()


@pytest.mark.parametrize("ausgang", AUSGAENGE)
def test_abbruch_mitten_in_der_einspielkopie_rueckrollen_stellt_den_ausgang_her(
        tmp_path, ausgang):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, ausgang)
    with _teil_abbruch(ZUO, [0.5]):
        with pytest.raises(Abbruch):
            _schreibe(ziel, m, 1, 1)
    teil = (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes()
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes() == teil     # nie geloescht


def test_abbruch_mitten_in_der_rueckroll_kopie_erneutes_rueckrollen_vollendet(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    start = _szenario(ziel, "gefuellt")
    assert _schreibe(ziel, m, 1, 1) == 0
    with _teil_abbruch(ZUO, [0.5]):
        with pytest.raises(Abbruch):
            pg.v2_rueckrollen(str(ziel), ST(1), str(m))
    teil = (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes()
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert _inhalt(ziel) == start
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil.verworfen_1").read_bytes() == teil


def test_zwei_abbrueche_mitten_in_der_kopie_erhalten_verworfen_1_und_2(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _szenario(ziel, "gefuellt")
    with _teil_abbruch(ZUO, [0.3, 0.6]):
        with pytest.raises(Abbruch):
            _schreibe(ziel, m, 1, 1)                              # Rest A (.teil)
        erster = (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes()
        with pytest.raises(Abbruch):
            pg.v2_weiter(str(ziel), str(m))                       # A -> _1, Rest B (.teil)
        zweiter = (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil").read_bytes()
    assert erster != zweiter
    assert pg.v2_weiter(str(ziel), str(m)) == 0                   # B -> _2, Kopie gelingt
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil.verworfen_1").read_bytes() == erster
    assert (Path(ziel) / f"{ZUO}.tmp_{ST(1)}.teil.verworfen_2").read_bytes() == zweiter
    assert _inhalt(ziel) == _neu_inhalt(tmp_path, 1)


def test_teilkopie_mit_falschem_hash_wird_nie_zur_tmp_kopie(tmp_path):
    quelle = tmp_path / "q.bin"
    quelle.write_bytes(b"inhalt\n")
    with pytest.raises(pg.TransaktionsFehler):
        pg._kopieren(str(quelle), str(tmp_path / "x.tmp_1"), soll="0" * 64)
    assert not (tmp_path / "x.tmp_1").exists() and (tmp_path / "x.tmp_1.teil").is_file()
    soll = hashlib.sha256(b"inhalt\n").hexdigest()
    pg._kopieren(str(quelle), str(tmp_path / "x.tmp_1"), soll=soll)
    assert (tmp_path / "x.tmp_1").read_bytes() == b"inhalt\n"
    assert (tmp_path / "x.tmp_1.teil.verworfen_1").is_file()
    assert not (tmp_path / "x.tmp_1.teil").exists()
    with pytest.raises(pg.TransaktionsFehler):                    # tmp belegt: nie darauf kopieren
        pg._kopieren(str(quelle), str(tmp_path / "x.tmp_1"), soll=soll)


def test_teil_rest_mit_dem_stempel_des_neuen_laufs_ist_eine_kollision(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    _ausgang(ziel)
    (ziel / f"{ZUO}.tmp_{ST(5)}.teil").write_bytes(b"fremd\n")
    snap = _snap(tmp_path)
    assert _schreibe(ziel, m, 1, 5) == 2
    assert _snap(tmp_path) == snap


# ── 14. E2: Pruefung 5.2b auch fuer unveraenderte Dateien ───────────────────

def test_zweite_pruefung_prueft_auch_unveraenderte_dateien(tmp_path):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    gleich = Path(ziel) / ZUO
    original = gleich.read_bytes()
    mp = _nach_stand_json(lambda: gleich.write_bytes(b"von aussen\n"))
    try:
        assert _schreibe(ziel, m, 1, 2) == 2                      # vorher == neu, trotzdem geprueft
    finally:
        mp.undo()
    ordner = Path(ziel) / f".v2_{ST(2)}"
    assert _eintraege(ziel) == [(ST(1), "FERTIG"), (ST(2), "BEREIT")]
    assert not (ordner / "EINSPIELEN").exists() and not (ordner / "fortschritt").exists()
    assert gleich.read_bytes() == b"von aussen\n"
    gleich.write_bytes(original)
    assert pg.v2_rueckrollen(str(ziel), ST(2), str(m)) == 0


# ── 15. E3: Manifestzeilen streng pruefen, nie eine Ausnahme ────────────────

def _gute_zeile():
    return {"art": "eingespielt", "stempel": ST(1), "ziel": "z", "zeit": "t",
            "dateien": [{"name": n, "vorher_sha256": None, "neu_sha256": "a" * 64}
                        for n in pg.V2_DATEIEN]}


def test_manifestzeile_wird_streng_geprueft():
    assert pg._manifest_zeile_gueltig(_gute_zeile())
    aenderungen = [
        lambda z: z.update(extra=1),
        lambda z: z.pop("zeit"),
        lambda z: z.update(stempel="a.b"),
        lambda z: z["dateien"][0].update(name="fremd.json"),
        lambda z: z["dateien"][1].update(name=pg.V2_DATEIEN[0]),          # doppelt
        lambda z: z["dateien"][0].update(neu_sha256=None),
        lambda z: z["dateien"][0].update(neu_sha256="xyz"),
        lambda z: z["dateien"][0].update(vorher_sha256="A" * 64),         # nur Kleinbuchstaben
        lambda z: z["dateien"][0].update(vorher_sha256=5),
        lambda z: z["dateien"][0].update(zusatz=1),
        lambda z: z["dateien"].pop(),
    ]
    for aendern in aenderungen:
        zeile = _gute_zeile()
        aendern(zeile)
        assert not pg._manifest_zeile_gueltig(zeile), zeile


def test_manifestzeile_mit_doppeltem_namen_und_gemischten_hashes_wirft_nie(tmp_path, capsys):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"
    assert _schreibe(ziel, m, 1, 1) == 0
    schluessel = os.path.normcase(os.path.realpath(str(ziel)))
    boese = {"art": "eingespielt", "stempel": ST(1), "ziel": schluessel, "zeit": "t",
             "dateien": [{"name": ZUO, "vorher_sha256": None, "neu_sha256": "a" * 64},
                         {"name": ZUO, "vorher_sha256": "b" * 64, "neu_sha256": "a" * 64},
                         {"name": BEI, "vorher_sha256": None, "neu_sha256": "a" * 64},
                         {"name": KEN, "vorher_sha256": "c" * 64, "neu_sha256": "a" * 64}]}
    m.write_text(json.dumps(boese) + "\n", encoding="utf-8")
    capsys.readouterr()
    assert pg.v2_weiter(str(ziel), str(m)) == 0                   # wie ohne Manifest
    assert "Warnung" in capsys.readouterr().out
    gueltig = [z for z in _manifest_zeilen(m) if pg._manifest_zeile_gueltig(z)]
    assert len(gueltig) == 1 and gueltig[0]["art"] == "eingespielt"
    m.write_text(json.dumps(boese) + "\n", encoding="utf-8")
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
    assert "Warnung" in capsys.readouterr().out


def test_manifest_lesen_wirft_nie_auch_bei_unerwarteten_ausnahmen(tmp_path, capsys, monkeypatch):
    ziel, m = tmp_path / "ziel", tmp_path / "m.jsonl"

    def kaputt(*a, **kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(pg, "_manifest_zeile_gueltig", kaputt)
    m.write_text(json.dumps(_gute_zeile()) + "\n", encoding="utf-8")
    assert _schreibe(ziel, m, 1, 1) == 0
    assert "Warnung" in capsys.readouterr().out
    assert pg.v2_weiter(str(ziel), str(m)) == 0
    assert pg.v2_rueckrollen(str(ziel), ST(1), str(m)) == 0
