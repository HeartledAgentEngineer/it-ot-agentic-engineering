"""Tests für den OrbitDesk MCP-Server (`mcp_server.py`)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from master_schalter import mcp_server, paare, ziele

THEMA = "orbitdesk"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen(THEMA, "019a2de5-bb88-71d2-8522-91ba62a9f4b2", paare.laufend_bilden(THEMA), aktiv=True)
    return repo


def test_mcp_initialize():
    anfrage = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    antwort = mcp_server.handle_rpc_anfrage(anfrage)
    assert antwort["jsonrpc"] == "2.0"
    assert antwort["id"] == 1
    assert antwort["result"]["serverInfo"]["name"] == "orbitdesk-mcp"


def test_mcp_tools_list():
    anfrage = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    antwort = mcp_server.handle_rpc_anfrage(anfrage)
    tools = antwort["result"]["tools"]
    namen = [t["name"] for t in tools]
    assert "orbitdesk_status" in namen
    assert "orbitdesk_goal_lesen" in namen
    assert "orbitdesk_goal_aktualisieren" in namen
    assert "orbitdesk_chat_wecken" in namen
    assert "orbitdesk_kosten_status" in namen


def test_mcp_goal_lifecycle(umgebung):
    # 1. Goal aktualisieren / neu anlegen
    call_mutation = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "orbitdesk_goal_aktualisieren",
            "arguments": {
                "thema": THEMA,
                "titel": "MCP Leitwarte Test",
                "zieltext": "Automatisierter MCP-Aufruf",
                "neue_entscheidung": "Entscheidung via MCP getroffen",
                "neuer_fortschritt": "MCP-Handler aktiv",
                "naechster_schritt": "Sprachadapter prüfen",
            },
        },
    }
    ant_mut = mcp_server.handle_rpc_anfrage(call_mutation)
    assert "error" not in ant_mut
    inhalt_mut = json.loads(ant_mut["result"]["content"][0]["text"])
    assert inhalt_mut["erfolg"] is True
    assert inhalt_mut["goal"]["titel"] == "MCP Leitwarte Test"

    # 2. Goal lesen
    call_lesen = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "orbitdesk_goal_lesen",
            "arguments": {"thema": THEMA},
        },
    }
    ant_les = mcp_server.handle_rpc_anfrage(call_lesen)
    inhalt_les = json.loads(ant_les["result"]["content"][0]["text"])
    assert inhalt_les["gefunden"] is True
    assert inhalt_les["goal"]["naechster_schritt"] == "Sprachadapter prüfen"
    assert "MCP Leitwarte Test" in inhalt_les["markdown"]

    # 3. Status abfragen
    call_status = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "orbitdesk_status", "arguments": {}},
    }
    ant_stat = mcp_server.handle_rpc_anfrage(call_status)
    inhalt_stat = json.loads(ant_stat["result"]["content"][0]["text"])
    themen = inhalt_stat["themen"]
    assert any(t["thema"] == THEMA and t["goal_titel"] == "MCP Leitwarte Test" for t in themen)
