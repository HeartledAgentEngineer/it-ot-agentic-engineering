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

from pathlib import Path

import pytest

from app.services.archiv_standard import StandardArchiv, _als_liste


class _Voll:
    """Steht für ``archiv_suche``: gibt ein Ergebnis-Dict mit ``treffer`` zurück."""

    is_available = True

    def __init__(self, treffer=None, fehler=None):
        self._treffer = treffer if treffer is not None else []
        self._fehler = fehler
        self.aufrufe = []
        self.wege = []  # (Methodenname, frage, top_k) — für die drei Suchwege

    def _ergebnis(self, frage):
        if self._fehler:
            raise self._fehler
        return {"frage": frage, "treffer": self._treffer, "sicher": True, "grund": "ok"}

    def hybrid(self, frage, top_k=None):
        self.aufrufe.append((frage, top_k))
        self.wege.append(("hybrid", frage, top_k))
        return self._ergebnis(frage)

    def volltext_suche(self, frage, top_k=None):
        self.wege.append(("volltext_suche", frage, top_k))
        return self._ergebnis(frage)

    def semantische_suche(self, frage, top_k=None):
        self.wege.append(("semantische_suche", frage, top_k))
        return self._ergebnis(frage)

    def statistik(self):
        return {"verfuegbar": True, "gesamt": {"chunks": 52679}, "hinweis": "voller Index"}


class _Alt:
    """Steht für ``archiv_service``: gibt eine nackte Trefferliste zurück."""

    is_available = True

    def __init__(self, treffer=None, fehler=None):
        self._treffer = treffer if treffer is not None else []
        self._fehler = fehler
        self.aufrufe = []
        self.wege = []

    def _liste(self):
        if self._fehler:
            raise self._fehler
        return list(self._treffer)

    def hybrid(self, frage, top_k=None):
        self.aufrufe.append((frage, top_k))
        self.wege.append(("hybrid", frage, top_k))
        return self._liste()

    def suche(self, frage, top_k=None):
        self.wege.append(("suche", frage, top_k))
        return self._liste()

    def semantische_suche(self, frage, top_k=None):
        self.wege.append(("semantische_suche", frage, top_k))
        return self._liste()

    def status(self):
        return {"verfuegbar": True, "chunks": 100, "hinweis": "alter Dienst"}


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


# ── Die drei Suchwege laufen alle ueber denselben Standardweg ──────────────

def test_volltext_fragt_den_vollen_index_und_laesst_den_alten_in_ruhe():
    """Der volle Index heisst ``volltext_suche`` — der alte ``suche``."""
    voll = _Voll([_t("voller Wortlaut")])
    alt = _Alt([_t("alter Wortlaut", source="chatgpt")])
    dienst = StandardArchiv(voll=voll, alt=alt)

    assert dienst.suche("Momo", top_k=2) == [_t("voller Wortlaut")]
    assert voll.wege == [("volltext_suche", "Momo", 2)]
    assert alt.wege == []


def test_volltext_faellt_auf_die_alte_suche_zurueck():
    alt = _Alt([_t("alter Wortlaut", source="chatgpt")])
    dienst = StandardArchiv(voll=_Weg(), alt=alt)

    assert dienst.suche("Momo") == [_t("alter Wortlaut", source="chatgpt")]
    assert alt.wege == [("suche", "Momo", 5)]


def test_semantische_suche_geht_ueber_den_vollen_index():
    voll = _Voll([_t("Bedeutung aus dem vollen Index")])
    dienst = StandardArchiv(voll=voll, alt=_Weg())

    assert dienst.semantische_suche("Momo") == [_t("Bedeutung aus dem vollen Index")]
    assert voll.wege == [("semantische_suche", "Momo", 5)]


def test_fehlt_einem_dienst_die_methode_wird_er_uebergangen_statt_zu_werfen():
    class _NurHybrid:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return {"treffer": [_t("nur hybrid")]}

    alt = _Alt([_t("alter Weg", source="gemini")])
    dienst = StandardArchiv(voll=_NurHybrid(), alt=alt)

    # Der volle kennt ``volltext_suche`` nicht -> er wird uebergangen, der alte traegt.
    assert dienst.suche("Momo") == [_t("alter Weg", source="gemini")]
    assert alt.wege == [("suche", "Momo", 5)]


# ── Der Status kommt vom tragenden Dienst ──────────────────────────────────

def test_status_kommt_vom_vollen_index_und_nennt_die_quelle():
    dienst = StandardArchiv(voll=_Voll([_t("x")]), alt=_Alt([_t("y")]))
    s = dienst.status()

    assert s["verfuegbar"] is True and s["quelle"] == "voll"
    assert s["gesamt"]["chunks"] == 52679          # aus ``statistik`` des vollen
    assert "hinweis" in s


def test_status_ohne_vollen_index_kommt_vom_alten_dienst():
    dienst = StandardArchiv(voll=_Weg(), alt=_Alt([_t("y")]))
    s = dienst.status()

    assert s["verfuegbar"] is True and s["quelle"] == "alt"
    assert s["chunks"] == 100                       # aus ``status`` des alten


def test_status_ohne_erreichbaren_dienst_ist_ehrlich():
    assert StandardArchiv(voll=_Weg(), alt=_Weg()).status() == {
        "verfuegbar": False, "quelle": None,
    }


def test_status_wenn_der_tragende_dienst_keinen_stand_liefert():
    class _OhneStand:
        is_available = True

    s = StandardArchiv(voll=_OhneStand(), alt=_Weg()).status()
    assert s == {"verfuegbar": True, "quelle": "voll"}


# ── Die Nachschau-Endpunkte (/api/archiv) nehmen den Standardweg ───────────

def test_nachschau_endpunkte_gehen_ueber_den_standardweg(monkeypatch):
    from app.router import archiv as archiv_modul

    benutzt = {}

    class _Merker:
        quelle = "voll"

        def suche(self, frage, top_k=None):
            benutzt["volltext"] = (frage, top_k)
            return [_t("aus dem vollen Index")]

        def semantische_suche(self, frage, top_k=None):
            benutzt["semantisch"] = (frage, top_k)
            return [_t("aus dem vollen Index")]

        def hybrid(self, frage, top_k=None):
            benutzt["hybrid"] = (frage, top_k)
            return [_t("aus dem vollen Index")]

        def status(self):
            return {"verfuegbar": True, "quelle": "voll"}

    monkeypatch.setattr(archiv_modul, "StandardArchiv", _Merker)

    a = archiv_modul.suche(q="Momo", top_k=3, modus="hybrid")
    assert a["treffer"] == [_t("aus dem vollen Index")] and a["quelle"] == "voll"
    assert benutzt["hybrid"] == ("Momo", 3)

    archiv_modul.suche(q="Momo", top_k=3, modus="volltext")
    assert benutzt["volltext"] == ("Momo", 3)

    archiv_modul.suche(q="Momo", top_k=3, modus="semantisch")
    assert benutzt["semantisch"] == ("Momo", 3)

    assert archiv_modul.status() == {"verfuegbar": True, "quelle": "voll"}


def test_router_archiv_greift_nicht_mehr_direkt_auf_den_alten_dienst():
    """Waechter gegen den Rueckfall: kein direkter Griff auf ``archiv_service``."""
    from app.router import archiv as archiv_modul

    text = Path(archiv_modul.__file__).read_text(encoding="utf-8")
    assert "archiv_service" not in text
    assert "StandardArchiv" in text
