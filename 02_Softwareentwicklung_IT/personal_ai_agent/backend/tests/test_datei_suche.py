"""Tests für die Handy-Dateisuche."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import datei_suche  # noqa: E402
from app.services.datei_suche import suche_dateien  # noqa: E402


def test_suche_leer_ohne_stichwort():
    """Leerer Suchbegriff → leere Trefferliste (kein Absturz)."""
    assert suche_dateien("") == []


def test_suche_findet_datei(tmp_path):
    """Sucht eine PDF in der freigegebenen Wurzel (gemockt)."""
    # Baue eine Test-Struktur unter tmp_path (simuliert ~/storage/shared/Download)
    download = tmp_path / "Download"
    download.mkdir()
    (download / "bewerbung_sebastian.pdf").write_bytes(b"%PDF-1.4 test")
    (download / "notizen.txt").write_text("hallo", encoding="utf-8")
    (download / "bild.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    with mock.patch.object(datei_suche, "_STORAGE_WURZEL", str(tmp_path)):
        treffer = suche_dateien("bewerbung")
    assert len(treffer) == 1
    assert treffer[0]["name"] == "bewerbung_sebastian.pdf"


def test_suche_ignoriert_nicht_erlaubte_dateien(tmp_path):
    """Nur erlaubte Erweiterungen werden gefunden (kein .exe/.env)."""
    download = tmp_path / "Download"
    download.mkdir()
    (download / "app.exe").write_bytes(b"MZ")
    (download / "secret.env").write_text("KEY=xyz", encoding="utf-8")

    with mock.patch.object(datei_suche, "_STORAGE_WURZEL", str(tmp_path)):
        treffer = suche_dateien("")
    # leeres Stichwort → sofort []
    assert treffer == []


def test_ordner_fehlend_kein_crash():
    """Fehlende Speicherwurzel → leere Treffer, kein Crash."""
    with mock.patch.object(datei_suche, "_STORAGE_WURZEL", "/nicht/vorhanden/xyz"):
        assert suche_dateien("etwas") == []
