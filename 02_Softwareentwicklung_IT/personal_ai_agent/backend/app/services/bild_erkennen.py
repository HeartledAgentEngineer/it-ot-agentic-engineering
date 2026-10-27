"""Bild-Editor B2: Gesichter eines Fotos (``fileid``) neu erkennen — speichert NICHTS.

Warum ein eigenes Modul (und nicht in ``gruppen_quiz.py``): ``gruppen_quiz`` ist ausdruecklich
„nur lokale Dateien, kein Netz, kein Modellaufruf“. Die Erkennung braucht aber pCloud (Netz) und
die Debian-Gesichtserkennung (Subprozess). Dieses Modul haengt die beiden zusammen und nutzt
``gruppen_quiz`` nur lesend (zusammengefuehrte Gesichtssicht fuer den Abgleich).

Ablauf von :func:`bild_erkennen`:

1. ``fileid`` pruefen (positive ganze Zahl, hoechstens 20 Stellen).
2. Erkennung verfuegbar? (``face_service.verfuegbar()``) — sonst gar nicht erst laden.
3. Bildquelle:
   * Pillow nutzbar (Probe :func:`_pillow_nutzbar`, wie ``datei_suche``): Original aus der pCloud
     nur in den Speicher laden (hoechstens 25 MB), ``ImageOps.exif_transpose`` (Drehung/Spiegelung
     einbacken — die Erkennung erwartet dieselbe Ausrichtung wie die Anzeige), auf hoechstens
     1600 px (laengste Seite) verkleinern, als JPEG ohne EXIF kodieren. ``quelle = original_1600``.
   * sonst (Android hat oft nur Stubs): pCloud-Vorschau 800x800 unveraendert. ``quelle =
     vorschau_800``. Die Masse kommen dann aus dem Dateikopf (JPEG/PNG), bei JPEG mit
     EXIF-Orientierung 5-8 vertauscht (die Erkennung dreht selbst, ``face_infer.orientiere_bild``).
4. ``face_service._infer`` (``max_faces = 30``, Zeitgrenze 45 s).
5. Pixel-Rahmen ``[x, y, w, h]`` -> ``bbox_norm`` (0..1, am Bild begrenzt; Rahmen unter 1 % Breite
   oder Hoehe fallen weg), Abgleich mit der B1-Sicht (``gruppen_quiz.gesichter_auf_bild``) ueber
   IoU >= 0,5 (jedes vorhandene Gesicht hoechstens einmal, bester Treffer zuerst), Namensvorschlaege
   aus dem Handy-Katalog (nur ``name`` und ``abstand``, hoechstens 3).

Datenschutz: Embeddings leben nur im Speicher dieses Aufrufs; sie stehen weder in der Antwort noch
im Log noch auf der Platte. Das Original wird nie gespeichert (kein ``open`` zum Schreiben).
Nie ein Wurf: Fehler kommen als ``{"ok": False, "grund", "fehler"}``; die Route uebersetzt
``grund`` ueber :data:`STATUS_JE_GRUND` in einen HTTP-Status.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services import face_service, gruppen_quiz
from app.services.pcloud_service import (
    MAX_DATEI_BYTES, PCloudFehler, PCloudNichtKonfiguriert, PCloudZuGross, pcloud_service)

logger = logging.getLogger(__name__)

MAX_GESICHTER = 30                 # max_faces fuer die Erkennung
ERKENNUNG_TIMEOUT_S = 45           # Zeitgrenze fuer diese Erkennung (Standard der anderen Aufrufer: 30)
MAX_KANTE = 1600                   # laengste Seite des Originals nach dem Verkleinern
JPEG_QUALITAET = 90
IOU_BEKANNT = 0.5                  # ab dieser Deckung gilt ein Rahmen als vorhandenes Gesicht
MAX_VORSCHLAEGE = 3
FILEID_MAX_STELLEN = 20

QUELLE_ORIGINAL = "original_1600"
QUELLE_VORSCHAU = "vorschau_800"

STATUS_JE_GRUND: Dict[str, int] = {
    "fileid_ungueltig": 400,
    "pcloud_nicht_konfiguriert": 503,
    "pcloud_nicht_erreichbar": 502,
    "bild_zu_gross": 413,
    "bild_unlesbar": 422,
    "erkennung_nicht_verfuegbar": 503,
    "zeitgrenze": 504,
    "erkennung_fehlgeschlagen": 502,
}

_TEXTE: Dict[str, str] = {
    "fileid_ungueltig": "Ungültige Bildkennung.",
    "pcloud_nicht_konfiguriert": "pCloud ist nicht konfiguriert.",
    "pcloud_nicht_erreichbar": "pCloud nicht erreichbar.",
    "bild_zu_gross": "Bild zu groß (über 25 MB).",
    "bild_unlesbar": "Bild nicht lesbar.",
    "erkennung_nicht_verfuegbar": "Erkennung nicht verfügbar.",
    "zeitgrenze": f"Zeitgrenze der Erkennung ({ERKENNUNG_TIMEOUT_S} s) erreicht — die Erkennung hat zu lange gebraucht.",
    "erkennung_fehlgeschlagen": "Die Erkennung ist fehlgeschlagen.",
}


class _Abbruch(Exception):
    """Interner Abbruch mit einem Grund aus :data:`STATUS_JE_GRUND`."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


