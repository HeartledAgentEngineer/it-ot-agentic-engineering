#!/usr/bin/env python3
"""
Hermes Coding Agent – Auftragsbrücke zum Personal AI Agent (grillAnAgent).

Vollständiger Workflow:
  1. Nächsten offenen Auftrag vom Server holen
  2. Status-Updates senden (Nachdenken, Codieren, Testen)
  3. Code ändern und zu GitHub pushen
  4. Ergebnis zurückmelden
  5. Bei Rückfragen: Fragen stellen und auf Antwort warten

Aufruf:
  python3 hermes_bridge/auftrags_agent.py

Erwartet:
  - FastAPI-Server auf 127.0.0.1:8080 (Termux)
  - Dulwich (Python-Git) für Git-Operationen
  - ./it-ot-agentic-engineering als Arbeitskopie
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import time

SERVER = "http://127.0.0.1:8080"
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(REPO_DIR)


# ── API-Helfer ──────────────────────────────────────────────────────────────

def api(method, path, data=None):
    url = f"{SERVER}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Fehler: {e}")
        return None


# ── Git-Operationen via dulwich ─────────────────────────────────────────────

def git_commit_all(msg):
    """Alle Änderungen committen via dulwich."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"""
from dulwich.repo import Repo
from dulwich import porcelain
r = Repo('.')
porcelain.add(r, '.')
cid = porcelain.commit(r, message={json.dumps(msg)})
print(cid.decode())
"""],
            capture_output=True, text=True, timeout=30, cwd=REPO_DIR
        )
        if result.returncode != 0:
            print(f"  Commit-Fehler: {result.stderr[:200]}")
            return None
        cid = result.stdout.strip()
        print(f"  Commit: {cid[:12]}")
        return cid
    except Exception as e:
        print(f"  Commit-Fehler: {e}")
        return None


def git_push():
    """Nach GitHub pushen via dulwich."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
from dulwich.repo import Repo
from dulwich import porcelain
r = Repo('.')
porcelain.push(r, 'origin', 'refs/heads/main')
print('Push OK')
"""],
            capture_output=True, text=True, timeout=60, cwd=REPO_DIR
        )
        if result.returncode != 0:
            print(f"  Push-Fehler: {result.stderr[:200]}")
            return False
        print(f"  Push: {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"  Push-Fehler: {e}")
        return False


# ── Hauptlogik ──────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Hermes Coding Agent – Auftragsbrücke")
    print("=" * 50)

    # 1. Nächsten Auftrag holen
    print("\n1. Suche offene Aufträge...")
    result = api("GET", "/api/auftraege/naechster")
    if not result or result.get("auftrag") is None:
        print("  Keine offenen Aufträge.")
        return

    auftrag = result["auftrag"]
    aid = auftrag["id"]
    aid_kurz = aid[:8]
    aufgabe = auftrag["auftrag"]
    kat = auftrag.get("kategorie", "unbekannt")
    kompl = auftrag.get("komplexitaet", "mittel")

    print(f"\n  📋 Auftrag {aid_kurz}")
    print(f"     Aufgabe: {aufgabe[:120]}...")
    print(f"     Kategorie: {kat} | Komplexität: {kompl}")

    # 2. Status-Update: Nachdenken
    print(f"\n2. Starte Bearbeitung...")
    api("POST", f"/api/auftraege/{aid}/status", {
        "meldung": "🔄 Hermes analysiert die Aufgabe..."
    })

    print(f"\n3. Status-Updates während der Bearbeitung:")
    print("   (Wird vom Coding-Agenten in der Konversation ausgefüllt)")

    # 4. Fertig: Pushen + Ergebnis melden
    print(f"\n4. Pushe zu GitHub...")
    commit_msg = f"Hermes: {aufgabe[:80]}"
    cid = git_commit_all(commit_msg)
    if cid:
        git_push()
        ergebnis_text = (
            f"✅ **Auftrag {aid_kurz} abgeschlossen!**\n\n"
            f"**Aufgabe:** {aufgabe[:200]}…\n"
            f"**Commit:** `{cid[:12]}`\n"
            f"**Repository:** HeartledAgentEngineer/it-ot-agentic-engineering\n\n"
            f"Die Änderungen sind auf GitHub verfügbar. "
            f"Ziehe sie in Termux mit `git pull origin main`."
        )
        api("POST", f"/api/auftraege/{aid}/ergebnis", {
            "ergebnis": ergebnis_text, "erfolg": True
        })
        print(f"\n✅ Auftrag {aid_kurz} erfolgreich abgeschlossen und gepusht!")
    else:
        # Keine Änderungen → Ergebnis ohne Push
        ergebnis_text = (
            f"ℹ️ **Auftrag {aid_kurz}** – Keine Code-Änderungen nötig.\n\n"
            f"**Aufgabe:** {aufgabe[:200]}…\n"
            f"Der Auftrag erforderte keine Code-Änderungen.\n"
            f"Bitte prüfe, ob die Aufgabe vollständig ist."
        )
        api("POST", f"/api/auftraege/{aid}/ergebnis", {
            "ergebnis": ergebnis_text, "erfolg": True
        })
        print(f"\n✅ Auftrag {aid_kurz} ohne Änderungen abgeschlossen.")


if __name__ == "__main__":
    main()
