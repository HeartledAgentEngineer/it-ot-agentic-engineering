#!/usr/bin/env python3
"""Inbox-Daemon fuer den 'aktiv'-Kanal (Wunsch Sebastian).

Der Server legt Track-C-Auftraege in ~/hermes_inbox/auftraege.jsonl (Kanal
'aktiv'). Dieser Daemon vertritt DIE EINE aktive Hermes-Session: er liest die
Auftraege, fuehrt sie ueber einen Hermes-Lauf mit dem Kontext der Session aus
und schreibt die Antwort in ~/hermes_inbox/antworten.jsonl. Der Server holt
sie dort (siehe stream_auftrag_aktiv) und liefert sie zurück.

So antwortet nur diese eine Hermes-Identität — keine weitere Instanz.

Live-Feedback (Stand 2026-09-15):
  * `hermes chat` laeuft mit dem konfigurierten Coding-Modell
    (HERMES_LOCAL_MODEL, Standard deepseek/deepseek-v4.1-flash).
  * Jede Ausgabezeile wird als Zwischengedanke nach status.jsonl geschrieben,
    aber GEBUENDELT (mehrere Zeilen pro Meldung, ~1,2s-Takt). Vorher erzeugte
    jede einzelne Zeile eine eigene Blase — das wirkte wie viele parallel
    tippende Nachrichten.
  * Der Lauf hat ein HARTES Zeitbudget (HERMES_AUFTRAG_TIMEOUT, Standard
    3600s) mit eigenem Lese-Thread. Vorher blockierte die Leseschleife
    unbegrenzt (kein Timeout griff), sodass ein haengender Lauf den Daemon
    dauerhaft lahmlegte und der Server nach 900s "keine Antwort" meldete.

Bedienung:
  python hermes_inbox_daemon.py          # startet den Poll-Loop
  python hermes_inbox_daemon.py --einmal # ein Durchgang, danach Ende
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time

INBOX = os.path.expanduser(os.environ.get("HERMES_INBOX_DIR") or "~/hermes_inbox")
AUFTR = os.path.join(INBOX, "auftraege.jsonl")
ANTW  = os.path.join(INBOX, "antworten.jsonl")
STATUS = os.path.join(INBOX, "status.jsonl")

# Modell fuer den lokalen Hermes-Lauf (Coding-Agent). Wunsch Sebastian
# (2026-09-15): DeepSeek V4.1 Flash — dieselbe Kennung wie im Chat.
MODELL = (os.environ.get("HERMES_LOCAL_MODEL") or "deepseek/deepseek-v4.1-flash").strip()

# Hartes Gesamt-Zeitbudget eines Auftrags (Sekunden). 900s war zu kurz fuer
# Coding-Auftraege und Ursache der Abbruchmeldung.
TIMEOUT = int(os.environ.get("HERMES_AUFTRAG_TIMEOUT") or 3600)

# Buendelung: So lange sammeln wir Ausgabezeilen, bevor sie als EINE
# Zwischenmeldung geschrieben werden (weniger, dafuer zusammenhaengende
# Blasen statt vieler paralleler Einzelzeilen).
FLUSH_S = 1.2
FLUSH_MAX_ZEILEN = 6


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


def _schreibe_antwort(aid: str, text: str) -> None:
    """Schreibt die (finale) Antwort des Auftrags nach antworten.jsonl."""
    ant = {"auftrag_id": aid, "text": text}
    with open(ANTW, "a", encoding="utf-8") as f:
        f.write(json.dumps(ant, ensure_ascii=False) + "\n")


def _beantworte(auftrag):
    aid = auftrag.get("auftrag_id")
    text = (auftrag.get("text") or "").strip()
    kontext = (auftrag.get("kontext") or "").strip()
    if not aid or not text:
        return
    # Session-Kontext aus session_kontext.md (verabredete Infos/Codewort) dem
    # Hermes-Lauf mitgeben, damit eine frische Instanz den Kontext kennt.
    _kontext_file = os.path.join(INBOX, "session_kontext.md")
    try:
        if os.path.exists(_kontext_file):
            with open(_kontext_file, encoding="utf-8") as _kf:
                sess_kontext = _kf.read().strip()
        else:
            sess_kontext = ""
    except Exception:
        sess_kontext = ""
    teile = [text]
    if kontext:
        teile.append(f"[Kontext dieser Hermes-Session (Frontend):]\n{kontext}")
    if sess_kontext:
        teile.append(f"[Persistenter Session-Kontext (verabredet):]\n{sess_kontext}")
    payload = "\n\n".join(teile)
    # Sofortige Statusmeldung (schnelle Rueckmeldung "was der Hermes tut").
    _schreibe_status(
        aid, f"🔧 Hermes bearbeitet die Nachricht (Modell {MODELL})…")

    cmd = ["hermes", "chat"]
    if MODELL:
        cmd += ["-m", MODELL]
    cmd += ["-q", payload, "-Q"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
    except Exception as e:
        _schreibe_status(aid, f"❌ Hermes-Start fehlgeschlagen: {e}")
        _schreibe_antwort(aid, f"[Fehler] Hermes-Start fehlgeschlagen: {e}")
        return

    # Lese-Thread: entkoppelt das Blockieren der Pipe vom Timeout-Waechter.
    # Vorher lief die for-Schleife direkt auf proc.stdout und konnte unbegrenzt
    # haengen — der 900s-Timeout griff dadurch nie.
    zeilen: "queue.Queue" = queue.Queue()

    def _leser():
        try:
            assert proc.stdout is not None
            for zeile in proc.stdout:
                zeilen.put(zeile)
        except Exception:
            pass
        finally:
            zeilen.put(None)   # EOF-Marker

    threading.Thread(target=_leser, daemon=True).start()

    puffer = []            # [(emoji, zeile), ...]
    ergebnis_zeilen = []
    letzter_flush = time.time()
    deadline = time.time() + TIMEOUT
    abgebrochen = False

    def _flush():
        """Gebündelte Zeilen als EINE Zwischenmeldung schreiben."""
        nonlocal letzter_flush
        if puffer:
            txt = "\n".join(f"{e} {z}" for e, z in puffer)
            _schreibe_status(aid, txt)
            puffer.clear()
        letzter_flush = time.time()

    while True:
        try:
            zeile = zeilen.get(timeout=0.5)
        except queue.Empty:
            zeile = ""
        if zeile is None:
            break
        if zeile:
            z = zeile.rstrip("\n").rstrip("\r")
            s = z.strip()
            if s:
                # Reasoning-/Rahmen-Zeilen -> 🧠, Antwort-/Ergebnis-Zeilen -> 💬.
                if ("Reasoning" in s or "─" in s
                        or s.startswith("┌") or s.startswith("└")):
                    puffer.append(("🧠", s))
                elif s.startswith("╭") or s.startswith("╰"):
                    pass
                elif (s.startswith("Resume this session") or s.startswith("Query:")
                      or s.startswith("Initializing") or s.startswith("  hermes")
                      or s.startswith("session_id:")):
                    # Technischer Abschluss-Hinweis der CLI (`-Q`) — keine
                    # Antwort fuer den Nutzer, weder als Gedanke noch im Ergebnis.
                    pass
                else:
                    ergebnis_zeilen.append(s)
                    puffer.append(("💬", s))
        # Buendeln: nach FLUSH_S oder bei genug Zeilen rausschreiben.
        if puffer and (time.time() - letzter_flush >= FLUSH_S
                       or len(puffer) >= FLUSH_MAX_ZEILEN):
            _flush()
        # Harte Zeitgrenze: Lauf beenden statt ewig warten.
        if time.time() > deadline:
            abgebrochen = True
            try:
                proc.kill()
            except Exception:
                pass
            break
    _flush()

    if abgebrochen:
        _schreibe_status(
            aid, f"⏱️ Zeitbudget von {TIMEOUT}s erreicht — Lauf beendet.")
        _schreibe_antwort(
            aid, f"[Timeout nach {TIMEOUT}s] Der Hermes-Lauf wurde beendet.")
        print(f"[daemon] timeout {aid[:8]}", flush=True)
        return

    try:
        proc.wait(timeout=30)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    ergebnis = "\n".join(ergebnis_zeilen).strip() or "—"
    _schreibe_antwort(aid, ergebnis)
    _schreibe_status(aid, "✅ Hermes hat geantwortet.")
    print(f"[daemon] beantwortet {aid[:8]}: {ergebnis[:60]}", flush=True)


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
    print(f"[daemon] start (einmalig={einmalig}) inbox={INBOX} "
          f"modell={MODELL} timeout={TIMEOUT}s", flush=True)
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