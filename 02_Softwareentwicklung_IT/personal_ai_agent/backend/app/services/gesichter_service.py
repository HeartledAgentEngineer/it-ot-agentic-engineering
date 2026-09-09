"""Gesichter-Katalog (Personen-Merkliste) für den Personal-Agent.

Speichert, wen der Agent kennen soll — Name + Rolle + eine Gesichts-/
Erscheinungs-Beschreibung (optional) sowie einen Referenz-Bildpfad. Nur der
PFAD des Referenzbilds wird gespeichert (Sebastian-Regel: die Originaldatei
wird nie verändert/dupliziert), nicht das Bild selbst.

Der Katalog ist die datengetriebene Grundlage fürs "Gesichter merken":
- Der LLM bekommt den Katalog als Kontext, wenn ein Foto analysiert wird
  (Vision), damit er sagt "Das ist Pedi" statt "eine Person".
- Neue Einträge entstehen reaktiv ("das ist Pedi") oder gepflegt per Katalog.

Persistenz: JSON-Datei neben `auftraege.json` (unter dem Projektordner, gleiche
Ablage wie chroma_data). Bewusst GITIGNORED — der Katalog enthält private
Personendaten und das Repo ist öffentlich.

Deterministisch, kein LLM: Der Service speichert nur. Das Auswerten/Abgleichen
von Fotos macht der Vision-LLM im Chat-Flow, nicht hier.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import List, Optional

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

# Persistenter Ablageort: neben chroma_data / auftraege.json im Projektordner.
KATALOG_DATEI = BASE_DIR / "gesichter_katalog.json"

# Schreib-/Lesezugriffe sind bewusst serialisiert (Single-Writer), damit zwei
# gleichzeitige Chat-/Tool-Aufrufe die Datei nicht zerschiessen.
_sperre = threading.Lock()


def _utc_iso() -> str:
    """Aktuell Zeit als ISO-String (UTC), konsistent für alle Zeitstempel."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer_katalog() -> List[dict]:
    return []


def _laden() -> List[dict]:
    """Liest den Katalog von der Platte (leer, wenn noch nicht vorhanden)."""
    if not os.path.exists(KATALOG_DATEI):
        return _leer_katalog()
    try:
        with open(KATALOG_DATEI, "r", encoding="utf-8") as f:
            daten = json.load(f)
        if isinstance(daten, dict) and isinstance(daten.get("personen"), list):
            return daten["personen"]
        if isinstance(daten, list):
            return daten
        return _leer_katalog()
    except Exception as e:
        logger.warning("Gesichter-Katalog nicht lesbar, liefere leer: %s", e)
        return _leer_katalog()


def _speichern(personen: List[dict]) -> None:
    """Schreibt den Katalog atomar auf die Platte (tmp + rename)."""
    os.makedirs(KATALOG_DATEI.parent, exist_ok=True)
    tmp = KATALOG_DATEI.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"personen": personen}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, KATALOG_DATEI)


def liste_personen() -> List[dict]:
    """Alle gelernten Personen (ohne interne Hilfsfelder)."""
    with _sperre:
        return sorted(_laden(), key=lambda p: (p.get("name") or "").lower())


