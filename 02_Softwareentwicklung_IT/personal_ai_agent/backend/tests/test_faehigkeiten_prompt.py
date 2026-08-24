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
