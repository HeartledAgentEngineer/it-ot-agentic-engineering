"""KI-Erzählung: eine frei formulierte deutsche Geschichte statt Vorlagen-Stakkato (02.11.2026).

Wunsch Sebastian: Die Bild-/Anlassgeschichte soll das KI-Modell aus den KI-Bild-
beschreibungen, den Personen und seiner eigenen Erinnerung zu EINER zusammen-
hängenden Erzählung verweben (kein Stakkato, kein Zusammenreimen). Englische
Bildbeschreibungen werden dabei vom Modell in deutsche Prosa umgeschrieben.

Eiserne Regeln (wie beim Vision-Modul ``bild_beschreibung_vorschlag.py``):
  * ZDR erzwungen, ``data_collection: deny`` im Aufruf selbst.
  * Fehler als ``{"ok": False, "grund": ...}`` mit ehrlichem Klartext — nie Schlüssel/URL/Ausnahmetext.
  * Der Client ist einspielbar (Tests arbeiten mit Attrappen, kein Netz).
  * Es wird NICHTS gespeichert — nur der Text geht zurück.

Aufruf:  .venv/Scripts/python -m pytest tests/test_geschichte_erzaehlen_ki.py -q
"""
from __future__ import annotations

import httpx
import pytest

from app.services import geschichte_erzaehlen_ki as kem


class FakeClient:
    """Zeichnet den Aufruf auf und liefert eine feste Antwort (oder wirft)."""

    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort
        self.fehler = fehler
        self.aufrufe = []

    def chat_completion(self, messages, **kwargs):
        self.aufrufe.append({"messages": messages, "kwargs": kwargs})
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


def _antwort(text="Mein Papa und ich lagen an jenem Tag beieinander.", kosten=0.0004):
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 120, "cost": kosten},
    }


FAKTEN = dict(
    titel="Taufe",
    datum_text="am 3. Mai 2003",
    ort="Hamburg",
    personen=["Sebastian", "Matthias"],
    beschreibungen=["An adult lies down playing with a small baby beside him."],
    notiz="Papa hat mit mir gespielt, ich war erst ein paar Wochen alt.",
    anzahl_dateien=1,
    perspektive="ich",
)


def test_baue_nachricht_enthaelt_die_fakten():
    text = kem.baue_nachricht(**FAKTEN)
    for muss in ("Taufe", "3. Mai 2003", "Hamburg", "Matthias", "Papa hat mit mir gespielt"):
        assert muss in text, f"fehlt in der Nachricht: {muss}"
    # Die (englische) Bildbeschreibung ist als Material dabei.
    assert "small baby" in text


def test_baue_nachricht_perspektive_unterscheidet_sich():
    ich = kem.baue_nachricht(**{**FAKTEN, "perspektive": "ich"})
    erz = kem.baue_nachricht(**{**FAKTEN, "perspektive": "erzaehler"})
    assert ich != erz
    assert "Ich-Form" in ich or "Ich-Perspektive" in ich or "in der Ich-Form" in ich


def test_erzaehle_geschichte_erfolg_mit_attrappe():
    client = FakeClient(antwort=_antwort())
    erg = kem.erzaehle_geschichte(client=client, **FAKTEN)
    assert erg["ok"] is True
    assert erg["geschichte"].startswith("Mein Papa")
    assert erg["modell"]
    assert erg["kosten_usd"] == pytest.approx(0.0004)
    # Genau ein Aufruf, mit ZDR-Härtung im Aufruf selbst.
    assert len(client.aufrufe) == 1
    extra = client.aufrufe[0]["kwargs"].get("extra_payload") or {}
    assert extra.get("provider", {}).get("data_collection") == "deny"


def test_erzaehle_geschichte_schickt_die_fakten_ans_modell():
    client = FakeClient(antwort=_antwort())
    kem.erzaehle_geschichte(client=client, **FAKTEN)
    gesendet = repr(client.aufrufe[0]["messages"])
    assert "Taufe" in gesendet and "Matthias" in gesendet
    assert "Papa hat mit mir gespielt" in gesendet


def test_ohne_schluessel_und_ohne_client_kein_netzaufruf(monkeypatch):
    # Ohne Schlüssel und ohne eingespielten Client darf NICHTS ans Netz gehen.
    monkeypatch.setattr(kem, "_schluessel", lambda: "")
    erg = kem.erzaehle_geschichte(client=None, **FAKTEN)
    assert erg["ok"] is False
    assert "grund" in erg and isinstance(erg["grund"], str) and erg["grund"]


def test_zeitgrenze_ehrlich_ohne_geheimnis():
    client = FakeClient(fehler=httpx.TimeoutException("boom"))
    erg = kem.erzaehle_geschichte(client=client, **FAKTEN)
    assert erg["ok"] is False
    assert "boom" not in erg["grund"]
    assert "Zeit" in erg["grund"] or "später" in erg["grund"].lower()


def test_leere_antwort_ehrlich():
    client = FakeClient(antwort={"choices": [{"message": {"content": "   "}}]})
    erg = kem.erzaehle_geschichte(client=client, **FAKTEN)
    assert erg["ok"] is False
    assert isinstance(erg["grund"], str) and erg["grund"]


def test_verfuegbar_ist_bool():
    assert isinstance(kem.verfuegbar(), bool)
