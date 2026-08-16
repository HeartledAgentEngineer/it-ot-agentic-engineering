#!/usr/bin/env python3
"""Monitor-Script für Hermes-Cron: Pollt den Server auf neue Aufträge.

Läuft als cron monitor_script (alle 1 Min). Pollt 12x intern (5s Abstand).
Nur bei NEUEM Auftrag wird Output erzeugt → LLM-Teil feuert.

ACHTUNG: Ruft NICHT /api/auftraege/naechster auf (der claimt den Job!).
Stattdessen: GET /api/auftraege → Liste aller Jobs → nach ältestem Status:"offen" suchen.

State: ~/.hermes/cron/auftrag_letzter.txt (letzte gesehene offene Auftrags-ID)
"""
import json
import os
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"
STATE_FILE = os.path.expanduser("~/.hermes/cron/auftrag_letzter.txt")


def api(path):
    url = f"{SERVER}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def letzte_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return f.read().strip()
    return ""


def speichere_id(aid):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(aid)


def aeltester_offener_auftrag(auftraege):
    """Findet den ältesten offenen Auftrag aus der Liste.
    Gibt (id, kategorie, komplexitaet, aufgabe) oder None zurück.
    """
    offene = [a for a in auftraege if a.get("status") == "offen"]
    if not offene:
        return None
    # Ältesten (früheste erstellt-Zeit) nehmen
    offene.sort(key=lambda a: a.get("erstellt", ""))
    a = offene[0]
    return (a["id"], a.get("kategorie", "unbekannt"),
            a.get("komplexitaet", "mittel"), a.get("auftrag", "")[:120])


def main():
    letzte = letzte_id()

    for i in range(12):
        result = api("/api/auftraege")
        if result and isinstance(result, dict) and "auftraege" in result:
            gefunden = aeltester_offener_auftrag(result["auftraege"])
            if gefunden:
                aid, kat, kompl, aufgabe = gefunden
                if aid and aid != letzte:
                    print(f"NEUER_AUFTRAG:{aid[:8]}:{kat}:{kompl}:{aufgabe}")
                    speichere_id(aid)
                    return  # Change detektiert → LLM feuert
                # Selbe ID → kein neuer Auftrag, weitermachen
        time.sleep(5)

    # Kein neuer Auftrag → kein Output → kein LLM-Call (spart Tokens)


if __name__ == "__main__":
    main()
