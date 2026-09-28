"""Wache: schiebt neue Agentenbus-Nachrichten in die laufende Hermes-Sitzung.

Laeuft als geplanter Auftrag jede Minute. Kostet NICHTS, solange nichts auf dem
Bus liegt: ohne neue Nachricht beendet sich das Skript sofort, ohne Modellaufruf.

Ablauf:
  1. ungelesene Nachrichten fuer 'hermes' vom Bus holen
  2. keine da -> still beenden (Exit 0)
  3. welche da -> per Hermes-API in die Sitzung schreiben
                 (POST /api/sessions/<id>/chat, Bearer API_SERVER_KEY)
  4. erst nach erfolgreicher Zustellung als gelesen markieren

Der Schluessel wird nur aus der Hermes-.env gelesen und nie ausgegeben.
Sitzungs-ID: Umgebungsvariable HERMES_SITZUNG oder .hermes/bus/wache.json
({"sitzung": "..."}).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
BASIS = os.environ.get("HERMES_API_URL", "http://127.0.0.1:8642").rstrip("/")
ENV_DATEIEN = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env",
    Path.home() / ".hermes" / ".env",
]
BUS = HIER / "agentbus.py"
SITZUNG_STANDARD = "20260820_144732_e799d8"
MAX_ZEICHEN = 1200


def busmodul():
    spec = importlib.util.spec_from_file_location("agentbus", BUS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def schluessel() -> str:
    if os.environ.get("API_SERVER_KEY"):
        return os.environ["API_SERVER_KEY"]
    for datei in ENV_DATEIEN:
        if datei.is_file():
            for zeile in datei.read_text(encoding="utf-8", errors="ignore").splitlines():
                if zeile.startswith("API_SERVER_KEY="):
                    return zeile.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("FEHLER: API_SERVER_KEY nicht gefunden.")


def sitzung(bus_verzeichnis: Path) -> str:
    if os.environ.get("HERMES_SITZUNG"):
        return os.environ["HERMES_SITZUNG"]
    stand = bus_verzeichnis / "wache.json"
    if stand.is_file():
        try:
            return json.loads(stand.read_text(encoding="utf-8")).get("sitzung") or SITZUNG_STANDARD
        except json.JSONDecodeError:
            pass
    return SITZUNG_STANDARD


def zustellen(sitzung_id: str, text: str) -> bool:
    req = urllib.request.Request(
        f"{BASIS}/api/sessions/{sitzung_id}/chat",
        data=json.dumps({"message": text}).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {schluessel()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as antwort:
            return antwort.status == 200
    except urllib.error.HTTPError as fehler:
        print(f"Zustellung fehlgeschlagen: HTTP {fehler.code} {fehler.read().decode('utf-8', 'ignore')[:200]}")
        return False
    except Exception as fehler:  # Server aus, Netz weg -> naechster Lauf versucht es erneut
        print(f"Zustellung nicht moeglich: {fehler}")
        return False


def nachrichtentext(neu: list[dict]) -> str:
    zeilen = ["[Agentenbus] Neue Nachricht(en) fuer dich von Claude Code:"]
    for m in neu:
        kopf = f"- {m['von']} [{m['typ']}]" + (f" Step {m['step']}" if m.get("step") else "")
        zeilen.append(kopf)
        zeilen.append("  " + (m.get("text") or "").strip()[:MAX_ZEICHEN])
        if m.get("pfade"):
            zeilen.append("  Pfade: " + ", ".join(m["pfade"]))
    zeilen.append("Antworte ueber den Bus: python tools/agentbus/agentbus.py send --from hermes --to claude --text \"...\"")
    return "\n".join(zeilen)


def wache(erzwingen: bool = False) -> int:
    mod = busmodul()
    d = mod.bus_dir()
    neu = mod.read(d, "hermes")
    if not neu:
        if erzwingen:
            print("keine neuen Nachrichten")
        return 0
    print(f"{len(neu)} neue Nachricht(en) -> zustellen")
    if zustellen(sitzung(d), nachrichtentext(neu)):
        print("zugestellt")
        return 0
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(wache(erzwingen="--laut" in sys.argv))