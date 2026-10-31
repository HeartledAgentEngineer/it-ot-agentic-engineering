"""Tests fuer das Best-Practice-Tor (tor.py).

Prueft die selektive Testauswahl (Impact-Analyse), die xdist-Erkennung und die
sichere Rueckfallebene auf die Gesamtsuite.
"""
from __future__ import annotations

import sys
from pathlib import Path

# tor.py importieren
TOR_DIR = Path(__file__).resolve().parents[2] / "tools" / "gate"
if str(TOR_DIR) not in sys.path:
    sys.path.insert(0, str(TOR_DIR))

import tor  # noqa: E402


def test_finde_relevante_tests_direkte_testdatei():
    geaendert = ["02_Softwareentwicklung_IT/personal_ai_agent/backend/tests/test_laeuft.py"]
    tests = tor.finde_relevante_tests(geaendert)
    assert tests == ["tests/test_laeuft.py"]


def test_finde_relevante_tests_gruppen():
    geaendert = [
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/router/gruppen.py",
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/services/gruppen_quiz.py",
    ]
    tests = tor.finde_relevante_tests(geaendert)
    assert len(tests) > 0
    assert "tests/test_gruppen_quiz.py" in tests
    # Keine unbeteiligten Tests
    assert "tests/test_whatsapp_db_import.py" not in tests


def test_finde_relevante_tests_erzaehlen():
    geaendert = ["02_Softwareentwicklung_IT/personal_ai_agent/backend/app/services/erzaehl_service.py"]
    tests = tor.finde_relevante_tests(geaendert)
    assert "tests/test_erzaehlen_bilder_info.py" in tests or "tests/test_erzaehlen.py" in tests


def test_finde_relevante_tests_pii():
    geaendert = ["02_Softwareentwicklung_IT/personal_ai_agent/backend/app/services/pii_shield.py"]
    tests = tor.finde_relevante_tests(geaendert)
    assert "tests/test_pii_shield.py" in tests


def test_finde_relevante_tests_voice_session():
    geaendert = ["02_Softwareentwicklung_IT/personal_ai_agent/backend/app/router/voice_stream.py"]
    tests = tor.finde_relevante_tests(geaendert)
    assert "tests/test_voice_session.py" in tests


def test_finde_relevante_tests_kern_dateien_erzwingen_alles():
    for kern in [
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/config.py",
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/main.py",
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/sicherheit.py",
        "02_Softwareentwicklung_IT/personal_ai_agent/backend/app/models.py",
    ]:
        tests = tor.finde_relevante_tests([kern])
        assert tests == ["tests/"], f"Kern-Datei {kern} muss alle Tests erzwingen"


def test_finde_relevante_tests_tor_tool():
    tests = tor.finde_relevante_tests(["02_Softwareentwicklung_IT/personal_ai_agent/tools/gate/tor.py"])
    assert tests == ["tests/test_tor.py"]


def test_finde_relevante_tests_unbekannt_faellt_auf_alles_zurueck():
    tests = tor.finde_relevante_tests(["irgendeine/unbekannte_datei.xyz"])
    assert tests == ["tests/"]


def test_xdist_verfuegbarkeit():
    # pytest-xdist wurde installiert
    assert tor.hat_xdist() is True
