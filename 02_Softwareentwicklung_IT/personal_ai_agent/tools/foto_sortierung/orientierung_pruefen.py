"""Welche Fotos waren von der doppelten Drehung betroffen? (08.10.2026)

Hintergrund (``docs/changelog-2026-10-08-exif-doppelte-drehung.md``): Mit
OpenCV 5.0 lief die Gesichtserkennung bei Fotos mit EXIF-Orientierung != 1 auf
einem zweimal gedrehten Bild. pCloud-Vorschaubilder sind dagegen richtig
gedreht (gemessen 08.10.2026 an kuenstlichen Testbildern). Deshalb zeigen
Ausschnitte und Rahmen dieser Fotos ins Leere oder auf ein anderes Gesicht.

Dieses Werkzeug liest je Foto **nur den Dateikopf** (hoechstens 128 KB, dort
steht die EXIF-Orientierung) und schreibt:

* ``orientierung.jsonl`` – je Bild eine Zeile ``{"bild_id", "orientierung"}``
  (nur anhaengend; schon gepruefte Bilder werden uebersprungen, Fehler beim
  naechsten Lauf erneut versucht),
* ``gedreht_plan.json`` – Plan im Format von ``gesicht_erkennen.py --plan``
  (``{"zuege": [{"fileid"}]}``) mit allen Bildern, deren Orientierung != 1 ist.
  Diese Bilder werden mit dem reparierten Code neu erkannt.

Die Bild-IDs kommen aus den Vektordateien (``--vektoren``, mehrere moeglich);
Video-Standbilder (``<fileid>#t=<s>``) haben keine EXIF-Drehung und fallen weg.

Standard ist der **Trockenlauf** (zaehlt nur, kein Netz). ``--schreiben`` holt
die Dateikoepfe. Die Konsole zeigt nur Zahlen – keine Bild-IDs, keine Namen,
keine Koordinaten. Ziel im Repo -> Exit 2.

Aufruf (PowerShell, aus dem Projektordner ``personal_ai_agent``; das Backend-venv
reicht, OpenCV wird nicht gebraucht)::

    & .\backend\.venv\Scripts\python.exe tools\foto_sortierung\orientierung_pruefen.py `
        --vektoren (Get-ChildItem "$HOME\foto_sortierung\personen_vektoren*.jsonl").FullName --schreiben
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent
BACKEND = os.path.join(REPO, "backend")
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = os.path.join(STANDARD_BASIS, "personen_vektoren.jsonl")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "orientierung.jsonl")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "gedreht_plan.json")
KOPF_BYTES = 128 * 1024


class PruefFehler(Exception):
    """Klartext-Fehler fuer die Konsole."""


def _face_infer():
    """``backend/face_infer.py`` (numpy-only Teil) – dieselbe EXIF-Lesung wie
    die Gesichtserkennung, nicht nachgebaut."""
    spez = importlib.util.spec_from_file_location(
        "orientierung_face_infer", os.path.join(BACKEND, "face_infer.py"))
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def im_repo(pfad: str) -> bool:
    """Liegt der Pfad im Repo? Dorthin duerfen keine Bilddaten."""
    a = os.path.normcase(os.path.abspath(pfad))
    r = os.path.normcase(os.path.abspath(REPO))
    return a == r or a.startswith(r + os.sep)


def bild_ids_lesen(pfade) -> tuple:
    """Bild-IDs aus Vektordateien -> ``(ids, mit_gesicht)``.

    ``ids`` in Lesereihenfolge ohne Doppelte; Video-Standbilder (``#t=``) und
    kaputte Zeilen fallen weg. ``mit_gesicht`` = IDs mit mindestens einem
    Gesicht (fuer den Bericht)."""
    ids, gesehen, mit_gesicht = [], set(), set()
    for pfad in pfade:
        if not os.path.isfile(pfad):
            raise PruefFehler(f"Vektordatei nicht gefunden: {pfad}")
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                try:
                    daten = json.loads(zeile)
                except ValueError:
                    continue
                if not isinstance(daten, dict):
                    continue
                kennung = str(daten.get("bild_id") or "").strip()
                if not kennung or "#" in kennung:
                    continue
                if daten.get("gesichter"):
                    mit_gesicht.add(kennung)
                if kennung not in gesehen:
                    gesehen.add(kennung)
                    ids.append(kennung)
    return ids, mit_gesicht


def erledigte_lesen(pfad: str) -> dict:
    """Schon gepruefte Bilder ``{bild_id: orientierung}`` (Fehlerzeilen zaehlen
    nicht als erledigt – sie werden beim naechsten Lauf erneut versucht)."""
    erledigt = {}
    if not os.path.isfile(pfad):
        return erledigt
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                daten = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(daten, dict) and isinstance(daten.get("orientierung"), int):
                erledigt[str(daten.get("bild_id"))] = daten["orientierung"]
    return erledigt


def pruefen(ids, kopf_holen, erledigt, ausgabe: str) -> dict:
    """Je offenes Bild den Kopf holen, Orientierung lesen, Zeile anhaengen.

    ``kopf_holen(fileid) -> bytes`` ist eingesteckt (Tests ohne Netz). Ein
    Fehler bei einem Bild bricht den Lauf nie ab."""
    lesen = _face_infer().exif_orientierung
    zaehler = collections.Counter()
    with open(ausgabe, "a", encoding="utf-8") as datei:
        for kennung in ids:
            if kennung in erledigt:
                zaehler["schon_geprueft"] += 1
                continue
            try:
                kopf = kopf_holen(kennung)
                wert = int(lesen(bytes(kopf or b"")))
                zeile = {"bild_id": kennung, "orientierung": wert}
                erledigt[kennung] = wert
                zaehler["neu_geprueft"] += 1
            except Exception as problem:  # einzelnes Bild darf scheitern
                zeile = {"bild_id": kennung, "fehler": problem.__class__.__name__}
                zaehler["fehler"] += 1
            datei.write(json.dumps(zeile) + "\n")
            datei.flush()
    return dict(zaehler)


def plan_schreiben(pfad: str, erledigt: dict) -> int:
    """Plan fuer ``gesicht_erkennen.py --plan``: alle Bilder mit Orientierung != 1.
    Wird jedes Mal vollstaendig neu geschrieben (Ableitung, kein Original)."""
    zuege = [{"fileid": k} for k, o in erledigt.items() if o != 1]
    zwischen = pfad + ".neu"
    with open(zwischen, "w", encoding="utf-8") as datei:
        json.dump({"zuege": zuege}, datei)
    os.replace(zwischen, pfad)
    return len(zuege)


def bericht(ids, mit_gesicht, erledigt) -> list:
    """Nur Zahlen: Orientierungen, betroffene Bilder mit/ohne Gesicht."""
    verteilung = collections.Counter(erledigt.get(k) for k in ids if k in erledigt)
    betroffen = [k for k in ids if erledigt.get(k, 1) != 1]
    mit = sum(1 for k in betroffen if k in mit_gesicht)
    zeilen = [f"Bilder in den Vektordateien: {len(ids)} (davon mit Gesicht: {len(mit_gesicht)})",
              f"Geprueft: {sum(verteilung.values())}"]
    for wert in sorted(verteilung):
        zeilen.append(f"  Orientierung {wert}: {verteilung[wert]}")
    zeilen.append(f"Betroffen (Orientierung != 1): {len(betroffen)} – davon mit Gesicht {mit}, "
                  f"ohne Gesicht {len(betroffen) - mit}")
    return zeilen


def pcloud_kopf_holer(max_bytes: int = KOPF_BYTES):
    """Echter Kopf-Holer: getfilelink, dann nur die ersten ``max_bytes`` lesen
    (Range-Kopf; liefert der Server mehr, wird nach ``max_bytes`` abgebrochen)."""
    sys.path.insert(0, BACKEND)
    import httpx
    from app.services.pcloud_service import PCloudService
    dienst = PCloudService()

    def holen(fileid: str) -> bytes:
        link = dienst._api("/getfilelink", fileid=int(fileid))
        hosts = [h for h in (link.get("hosts") or []) if h]
        if not hosts or not link.get("path"):
            raise PruefFehler("kein Download-Link")
        url = f"https://{hosts[0]}{link['path']}"
        teile = bytearray()
        with httpx.stream("GET", url, headers={"Range": f"bytes=0-{max_bytes - 1}"},
                          timeout=60) as antwort:
            if antwort.status_code not in (200, 206):
                raise PruefFehler(f"HTTP {antwort.status_code}")
            for stueck in antwort.iter_bytes():
                teile.extend(stueck)
                if len(teile) >= max_bytes:
                    break
        return bytes(teile[:max_bytes])

    return holen


def main(argv=None, kopf_holen=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="EXIF-Orientierung je Foto lesen (nur Dateikopf) und den Plan "
                    "fuer die Neuerkennung gedrehter Fotos schreiben.")
    zerleger.add_argument("--vektoren", nargs="+", default=[STANDARD_VEKTOREN])
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE)
    zerleger.add_argument("--plan", default=STANDARD_PLAN)
    zerleger.add_argument("--schreiben", action="store_true",
                          help="Dateikoepfe wirklich holen (sonst nur zaehlen)")
    args = zerleger.parse_args(argv)

    for ziel in (args.ausgabe, args.plan):
        if im_repo(ziel):
            print(f"Abbruch: Ziel liegt im Repo ({os.path.basename(ziel)}). "
                  "Bilddaten gehoeren nach ~/foto_sortierung.")
            return 2
    try:
        ids, mit_gesicht = bild_ids_lesen(args.vektoren)
    except PruefFehler as problem:
        print(f"Abbruch: {problem}")
        return 1
    erledigt = erledigte_lesen(args.ausgabe)
    offen = sum(1 for k in ids if k not in erledigt)

    if not args.schreiben:
        print("Trockenlauf – kein Netz, nichts geschrieben.")
        print(f"Bilder: {len(ids)}, schon geprueft: {len(ids) - offen}, offen: {offen}")
        print("Mit --schreiben werden die offenen Dateikoepfe geholt (je hoechstens 128 KB).")
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(args.ausgabe)), exist_ok=True)
    holer = kopf_holen or pcloud_kopf_holer()
    zaehler = pruefen(ids, holer, erledigt, args.ausgabe)
    anzahl_plan = plan_schreiben(args.plan, erledigt)
    print(f"Lauf: neu geprueft {zaehler.get('neu_geprueft', 0)}, "
          f"schon geprueft {zaehler.get('schon_geprueft', 0)}, Fehler {zaehler.get('fehler', 0)}")
    for zeile in bericht(ids, mit_gesicht, erledigt):
        print(zeile)
    print(f"Plan fuer die Neuerkennung: {anzahl_plan} Bilder -> {os.path.basename(args.plan)}")
    return 0 if not zaehler.get("fehler") else 3


if __name__ == "__main__":
    sys.exit(main())
