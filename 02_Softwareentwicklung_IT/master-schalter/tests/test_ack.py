"""Tests für die ACK-Prüfung: nur Assistentenantworten des Zielchats zählen."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import ack

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"
ANDERER = "01a0a68e-5041-7610-a528-38d42f66bed3"
ID = "engineering@4102444800"
SENDUNG = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ordner(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    return tmp_path / "codex"


def _antwort(text, *, zeit=SENDUNG + timedelta(minutes=1), art="response_item",
             rolle="assistant", thread=THREAD, ordner=None):
    ordner = ordner or ack.signale.codex_ordner()
    unter = ordner / "2026" / "10" / "15"
    unter.mkdir(parents=True, exist_ok=True)
    datei = unter / f"rollout-2026-10-15T12-00-00-{thread}.jsonl"
    if art == "response_item":
        nutzlast = {"type": "message", "role": rolle,
                    "content": [{"type": "output_text", "text": text}]}
        zeile = {"timestamp": zeit.isoformat(), "type": "response_item", "payload": nutzlast}
    else:
        zeile = {"timestamp": zeit.isoformat(), "type": "event_msg",
                 "payload": {"type": art if rolle is None else "agent_message", "message": text}}
    with datei.open("a", encoding="utf-8") as f:
        f.write(json.dumps(zeile) + "\n")
    return datei


def test_exakte_kennung_in_assistentenantwort_bestaetigt(ordner):
    _antwort(f"ACK {ID}")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is True


def test_agent_message_bestaetigt_ebenso(ordner):
    _antwort(f"ACK {ID}\nAlles übernommen.", art="event_msg")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is True


def test_ack_muss_den_text_beginnen(ordner):
    _antwort(f"Kurz zur Info: ACK {ID}")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_falsche_kennung_bestaetigt_nicht(ordner):
    _antwort("ACK engineering@9999999999")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_nutzerprompt_allein_bestaetigt_nicht(ordner):
    _antwort(f"Antworte mit ACK {ID}", rolle="user")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_eintrag_vor_dem_sendezeitpunkt_zaehlt_nicht(ordner):
    _antwort(f"ACK {ID}", zeit=SENDUNG - timedelta(seconds=1))
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_antwort_in_einem_anderen_chat_zaehlt_nicht(ordner):
    _antwort(f"ACK {ID}", thread=ANDERER)
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_leerer_ordner_bestaetigt_nicht(ordner):
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is False


def test_kaputte_zeile_wird_uebersprungen(ordner):
    unter = ordner / "2026" / "10" / "15"
    unter.mkdir(parents=True, exist_ok=True)
    datei = unter / f"rollout-x-{THREAD}.jsonl"
    datei.write_text("kein json mit ACK\n" + json.dumps({
        "timestamp": (SENDUNG + timedelta(minutes=1)).isoformat(), "type": "response_item",
        "payload": {"type": "message", "role": "assistant",
                    "content": [{"text": f"ACK {ID}"}]}}) + "\n", encoding="utf-8")
    assert ack.pruefen(ID, THREAD, SENDUNG, ordner) is True


def test_rollout_dateien_nur_des_zielchats(ordner):
    _antwort(f"ACK {ID}")
    _antwort(f"ACK {ID}", thread=ANDERER)
    assert [p.name for p in ack.rollout_dateien(THREAD, ordner)] == \
        [f"rollout-2026-10-15T12-00-00-{THREAD}.jsonl"]
