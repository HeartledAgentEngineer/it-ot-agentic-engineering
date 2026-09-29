"""Wache: meldet neue Agentenbus-Nachrichten fuer Hermes.

Zwei Modi (seit 29.09.2026):
  * melden (STANDARD): nur eine Windows-Benachrichtigung, KEIN Modellaufruf,
    0 Tokens. Nachrichten bleiben ungelesen, bis Hermes sie selbst liest.
  * zustellen (--zustellen oder WACHE_MODUS=zustellen): wie frueher in die
    laufende Hermes-Sitzung schreiben. ACHTUNG: jede Zustellung weckt die
    Sitzung mit ihrem ganzen Verlauf - am 29.09.2026 bis ~800k Tokens je Aufruf.

Laeuft als geplanter Auftrag jede Minute. Ohne neue Nachricht beendet sich das
Skript sofort.

Ablauf im Modus zustellen:
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


def toast(titel: str, text: str) -> None:
    """Windows-Benachrichtigung zeigen - kostet keine Tokens. Fehler still."""
    import subprocess

    def q(s: str) -> str:
        return s.replace("'", "''")[:200]

    befehl = (
        "try { [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null; "
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f"$t.GetElementsByTagName('text').Item(0).InnerText = '{q(titel)}'; "
        f"$t.GetElementsByTagName('text').Item(1).InnerText = '{q(text)}'; "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Agentenbus')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($t)) } catch {}"
    )
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", befehl],
                       timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as fehler:
        print(f"Benachrichtigung nicht moeglich: {fehler}")


def melden(mod, d: Path) -> int:
    """Modus 'melden' (Standard seit 29.09.2026): NUR eine Windows-Benachrichtigung.

    Befund 29.09.2026: Jede Zustellung weckte die Hermes-Sitzung mit ihrem ganzen
    Verlauf (bis ~800k Tokens je Aufruf) - viele kleine Bus-Nachrichten kosteten so
    echtes Geld. Jetzt: kein Modellaufruf. Die Nachrichten bleiben UNGELESEN auf dem
    Bus, Hermes liest sie, wenn Sebastian ihn anspricht ("schau auf den Bus").
    Jede Nachricht wird nur EINMAL gemeldet (wache-gemeldet.txt).
    """
    offen = mod._ungelesen(d, "hermes")
    if not offen:
        return 0
    datei = d / "wache-gemeldet.txt"
    gemeldet = set(datei.read_text(encoding="utf-8").split()) if datei.is_file() else set()
    neu = [m for m in offen if m["id"] not in gemeldet]
    if not neu:
        return 0
    letzte = neu[-1]
    toast(f"Agentenbus: {len(offen)} Nachricht(en) fuer Hermes",
          f"{letzte['von']} [{letzte['typ']}] {(letzte.get('text') or '').strip()[:120]}")
    with open(datei, "a", encoding="utf-8") as fh:
        fh.write("".join(f"{m['id']}\n" for m in neu))
    print(f"{len(neu)} neue Nachricht(en) gemeldet (keine Zustellung, 0 Tokens)")
    return 0


def wache(erzwingen: bool = False, modus: str | None = None) -> int:
    mod = busmodul()
    d = mod.bus_dir()
    modus = modus or os.environ.get("WACHE_MODUS", "melden")
    if modus != "zustellen":
        return melden(mod, d)
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
    # pythonw.exe hat KEIN stdout (None) - reconfigure() wuerde abstuerzen.
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    # Ohne Konsole (pythonw.exe) gibt es kein sichtbares stdout -> alles in eine
    # Logdatei neben dem Bus, damit der geplante Auftrag unsichtbar laeuft.
    try:
        ziel = None
        try:
            ziel = busmodul().bus_dir() / "wache.log"
        except Exception:
            ziel = HIER / "wache.log"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        protokoll = open(ziel, "a", encoding="utf-8", buffering=1)
        sys.stdout = protokoll
        sys.stderr = protokoll
        print(f"--- Lauf {__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S} (PID {os.getpid()})")
    except Exception:
        pass
    sys.exit(wache(erzwingen="--laut" in sys.argv,
                   modus="zustellen" if "--zustellen" in sys.argv else None))