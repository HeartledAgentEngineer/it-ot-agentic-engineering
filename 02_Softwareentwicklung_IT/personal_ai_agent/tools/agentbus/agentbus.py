"""agentbus - file-based mailbox + task broker for cooperating agents.

Two agents (Hermes on the PC, Claude Code / Codex in the same repo) talk through
plain files: no server, no port, survives restarts, works in Termux too.

Design rules:
- One writer per file: message log is append-only JSONL, claims are created with
  O_CREAT|O_EXCL (atomic, so two agents can never claim the same step).
- Only coordination data lives here (task ids, paths, short notes). Never
  personal data, never secrets - the bus directory is local and not committed.

CLI
    agentbus init
    agentbus send --from hermes --to claude --type task --step N27
                    --paths a,b --text "implement step 1 only"
    agentbus read --for claude [--all]
    agentbus claim --agent claude --step N27 --paths a,b
    agentbus release --agent claude --step N27
    agentbus verify --agent hermes --step N27 --result gruen --text "gate 2270"
    agentbus status
    agentbus wait --for claude [--timeout 3600] [--intervall 1]
                    blocks until mail arrives: exit 0 + prints it, exit 3 on timeout
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

TYPES = ("task", "tip", "frage", "erledigt", "blockiert", "pruefung", "info")
AGENTS = ("hermes", "claude", "codex", "mensch")


def bus_dir() -> Path:
    env = os.environ.get("AGENTBUS_DIR")
    if env:
        return Path(env)
    # default: <git root of this script>/.hermes/bus - independent of the CWD,
    # otherwise agents started from different folders get separate mailboxes
    for ordner in Path(__file__).resolve().parents:
        if (ordner / ".git").exists():
            return ordner / ".hermes" / "bus"
    return Path.cwd() / ".hermes" / "bus"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def init(d: Path) -> list[str]:
    made = []
    d.mkdir(parents=True, exist_ok=True)
    for name in ("messages.jsonl", "claims"):
        p = d / name
        if not p.exists():
            if name == "claims":
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.touch()
            made.append(name)
    return made


def send(d: Path, von: str, an: str, typ: str, text: str,
         step: str = "", paths: str = "") -> dict:
    if typ not in TYPES:
        raise SystemExit(f"unbekannter Typ: {typ} (erlaubt: {', '.join(TYPES)})")
    msg = {
        "id": f"m{int(time.time() * 1000)}",
        "zeit": _now(),
        "von": von,
        "an": an,
        "typ": typ,
        "step": step,
        "pfade": [p.strip() for p in paths.split(",") if p.strip()],
        "text": text,
        "gelesen": [],
    }
    d.joinpath("messages.jsonl").parent.mkdir(parents=True, exist_ok=True)
    with open(d / "messages.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def _gelesen_datei(d: Path, fuer: str) -> Path:
    return d / f"gelesen-{fuer}.txt"


def _ungelesen(d: Path, fuer: str, alles: bool = False) -> list[dict]:
    p = d / "messages.jsonl"
    if not p.exists():
        return []
    gd = _gelesen_datei(d, fuer)
    gelesen = set(gd.read_text(encoding="utf-8").split()) if gd.exists() else set()
    offen = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("an") not in (fuer, "alle") or m.get("von") == fuer:
                continue
            # legacy: older buses stored read markers inside the message
            schon = m.get("id") in gelesen or fuer in m.get("gelesen", [])
            if schon and not alles:
                continue
            offen.append(m)
    return offen


def read(d: Path, fuer: str, alles: bool = False) -> list[dict]:
    # Read markers live in gelesen-<agent>.txt (one writer: that agent), so
    # messages.jsonl stays append-only and a concurrent send is never lost.
    offen = _ungelesen(d, fuer, alles)
    if offen and not alles:
        with open(_gelesen_datei(d, fuer), "a", encoding="utf-8") as fh:
            fh.write("".join(f"{m['id']}\n" for m in offen))
    return offen


def wait(d: Path, fuer: str, timeout: float = 3600, intervall: float = 1.0) -> list[dict]:
    """Block until unread mail for `fuer` exists (then read it) or timeout -> []."""
    ende = time.monotonic() + timeout
    while True:
        if _ungelesen(d, fuer):
            return read(d, fuer)
        if time.monotonic() >= ende:
            return []
        time.sleep(intervall)


def claim(d: Path, agent: str, step: str, paths: str = "", text: str = "") -> dict:
    d.joinpath("claims").mkdir(parents=True, exist_ok=True)
    datei = d / "claims" / f"step-{step}.json"
    try:
        fd = os.open(datei, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        vorhanden = json.loads(datei.read_text(encoding="utf-8"))
        raise SystemExit(
            f"Step {step} ist schon beansprucht von {vorhanden.get('agent')} "
            f"seit {vorhanden.get('zeit')} - nicht anfassen."
        )
    daten = {
        "step": step,
        "agent": agent,
        "zeit": _now(),
        "pfade": [p.strip() for p in paths.split(",") if p.strip()],
        "notiz": text,
    }
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, indent=2)
    return daten


def release(d: Path, agent: str, step: str) -> str:
    datei = d / "claims" / f"step-{step}.json"
    if not datei.exists():
        return "kein Anspruch vorhanden"
    daten = json.loads(datei.read_text(encoding="utf-8"))
    if daten.get("agent") != agent:
        raise SystemExit(f"Step {step} gehoert {daten.get('agent')}, nicht {agent}.")
    datei.unlink()
    return f"Anspruch auf {step} freigegeben"


def verify(d: Path, agent: str, step: str, ergebnis: str, text: str = "") -> dict:
    if ergebnis not in ("gruen", "rot"):
        raise SystemExit("--result muss gruen oder rot sein")
    datei = d / "claims" / f"step-{step}.json"
    if datei.exists():
        daten = json.loads(datei.read_text(encoding="utf-8"))
        if daten.get("agent") == agent:
            raise SystemExit("Ein Pruefer darf nicht der Arbeiter sein - anderer Agent noetig.")
    msg = send(d, agent, "alle", "pruefung", f"[{ergebnis}] {text or step}", step=step)
    msg["ergebnis"] = ergebnis
    return msg


def status(d: Path) -> dict:
    claims = []
    cd = d / "claims"
    if cd.exists():
        for f in sorted(cd.glob("step-*.json")):
            try:
                claims.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    letzte = []
    p = d / "messages.jsonl"
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            letzte = [json.loads(x) for x in fh if x.strip()][-8:]
    return {"claims": claims, "letzte_nachrichten": letzte, "ungelesen": len(letzte)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentbus", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    s = sub.add_parser("send")
    s.add_argument("--from", dest="von", required=True)
    s.add_argument("--to", dest="an", required=True)
    s.add_argument("--type", dest="typ", required=True, choices=TYPES)
    s.add_argument("--step", default="")
    s.add_argument("--paths", default="")
    s.add_argument("--text", default="")

    r = sub.add_parser("read")
    r.add_argument("--for", dest="fuer", required=True)
    r.add_argument("--all", dest="alles", action="store_true")

    c = sub.add_parser("claim")
    c.add_argument("--agent", required=True)
    c.add_argument("--step", required=True)
    c.add_argument("--paths", default="")
    c.add_argument("--text", default="")

    f = sub.add_parser("release")
    f.add_argument("--agent", required=True)
    f.add_argument("--step", required=True)

    v = sub.add_parser("verify")
    v.add_argument("--agent", required=True)
    v.add_argument("--step", required=True)
    v.add_argument("--result", dest="ergebnis", required=True)
    v.add_argument("--text", default="")

    sub.add_parser("status")

    w = sub.add_parser("wait")
    w.add_argument("--for", dest="fuer", required=True)
    w.add_argument("--timeout", type=float, default=3600)
    w.add_argument("--intervall", type=float, default=1.0)

    a = ap.parse_args(argv)
    d = bus_dir()
    if a.cmd == "init":
        gemacht = init(d)
        print(f"Bus bereit: {d}" + (f" (neu: {', '.join(gemacht)})" if gemacht else " (war schon da)"))
        return 0
    init(d)
    if a.cmd == "send":
        m = send(d, a.von, a.an, a.typ, a.text, a.step, a.paths)
        print(f"{m['id']} an {a.an}: [{a.typ}] {a.text[:80]}")
    elif a.cmd in ("read", "wait"):
        if a.cmd == "read":
            nachrichten = read(d, a.fuer, a.alles)
        else:
            nachrichten = wait(d, a.fuer, a.timeout, a.intervall)
            if not nachrichten:
                return 3
        for m in nachrichten:
            print(f"[{m['zeit']}] {m['von']} -> {m['an']} [{m['typ']}] "
                  f"{('Step ' + m['step'] + ' ') if m.get('step') else ''}{m['text']}")
    elif a.cmd == "claim":
        c2 = claim(d, a.agent, a.step, a.paths, a.text)
        print(f"beansprucht: Step {a.step} von {a.agent} ({len(c2['pfade'])} Pfade)")
    elif a.cmd == "release":
        print(release(d, a.agent, a.step))
    elif a.cmd == "verify":
        verify(d, a.agent, a.step, a.ergebnis, a.text)
        print(f"Pruefung {a.ergebnis} fuer Step {a.step} notiert")
    elif a.cmd == "status":
        st = status(d)
        print(f"offene Ansprueche: {len(st['claims'])}")
        for c3 in st["claims"]:
            print(f"  Step {c3['step']}: {c3['agent']} seit {c3['zeit']} "
                  f"({len(c3.get('pfade', []))} Pfade)")
        print("letzte Nachrichten:")
        for m in st["letzte_nachrichten"]:
            print(f"  [{m['zeit']}] {m['von']}->{m['an']} [{m['typ']}] {m['text'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
