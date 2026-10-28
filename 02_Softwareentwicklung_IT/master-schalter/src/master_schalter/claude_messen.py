"""Claude-Kontingent über den OAuth-Usage-Endpunkt aktualisieren."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import signale, zustand
from .claude_anmeldung import erneuern as cli_erneuern

URL = "https://api.anthropic.com/api/oauth/usage"
BETA = "oauth-2025-04-20"
TIMEOUT_SEKUNDEN = 10
ANMELDUNG_FEHLT = "Claude-Anmeldung fehlt – Claude Code auth login --claudeai ausführen"
ANMELDUNG_DEFEKT = "Lokaler Claude-Messzugang ist defekt – Claude Code auth login --claudeai ausführen"
ANMELDUNG_ABGELAUFEN = ("Claude-Messzugang abgelaufen – Claude Code auth login --claudeai ausführen; "
                         "Desktop-Anmeldung damit nicht bewertet")
ANMELDUNG_ABGELAUFEN_ERNEUERT = ("Claude-Messzugang abgelaufen – automatische Erneuerung um {uhrzeit} ohne Erfolg; "
                                 "Claude Code auth login --claudeai ausführen")
ERNEUERUNG_ABSTAND = timedelta(minutes=30)   # höchstens ein Erneuerungsversuch je 30 min über alle Prozesse
ERNEUERUNG_NAME = "claude-erneuerung"        # Sperre `<name>.lock` und Zeitstempel `<name>.json` im Datenordner
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


def _erneuerung_datei() -> Path:
    return signale.daten_ordner() / f"{ERNEUERUNG_NAME}.json"


def _erneuerung_zeit() -> datetime | None:
    """Zeitpunkt des letzten Erneuerungsversuchs; fehlende, unlesbare oder kaputte Datei ergibt `None` (= alt)."""
    try:
        roh = json.loads(_erneuerung_datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    zeit = signale._iso(roh.get("zeit")) if isinstance(roh, dict) else None
    if zeit is None:
        return None
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _erneuerung_versuchen(jetzt: datetime) -> datetime | None:
    """Erneuert den Messzugang höchstens einmal je `ERNEUERUNG_ABSTAND` über alle Prozesse; wirft nie.

    Ablauf unter der nicht blockierenden Sperre `claude-erneuerung.lock` (belegt ⇒ ein anderer Prozess erneuert
    gerade ⇒ kein Versuch): Zeitstempel lesen (jünger als der Abstand ⇒ kein Versuch), den neuen Zeitstempel
    **vor** dem Start atomar schreiben (Reservierung; scheitert das, gibt es keinen Versuch – ohne speicherbare
    Reservierung keine Erneuerung), erst dann `cli_erneuern()`. Ein Zeitstempel in der Zukunft gilt als alt, damit
    eine falsche Uhr die Erneuerung nicht dauerhaft sperrt. Rückgabe: Zeitpunkt des Versuchs oder `None`.
    """
    try:
        with zustand.instanz_sperre(ERNEUERUNG_NAME) as frei:
            if not frei:
                return None
            letzte = _erneuerung_zeit()
            if letzte is not None and letzte <= jetzt and jetzt - letzte < ERNEUERUNG_ABSTAND:
                return None
            try:
                signale._atomar_schreiben(_erneuerung_datei(), json.dumps({"zeit": jetzt.isoformat()}))
            except Exception:  # noqa: BLE001 - fail-closed: ohne Reservierung kein Versuch
                return None
            cli_erneuern()
            return jetzt
    except Exception:  # noqa: BLE001 - Erneuerung ist Zugabe; die Messung selbst bleibt maßgeblich
        return None


def _abgelaufen_fehler(zeit: datetime) -> MessFehler:
    """Fester Text mit der Uhrzeit (Ortszeit) des letzten Erneuerungsversuchs; nie Rohdaten."""
    uhrzeit = zeit.astimezone().strftime("%H:%M")
    return MessFehler(ANMELDUNG_ABGELAUFEN_ERNEUERT.format(uhrzeit=uhrzeit), kategorie="anmeldung_abgelaufen")


def _mit_erneuerung(abgelaufen: MessFehler, credentials_datei: Path | None, ziel: Path | None,
                    jetzt: datetime | None, transport) -> bool:
    """Reaktion auf `anmeldung_abgelaufen`: genau ein gedrosselter Erneuerungsversuch, danach genau ein zweiter `_messen`.

    Ohne Versuch (Drossel, belegte Sperre, nicht speicherbare Reservierung) bleibt es beim Fehler; liegt der letzte
    Versuch vor, nennt der Text seine Uhrzeit.
    """
    zeit = jetzt or datetime.now(timezone.utc)
    versucht = _erneuerung_versuchen(zeit)
    if versucht is None:
        letzte = _erneuerung_zeit()
        if letzte is None:
            raise abgelaufen from None
        raise _abgelaufen_fehler(letzte) from None
    try:
        return _messen(credentials_datei, ziel, jetzt, transport)
    except MessFehler as zweiter:
        if zweiter.kategorie == "anmeldung_abgelaufen":
            raise _abgelaufen_fehler(versucht) from None
        raise


def messen(credentials_datei: Path | None = None, ziel: Path | None = None,
           jetzt: datetime | None = None, transport=None, erneuern: bool = True) -> bool:
    """Misst (siehe `_messen`) und führt den Messfehler-Status in `messfehler.json` nach.

    Scheitert die Messung, wird der Eintrag der Quelle „claude“ gesetzt (Kategorie und fester Text der
    `MessFehler`, nie Rohdaten); gelingt sie, entfällt er. Das gilt für jeden Aufrufer (Leiste, CLI, Automatik).
    Fehler beim Schreiben der Statusdatei werden verschluckt; Ergebnis und Ausnahme bleiben unverändert.

    Endet die Messung mit `anmeldung_abgelaufen` und ist `erneuern` gesetzt, startet sie höchstens einmal je
    30 Minuten (über alle Prozesse) `claude auth status` zur Erneuerung des Tokens und liest danach genau einmal neu
    (`_mit_erneuerung`). Andere Fehlerarten lösen nie eine Erneuerung aus.
    """
    try:
        try:
            ergebnis = _messen(credentials_datei, ziel, jetzt, transport)
        except MessFehler as fehler:
            if not erneuern or fehler.kategorie != "anmeldung_abgelaufen":
                raise
            ergebnis = _mit_erneuerung(fehler, credentials_datei, ziel, jetzt, transport)
    except MessFehler as fehler:
        signale.messfehler_setzen("claude", fehler.kategorie, str(fehler), jetzt=jetzt)
        raise
    except Exception:
        signale.messfehler_setzen("claude", "unerwartet", MESSUNG_FEHLGESCHLAGEN, jetzt=jetzt)
        raise
    signale.messfehler_loeschen("claude")
    return ergebnis


def _messen(credentials_datei: Path | None, ziel: Path | None, jetzt: datetime | None, transport) -> bool:
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
                raise MessFehler(MESSUNG_FEHLGESCHLAGEN, getattr(antwort, "status", None), "http")
            daten = json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        if fehler.code == 401:
            raise MessFehler(ANMELDUNG_ABGELEHNT, 401, "anmeldung_abgelehnt") from None
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, fehler.code, "http") from None
    except MessFehler:
        raise
    except ValueError:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, kategorie="antwort") from None   # kein gültiges JSON
    except Exception:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, kategorie="netz") from None     # Verbindung, Zeitüberschreitung

    rate_limits = _validierte_fenster(daten)
    if rate_limits is None:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, kategorie="antwort")
    try:
        if not signale.claude_schreiben(rate_limits, ziel, jetzt=jetzt):
            raise MessFehler(MESSUNG_FEHLGESCHLAGEN, kategorie="speichern")
    except MessFehler:
        raise
    except Exception:
        raise MessFehler(MESSUNG_FEHLGESCHLAGEN, kategorie="speichern") from None
    return True
