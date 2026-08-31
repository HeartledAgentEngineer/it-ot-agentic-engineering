"""Trains den Gesichter-Katalog aus den heute (22:58–23:12) bestätigten Bildern.

Sebastian-Zuordnung (von ihm bestätigt):
- 5305de8b69d7.jpg, 065e8490a052.jpg: 2 junge Männer -> LINKS g0 = Sebastian,
  RECHTS g1 = Julian (nach bbox-x sortiert).
- 7afaa721e715.jpg: 1 – Oma Helga Jacobs.
- 8b102eb2e7f4.jpg: 2 – vorne links = Sebastian, hinten rechts = Oma (per
  Vision beschrieben). Hier wird Oma gelernt (hinten/rechts) – für Sebastian
  nicht nötig, da in 5305/065e bereits vorhanden.

Es wird NUR das Embedding je Person gespeichert (referenz_bild_miniatur bleibt,
sofern vorhanden). Mehrere Referenz-Embeddings je Person werden als Liste
gespeichert (bessere Robustheit gegen Winkel/Licht).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services import face_service  # noqa: E402
from app.services import gesichter_service  # noqa: E402

BASE = "/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/"


def _nach_x_sortieren(gesichter: list) -> list:
    """Gesichter nach Bounding-Box-x aufsteigend sortieren (links zuerst)."""
    def _x(g):
        b = g.get("bbox") or [0, 0, 0, 0]
        return float(b[0])
    return sorted(gesichter, key=_x)


def _embedding_aus(gesichter: list, index: int):
    if 0 <= index < len(gesichter):
        return gesichter[index].get("embedding")
    return None


def main():
    if not face_service.verfuegbar():
        print("Face-Engine nicht verfügbar – Stopp.")
        return

    # 1) Sebastian: links (g0) in den zwei Zwillings-Bildern
    sebastian_embs = []
    for rel in ["uploads/5305de8b69d7.jpg", "uploads/065e8490a052.jpg"]:
        ges = _nach_x_sortieren(face_service.embeddings_fuer_pfad(BASE + rel))
        e = _embedding_aus(ges, 0)
        if e:
            sebastian_embs.append(e)
            print(f"Sebastian aus {rel}: links-embedding ok ({len(e)} dims)")

    # 2) Julian: rechts (g1) in denselben Bildern
    julian_embs = []
    for rel in ["uploads/5305de8b69d7.jpg", "uploads/065e8490a052.jpg"]:
        ges = _nach_x_sortieren(face_service.embeddings_fuer_pfad(BASE + rel))
        e = _embedding_aus(ges, 1)
        if e:
            julian_embs.append(e)
            print(f"Julian aus {rel}: rechts-embedding ok ({len(e)} dims)")

    # 3) Oma Helga: Einzelbild
    helga_embs = []
    ges_helga = _nach_x_sortieren(
        face_service.embeddings_fuer_pfad(BASE + "uploads/7afaa721e715.jpg"))
    e = _embedding_aus(ges_helga, 0)
    if e:
        helga_embs.append(e)
        print(f"Oma aus 7afaa721e715: embedding ok ({len(e)} dims)")

    # Personen speichern (Upsert) – Embedding als Liste ablegen
    if sebastian_embs:
        gesichter_service.person_speichern(
            name="Sebastian", rolle="Nutzer",
            beschreibung="Bestätigt: links auf Zwillings-Bildern",
            embedding=sebastian_embs)
        print("-> Sebastian gespeichert")

    if julian_embs:
        gesichter_service.person_speichern(
            name="Julian", rolle="Zwillingsbruder",
            beschreibung="Bestätigt: rechts auf Zwillings-Bildern",
            embedding=julian_embs)
        print("-> Julian gespeichert")

    if helga_embs:
        gesichter_service.person_speichern(
            name="Helga Jacobs", rolle="Oma",
            beschreibung="Einzelbild 7afaa721e715",
            embedding=helga_embs)
        print("-> Helga Jacobs gespeichert")

    print("\nKatalog:")
    for p in gesichter_service.liste_personen():
        n = len(p.get("embedding") or [])
        print(f"  {p.get('name')}: {n} embedding(s)")

if __name__ == "__main__":
    main()