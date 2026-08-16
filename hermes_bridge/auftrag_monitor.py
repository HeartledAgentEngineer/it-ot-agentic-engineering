#!/usr/bin/env python3
"""Cron-Monitor: Pollt 60s lang alle 2s den Server nach neuen Aufträgen.

Läuft als cron monitor_script (alle 1 Min).
- Bei NEUEM Auftrag → Output → Hash ändert sich → LLM feuert sofort
- Kein NEUER Auftrag → kein Output → kein LLM-Call (0 Token)
- Nur cheap HTTP-Polls localhost (null Tokens)
"""
import json
import os
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"
STATE_FILE = os.path.expanduser("~/.hermes/cron/auftrag_letzter.txt")
POLLS = 30  # 30 × 2s = 60s = volle Cron-Laufzeit


def api(path):
    url = f"{SERVER}{path}"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
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


def aeltester_offener(auftraege):
    """Findet ältesten offenen Auftrag (read-only, kein Claim!)."""
    offene = [a for a in auftraege if a.get("status") == "offen"]
    if not offene:
        return None
    offene.sort(key=lambda a: a.get("erstellt", ""))
    return offene[0]


def main():
    letzte = letzte_id()

    for i in range(POLLS):
        result = api("/api/auftraege")
        if result and isinstance(result, dict) and "auftraege" in result:
            gefunden = aeltester_offener(result["auftraege"])
            if gefunden:
                aid = gefunden["id"]
                if aid != letzte:
                    # Neuer Auftrag! Trigger setzen und sofort beenden
                    info = (
                        f"{aid[:8]}|{gefunden.get('kategorie','?')}|"
                        f"{gefunden.get('komplexitaet','?')}|"
                        f"{gefunden.get('auftrag','')[:200]}"
                    )
                    print(f"NEUER_AUFTRAG:{info}")
                    speichere_id(aid)
                    return  # → LLM feuert!
                # Selbe ID → kein neuer Auftrag, weiter polln

        time.sleep(2)

    # Kein neuer Auftrag nach 60s → kein Output → kein LLM (0 Token)


if __name__ == "__main__":
    main()
