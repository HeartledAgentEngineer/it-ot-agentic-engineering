"""Tests für die Handy-Dateisuche."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import datei_suche  # noqa: E402
from app.services.datei_suche import lese_datei_info, suche_dateien  # noqa: E402


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


def test_lese_txt_inhalt(tmp_path):
    """liest eine TXT-Datei (Stufe B)."""
    file = tmp_path / "notiz.txt"
    file.write_text("Wichtige Notiz: Azure Kurse starten im September.", encoding="utf-8")
    info = lese_datei_info(str(file))
    assert info["text"] == "Wichtige Notiz: Azure Kurse starten im September."
    assert info["ist_bild"] is False


def test_lese_bild_als_vision(tmp_path):
    """liest ein Bild → ist_bild=True + data_url (Basis64)."""
    file = tmp_path / "foto.png"
    file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    info = lese_datei_info(str(file))
    assert info["ist_bild"] is True
    assert info["data_url"].startswith("data:image/png;base64,")


def test_lese_nicht_existiert_kein_crash():
    """nicht vorhandene Datei → kein Crash, fehler gesetzt."""
    info = lese_datei_info("/nicht/da/datei.pdf")
    assert "fehler" in info


# --- Dateityp-Filter (nur_erweiterungen) ---
# Gleiche Sets wie in app/router/chat.py (_datei_tool, Kern-Fix).
_BILDER = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_DOKUMENTE = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls"}


def _mock_wurzel(tmp_path):
    """Patcht Speicherbasis + Fallback-Wurzeln auf tmp_path (kein /sdcard-Walk)."""
    return [
        mock.patch.object(datei_suche, "_STORAGE_WURZEL", str(tmp_path)),
        mock.patch.object(datei_suche, "_FALLBACK_WURZELN", []),
    ]


def test_suche_nur_erweiterungen_bilder_liefert_nie_pdf(tmp_path):
    """Foto-Kontext (nur_erweiterungen=Bilder) liefert NIE ein PDF — nur Bilder.

    Reproduziert den Live-Bug: Bei einer Foto-Frage tauchte die
    EasyBank-PDF in den Treffern auf. Mit dem Filter darf sie nicht mehr
    erscheinen, obwohl sie im selben Ordner liegt.
    """
    download = tmp_path / "Download"
    download.mkdir()
    (download / "easybank_auszug.pdf").write_bytes(b"%PDF-1.4 test")
    (download / "urlaub.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (download / "portrait.jpg").write_bytes(b"jpeg")

    with _mock_wurzel(tmp_path)[0], _mock_wurzel(tmp_path)[1]:
        treffer = suche_dateien("", neueste_zuerst=True, nur_erweiterungen=_BILDER)
    assert treffer, "es sollten Bilder gefunden werden"
    for t in treffer:
        assert t["erweiterung"] in _BILDER
        assert t["erweiterung"] != ".pdf"
    namen = [t["name"] for t in treffer]
    assert "easybank_auszug.pdf" not in namen


def test_suche_nur_erweiterungen_dokumente_liefert_nie_png(tmp_path):
    """Dokument-Kontext (nur_erweiterungen=Docs) liefert NIE ein PNG/Bild.

    Reproduziert den Live-Bug: Bei einer PDF-Frage tauchten random
    file-PNGs in den Treffern auf. Mit dem Filter dürfen sie nicht mehr
    erscheinen, obwohl sie im selben Ordner liegen.
    """
    download = tmp_path / "Download"
    download.mkdir()
    (download / "easybank_auszug.pdf").write_bytes(b"%PDF-1.4 test")
    (download / "lebenslauf_sebastian.docx").write_bytes(b"docx")
    (download / "random.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    with _mock_wurzel(tmp_path)[0], _mock_wurzel(tmp_path)[1]:
        treffer = suche_dateien("", neueste_zuerst=True, nur_erweiterungen=_DOKUMENTE)
    assert treffer, "es sollten Dokumente gefunden werden"
    for t in treffer:
        assert t["erweiterung"] in _DOKUMENTE
        assert t["erweiterung"] != ".png"
    namen = [t["name"] for t in treffer]
    assert "random.png" not in namen


def test_datei_tool_foto_frage_filtert_auf_bilder():
    """Verdrahtung: Foto-Frage übergibt nur_erweiterungen (Bilder) an suche_dateien."""
    from app.router.chat import _datei_tool  # noqa: E402

    treffer = [{"pfad": "/x/a.jpg", "name": "a.jpg", "erweiterung": ".jpg",
                "groesse_byte": 1, "mtime": 1.0}]
    with mock.patch.object(datei_suche, "suche_dateien",
                           return_value=treffer) as suche, \
         mock.patch.object(datei_suche, "lese_datei_info",
                           return_value={"ist_bild": True, "data_url": ""}):
        _datei_tool("zeig mir das neueste bild auf deinem speicher")
    assert suche.called
    assert suche.call_args.kwargs["nur_erweiterungen"] == _BILDER


def test_datei_tool_pdf_frage_filtert_auf_dokumente():
    """Verdrahtung: PDF/Dokument-Frage übergibt nur_erweiterungen (Docs) an suche_dateien."""
    from app.router.chat import _datei_tool  # noqa: E402

    with mock.patch.object(datei_suche, "suche_dateien", return_value=[]) as suche:
        _datei_tool("finde mir die pdf zeitplan")
    assert suche.called
    assert suche.call_args.kwargs["nur_erweiterungen"] == _DOKUMENTE
