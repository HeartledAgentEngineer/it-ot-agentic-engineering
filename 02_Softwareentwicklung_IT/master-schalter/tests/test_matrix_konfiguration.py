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


def test_presets_enthalten_integrative_maschine_und_argon(tmp_path):
    datei = tmp_path / "matrix-preset-test.json"
    assert "Integrative Maschine (Claude Opus 5.5)" in mk.PRESETS
    assert "Antigravity & Argon (Google AI)" in mk.PRESETS
    assert "Gemini 3.8 Flash Fokus" in mk.PRESETS

    # Preset Integrative Maschine anwenden
    daten = mk.preset_anwenden("Integrative Maschine (Claude Opus 5.5)", datei=datei)
    assert daten["preset"] == "Integrative Maschine (Claude Opus 5.5)"
    assert daten["lage_1"]["master"] == "Claude Opus 5.5"
    assert daten["lage_1"]["worker"] == "Gemini 3.8 Flash"

    # Preset Argon anwenden
    daten_argon = mk.preset_anwenden("Antigravity & Argon (Google AI)", datei=datei)
    assert daten_argon["lage_1"]["master"] == "Argon (Antigravity)"


def test_themen_rotation_lesen_und_schreiben(tmp_path):
    datei = tmp_path / "matrix-themen-test.json"
    assert "Antigravity ➔ Hermes ➔ Codex" in mk.VERFUEGBARE_ROTATIONEN
    assert "Integrative Maschine (Claude Opus 5.5 ➔ Argon ➔ Gemini 3.8 Flash)" in mk.VERFUEGBARE_ROTATIONEN

    # Standard lesen wenn noch nichts hinterlegt
    default_einst = mk.themen_einstellungen_lesen("neues-projekt", datei=datei)
    assert default_einst["rotation"] == "Antigravity ➔ Hermes ➔ Codex"

    # Spezifische Rotation für das Thema schreiben
    assert mk.themen_einstellungen_schreiben("neues-projekt", {
        "rotation": "Claude ➔ Codex ➔ Antigravity",
        "erst_master": "Claude",
    }, datei=datei)

    gelesen = mk.themen_einstellungen_lesen("neues-projekt", datei=datei)
    assert gelesen["rotation"] == "Claude ➔ Codex ➔ Antigravity"
    assert gelesen["erst_master"] == "Claude"

