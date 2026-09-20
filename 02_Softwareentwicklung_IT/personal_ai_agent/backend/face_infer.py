#!/usr/bin/env python3
"""Face-Inferenz (in Debian/proot) fuer personal_ai_agent.

Wird von der Termux-FastAPI-App als Subprozess aufgerufen
(proot-distro login debian -- /root/facy_venv/bin/python src/face_infer.py).
Liest eine JSON-Anweisung von stdin, fuehrt Detektion (YuNet) + Embedding
(SFace/OpenCV FaceRecognizerSF) aus und schreibt das Ergebnis als JSON auf
stdout.

Drei Operationen:
  {"op":"embed","bild_base64":"...","max_faces":N}
      -> liefert fuer das/die erkannte/n Gesicht/er je {bbox, landm, embedding:[...]}
  {"op":"embed_crop","bild_base64":"...","bbox":[x,y,w,h]}
      -> liefert EIN Embedding fuer ein selbst gezeichnetes Rechteck (bbox in
         ABSOLUTEN Pixeln). Ermoeglicht das Anlernen einer Person, die YuNet
         nicht (richtig) erkannt hat.
  {"op":"ping"}
      -> {"ok":true,"version":...} (Verfuegbarkeits-/Health-Check)

Embedding ist 128-dim float32 (SFace). Zur Zwillings-Unterscheidung vergleicht
der Aufrufer Cosinus-Ähnlichkeit mit enger Schwelle.
"""
import sys
import json
import base64
import time

import numpy as np

# cv2 wird BEWUSST erst in den Funktionen importiert (lazy): So bleibt dieses
# Modul auch ohne installiertes OpenCV importierbar — die reine EXIF-/Bild-
# Logik (exif_orientierung/orientiere_bild) ist damit testbar (Fix 2026-09-15).

MODEL_BASE = "/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/ml_models"
DET_MODEL = MODEL_BASE + "/face_detection_yunet_2023mar.onnx"
REC_MODEL = MODEL_BASE + "/face_recognition_sface_2021dec.onnx"

SCORE_THR = 0.6
NMS_THR = 0.3
TOPK = 5000
REC_SIZE = 112  # SFace erwartet 112x112

_det = None
_rec = None


# ---------------------------------------------------------------------------
# EXIF-Orientierung (Fix 2026-09-15)
# ---------------------------------------------------------------------------
# Befund Sebastian: "die Kästen sind zu groß / verschieben sich beim Öffnen und
# Drehen". Ursache: Das Backend backt die EXIF-Drehung in die anzeigbare
# data_url ein (datei_suche.lese_datei_info -> ImageOps.exif_transpose), YuNet
# bekam das Bild aber UNGEDREHT (cv2.imdecode ignoriert EXIF). Damit lag die
# bbox in einem anderen Koordinatenraum als das angezeigte Bild (90°-Faelle
# sogar mit vertauschten Seiten -> "viel zu groß"). Hier wird das Bild VOR der
# Detektion identisch zur Anzeige orientiert.

def exif_orientierung(roh: bytes) -> int:
    """Liest den EXIF-Orientierungs-Tag (274) aus JPEG-Bytes. 1 = normal.

    Reine Bytes-Arbeit (kein PIL/cv2) -> ohne Bildabhaengigkeiten testbar.
    """
    try:
        if len(roh) < 4 or roh[0:2] != b"\xff\xd8":   # kein JPEG
            return 1
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
            seg_len = int.from_bytes(roh[i + 2:i + 4], "big")
            if seg_len < 2:
                return 1
            if marker == 0xE1 and roh[i + 4:i + 10] == b"Exif\x00\x00":
                tiff = i + 10
                if roh[tiff:tiff + 2] == b"II":
                    endian = "little"
                elif roh[tiff:tiff + 2] == b"MM":
                    endian = "big"
                else:
                    return 1
                off = int.from_bytes(roh[tiff + 4:tiff + 8], endian)
                ifd = tiff + off
                if ifd + 2 > n:
                    return 1
                anzahl = int.from_bytes(roh[ifd:ifd + 2], endian)
                for k in range(anzahl):
                    e = ifd + 2 + k * 12
                    if e + 10 > n:
                        return 1
                    tag = int.from_bytes(roh[e:e + 2], endian)
                    if tag == 274:
                        wert = int.from_bytes(roh[e + 8:e + 10], endian)
                        return wert if 1 <= wert <= 8 else 1
                return 1
            i += 2 + seg_len
    except Exception:
        return 1
    return 1