def _fehler(grund: str) -> Dict[str, Any]:
    return {"ok": False, "grund": grund, "fehler": _TEXTE[grund]}


# ── Eingabe ────────────────────────────────────────────────────────────────

def _fileid_pruefen(fileid: Any) -> Optional[int]:
    """Positive ganze Zahl (int oder Ziffern-Text, hoechstens 20 Stellen), sonst ``None``."""
    if isinstance(fileid, bool):
        return None
    if isinstance(fileid, int):
        wert = fileid
    elif isinstance(fileid, str):
        s = fileid.strip()
        if not (s and s.isascii() and s.isdigit() and len(s) <= FILEID_MAX_STELLEN):
            return None
        wert = int(s)
    else:
        return None
    return wert if 0 < wert < 10 ** FILEID_MAX_STELLEN else None


# ── Bildquelle ─────────────────────────────────────────────────────────────

def _pillow_nutzbar() -> bool:
    """Probe wie ``datei_suche``/``upload``: Pillow ist am Handy oft nur ein Stub ohne native Teile."""
    try:
        from PIL import Image, ImageOps  # noqa: F401
        return True
    except Exception:
        return False


def _original_vorbereiten(roh: bytes) -> Tuple[bytes, int, int]:
    """Original (Bytes im Speicher) -> JPEG in Anzeige-Ausrichtung, laengste Seite <= 1600.

    Rueckgabe: (jpeg_bytes, breite, hoehe) der verarbeiteten Pixel. Das JPEG traegt kein EXIF
    (die Drehung steckt in den Pixeln; die Erkennung darf nicht ein zweites Mal drehen).
    Wirft ``_Abbruch`` (``bild_zu_gross`` bei Dekompressionsbombe, sonst ``bild_unlesbar``).
    """
    from PIL import Image, ImageOps
    try:
        with Image.open(io.BytesIO(roh)) as bild:
            if bild.format == "JPEG":
                try:
                    bild.draft("RGB", (MAX_KANTE, MAX_KANTE))      # schneller/sparsamer dekodieren
                except Exception:
                    pass
            gedreht = ImageOps.exif_transpose(bild)                 # Drehung/Spiegelung einbacken
            gedreht = gedreht.convert("RGB")
            gedreht.thumbnail((MAX_KANTE, MAX_KANTE))               # nie hochrechnen
            breite, hoehe = gedreht.size
            puffer = io.BytesIO()
            gedreht.save(puffer, format="JPEG", quality=JPEG_QUALITAET)
    except Image.DecompressionBombError:
        raise _Abbruch("bild_zu_gross") from None
    except Exception:
        raise _Abbruch("bild_unlesbar") from None
    return puffer.getvalue(), breite, hoehe


