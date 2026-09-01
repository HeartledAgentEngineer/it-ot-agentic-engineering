#!/usr/bin/env python3
"""Inbox-Daemon fuer den 'aktiv'-Kanal (Wunsch Sebastian).

Der Server legt Track-C-Auftraege in ~/hermes_inbox/auftraege.jsonl (Kanal
'aktiv'). Dieser Daemon vertritt DIE EINE aktive Hermes-Session: er liest die
Auftraege, fuehrt sie ueber einen Hermes-Lauf mit dem Kontext der Session aus
und schreibt die Antwort in ~/hermes_inbox/antworten.jsonl. Der Server holt
sie dort (siehe stream_auftrag_aktiv) und liefert sie zurück.

So antwortet nur diese eine Hermes-Identität — keine weitere Instanz.

Bedienung:
  python hermes_inbox_daemon.py          # startet den Poll-Loop
  python hermes_inbox_daemon.py --einmal # ein Durchgang, danach Ende
"""
import json
import os
import subprocess
import sys
import time

INBOX = os.path.expanduser("~/hermes_inbox")
AUFTR = os.path.join(INBOX, "auftraege.jsonl")
ANTW  = os.path.join(INBOX, "antworten.jsonl")
STATUS = os.path.join(INBOX, "status.jsonl")


def _schreibe_status(aid: str, text: str) -> None:
    """Schreibt eine Live-Statusmeldung (was der Daemon gerade tut)."""
    try:
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"auftrag_id": aid, "text": text,
                 "zeit": time.strftime("%H:%M:%S")}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[daemon] status schreiben fehlgeschlagen: {e}", flush=True)


def _gelesene_ids():
    """IDs, fuer die bereits eine Antwort existiert (vermied Doppelbearbeitung)."""
    ids = set()
    if os.path.exists(ANTW):
        with open(ANTW, encoding="utf-8") as f:
            for zeile in f:
                z = zeile.strip()
                if not z:
                    continue
                try:
                    ids.add(json.loads(z).get("auftrag_id"))
                except Exception:
                    pass
    return ids


def _beantworte(auftrag):
    aid = auftrag.get("auftrag_id")
    text = (auftrag.get("text") or "").strip()
    kontext = (auftrag.get("kontext") or "").strip()
    if not aid or not text:
        return
    payload = text
    if kontext:
        payload = f"{text}\n\n[Kontext dieser Hermes-Session:]\n{kontext}"
    # Sofortige Statusmeldung (schnelle Rueckmeldung "was der Hermes tut").
    _schreibe_status(aid, "🔧 Hermes bearbeitet die Nachricht (Inbox-Daemon aktiv)…")
    try:
        r = subprocess.run(
            ["hermes", "chat", "-q", payload, "-Q"],
            capture_output=True, text=True, timeout=900,
        )
        out = (r.stdout or "").strip()
        zeilen = [z for z in out.splitlines() if z.strip()]
        ergebnis = "".join(zeilen) if zeilen else (r.stderr or "").strip()
        ant = {"auftrag_id": aid, "text": ergebnis or "—"}
        with open(ANTW, "a", encoding="utf-8") as f:
            f.write(json.dumps(ant, ensure_ascii=False) + "\n")
        _schreibe_status(aid, "✅ Hermes hat geantwortet.")
        print(f"[daemon] beantwortet {aid[:8]}: {ergebnis[:60]}", flush=True)
    except subprocess.TimeoutExpired:
        ant = {"auftrag_id": aid, "text": "[Timeout]"}
        with open(ANTW, "a", encoding="utf-8") as f:
            f.write(json.dumps(ant, ensure_ascii=False) + "\n")
        print(f"[daemon] timeout {aid[:8]}", flush=True)
    except Exception as e:
        print(f"[daemon] fehler {aid[:8]}: {e}", flush=True)


def durchgang():
    if not os.path.exists(AUFTR):
        return
    gelesen = _gelesene_ids()
    neue = []
    with open(AUFTR, encoding="utf-8") as f:
        for zeile in f:
            z = zeile.strip()
            if not z:
                continue
            try:
                auftrag = json.loads(z)
            except Exception:
                continue
            aid = auftrag.get("auftrag_id")
            if aid and aid not in gelesen:
                neue.append(auftrag)
    for auftrag in neue:
        _beantworte(auftrag)


def main():
    einmalig = "--einmal" in sys.argv
    print(f"[daemon] start (einmalig={einmalig}) inbox={INBOX}", flush=True)
    try:
        os.makedirs(INBOX, exist_ok=True)
    except Exception as e:
        print(f"[daemon] inbox anlegen: {e}", flush=True)
    while True:
        try:
            durchgang()
        except Exception as e:
            print(f"[daemon] throughlauf-fehler: {e}", flush=True)
        if einmalig:
            break
        time.sleep(3)


if __name__ == "__main__":
    main()