def orientiere_bild(img, roh: bytes):
    """Wendet die EXIF-Orientierung auf das (BGR-)Bildarray an — identisch zur
    Anzeige-Drehung des Frontends. numpy-only (kein cv2) -> testbar."""
    o = exif_orientierung(roh)
    if o == 1:
        return img
    try:
        if o == 2:
            return img[:, ::-1]
        if o == 3:
            return img[::-1, ::-1]
        if o == 4:
            return img[::-1, :]
        if o == 5:                       # transpose
            return np.rot90(img[:, ::-1], k=-1)
        if o == 6:                       # 90° im Uhrzeigersinn
            return np.rot90(img, k=-1)
        if o == 7:                       # transverse
            return np.rot90(img[:, ::-1], k=1)
        if o == 8:                       # 90° gegen den Uhrzeigersinn
            return np.rot90(img, k=1)
    except Exception:
        return img
    return img


def dekodiere_bild(roh: bytes):
    """JPEG/PNG-Bytes -> BGR-Array, EXIF-orientiert wie im Frontend."""
    import cv2
    arr = np.frombuffer(roh, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return orientiere_bild(img, roh)


def _lazy_load():
    import cv2
    global _det, _rec
    if _det is None:
        _det = cv2.FaceDetectorYN.create(DET_MODEL, "", (320, 320), SCORE_THR, NMS_THR, TOPK)
    if _rec is None:
        _rec = cv2.FaceRecognizerSF.create(REC_MODEL, "")
    return _det, _rec


def _align_face(img_bgr, bbox, landm) -> np.ndarray:
    """Schneidet das Gesicht anhand der 5 Landmarken raus und aligniert es auf
    112x112 (SFace-Vorverarbeitung entspricht dem OpenCV AlignCrop)."""
    det, rec = _lazy_load()
    return rec.alignCrop(img_bgr, landm.astype(np.float32))


def _embed_crop_pixels(img, bbox):
    """Erzeugt ein SFace-Embedding fuer einen selbst gezeichneten Ausschnitt.

    bbox: [x, y, w, h] in ABSOLUTEN Pixeln relativ zum vollen Bild. Es wird
    zuerst versucht, im Ausschnitt das Gesicht + Landmarken zu finden (genaue
    alignCrop-Embedding); schlaegt das fehl, wird der Quadrat-Crop auf 112x112
    skaliert und direkt eingebettet (Fallback). Liefert None, wenn nichts
    brauchbares entsteht.
    """
    h, w = img.shape[:2]
    try:
        x = max(0, min(int(round(float(bbox[0]))), w - 1))
        y = max(0, min(int(round(float(bbox[1]))), h - 1))
        bw = max(4, min(int(round(float(bbox[2]))), w - x))
        bh = max(4, min(int(round(float(bbox[3]))), h - y))
    except (TypeError, ValueError, IndexError):
        return None
    crop = img[y:y + bh, x:x + bw]
    import cv2
    det, rec = _lazy_load()
    emb = None
    # 1) Gesicht + Landmarken im Ausschnitt suchen -> genaue alignCrop-Embedding.
    try:
        det.setInputSize((crop.shape[1], crop.shape[0]))
        ok, faces = det.detect(crop)
        if faces is not None and len(faces) > 0:
            f = faces[0]
            landm = f[4:14].reshape(-1, 2).astype(np.float32)
            aligned = rec.alignCrop(crop, landm)
            emb = rec.feature(aligned)
    except Exception:
        emb = None
    # 2) Fallback: Quadrat-Crop auf 112x112 skalieren und direkt einbetten.
    if emb is None:
        try:
            sq = crop
            s = min(sq.shape[0], sq.shape[1])
            if s > 0:
                sq = sq[0:s, 0:s]
            sq = cv2.resize(sq, (REC_SIZE, REC_SIZE), interpolation=cv2.INTER_AREA)
            emb = rec.feature(sq)
        except Exception:
            emb = None
    if emb is None:
        return None
    return emb[0]


def op_embed(payload: dict) -> dict:
    det, rec = _lazy_load()
    b64 = payload.get("bild_base64", "")
    try:
        roh = base64.b64decode(b64)
        # EXIF-orientiert dekodieren: die bbox liegt damit im SELBEN Raum wie das
        # im Frontend angezeigte (ebenfalls EXIF-gedrehte) Bild.
        img = dekodiere_bild(roh)
    except Exception as e:
        return {"ok": False, "fehler": f"decode: {e}"}
    if img is None:
        return {"ok": False, "fehler": "bild nicht decodierbar"}

    h, w = img.shape[:2]
    det.setInputSize((w, h))
    ok, faces = det.detect(img)
    if faces is None or len(faces) == 0:
        return {"ok": True, "gesichter": []}

    max_faces = int(payload.get("max_faces", 0)) or len(faces)
    ergebnis = []
    for i, f in enumerate(faces[:max_faces]):
        # f: [x,y,w,h, ... 5 landmarks (10 werte), score]
        xywh = f[:4]
        score = float(f[-1])
        landm = f[4:14].reshape(-1, 2).astype(np.float32)
        try:
            crop = rec.alignCrop(img, landm)
            emb = rec.feature(crop)  # (1,128) float32
            ergebnis.append({
                "bbox": [float(v) for v in xywh],
                "score": score,
                "landm": [[float(a), float(b)] for a, b in landm],
                "embedding": [float(v) for v in emb[0]],
            })
        except Exception as e:
            ergebnis.append({"bbox": [float(v) for v in xywh], "score": score,
                             "fehler": str(e)})
    return {"ok": True, "gesichter": ergebnis}


def op_embed_crop(payload: dict) -> dict:
    """Embedding fuer EIN selbst gezeichnetes Rechteck (bbox) — nicht fuer die
    YuNet-Autodetektion. Damit kann das Quiz eine Person auch dann anlernen,
    wenn YuNet das Gesicht nicht (richtig) erkannt hat (Wunsch Sebastian:
    'Rahmen um nicht automatisch erkannte Personen ergaenzen').

    bbox ist in ABSOLUTEN Pixeln relativ zum vollen Bild: [x, y, w, h].
    """
    b64 = payload.get("bild_base64", "")
    bbox = payload.get("bbox") or []
    if len(bbox) < 4:
        return {"ok": False, "fehler": "bbox fehlt"}
    try:
        roh = base64.b64decode(b64)
        img = dekodiere_bild(roh)
    except Exception as e:
        return {"ok": False, "fehler": f"decode: {e}"}
    if img is None:
        return {"ok": False, "fehler": "bild nicht decodierbar"}
    try:
        emb = _embed_crop_pixels(img, bbox)
    except Exception as e:
        return {"ok": False, "fehler": str(e)}
    if emb is None:
        return {"ok": False, "fehler": "kein Gesicht im Ausschnitt"}
    return {"ok": True, "embedding": [float(v) for v in emb],
            "bbox": [float(v) for v in bbox]}


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
    except Exception as e:
        print(json.dumps({"ok": False, "fehler": f"stdin: {e}"}))
        return

    op = payload.get("op")
    if op == "ping":
        import cv2
        print(json.dumps({"ok": True, "version": cv2.__version__,
                          "detektor": "yunet", "rec": "sface"}))
    elif op == "embed":
        print(json.dumps(op_embed(payload)))
    elif op == "embed_crop":
        print(json.dumps(op_embed_crop(payload)))
    else:
        print(json.dumps({"ok": False, "fehler": f"unbekannte op: {op}"}))


if __name__ == "__main__":
    main()