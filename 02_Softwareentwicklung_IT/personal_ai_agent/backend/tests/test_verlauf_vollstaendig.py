"""Tests: Der Chat-Verlauf muss VOLLSTÄNDIG sein (Wunsch Sebastian, 15.09.2026).

Hintergrund
-----------
Die eigene Nachricht wurde früher erst von `finish_exchange` am **Ende** des
Austauschs in den Verlauf geschrieben. Brach der Stream vorher ab (Browser-
Neustart, Hänger, Timeout), war die Nachricht spurlos verloren — genau das ist
live passiert („meine letzte Nachricht wurde nicht gespeichert").

Seit 15.09.2026 sichert `chat_stream` die User-Nachricht **sofort** beim Start;
`finish_exchange` hängt sie dank Idempotenz-Prüfung nicht doppelt an.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import chat_verlauf  # noqa: E402


@pytest.fixture(autouse=True)
def _isolierter_verlauf(tmp_path, monkeypatch):
    """Eigener Verlauf + eigene Persistenz-Datei je Test.

    Die echten Chat-Daten (conversations.json) werden NIE angefasst: Pfad und
    Topf werden auf tmp_path umgebogen.
    """
    monkeypatch.setattr(chat_verlauf, "_verlauf_datei", str(tmp_path / "verlauf.json"))
    monkeypatch.setattr(chat_verlauf, "_persist_dir", str(tmp_path))
    original = dict(chat_verlauf.conversations)
    chat_verlauf.conversations.clear()
    yield
    chat_verlauf.conversations.clear()
    chat_verlauf.conversations.update(original)


def test_user_nachricht_ueberlebt_abgebrochenen_stream():
    """Sofort-Sicherung: Nachricht steht im Verlauf, auch ohne Antwort."""
    cid = "conv_abbruch"
    chat_verlauf.conversations[cid] = []

    # Stream-Start sichert sofort …
    chat_verlauf.verlauf_nachricht_anhaengen(cid, "user", "Baue Knopf X ein")
    # … und der Stream bricht ab (kein finish_exchange).

    eintraege = chat_verlauf.conversations[cid]
    assert [e["role"] for e in eintraege] == ["user"]
    assert eintraege[0]["content"] == "Baue Knopf X ein"
    assert eintraege[0].get("zeit"), "Zeitstempel fehlt — Verlauf nicht nachvollziehbar"


def test_finish_exchange_haengt_user_nicht_doppelt_an():
    """Idempotenz: Sofort-Sicherung + finish_exchange = genau 2 Einträge."""
    cid = "conv_doppelt"
    chat_verlauf.conversations[cid] = []

    chat_verlauf.verlauf_nachricht_anhaengen(cid, "user", "Frage")
    chat_verlauf.finish_exchange(cid, "Frage", "Antwort")

    rollen = [e["role"] for e in chat_verlauf.conversations[cid]]
    assert rollen == ["user", "assistant"], f"doppelter Eintrag: {rollen}"


def test_finish_exchange_ohne_vorherige_sicherung_schreibt_beides():
    """Abwärtskompatibel: ohne Sofort-Sicherung bleibt das alte Verhalten."""
    cid = "conv_klassisch"
    chat_verlauf.conversations[cid] = []

    chat_verlauf.finish_exchange(cid, "Frage", "Antwort")

    rollen = [e["role"] for e in chat_verlauf.conversations[cid]]
    assert rollen == ["user", "assistant"]


def test_finish_exchange_traegt_bild_pfad_nach():
    """Ein nachgereichter Upload-Pfad wird an den bestehenden User-Eintrag gehängt."""
    cid = "conv_bild"
    chat_verlauf.conversations[cid] = []

    chat_verlauf.verlauf_nachricht_anhaengen(cid, "user", "Schau dir das an")
    chat_verlauf.finish_exchange(cid, "Schau dir das an", "Antwort",
                                 user_bild_pfad="/tmp/bild.jpg")

    eintraege = chat_verlauf.conversations[cid]
    assert [e["role"] for e in eintraege] == ["user", "assistant"]
    assert eintraege[0].get("bild_pfad") == "/tmp/bild.jpg"
