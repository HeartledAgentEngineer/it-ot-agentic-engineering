#!/usr/bin/env python
"""OpenRouter-Guthaben, Verbrauch und echte Kosten - in Dollar und Euro.

OPENROUTER IST KEIN ABO, SONDERN EIN TANK:
  - Abgerechnet wird pro Token (Prompt + Completion + Cache), kein Grundpreis.
  - Beim AUFLADEN kommen zwei Posten dazu (auf den Kaufpreis, nicht auf den
    Verbrauch):
        1. Service fee   5,5%  (Minimum $0,80)  - die OpenRouter-Marge
        2. Sales Tax/VAT 19%   (deutsche USt auf Guthaben + Service fee)
    Belegt am echten Kaufdialog: $17,00 -> $0,94 Service -> $3,41 USt
    -> $21,35 gesamt. Das sind +25,5% auf das Guthaben.
  - Auf die Modellpreise selbst gibt es KEINEN Aufschlag (Durchleitung).
  - Ist das Guthaben leer, stoppt alles (HTTP 402).

Der Schluessel wird aus $LOCALAPPDATA/hermes/.env gelesen und nie ausgegeben.

Benutzung:
    python guthaben.py                 # Guthaben + Verbrauch (USD)
    python guthaben.py --euro          # dieselben Zahlen in EUR
    python guthaben.py --kaufen 25     # was bekommt man fuer 25 EUR Cash?
    python guthaben.py --json          # Rohdaten (fuer Skripte)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVICE_SATZ = 0.055      # OpenRouter-Gebuehr beim Aufladen
SERVICE_MIN = 0.80        # Mindestgebuehr
UST_SATZ = 0.19           # deutsche Umsatzsteuer
FALLBACK_KURS = 0.92      # EUR je USD, falls keine Kurs-API antwortet
PRO_TAG_ANNAHME = 3.36    # USD/Tag - sein gemessener Durchschnitt (OpenRouter live)
KURS_QUELLEN = (
    "https://open.er-api.com/v6/latest/USD",
    "https://api.exchangerate.host/latest?base=USD&symbols=EUR",
)


def wechselkurs() -> tuple[float, str]:
    """EUR je USD. Faellt auf einen festen Kurs zurueck, wenn keine API antwortet."""
    for url in KURS_QUELLEN:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                d = json.load(r)
            kurs = (d.get("rates") or {}).get("EUR")
            if kurs:
                return float(kurs), "live"
        except Exception:                       # noqa: BLE001 - naechste Quelle probieren
            continue
    return FALLBACK_KURS, "fest (Kurs-API nicht erreichbar)"


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


def kauf_rechnen(guthaben_usd: float) -> dict:
    """Was kostet dieses Guthaben in echtem Geld (Service fee + USt)?"""
    service = max(guthaben_usd * SERVICE_SATZ, SERVICE_MIN)
    zwischen = guthaben_usd + service
    ust = zwischen * UST_SATZ
    return {
        "guthaben": guthaben_usd,
        "service": service,
        "ust": ust,
        "total": zwischen + ust,
        "aufschlag_pct": (service + ust) / guthaben_usd * 100,
    }


def guthaben_fuer_cash(cash_usd: float) -> float:
    """Umkehrung: wie viel Guthaben bekommt man fuer X Cash (inkl. Gebuehren)?"""
    return cash_usd / (1 + SERVICE_SATZ) / (1 + UST_SATZ)


def main() -> int:
    argv = sys.argv[1:]
    kurs, kurs_art = wechselkurs()

    # ---- Rechenmodus ohne API: --kaufen <EUR> ----
    if "--kaufen" in argv:
        i = argv.index("--kaufen")
        try:
            cash_eur = float(argv[i + 1])
        except (IndexError, ValueError):
            print("Benutzung: python guthaben.py --kaufen 25")
            return 1
        cash_usd = cash_eur / kurs
        # cash_usd ist GELD, nicht Guthaben: erst die Gebuehren herausrechnen
        guthaben_usd = guthaben_fuer_cash(cash_usd)
        k = kauf_rechnen(guthaben_usd)
        print("=" * 60)
        print(f"  Was bekommst du fuer {cash_eur:.2f} EUR?")
        print("=" * 60)
        print(f"  Wechselkurs:     1 USD = {kurs:.4f} EUR  [{kurs_art}]")
        print(f"  Dein Cash:       {cash_eur:>7.2f} EUR  =  {cash_usd:>7.2f} USD")
        print()
        print(f"  davon Service:   {k['service']:>7.2f} USD  =  {k['service'] * kurs:>6.2f} EUR  (5,5%)")
        print(f"  davon USt:       {k['ust']:>7.2f} USD  =  {k['ust'] * kurs:>6.2f} EUR  (19%)")
        print("  " + "-" * 56)
        print(f"  GUTHABEN:        {k['guthaben']:>7.2f} USD  =  {k['guthaben'] * kurs:>6.2f} EUR")
        print()
        print(f"  Aufschlag gesamt: {k['aufschlag_pct']:.1f}%")
        tage = k["guthaben"] / PRO_TAG_ANNAHME
        print(f"  Bei deinem bisherigen Tempo (${PRO_TAG_ANNAHME:.2f}/Tag): reicht {tage:.0f} Tage")
        return 0

    # ---- Live-Modus ----
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

    if "--json" in argv:
        print(json.dumps(d, indent=2))
        return 0

    in_euro = "--euro" in argv
    w = kurs if in_euro else 1.0
    einheit = "EUR" if in_euro else "USD"

    frei = d.get("is_free_tier")
    limit = d.get("limit")
    rest = d.get("limit_remaining")
    heute = float(d.get("usage_daily") or 0)
    woche = float(d.get("usage_weekly") or 0)
    monat = float(d.get("usage_monthly") or 0)
    gesamt = float(d.get("usage") or 0)

    print("=" * 60)
    print(f"  OpenRouter (live)  -  Werte in {einheit}")
    if in_euro:
        print(f"  Umrechnung: 1 USD = {kurs:.4f} EUR  [{kurs_art}]")
    else:
        print("  Tipp: --euro zeigt alles in EUR, --kaufen 25 rechnet einen Kauf vor")
    print("=" * 60)
    print(f"  Konto bezahlt:        {'nein (Free-Tier)' if frei else 'ja'}")
    if limit is None:
        print("  Key-Limit:            NICHT GESETZT -> unbegrenzte Ausgabe moeglich")
    else:
        print(f"  Key-Limit:            {limit * w:>7.2f}   verbleibend: {float(rest or 0) * w:>7.2f} {einheit}")
    print()
    print("  --- Verbrauch ---")
    for label, wert in (("heute", heute), ("diese Woche", woche),
                        ("diesen Monat", monat), ("gesamt", gesamt)):
        print(f"  {label:<21} {wert * w:>9.4f} {einheit}")
    print()

    if monat > 0:
        pro_tag = monat / 25          # grobe Monatsbasis; ersetzt keine Kalenderlogik
        print("  --- Hochrechnung ---")
        print(f"  Durchschnitt/Tag:     {pro_tag * w:>9.4f} {einheit}")
        print(f"  Monat (30 Tage):      {pro_tag * 30 * w:>9.2f} {einheit}")
        if not in_euro:
            k = kauf_rechnen(pro_tag * 30)
            print(f"  Cash fuer 1 Monat:    {k['total']:>8.2f} USD  = {k['total'] * kurs:>7.2f} EUR"
                  f"   (inkl. {k['aufschlag_pct']:.1f}% Aufschlag)")
        print()
        tage100 = 100 / pro_tag if pro_tag else 0
        cash100 = kauf_rechnen(100)["total"]
        print(f"  $100 Guthaben reicht: {tage100:.1f} Tage  "
              f"({100 * kurs:.2f} EUR Guthaben, Cash {cash100 * kurs:.2f} EUR)")
    print()
    print("  Kein Abo: kein Grundpreis, keine Inklusivleistung - reiner Verbrauch.")
    print("  Aufschlag nur beim Kauf: 5,5% Service + 19% USt = +25,5%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