def person_finden(name: str) -> Optional[dict]:
    """Eine Person anhand ihres Namens (case-insensitive). None, wenn unbekannt."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return None
    with _sperre:
        for p in _laden():
            if (p.get("name") or "").strip().lower() == ziel:
                return p
    return None


# Maximale Kantenlänge der gespeicherten Referenz-Miniatur (Pixel). Bewusst
# klein, damit der Katalog kompakt bleibt und pCloud-Transfers nicht aufbläht.
_MAX_MINIATUR_PX = 512
# Kompressionsqualität für die gespeicherte JPEG-Miniatur.
_MINIATUR_QUALITAET = 80


def referenz_miniatur_von_pfad(
    pfad: str, max_px: int = _MAX_MINIATUR_PX
) -> Optional[str]:
    """Erzeugt aus einem Bildpfad eine kleine Base64-JPEG-Miniatur (in-memory).

    Sebastian-Regel: Die Originaldatei wird NIEMALS überschrieben. Diese
    Miniatur ist eine separate, verkleinerte Daten-Kopie (für den Katalog),
    damit das Referenzbild auch dann erhalten bleibt, wenn das Original in
    z. B. die pCloud verschoben wird. Die Miniatur bleibt beim Assistenten;
    das Original wandert/e mit dem Nutzer.

    Returns: data_url (Base64) der Miniatur, oder None bei Fehler/kein PIL.
    """
    try:
        from PIL import Image, ImageOps
        import base64
        import io
        img = Image.open(pfad)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_MINIATUR_QUALITAET)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        logger.warning("Miniatur-Erzeugung fehlgeschlagen für %s: %s", pfad, e)
        return None


def _refs_bereinigen(referenzen: Optional[list]) -> Optional[list]:
    """Reduziert eine Referenzliste auf {embedding, jahr}-Dicts (bereinigt)."""
    if not referenzen:
        return None
    out = []
    for r in referenzen:
        if isinstance(r, dict) and r.get("embedding"):
            out.append({"embedding": r["embedding"], "jahr": r.get("jahr")})
        elif r:  # roher Vektor -> kein jahr
            out.append({"embedding": r, "jahr": None})
    return out or None


def person_speichern(
    name: str,
    rolle: str = "",
    beziehung: str = "",
    beschreibung: str = "",
    referenz_bild_pfad: str = "",
    referenz_bild_miniatur: str = "",
    embedding: Optional[list] = None,
    referenzen: Optional[list] = None,
) -> dict:
    """Legt eine Person an oder aktualisiert sie (Upsert nach Name).

    Reihenfolge des Erscheinungsbilds ist Daten, kein Encodierungs-Wirrwarr:
    `rolle` (z. B. "Mutter"), `beziehung` (z. B. "Fährt im Auto hinten mit"),
    `beschreibung` (Merkmale wie "graue Haare"), `referenz_bild_pfad` (nur der
    Pfad! die Datei bleibt unangetastet). Zusätzlich wird eine kleine
    Referenz-Miniatur automatisch aus dem Pfad erzeugt und eingebettet
    gespeichert — damit das Referenzbild erhalten bleibt, auch wenn das
    Original später in z. B. die pCloud verschoben wird. Erhalt die Miniatur
    als `referenz_bild_miniatur` (Base64), überlebt sie Umzüge bzw. wird
    optional direkt übergeben.

    Returns: die (neue/aktualisierte) Person als dict.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Name darf nicht leer sein")

    # Miniatur immer aus dem (neuen) Pfad erzeugen, sofern vorhanden — und
    # die zuletzt gelieferte Miniatur hat Vorrang vor der aus dem Pfad.
    miniature = referenz_bild_miniatur
    if referenz_bild_pfad and not miniature:
        gefunden = person_finden(name)
        vorhandene = (gefunden or {}).get("referenz_bild_miniatur") if gefunden else ""
        if not vorhandene:
            miniature = referenz_miniatur_von_pfad(referenz_bild_pfad) or ""

    with _sperre:
        personen = _laden()
        vorhanden = next(
            (p for p in personen if (p.get("name") or "").strip().lower() == name.lower()),
            None,
        )
        if vorhanden is not None:
            if rolle:
                vorhanden["rolle"] = rolle.strip()
            if beziehung:
                vorhanden["beziehung"] = beziehung.strip()
            if beschreibung:
                vorhanden["beschreibung"] = beschreibung.strip()
            if referenz_bild_pfad:
                vorhanden["referenz_bild_pfad"] = referenz_bild_pfad.strip()
            if miniature:
                vorhanden["referenz_bild_miniatur"] = miniature
            if referenzen is not None:
                vorhanden["referenzen"] = _refs_bereinigen(referenzen)
                vorhanden["embedding"] = [r.get("embedding") for r in vorhanden["referenzen"]]
            elif embedding is not None:
                vorhanden["embedding"] = embedding
            vorhanden.setdefault("gelernt_am", _utc_iso())
            _speichern(personen)
            logger.info("Person aktualisiert: %s", name)
            return dict(vorhanden)

        neu = {
            "name": name,
            "rolle": rolle.strip(),
            "beziehung": beziehung.strip(),
            "beschreibung": beschreibung.strip(),
            "referenz_bild_pfad": referenz_bild_pfad.strip(),
            "referenz_bild_miniatur": miniature,
            "embedding": embedding,
            "gelernt_am": _utc_iso(),
            "referenzen": _refs_bereinigen(referenzen) if referenzen else None,
        }
        personen.append(neu)
        _speichern(personen)
        logger.info("Neue Person gelernt: %s", name)
        return dict(neu)


def _ref_id(embedding) -> str:
    """Stabile ID einer Referenz aus ihrem Embedding (ggf. + bbox-Hash)."""
    try:
        import hashlib
        roh = json.dumps((embedding or [])[:32], ensure_ascii=False).encode("utf-8", "ignore")
        return hashlib.sha1(roh).hexdigest()[:12]
    except Exception:
        return "ref"


