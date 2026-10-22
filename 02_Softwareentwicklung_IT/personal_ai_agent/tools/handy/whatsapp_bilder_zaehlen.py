"""W0: WhatsApp-Bilder zaehlen + Voraussetzungen pruefen (21.10.2026).

Plan: ``.hermes/plans/2026-10-21_whatsapp-bilder.md`` (Fassung 5, Schritt W0).

Laeuft am Handy in Termux. **Nur lesend, nur Zahlen:** Anzahl und Gesamtgroesse je
Unterordner (``empfangen`` = Medienordner selbst, ``gesendet`` = ``Sent``), je Jahr
und je Dateityp. In der Ausgabe stehen keine Datei-, Ordner- oder Chatnamen und
kein Pfad; unbekannte Dateiendungen heissen "andere".

Zugriff ist eine eigene Pruefung, keine Nullzaehlung: fehlt der Medienordner oder
ist er nicht lesbar, endet das Werkzeug mit **Exit 3** und der Zeile "kein Zugriff
auf den WhatsApp-Medienordner (Termux-Speicherrecht: termux-setup-storage)". Nur
ein lesbarer Ordner darf 0 melden.

``--voraussetzungen`` prueft zusaetzlich (der Reihe nach, die erste fehlende
Voraussetzung ergibt Exit 3 mit einer Zeile, ohne Token/Pfad):
    * ``httpx`` importierbar,
    * Token vorhanden (nur ja/nein; Umgebung, dann ``backend/.env``),
    * Host gueltig (nur ``eapi.pcloud.com``; jeder andere Wert endet VOR jeder
      Netzanfrage),
    * eine nur lesende pCloud-Abfrage (``userinfo``) -> ja/nein.

Exit: 0 = ok; 1 = unerwarteter Fehler; 2 = Aufrufefehler; 3 = Voraussetzung fehlt.

Aufruf (am Handy, im Projektordner ``personal_ai_agent``):
    python tools/handy/whatsapp_bilder_zaehlen.py --voraussetzungen
    python tools/handy/whatsapp_bilder_zaehlen.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)

import whatsapp_bilder_gemeinsam as gemeinsam  # noqa: E402


def _leer() -> Dict[str, Any]:
    return {"dateien": 0, "bytes": 0, "bilder": 0, "jahre": {}, "typen": Counter()}


def zaehlen(medien: "gemeinsam.Medien") -> Dict[str, Any]:
    """Die Zahlen aus einem eingelesenen Medienordner (rein, nur Zaehler)."""
    bericht: Dict[str, Any] = {k: _leer() for k in gemeinsam.KATEGORIEN}
    for eintrag in medien.dateien:
        teil = bericht[eintrag.kategorie]
        teil["dateien"] += 1
        teil["bytes"] += eintrag.groesse
        if gemeinsam.ist_bild(eintrag.name):
            teil["bilder"] += 1
        jahr = teil["jahre"].setdefault(eintrag.jahr, {"dateien": 0, "bytes": 0})
        jahr["dateien"] += 1
        jahr["bytes"] += eintrag.groesse
        endung = os.path.splitext(eintrag.name)[1].lower()
        teil["typen"][endung if endung in gemeinsam.BEKANNTE_TYPEN else "andere"] += 1
    for teil in bericht.values():
        teil["typen"] = dict(teil["typen"])
    bericht["uebersprungen"] = {
        "versteckt": medien.versteckt, "private": medien.private,
        "unterordner": medien.unterordner, "nicht_lesbar": medien.nicht_lesbar}
    return bericht


def zeilen_bauen(bericht: Dict[str, Any]) -> List[str]:
    """Die Ausgabezeilen: nur Zahlen und feste Woerter."""
    z = gemeinsam.zahl_de
    zeilen = ["WhatsApp-Bilder zaehlen (nur Zahlen, keine Namen)"]
    gesamt: Counter = Counter()
    for kategorie in gemeinsam.KATEGORIEN:
        teil = bericht[kategorie]
        zeilen.append(f"{kategorie}: {z(teil['dateien'])} Dateien, {z(teil['bytes'])} Bytes "
                      f"(Bilder {z(teil['bilder'])})")
        jahre = " · ".join(f"{jahr}: {z(v['dateien'])} ({z(v['bytes'])} Bytes)"
                           for jahr, v in sorted(teil["jahre"].items()))
        zeilen.append(f"  Jahre {kategorie}: {jahre or 'keine'}")
        gesamt.update(teil["typen"])
    typen = " · ".join(f"{t} {z(n)}" for t, n in sorted(gesamt.items()))
    zeilen.append(f"Dateitypen: {typen or 'keine'}")
    u = bericht["uebersprungen"]
    zeilen.append(f"Uebersprungen: versteckt {z(u['versteckt'])} · Private {z(u['private'])} · "
                  f"weitere Unterordner {z(u['unterordner'])} · nicht lesbar {z(u['nicht_lesbar'])}")
    return zeilen


def voraussetzungen_pruefen() -> str:
    """Alle Voraussetzungen der Reihe nach; die erste fehlende wirft ``Voraussetzung``.

    Token und Host werden vor jeder Netzanfrage geprueft. Rueckgabe: die
    Erfolgszeile (nur ja/nein).
    """
    zugang = gemeinsam.zugang_aufloesen()            # httpx, Host, Token — kein Netz
    ug = gemeinsam.uebergabe_laden()
    art = None
    try:
        ug.userinfo_pruefen(token=zugang.token, host=zugang.host)
    except ug.UebergabeFehler as fehler:
        art = gemeinsam.fehlerart(fehler)   # nur die feste Art merken; geworfen wird danach
    if art is not None:
        raise gemeinsam.Voraussetzung(
            f"Voraussetzung fehlt: pCloud-Abfrage (userinfo) fehlgeschlagen ({art})")
    return ("Voraussetzungen erfuellt: Medienordner ja · httpx ja · Token ja · "
            "Host ja · pCloud ja")


def _argumente(argv: Optional[List[str]] = None):
    p = gemeinsam.LeiserParser(
        description="WhatsApp-Bilder zaehlen (nur Zahlen) und Voraussetzungen pruefen.")
    p.add_argument("--ordner", default=gemeinsam.STANDARD_MEDIENPFAD,
                   help="Medienordner (Standard: WhatsApp Images auf dem Handy)")
    p.add_argument("--voraussetzungen", action="store_true",
                   help="zusaetzlich httpx, Token, Host und eine lesende pCloud-Abfrage pruefen")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit as ende:
        return int(ende.code or 0)
    try:
        medien = gemeinsam.medien_lesen(args.ordner)
        for zeile in zeilen_bauen(zaehlen(medien)):
            print(zeile)
        if args.voraussetzungen:
            print(voraussetzungen_pruefen())
        return gemeinsam.EXIT_OK
    except gemeinsam.Voraussetzung as fehler:
        return gemeinsam.voraussetzung_melden(fehler)
    except Exception as fehler:                      # letzte Absicherung: nur die Fehlerart
        print(f"Fehler: unerwarteter Abbruch ({gemeinsam.fehlerart(fehler)})", file=sys.stderr)
        return gemeinsam.EXIT_FEHLER


if __name__ == "__main__":
    raise SystemExit(main())
