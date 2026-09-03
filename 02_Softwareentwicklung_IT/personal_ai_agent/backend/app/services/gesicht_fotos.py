"""Gesichts-Suche ueber lokale Bildersammlung — dynamisch fuer ALLE Katalog-Personen.

Sucht Bilder, auf denen eine beliebige gespeicherte Person (Name ODER Rolle aus
dem Katalog) erkannt wird. Kein Personenname ist im Code hartkodiert — die
Person kommt zur Laufzeit vom Aufrufer (Intent/Prompt) und wird gegen den
Gesichter-Katalog aufgeloest. Pro Bild: Foto-Sammlung -> SFace-Erkennung ->
Abgleich gegen ALLE Katalogpersonen. Rueckgabe als Liste (Pfad/Datum/Person);

data_url nur bei Bedarf (fluechtig, via lese_datei_info).

Deterministisch + lokal: kein Vision-LLM noetig (der sich oft per Safety
verweigert), nur das echte SFace-Matching.
"""
import glob
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _sammle_bild_pfade(zeitraum_ab: Optional[float] = None,
                       max_bilder: int = 200) -> List[str]:
    """Sammelt Bild-Dateien (jpg/jpeg/png/webp/gif) aus lokalen Foto-Quellen."""
    from app.config import BASE_DIR
    roots = [
        str(BASE_DIR / "uploads"),
        os.path.expanduser("~/storage/shared/DCIM"),
        os.path.expanduser("~/storage/shared/Download"),
    ]
    erla = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    liste: List[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for ex in erla:
            try:
                liste += glob.glob(os.path.join(root, "**", "*" + ex), recursive=True)
            except Exception:
                pass
    gesehen = set()
    pf = []
    for p in liste:
        try:
            rp = os.path.realpath(p)
        except Exception:
            rp = p
        if rp in gesehen:
            continue
        gesehen.add(rp)
        pf.append(p)
    if zeitraum_ab is not None:
        pf = [p for p in pf if (_zeitstempel(p) or 0) >= zeitraum_ab]
    pf.sort(key=lambda p: _zeitstempel(p) or 0, reverse=True)
    return pf[:max_bilder]


def _zeitstempel(pfad: str) -> Optional[float]:
    try:
        from PIL import Image
        with Image.open(pfad) as img:
            exif = img.getexif()
            wert = exif.get(36867) or exif.get(36868) or exif.get(306)
            if wert:
                return datetime.strptime(str(wert).strip(), "%Y:%m:%d %H:%M:%S").timestamp()
    except Exception:
        pass
    try:
        return os.path.getmtime(pfad)
    except OSError:
        return None


def _normalisiere_person(person: str) -> str:
    return (person or "").strip().lower().replace("  ", " ")


def suche_bilder_mit_person(person: str, tage: Optional[int] = None) -> Dict[str, object]:
    """Findet alle lokalen Bilder, auf denen die gespeicherte Person aufgeloest
    wird. Returns {"person","gefunden":[{name,pfad,zeit,distanz,sicher}],"anzahl"}."""
    from app.services import face_service

    ziel = _normalisiere_person(person)
    if not ziel or not face_service.verfuegbar():
        return {"person": person, "gefunden": [], "anzahl": 0}

    ab = None if tage is None else (time.time() - timedelta(days=int(tage)).total_seconds())

    from app.services import gesichter_service
    katalog = gesichter_service.liste_personen()
    ziele = set()
    for p in katalog:
        n = (p.get("name") or "").lower()
        r = (p.get("rolle") or "").lower()
        if n == ziel or r == ziel or ziel in n or n in ziel:
            ziele.add(n)
    if not ziele:
        return {"person": person, "gefunden": [], "anzahl": 0,
                "hinweis": "Person ist nicht im Katalog — erst anlernen."}

    gefunden_liste = []
    for pfad in _sammle_bild_pfade(zeitraum_ab=ab):
        try:
            ergebnis = face_service.erkenne_bild_pfad(pfad)
        except Exception as e:
            logger.debug("Gesichtssuche %s: %s", pfad, e)
            continue
        for block in ergebnis.get("personen") or []:
            for t in block.get("treffer") or []:
                name = (t.get("name") or "").lower()
                if name in ziele:
                    gefunden_liste.append({
                        "name": t.get("name"),
                        "pfad": pfad,
                        "zeit": _zeitstempel(pfad),
                        "distanz": t.get("distanz"),
                        "sicher": bool(t.get("sicher")),
                    })
                    break
            else:
                continue
            break
    gefunden_liste.sort(key=lambda g: g["zeit"] or 0, reverse=True)
    return {"person": person, "gefunden": gefunden_liste, "anzahl": len(gefunden_liste)}