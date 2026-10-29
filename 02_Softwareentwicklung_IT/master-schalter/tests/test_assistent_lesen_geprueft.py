"""Gezielte Tests des fail-closed Lesers für Wechselvorgänge."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from master_schalter import assistent_vorgaenge as av


def _vorgang(ident: str = "v-1") -> dict:
    return asdict(av.Vorgang(ident, "engineering", "hermes", "codex", "vorbereitet",
                             "2026-10-29T00:00:00+00:00",
                             {"master": "codex", "worker": "codex", "modell": "gpt-6-luna"}, ""))


def test_nicht_angelegte_datei_ist_geprueft_leer(tmp_path):
    assert av.lesen_geprueft(tmp_path / "fehlt.json") == []


@pytest.mark.parametrize("inhalt", ["{kaputt", "{}", "[null]"])
def test_beschaedigter_bestand_oder_ungueltiger_eintrag_wird_abgelehnt(tmp_path, inhalt):
    pfad = tmp_path / "assistent.json"
    pfad.write_text(inhalt, encoding="utf-8")

    with pytest.raises(av.AssistentFehler):
        av.lesen_geprueft(pfad)


def test_doppelte_vorgangskennung_wird_abgelehnt(tmp_path):
    pfad = tmp_path / "assistent.json"
    pfad.write_text(json.dumps([_vorgang(), _vorgang()]), encoding="utf-8")

    with pytest.raises(av.AssistentFehler, match="doppelt"):
        av.lesen_geprueft(pfad)


def test_unlesbarer_bestand_wird_nicht_als_leer_behandelt(tmp_path, monkeypatch):
    pfad = tmp_path / "assistent.json"
    pfad.write_text("[]", encoding="utf-8")
    original = type(pfad).read_text

    def unlesbar(self, *args, **kwargs):
        if self == pfad:
            raise PermissionError("gesperrt")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(pfad), "read_text", unlesbar)
    with pytest.raises(av.AssistentFehler):
        av.lesen_geprueft(pfad)
