#!/usr/bin/env python
"""OpenRouter-Guthaben und Verbrauch live abfragen.

OPENROUTER IST KEIN ABO, SONDERN EIN TANK:
  - Abgerechnet wird pro Token (Prompt + Completion + Cache), kein Grundpreis.
  - Beim AUFLADEN fallen 5,5% Gebuehr an (minimum $0,80) - auf den Preis oben drauf.
  - Auf die Modellpreise selbst gibt es KEINEN Aufschlag (Durchleitung).
  - Ist das Guthaben leer, stoppt alles (HTTP 402).

Der Schluessel wird aus $LOCALAPPDATA/hermes/.env gelesen und nie ausgegeben.

Benutzung:
    python guthaben.py              # Guthaben + Verbrauch + Hochrechnung
    python guthaben.py --json       # nur Rohdaten (fuer Skripte)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GEBUEHR_BEI_KAUF = 0.055   # OpenRouter-Aufschlag beim Aufladen
MIN_GEBUEHR = 0.80         # Mindestgebuehr pro Aufladung
UST_DE = 0.19              # deutsche Umsatzsteuer auf den Kauf


def key_holen() -> str | None:
    """Sucht den OpenRouter-Schluessel in den ueblichen Ablageorten."""
    kandidaten = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for p in kandidaten:
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            treffer = re.findall(r"sk-or-v1-[A-Za-z0-9_.\-]{20,}", text)
            if treffer:
                return treffer[0].strip()
    env_key = os.environ.get("OPENROUTER_API_KEY")
    return env_key.strip() if env_key else None


def abfragen(key: str) -> dict:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r).get("data", {})


def cash_fuer(guthaben: float) -> tuple[float, float, float]:
    """Rechnet aus, was X Guthaben in echtem Geld kostet (Gebuehr + USt)."""
    gebuehr = max(guthaben * GEBUEHR_BEI_KAUF, MIN_GEBUEHR)
    netto = guthaben + gebuehr
    ust = netto * UST_DE
    return gebuehr, ust, netto + ust


def main() -> int:
    key = key_holen()
    if not key:
        print("Kein OpenRouter-Schluessel gefunden (hermes/.env oder OPENROUTER_API_KEY).")
        return 1

    try:
        d = abfragen(key)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}")
        return 1
    except Exception as e:                      # noqa: BLE001 - Netzfehler durchreichen
        print(f"Netzfehler: {e}")
        return 1

    if "--json" in sys.argv:
        print(json.dumps(d, indent=2))
        return 0

    frei = d.get("is_free_tier")
    limit = d.get("limit")
    rest = d.get("limit_remaining")
    heute = float(d.get("usage_daily") or 0)
    woche = float(d.get("usage_weekly") or 0)
    monat = float(d.get("usage_monthly") or 0)
    gesamt = float(d.get("usage") or 0)

    print("=" * 58)
    print("  OpenRouter-Guthaben (live)")
    print("=" * 58)
    print(f"  Konto bezahlt:        {'nein (Free-Tier)' if frei else 'ja'}")
    if limit is None:
        print("  Key-Limit:            NICHT GESETZT -> unbegrenzte Ausgabe moeglich")
    else:
        print(f"  Key-Limit:            ${limit:.2f}   verbleibend: ${rest or 0:.2f}")
    print()
    print("  --- Verbrauch ---")
    print(f"  heute:                ${heute:>9.4f}")
    print(f"  diese Woche:          ${woche:>9.4f}")
    print(f"  diesen Monat:         ${monat:>9.4f}")
    print(f"  gesamt:               ${gesamt:>9.4f}")
    print()

    if monat > 0:
        tage = 25  # grobe Monatsmitte; ersetzt keine Kalenderlogik
        pro_tag = monat / tage
        print("  --- Hochrechnung ---")
        print(f"  Durchschnitt/Tag:     ${pro_tag:>9.4f}")
        print(f"  Monat (30 Tage):      ${pro_tag * 30:>9.2f}")
        for ziel in (25, 50, 100):
            g, u, total = cash_fuer(ziel)
            print(f"  ${ziel} Guthaben kostet: ${total:>7.2f}  (Gebuehr ${g:.2f} + USt ${u:.2f})")
        print()
        tage_reichweite = 100 / pro_tag if pro_tag else 0
        print(f"  $100 Guthaben reicht bei diesem Tempo: {tage_reichweite:.1f} Tage")
    print()
    print("  Kein Abo: kein Grundpreis, keine Inklusivleistung - reiner Verbrauch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
