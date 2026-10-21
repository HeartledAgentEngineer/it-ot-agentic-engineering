"""Bilder im Chat gehen an EIN zentrales Vision-Modell (Befund 21.10.2026).

``router/chat.py`` hatte ``google/gemini-2.5-flash`` an zwei Stellen fest
eingetragen. OpenRouter bietet dieses Modell inzwischen nur noch über Google AI
Studio an — das steht nicht auf der Provider-Whitelist (dort Google Vertex).
Folge: Jede Bildfrage endete in „Dieses Modell ist mit deinen
Datenschutz-Einstellungen nicht nutzbar". Der Modell-Router kannte schon ein
gültiges Vision-Modell (``MODELL_VISION``); beide Chat-Wege nutzen jetzt genau
dieses, damit ein Modellwechsel nur noch an einer Stelle passiert.
"""
from pathlib import Path

from app.services.modell_router import MODELL_VISION

CHAT = Path(__file__).resolve().parents[1] / "app" / "router" / "chat.py"


def test_chat_traegt_kein_vision_modell_fest_ein():
    text = CHAT.read_text(encoding="utf-8")
    assert "gemini-2.5-flash" not in text


def test_beide_chat_wege_nutzen_das_zentrale_vision_modell():
    text = CHAT.read_text(encoding="utf-8")
    # /chat (vision_modell = …) und /chat/stream (s_modell = …)
    assert text.count("MODELL_VISION") >= 3  # Import + zwei Verwendungen


def test_zentrales_vision_modell_ist_kein_abgekuendigtes():
    assert MODELL_VISION != "google/gemini-2.5-flash"
    assert MODELL_VISION.startswith("google/gemini-")
