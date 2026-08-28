"""Tests für die Chat-Volltextsuche (Ein-Chat / suche)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import chat_suche  # noqa: E402


def test_suche_findet_treffer():
    """Findet Nachrichten mit dem Suchbegriff, sortiert nach Zeit."""
    nachrichten = [
        {"role": "user", "content": "Was ist mein Berufsziel?",
         "zeit": "2026-02-01T10:00:00"},
        {"role": "assistant", "content": "AI-Engineering, basierend auf deinem Profil.",
         "zeit": "2026-02-01T10:00:05"},
        {"role": "user", "content": "Wie plane ich die Bewerbung?",
         "zeit": "2026-02-02T09:00:00"},
    ]
    with mock.patch("app.router.chat.conversations", {"conv1": nachrichten}):
        r = asyncio_looper(chat_suche("bewerbung"))
    assert r["anzahl"] == 1
    assert r["treffer"][0]["text"] == "Wie plane ich die Bewerbung?"


def test_suche_kurz_leer():
    """Zu kurzer Begriff → Hinweis, keine Treffer."""
    with mock.patch("app.router.chat.conversations", {}):
        r = asyncio_looper(chat_suche("a"))
    assert r["hinweis"]


def asyncio_looper(coro):
    import asyncio
    return asyncio.run(coro)
