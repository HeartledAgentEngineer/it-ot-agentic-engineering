#!/usr/bin/env python3
"""
Hermes Auftrags-Daemon – Läuft permanent im Hintergrund, pollt sekündlich.

KEIN LLM, KEINE TOKEN-KOSTEN.
Nur HTTP-Polls alle 1-2 Sekunden. Bei neuem Auftrag → Trigger-Datei schreiben.

Cron-Monitor checkt die Trigger-Datei und weckt bei Bedarf den Hermes-Agenten.

Start (einmalig):
  python3 hermes_bridge/auftrag_daemon.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"
TRIGGER_FILE = os.path.expanduser("~/.hermes/cron/auftrag_trigger.txt")
STATE_FILE = os.path.expanduser("~/.hermes/cron/auftrag_letzter.txt")
POLL_INTERVAL = 1.5  # Sekunden zwischen Polls


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
    offene = [a for a in auftraege if a.get("status") == "offen"]
    if not offene:
        return None
    offene.sort(key=lambda a: a.get("erstellt", ""))
    return offene[0]


def write_trigger(a):
    """Schreibt Trigger-Datei für den Cron-Monitor."""
    info = f"{a['id'][:8]}|{a.get('kategorie','?')}|{a.get('komplexitaet','?')}|{a.get('auftrag','')[:200]}"
    with open(TRIGGER_FILE, "w") as f:
        f.write(info)
    # Auch die volle ID speichern
    speichere_id(a["id"])
    return info


def main():
    print(f"Hermes Auftrags-Daemon gestartet (Poll alle {POLL_INTERVAL}s)")
    print(f"Server: {SERVER}")
    print(f"Trigger: {TRIGGER_FILE}")
    print("─" * 50)

    letzte = letzte_id()
    ticks = 0

    while True:
        try:
            result = api("/api/auftraege")
            ticks += 1

            if result and isinstance(result, dict) and "auftraege" in result:
                gefunden = aeltester_offener(result["auftraege"])
                if gefunden:
                    aid = gefunden["id"]
                    if aid != letzte:
                        info = write_trigger(gefunden)
                        ts = time.strftime("%H:%M:%S")
                        print(f"[{ts}] 🔔 NEUER AUFTRAG: {info}")
                        letzte = aid
            elif ticks % 60 == 0:
                # Nur alle ~60 Ticks Status anzeigen
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] ⏳ Daemon läuft ({ticks} Polls) — Server: {'OK' if result else 'DOWN'}")

            # Bei Server-Down trotzdem weitermachen (Server startet neu)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nDaemon gestoppt.")
            sys.exit(0)
        except Exception as e:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] ⚠ Fehler: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
