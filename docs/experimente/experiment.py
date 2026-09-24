#!/usr/bin/env python
"""Experiment-Register fuer Agentic-Engineering-Messungen.

Prinzip (nach Marcel/Everlast): Baseline messen -> EINE Sache aendern ->
gegen Baseline vergleichen. Nie zwei Dinge gleichzeitig aendern.

Aufrufe:
    python experiment.py start  "Frage in einem Satz"
    python experiment.py ende   "Ergebnis in einem Satz" [--notiz "..."]
    python experiment.py liste

Was automatisch gemessen wird (aus der Hermes-Session-DB):
    Dauer (Sekunden), Turns, Input-/Output-/Reasoning-/Cache-Tokens, Kosten USD.

Die Werte werden als Differenz zwischen start und ende gebildet, damit nur die
Arbeit am Experiment gezaehlt wird, nicht die ganze Sitzung.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
DB = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local")) / "hermes" / "state.db"
REGISTER = Path(__file__).resolve().parent / "EXPERIMENT-REGISTER.md"
STATE = Path(__file__).resolve().parent / ".experiment-lauf.json"


# ---------------------------------------------------------------- Messung ----
def _snapshot() -> dict:
    """Summiert die Verbrauchswerte ueber alle Sessions (robust gegen Schema-Unterschiede)."""
    if not DB.exists():
        return {"fehler": f"Session-DB nicht gefunden: {DB}"}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
    wants = {
        "turns": ["message_count", "message_count_total", "turns", "turn_count"],
        "tools": ["tool_call_count", "tool_calls"],
        "input": ["input_tokens", "total_input_tokens", "prompt_tokens"],
        "output": ["output_tokens", "total_output_tokens", "completion_tokens"],
        "reasoning": ["reasoning_tokens", "total_reasoning_tokens"],
        "cache": ["cache_read_tokens", "cache_tokens", "cached_tokens", "total_cache_read_tokens"],
        "cost": ["cost_usd", "estimated_cost_usd", "actual_cost_usd", "total_cost_usd"],
    }
    snap: dict = {}
    for key, names in wants.items():
        col = next((n for n in names if n in cols), None)
        if not col:
            snap[key] = 0.0
            continue
        val = con.execute(f"SELECT COALESCE(SUM({col}), 0) FROM sessions").fetchone()[0]
        snap[key] = float(val or 0)
    snap["zeit"] = datetime.now().isoformat(timespec="seconds")
    con.close()
    return snap


def _delta(alt: dict, neu: dict) -> dict:
    return {
        k: round(neu.get(k, 0) - alt.get(k, 0), 4)
        for k in ("turns", "tools", "input", "output", "reasoning", "cache", "cost")
    }


# --------------------------------------------------------------- Register ----
def _kopf() -> str:
    return (
        "# Experiment-Register — Agentic Engineering\n\n"
        "Jede Zeile ist eine echte Messung (keine Behauptung). Prinzip: Baseline festhalten,\n"
        "**eine** Sache aendern, gegen die Baseline vergleichen. Metriken kommen aus der\n"
        "Hermes-Session-DB (`state.db`), nicht aus dem Gefuehl.\n\n"
        "| # | Datum | Frage | Ergebnis | Dauer | Turns | Input | Output | Cache | Kosten | Wiederholungen |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )


def _zeile(nr: int, eintrag: dict) -> str:
    d = eintrag["delta"]
    def f(n): return f"{n:,.0f}".replace(",", ".")
    return (
        f"| {nr} | {eintrag['datum']} | {eintrag['frage']} | {eintrag['ergebnis']} "
        f"| {eintrag['dauer_min']:.1f} min | {f(d['turns'])}/{f(d.get('tools', 0))} "
        f"| {f(d['input'])} | {f(d['output'])} | {f(d['cache'])} "
        f"| ${d['cost']:.2f} | {eintrag.get('notiz') or '—'} |\n"
    )


def _lade_register() -> str:
    return REGISTER.read_text(encoding="utf-8") if REGISTER.exists() else _kopf()


def _naechste_nummer(text: str) -> int:
    return max([int(l.split("|")[1].strip()) for l in text.splitlines()
                if l.startswith("| ") and l.split("|")[1].strip().isdigit()] or [0]) + 1


# ------------------------------------------------------------------ Aktionen ----
def start(frage: str) -> int:
    if STATE.exists():
        alt = json.loads(STATE.read_text(encoding="utf-8"))
        print(f"[!] Es laeuft noch ein Experiment: {alt['frage']!r}")
        print("    Erst 'ende' aufrufen oder die Datei entfernen:")
        print(f"    {STATE}")
        return 1
    snap = _snapshot()
    if "fehler" in snap:
        print("[!]", snap["fehler"])
        return 2
    STATE.write_text(json.dumps({"frage": frage, "start": snap}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"[OK] Baseline festgehalten ({snap['zeit']})")
    print(f"     Frage: {frage}")
    print(f"     Bisher: {snap['turns']:.0f} Turns, ${snap['cost']:.2f} — ab jetzt wird gezaehlt.")
    print("     -> Jetzt EINE Sache aendern und arbeiten. Danach: experiment.py ende '...'")
    return 0


def ende(ergebnis: str, notiz: str | None = None) -> int:
    if not STATE.exists():
        print("[!] Kein laufendes Experiment. Erst 'start' aufrufen.")
        return 1
    alt = json.loads(STATE.read_text(encoding="utf-8"))
    neu = _snapshot()
    if "fehler" in neu:
        print("[!]", neu["fehler"])
        return 2
    d = _delta(alt["start"], neu)
    dauer_min = (datetime.fromisoformat(neu["zeit"]) - datetime.fromisoformat(alt["start"]["zeit"])).total_seconds() / 60

    eintrag = {
        "datum": neu["zeit"][:10],
        "frage": alt["frage"],
        "ergebnis": ergebnis,
        "dauer_min": dauer_min,
        "delta": d,
        "notiz": notiz or "",
    }
    text = _lade_register()
    if "| # |" not in text:
        text = _kopf() + text
    text = text.rstrip() + "\n" + _zeile(_naechste_nummer(text), eintrag)
    REGISTER.write_text(text, encoding="utf-8")
    STATE.unlink()

    print("[OK] Experiment geschlossen und im Register vermerkt.")
    print(f"     Dauer:   {dauer_min:.1f} min")
    print(f"     Turns:   {d['turns']:.0f} Nachrichten, {d.get('tools', 0):.0f} Tool-Calls")
    print(f"     Tokens:  {d['input']:,.0f} rein / {d['output']:,.0f} raus / {d['cache']:,.0f} Cache")
    print(f"     Kosten:  ${d['cost']:.2f}")
    print(f"     Register: {REGISTER}")
    return 0


def liste() -> int:
    text = _lade_register()
    zeilen = [l for l in text.splitlines() if l.startswith("| ") and not l.startswith("| #") and "---" not in l]
    print(f"Register: {REGISTER}")
    print(f"{len(zeilen)} Eintrag/Eintraege")
    for l in zeilen:
        felder = [f.strip() for f in l.split("|") if f.strip()]
        print("  " + " · ".join(felder[:4]) + (f" · {felder[9]}" if len(felder) > 9 else ""))
    if STATE.exists():
        alt = json.loads(STATE.read_text(encoding="utf-8"))
        print(f"\n[LAEUFT] {alt['frage']}  (seit {alt['start']['zeit']})")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "hilfe"):
        print(__doc__)
        raise SystemExit(0)
    cmd, rest = args[0], args[1:]
    if cmd == "start":
        raise SystemExit(start(" ".join(rest) or "(ohne Beschreibung)"))
    if cmd == "ende":
        notiz = None
        if "--notiz" in rest:
            i = rest.index("--notiz")
            notiz = " ".join(rest[i + 1:])
            rest = rest[:i]
        raise SystemExit(ende(" ".join(rest) or "(ohne Ergebnis)", notiz))
    if cmd in ("liste", "list"):
        raise SystemExit(liste())
    print(f"Unbekannt: {cmd}")
    print(__doc__)
    raise SystemExit(2)
