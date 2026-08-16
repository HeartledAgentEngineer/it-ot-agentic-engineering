#!/usr/bin/env python3
"""
Hermes Test-Framework: Erstellt Test-Aufträge und prüft den gesamten Workflow.

Verwendung:
  python3 hermes_bridge/test_workflow.py           ← Standard-Test
  python3 hermes_bridge/test_workflow.py --create   ← Nur Auftrag anlegen
  python3 hermes_bridge/test_workflow.py --poll     ← Nur Pollen + Prüfen

Der Test:
  1. Legt einen Test-Auftrag im Server an (via POST /api/auftraege)
  2. Pollt den Server, bis der Cron-Job den Auftrag abgeholt hat
  3. Prüft, ob Status auf "laeuft" wechselt
  4. Wartet auf "fertig" oder "fehler"
  5. Zeigt das Ergebnis an
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"
POLL_INTERVAL = 5  # Sekunden
MAX_WARTE = 300    # Maximal 5 Minuten warten


def api(method, path, data=None):
    url = f"{SERVER}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        return None


def create_test_task(text=None):
    """Legt einen Test-Auftrag im Server an."""
    if text is None:
        text = (
            "TEST: Bitte erstelle eine Datei hermes_test_$(date +%s).txt "
            "mit dem Inhalt 'Hermes-Test erfolgreich' im Hauptverzeichnis. "
            "Das ist ein automatischer Test zur Überprüfung des Workflows."
        )
    print(f"\n📝 Lege Test-Auftrag an...")
    result = api("POST", "/api/auftraege", {
        "auftrag": text,
        "hinweis": "Automatischer Hermes-Test",
        "kategorie": "feature",
        "komplexitaet": "einfach",
    })
    if result:
        aid = result["id"]
        print(f"  ✅ Auftrag angelegt: {aid[:8]} (Status: {result['status']})")
        print(f"  📋 {text[:80]}...")
        return result
    else:
        print(f"  ❌ Konnte Auftrag nicht anlegen!")
        return None


def wait_for_pickup(aid, timeout=120):
    """Wartet, bis der Cron-Job den Auftrag abgeholt hat (Status → laeuft)."""
    print(f"\n⏳ Warte auf Abholung durch Hermes-Cron...")
    start = time.time()
    while time.time() - start < timeout:
        result = api("GET", f"/api/auftraege/{aid}")
        if result:
            status = result.get("status")
            if status == "laeuft":
                print(f"  ✅ Auftrag abgeholt nach {int(time.time()-start)}s (Status: {status})")
                if result.get("status_meldungen"):
                    for m in result["status_meldungen"]:
                        print(f"     {m}")
                return result
            elif status in ("fertig", "fehler"):
                print(f"  ⚡ Auftrag bereits beendet: {status}")
                return result
        time.sleep(POLL_INTERVAL)
    print(f"  ⏰ Abbruch nach {timeout}s – Auftrag wurde nicht abgeholt!")
    return None


def wait_for_completion(aid, timeout=MAX_WARTE):
    """Wartet, bis der Auftrag fertig bearbeitet ist."""
    print(f"\n⏳ Warte auf Fertigstellung...")
    start = time.time()
    while time.time() - start < timeout:
        result = api("GET", f"/api/auftraege/{aid}")
        if result:
            status = result.get("status")
            if status in ("fertig", "fehler"):
                dauer = int(time.time() - start)
                print(f"  {'✅' if status == 'fertig' else '❌'} Status: {status} nach {dauer}s")
                if result.get("status_meldungen"):
                    print(f"\n  📋 Zwischenmeldungen:")
                    for m in result["status_meldungen"]:
                        print(f"     {m}")
                if result.get("ergebnis"):
                    erg = result["ergebnis"][:300]
                    print(f"\n  📄 Ergebnis:\n     {erg}")
                return result
            # Noch in Bearbeitung – Zwischenmeldungen zeigen
            if result.get("status_meldungen"):
                last = result["status_meldungen"][-1]
                print(f"     ⏳ {last[:80]}...")
        time.sleep(POLL_INTERVAL)
    print(f"  ⏰ Abbruch nach {timeout}s – Auftrag nicht fertig!")
    return None


def run_full_test():
    """Führt einen vollständigen Test der Pipeline durch."""
    print("=" * 60)
    print("🧪 Hermes Workflow-Test")
    print("=" * 60)

    # 1. Server-Check
    print(f"\n1. Server-Check...")
    health = api("GET", "/api/health")
    if health and health.get("status") == "ok":
        print(f"  ✅ Server läuft (LLM: {health.get('llm_configured')})")
    else:
        print(f"  ❌ Server nicht erreichbar!")
        return False

    # 2. Test-Auftrag anlegen
    auftrag = create_test_task(
        "TEST: Bitte erstelle eine Datei hermes_test.txt "
        "im Hauptverzeichnis mit dem Inhalt 'Hermes Workflow funktioniert!'"
    )
    if not auftrag:
        return False
    aid = auftrag["id"]

    # 3. Auf Abholung warten
    abgeholt = wait_for_pickup(aid)
    if not abgeholt:
        return False

    # 4. Auf Fertigstellung warten
    ergebnis = wait_for_completion(aid)
    if not ergebnis:
        return False

    # 5. Ergebnis
    status = ergebnis.get("status")
    print(f"\n{'=' * 60}")
    if status == "fertig":
        print(f"✅ TEST BESTANDEN! Gesamtdauer: {MAX_WARTE}s max")
        print(f"   Auftrag {aid[:8]} erfolgreich → fertig")
    else:
        print(f"❌ TEST FEHLGESCHLAGEN! Status: {status}")
        return False

    print(f"{'=' * 60}")
    return True


if __name__ == "__main__":
    if "--create" in sys.argv:
        create_test_task()
    elif "--poll" in sys.argv:
        aid = input("Auftrags-ID: ").strip()
        if aid:
            wait_for_completion(aid)
        else:
            print("Bitte eine Auftrags-ID angeben.")
    else:
        run_full_test()
