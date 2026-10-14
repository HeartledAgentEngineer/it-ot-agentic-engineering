"""Befehlszeile `masterwechsel`.

    masterwechsel status              beide Kontingente anzeigen
    masterwechsel statuszeile         Statuszeilen-Befehl für Claude Code (liest JSON von stdin)
    masterwechsel claude-kontingent   Claude-Werte von Hand eintragen (Ersatzweg ohne Statuszeile)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import __version__, anzeige, signale


def _statuszeile() -> int:
    """Darf nie scheitern: Claude Code zeigt sonst eine Fehlermeldung in der Statuszeile."""
    try:
        daten = json.load(sys.stdin)
        if isinstance(daten, dict):
            signale.claude_schreiben(daten.get("rate_limits"))
        print(anzeige.tooltip([signale.claude_lesen()]))
    except Exception:  # noqa: BLE001 - bewusst breit, siehe Docstring
        print(anzeige.tooltip([signale.claude_lesen()]))
    return 0


def _zeitpunkt(text: str) -> datetime:
    zeit = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _prozent(text: str) -> float:
    wert = float(text)
    if not 0 <= wert <= 100:
        raise argparse.ArgumentTypeError("Prozent muss zwischen 0 und 100 liegen")
    return wert


def _claude_kontingent(args: argparse.Namespace) -> int:
    signale.claude_schreiben({
        "five_hour": {"used_percentage": args.fuenf, "resets_at": args.reset_fuenf.timestamp()},
        "seven_day": {"used_percentage": args.woche, "resets_at": args.reset_woche.timestamp()},
    })
    print(anzeige.tooltip([signale.claude_lesen()]))
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="masterwechsel", description="Befehlszeile des Master-Schalters")
    p.add_argument("--version", action="version", version=f"master-schalter {__version__}")
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("status", help="beide Kontingente anzeigen")
    unter.add_parser("statuszeile", help="Statuszeilen-Befehl für Claude Code")
    hand = unter.add_parser("claude-kontingent", help="Claude-Werte von Hand eintragen")
    hand.add_argument("--fuenf", type=_prozent, required=True, help="5-Stunden-Verbrauch in Prozent")
    hand.add_argument("--woche", type=_prozent, required=True, help="Wochen-Verbrauch in Prozent")
    hand.add_argument("--reset-fuenf", type=_zeitpunkt, required=True, help="ISO-Zeitpunkt")
    hand.add_argument("--reset-woche", type=_zeitpunkt, required=True, help="ISO-Zeitpunkt")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as ende:
        if ende.code not in (0, None):
            return 2
        raise
    if args.befehl == "statuszeile":
        return _statuszeile()
    if args.befehl == "claude-kontingent":
        return _claude_kontingent(args)
    print("\n".join(anzeige.details(signale.alle_lesen())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
