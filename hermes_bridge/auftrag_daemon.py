#!/usr/bin/env python3
"""
Hintergrund-Daemon: Pollt alle 5s den Server und verarbeitet neue Aufträge.
KEIN Cron, KEIN LLM — nur HTTP + Git. Läuft permanent im Hintergrund.

Start:
  python3 hermes_bridge/auftrag_daemon.py

Macht bei jedem neuen Auftrag:
  1. Claimt ihn (POST /naechster)
  2. Sendet Status-Updates
  3. Erstellt ggf. eine Datei
  4. Commit + Push
  5. Ergebnis melden
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"
STATE_FILE = os.path.expanduser("~/.hermes/cron/auftrag_letzter.txt")
REPO_DIR = "/data/data/com.hermesagent.android/files/home/it-ot-agentic-engineering"
os.chdir(REPO_DIR)


def api(method, path, data=None):
    url = f"{SERVER}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"fehler": f"HTTP {e.code}"}
    except Exception as e:
        return None


def send_status(aid, meldung):
    api("POST", f"/api/auftraege/{aid}/status", {"meldung": meldung})


def letzte_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return f.read().strip()
    return ""


def speichere_id(aid):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(aid)


def verarbeite_auftrag(aid, aufgabe):
    """Verarbeitet einen Auftrag: Claim → Arbeit → Git → Ergebnis"""
    print(f"\n🔄 Verarbeite {aid[:8]}: {aufgabe[:60]}...")

    # 1. Claimen
    result = api("GET", "/api/auftraege/naechster")
    if not result or result.get("auftrag") is None:
        print("  ⚠ Kein Claim möglich (vielleicht schon bearbeitet)")
        return

    # 2. Status: Analysiere
    send_status(aid, "⏳ **Hermes Daemon** hat den Auftrag übernommen...")

    # 3. Datei erstellen (bei TEST-Aufträgen)
    if "TEST:" in aufgabe or "test" in aufgabe.lower()[:20]:
        # Dateiname aus Aufgabe extrahieren
        import re
        match = re.search(r'(\S+\.\w+)', aufgabe)
        if match:
            dateiname = match.group(1)
            send_status(aid, f"📝 **Erstelle Datei** `{dateiname}`...")
            inhalt_match = re.search(r"mit dem Inhalt ['\"](.+?)['\"]", aufgabe)
            inhalt = inhalt_match.group(1) if inhalt_match else f"Automatisch erstellt von Hermes Daemon am {time.strftime('%Y-%m-%d %H:%M')}"

            try:
                with open(dateiname, "w") as f:
                    f.write(inhalt)
                send_status(aid, f"✅ **Datei erstellt**: `{dateiname}`")
            except Exception as e:
                send_status(aid, f"⚠️ **Datei-Fehler:** {e}")

    # 4. Git: Commit + Push
    send_status(aid, "📤 **Pushe zu GitHub...**")
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"""
from dulwich.repo import Repo
from dulwich import porcelain
r = Repo('.')
porcelain.add(r, '.')
cid = porcelain.commit(r, message='Hermes (Daemon): {aufgabe[:70]}')
print(cid.decode()[:12])
porcelain.push(r, 'origin', 'refs/heads/main')
print('Push OK')
"""],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            commit_id = result.stdout.strip().split('\n')[0]
            send_status(aid, f"✅ **Commit:** `{commit_id}` – Push zu GitHub OK")
            ergebnis = (
                f"✅ **Auftrag {aid[:8]} abgeschlossen (Daemon)**\n\n"
                f"**Aufgabe:** {aufgabe[:200]}…\n"
                f"**Commit:** `{commit_id}`\n"
                f"**Repository:** HeartledAgentEngineer/it-ot-agentic-engineering\n\n"
                f"**Nächste Schritte in Termux:**\n"
                f"`cd ~/it-ot-agentic-engineering && git pull origin main`"
            )
            api("POST", f"/api/auftraege/{aid}/ergebnis", {
                "ergebnis": ergebnis, "erfolg": True
            })
            print(f"  ✅ Fertig: {commit_id}")
        else:
            send_status(aid, f"⚠️ **Git-Fehler:** {result.stderr[:100]}")
            api("POST", f"/api/auftraege/{aid}/ergebnis", {
                "ergebnis": f"Fehler: {result.stderr[:200]}", "erfolg": False
            })
    except Exception as e:
        print(f"  ❌ Fehler: {e}")


def main():
    print("🤖 Hermes Auftrags-Daemon gestartet")
    print(f"   Server: {SERVER}")
    print(f"   Poll:   alle 5s")
    print(f"   State:  {STATE_FILE}")
    print("─" * 40)

    letzte = letzte_id()
    ticks = 0

    while True:
        try:
            result = api("GET", "/api/auftraege")
            ticks += 1

            if result and "auftraege" in result:
                # Neuesten offenen Job finden
                offene = [a for a in result["auftraege"] if a.get("status") == "offen"]
                if offene:
                    # Ältesten offenen Job nehmen
                    offene.sort(key=lambda a: a.get("erstellt", ""))
                    job = offene[0]
                    aid = job["id"]
                    aufgabe = job.get("auftrag", "")

                    if aid != letzte:
                        verarbeite_auftrag(aid, aufgabe)
                        letzte = aid
                        speichere_id(aid)

            # Status alle 60 Ticks (5 Min)
            if ticks % 60 == 0:
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] Daemon läuft ({ticks} Polls)")

            time.sleep(5)

        except KeyboardInterrupt:
            print("\nDaemon gestoppt.")
            sys.exit(0)
        except Exception as e:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] ⚠ Fehler: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
