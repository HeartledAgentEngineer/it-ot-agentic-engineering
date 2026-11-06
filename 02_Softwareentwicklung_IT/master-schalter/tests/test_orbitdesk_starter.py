"""Tests für orbitdesk_starter."""
import sys
from master_schalter import orbitdesk_starter


def test_starter_status(capsys):
    code = orbitdesk_starter.main(["status"])
    assert code == 0
    out, _ = capsys.readouterr()
    assert "Master-Status" in out
