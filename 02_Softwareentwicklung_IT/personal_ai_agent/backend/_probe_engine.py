"""Ping + Timing der Face-Engine an ein paar echten Galerie-Fotos."""
import os, sys, glob, time
sys.path.insert(0, "/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/backend")
from app.services import face_service

def main():
    print("verfuegbar:", face_service.verfuegbar())
    # ein paar Galerie-Fotos zum Test
    kandid = sorted(glob.glob(os.path.expanduser("~/storage/dcim/Lieblingsbilder/*.jpg")))[:3]
    if not kandid:
        kandid = sorted(glob.glob(os.path.expanduser("~/storage/dcim/Camera/*.jpg")))[:3]
    print("Teste", len(kandid), "Fotos")
    for p in kandid:
        t0 = time.time()
        ges = face_service.embeddings_fuer_pfad(p)
        dt = time.time() - t0
        print(f"{os.path.basename(p)}: {len(ges)} gesicht(er), {dt:.2f}s")
    print("Katalog:")
    for per in face_service.gesichter_service.liste_personen():
        print("  ", per.get("name"), "->", len(per.get("embedding") or []), "embedding(s)")

if __name__ == "__main__":
    main()