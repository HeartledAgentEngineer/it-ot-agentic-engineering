"""Tests für die OrbitDesk-Befehle der Befehlszeile (goal, kosten, sprache, mcp)."""
import json
import pytest

from master_schalter import cli, ziele, kosten_budget


def test_cli_goal_setzen_und_lesen(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    
    # Goal setzen
    code = cli.main([
        "goal-setzen", "test-projekt",
        "--titel", "Test Projekt Goal",
        "--ziel", "Autonomer Dauerlauf",
        "--abnahme", "Kriterium 1", "Kriterium 2",
        "--schritt", "Schritt A ausführen",
        "--rolle", "Hermes",
        "--zustaendigkeit", "Hermes",
    ])
    assert code == 0
    out, _ = capsys.readouterr()
    assert "Goal für 'test-projekt' aktualisiert" in out

    # Goal im Textmodus lesen
    code = cli.main(["goal", "test-projekt"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert "Goal für test-projekt" in out
    assert "Titel: Test Projekt Goal" in out
    assert "Kriterium 1" in out
    assert "Schritt A ausführen" in out

    # Goal im JSON-Modus lesen
    code = cli.main(["goal", "test-projekt", "--json"])
    assert code == 0
    out, _ = capsys.readouterr()
    daten = json.loads(out)
    assert daten["thema"] == "test-projekt"
    assert daten["titel"] == "Test Projekt Goal"


def test_cli_kosten(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    
    # Kosten abfragen (Text)
    code = cli.main(["kosten"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert "OrbitDesk Budget- & Kostenstatus" in out

    # Kosten abfragen (JSON)
    code = cli.main(["kosten", "--json"])
    assert code == 0
    out, _ = capsys.readouterr()
    daten = json.loads(out)
    assert "gesamt_kosten_usd" in daten


def test_cli_sprache(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    
    # was-laeuft-wo
    code = cli.main(["sprache", "was-laeuft-wo"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert len(out.strip()) > 0

    # pruefungen
    code = cli.main(["sprache", "pruefungen"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert len(out.strip()) > 0

    # fragen
    code = cli.main(["sprache", "fragen"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert len(out.strip()) > 0
