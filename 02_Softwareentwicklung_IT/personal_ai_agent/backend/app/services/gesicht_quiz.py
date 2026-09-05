"""Gesichtserkennungs-Quiz (spielerisch Anlernen ueber das Frontend).

Zeigt ein Lieblingsbild, fragt 'Wen siehst du?', speichert die Antwort als
zusaetzliches Referenz-Embedding der genannten Person. So lernt der Agent jede
Person ueber viele Bilder/Winkel/Entfernungen und auch auf Gruppenbildern sicher.

Prinzipien:
- Dominantes (groesstes) Gesicht als Referenz der genannten Person anreichern —
  kein erfundener Name, kein falsches Anreichern aller Gesichter bei Gruppenbild.
- 'Neue Person' -> wird angelegt.
"""
import glob
import logging
import os

logger = logging.getLogger(__name__)

LIEBLINGS_ORDNER = "/sdcard/DCIM/Lieblingsbilder"


def _alle_bilder():
    if not os.path.isdir(LIEBLINGS_ORDNER):
        return []
    dateien = []
    for e in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif"):
        dateien += glob.glob(os.path.join(LIEBLINGS_ORDNER, e))
    return sorted(dateien)


def _dominantes_gesicht(gesichter):
    beste, beste_gr = None, -1.0
    for g in gesichter:
        bbox = g.get("bbox") or []
        if len(bbox) >= 4:
            gr = float(bbox[2]) * float(bbox[3])
        else:
            gr = 0.0
        if gr > beste_gr:
            beste_gr, beste = gr, g
    return beste


def _refs_als_liste(embedding):
    """Normalisiert das Embedding-Feld einer Person zu einer Liste von Vektoren."""
    if not embedding:
        return []
    if isinstance(embedding[0], (int, float)):
        return [embedding]
    return embedding


def start_runde(ausgeschlossen=None):
    from app.services.datei_suche import lese_datei_info
    bilder = _alle_bilder()
    if not bilder:
        return {"keine": True, "hinweis": "Kein Lieblingsbilder-Ordner gefunden."}
    kandidat = None
    for b in bilder:
        if b not in (ausgeschlossen or []):
            kandidat = b
            break
    if not kandidat:
        kandidat = bilder[0]
    info = lese_datei_info(kandidat)
    return {
        "bild_pfad": kandidat,
        "name": info.get("name"),
        "data_url": info.get("data_url", ""),
        "ist_bild": bool(info.get("ist_bild")),
    }


def beantworte_runde(bild_pfad: str, person: str, ist_neu: bool, rolle: str = ""):
    from app.services import face_service, gesichter_service
    name = (person or "").strip()
    rolle = (rolle or "").strip()
    if not name:
        return {"ok": False, "fehler": "keine Person angegeben"}
    if not bild_pfad or not os.path.exists(bild_pfad):
        return {"ok": False, "fehler": "Bild nicht gefunden"}

    gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
    if not gesichter:
        return {"ok": False, "fehler": "kein Gesicht im Bild erkannt"}
    dom = _dominantes_gesicht(gesichter)
    if not dom or not dom.get("embedding"):
        return {"ok": False, "fehler": "kein brauchbares Gesicht"}

    neu = False
    vorhanden = None
    for p in gesichter_service.liste_personen():
        if (p.get("name") or "").strip().lower() == name.lower():
            vorhanden = p
            break

    if vorhanden is None:
        neue_emb = dom["embedding"]
        gesichter_service.person_speichern(name=name, rolle=rolle, embedding=neue_emb)
        neu = True
        referenzen = 1
    else:
        basis = {
            "name": name,
            "rolle": rolle or vorhanden.get("rolle", ""),
            "beziehung": vorhanden.get("beziehung", ""),
            "beschreibung": vorhanden.get("beschreibung", ""),
            "referenz_bild_pfad": vorhanden.get("referenz_bild_pfad", ""),
            "referenz_bild_miniatur": vorhanden.get("referenz_bild_miniatur", ""),
        }
        refs = _refs_als_liste(vorhanden.get("embedding"))
        # Dedup/Eindeutigkeit: neue Ref nur anhaengen, wenn sie zu allen >0.05
        # distanziert ist (wirklich eigener Winkel), sonst ueberspringen.
        zu_alt = min((face_service._cosinus_distanz(dom["embedding"], r) for r in refs if r),
                     default=None)
        if zu_alt is None or zu_alt > 0.05:
            refs = refs + [dom["embedding"]]
            gesichter_service.person_speichern(**basis, embedding=refs)
        referenzen = len(refs)

    return {"ok": True, "person": name, "ist_neu": neu, "referenzen": referenzen}