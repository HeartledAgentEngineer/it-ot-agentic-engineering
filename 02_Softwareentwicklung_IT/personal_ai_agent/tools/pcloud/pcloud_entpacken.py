"""Papas Amazon-Fotos: die ZIPs in der pCloud auf dem SERVER entpacken.

Anlass (10.10.2026, Sebastians ausdrueckliche Freigabe):
    Im Ordner ``/AmazonPhotosvonPapa`` liegen 32 ZIP-Dateien mit zusammen
    16,1 GB (rund 200 Bilder je Archiv, Dateinamen mit Datum). Entpackt wird
    nach ``Bilder & Videos/Papa (Amazon)/<Name des ZIPs>``. pCloud selbst
    entpackt (``extractarchive``) — es geht KEIN Byte ueber die Leitung,
    weder herunter noch hoch. Nur so ist der Schritt bezahlbar.

Dieses Werkzeug ist nur der Durchlauf; die Schreiblogik (und damit Manifest,
Positivliste und Trockenlauf) liegt in ``pcloud_bewegungen.py``. Es gibt
absichtlich keine zweite Schreiblogik.

Regeln, die der Durchlauf einhaelt:
    * **Trockenlauf ist Standard.** Geschrieben wird nur mit ``--schreiben``.
    * **Nie ueberschreiben.** Ein Zielordner, in dem schon etwas liegt, wird
      uebersprungen. Ein zweiter Lauf tut deshalb nichts (idempotent).
    * **Alles ruckholbar.** Jeder Entpackvorgang landet als Manifest-Zeile mit
      ``fileid`` (das Archiv) und ``nach_folderid`` (der angelegte Ordner).
      Das Archiv selbst bleibt unberuehrt.
    * **Erst messen, dann alle.** ``--nur`` laesst genau ein Archiv laufen —
      so sieht man Dauer und Ergebnis, bevor 32 Archive angestossen werden.
    * **Ergebnis nur in Zahlen.** Keine Dateinamen, keine Bildinhalte.

Aufruf (aus dem Projektordner ``personal_ai_agent``):
    backend/.venv/Scripts/python.exe tools/pcloud/pcloud_entpacken.py            # Trockenlauf
    backend/.venv/Scripts/python.exe tools/pcloud/pcloud_entpacken.py --nur 35 --schreiben
    backend/.venv/Scripts/python.exe tools/pcloud/pcloud_entpacken.py --schreiben
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Das Nachbarmodul importierbar machen, egal aus welchem Verzeichnis gestartet wird.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pcloud_bewegungen as pb  # noqa: E402

STANDARD_QUELLE = "/AmazonPhotosvonPapa"
STANDARD_ELTERN = "/Bilder & Videos"
STANDARD_ZIELNAME = "Papa (Amazon)"

ARCHIV_ENDUNGEN = (".zip",)


def archiv_liste(quelle_id: int, token: Optional[str], host: Optional[str]) -> List[Dict[str, Any]]:
    """Alle Archive (Dateien mit Archiv-Endung) im Quellordner, nach Namen sortiert."""
    eintraege = pb.ordner_inhalt(quelle_id, token=token, host=host)
    archive = [
        e for e in eintraege
        if not e["ist_ordner"] and e["name"].lower().endswith(ARCHIV_ENDUNGEN)
    ]
    return sorted(archive, key=lambda e: e["name"])


def ziel_name(zip_name: str) -> str:
    """Der Zielordner heisst wie das Archiv ohne Endung (z. B. 'AmazonPhotos (11)')."""
    for endung in ARCHIV_ENDUNGEN:
        if zip_name.lower().endswith(endung):
            return zip_name[: -len(endung)]
    return zip_name


def _argumente(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Archive in der pCloud auf dem Server entpacken (Trockenlauf ist Standard).",
    )
    p.add_argument("--quelle", default=STANDARD_QUELLE, help=f"Quellordner (Standard {STANDARD_QUELLE})")
    p.add_argument("--eltern", default=STANDARD_ELTERN, help=f"Elternordner des Ziels (Standard {STANDARD_ELTERN})")
    p.add_argument("--zielname", default=STANDARD_ZIELNAME, help=f"Zielordner (Standard {STANDARD_ZIELNAME})")
    p.add_argument("--nur", default="", help="Nur Archive, deren Name diesen Text enthaelt (erst messen)")
    p.add_argument("--schreiben", action="store_true", help="WIRKLICH entpacken (ohne: Trockenlauf)")
    p.add_argument("--manifest", default=None, help="Ablage des Manifests (Standard ~/foto_sortierung/manifest.jsonl)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _argumente(argv)
    trocken = not args.schreiben

    try:
        quelle = pb.ordner_per_pfad(args.quelle)
        eltern = pb.ordner_per_pfad(args.eltern)
    except pb.PCloudBewegungsFehler as fehler:
        print(f"Abbruch: {fehler}")
        return 2

    archive = archiv_liste(quelle["folderid"], None, None)
    if args.nur:
        archive = [a for a in archive if args.nur.lower() in a["name"].lower()]
    if not archive:
        print("Keine passenden Archive gefunden — es wurde nichts getan.")
        return 0

    print(f"Quelle:    {args.quelle}  ({len(archive)} Archive)")
    print(f"Ziel:      {args.eltern}/{args.zielname}/<Name des Archivs>")
    print(f"Betrieb:   {'TROCKENLAUF (nichts wird geschrieben)' if trocken else 'SCHREIBEN'}")
    print()

    zaehler = {"neu": 0, "vorhanden": 0, "entpackt": 0, "uebersprungen": 0, "fehler": 0}

    # Den Zielordner einmal idempotent holen/anlegen (nie doppelt).
    try:
        papa = pb.zielordner_finden_oder_bauen(
            eltern["folderid"], args.zielname, trocken=trocken,
            manifest_pfad=args.manifest,
        )
    except pb.PCloudBewegungsFehler as fehler:
        print(f"Abbruch: {fehler}")
        return 2

    if trocken:
        print(f"(Trockenlauf: der Ordner '{args.zielname}' wuerde {'genommen' if not papa.get('trocken') else 'angelegt'})")
        for archiv in archive:
            zielname = ziel_name(archiv["name"])
            plan = pb.archiv_entpacken(
                archiv["fileid"], 0, name=archiv["name"], von_folderid=quelle["folderid"],
                von_pfad=f"{args.quelle}/{archiv['name']}",
                nach_pfad=f"{args.eltern}/{args.zielname}/{zielname}",
                trocken=True,
            )
            assert plan["trocken"] is True
            zaehler["neu"] += 1
        print(f"Geplant: {zaehler['neu']} Archive. Nichts gesendet.")
        print("Zum Ausfuehren: --schreiben anhaengen.")
        return 0

    for nummer, archiv in enumerate(archive, start=1):
        zielname = ziel_name(archiv["name"])
        try:
            unterordner = pb.zielordner_finden_oder_bauen(
                papa["folderid"], zielname, trocken=False, manifest_pfad=args.manifest,
            )
            if unterordner.get("angelegt"):
                zaehler["neu"] += 1
            else:
                zaehler["vorhanden"] += 1
            ergebnis = pb.archiv_entpacken(
                archiv["fileid"], unterordner["folderid"], name=archiv["name"],
                von_folderid=quelle["folderid"],
                von_pfad=f"{args.quelle}/{archiv['name']}",
                nach_pfad=f"{args.eltern}/{args.zielname}/{zielname}",
                trocken=False, manifest_pfad=args.manifest,
            )
            if ergebnis.get("uebersprungen"):
                zaehler["uebersprungen"] += 1
            else:
                zaehler["entpackt"] += 1
        except pb.PCloudBewegungsFehler as fehler:
            zaehler["fehler"] += 1
            print(f"  [{nummer}/{len(archive)}] Fehler: {fehler}")
            continue

    print()
    print(f"Archive gesamt:      {len(archive)}")
    print(f"entpackt:            {zaehler['entpackt']}")
    print(f"uebersprungen:       {zaehler['uebersprungen']}  (Zielordner war nicht leer)")
    print(f"Ordner neu angelegt: {zaehler['neu']}")
    print(f"Ordner vorhanden:    {zaehler['vorhanden']}")
    print(f"Fehler:              {zaehler['fehler']}")
    print()
    print("pCloud arbeitet grosses Entpacken im Hintergrund — den Zielordner")
    print("danach mit listfolder/Explorer pruefen, statt es sofort zu glauben.")
    return 1 if zaehler["fehler"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
