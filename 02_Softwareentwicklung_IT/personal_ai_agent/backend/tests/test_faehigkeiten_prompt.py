"""Tests: Fähigkeiten-Selbstbild im System-Prompt (Task 2)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import faehigkeiten  # noqa: E402


def test_faehigkeits_block_enthaelt_kann_und_grenzen():
    block = faehigkeiten.faehigkeits_block()
    assert "DEINE FÄHIGKEITEN & GRENZEN" in block
    assert "Du kannst:" in block
    assert "Du kannst NICHT" in block
    assert "Hermes" in block  # Grenz-Handling erwähnt


def test_faehigkeits_block_nennt_terminal_als_grenze():
    block = faehigkeiten.faehigkeits_block()
    assert "terminal" in block.lower()


def test_faehigkeits_block_verspricht_kein_hermes_werkzeug():
    """Befund 10.10.2026: Der Block nannte Hermes ein „benutzbares Werkzeug" —
    das Modell wollte es aufrufen, es existiert aber nicht in der
    Werkzeugliste („mein Personal Agent wollte Hermes, was gar nicht
    aktiviert ist"). Der Block muss die automatische Uebergabe klarstellen
    und darf keine aufrufbare Uebergabe versprechen."""
    block = faehigkeiten.faehigkeits_block()
    assert "benutzbares Werkzeug" not in block
    assert "kein Werkzeug in deiner Werkzeugliste" in block
    assert "automatisch im Backend" in block
    # Die alte Formel darf nicht mehr drinstehen: sie liess das Modell eine
    # Uebergabe behaupten, die so nie passiert.
    assert "Das übernimmt Hermes" not in block


def test_load_system_prompt_hängt_block_an():
    """load_system_prompt() enthält den Fähigkeiten-Block."""
    from app.services.llm_service import llm_service
    # System-Prompt-Dateien könnten fehlen → wir mocken sie mit Fake-Inhalt.
    with mock.patch.object(llm_service, "load_system_prompt", wraps=llm_service.load_system_prompt) as _:
        with mock.patch("app.services.llm_service.settings.system_prompt_file", "___nicht_da___"), \
             mock.patch("app.services.llm_service.settings.system_prompt_local_file", "___nicht_da___"):
            prompt = llm_service.load_system_prompt()
    assert "DEINE FÄHIGKEITEN" in prompt
    assert "Hermes" in prompt