def _exif_orientierung(roh: bytes) -> int:
    """EXIF-Tag 274 aus JPEG-Bytes (1 = normal). Reine Bytes-Arbeit, wirft nie."""
    try:
        i, n = 2, len(roh)
        while i + 4 <= n:
            if roh[i] != 0xFF:
                i += 1
                continue
            marker = roh[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            laenge = int.from_bytes(roh[i + 2:i + 4], "big")
            if laenge < 2:
                return 1
            if marker == 0xE1 and roh[i + 4:i + 10] == b"Exif\x00\x00":
                tiff = i + 10
                endian = {b"II": "little", b"MM": "big"}.get(roh[tiff:tiff + 2])
                if not endian:
                    return 1
                ifd = tiff + int.from_bytes(roh[tiff + 4:tiff + 8], endian)
                for k in range(int.from_bytes(roh[ifd:ifd + 2], endian)):
                    e = ifd + 2 + k * 12
                    if e + 10 > n:
                        return 1
                    if int.from_bytes(roh[e:e + 2], endian) == 274:
                        wert = int.from_bytes(roh[e + 8:e + 10], endian)
                        return wert if 1 <= wert <= 8 else 1
                return 1
            if marker == 0xDA:                                       # Bilddaten: keine Kopfsegmente mehr
                return 1
            i += 2 + laenge
    except Exception:
        return 1
    return 1


def _masse_aus_kopf(roh: bytes) -> Optional[Tuple[int, int]]:
    """(Breite, Hoehe) in Anzeige-Ausrichtung aus dem Dateikopf (JPEG/PNG), ohne Pillow; sonst ``None``.

    Bei JPEG mit EXIF-Orientierung 5-8 sind Breite und Hoehe vertauscht (die Erkennung dreht selbst).
    """
    try:
        if roh[:8] == b"\x89PNG\r\n\x1a\n":
            breite = int.from_bytes(roh[16:20], "big")
            hoehe = int.from_bytes(roh[20:24], "big")
            return (breite, hoehe) if breite > 0 and hoehe > 0 else None
        if roh[:2] != b"\xff\xd8":
            return None
        i, n = 2, len(roh)
        while i + 9 <= n:
            if roh[i] != 0xFF:
                i += 1
                continue
            marker = roh[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            laenge = int.from_bytes(roh[i + 2:i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):    # SOFn
                hoehe = int.from_bytes(roh[i + 5:i + 7], "big")
                breite = int.from_bytes(roh[i + 7:i + 9], "big")
                if breite <= 0 or hoehe <= 0:
                    return None
                if _exif_orientierung(roh) >= 5:
                    breite, hoehe = hoehe, breite
                return breite, hoehe
            if laenge < 2:
                return None
            i += 2 + laenge
    except Exception:
        return None
    return None


def _bild_holen(fid: int) -> Tuple[bytes, int, int, str]:
    """(Bild-Bytes fuer die Erkennung, Breite, Hoehe, Quelle). Wirft ``_Abbruch``."""
    nutzbar = _pillow_nutzbar()
    try:
        if nutzbar:
            roh = pcloud_service.datei_bytes(fid, MAX_DATEI_BYTES)
        else:
            roh = pcloud_service.thumb(fid, "800x800")
    except PCloudNichtKonfiguriert:
        raise _Abbruch("pcloud_nicht_konfiguriert") from None
    except PCloudZuGross:
        raise _Abbruch("bild_zu_gross") from None
    except PCloudFehler as fehler:
        logger.warning("pCloud-Zugriff fuer Bild-Erkennung fehlgeschlagen: %s", fehler)
        raise _Abbruch("pcloud_nicht_erreichbar") from None
    if not roh:
        raise _Abbruch("pcloud_nicht_erreichbar")
    if nutzbar:
        jpeg, breite, hoehe = _original_vorbereiten(roh)
        return jpeg, breite, hoehe, QUELLE_ORIGINAL
    masse = _masse_aus_kopf(roh)
    if not masse:
        raise _Abbruch("bild_unlesbar")
    return roh, masse[0], masse[1], QUELLE_VORSCHAU


# ── Rahmen, Abgleich, Vorschlaege ──────────────────────────────────────────

def _norm_rahmen(bbox: Any, breite: int, hoehe: int) -> Optional[List[float]]:
    """Pixel-Rahmen ``[x, y, w, h]`` -> ``bbox_norm``, am Bild begrenzt; ``None`` bei Unbrauchbarem."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if any(v != v or abs(v) == float("inf") for v in (x, y, w, h)):
        return None
    x0, y0 = max(0.0, x), max(0.0, y)
    x1, y1 = min(float(breite), x + w), min(float(hoehe), y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    nx, ny = round(x0 / breite, 6), round(y0 / hoehe, 6)
    nw, nh = round(x1 / breite - nx, 6), round(y1 / hoehe - ny, 6)
    if nx + nw > 1:
        nw = round(1 - nx, 6)
    if ny + nh > 1:
        nh = round(1 - ny, 6)
    return gruppen_quiz._bbox_norm([nx, ny, nw, nh])          # ab 1 % Breite/Hoehe, sonst None


def _iou(a: List[float], b: List[float]) -> float:
    """Deckung zweier normierter Rahmen ``[x, y, w, h]`` (Schnitt / Vereinigung)."""
    breite = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    hoehe = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if breite <= 0 or hoehe <= 0:
        return 0.0
    schnitt = breite * hoehe
    vereinigung = a[2] * a[3] + b[2] * b[3] - schnitt
    return schnitt / vereinigung if vereinigung > 0 else 0.0


def _abgleichen(erkannt: List[List[float]], vorhanden: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
    """Je erkanntem Rahmen das vorhandene Gesicht mit IoU >= 0,5 (sonst ``None``).

    Jedes vorhandene Gesicht wird hoechstens einmal vergeben: die Paare mit der groessten
    Deckung kommen zuerst.
    """
    paare = []
    for i, rahmen in enumerate(erkannt):
        for j, gesicht in enumerate(vorhanden):
            wert = _iou(rahmen, gesicht["bbox_norm"])
            if wert >= IOU_BEKANNT:
                paare.append((wert, i, j))
    paare.sort(key=lambda p: (-p[0], p[1], p[2]))
    ergebnis: List[Optional[Dict[str, Any]]] = [None] * len(erkannt)
    vergeben: set = set()
    for _wert, i, j in paare:
        if ergebnis[i] is None and j not in vergeben:
            ergebnis[i] = vorhanden[j]
            vergeben.add(j)
    return ergebnis


def _vorschlaege(embedding: Any) -> List[Dict[str, Any]]:
    """Namensvorschlaege aus dem Handy-Katalog — nur ``name`` und ``abstand``."""
    if not embedding:
        return []
    try:
        treffer = face_service.erkenne_personen(embedding)
    except Exception:
        logger.warning("Namensvorschlaege nicht verfuegbar (Katalog nicht lesbar).")
        return []
    return [{"name": t.get("name"), "abstand": t.get("distanz")}
            for t in treffer[:MAX_VORSCHLAEGE] if isinstance(t, dict)]


def _vorhandene_gesichter(fileid: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """(Abgleich moeglich, vorhandene Gesichter mit ``bbox_norm``) aus der B1-Sicht."""
    try:
        sicht = gruppen_quiz.gesichter_auf_bild(fileid)
    except Exception:
        return False, []
    if not sicht.get("ok"):
        return False, []
    return True, [g for g in sicht.get("gesichter", []) if g.get("bbox_norm")]


# ── Oeffentliche Funktion ──────────────────────────────────────────────────

def bild_erkennen(fileid: Any) -> Dict[str, Any]:
    """Gesichter des Fotos ``fileid`` neu erkennen und mit den vorhandenen abgleichen.

    Erfolg: ``{"ok": True, "fileid", "quelle", "breite", "hoehe", "abgleich", "gesichter": [...]}``;
    je Gesicht ``bbox_norm``, ``status`` (``bekannt`` mit ``gid`` und ``name`` des vorhandenen
    Gesichts | ``neu``) und ``vorschlaege`` (``[{name, abstand}]``). ``abgleich`` ist ``False``, wenn
    die vorhandene Sicht nicht lesbar war (dann ist jedes Gesicht ``neu``).
    Fehler: ``{"ok": False, "grund", "fehler"}`` (``grund`` -> :data:`STATUS_JE_GRUND`). Speichert nichts.
    """
    fid = _fileid_pruefen(fileid)
    if fid is None:
        return _fehler("fileid_ungueltig")
    if not face_service.verfuegbar():
        return _fehler("erkennung_nicht_verfuegbar")
    try:
        bild, breite, hoehe, quelle = _bild_holen(fid)
    except _Abbruch as abbruch:
        return _fehler(abbruch.grund)

    b64 = base64.b64encode(bild).decode("ascii")
    del bild
    antwort = face_service._infer({"op": "embed", "bild_base64": b64, "max_faces": MAX_GESICHTER},
                                  timeout_s=ERKENNUNG_TIMEOUT_S)
    del b64
    if not antwort.get("ok"):
        fehlertext = str(antwort.get("fehler") or "")
        if fehlertext == "timeout":
            return _fehler("zeitgrenze")
        if fehlertext == "face-engine nicht verfuegbar":
            return _fehler("erkennung_nicht_verfuegbar")
        logger.warning("Bild-Erkennung fehlgeschlagen: %s", fehlertext[:120])
        return _fehler("erkennung_fehlgeschlagen")

    rohe = [g for g in (antwort.get("gesichter") or []) if isinstance(g, dict)]
    behalten: List[Tuple[List[float], Any]] = []
    for g in rohe:
        rahmen = _norm_rahmen(g.get("bbox"), breite, hoehe)
        if rahmen:
            behalten.append((rahmen, g.get("embedding")))

    abgleich, vorhanden = _vorhandene_gesichter(str(fid))
    treffer = _abgleichen([r for r, _e in behalten], vorhanden)
    gesichter: List[Dict[str, Any]] = []
    for (rahmen, embedding), bekannt in zip(behalten, treffer):
        eintrag: Dict[str, Any] = {"bbox_norm": rahmen,
                                   "status": "bekannt" if bekannt else "neu"}
        if bekannt:
            eintrag["gid"] = bekannt.get("gid")
            eintrag["name"] = bekannt.get("name")
        eintrag["vorschlaege"] = _vorschlaege(embedding)
        gesichter.append(eintrag)
    return {"ok": True, "fileid": str(fid), "quelle": quelle, "breite": breite, "hoehe": hoehe,
            "abgleich": abgleich, "gesichter": gesichter}
