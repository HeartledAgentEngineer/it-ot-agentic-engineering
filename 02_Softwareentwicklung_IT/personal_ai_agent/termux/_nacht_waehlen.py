#!/usr/bin/env python3
"""Hilfsskript fuer hermes-nacht-job.sh: waehlt aus der gelieferten
Auftrags-Liste (JSON-Datei) EINEN plausiblen Programmier-Auftrag aus.

Filterkriterien:
- Status in (offen, laeuft, fehler)
- kein Test/Cron/Messung/Beispiel im Text
- Coding-/System-Stichworte

Ausgabe: JSON-Zeile {"id", "auftrag", "status"} oder "NONE"/"API_FAIL".
Dient nur der Nachtjob-Auswahl; wählt nichts, loescht nichts.
"""
import json
import sys


def ist_coding(txt: str) -> bool:
    t = (txt or "").lower()
    AUSSCHLUSS = ("test", "cron", "messung", "messtest", "beispiel")
    if any(w in t for w in AUSSCHLUSS):
        return False
    return any(k in t for k in (
        "api", "endpoint", "ui", "frontend", "backend", "seite", ".py",
        "fehler", "fix", "feat", "programm", "datenbank", "chat", "upload",
        "quiz", "modell", "datei", "gesicht"))


def main():
    if len(sys.argv) < 2:
        sys.exit("API_FAIL")
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        sys.exit("API_FAIL")
    jobs = d.get("auftraege", []) if isinstance(d, dict) else d
    for j in jobs:
        if j.get("status") not in ("offen", "laeuft", "fehler"):
            continue
        txt = j.get("auftrag", "")
        if not ist_coding(txt):
            continue
        print(json.dumps({
            "id": j.get("id"),
            "auftrag": txt[:300],
            "status": j.get("status"),
        }))
        sys.exit(0)
    sys.exit("NONE")


if __name__ == "__main__":
    main()