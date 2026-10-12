"""Gemeinsame Vorrichtungen für alle Backend-Tests."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _testserver_als_host_erlauben(monkeypatch):
    """Der TestClient schickt ``Host: testserver``.

    Die Host-Prüfung aus P0 (``app/sicherheit.py``) ließe diesen Namen nicht
    durch. Er wird deshalb **nur in Tests** erlaubt und nach jedem Test über
    ``monkeypatch`` zurückgenommen. Die Middleware liest die Liste bei jeder
    Anfrage neu, darum wirkt das auch für eine schon gebaute App.
    """
    from app.config import settings

    bisher = getattr(settings, "erlaubte_hosts", "") or ""
    monkeypatch.setattr(
        settings, "erlaubte_hosts", ",".join(n for n in (bisher, "testserver") if n)
    )
