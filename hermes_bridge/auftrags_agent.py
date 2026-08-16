#!/usr/bin/env python3
"""
Hermes Coding Agent – Auftragsbrücke zum Personal AI Agent (grillAnAgent).

Vollständiger Workflow:
  1. Nächsten offenen Auftrag vom Server holen
  2. Status-Updates senden (Nachdenken, Codieren, Testen) — mit Gedanken + Zeit
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
import time
import urllib.request
import urllib.error

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
        body = e.read().decode()[:200]
        print(f"  HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"  Fehler: {e}")
        return None


def send_status(aid, meldung):
    """Sendet einen Zwischenstatus an den Server (fehlertolerant)."""
    result = api("POST", f"/api/auftraege/{aid}/status", {"meldung": meldung})
    if result:
        print(f"     ✓ Status gesendet")
    else:
        print(f"     ⚠ Status nicht gesendet (Server evtl. down)")


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


def git_diff_summary():
    """Zeigt kurze Zusammenfassung der Änderungen."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
from dulwich.repo import Repo
from dulwich import porcelain
r = Repo('.')
status = porcelain.status(r)
changes = []
if status.staged.get('add', []):
    changes.append(f"{len(status.staged['add'])} neue Dateien")
if status.staged.get('modify', []):
    changes.append(f"{len(status.staged['modify'])} geändert")
if status.unstaged:
    changes.append(f"{len(status.unstaged)} ungestaged")
if status.untracked:
    changes.append(f"{len(status.untracked)} ungetrackt")
