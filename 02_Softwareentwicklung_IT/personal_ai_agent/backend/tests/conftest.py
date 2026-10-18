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


@pytest.fixture(autouse=True)
def _sitzungen_nie_neben_das_projekt(tmp_path, monkeypatch):
    """Die Sitzungs-Ablage (To-do Punkt 13) zeigt in Tests in einen tmp-Ordner.

    Ohne diese Vorrichtung schriebe jeder Anmelde-Test in die echte Datei neben
    dem Projekt (`.sitzungen.json`) - und die Testdateien schoeben sich
    gegenseitig Sitzungen unter, weil sie den Speicher leeren, die Ablage aber
    bestehen bliebe. Der Lade-Merker wird mit zurueckgesetzt, damit jeder Test
    wieder wie ein frischer Prozess startet.
    """
    from app.config import settings as _settings
    from app.router import auth

    monkeypatch.setattr(_settings, "sitzungen_datei", str(tmp_path / ".sitzungen.json"))
    monkeypatch.setattr(auth, "_SITZUNGEN_GELADEN", None)
