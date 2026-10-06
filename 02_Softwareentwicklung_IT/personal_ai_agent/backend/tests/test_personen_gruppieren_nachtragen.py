"""Tests: neue Gesichter an BESTEHENDE Gruppen nachtragen (06.10.2026).

Alles offline und mit **erfundenen** Vektoren: Personen sind zufaellige
Einheitsvektoren im 128-dimensionalen Raum, ihre Gesichter liegen mit Cosinus
~0,85 um den Mittelpunkt. Keine echten Gesichter, keine Namen, kein Netz,
keine pCloud — alle Dateien liegen in ``tmp_path``.

Geprueft werden die Kernregeln des Nachtragens: alte Zeilen bleiben wortgleich
erhalten, cannot-link je Bild, Schwelle greift, der Rest bildet neue Kennungen
mit fortlaufender Nummer, der zweite Lauf ist idempotent, vor dem Schreiben
entsteht eine ``*.vorher``-Sicherung, ohne ``--schreiben`` wird nichts
geschrieben und das Repo-Ziel bleibt gesperrt (Exit 2).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_personen_gruppieren_nachtragen.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys

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


# ── erfundene Welt ───────────────────────────────────────────────────────

def _mitte(rng):
    v = rng.normal(size=D)
    return v / np.linalg.norm(v)


def _gesicht(rng, mitte, naehe=0.85):
    rausch = rng.normal(size=D)
    rausch -= rausch.dot(mitte) * mitte
    rausch /= np.linalg.norm(rausch)
    return naehe * mitte + np.sqrt(1 - naehe ** 2) * rausch


def _zeile(bild_id, vektoren, aufnahme="2015-06-01T10:00:00", score=0.99):
    """Eine Vektorzeile im Eingabeformat (1000x750, grosse Gesichter).

    ``bbox`` ist im Haus ``[x, y, Breite, Hoehe]`` — beide Gesichter eines
    Bildes sind hier gleich gross, damit die Reihenfolge stabil bleibt.
    """
    gesichter = []
    for i, v in enumerate(vektoren):
        gesichter.append({"index": i, "bbox": [60.0 + 300 * i, 120.0, 260.0, 340.0],
                          "score": score, "embedding": [float(w) for w in v]})
    return {"bild_id": bild_id, "breite": 1000, "hoehe": 750, "gesichter": gesichter,
            "metadaten": {"aufnahme": aufnahme}}


def _schreiben(pfad, zeilen):
    with open(pfad, "w", encoding="utf-8", newline="\n") as datei:
        for z in zeilen:
            datei.write(json.dumps(z, ensure_ascii=False) + "\n")
    return str(pfad)


def _alte_welt(tmp_path, seed=7, personen=3, je_person=12):
    """Eine bestehende Gruppen-Welt bauen (wie der echte erste Lauf)."""
    rng = np.random.default_rng(seed)
    mitten = [_mitte(rng) for _ in range(personen)]
    zeilen = []
    for p, mitte in enumerate(mitten):
        for i in range(je_person):
            zeilen.append(_zeile(f"alt_{p}_{i}", [_gesicht(rng, mitte)],
                                 aufnahme=f"201{2 + p}-0{1 + i % 9}-15T12:00:00"))
    quelle = _schreiben(tmp_path / "alt.jsonl", zeilen)
    lauf = pg.lauf_rechnen(pg.gesichter_lesen([quelle], {}))
    ausgabe = str(tmp_path / "gruppen")
    pg.schreiben(lauf, ausgabe)
    return ausgabe, mitten, rng


def _pfad(ausgabe, name):
    return os.path.join(ausgabe, name)


def _kennungen(ausgabe):
    with open(_pfad(ausgabe, pg.DATEI_KENNUNGEN), encoding="utf-8") as datei:
        return json.load(datei)["kennungen"]


def _stand(ausgabe):
    """Die geschriebene Zuordnung als ``{(bild_id, index): kennung}``."""
    ergebnis = {}
    with open(_pfad(ausgabe, pg.DATEI_ZUORDNUNG), encoding="utf-8") as datei:
        for zeile in datei:
            eintrag = json.loads(zeile)
            ergebnis[(str(eintrag["bild_id"]), int(eintrag["index"]))] = eintrag.get("kennung")
    return ergebnis


def _summen(ausgabe):
    """SHA-256 der drei Dateien — belegt, ob sich etwas geaendert hat."""
    ergebnis = {}
    for name in (pg.DATEI_ZUORDNUNG, pg.DATEI_BEISPIELE, pg.DATEI_KENNUNGEN):
        pfad = _pfad(ausgabe, name)
        if os.path.isfile(pfad):
            with open(pfad, "rb") as datei:
                ergebnis[name] = hashlib.sha256(datei.read()).hexdigest()
    return ergebnis


def _lauf(ausgabe, neu_pfad, **kwargs):
    """Nachtragen rechnen (ohne Schreiben) — liefert ``(lauf, alte_zeilen)``."""
    alte_zeilen = pg.zuordnung_zeilen_lesen(_pfad(ausgabe, pg.DATEI_ZUORDNUNG))
    lauf = pg.nachtrag_rechnen(
        pg.gesichter_lesen([neu_pfad], {}), alte_zeilen, _kennungen(ausgabe),
        beispiele_alt=pg.beispiele_lesen(_pfad(ausgabe, pg.DATEI_BEISPIELE)), **kwargs)
    return lauf, alte_zeilen


def _hoechste(kennungen):
    return pg._cluster._naechste_nummer(sorted(e["kennung"] for e in kennungen))


# ── Andocken ─────────────────────────────────────────────────────────────

def test_neue_gesichter_docken_an_ihre_gruppe(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    stand = _stand(ausgabe)
    erwartet = stand[("alt_0_0", 0)]
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["bericht"]["neue_gesichter"] == 1
    assert lauf["neu"][0] == erwartet
    assert lauf["bericht"]["angedockt"] == 1
    assert lauf["bericht"]["neue_gruppen"] == 0
    assert lauf["bericht"]["rauschen"] == 0


def test_zwei_gesichter_eines_bildes_nie_in_einer_gruppe(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    gruppe = _stand(ausgabe)[("alt_1_0", 0)]
    neu = _schreiben(tmp_path / "neu.jsonl", [
        _zeile("fb_doppel", [_gesicht(rng, mitten[1]), _gesicht(rng, mitten[1])])])
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["neu"][0] == gruppe          # das erste dockt an
    assert lauf["neu"][1] != gruppe          # das zweite nicht — gleiches Bild
    assert lauf["bericht"]["angedockt"] == 1
    assert lauf["bericht"]["rauschen"] == 1  # Einzelgesicht, keine Gruppe


def test_fremdes_gesicht_dockt_nicht_an(tmp_path):
    """Die Schwelle greift: ein unabhaengiges Gesicht bleibt draussen."""
    ausgabe, _, _ = _alte_welt(tmp_path)
    fremd = np.random.default_rng(99)
    neu = _schreiben(tmp_path / "neu.jsonl",
                     [_zeile("fb_fremd", [_gesicht(fremd, _mitte(fremd))])])
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["bericht"]["angedockt"] == 0
    assert lauf["bericht"]["gruppen_mit_zuwachs"] == 0
    assert lauf["neu"][0] is None
    assert lauf["bericht"]["rauschen"] == 1


def test_ausschlussregel_wird_beachtet(tmp_path):
    """personen_vorgaben.json: dieses Gesicht ist NICHT diese Person."""
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    gruppe = _stand(ausgabe)[("alt_2_0", 0)]
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_aus", [_gesicht(rng, mitten[2])])])
    vorgaben = {"gleich": set(), "verschieden": set(),
                "ausgeschlossen": {(gruppe, "fb_aus", 0)}}
    lauf, _ = _lauf(ausgabe, neu, vorgaben=vorgaben)
    assert lauf["neu"][0] != gruppe
    assert lauf["bericht"]["angedockt"] == 0


# ── Rest und Kennungen ───────────────────────────────────────────────────

def test_rest_bildet_neue_kennung_fortlaufend(tmp_path):
    ausgabe, _, rng = _alte_welt(tmp_path)
    hoechste = _hoechste(_kennungen(ausgabe))
    neue_mitte = _mitte(rng)
    neu = _schreiben(tmp_path / "neu.jsonl",
                     [_zeile(f"fb_neu_{i}", [_gesicht(rng, neue_mitte)]) for i in range(5)])
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["bericht"]["neue_gruppen"] == 1
    assert lauf["bericht"]["neue_kennungen"] == [f"Person_{hoechste + 1:03d}"]
    assert lauf["bericht"]["rauschen"] == 0
    assert lauf["bericht"]["angedockt"] == 0
    assert {lauf["neu"][i] for i in range(5)} == {f"Person_{hoechste + 1:03d}"}


def test_zwei_neue_personen_bekommen_fortlaufende_nummern(tmp_path):
    ausgabe, _, rng = _alte_welt(tmp_path)
    hoechste = _hoechste(_kennungen(ausgabe))
    a, b = _mitte(rng), _mitte(rng)
    zeilen = [_zeile(f"fb_a_{i}", [_gesicht(rng, a)]) for i in range(4)]
    zeilen += [_zeile(f"fb_b_{i}", [_gesicht(rng, b)]) for i in range(4)]
    neu = _schreiben(tmp_path / "neu.jsonl", zeilen)
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["bericht"]["neue_gruppen"] == 2
    assert lauf["bericht"]["neue_kennungen"] == [f"Person_{hoechste + 1:03d}",
                                                 f"Person_{hoechste + 2:03d}"]


def test_kleine_restgruppe_ist_rauschen(tmp_path):
    """Unter MIN_GROESSE gibt es keine Kennung — wie im grossen Lauf."""
    ausgabe, _, rng = _alte_welt(tmp_path)
    andere = _mitte(rng)
    zeilen = [_zeile(f"fb_einzel_{i}", [_gesicht(rng, andere)]) for i in range(2)]
    neu = _schreiben(tmp_path / "neu.jsonl", zeilen)
    lauf, _ = _lauf(ausgabe, neu)
    assert lauf["bericht"]["neue_gruppen"] == 0
    assert lauf["bericht"]["rauschen"] == 2
    assert all(lauf["neu"][i] is None for i in range(2))


# ── Idempotenz und Schreiben ─────────────────────────────────────────────

def test_zweiter_lauf_ist_idempotent(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    lauf, alte_zeilen = _lauf(ausgabe, neu)
    pg.nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand="2026-10-06T12:00:00")
    lauf2, _ = _lauf(ausgabe, neu)
    assert lauf2["bericht"]["neue_gesichter"] == 0
    assert lauf2["bericht"]["uebersprungen"] == 1
    assert lauf2["bericht"]["angedockt"] == 0


def test_ohne_schreiben_bleiben_die_dateien_gleich(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    vorher = _summen(ausgabe)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    _lauf(ausgabe, neu)
    assert _summen(ausgabe) == vorher


def test_schreiben_haelt_alte_zeilen_wortgleich_und_sichert_vorher(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    alter_hash = _summen(ausgabe)[pg.DATEI_ZUORDNUNG]
    neu = _schreiben(tmp_path / "neu.jsonl",
                     [_zeile("fb_0", [_gesicht(rng, mitten[0])]),
                      _zeile("fb_1", [_gesicht(rng, mitten[1])])])
    lauf, alte_zeilen = _lauf(ausgabe, neu)
    ergebnis = pg.nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand="2026-10-06T12:00:00")
    assert len(ergebnis["sicherungen"]) == 3
    assert len(ergebnis["geschrieben"]) == 3
    # Sicherung ist der alte Stand, die Zuordnung enthaelt die alten Zeilen wortgleich
    mit_sicherung = open(_pfad(ausgabe, pg.DATEI_ZUORDNUNG) + ".vorher", "rb").read()
    assert hashlib.sha256(mit_sicherung).hexdigest() == alter_hash
    zeilen = pg.zuordnung_zeilen_lesen(_pfad(ausgabe, pg.DATEI_ZUORDNUNG))
    assert zeilen[:len(alte_zeilen)] == alte_zeilen
    assert len(zeilen) == len(alte_zeilen) + 2
    # die Sicherung wird bei einem zweiten Schreiben NICHT ueberschrieben
    zweite = pg.nachtrag_schreiben(lauf, ausgabe, alte_zeilen)
    assert zweite["sicherungen"] == []


def test_alte_mittelpunkte_bleiben_unveraendert(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    vorher = _kennungen(ausgabe)
    neue_mitte = _mitte(rng)
    neu = _schreiben(tmp_path / "neu.jsonl",
                     [_zeile(f"fb_neu_{i}", [_gesicht(rng, neue_mitte)]) for i in range(3)])
    lauf, alte_zeilen = _lauf(ausgabe, neu)
    pg.nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand="2026-10-06T12:00:00")
    nachher = _kennungen(ausgabe)
    assert nachher[:len(vorher)] == vorher
    assert len(nachher) == len(vorher) + lauf["bericht"]["neue_gruppen"]
    assert nachher[-1]["kennung"] == lauf["bericht"]["neue_kennungen"][0]
    assert len(nachher[-1]["mittelpunkt"]) == D


def test_beispiele_werden_um_neue_gesichter_ergaenzt(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    gruppe = _stand(ausgabe)[("alt_0_0", 0)]
    vorher = {g["kennung"]: g for g in json.load(
        open(_pfad(ausgabe, pg.DATEI_BEISPIELE), encoding="utf-8"))["gruppen"]}[gruppe]
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    lauf, alte_zeilen = _lauf(ausgabe, neu)
    pg.nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand="2026-10-06T12:00:00")
    nachher = {g["kennung"]: g for g in json.load(
        open(_pfad(ausgabe, pg.DATEI_BEISPIELE), encoding="utf-8"))["gruppen"]}[gruppe]
    assert nachher["groesse"] == vorher["groesse"] + 1
    assert nachher["bilder"] == vorher["bilder"] + 1
    assert len(nachher["beispiele"]) <= pg.BEISPIELE_JE_GRUPPE
    assert vorher["beispiele"][0] in nachher["beispiele"]      # nichts geht verloren
    assert "fb_0" in {b["bild_id"] for b in nachher["beispiele"]}


# ── Kommandozeile ────────────────────────────────────────────────────────

def test_kommandozeile_trockenlauf_schreibt_nichts(tmp_path, capsys):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    vorher = _summen(ausgabe)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    code = pg.main(["--nachtragen", neu, "--ausgabe", ausgabe])
    assert code == 0
    text = capsys.readouterr().out
    assert "Trockenlauf" in text
    assert "Neue Gesichter: 1" in text
    assert _summen(ausgabe) == vorher


def test_kommandozeile_schreiben(tmp_path, capsys):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    vorher = _stand(ausgabe)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    code = pg.main(["--nachtragen", neu, "--ausgabe", ausgabe, "--schreiben"])
    assert code == 0
    text = capsys.readouterr().out
    assert "gesichert: gesicht_zuordnung.jsonl.vorher" in text
    assert "geschrieben: gesicht_zuordnung.jsonl" in text
    nachher = _stand(ausgabe)
    assert len(nachher) == len(vorher) + 1
    assert nachher[("fb_0", 0)] == vorher[("alt_0_0", 0)]


def test_repo_ziel_ist_gesperrt(tmp_path):
    """Ausgabe im Repo = Exit 2 (wie im grossen Lauf)."""
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    verboten = os.path.join(BACKEND, "verboten")
    with pytest.raises(SystemExit) as ende:
        pg.main(["--nachtragen", neu, "--ausgabe", verboten])
    assert ende.value.code == 2


def test_fehlende_grundlage_ist_ein_fehler(tmp_path):
    """Ohne bestehende Zuordnung gibt es nichts zum Andocken."""
    leer = tmp_path / "leer"
    leer.mkdir()
    rng = np.random.default_rng(3)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, _mitte(rng))])])
    assert pg.main(["--nachtragen", neu, "--ausgabe", str(leer)]) == 2


def test_bericht_nennt_keine_pfade_oder_namen(tmp_path):
    ausgabe, mitten, rng = _alte_welt(tmp_path)
    neu = _schreiben(tmp_path / "neu.jsonl", [_zeile("fb_0", [_gesicht(rng, mitten[0])])])
    lauf, _ = _lauf(ausgabe, neu)
    text = pg.nachtrag_bericht_text(lauf["bericht"])
    assert "/" not in text and "\\" not in text
    assert ".jsonl" not in text
