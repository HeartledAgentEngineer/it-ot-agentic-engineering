"""OrbitDesk MCP-Server (Model Context Protocol).

Ermöglicht dem Personal AI Agent (Code-Chat, Sprachsteuerung) und externen Agenten
den direkten Zugriff auf den konsistenten OrbitDesk-Projektzustand:
- `orbitdesk_status`: Gesamtstatus (Kontingente, aktive Master, Limits)
- `orbitdesk_goal_lesen`: Versioniertes Projekt-Goal mit Fortschritt und Aufgaben
- `orbitdesk_goal_aktualisieren`: Mutation von Kriterien, Entscheidungen, Aufgaben und nächstem Schritt
- `orbitdesk_chat_wecken`: Gezieltes Anstoßen / Wecken eines Agenten-Chats
- `orbitdesk_kosten_status`: Budget, Tokens und Kosten je Projekt
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

from . import agy_senden, assistent, kosten_budget, modi, paare, signale, ziele
from .assistent import ChatRef

PROTOKOLL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "orbitdesk_status",
        "description": "Liest den aktuellen Leitwarten-Status aller Projekte (aktive Master, Limits, Wartegründe).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "orbitdesk_goal_lesen",
        "description": "Liest das versionierte Goal und den belegten Fortschritt für ein bestimmtes Thema/Projekt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thema": {"type": "string", "description": "Projekt-/Themenname, z. B. 'orbitdesk'"},
            },
            "required": ["thema"],
        },
    },
    {
        "name": "orbitdesk_goal_aktualisieren",
        "description": "Aktualisiert oder ergänzt Goal, Abnahmekriterien, Entscheidungen, Aufgaben oder nächsten Schritt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thema": {"type": "string", "description": "Projekt-/Themenname"},
                "titel": {"type": "string", "description": "Titel des Goals"},
                "zieltext": {"type": "string", "description": "Zielbeschreibung"},
                "neue_entscheidung": {"type": "string", "description": "Neue getroffene Entscheidung"},
                "neuer_fortschritt": {"type": "string", "description": "Neu belegter Fortschritt"},
                "naechster_schritt": {"type": "string", "description": "Nächster geplanter Arbeitsschritt"},
                "status": {"type": "string", "enum": ["in_arbeit", "abgenommen", "blockiert", "pausiert"]},
                "wartegrung": {"type": "string", "description": "Aktueller Wartegrund (oder leer)"},
            },
            "required": ["thema"],
        },
    },
    {
        "name": "orbitdesk_chat_wecken",
        "description": "Weckt einen Zielchat (Antigravity oder Codex) direkt auf und übermittelt eine Nachricht.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "werkzeug": {"type": "string", "enum": ["agy", "codex"]},
                "kennung": {"type": "string", "description": "Sitzungs- oder Conversation-ID"},
                "nachricht": {"type": "string", "description": "Übermittlungstext"},
                "titel": {"type": "string", "description": "Optionaler Titel"},
            },
            "required": ["werkzeug", "kennung", "nachricht"],
        },
    },
    {
        "name": "orbitdesk_kosten_status",
        "description": "Liest den aktuellen Kosten- und Token-Verbrauch sowie das Budgetlimit für ein Thema.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thema": {"type": "string", "description": "Projekt-/Themenname"},
            },
            "required": ["thema"],
        },
    },
]


def tool_status(_args: dict[str, Any]) -> dict[str, Any]:
    themen_status = []
    for p in paare.lesen():
        ziel = ziele.goal_lesen(p.thema)
        kosten = kosten_budget.budget_status_lesen(p.thema)
        profil = modi.profil(p.thema)
        themen_status.append({
            "thema": p.thema,
            "master": profil.master,
            "worker": profil.worker,
            "modell": profil.modell,
            "goal_titel": ziel.titel if ziel else "",
            "goal_revision": ziel.revision if ziel else 0,
            "status": ziel.status if ziel else "unbekannt",
            "naechster_schritt": ziel.naechster_schritt if ziel else "",
            "wartegrung": ziel.wartegrung if ziel else None,
            "kosten_usd": kosten.verbraucht_usd,
            "budget_limit_usd": kosten.budget_limit_usd,
            "warnung": kosten.warnung_aktiv,
        })
    return {"themen": themen_status}


def tool_goal_lesen(args: dict[str, Any]) -> dict[str, Any]:
    thema = str(args.get("thema") or "").strip()
    ziel = ziele.goal_lesen(thema)
    if ziel is None:
        return {"gefunden": False, "thema": thema, "hinweis": "Kein Goal vorhanden"}
    return {"gefunden": True, "goal": ziel.als_dict(), "markdown": ziele.goal_zu_markdown(ziel)}


def tool_goal_aktualisieren(args: dict[str, Any]) -> dict[str, Any]:
    thema = str(args.get("thema") or "").strip()
    alt = ziele.goal_lesen(thema)
    
    entscheidungen = list(alt.entscheidungen) if alt else []
    if args.get("neue_entscheidung"):
        entscheidungen.append(str(args["neue_entscheidung"]).strip())
        
    fortschritt = list(alt.belegter_fortschritt) if alt else []
    if args.get("neuer_fortschritt"):
        fortschritt.append(str(args["neuer_fortschritt"]).strip())

    neu = ziele.goal_anlegen_oder_aktualisieren(
        thema,
        titel=str(args.get("titel") or (alt.titel if alt else f"Goal {thema}")),
        zieltext=str(args.get("zieltext") or (alt.zieltext if alt else "")),
        entscheidungen=entscheidungen,
        belegter_fortschritt=fortschritt,
        naechster_schritt=str(args.get("naechster_schritt") or (alt.naechster_schritt if alt else "")),
        status=str(args.get("status") or (alt.status if alt else ziele.STATUS_IN_ARBEIT)),
        wartegrung=args.get("wartegrung") if "wartegrung" in args else (alt.wartegrung if alt else None),
    )
    return {"erfolg": True, "goal": neu.als_dict()}


def tool_chat_wecken(args: dict[str, Any]) -> dict[str, Any]:
    werkzeug = str(args.get("werkzeug") or "").strip()
    kennung = str(args.get("kennung") or "").strip()
    nachricht = str(args.get("nachricht") or "").strip()
    titel = str(args.get("titel") or "OrbitDesk Weckruf").strip()

    if werkzeug == "agy":
        code = agy_senden.nachricht_senden(kennung, nachricht, titel=titel)
        return {"werkzeug": "agy", "ergebnis": code, "erfolg": code == "ok"}
    elif werkzeug == "codex":
        from . import codex_senden
        rc = assistent._codex_senden(kennung, nachricht, transport=None)
        return {"werkzeug": "codex", "ergebnis": rc, "erfolg": rc == "ok"}
    return {"werkzeug": werkzeug, "ergebnis": "unbekanntes_werkzeug", "erfolg": False}


def tool_kosten_status(args: dict[str, Any]) -> dict[str, Any]:
    thema = str(args.get("thema") or "").strip()
    status = kosten_budget.budget_status_lesen(thema)
    return {"thema": thema, "status": status.als_dict()}


TOOL_ROUTER: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "orbitdesk_status": tool_status,
    "orbitdesk_goal_lesen": tool_goal_lesen,
    "orbitdesk_goal_aktualisieren": tool_goal_aktualisieren,
    "orbitdesk_chat_wecken": tool_chat_wecken,
    "orbitdesk_kosten_status": tool_kosten_status,
}


def handle_rpc_anfrage(anfrage: dict[str, Any]) -> dict[str, Any]:
    """Verarbeitet eine standardkonforme JSON-RPC Anfrage für MCP."""
    method = anfrage.get("method")
    req_id = anfrage.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOKOLL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "orbitdesk-mcp", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = anfrage.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if tool_name not in TOOL_ROUTER:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' nicht gefunden"},
            }

        try:
            handler = TOOL_ROUTER[tool_name]
            ergebnis = handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(ergebnis, ensure_ascii=False, indent=2)}]
                },
            }
        except Exception as fehler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(fehler)},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Methode '{method}' unbekannt"},
    }
