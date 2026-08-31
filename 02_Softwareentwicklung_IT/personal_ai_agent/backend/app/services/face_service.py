"""Embedding-basierte Gesichts-Erkennung via Debian/proot (real, unterstützt
Zwillings-Unterscheidung).

Die eigentliche Inferenz (Detektion YuNet + Embedding SFace) laeuft in einer
proot-Debian-Distro, weil onnxruntime/opencv auf purem Termux nicht tragbar
sind. Dieser Service kuemmert sich um:
  - Aufruf von `face_infer.py` (Subprozess, JSON/stdin-stdout) mit Timeout
  - Cosinus-Abstand zwischen neuem Embedding und gespeicherten Referenzen
  - enge Schwelle + Ehrlichkeits-Klausel, damit nicht "Julian" fuer Sebastian
    geraten wird, wenn die Abstaende zu aehnlich sind.

Persistenz: Embeddings liegen bei den Personen im Katalog
(`gesichter_katalog.json`, Feld `embedding`, 128-dim float list).
"""

import base64
import json
import logging
import os
import subprocess
import time
from typing import List, Optional

from app.services import gesichter_service

logger = logging.getLogger(__name__)

# Debian-Inferenz frisch (kein Caching des Prozesses -> robust, vermeidet
# haengende Subprozesse). Ein Aufruf kostet nur wenige 100ms.
_DEBIAN_PY = "/root/facy_venv/bin/python"
_DEBIAN_SCRIPT = "/root/app/face_infer.py"
_COMMAND = ["proot-distro", "login", "debian", "--", "bash", "-lc",
            f"{_DEBIAN_PY} {_DEBIAN_SCRIPT}"]
_INFER_TIMEOUT_S = 30

# Cosinus-Distanz-Schwellen (SFace/OpenCV). Anpassung an REALE Messdaten
# dieses Katalogs (2026-08-31): Dieselbe Person über zwei verschiedene Fotos
# hatte hier Distanzen von ~0.36-0.40, VERSCHIEDENE Personen (Sebastian vs
# Julian, Zwillingsbrüder) ~0.57-0.97. Die früheren, aus der Literatur
# übernommenen Schwellen (0.12/0.25) waren VIEL zu strikt und hätten jede
# echte Erkennung abgelehnt.
#   _SCHWELLE_JA:    Distanz darunter = sichere Erkennung (gleiche Person)
#   _SCHWELLE_UNSICHER: bis hierher "ähnlich (unsicher, nicht raten)"; darüber = andere
_SCHWELLE_JA = 0.45
_SCHWELLE_UNSICHER = 0.58

# Einmal gecacht: pruefen, ob die Face-Engine ueberhaupt verfuegbar ist.
_verfuegbar_cache: Optional[bool] = None


def verfuegbar() -> bool:
    """True, wenn die Debian-Face-Engine antwortet (embeddings moeglich)."""
    global _verfuegbar_cache
    if _verfuegbar_cache is not None:
        return _verfuegbar_cache
    try:
        r = subprocess.run(
            _COMMAND + ["-c", ""],
            input=json.dumps({"op": "ping"}),
            capture_output=True,
            text=True,
            timeout=20,
        )
        out = (r.stdout or "").strip()
        _verfuegbar_cache = '"ok": true' in out
    except Exception as e:
        logger.warning("Face-Engine (Debian) nicht verfuegbar: %s", e)
        _verfuegbar_cache = False
    if not _verfuegbar_cache:
        logger.info("Gesichts-Embedding-Erkennung deaktiviert (kein Debian/proot).")
    return _verfuegbar_cache


def _infer(payload: dict) -> dict:
    """Fuehrt einen Inferenz-Aufruf im Debian-Subprozess aus und liefert dict."""
    if not verfuegbar():
        return {"ok": False, "fehler": "face-engine nicht verfuegbar"}
    try:
        r = subprocess.run(
            _COMMAND,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=_INFER_TIMEOUT_S,
        )
        out = (r.stdout or "").strip()
        # Nur die letzte JSON-Zeile nehmen (proot-Warnungen koennen vorn stehen).
        zeilen = [z for z in out.splitlines() if z.startswith("{")]
        if not zeilen:
            return {"ok": False, "fehler": "keine JSON-Ausgabe: " + out[-400:]}
        return json.loads(zeilen[-1])
    except subprocess.TimeoutExpired:
        return {"ok": False, "fehler": "timeout"}
    except Exception as e:
        return {"ok": False, "fehler": str(e)}