def _refs_of(p: dict) -> list:
    """Normale Referenz-Liste ({embedding, jahr}) einer Person."""
    refs = []
    e = p.get("embedding")
    if e:
        if isinstance(e[0], (int, float)):
            refs.append({"embedding": e, "jahr": None})
        else:
            refs.extend({"embedding": x, "jahr": None} for x in e if x)
    for r in (p.get("referenzen") or []):
        if isinstance(r, dict) and r.get("embedding"):
            refs.append({"embedding": r["embedding"], "jahr": r.get("jahr")})
    return refs


def referenzen_auflisten() -> dict:
    """Je Person die Referenzen mit ref_id + Jahr + Miniatur-DataURL."""
    personen = liste_personen()
    erg = []
    for p in personen:
        refs = _refs_of(p)
        eintraege = []
        for idx, r in enumerate(refs):
            eintraege.append({
                "ref_id": _ref_id(r.get("embedding")),
                "index": idx,
                "jahr": r.get("jahr"),
                "bild_pfad": r.get("bild_pfad", ""),   # Ursprungsbild (falls vorhanden)
            })
        erg.append({
            "name": p.get("name"),
            "rolle": p.get("rolle", ""),
            "anzahl": len(refs),
            "miniatur": p.get("referenz_bild_miniatur", ""),
            "referenzen": eintraege,
        })
    return {"personen": erg}


def referenz_entfernen(name: str, ref_id: str) -> dict:
    """Loescht genau eine Referenz (ref_id) der Person. Beh aelt die Person."""
    ziel = ((name or "").strip().lower(), (ref_id or "").strip())
    if not all(ziel):
        return {"ok": False, "fehler": "person/ref_id leer"}
    name_lower, rid = ziel
    with _sperre:
        personen = _laden()
        p = next((x for x in personen if (x.get("name") or "").strip().lower() == name_lower), None)
        if p is None:
            return {"ok": False, "fehler": "person nicht gefunden"}
        refs = _refs_of(p)
        rest = [r for r in refs if _ref_id(r.get("embedding")) != rid]
        if len(rest) == len(refs):
            return {"ok": False, "fehler": "referenz nicht gefunden"}
        # aktualisieren: referenzen + embedding konsistent.
        p["referenzen"] = _refs_bereinigen(rest)
        emb = _refs_bereinigen(rest)
        p["embedding"] = [r["embedding"] for r in emb] if emb else None
        _speichern(personen)
        return {"ok": True, "name": p.get("name"), "verbleibend": len(rest)}


def person_entfernen(name: str) -> bool:
    """Löscht eine Person nach Name. True, wenn sie existierte."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return False
    with _sperre:
        personen = _laden()
        rest = [
            p for p in personen
            if (p.get("name") or "").strip().lower() != ziel
        ]
        if len(rest) == len(personen):
            return False
        _speichern(rest)
        logger.info("Person entfernt: %s", name)
        return True


def katalog_kontext() -> str:
    """Baut den Kontext-Block für den System-/User-Prompt.

    Wandert in den LLM-Prompt, sobald ein Foto analysiert wird, damit der
    Agent bekannte Personen auf dem Bild benennen statt erraten kann. Leer,
    wenn noch niemand gelernt wurde.
    """
    personen = liste_personen()
    if not personen:
        return ""
    zeilen = []
    for p in personen:
        teile = [p.get("name", "")]
        if p.get("rolle"):
            teile.append(p["rolle"])
        if p.get("beschreibung"):
            teile.append(p["beschreibung"])
        if p.get("beziehung"):
            teile.append(p["beziehung"])
        zeilen.append(" / ".join(teile))
    return (
        "\n\n[GELERNTE PERSONEN (Gesichter-Katalog) — nutze diese Infos, wenn "
        f"du Personen auf einem Bild erkennst:\n- " + "\n- ".join(zeilen) + "]"
    )


def referenz_bilder() -> List[dict]:
    """Die eingebetteten Referenz-Miniaturen als Bild-Files für den Vision-LLM.

    Liefert eine Liste von {"type": "image", "data_url": ..., "person": name}
    genau für die Personen, die eine gespeicherte Miniatur haben. Dem
    Vision-LLM mitgegeben, kann er ein aktuelles Foto gegen die bekannten
    Referenzgesichter abgleichen statt nur über Text-Beschreibung zu raten.
    """
    personen = liste_personen()
    bilder = []
    for p in personen:
        mini = (p.get("referenz_bild_miniatur") or "").strip()
        if mini and mini.startswith("data:image"):
            bilder.append({
                "type": "image",
                "data_url": mini,
                "person": p.get("name", ""),
                "pfad": p.get("referenz_bild_pfad", ""),
            })
    return bilder