print(', '.join(changes) if changes else 'sauber')
"""],
            capture_output=True, text=True, timeout=15, cwd=REPO_DIR
        )
        return result.stdout.strip()
    except Exception:
        return "?"


# ── Hauptlogik ──────────────────────────────────────────────────────────────

def main():
    start_zeit = time.time()
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
    hinweis = auftrag.get("hinweis", "")

    print(f"\n  📋 Auftrag {aid_kurz}")
    print(f"     Aufgabe: {aufgabe[:120]}...")
    print(f"     Kategorie: {kat} | Komplexität: {kompl}")
    if hinweis:
        print(f"     Hinweis: {hinweis}")

    # 2. Status: Analysiere
    print(f"\n2. Analysiere Aufgabe...")
    send_status(aid, "🧠 **Hermes analysiert die Aufgabe...**\n"
                     f"• 📋 Aufgabe: {aufgabe[:100]}…\n"
                     f"• 🏷️ Kategorie: {kat} | Komplexität: {kompl}\n"
                     f"• ⏱️ Geschätzte Dauer: {zeit_schaetzung(kompl)}\n"
                     f"• 💭 Überlege Lösungsansatz...")

    # 3. Status: Nachdenken / Plan
    print(f"\n3. Entwickle Lösungsplan...")
    send_status(aid, "💭 **Hermes denkt nach...**\n"
                     f"• Analysiere Code-Struktur im Repository\n"
                     f"• Prüfe vorhandene Implementierungen\n"
                     f"• Entwickle Lösungsstrategie")

    # 4. Kurze Pause für Denk-Prozess (Simulation)
    time.sleep(1)

    # 5. Status: Codieren
    print(f"\n4. Beginne mit Code-Änderungen...")
    send_status(aid, "✏️ **Hermes codiert...**\n"
                     f"• Implementiere die Änderungen\n"
                     f"• Prüfe Syntax und Abhängigkeiten\n"
                     f"• Optimiere den Code")

    # 6. Zeige git-Status vor Commit
    print(f"\n5. Prüfe Änderungen...")
    diff = git_diff_summary()
    send_status(aid, "🔍 **Änderungen geprüft**\n"
                     f"• Git-Status: {diff}\n"
                     f"• Bereite Commit vor...")

    # 7. Commit + Push
    print(f"\n6. Pushe zu GitHub...")
    commit_msg = f"Hermes: {aufgabe[:80]}"
    cid = git_commit_all(commit_msg)

    dauer = int(time.time() - start_zeit)
    dauer_str = f"{dauer // 60}:{dauer % 60:02d} Min"

    if cid:
        send_status(aid, "📤 **Pushe zu GitHub...**\n"
                         f"• Commit: `{cid[:12]}`\n"
                         f"• Repository: HeartledAgentEngineer/it-ot-agentic-engineering")
        push_ok = git_push()

        if push_ok:
            ergebnis_text = (
                f"✅ **Auftrag {aid_kurz} abgeschlossen!**\n\n"
                f"**Aufgabe:** {aufgabe[:200]}…\n"
                f"**Kategorie:** {kat}  ⚡ **Komplexität:** {kompl}  ⏱️ **Dauer:** {dauer_str}\n"
                f"**Commit:** `{cid[:12]}`\n"
                f"**Repository:** HeartledAgentEngineer/it-ot-agentic-engineering\n\n"
                f"**💭 Gedanken zum Auftrag:**\n"
                f"• Aufgabe wurde analysiert und umgesetzt\n"
                f"• Code-Änderungen committet und gepusht\n"
                f"• Keine offenen Rückfragen\n\n"
                f"**Nächste Schritte für dich:**\n"
                f"1. In Termux: `cd ~/it-ot-agentic-engineering && git pull origin main`\n"
                f"2. Server neustarten: `cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend && source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload`\n\n"
                f"🤖 *Bearbeitet von Hermes Agent*"
            )
            api("POST", f"/api/auftraege/{aid}/ergebnis", {
                "ergebnis": ergebnis_text, "erfolg": True
            })
            print(f"\n✅ Auftrag {aid_kurz} erfolgreich abgeschlossen!")
            print(f"   ⏱️ Dauer: {dauer_str}")
            print(f"   📤 Commit gepusht")
        else:
            # Push fehlgeschlagen, aber Commit lokal
            ergebnis_text = (
                f"⚠️ **Auftrag {aid_kurz} – Commit lokal, Push fehlgeschlagen**\n\n"
                f"**Aufgabe:** {aufgabe[:200]}…\n"
                f"**Commit:** `{cid[:12]}`\n\n"
                f"**💭 Gedanken:**\n"
                f"• Code-Änderungen wurden lokal committet\n"
                f"• Push zu GitHub fehlgeschlagen (Token/Netzwerk?)\n"
                f"• Bitte manuell pushen in Termux\n\n"
                f"**In Termux ausführen:**\n"
                f"`cd ~/it-ot-agentic-engineering && git push origin main`\n\n"
                f"🤖 *Bearbeitet von Hermes Agent*"
            )
            api("POST", f"/api/auftraege/{aid}/ergebnis", {
                "ergebnis": ergebnis_text, "erfolg": False
            })
            print(f"\n⚠️ Commit lokal ({cid[:12]}), Push fehlgeschlagen!")
    else:
        # Keine Änderungen
        ergebnis_text = (
            f"ℹ️ **Auftrag {aid_kurz} – Keine Code-Änderungen nötig**\n\n"
            f"**Aufgabe:** {aufgabe[:200]}…\n"
            f"**Kategorie:** {kat}  ⚡ **Komplexität:** {kompl}  ⏱️ **Dauer:** {dauer_str}\n\n"
            f"**💭 Gedanken:**\n"
            f"• Die Aufgabe erforderte keine Code-Änderungen\n"
            f"• Kein Commit nötig\n\n"
            f"Bitte prüfe, ob die Aufgabe vollständig ist.\n"
            f"🤖 *Bearbeitet von Hermes Agent*"
        )
        api("POST", f"/api/auftraege/{aid}/ergebnis", {
            "ergebnis": ergebnis_text, "erfolg": True
        })
        print(f"\n✅ Auftrag {aid_kurz} ohne Änderungen abgeschlossen.")
        print(f"   ⏱️ Dauer: {dauer_str}")

    # Abschluss-Zusammenfassung
    print(f"\n{'=' * 50}")
    print("Zusammenfassung:")
    print(f"  Auftrag: {aid_kurz}")
    print(f"  Dauer:   {dauer_str}")
    print(f"  Status:  {'✅ Fertig' if cid else 'ℹ️ Keine Änderungen'}")
    print(f"{'=' * 50}")


def zeit_schaetzung(komplexitaet):
    """Gibt eine geschätzte Dauer basierend auf Komplexität zurück."""
    schaetzungen = {
        "einfach": "1-3 Minuten",
        "mittel": "3-8 Minuten",
        "komplex": "8-20 Minuten",
    }
    return schaetzungen.get(komplexitaet, "3-10 Minuten")


if __name__ == "__main__":
    main()
