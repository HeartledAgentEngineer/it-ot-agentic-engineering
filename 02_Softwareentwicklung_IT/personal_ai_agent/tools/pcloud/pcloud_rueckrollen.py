"""pCloud-Rueckrollung — Verschiebungen aus dem Manifest rueckwaerts fahren.

Warum es dieses Werkzeug gibt (Nachtlauf 26./27.09.2026):
    ``tools/pcloud/pcloud_bewegungen.py`` verschiebt Fotos nur mit Manifest
    (Standard ``~/foto_sortierung/manifest.jsonl``). Dieses Werkzeug ist die
    Rueckfahr-Versicherung dazu: Es liest das Manifest und stellt die letzten
    Aktionen wieder her — in umgekehrter Reihenfolge, jede Verschiebung
    zurueck in ihren Quellordner.

Was es kann:
    --zeigen          Das Manifest nummeriert auflisten (Zeit, Art, Name,
                      von -> nach) und am Ende zaehlen, wie viele Aktionen
                      (noch) rueckholbar waeren.
    --rueckwaerts N   Die letzten N Aktionen rueckwaerts fahren (neueste
                      zuerst). Ohne ``--wirklich`` passiert NICHTS — es kommt
                      nur die Liste, was passieren wuerde.
    --wirklich        Erst damit wird wirklich gesendet.
    --manifest PFAD   Anderes Manifest als der Standard (auch per
                      Umgebungsvariable ``PCLOUD_MANIFEST``).

Grenzen (bewusst so gebaut):
    * Angelegte Ordner werden NICHT entfernt — dafuer gibt es hier keinen
      Weg, auch nicht als Schalter. Sie werden nur gemeldet und bleiben
      bestehen.
    * Zurueckgefahren wird nur, was noch dort liegt, wo es hingehoert: Jede
      Verschiebung wird vor der Rueckrollung per Lesepruefung bestaetigt
      ("Element noch im Zielordner?"). Sonst wird nur gemeldet, nichts
      angefasst.
    * Jede echte Rueckrollung wird selbst wieder ins Manifest geschrieben
      (``art=rueckroll``) — damit ist auch die Rueckrollung nachvollziehbar,
      und ein zweiter Lauf fasst sie nicht doppelt an.

Aufruf:
    python tools/pcloud/pcloud_rueckrollen.py --zeigen
    python tools/pcloud/pcloud_rueckrollen.py --rueckwaerts 10
    python tools/pcloud/pcloud_rueckrollen.py --rueckwaerts 10 --wirklich

Rueckgabewerte: 0 = alles in Ordnung (auch Trockenlauf); 2 = Manifest
fehlt/kaputt oder Bedienfehler; 3 = mindestens eine echte Rueckroll-Aktion
ist fehlgeschlagen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Damit ``import pcloud_bewegungen`` auch dann klappt, wenn dieses Werkzeug
# aus einem anderen Arbeitsverzeichnis gestartet oder per Pfad geladen wird
# (Tests): das eigene Verzeichnis in den Suchpfad aufnehmen.
_HIER = Path(__file__).resolve().parent
if str(_HIER) not in sys.path:
    sys.path.insert(0, str(_HIER))

import pcloud_bewegungen as bewegen  # noqa: E402

# Diese Arten zaehlen als "Aktionen" beim Rueckwaertsfahren. Rueckrollungen
# selbst sind Buchungen einer Umkehr, keine eigenen Aktionen.
AKTIONS_ARTEN = ("movefile", "movefolder", "createfolder")


# ── Manifest lesen und beschreiben ────────────────────────────────────────

def _ort(eintrag: Dict[str, Any], seite: str) -> str:
    """Lesbare Ortsangabe eines Eintrags: Pfad, sonst Ordner-Id, sonst '?'."""
    pfad = eintrag.get(f"{seite}_pfad")
    if pfad:
        return str(pfad)
    kennung = eintrag.get(f"{seite}_folderid")
    if kennung is not None:
        return f"Ordner {kennung}"
    return "?"


def beschreibung(eintrag: Dict[str, Any]) -> str:
    """'von -> nach' eines Eintrags, lesbar (Pfad, sonst Ordner-Id)."""
    return f"{_ort(eintrag, 'von')} -> {_ort(eintrag, 'nach')}"


def _kennung_als_int(wert: Any) -> Optional[int]:
    """Kennung tolerant als int (None bei unbrauchbaren Werten)."""
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def _kennung_von(eintrag: Dict[str, Any], art: str) -> Optional[int]:
    """Die Kennung (fileid/folderid), die dieser Eintrag bewegt hat."""
    wert = eintrag.get("folderid") if art == "movefolder" else eintrag.get("fileid")
    if wert is None:
        wert = eintrag.get("fileid") if eintrag.get("fileid") is not None else eintrag.get("folderid")
    return _kennung_als_int(wert)


def _offen_status(eintraege: List[Dict[str, Any]]) -> Dict[int, bool]:
    """Je Kennung: ist die letzte Bewegung dazu (laut Manifest) noch offen?

    Eine spaetere Rueckrollung zur selben Kennung setzt den Stand auf False —
    dann waere sie schon zurueckgeholt.
    """
    offen: Dict[int, bool] = {}
    for eintrag in eintraege:
        art = str(eintrag.get("art") or "")
        if art in ("movefile", "movefolder"):
            kennung = _kennung_von(eintrag, art)
            if kennung is not None:
                offen[kennung] = True
        elif art == "rueckroll":
            kennung = _kennung_von(eintrag, "movefile")
            if kennung is not None:
                offen[kennung] = False
    return offen


def zaehlung(eintraege: List[Dict[str, Any]]) -> Dict[str, int]:
    """Gesamt, Verschiebungen, offen/rueckholbar, angelegte Ordner, Rueckrollungen."""
    verschiebungen = 0
    ordner = 0
    rueckrollungen = 0
    for eintrag in eintraege:
        art = str(eintrag.get("art") or "")
        if art in ("movefile", "movefolder"):
            verschiebungen += 1
        elif art == "createfolder":
            ordner += 1
        elif art == "rueckroll":
            rueckrollungen += 1
    return {
        "gesamt": len(eintraege),
        "verschiebungen": verschiebungen,
        "rueckholbar": sum(1 for wert in _offen_status(eintraege).values() if wert),
        "ordner": ordner,
        "rueckrollungen": rueckrollungen,
    }


def zeigen(eintraege: List[Dict[str, Any]], manifest_ort: str = "") -> str:
    """Die nummerierte Liste + Zaehlung als Text (rein, ohne Netz)."""
    zeilen: List[str] = []
    if manifest_ort:
        zeilen.append(f"Manifest: {manifest_ort}")
    if not eintraege:
        zeilen.append("Keine Eintraege vorhanden — es wurde noch nichts gebucht.")
        return "\n".join(zeilen)
    for nummer, eintrag in enumerate(eintraege, start=1):
        art = str(eintrag.get("art") or "?")
        name = str(eintrag.get("name") or "(ohne Namen)")
        zeit = str(eintrag.get("zeit") or "?")
        zeilen.append(f"{nummer:>4}  {zeit}  {art:<12}  {name}  [{beschreibung(eintrag)}]")
    zahlen = zaehlung(eintraege)
    zeilen.append("")
    zeilen.append(f"Eintraege gesamt: {zahlen['gesamt']}")
    zeilen.append(
        f"  Verschiebungen: {zahlen['verschiebungen']}"
        f"  (davon laut Manifest noch offen/rueckholbar: {zahlen['rueckholbar']})"
    )
    zeilen.append(
        f"  Angelegte Ordner: {zahlen['ordner']}  (bleiben bestehen — kein Loeschweg)"
    )
    zeilen.append(f"  Rueckrollungen im Manifest: {zahlen['rueckrollungen']}")
    zeilen.append("")
    zeilen.append("Rueckwaerts fahren: --rueckwaerts N (erst ohne --wirklich ansehen).")
    return "\n".join(zeilen)


# ── Plan und Ausfuehrung ──────────────────────────────────────────────────

def letzte_aktionen(eintraege: List[Dict[str, Any]], anzahl: int) -> List[Dict[str, Any]]:
    """Die letzten ``anzahl`` Aktionen in Manifest-Reihenfolge (Rest, falls weniger)."""
    aktionen = [e for e in eintraege if str(e.get("art") or "") in AKTIONS_ARTEN]
    if anzahl >= len(aktionen):
        return aktionen
    return aktionen[-anzahl:]


def rueckroll_plan(eintraege: List[Dict[str, Any]], anzahl: int) -> List[Dict[str, Any]]:
    """Die Schritte in UMGEKEHRTER Reihenfolge (neueste Aktion zuerst).

    Jeder Schritt: ``art``, ``eintrag``, ``name``, ``kennung``/``von``/``nach``
    (ints oder None), ``ist_ordner``, ``machbar``, ``grund``. ``machbar=False``
    heisst: nur melden, nichts anfassen (angelegter Ordner, unvollstaendiger
    Eintrag, laut Manifest schon zurueckgeholt).
    """
    offen = _offen_status(eintraege)
    schritte: List[Dict[str, Any]] = []
    for eintrag in reversed(letzte_aktionen(eintraege, anzahl)):
        art = str(eintrag.get("art") or "")
        name = str(eintrag.get("name") or "").strip()
        schritt: Dict[str, Any] = {
            "art": art,
            "eintrag": eintrag,
            "name": name or "(ohne Namen)",
            "kennung": None,
            "von": None,
            "nach": None,
            "ist_ordner": art == "movefolder",
            "machbar": False,
            "grund": "",
        }
        if art == "createfolder":
            schritt["grund"] = "Ordner wurde angelegt und bleibt bestehen (kein Loeschweg)."
            schritte.append(schritt)
            continue
        if art not in ("movefile", "movefolder"):
            schritt["grund"] = f"Unbekannte Art {art!r} — nichts angefasst."
            schritte.append(schritt)
            continue
        kennung = _kennung_von(eintrag, art)
        von = _kennung_als_int(eintrag.get("von_folderid"))
        nach = _kennung_als_int(eintrag.get("nach_folderid"))
        if kennung is None or von is None or nach is None:
            schritt["grund"] = "Eintrag unvollstaendig (Kennung/Quelle/Ziel fehlt) — nichts angefasst."
        elif not name:
            schritt["grund"] = "Eintrag ohne Namen — ein sicherer Lauf ist so nicht moeglich."
        elif not offen.get(kennung, True):
            schritt["grund"] = "Laut Manifest bereits zurueckgeholt — nichts angefasst."
        else:
            schritt["kennung"], schritt["von"], schritt["nach"] = kennung, von, nach
            schritt["machbar"] = True
        schritte.append(schritt)
    return schritte


def trocken_zeilen(schritte: List[Dict[str, Any]]) -> List[str]:
    """Die Liste 'was wuerde passieren' fuer den Trockenlauf (rein, ohne Netz)."""
    zeilen: List[str] = []
    for nummer, schritt in enumerate(schritte, start=1):
        if schritt["machbar"]:
            ziel = _ort(schritt["eintrag"], "von")
            zeilen.append(
                f"  {nummer}. WUERDE ZURUECK  {schritt['art']:<12} {schritt['name']}: nach [{ziel}]"
            )
        else:
            zeilen.append(
                f"  {nummer}. NICHT ANFASSEN  {schritt['art']:<12} {schritt['name']}: {schritt['grund']}"
            )
    return zeilen


def _element_im_ordner(
    ordner_id: int,
    kennung: int,
    ist_ordner: bool,
    *,
    token: Optional[str],
    host: Optional[str],
) -> bool:
    """Lesepruefung: liegt diese Kennung (noch) direkt in diesem Ordner?"""
    for vorhanden in bewegen.ordner_inhalt(ordner_id, token=token, host=host):
        if vorhanden["ist_ordner"] != ist_ordner:
            continue
        if bewegen.element_kennung(vorhanden) == kennung:
            return True
    return False


def fahre_zurueck(
    schritte: List[Dict[str, Any]],
    *,
    manifest_pfad: Optional[str] = None,
    token: Optional[str] = None,
    host: Optional[str] = None,
    ausgabe: Callable[[str], None] = print,
) -> Dict[str, int]:
    """Die Schritte wirklich ausfuehren (nur von main() mit ``--wirklich``).

    Bricht bei einem Fehler NICHT ab: Der Rest wird weiter versucht, der
    Fehler gezaehlt und am Ende als Rueckgabewert 3 gemeldet.
    """
    zaehler = {"zurueckgeholt": 0, "uebersprungen": 0, "gemeldet": 0, "fehler": 0}
    for nummer, schritt in enumerate(schritte, start=1):
        art = schritt["art"]
        name = schritt["name"]
        if not schritt["machbar"]:
            if art == "createfolder":
                zaehler["gemeldet"] += 1
            else:
                zaehler["uebersprungen"] += 1
            ausgabe(f"  {nummer}. NICHT ANGEFASST  {art:<12} {name}: {schritt['grund']}")
            continue
        kennung, von, nach = schritt["kennung"], schritt["von"], schritt["nach"]
        eintrag = schritt["eintrag"]
        try:
            if not _element_im_ordner(
                nach, kennung, schritt["ist_ordner"], token=token, host=host
            ):
                zaehler["uebersprungen"] += 1
                ausgabe(
                    f"  {nummer}. UEBERSPRUNGEN     {art:<12} {name}: liegt nicht (mehr) "
                    f"in Ordner {nach} — nichts angefasst."
                )
                continue
            if art == "movefile":
                gebucht = bewegen.datei_verschieben(
                    kennung, von, name=name,
                    von_folderid=nach,
                    von_pfad=eintrag.get("nach_pfad"), nach_pfad=eintrag.get("von_pfad"),
                    trocken=False, art="rueckroll", manifest_pfad=manifest_pfad,
                    token=token, host=host,
                )
            else:
                gebucht = bewegen.ordner_verschieben(
                    kennung, von, name=name,
                    von_folderid=nach,
                    von_pfad=eintrag.get("nach_pfad"), nach_pfad=eintrag.get("von_pfad"),
                    trocken=False, art="rueckroll", manifest_pfad=manifest_pfad,
                    token=token, host=host,
                )
        except bewegen.PCloudBewegungsFehler as problem:
            zaehler["fehler"] += 1
            ausgabe(f"  {nummer}. FEHLER          {art:<12} {name}: {problem}")
            continue
        if gebucht.get("uebersprungen"):
            zaehler["uebersprungen"] += 1
            ausgabe(f"  {nummer}. UEBERSPRUNGEN     {art:<12} {name}: {gebucht.get('grund')}")
        else:
            zaehler["zurueckgeholt"] += 1
            ausgabe(
                f"  {nummer}. RUECKWAERTS      {art:<12} {name}: "
                f"zurueck nach [{_ort(eintrag, 'von')}]"
            )
    return zaehler


# ── Kommandozeile ─────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="pCloud-Rueckrollung: Aktionen aus dem Manifest rueckwaerts fahren.",
        epilog="Erst --zeigen, dann --rueckwaerts N ohne --wirklich, dann mit --wirklich.",
    )
    gruppe = zerleger.add_mutually_exclusive_group(required=True)
    gruppe.add_argument("--zeigen", action="store_true", help="Manifest nummeriert anzeigen")
    gruppe.add_argument(
        "--rueckwaerts", type=int, metavar="N",
        help="die letzten N Aktionen rueckwaerts fahren (ohne --wirklich nur Trockenlauf)",
    )
    zerleger.add_argument(
        "--wirklich", action="store_true",
        help="ohne diesen Schalter passiert NICHTS (Trockenlauf)",
    )
    zerleger.add_argument(
        "--manifest", default=None,
        help=f"Pfad des Manifests (Standard: {bewegen.STANDARD_MANIFEST}; "
             f"auch per Umgebungsvariable {bewegen.UMGEBUNG_MANIFEST})",
    )
    args = zerleger.parse_args(argv)

    if args.zeigen and args.wirklich:
        print("--wirklich gehoert zu --rueckwaerts, nicht zu --zeigen.")
        return 2

    pfad = bewegen.manifest_datei(args.manifest)

    if args.zeigen:
        try:
            eintraege = bewegen.manifest_lesen(args.manifest)
        except bewegen.PCloudBewegungsFehler as problem:
            print(f"Manifest nicht nutzbar: {problem}")
            return 2
        print(zeigen(eintraege, str(pfad)))
        return 0

    # --rueckwaerts
    if args.rueckwaerts < 1:
        print("--rueckwaerts braucht eine Zahl ab 1.")
        return 2
    if not pfad.exists():
        print(f"Kein Manifest unter {pfad} — es gibt nichts rueckwaerts zu fahren.")
        return 2
    try:
        eintraege = bewegen.manifest_lesen(args.manifest)
    except bewegen.PCloudBewegungsFehler as problem:
        print(f"Manifest nicht nutzbar: {problem}")
        return 2

    aktionen = letzte_aktionen(eintraege, args.rueckwaerts)
    if not aktionen:
        print(f"Keine Aktionen im Manifest ({pfad}) — nichts zu tun.")
        return 0
    schritte = rueckroll_plan(eintraege, args.rueckwaerts)
    print(f"Rueckrollung: {len(schritte)} Schritt(e), neueste Aktion zuerst ({pfad}).")
    if len(aktionen) < args.rueckwaerts:
        print(f"Hinweis: es gibt nur {len(aktionen)} Aktionen im Manifest — alle werden genommen.")
    if not args.wirklich:
        print("Trockenlauf — es wird NICHTS gesendet. Mit --wirklich ausfuehren:")
        for zeile in trocken_zeilen(schritte):
            print(zeile)
        return 0

    print("Fahre rueckwaerts — jede echte Rueckrollung wird selbst ins Manifest gebucht:")
    ergebnis = fahre_zurueck(schritte, manifest_pfad=args.manifest)
    print("")
    print(
        f"Ergebnis: {ergebnis['zurueckgeholt']} rueckwaerts gefahren, "
        f"{ergebnis['uebersprungen']} uebersprungen, {ergebnis['gemeldet']} nur gemeldet, "
        f"{ergebnis['fehler']} fehlgeschlagen."
    )
    return 3 if ergebnis["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
