"""Tests für die Befehlszeile `masterwechsel`."""
import io
import json

import pytest

from master_schalter import cli, signale


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    return tmp_path / "daten"


def test_statuszeile_speichert_und_zeigt(daten, monkeypatch, capsys):
    eingabe = {"session_id": "geheim", "rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": 4102444800},
        "seven_day": {"used_percentage": 41.2, "resets_at": 4102444800}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(eingabe)))

    assert cli.main(["statuszeile"]) == 0

    assert capsys.readouterr().out.strip() == "Claude 5h 24% · Wo 41%"
    gespeichert = json.loads((daten / "kontingent-claude.json").read_text(encoding="utf-8"))
    assert "session_id" not in json.dumps(gespeichert)


def test_statuszeile_stuerzt_nie_ab(daten, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("kein json"))
    assert cli.main(["statuszeile"]) == 0
    assert capsys.readouterr().out.strip() == "Claude: keine Daten"


def test_claude_kontingent_von_hand(daten, capsys):
    rc = cli.main(["claude-kontingent", "--fuenf", "79", "--woche", "58",
                   "--reset-fuenf", "2099-01-01T10:00:00+00:00", "--reset-woche", "2099-01-05T21:00:00Z"])
    assert rc == 0
    k = signale.claude_lesen(daten / "kontingent-claude.json")
    assert k.fenster_nach_name("5h").prozent == 79
    assert k.fenster_nach_name("Woche").reset.isoformat() == "2099-01-05T21:00:00+00:00"


def test_claude_kontingent_lehnt_unsinn_ab(daten, capsys):
    assert cli.main(["claude-kontingent", "--fuenf", "150", "--woche", "5",
                     "--reset-fuenf", "2099-01-01T10:00:00Z", "--reset-woche", "2099-01-01T10:00:00Z"]) == 2
    assert not (daten / "kontingent-claude.json").exists()


def test_status_zeigt_beide(daten, capsys):
    assert cli.main(["status"]) == 0
    aus = capsys.readouterr().out
    assert "Claude" in aus and "Codex" in aus and "keine Daten" in aus


def test_version(capsys):
    with pytest.raises(SystemExit) as ende:
        cli.main(["--version"])
    assert ende.value.code == 0
    assert "0.2.0" in capsys.readouterr().out


def test_claude_messen_cli_ruft_adapter_auf(daten, monkeypatch, capsys):
    aufrufe = []
    monkeypatch.setattr(cli.claude_messen, "messen", lambda **kw: aufrufe.append(kw) or True)

    assert cli.main(["claude-messen"]) == 0

    assert aufrufe == [{}]
    assert capsys.readouterr().out.strip() == "Claude-Kontingent aktualisiert."


def test_claude_messen_cli_zeigt_nur_sicheren_fehler(daten, monkeypatch, capsys):
    def fehler(**kw):
        raise cli.claude_messen.MessFehler("Claude-Anmeldung abgelaufen – Claude Code einmal starten")

    monkeypatch.setattr(cli.claude_messen, "messen", fehler)

    assert cli.main(["claude-messen"]) == 1

    aus = capsys.readouterr()
    assert "Claude-Anmeldung abgelaufen" in aus.err
    assert "Traceback" not in aus.out + aus.err
