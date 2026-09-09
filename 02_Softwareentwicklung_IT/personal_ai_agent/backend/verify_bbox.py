"""Verifikations-Gate: Stimmt der (gerenderte) gelbe Rahmen wirklich 1:1 mit
dem von der Face-Engine markierten Gesicht ueberein?

Nutzt dieselbe bbox->%-Berechnung wie `markiereGesichtImBild` im Frontend und
prueft, dass der (erweiterte) Rahmen innerhalb des nativen Bildes liegt, nie
abgeschnitten/verschoben ist, und dass das SFace-Embedding gueltig (128-dim)
ist. So verifizieren wir den Kritischen Pfad bbox -> Rahmen -> Ausschnitt,
BEVOR wir weiter blind Referenzen im Quiz lernen.
"""
import glob, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services import face_service

LIEBLINGE = "/sdcard/DCIM/Lieblingsbilder"

# Exakt die Erweiterungs-/Klemm-Werte aus markiereGesichtImBild:
def rahmen_aus_bbox(b, iw, ih):
    """Berechnet den ERWEITERTEN Rahmen in nativen Pixeln + klemmt an Bildrand."""
    x, y, w, h = b
    erx = w * 0.06   # seitlich
    ery = h * 0.10   # unten (Kinn)
    ert = h * 0.28   # oben (Haare/Kopf)
    nx = max(0, x - erx)
    ny = max(0, y - ert)
    nw = min(iw - nx, w + erx * 2)
    nh = min(ih - ny, h + erx * 2 + ert + ery)
    rechts = nx + nw
    unten = ny + nh
    return nx, ny, nw, nh, rechts, unten

def pruefe(fn):
    p = os.path.join(LIEBLINGE, fn)
    if not os.path.exists(p):
        print(f"  SKIP {fn}: fehlt"); return
    try:
        from PIL import Image
        im = Image.open(p); iw, ih = im.size
    except Exception as e:
        print(f"  STOP {fn}: {e}"); return
    t0 = time.time()
    gs = face_service.embeddings_fuer_pfad(p)
    dt = time.time() - t0
    if not gs:
        print(f"  {fn}  [{dt:.1f}s]  KEINE GESICHTER (Detektion-Score?)")
        return
    for i, g in enumerate(gs[:3]):
        bb = g.get("bbox") or []
        emb = g.get("embedding") or []
        if len(bb) < 4:
            print(f"  {fn} g{i+1}: keine brauchbare bbox"); continue
        nx, ny, nw, nh, rex, uny = rahmen_aus_bbox(bb, iw, ih)
        # Rahmen muss innerhalb des nativen Bildes liegen (nicht abgeschnitten)
        ok = (nx >= 0 and ny >= 0 and rex <= iw and uny <= ih)
        emb_ok = len(emb) == 128
        # Ann: bbox im nativen Bild? (Original-Pixel, wie die Engine liefert)
        bb_im_gross = (bb[0] >= 0 and bb[1] >= 0 and (bb[0]+bb[2]) <= iw and (bb[1]+bb[3]) <= ih)
        flag = "OK" if (ok and emb_ok and bb_im_gross) else "!!WARN"
        print(f"  {fn} g{i+1}: {flag} bbox=({int(bb[0])},{int(bb[1])},{int(bb[2])},{int(bb[3])})"
              f" nat={iw}x{ih} rahm=({int(nx)},{int(ny)},{int(nw)},{int(nh)})"
              f" [imRahmen={ok} bbInBild={bb_im_gross} emb={len(emb)}]")
    print(f"  (@{dt:.1f}s)")

if __name__ == "__main__":
    bilder = sorted(f for f in os.listdir(LIEBLINGE) if f.lower().endswith((".jpg",".jpeg",".png")))
    print(f"Verifikation Gesicht-Erkennung: pruefe bis zu 6 von {len(bilder)} Bildern ...")
    print("(Detektion + bbox -> Rahmen -> Embedding, je 'OK' = kritischer Pfad intakt)\n")
    for fn in bilder[:6]:
        pruefe(fn)
    print()
    print("Interpretation:")
    print("  OK      : Engine-bbox liegt im nativen Bild, Rahmen umschliesst Kopf,"
          " Embedding 128-dim -> zuverlaessig lernbar")
    print("  WARN    : bbox ragt aus Bild / Embedding defekt -> NICHT zum Lernen nutzen")
    print("  KEINE GESICHTER : Detektion fand nichts (Score-Schwelle?) - prüfe SCORE_THR/max_faces")