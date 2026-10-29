"""Antigravity-Transport über `agentapi` (`language_server.exe agentapi`): Gespräche anlegen und wecken.

Antigravity übergibt seinen Kindprozessen (insbesondere den Hooks aus `hooks.json`) die Verbindungsdaten
zum lokalen Language-Server über Umgebungsvariablen (`ANTIGRAVITY_AGENTAPI_EXE`, `ANTIGRAVITY_LS_ADDRESS`,
`ANTIGRAVITY_CSRF_TOKEN`, `ANTIGRAVITY_PROJECT_ID`, `ANTIGRAVITY_APP_DATA_DIR`). Damit auch Prozesse außerhalb
des Antigravity-Prozessbaums (wie `leiste.py` oder ein externes `masterwechsel`-Kommando) bei einem
Kontingent-Limit automatisch neue Antigravity-Gespräche anlegen und benachrichtigen können, merkt
`umgebung_merken()` diese lokalen Laufzeitvariablen atomar in `<daten_ordner>/agy-server.json`.

Sicherheitsregeln:
* Der CSRF-Token und Pfade aus `agy-server.json` werden niemals ausgegeben, geloggt oder in Fehlermeldungen
  übernommen.
* `language_server.exe` wird immer direkt als Liste (`shell=False`) mit dem Unterbefehl `agentapi` gestartet
  (wie im offiziellen Antigravity-Sidecar-SDK dokumentiert), niemals über `cmd.exe` / `agentapi.bat`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import modi, signale

SERVER_DATEI = "agy-server.json"
TIMEOUT_SEKUNDEN = 20
ENV_SCHLUESSEL = (
    "ANTIGRAVITY_AGENTAPI_EXE",
    "ANTIGRAVITY_LS_ADDRESS",
    "ANTIGRAVITY_CSRF_TOKEN",
    "ANTIGRAVITY_PROJECT_ID",
    "ANTIGRAVITY_APP_DATA_DIR",
    "ANTIGRAVITY_CLI_BIN_DIR",
)
UUID_MUSTER = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
Lauf = Callable[[list[str], dict[str, str], int], tuple[int, str]]


def server_pfad(datei: Path | None = None) -> Path:
    return datei if datei is not None else signale.daten_ordner() / SERVER_DATEI


def umgebung_merken(umgebung: Mapping[str, str] | None = None, datei: Path | None = None) -> bool:
    """Lokale Antigravity-Verbindungsdaten atomar speichern, falls Adresse und Token vorliegen. Wirft nie."""
    try:
        quelle = os.environ if umgebung is None else umgebung
        adresse = quelle.get("ANTIGRAVITY_LS_ADDRESS", "").strip()
        token = quelle.get("ANTIGRAVITY_CSRF_TOKEN", "").strip()
        if not adresse or not token:
            return False
        gesammelt = {
            k: quelle[k].strip()
            for k in ENV_SCHLUESSEL
            if isinstance(quelle.get(k), str) and quelle[k].strip()
        }
        pfad = server_pfad(datei)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        inhalt = json.dumps(
            {"version": 1, "zeit": datetime.now(timezone.utc).isoformat(), "env": gesammelt},
            ensure_ascii=False,
            indent=2,
        )
        signale._atomar_schreiben(pfad, inhalt)
        return True
    except Exception:  # noqa: BLE001 - darf niemals einen Hook oder CLI-Aufruf stören
        return False


def umgebung_lesen(datei: Path | None = None) -> dict[str, str]:
    """Gespeicherte Antigravity-Umgebungsvariablen lesen; bei fehlender oder defekter Datei `{}`."""
    try:
        roh = json.loads(server_pfad(datei).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(roh, dict) or not isinstance(roh.get("env"), dict):
        return {}
    return {
        k: v.strip()
        for k, v in roh["env"].items()
        if k in ENV_SCHLUESSEL and isinstance(v, str) and v.strip()
    }


def _standard_exe() -> str | None:
    """Standardpfad von `language_server.exe` unter Windows, falls vorhanden."""
    lokal = os.environ.get("LOCALAPPDATA", "").strip()
    if lokal:
        kandidat = Path(lokal) / "Programs" / "antigravity" / "resources" / "bin" / "language_server.exe"
        if kandidat.is_file():
            return str(kandidat)
    return None


def _befehl_und_umgebung(umgebung: Mapping[str, str] | None = None,
                         datei: Path | None = None) -> tuple[list[str], dict[str, str]] | None:
    """`(Befehlspräfix, Prozessumgebung)` für `agentapi` oder `None`, wenn nicht verfügbar.

    Gelesen wird aus `umgebung` (falls ausdrücklich übergeben) oder aus `agy-server.json` im aktuellen
    `daten_ordner()`. Dadurch lösen Tests mit eigenem `MASTER_SCHALTER_DATEN` niemals versehentlich echte
    `language_server.exe`-Aufrufe aus der Elternprozess-Umgebung aus.
    """
    gespeichert = dict(umgebung) if umgebung is not None else umgebung_lesen(datei)
    if not (gespeichert.get("ANTIGRAVITY_LS_ADDRESS", "").strip()
            and gespeichert.get("ANTIGRAVITY_CSRF_TOKEN", "").strip()):
        return None
    exe = gespeichert.get("ANTIGRAVITY_AGENTAPI_EXE", "").strip()
    if not exe or not Path(exe).is_file():
        exe = _standard_exe() or ""
    if not exe:
        return None
    basis = dict(os.environ)
    basis.update(gespeichert)
    return [exe, "agentapi"], basis


def _standard_lauf(befehl: list[str], umgebung: dict[str, str], timeout: int) -> tuple[int, str]:
    ergebnis = subprocess.run(
        befehl,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=umgebung,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    return ergebnis.returncode, ergebnis.stdout or ""


def _kennung_aus_daten(daten: object) -> str | None:
    """Extrahiert eine gültige Sitzungskennung aus der JSON-Antwort von `agentapi`."""
    if isinstance(daten, dict):
        for schluessel in ("conversationId", "conversation_id", "cascadeId", "cascade_id", "id"):
            wert = daten.get(schluessel)
            if isinstance(wert, str) and modi.VORGANG_ID_MUSTER.fullmatch(wert.strip()):
                return wert.strip()
        for wert in daten.values():
            treffer = _kennung_aus_daten(wert)
            if treffer is not None:
                return treffer
    elif isinstance(daten, list):
        for element in daten:
            treffer = _kennung_aus_daten(element)
            if treffer is not None:
                return treffer
    elif isinstance(daten, str):
        treffer = UUID_MUSTER.search(daten)
        if treffer is not None:
            wert = treffer.group(0)
            if modi.VORGANG_ID_MUSTER.fullmatch(wert):
                return wert
    return None


def _kennung_aus_ausgabe(ausgabe: str) -> str | None:
    text = ausgabe.strip()
    if not text:
        return None
    try:
        daten = json.loads(text)
    except ValueError:
        return _kennung_aus_daten(text)
    if isinstance(daten, dict) and daten.get("error"):
        return None
    return _kennung_aus_daten(daten)


def nachricht_senden(kennung: str, text: str, *, titel: str = "", lauf: Lauf | None = None,
                     umgebung: Mapping[str, str] | None = None, datei: Path | None = None) -> str:
    """Nachricht an ein bestehendes Antigravity-Gespräch senden (`ok` | `fehler` | `unklar`)."""
    if not isinstance(kennung, str) or modi.VORGANG_ID_MUSTER.fullmatch(kennung) is None:
        return "fehler"
    if not isinstance(text, str) or not text.strip():
        return "fehler"
    vorbereitet = _befehl_und_umgebung(umgebung, datei)
    if vorbereitet is None and lauf is None:
        return "fehler"
    praefix, env = vorbereitet if vorbereitet is not None else (["agentapi"], dict(umgebung or {}))
    befehl = [*praefix, "send-message"]
    if titel.strip():
        befehl.extend(["--title", titel.strip()])
    befehl.extend([kennung, text])
    try:
        code, ausgabe = (lauf or _standard_lauf)(befehl, env, TIMEOUT_SEKUNDEN)
    except subprocess.TimeoutExpired:
        return "unklar"
    except OSError:
        return "fehler"
    if code != 0:
        return "fehler"
    if ausgabe.strip():
        try:
            daten = json.loads(ausgabe.strip())
            if isinstance(daten, dict) and daten.get("error"):
                return "fehler"
        except ValueError:
            pass
    return "ok"


def uebergabe_prompt(thema: str, laufend: str) -> str:
    """Startauftrag für ein automatisch angelegtes Antigravity-Gespräch bei Codex-Limit."""
    return (
        f"Nachricht des Master-Schalters:\n"
        f"Automatische Übergabe des Themas „{thema}“ an Antigravity (agy), da Codex im Nutzungslimit ist.\n"
        f"1. Bitte hole sofort dein Postfach mit `masterwechsel postfach agy <deine-Conversation-ID>` ab "
        f"(deine Conversation-ID steht in `<user_information>`) und bestätige den Vorgang mit "
        f"`masterwechsel quittieren <vorgang-id> neu`.\n"
        f"2. Lies `AGENTS.md` sowie die laufende Übergabe `{laufend}` und führe das Thema als neuer Master weiter."
    )


def neues_gespraech(thema: str, laufend: str, *, modell: str = "pro", lauf: Lauf | None = None,
                    umgebung: Mapping[str, str] | None = None, datei: Path | None = None) -> str | None:
    """Neues Antigravity-Gespräch für `thema` anlegen und dessen `conversationId` zurückgeben (sonst `None`)."""
    vorbereitet = _befehl_und_umgebung(umgebung, datei)
    if vorbereitet is None and lauf is None:
        return None
    praefix, env = vorbereitet if vorbereitet is not None else (["agentapi"], dict(umgebung or {}))
    titel = f"Thema: {thema}"
    prompt = uebergabe_prompt(thema, laufend)
    befehl = [*praefix, "new-conversation", f"--model={modell}", f"--title={titel}", prompt]
    try:
        code, ausgabe = (lauf or _standard_lauf)(befehl, env, TIMEOUT_SEKUNDEN)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if code != 0:
        return None
    return _kennung_aus_ausgabe(ausgabe)