# ---------------------------------------------------------------------------
# Public-API für den Chat-Flow
# ---------------------------------------------------------------------------

def embeddings_fuer_pfad(pfad: str) -> List[dict]:
    """Liest ein Bild (Pfad) und liefert die erkannten Gesichter samt Embedding.

    Returns: Liste von {"bbox", "score", "embedding":[...]} - leer, wenn kein
    Gesicht gefunden oder Engine nicht verfügbar.
    """
    try:
        with open(pfad, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception as e:
        logger.warning("Bild nicht lesbar fuer Gesichts-Erkennung: %s", e)
        return []
    if not b64:
        return []
    res = _infer({"op": "embed", "bild_base64": b64, "max_faces": 4})
    if not res.get("ok"):
        logger.warning("Gesichts-Erkennung fehlgeschlagen: %s", res.get("fehler"))
        return []
    return res.get("gesichter", [])


def _cosinus_distanz(a: List[float], b: List[float]) -> Optional[float]:
    """1 - cos; None bei ungueltigen Vektoren."""
    try:
        import numpy as np
        va = np.asarray(a, dtype=np.float64)
        vb = np.asarray(b, dtype=np.float64)
        if va.shape != vb.shape or va.size == 0:
            return None
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return None
        return float(1.0 - np.dot(va, vb) / (na * nb))
    except Exception:
        return None


def erkenne_personen(embedding: List[float]) -> List[dict]:
    """Vergleicht ein Embedding gegen alle Katalog-Referenzen.

    Returns: sortierte Liste [{"name","rolle","distanz","sicher":bool}] —
    nur Eintraege unter _SCHWELLE_UNSICHER. Liegt keiner unter _SCHWELLE_JA,
    wird die naechste benannt, aber als "unsicher" markiert (Ehrlichkeit) —
    so wird bei Zwillingen nicht blind geraten.
    """
    if not embedding:
        return []
    kandidaten = []
    for p in gesichter_service.liste_personen():
        refs = p.get("embedding")
        if not refs:
            continue
        # refs kann EINE 128-dim Liste sein ODER eine Liste davon (mehrere
        # Referenzbilder je Person). Normalisieren zu einer Liste von Vektoren.
        if refs and isinstance(refs[0], (int, float)):
            refs = [refs]
        beste_d = None
        for ref in refs:
            d = _cosinus_distanz(embedding, ref)
            if d is None:
                continue
            if beste_d is None or d < beste_d:
                beste_d = d
        if beste_d is None:
            continue
        kandidaten.append({
            "name": p.get("name", "?"),
            "rolle": p.get("rolle", ""),
            "distanz": round(beste_d, 4),
            "sicher": beste_d <= _SCHWELLE_JA,
        })
    kandidaten.sort(key=lambda k: k["distanz"])
    # Nur nahe genug lieferbare Kandidaten zurückgeben.
    ergebnis = [k for k in kandidaten if k["distanz"] <= _SCHWELLE_UNSICHER]
    return ergebnis


def erkenne_bild_pfad(pfad: str) -> dict:
    """Komfort-Wrapper: Bild -> erkennbare Personen als {'personen':[...]}."""
    if not verfuegbar():
        return {"verfuegbar": False, "personen": []}
    if not pfad or not os.path.exists(pfad):
        return {"verfuegbar": True, "personen": [], "hinweis": "Bild nicht gefunden"}
    alle = []
    for gesicht in embeddings_fuer_pfad(pfad):
        emb = gesicht.get("embedding")
        if not emb:
            continue
        treffer = erkenne_personen(emb)
        alle.append({"gesicht_bbox": gesicht.get("bbox"),
                     "treffer": treffer})
    return {"verfuegbar": True, "personen": alle}