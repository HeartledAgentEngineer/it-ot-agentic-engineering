#!/usr/bin/env python3
"""
Test-Auftrag für die Hermes-Coding-Pipeline.

Legt einen Test-Auftrag im Server an → Monitor erkennt ihn → LLM verarbeitet ihn.

Verwendung:
  python3 hermes_bridge/test_auftrag.py
  python3 hermes_bridge/test_auftrag.py "Erstelle eine Datei test.txt mit Hallo Welt"
  python3 hermes_bridge/test_auftrag.py --status    # Letzten Auftrag Status checken
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"


def api(method, path, data=None):
    url = f"{SERVER}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Fehler: {e}")
        return None


def create(text=None):
    if text is None:
        text = (
            "TEST: Bitte erstelle eine Datei hermes_test_$(date +%s).txt "
            "im Hauptverzeichnis mit dem Inhalt 'Hermes-Test erfolgreich!'"
        )
    
    print(f"\n📝 Lege Test-Auftrag an...")
    result = api("POST", "/api/auftraege", {
        "auftrag": text,
        "hinweis": "Test von Hermes-Sandbox",
        "kategorie": "feature",
        "komplexitaet": "einfach",
    })
    if result:
        aid = result["id"][:8]
        print(f"  ✅ Auftrag {aid} angelegt (Status: {result['status']})")
        print(f"  📋 {text[:80]}...")
        print(f"\n  ⏳ Monitor erkennt ihn in <2s → LLM startet Bearbeitung")
        print(f"  📊 Status abrufen mit: python3 hermes_bridge/test_auftrag.py --status {aid}")
        return result["id"]
    else:
        print(f"  ❌ Server nicht erreichbar?")
        print(f"  Starte Server in Termux:")
        print(f"    cd ~/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend")
        print(f"    source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload")
        return None


def status(aid_kurz=None):
    """Zeigt Status aller Aufträge oder eines bestimmten."""
    result = api("GET", "/api/auftraege")
    if not result or "auftraege" not in result:
        print("  ❌ Server nicht erreichbar")
        return
    
    auftraege = result["auftraege"]
    if aid_kurz:
        for a in auftraege:
            if a["id"].startswith(aid_kurz):
                _print_auftrag(a)
                return
        print(f"  ❌ Auftrag {aid_kurz} nicht gefunden")
    else:
        # Nur die letzten 5 anzeigen
        print(f"\n📋 Letzte Aufträge:")
        for a in auftraege[-5:]:
            id8 = a["id"][:8]
            s = a["status"]
            t = a["auftrag"][:60]
            print(f"  {id8} [{s}] {t}")


def _print_auftrag(a):
    id8 = a["id"][:8]
    print(f"\n📋 Auftrag {id8}")
    print(f"   Status: {a['status']}")
    print(f"   Aufgabe: {a['auftrag'][:120]}")
    print(f"   Kategorie: {a.get('kategorie','?')}")
    print(f"   Komplexität: {a.get('komplexitaet','?')}")
    if a.get("status_meldungen"):
        print(f"   Meldungen:")
        for m in a["status_meldungen"]:
            print(f"     • {m[:100]}")
    if a.get("ergebnis"):
        print(f"   Ergebnis: {a['ergebnis'][:200]}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--status" or sys.argv[1] == "-s":
            aid = sys.argv[2] if len(sys.argv) > 2 else None
            status(aid)
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print(__doc__)
        else:
            # Text als Auftrag
            create(" ".join(sys.argv[1:]))
    else:
        create()
