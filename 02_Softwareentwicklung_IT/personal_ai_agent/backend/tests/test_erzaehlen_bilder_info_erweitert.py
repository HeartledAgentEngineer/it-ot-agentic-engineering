"""Tests für erweiterte Bildbeschreibungs-Quellen und englische Gemini-Bildgeschichten (01.11.2026)."""
from __future__ import annotations

import json
from pathlib import Path
from app.services import erzaehl_service


def test_beschreibungen_alle_pfade_und_gesamt_lesen(tmp_path, monkeypatch):
    """Prüft, dass mehrere JSONL-Dateien (Haupt-, Reich-, Rest-Bestand) zusammengeführt werden."""
    ereignisse_datei = tmp_path / "ereignisse.jsonl"
    ereignisse_datei.write_text(
        json.dumps({
            "kennung": "E-Test",
            "event": "Testevent",
            "datei_kennungen": [101, 102, 103, 104]
        }) + "\n",
        encoding="utf-8"
    )
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse_datei))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))

    # Basis-Datei
    (tmp_path / "bild_beschreibungen.jsonl").write_text(
        json.dumps({"fileid": 101, "beschreibung": "Basis Beschreibung 101"}) + "\n" +
        json.dumps({"fileid": 102, "beschreibung": "Basis Beschreibung 102"}) + "\n",
        encoding="utf-8"
    )
    # Reiche Datei überschreibt 102 und ergänzt 103
    (tmp_path / "bild_beschreibungen_reich.jsonl").write_text(
        json.dumps({"fileid": 102, "beschreibung": "Reiche Gemini Beschreibung 102"}) + "\n" +
        json.dumps({"fileid": 103, "beschreibung": "Reiche Gemini Beschreibung 103"}) + "\n",
        encoding="utf-8"
    )
    # Rest-Datei (wie Fotobuch) ergänzt 104
    (tmp_path / "bild_beschreibungen_rest_reich.jsonl").write_text(
        json.dumps({"fileid": 104, "beschreibung": "A newborn baby rests peacefully."}) + "\n",
        encoding="utf-8"
    )

    info = erzaehl_service.bilder_info("E-Test")
    assert info is not None
    assert info["mit_beschreibung"] == 4
    assert info["bilder"]["101"]["beschreibung"] == "Basis Beschreibung 101"
    assert info["bilder"]["102"]["beschreibung"] == "Reiche Gemini Beschreibung 102"
    assert info["bilder"]["103"]["beschreibung"] == "Reiche Gemini Beschreibung 103"
    assert info["bilder"]["104"]["beschreibung"] == "A newborn baby rests peacefully."

    # Einzelabruf über beschreibung_holen
    assert erzaehl_service.beschreibung_holen(104) == "A newborn baby rests peacefully."


def test_ki_geschichte_mit_englischer_gemini_beschreibung(tmp_path, monkeypatch):
    """Prüft, dass englische Gemini-Beschreibungen natürlich formuliert werden."""
    ereignisse_datei = tmp_path / "ereignisse.jsonl"
    ereignisse_datei.write_text(
        json.dumps({
            "kennung": "E-Test",
            "event": "Geburtstag",
            "datum": "2020-05-10",
            "datei_kennungen": [201]
        }) + "\n",
        encoding="utf-8"
    )
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse_datei))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))

    (tmp_path / "bild_beschreibungen.jsonl").write_text(
        json.dumps({
            "fileid": 201,
            "beschreibung": "A joyful group of friends laughing around a birthday cake with candles."
        }) + "\n",
        encoding="utf-8"
    )

    # 1. Ich-Form
    res_ich = erzaehl_service.ki_geschichte_generieren(
        fileid=201,
        perspektive="ich",
        ereignis_kennung="E-Test",
        notiz="Ein unvergesslicher Abend."
    )
    assert res_ich["ok"] is True
    assert "Auf dem Bild zu sehen: A joyful group" in res_ich["geschichte"]
    assert "Meine Erinnerung dazu: Ein unvergesslicher Abend." in res_ich["geschichte"]

    # 2. Erzähler
    res_erz = erzaehl_service.ki_geschichte_generieren(
        fileid=201,
        perspektive="erzaehler",
        ereignis_kennung="E-Test",
        notiz="Ein unvergesslicher Abend."
    )
    assert res_erz["ok"] is True
    assert "Bildaufnahme: A joyful group" in res_erz["geschichte"]
    assert 'Dazu die persoenliche Notiz: "Ein unvergesslicher Abend".' in res_erz["geschichte"]
