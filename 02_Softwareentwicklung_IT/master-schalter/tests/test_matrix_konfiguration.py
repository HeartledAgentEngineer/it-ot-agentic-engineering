"""Tests für die Matrix-Konfiguration ('Nach Kontingent')."""
import json
from master_schalter import matrix_konfiguration as mk


def test_default_matrix_hat_alle_vier_lagen_und_schwellen():
    cfg = mk.matrix_lesen()
    assert "lage_1" in cfg
    assert "lage_2a" in cfg
    assert "lage_2b" in cfg
    assert "lage_3" in cfg
    assert cfg["lage_1"]["master"] == "Claude Opus 5.5"
    assert cfg["lage_1"]["pruefer"] == "GPT-6 Sol"
    assert cfg["lage_3"]["master"] == "DeepSeek V4.1 Flash"
    assert "antigravity" in cfg
    assert cfg["schwellen"]["warnung_prozent"] == 80


def test_matrix_schreiben_und_lesen_roundtrip(tmp_path):
    datei = tmp_path / "matrix-test.json"
    daten = {
        "lage_1": {"master": "Antigravity", "pruefer": "DeepSeek"},
        "antigravity": {"rolle": "Master / Thinker"},
    }
    assert mk.matrix_schreiben(daten, datei=datei)
    gelesen = mk.matrix_lesen(datei=datei)
    assert gelesen["lage_1"]["master"] == "Antigravity"
    assert gelesen["lage_1"]["pruefer"] == "DeepSeek"
    # Ungenannte Lagen werden aus den Defaults ergänzt:
    assert "lage_3" in gelesen
