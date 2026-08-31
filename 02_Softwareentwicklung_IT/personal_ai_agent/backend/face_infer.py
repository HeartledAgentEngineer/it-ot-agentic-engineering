#!/usr/bin/env python3
"""Face-Inferenz (in Debian/proot) fuer personal_ai_agent.

Wird von der Termux-FastAPI-App als Subprozess aufgerufen
(proot-distro login debian -- /root/facy_venv/bin/python src/face_infer.py).
Liest eine JSON-Anweisung von stdin, fuehrt Detektion (YuNet) + Embedding
(SFace/OpenCV FaceRecognizerSF) aus und schreibt das Ergebnis als JSON auf
stdout.

Zwei Operationen:
  {"op":"embed","bild_base64":"...","max_faces":N}
      -> liefert fuer das/die erkannte/n Gesicht/er je {bbox, landm, embedding:[...]}
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
    # OpenCV liefert Landmarken relativ zum Bild; wir nutzen den eingebauten
    # Aligner, der konsistent zum Modell-Training ist.
    det, rec = _lazy_load()
    # Landmarken Shape: (5,2). FaceRecognizerSF muellt alignCrop ueber den
    # Rec-Objekts-Modus, der selbst die Landmarken hat.
    return rec.alignCrop(img_bgr, landm.astype(np.float32))


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
    else:
        print(json.dumps({"ok": False, "fehler": f"unbekannte op: {op}"}))


if __name__ == "__main__":
    main()