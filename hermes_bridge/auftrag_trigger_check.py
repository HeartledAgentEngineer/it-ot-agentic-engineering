#!/usr/bin/env python3
"""Cron-Monitor: Checkt ob der Daemon einen neuen Auftrag entdeckt hat.

Läuft als cron monitor_script (alle 1 Min).
Wenn eine Trigger-Datei existiert → Output → Hash ändert sich → LLM feuert.
KEIN direkter Server-Poll — das macht der Daemon sekündlich.
"""
import os
import time

TRIGGER_FILE = os.path.expanduser("~/.hermes/cron/auftrag_trigger.txt")


def main():
    if os.path.exists(TRIGGER_FILE):
        with open(TRIGGER_FILE) as f:
            content = f.read().strip()
        # Trigger löschen (damit nächstes Mal kein Re-Trigger)
        os.remove(TRIGGER_FILE)
        if content:
            print(f"NEUER_AUFTRAG:{content}")
            return

    # Kein Trigger → kein Output → kein LLM-Call (spart Tokens)


if __name__ == "__main__":
    main()
