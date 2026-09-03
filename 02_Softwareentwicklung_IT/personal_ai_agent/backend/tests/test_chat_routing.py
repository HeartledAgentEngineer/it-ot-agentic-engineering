"""Tests für den Routing-Service (Track A/C/B — Refactoring chat.py)."""
import os
import sys
from contextlib import contextmanager
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import app.services.chat_routing as routing  # noqa: E402
from app.services.hermes_gateway import hermes_gateway as hg_instanz  # noqa: E402


@pytest.fixture(autouse=True)
def _klare_mocks():
    """Isoliert die Buch-Helfer (anlegen_im_buch etc.)."""
    with mock.patch.object(routing, "anlegen_im_buch", return_value={"id": "eintrag-abc"}), \
         mock.patch.object(routing, "statusmeldung_wartet"), \
         mock.patch.object(routing, "verknuepfe_chat"):
        yield


def _route(pc_antwort=None, lokal_verfuegbar=False):
    """Ruf route_auftrag mit Mock-Kontext auf (Mocks bleiben aktiv)."""
    def finish(conv, msg, reply):
        pass

    def getconv(_):
        return "conv_fake"

    with mock.patch.object(hg_instanz, "sende_auftrag", return_value=pc_antwort), \
         mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar",
                    return_value=lokal_verfuegbar), \
         mock.patch("app.services.chat_routing._starte_lokale_hermes_default",
                    side_effect=lambda *a, **k: {"id": "lokal-eintrag"}):
        return routing.route_auftrag(
            "Baue X", "Verb", "feature", "komplex", finish, getconv,
            routing._starte_lokale_hermes_default,
        )


def test_track_a_pc_erreichbar():
    """PC-Hermes antwortet → art='pc', ziel='pc'."""
    r = _route(pc_antwort="PC-Antwort")
    assert r["art"] == "pc"
    assert r["reply"] == "PC-Antwort"
    assert r["conversation_id"] == "conv_fake"
    assert r["ziel"] == "pc"


def test_track_c_lokal_verfuegbar():
    """PC leer → lokal verfügbar → art='lokal', ziel='handy'."""
    r = _route(pc_antwort=None, lokal_verfuegbar=True)
    assert r["art"] == "lokal"
    assert "Hermes-Aufgabe erkannt" in r["reply"]
    assert r["ziel"] == "handy"


def test_track_b_buch_fallback():
    """PC + lokal nicht da → art='buch', ziel='buch'."""
    r = _route(pc_antwort=None, lokal_verfuegbar=False)
    assert r["art"] == "buch"
    assert "wird übernommen" in r["reply"]
    assert r["ziel"] == "buch"


def test_track_c_antwort_nennt_ziel_handy():
    """Track C: Die Antwort nennt das Ziel sichtbar („Weitergeleitet an")."""
    r = _route(pc_antwort=None, lokal_verfuegbar=True)
    assert "Hermes (Handy)" in r["reply"]


def test_track_b_antwort_ohne_auftragsbuch():
    """Track B: In der Nutzer-Antwort taucht weder 'Auftragsbuch' noch
    'wird bearbeitet' auf – das sichtbare Auftragskonzept ist entfernt
    (nur noch 'Hermes' als Ziel)."""
    r = _route(pc_antwort=None, lokal_verfuegbar=False)
    assert "Weitergeleitet an:" in r["reply"] and "Hermes" in r["reply"]
    assert "Auftragsbuch" not in r["reply"]
    assert "wird bearbeitet" not in r["reply"]
