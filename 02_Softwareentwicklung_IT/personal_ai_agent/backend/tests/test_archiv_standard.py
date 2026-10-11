"""
Der Standardweg in die Chat-Archive: erst der volle Index, dann der alte.

Anlass (Sebastians Befund Nr. 3, 10.10.2026): „WhatsApp fehlt vollständig —
es kommt kein einziger Zusammenhang aus den WhatsApp-Daten." Die Daten lagen
im vollen Index (``app.services.archiv_suche``), die Standard-Suche und das
Werkzeug ``archiv_suchen`` fragten aber den alten Dienst
(``app.services.archiv_service``) — dessen Vektoren sind der Stand *vor* dem
WhatsApp-Import. Diese Tests halten die Verdrahtung des Standardwegs fest:
Vorrang, Rückfall, Ehrlichkeit bei Ausfall. Kein echter Index, kein Netz.
"""

from __future__ import annotations

import pytest

from app.services.archiv_standard import StandardArchiv, _als_liste


class _Voll:
    """Steht für ``archiv_suche``: gibt ein Ergebnis-Dict mit ``treffer`` zurück."""

    is_available = True

    def __init__(self, treffer=None, fehler=None):
        self._treffer = treffer if treffer is not None else []
        self._fehler = fehler
        self.aufrufe = []

    def hybrid(self, frage, top_k=None):
        self.aufrufe.append((frage, top_k))
        if self._fehler:
            raise self._fehler
        return {"frage": frage, "treffer": self._treffer, "sicher": True, "grund": "ok"}


class _Alt:
    """Steht für ``archiv_service``: gibt eine nackte Trefferliste zurück."""

    is_available = True

    def __init__(self, treffer=None, fehler=None):
        self._treffer = treffer if treffer is not None else []
        self._fehler = fehler
        self.aufrufe = []

    def hybrid(self, frage, top_k=None):
        self.aufrufe.append((frage, top_k))
        if self._fehler:
            raise self._fehler
        return list(self._treffer)


class _Weg:
    is_available = False


def _t(text, source="whatsapp", beginn="2026-03-12T10:00:00+00:00"):
    return {"text": text, "source": source, "beginn": beginn,
            "ende": beginn, "title": "", "zeiger": {}}


# ── Die Form-Uebersetzung ──────────────────────────────────────────────────

def test_dict_form_wird_zur_liste():
    assert _als_liste({"treffer": [{"text": "a"}]}) == [{"text": "a"}]
    assert _als_liste({"treffer": None}) == []
    assert _als_liste({"ohne": "treffer"}) == []
    assert _als_liste([{"text": "b"}]) == [{"text": "b"}]
    assert _als_liste(None) == []


# ── Die Wahl zwischen den beiden Diensten ──────────────────────────────────

def test_voller_index_hat_vorrang_und_der_alte_wird_nicht_befragt():
    voll = _Voll([_t("aus WhatsApp")])
    alt = _Alt([_t("aus dem alten Index", source="chatgpt")])
    dienst = StandardArchiv(voll=voll, alt=alt)

    assert dienst.quelle == "voll"
    treffer = dienst.hybrid("Momo", top_k=3)
    assert treffer == [_t("aus WhatsApp")]
    assert voll.aufrufe == [("Momo", 3)]
    # Der alte Dienst wird gar nicht erst gefragt — der volle hat geliefert.
    assert alt.aufrufe == []


def test_ohne_vollen_index_traegt_der_alte():
    alt = _Alt([_t("aus dem alten Index", source="chatgpt")])
    dienst = StandardArchiv(voll=_Weg(), alt=alt)

    assert dienst.quelle == "alt" and dienst.is_available
    assert dienst.hybrid("Momo") == [_t("aus dem alten Index", source="chatgpt")]
    assert alt.aufrufe == [("Momo", 5)]


def test_stuerzt_der_volle_ab_traegt_der_alte():
    voll = _Voll(fehler=RuntimeError("Index kaputt"))
    alt = _Alt([_t("gerettet", source="gemini")])
    dienst = StandardArchiv(voll=voll, alt=alt)

    assert dienst.hybrid("Momo") == [_t("gerettet", source="gemini")]
    assert alt.aufrufe == [("Momo", 5)]


def test_findet_der_volle_nichts_bekommt_der_alte_eine_zweite_chance():
    voll = _Voll([])
    alt = _Alt([_t("im alten doch gefunden", source="claude-ai")])
    dienst = StandardArchiv(voll=voll, alt=alt)

    assert dienst.hybrid("Momo") == [_t("im alten doch gefunden", source="claude-ai")]
    assert voll.aufrufe and alt.aufrufe


def test_keiner_erreichbar_ist_ehrlich_und_wirft_nicht():
    dienst = StandardArchiv(voll=_Weg(), alt=_Weg())

    assert dienst.quelle is None
    assert dienst.is_available is False
    assert dienst.hybrid("Momo") == []


def test_stuerzt_auch_der_alte_ab_bleibt_es_bei_der_leeren_liste():
    dienst = StandardArchiv(voll=_Weg(), alt=_Alt(fehler=RuntimeError("auch kaputt")))
    assert dienst.hybrid("Momo") == []


# ── Die Verdrahtung in Chat und Werkzeug ───────────────────────────────────

def test_chat_sucht_ueber_den_standardweg(monkeypatch):
    """``router.chat._archiv_treffer`` muss den Standardweg nehmen, nicht den alten."""
    from app.router import chat as chat_modul

    benutzt = {}

    class _Merker(StandardArchiv):
        def hybrid(self, frage, top_k=None):
            benutzt["frage"] = frage
            return [_t("aus dem vollen Index")]

    monkeypatch.setattr(chat_modul, "StandardArchiv", _Merker)

    treffer = chat_modul._archiv_treffer("Momo", True)
    assert treffer == [_t("aus dem vollen Index")]
    assert benutzt["frage"] == "Momo"
    # Der Schalter bleibt: abgeschaltet wird gar nicht gesucht.
    assert chat_modul._archiv_treffer("Momo", False) == []


def test_werkzeug_archiv_suchen_geht_ueber_den_standardweg(monkeypatch):
    from app.services import archiv_standard as std_modul
    from app.services import werkzeuge as wz

    class _Merker(StandardArchiv):
        def hybrid(self, frage, top_k=None):
            return [_t("WhatsApp-Fundstelle")]

    monkeypatch.setattr(std_modul, "StandardArchiv", _Merker)

    e = wz.ausfuehren("archiv_suchen", {"frage": "Momo"})
    assert e.ok and "WhatsApp-Fundstelle" in e.text


def test_werkzeug_meldet_ehrlich_wenn_kein_index_da_ist(monkeypatch):
    from app.services import archiv_service as alt_modul
    from app.services import archiv_suche as voll_modul
    from app.services import werkzeuge as wz

    monkeypatch.setattr(alt_modul, "archiv_service", _Weg())
    monkeypatch.setattr(voll_modul, "archiv_suche", _Weg())

    e = wz.ausfuehren("archiv_suchen", {"frage": "Momo"})
    assert not e.ok and "nicht erreichbar" in e.text


@pytest.mark.parametrize("top_k", [None, 1, 8])
def test_top_k_wird_durchgereicht(top_k):
    voll = _Voll([_t("x")])
    dienst = StandardArchiv(voll=voll, alt=_Weg())
    dienst.hybrid("Momo", top_k=top_k)
    assert voll.aufrufe == [("Momo", top_k or 5)]
