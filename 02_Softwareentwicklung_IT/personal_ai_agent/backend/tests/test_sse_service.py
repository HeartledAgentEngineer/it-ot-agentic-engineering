"""Tests für den SSE-Service (Refactoring chat.py)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import sse  # noqa: E402


def test_sse_format():
    payload = {"delta": "hallo", "x": 1}
    out = sse._sse(payload)
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    # wieder parsebar
    import json
    assert json.loads(out[6:].strip())["delta"] == "hallo"


def test_strom_auftrag_live_reicht_meldungen_und_done():
    buch = {
        "status": "laeuft",
        "status_meldungen": ["[ISO] Schritt 1"],
        "ergebnis": "",
    }
    sequenz = iter([
        dict(buch),                                  # 1. poll: laeuft, 1 meldung
        dict(buch, status_meldungen=["[ISO] Schritt 1", "[ISO] Schritt 2"]),
        dict(buch, status="fertig", status_meldungen=[
            "[ISO] Schritt 1", "[ISO] Schritt 2",
        ], ergebnis="Commit abc"),
    ])
    with mock.patch.object(sse.auftrag_service, "einzeln", side_effect=lambda _: next(sequenz)), \
         mock.patch.object(sse.memory_service, "get_memory_count", return_value=7):
        ereignisse = list(sse.strom_auftrag_live("aid", "conv1", "anfang"))
    text = "".join(ereignisse)
    assert "anfang" in text                     # Bestätigung
    assert '"art": "gedanke"' in text           # Zwischenmeldung als gedanke
    assert "Schritt 1" in text and "Schritt 2" in text
    assert '"done": true' in text
    assert "Commit abc" in text                 # Endergebnis
    assert "memory_count" in text and "7" in text
