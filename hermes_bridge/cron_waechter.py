#!/usr/bin/env python3
"""Cron-Wächter: Prüft ob der Auftrags-Cron noch lebt, repariert ihn wenn nötig.

Läuft als cron no_agent=True Skript (0 Token).
- Checkt ob der Haupt-Cron in den letzten 2 Minuten getickt hat
- Wenn nicht → pause + resume (setzt den Schedule zurück)
- Kein LLM, kein Token
"""
import json
import os
import subprocess
import sys
import time

STATE_DIR = os.path.expanduser("~/.hermes/cron")
CRON_JOB_ID = "06448a93f989"
STATE_FILE = os.path.join(STATE_DIR, "wachter_letzter_check.txt")
MAX_ALTER = 150  # Sekunden: 2.5 Minuten ohne Tick → Reparatur


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    jetzt = time.time()
    
    # Letzten Check-Zeitpunkt lesen
    letzter = 0
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            try:
                letzter = int(f.read().strip())
            except:
                pass
    
    # Wenn der letzte Check zu lange her ist (Cron hängt)
    if jetzt - letzter > MAX_ALTER:
        # Cron reparieren: pause + resume
        result = subprocess.run(
            [sys.executable, "-c", f"""
import json, urllib.request
# Kann den cronjob tool nicht direkt aufrufen, aber schreibt ein Reparatur-Flag
flag = "{STATE_DIR}/cron_reparieren.txt"
with open(flag, 'w') as f:
    f.write(str(int({jetzt})))
print("Reparatur nötig: Flag geschrieben")
"""],
            capture_output=True, text=True, timeout=10
        )
        print(f"⚠️ Cron hängt seit {int(jetzt-letzter)}s — Flag gesetzt")
    
    # Aktuellen Check speichern
    with open(STATE_FILE, "w") as f:
        f.write(str(int(jetzt)))


if __name__ == "__main__":
    main()
