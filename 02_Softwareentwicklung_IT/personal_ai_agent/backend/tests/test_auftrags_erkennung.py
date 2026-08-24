"""Tests für die Auftragserkennung (Fehlklassifikation von Meta-Gesprächen)."""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.auftrags_erkennung import ist_auftrag  # noqa: E402


def test_meta_kommunikation_ist_kein_auftrag():
    """Meta-Gespräch (Lob über Hermes/Agent) darf NICHT als Coding erkannt werden."""
    msg = "Super, du hast was geschafft. Das sieht doch gut aus. Da ist quasi immer noch ein kleines Problem mit der Kommunikation zwischen Hermes und diesem Agenten hier."
    ok, _, _, _ = ist_auftrag(msg)
    assert ok is False, "Meta-Gespräch wurde fälschlich als Coding-Auftrag erkannt"


def test_frage_nach_zustand_kein_auftrag():
    ok, _, _, _ = ist_auftrag("Wie ist der aktuelle Stand des Projekts?")
    assert ok is False


def test_echter_coding_auftrag_erkannt():
    ok, _, kat, _ = ist_auftrag("Baue einen neuen /health-Endpoint in der FastAPI-App")
    assert ok is True
    assert kat in ("feature", "bug", "refactor", "frage")
