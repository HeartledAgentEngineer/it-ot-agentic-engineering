"""Tests: tools/foto_sortierung/fotobuch_gesichter_pruefen.py (06.10.2026).

Offline, erfundene Kennungen in ``tmp_path``. Geprüft: richtige Zählung je
Kettenglied, Befund-Satz, und dass NUR Zahlen ausgegeben werden.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]


def _werkzeug():
    pfad = PROJEKT / "tools" / "foto_sortierung" / "fotobuch_gesichter_pruefen.py"
    spez = importlib.util.spec_from_file_location("fotobuch_gesichter_pruefen", pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def _jsonl(pfad: Path, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z if isinstance(z, str) else json.dumps(z) for z in zeilen) + "\n",
                    encoding="utf-8")


def _basis(tmp_path, mit_zuordnung=True):
    _jsonl(tmp_path / "fotobuch_ereignisse.jsonl", [
        {"kennung": "fotobuch-x-001", "datei_kennungen": [9101, 9102]},
        {"kennung": "fotobuch-x-002", "datei_kennungen": [9103, 9101]},
        "kaputt",
    ])
    _jsonl(tmp_path / "personen_vektoren_n0929_voll.jsonl", [
        {"bild_id": "9101", "gesichter": [{"embedding": [0.1]}, {"embedding": [0.2]}]},
        {"bild_id": "9102", "gesichter": []},
        {"bild_id": "5555", "gesichter": [{"embedding": [0.3]}]},           # kein Fotobuch-Foto
    ])
    if mit_zuordnung:
        _jsonl(tmp_path / "personen_gruppen" / "gesicht_zuordnung.jsonl", [
            {"bild_id": "9101", "kennung": "Person_1001"},
            {"bild_id": "9101", "kennung": "Person_1002"},
            {"bild_id": "5555", "kennung": "Person_1001"},
        ])
    return tmp_path


def test_zaehlt_je_kettenglied(tmp_path):
    w = _werkzeug()
    basis = _basis(tmp_path)
    fotos = w.fotobuch_fotos(str(basis / "fotobuch_ereignisse.jsonl"))
    assert fotos == {"9101", "9102", "9103"}
    assert w.vektoren_zaehlen(str(basis / "personen_vektoren_n0929_voll.jsonl"), fotos) == \
        {"mit_zeile": 2, "mit_gesicht": 1, "gesichter": 2}
    assert w.zuordnung_zaehlen(str(basis / "personen_gruppen" / "gesicht_zuordnung.jsonl"), fotos) == \
        {"mit_gruppe": 1, "gruppen": 2}


def test_befund_saetze():
    w = _werkzeug()
    assert "NICHT in der Gesichtererkennung" in w.befund(849, 0, 0, 0)
    assert "keine Gesichter gefunden" in w.befund(849, 849, 0, 0)
    assert "neu gruppieren" in w.befund(849, 849, 300, 0)
    assert "Teilweise" in w.befund(849, 400, 300, 200)
    assert "Erkannt und gruppiert" in w.befund(849, 849, 300, 280)


def test_ausgabe_nur_zahlen(tmp_path, capsys):
    w = _werkzeug()
    assert w.main(["--basis", str(_basis(tmp_path))]) == 0
    aus = capsys.readouterr().out
    assert "Fotobuch: 3 Fotos" in aus and "2 Fotos mit Zeile" in aus and "1 Fotos an 2 Gruppen" in aus
    for geheim in ("9101", "9102", "9103", "Person_1001", "fotobuch-x"):
        assert geheim not in aus


def test_ohne_fotobuch_exit_2(tmp_path, capsys):
    assert _werkzeug().main(["--basis", str(tmp_path)]) == 2
    assert "fehlt" in capsys.readouterr().out


def test_ohne_zuordnung_kein_wurf(tmp_path, capsys):
    assert _werkzeug().main(["--basis", str(_basis(tmp_path, mit_zuordnung=False))]) == 0
    assert "gesicht_zuordnung.jsonl fehlt" in capsys.readouterr().out
