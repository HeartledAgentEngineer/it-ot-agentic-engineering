"""Test: Hermes-Spiegel-Runde wird append-only in den Verlauf geschrieben.

Nutzt eine TMP-Verlaufsdatei (Pytest-Fixture-Stil) — fasst die echte
chroma_data/conversations.json NIE an (Schutz-Regel).
"""
import json
from pathlib import Path

from app.services import chat_verlauf


def test_hermes_runde_wird_persistiert(tmp_path):
    vp = tmp_path / "conversations.json"
    chat_verlauf.init(str(vp), str(tmp_path))
    cid = chat_verlauf._AKTIVE_CONVERSATION_ID
    chat_verlauf.conversations.setdefault(cid, [])

    # Direkt die Helferfunktion aus hermes_steuerung pruefen (Import hier).
    from app.router.hermes_steuerung import _persistiere_hermes_runde
    _persistiere_hermes_runde("Frage eins?", "Antwort eins.", cid=cid)
    _persistiere_hermes_runde("Frage zwei?", "Antwort zwei.", cid=cid)

    msgs = chat_verlauf.conversations[cid]
    assert len(msgs) == 4
    # Reihenfolge: Frage -> Antwort -> Frage -> Antwort
    assert msgs[0]["role"] == "user" and msgs[0]["content"] == "Frage eins?"
    assert msgs[1]["role"] == "assistant" and msgs[1]["content"] == "Antwort eins."
    assert msgs[2]["role"] == "user" and msgs[2]["content"] == "Frage zwei?"
    assert msgs[3]["role"] == "assistant" and msgs[3]["content"] == "Antwort zwei."

    # Auf Platte nachgeschrieben.
    auf_platte = json.loads(Path(vp).read_text(encoding="utf-8"))
    assert len(auf_platte["conversations"][cid]) == 4
