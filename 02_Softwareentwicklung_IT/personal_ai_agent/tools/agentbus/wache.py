"""Wache: meldet neue Agentenbus-Nachrichten fuer Hermes.

Drei Modi (seit 29.09.2026):
  * melden (STANDARD): nur eine Windows-Benachrichtigung, KEIN Modellaufruf,
    0 Tokens. Nachrichten bleiben ungelesen, bis Hermes sie selbst liest.
  * auftrag (--auftrag oder WACHE_MODUS=auftrag): startet je Nachricht vom Typ
    'task' eine FRISCHE Hermes-Einmal-Sitzung (`hermes -z ... --usage-file ...`),
    hoechstens einen Lauf je Wache-Lauf. Kostet echtes Geld (ein Modellaufruf
    mit kurzem Prompt statt ~800k Tokens Verlauf); jeder Lauf wird mit den
    Kosten in .hermes/bus/kosten.jsonl festgehalten. Kostenbremse:
    WACHE_TAGESLIMIT_USD (Standard 1.00) - ist die Tagessumme erreicht, startet
    kein neuer Lauf und die Nachricht bleibt ungelesen. Andere Typen (info, tip,
    frage, erledigt, ...) werden nur gemeldet wie im Modus melden.
    Optional: WACHE_MODELL (-m), --max-minuten N (Standard 60; Zeitgrenze und
    Alter, ab dem eine Sperre .hermes/bus/wache-auftrag.lock als verwaist gilt).
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
import shutil
import subprocess
import sys
import time
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


def _melde_neue(d: Path, offen: list[dict]) -> int:
    """Meldet die noch nicht gemeldeten Nachrichten aus `offen` genau einmal."""
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
    return _melde_neue(d, offen)


# --- Modus 'auftrag' -------------------------------------------------------------

MAX_MINUTEN_STANDARD = 60
TAGESLIMIT_STANDARD = 1.00
PROMPT_MAX_ZEICHEN = 4000

KOSTEN_SCHLUESSEL = ("estimated_cost_usd", "cost_usd", "estimated_cost", "total_cost_usd",
                     "total_cost", "cost")
TOKENS_IN_SCHLUESSEL = ("input_tokens", "prompt_tokens", "tokens_in", "total_input_tokens")
TOKENS_OUT_SCHLUESSEL = ("output_tokens", "completion_tokens", "tokens_out", "total_output_tokens")
MODELL_SCHLUESSEL = ("model", "modell", "model_name")


def repo_wurzel() -> Path:
    for ordner in HIER.parents:
        if (ordner / ".git").exists():
            return ordner
    return HIER.parents[2]


def tageslimit() -> float:
    try:
        return float(os.environ.get("WACHE_TAGESLIMIT_USD", TAGESLIMIT_STANDARD))
    except ValueError:
        return TAGESLIMIT_STANDARD


def heute_kosten(d: Path) -> float:
    """Summe der heutigen Eintraege in kosten.jsonl (defekte Zeilen zaehlen 0)."""
    datei = d / "kosten.jsonl"
    if not datei.is_file():
        return 0.0
    heute = time.strftime("%Y-%m-%d")
    summe = 0.0
    for zeile in datei.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            e = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and str(e.get("zeit", "")).startswith(heute):
            try:
                summe += float(e.get("kosten_usd") or 0)
            except (TypeError, ValueError):
                pass
    return summe


def als_gelesen_markieren(d: Path, msg_id: str) -> None:
    """Haengt GENAU eine id an gelesen-hermes.txt (agentbus.read wuerde alle markieren)."""
    with open(d / "gelesen-hermes.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{msg_id}\n")


def sperre_holen(d: Path, max_minuten: float) -> bool:
    """Sperrdatei per O_CREAT|O_EXCL. Verwaiste Sperre (aelter als max_minuten) wird uebernommen."""
    pfad = d / "wache-auftrag.lock"
    for _ in range(2):
        try:
            fd = os.open(pfad, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                alter = time.time() - pfad.stat().st_mtime
            except FileNotFoundError:
                continue
            if alter <= max_minuten * 60:
                return False
            print(f"Sperre verwaist (Alter {int(alter // 60)} min > {max_minuten:g}) - uebernommen")
            try:
                pfad.unlink()
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        return True
    return False


def auftrag_prompt(m: dict) -> str:
    text = (m.get("text") or "").strip()[:PROMPT_MAX_ZEICHEN]
    step = m.get("step") or "ohne-step"
    zeilen = [
        "Du bist Hermes, Daten-Arbeiter im Agentenbus. Frische Sitzung fuer GENAU diesen Auftrag.",
        "",
        f"Auftrag von {m.get('von', 'claude')} (Step {step}):",
        text,
    ]
    if m.get("pfade"):
        zeilen.append("Pfade: " + ", ".join(m["pfade"]))
    zeilen += [
        "",
        "Lies bei Bedarf (nur Verweise, nichts vorab kopieren):",
        "- 02_Softwareentwicklung_IT/personal_ai_agent/HANDOVER-CLAUDE-CODE.md",
        "- docs/agentbus-protokoll.md",
        "- Plan-Dateien unter .hermes/plans/",
        "",
        "Regeln: private Daten nur lesen/kopieren, nie loeschen; jede schreibende Operation "
        "kommt in ein Manifest; keine Web-Recherche ohne ausdruecklichen Auftrag.",
        "",
        "PFLICHT am Ende: melde das Ergebnis mit Zahlen auf dem Bus:",
        "python tools/agentbus/agentbus.py send --from hermes --to claude --type erledigt "
        f'(oder blockiert) --step {step} --text "..."',
    ]
    return "\n".join(zeilen)


def _finde(daten, kandidaten):
    """Erster Treffer fuer einen der Schluessel, auch eine Ebene tiefer (tolerant)."""
    if not isinstance(daten, dict):
        return None
    for k in kandidaten:
        if daten.get(k) is not None:
            return daten[k]
    for wert in daten.values():
        if isinstance(wert, dict):
            for k in kandidaten:
                if wert.get(k) is not None:
                    return wert[k]
    return None


def bericht_lesen(pfad: Path) -> dict:
    """Liest den Kostenbericht tolerant; unbekannte Feldnamen -> None + Rohschluessel."""
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"kosten_usd": None, "tokens_in": None, "tokens_out": None, "modell": None,
                "bericht": "fehlt_oder_defekt"}
    ergebnis = {
        "kosten_usd": _finde(daten, KOSTEN_SCHLUESSEL),
        "tokens_in": _finde(daten, TOKENS_IN_SCHLUESSEL),
        "tokens_out": _finde(daten, TOKENS_OUT_SCHLUESSEL),
        "modell": _finde(daten, MODELL_SCHLUESSEL),
    }
    if any(v is None for v in ergebnis.values()) and isinstance(daten, dict):
        ergebnis["rohschluessel"] = sorted(daten.keys())
    try:
        if ergebnis["kosten_usd"] is not None:
            ergebnis["kosten_usd"] = float(ergebnis["kosten_usd"])
    except (TypeError, ValueError):
        ergebnis["kosten_usd"] = None
    return ergebnis


def _einmal_pro_tag(d: Path, schluessel: str) -> bool:
    """True genau beim ersten Aufruf je Schluessel und Tag (verhindert Toast-Flut jede Minute)."""
    datei = d / "wache-auftrag-hinweise.txt"
    marke = f"{time.strftime('%Y-%m-%d')} {schluessel}"
    if datei.is_file() and marke in datei.read_text(encoding="utf-8").splitlines():
        return False
    with open(datei, "a", encoding="utf-8") as fh:
        fh.write(marke + "\n")
    return True


def _hat_abschluss(d: Path, step: str, ab_ms: int) -> bool:
    datei = d / "messages.jsonl"
    if not datei.is_file():
        return False
    for zeile in datei.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            m = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if (m.get("von") == "hermes" and m.get("an") in ("claude", "alle")
                and m.get("typ") in ("erledigt", "blockiert") and m.get("step", "") == step):
            try:
                if int(str(m["id"]).lstrip("m")) >= ab_ms:
                    return True
            except (ValueError, KeyError):
                continue
    return False


def auftrag(mod, d: Path, max_minuten: float = MAX_MINUTEN_STANDARD) -> int:
    """Modus 'auftrag': je 'task' eine frische Hermes-Einmal-Sitzung (hoechstens eine je Lauf)."""
    offen = mod._ungelesen(d, "hermes")
    if not offen:
        return 0
    tasks = [m for m in offen if m.get("typ") == "task"]
    rest = [m for m in offen if m.get("typ") != "task"]
    if rest:
        _melde_neue(d, rest)
    if not tasks:
        return 0
    m = tasks[0]  # aelteste zuerst (Bus-Reihenfolge)
    step = m.get("step") or ""

    limit = tageslimit()
    if heute_kosten(d) >= limit:
        if _einmal_pro_tag(d, "limit"):
            toast("Agentenbus: Tageslimit erreicht",
                  f"Hermes-Auftraege pausieren (Limit {limit:.2f} $). Nachricht bleibt ungelesen.")
        print("Tageslimit erreicht - kein Lauf gestartet")
        return 0

    hermes_bin = shutil.which("hermes")
    if not hermes_bin:
        if _einmal_pro_tag(d, "kein-hermes"):
            toast("Agentenbus: hermes fehlt", "Die Hermes-CLI ist nicht im PATH. Nachricht bleibt ungelesen.")
        print("hermes nicht im PATH - Nachricht bleibt ungelesen")
        return 1

    if not sperre_holen(d, max_minuten):
        return 0  # laeuft schon einer -> still beenden
    sperre = d / "wache-auftrag.lock"
    try:
        als_gelesen_markieren(d, m["id"])
        kosten_dir = d / "kosten"
        kosten_dir.mkdir(parents=True, exist_ok=True)
        bericht = kosten_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{m['id']}.json"
        befehl = [hermes_bin, "-z", auftrag_prompt(m), "--usage-file", str(bericht),
                  "--in", str(repo_wurzel())]
        if os.environ.get("WACHE_MODELL"):
            befehl += ["-m", os.environ["WACHE_MODELL"]]
        print(f"Auftrag {m['id']} (Step {step or '-'}) -> frische Hermes-Sitzung")
        start = time.monotonic()
        ab_ms = int(time.time() * 1000)
        try:
            lauf = subprocess.run(befehl, timeout=max_minuten * 60)
            exitcode = lauf.returncode
        except subprocess.TimeoutExpired:
            exitcode = -1
            print(f"Zeitgrenze {max_minuten:g} min ueberschritten")
        except Exception as fehler:
            exitcode = -2
            print(f"Start fehlgeschlagen: {fehler}")
        dauer = round(time.monotonic() - start, 1)

        werte = bericht_lesen(bericht)
        zeile = {"zeit": time.strftime("%Y-%m-%dT%H:%M:%S"), "msg_id": m["id"], "step": step,
                 "dauer_s": dauer, "exit": exitcode, **werte}
        with open(d / "kosten.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(zeile, ensure_ascii=False) + "\n")

        preis = f"{werte['kosten_usd']:.2f} $" if werte["kosten_usd"] is not None else "Kosten unbekannt"
        toast(f"Hermes-Auftrag {step or m['id']} fertig ({preis})", f"Exit {exitcode}, {dauer} s")
        if not _hat_abschluss(d, step, ab_ms):
            mod.send(d, "hermes", "claude", "blockiert",
                     f"[Wache-Ersatzmeldung] Hermes-Lauf beendet (Exit {exitcode}, {dauer} s), aber "
                     f"keine erledigt/blockiert-Meldung zu diesem Step auf dem Bus. "
                     f"Kostenbericht: {bericht.name}. Bitte Ergebnis pruefen.", step=step)
            print("keine Abschlussmeldung von Hermes - Ersatz-blockiert gesendet")
        return 0
    finally:
        try:
            sperre.unlink()
        except FileNotFoundError:
            pass


def wache(erzwingen: bool = False, modus: str | None = None,
          max_minuten: float = MAX_MINUTEN_STANDARD) -> int:
    mod = busmodul()
    d = mod.bus_dir()
    modus = modus or os.environ.get("WACHE_MODUS", "melden")
    if modus == "auftrag":
        return auftrag(mod, d, max_minuten)
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
    def _minuten() -> float:
        if "--max-minuten" in sys.argv:
            try:
                return float(sys.argv[sys.argv.index("--max-minuten") + 1])
            except (IndexError, ValueError):
                pass
        return MAX_MINUTEN_STANDARD

    _modus = "zustellen" if "--zustellen" in sys.argv else ("auftrag" if "--auftrag" in sys.argv else None)
    sys.exit(wache(erzwingen="--laut" in sys.argv, modus=_modus, max_minuten=_minuten()))
