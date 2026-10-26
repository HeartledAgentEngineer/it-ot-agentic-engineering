"""Claude-Kontingent über den OAuth-Usage-Endpunkt aktualisieren."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import signale

URL = "https://api.anthropic.com/api/oauth/usage"
BETA = "oauth-2025-04-20"
TIMEOUT_SEKUNDEN = 10
ANMELDUNG_FEHLT = "Claude-Anmeldung fehlt – Claude Code auth login --claudeai ausführen"
ANMELDUNG_DEFEKT = "Lokaler Claude-Messzugang ist defekt – Claude Code auth login --claudeai ausführen"
ANMELDUNG_ABGELAUFEN = ("Claude-Messzugang abgelaufen – Claude Code auth login --claudeai ausführen; "
                         "Desktop-Anmeldung damit nicht bewertet")
ANMELDUNG_ABGELEHNT = "Claude-Server hat den Messzugang abgelehnt – Claude Code auth login --claudeai ausführen"
MESSUNG_FEHLGESCHLAGEN = "Claude-Kontingent konnte nicht gelesen werden"


class MessFehler(Exception):
    """Sichere, nutzerseitige Fehlermeldung ohne HTTP- oder Zugangsdaten."""

    def __init__(self, meldung: str, status: int | None = None, kategorie: str = "messung"):
        super().__init__(meldung)
        self.status = status
        self.kategorie = kategorie


class _KeineWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Verhindert, dass ein OAuth-Bearer an ein Weiterleitungsziel gelangt."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(anfrage: urllib.request.Request, timeout: int):
    """Öffnet genau die angefragte URL; Redirects werden als HTTP-Fehler behandelt."""
    opener = urllib.request.build_opener(_KeineWeiterleitung())
    return opener.open(anfrage, timeout=timeout)


def _standard_credentials_datei() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def _konfigurierte_credentials_datei() -> Path:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(config_dir) / ".credentials.json" if config_dir else _standard_credentials_datei()


def credentials_datei() -> Path:
    return _konfigurierte_credentials_datei()


def _ablaufzeit(oauth: dict[str, Any]) -> float | None:
    wert = oauth.get("expiresAt")
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    ablauf = signale._zahl(wert)
    if ablauf is None:
        return None
    if ablauf > 1e12:  # Claude Code speichert expiresAt als Unix-Millisekunden.
        ablauf /= 1000
    return ablauf


def _fenster(antwort: Any) -> dict[str, float | None] | None:
    """Fenster prüfen; ganz ohne Verbrauch darf die Rücksetzzeit fehlen (kein Fenster aktiv)."""
    if not isinstance(antwort, dict):
        return None
    prozent = signale._prozent(antwort.get("utilization"))
    if prozent is None:
        return None
    reset_text = antwort.get("resets_at")
    if reset_text is None:
        # Live gesehen 16.10.2026: leeres Fenster → {"utilization": 0.0, "resets_at": null}.
        if prozent != 0:
            return None
        return {"used_percentage": 0.0, "resets_at": None}
    reset = signale._iso(reset_text)
    if reset is None:
        return None
    try:
        ruecksetzung = reset.timestamp()
    except (OverflowError, OSError, ValueError):
        return None
    return {"used_percentage": prozent, "resets_at": ruecksetzung}


def _validierte_fenster(antwort: Any) -> dict[str, dict[str, float | None]] | None:
    if not isinstance(antwort, dict):
        return None
    fenster: dict[str, dict[str, float | None]] = {}
    for schluessel in ("five_hour", "seven_day"):
        wert = _fenster(antwort.get(schluessel))
        if wert is None:
            return None
        fenster[schluessel] = wert
    return fenster


def messen(credentials_datei: Path | None = None, ziel: Path | None = None,
           jetzt: datetime | None = None, transport=None) -> bool:
    """Liest den Access-Token nur im Speicher, prüft beide Fenster und speichert sie atomar."""
    pfad = credentials_datei if credentials_datei is not None else _konfigurierte_credentials_datei()
    try:
        text = pfad.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MessFehler(ANMELDUNG_FEHLT, kategorie="anmeldung_fehlt") from None
    except (OSError, UnicodeError):
        raise MessFehler(ANMELDUNG_DEFEKT, kategorie="anmeldung_defekt") from None
    try:
        roh = json.loads(text)
    except (TypeError, ValueError):
        raise MessFehler(ANMELDUNG_DEFEKT, kategorie="anmeldung_defekt") from None
    oauth = roh.get("claudeAiOauth") if isinstance(roh, dict) else None
    token = oauth.get("accessToken") if isinstance(oauth, dict) else None
    ablauf = _ablaufzeit(oauth) if isinstance(oauth, dict) else None
    if not isinstance(token, str) or not token or ablauf is None:
        raise MessFehler(ANMELDUNG_DEFEKT, kategorie="anmeldung_defekt")
    jetzt_ts = (jetzt or datetime.now(timezone.utc)).timestamp()
    if ablauf <= jetzt_ts:
        raise MessFehler(ANMELDUNG_ABGELAUFEN, kategorie="anmeldung_abgelaufen")

    try:
        anfrage = urllib.request.Request(
            URL,
            headers={"Authorization": f"Bearer {token}", "anthropic-beta": BETA},
            method="GET",
        )
        with (transport or _transport)(anfrage, timeout=TIMEOUT_SEKUNDEN) as antwort:
            if getattr(antwort, "status", 200) != 200:
                raise MessFehler(MESSUNG_FEHLGESCHLAGEN, getattr(antwort, "status", None))
            daten = json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        if fehler.code == 401:
            raise MessFehler(ANMELDUNG_ABGELEHNT, 401, "anmeldung_abgelehnt") from None
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, fehler.code) from None
    except MessFehler:
        raise
    except Exception:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN) from None

    rate_limits = _validierte_fenster(daten)
    if rate_limits is None:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN)
    try:
        if not signale.claude_schreiben(rate_limits, ziel, jetzt=jetzt):
            raise MessFehler(MESSUNG_FEHLGESCHLAGEN)
    except MessFehler:
        raise
    except Exception:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN) from None
    return True
