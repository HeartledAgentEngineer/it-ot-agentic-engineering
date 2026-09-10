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

import cv2
import numpy as np

MODEL_BASE = "/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/ml_models"
DET_MODEL = MODEL_BASE + "/face_detection_yunet_2023mar.onnx"
REC_MODEL = MODEL_BASE + "/face_recognition_sface_2021dec.onnx"

SCORE_THR = 0.6
NMS_THR = 0.3
TOPK = 5000
REC_SIZE = 112  # SFace erwartet 112x112

_det = None
_rec = None


def _lazy_load():
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
        arr = np.frombuffer(roh, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
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
        arr = np.frombuffer(roh, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
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