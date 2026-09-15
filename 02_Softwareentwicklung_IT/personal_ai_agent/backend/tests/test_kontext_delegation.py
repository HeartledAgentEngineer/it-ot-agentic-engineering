"""Tests: Kontext-Transfer an Hermes bei der Delegation (Variante C)."""
import os
import sys
from unittest import mock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router.chat import _baue_kontext  # noqa: E402

# Alle Patches dieses Moduls laufen über die Globals der importierten Funktion
# (siehe `_kontext_fuer`). Warum: `test_chat_verlauf.py` wirft
# `app.router.chat` aus `sys.modules` und importiert das Modul neu — ein Patch
# per Modulname träfe dann ein anderes Objekt als die hier importierte Funktion.


def test_baue_kontext_leer_ohne_verlauf():
    """Ohne Verlauf/Erinnerungen ist der Kontext leer (kein Bruch)."""
    with mock.patch.dict(_baue_kontext.__globals__, {
            "conversations": {},
            "_get_or_create_conversation": lambda _: "keine",
            "memory_service": mock.Mock(
                retrieve_relevant_memories=lambda *a, **k: []
            ),
    }):
        assert _baue_kontext("Testfrage") == ""


def test_kontext_wird_an_buch_weitergegeben():
    """route_auftrag gibt den Kontext als Teil des Hermes-Auftrags weiter."""
    from app.services import chat_routing

    called = {}
    def fake_anlegen(auftrag, hinweis=None, kategorie=None, komplexitaet=None):
        called["auftrag"] = auftrag
        return {"id": "abc12345"}
    def fake_status(_id):
        pass

    with mock.patch.object(chat_routing, "hermes_gateway") as gw, \
         mock.patch("app.services.chat_routing.hermes_local_ist_verfuegbar", return_value=False), \
         mock.patch.object(chat_routing, "anlegen_im_buch", side_effect=fake_anlegen), \
         mock.patch.object(chat_routing, "statusmeldung_wartet", side_effect=fake_status), \
         mock.patch.object(chat_routing, "verknuepfe_chat", return_value=None):
        gw.sende_auftrag.return_value = None
        r = chat_routing.route_auftrag(
            "Baue ein Skript",
            "Testbegründung", "feature", "mittel",
            finish_exchange=lambda *a, **k: None,
            get_or_create_conversation=lambda _: "conv1",
            starte_lokale_hermes=lambda *a, **k: None,
            kontext="user: Was ist mein Ziel?\nErinnerung: AI-Engineering",
        )
    assert r["art"] == "buch"
    assert "[Kontext aus dem Gespräch" in called["auftrag"]
    assert "AI-Engineering" in called["auftrag"]


# ── Weitergefuehrter Faden im Coding-Chat (Stand 2026-09-15) ──────────────
# Wunsch Sebastian: „die Gespräche müssen weitergeführt werden". Jeder Auftrag
# im Coding-Chat ist ein frischer `hermes chat -q`-Prozess — Kontinuitaet
# entsteht nur im Kontextpaket. Vorher: 3 Runden x 400 Zeichen (Faden riss).


def _verlauf(n: int, laenge: int = 20):
    """n Runden (Frage/Antwort) — jede Nachricht eindeutig."""
    msgs = []
    for i in range(n):
        msgs.append({"role": "user", "content": f"Frage {i} " + "x" * laenge})
        msgs.append({"role": "assistant", "content": f"Antwort {i} " + "y" * laenge})
    return msgs


def _kontext_fuer(cid: str, nachrichten, frage="Was war der letzte Schritt?"):
    """Baut den Kontext mit isoliertem Verlauf.

    WICHTIG: Gepatcht wird der Globals-Dict der Funktion `_baue_kontext` SELBST
    — nicht `app.router.chat`. Grund: `test_chat_verlauf.py` löscht
    `app.router.chat` aus `sys.modules` und importiert das Modul neu. Danach
    läuft ein Patch auf dem frischen Modul ins Leere, während die hier
    importierte Funktion weiter den ALTEN, geteilten Topf liest (im
    Sammellauf: fremde Inhalte oder leer).
    """
    def _conv(_):
        return cid

    with mock.patch.dict(_baue_kontext.__globals__, {
            "conversations": {cid: nachrichten},
            "_get_or_create_conversation": _conv,
            "memory_service": mock.Mock(
                retrieve_relevant_memories=lambda *a, **k: []
            ),
    }):
        return _baue_kontext(frage, cid)


def test_coding_chat_bekommt_mehr_runden_als_hauptchat():
    verlauf = _verlauf(8)          # 16 Nachrichten
    haupt = _kontext_fuer("conv_main", verlauf)
    code = _kontext_fuer("conv_code", verlauf)

    # Haupt-Chat: unveraendert knapp (3 Runden).
    assert len(haupt.split("\n")) == 3, haupt
    # Coding-Chat: deutlich weiter zurueck.
    assert len(code.split("\n")) >= 8, code
    # Beide haben das Neueste ...
    assert "Frage 7" in haupt and "Frage 7" in code
    # ... aber nur der Coding-Chat greift weiter zurueck.
    assert "Frage 2" not in haupt
    assert "Frage 2" in code


def test_coding_chat_haelt_lange_nachrichten_laenger():
    lang = "D" * 900
    verlauf = [{"role": "user", "content": lang}]
    haupt = _kontext_fuer("conv_main", verlauf)
    code = _kontext_fuer("conv_code", verlauf)

    assert haupt.count("D") == 400 and haupt.endswith("…")   # gekuerzt
    assert code.count("D") == 900                            # vollstaendig


def test_coding_chat_deckel_wird_eingehalten():
    """Genug Material fuer 14400 Zeichen — der Deckel greift, das NEUESTE bleibt."""
    verlauf = [{"role": "user", "content": "Z" * 1195 + f"{i:05d}"}
               for i in range(12)]
    code = _kontext_fuer("conv_code", verlauf)
    assert len(code) <= 7000 + 2, len(code)
    assert code.startswith("…")            # vorne gekuerzt, hinten vollstaendig
    assert "00011" in code                 # die neueste Nachricht ist dabei

    haupt = _kontext_fuer("conv_main", verlauf)
    assert not haupt.startswith("…")       # Haupt-Chat bleibt unter seinem Deckel


def test_statuszeilen_bleiben_aus_dem_kontext():
    """Hermes-Statuszeilen mit Zeitstempel sind kein Gespraechs-Kontext."""
    verlauf = [
        {"role": "user", "content": "Baue Knopf X ein"},
        {"role": "assistant", "content": "[10:48:20] 🔧 Hermes bearbeitet …"},
        {"role": "assistant", "content": "Erledigt, Commit 1234abcd."},
    ]
    code = _kontext_fuer("conv_code", verlauf)
    assert "Baue Knopf X ein" in code
    assert "Erledigt" in code
    assert "bearbeitet" not in code
