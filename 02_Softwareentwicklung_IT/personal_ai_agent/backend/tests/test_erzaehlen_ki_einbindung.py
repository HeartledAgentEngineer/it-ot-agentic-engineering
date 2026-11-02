"""Einbindung der KI-Erzählung in erzaehl_service (02.11.2026).

Prüft die Nahtstelle ``_erzaehle_text``: das KI-Modell formuliert frei, wenn ein
Schlüssel da ist; ohne Schlüssel oder bei jedem Fehler greift verlässlich die
Vorlage (die Oberfläche bleibt nie ohne Geschichte). Offline, keine echten Aufrufe.
"""
from __future__ import annotations

from app.services import erzaehl_service as es
from app.services import geschichte_erzaehlen_ki as kem

FAKTEN = dict(
    titel="Taufe", datum_text="am 3. Mai 2003", ort="Hamburg",
    personen=["Sebastian", "Matthias"], beschreibungen=["Ein Mann mit einem Baby."],
    notiz="Papa hat mit mir gespielt.", anzahl_dateien=1, perspektive="ich",
)


def test_ohne_schluessel_vorlage(monkeypatch):
    monkeypatch.setattr(kem, "verfuegbar", lambda: False)
    text, quelle, kosten = es._erzaehle_text(**FAKTEN)
    assert quelle == "vorlage"
    assert kosten is None
    assert isinstance(text, str) and text.strip()


def test_mit_schluessel_nimmt_die_ki(monkeypatch):
    monkeypatch.setattr(kem, "verfuegbar", lambda: True)
    monkeypatch.setattr(kem, "erzaehle_geschichte",
                        lambda **kw: {"ok": True, "geschichte": "Eine fließende Geschichte.",
                                      "modell": "x", "kosten_usd": 0.0005})
    text, quelle, kosten = es._erzaehle_text(**FAKTEN)
    assert quelle == "ki"
    assert text == "Eine fließende Geschichte."
    assert kosten == 0.0005


def test_ki_wirft_faellt_auf_vorlage(monkeypatch):
    monkeypatch.setattr(kem, "verfuegbar", lambda: True)

    def boom(**kw):
        raise RuntimeError("netz weg")

    monkeypatch.setattr(kem, "erzaehle_geschichte", boom)
    text, quelle, kosten = es._erzaehle_text(**FAKTEN)
    assert quelle == "vorlage"
    assert isinstance(text, str) and text.strip()


def test_ki_nicht_ok_faellt_auf_vorlage(monkeypatch):
    monkeypatch.setattr(kem, "verfuegbar", lambda: True)
    monkeypatch.setattr(kem, "erzaehle_geschichte", lambda **kw: {"ok": False, "grund": "leer"})
    text, quelle, kosten = es._erzaehle_text(**FAKTEN)
    assert quelle == "vorlage"
    assert kosten is None
