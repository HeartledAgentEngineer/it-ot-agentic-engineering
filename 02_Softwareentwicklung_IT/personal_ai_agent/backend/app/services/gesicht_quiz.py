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


def _hypothese(bild_pfad):
    """Stellt eine ML-Vermutung auf: welcher Katalog-Person das dominanteste
    Gesicht des Bildes am naechsten liegt (SFace-Cosinus) und wie sicher.

    Returns dict {person, sicherheit(hoch/mittel/niedrig|None), distanz} oder
    {person: None} wenn kein Gesicht/kein Katalog/kein plausibler Treffer.
    """
    try:
        from app.services import face_service, gesichter_service
        if not face_service.verfuegbar():
            return {"person": None}
        katalog = gesichter_service.liste_personen()
        if not katalog:
            return {"person": None}
        gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
        if not gesichter:
            return {"person": None}
        dom = _dominantes_gesicht(gesichter)
        if not dom or not dom.get("embedding"):
            return {"person": None}
        # Aufnahmejahr des Bildes (EXIF, Fallback mtime) fuer die Altersphasen-
        # Vermutung. Bei bekantem Jahr werden Personen mit Referenz in passender
        # Dekade leicht bevorzugt (weiche Priorisierung, kein Ausschluss).
        try:
            from app.services.datei_suche import _datei_jahr
            bild_jahr = _datei_jahr(bild_pfad)
        except Exception:
            bild_jahr = None
        emb = dom["embedding"]
        kandidaten = []
        for p in katalog:
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
            if not refs:
                continue
            beste_d = None
            naechstes_jahr_dist = None
            for r in refs:
                d = face_service._cosinus_distanz(emb, r["embedding"])
                if d is None:
                    continue
                if beste_d is None or d < beste_d:
                    beste_d = d
                if bild_jahr and r.get("jahr"):
                    abd = abs(r["jahr"] - bild_jahr)
                    if naechstes_jahr_dist is None or abd < naechstes_jahr_dist:
                        naechstes_jahr_dist = abd
            if beste_d is None:
                continue
            bonus = 0.0
            if bild_jahr and naechstes_jahr_dist is not None:
                if naechstes_jahr_dist <= 10:
                    bonus = -0.02
                elif naechstes_jahr_dist <= 25:
                    bonus = 0.0
                else:
                    bonus = 0.03
            kandidaten.append({"person": p.get("name"), "distanz": beste_d + bonus})
        if not kandidaten:
            return {"person": None}
        kandidaten.sort(key=lambda k: k["distanz"])
        best = kandidaten[0]
        d = best["distanz"]
        if d <= 0.45:
            sh = "hoch"
        elif d <= 0.58:
            sh = "mittel"
        else:
            sh = "niedrig"
        return {"person": best["person"], "sicherheit": sh, "distanz": round(d, 3)}
    except Exception:
        return {"person": None}


def _erkannte_personen_bildes(bild_pfad):
    """Erkennt ALLE Personen auf einem Bild (Gruppenbild-faehig).

    Liefert dict {anzahl_gesichter: int, erkannte: [names], unsicher: [names]}.
    Fuer jedes erkannte Gesicht wird erkenne_personen aufgerufen; sichere und
    unsichere Treffer werden getrennt gesammelt (Ehrlichkeit: keine erfundene
    Zuordnung bei unsicheren/kleinen Gesichtern).
    """
    try:
        from app.services import face_service, gesichter_service
        gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
        anzahl = len(gesichter)
        sicher, unsicher = [], []
        # bbox je Gesicht (relativ zur Bildgroesse) fuer das Markieren im Quiz.
        gesicht_boxen = []
        for i, g in enumerate(gesichter):
            emb = g.get("embedding")
            bbox = g.get("bbox") or []
            gesicht_boxen.append({"index": i, "bbox": bbox})
            if not emb:
                continue
            treffer = face_service.erkenne_personen(emb)
            for t in treffer:
                name = t.get("name")
                if not name:
                    continue
                if t.get("sicher") and name not in sicher:
                    sicher.append(name)
                elif not t.get("sicher") and name not in unsicher:
                    unsicher.append(name)
        return {"anzahl_gesichter": anzahl,
                "erkannte": sicher,
                "unsicher": unsicher,
                "gesichter": gesicht_boxen}
    except Exception:
        return {"anzahl_gesichter": 0, "erkannte": [], "unsicher": []}


def _fortschritt_pfad():
    from app.config import BASE_DIR
    return str(BASE_DIR / "quiz_fortschritt.json")


def _fortschritt_laden():
    try:
        import json as _j
        p = _fortschritt_pfad()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = _j.load(f)
            g = d.get("gesehen", []) if isinstance(d, dict) else []
            return [x for x in g if isinstance(x, str)]
    except Exception as e:
        logger.warning("Quiz-Fortschritt laden fehlgeschlagen: %s", e)
    return []


def _fortschritt_speichern(gesehen):
    try:
        import json as _j, time as _t
        p = _fortschritt_pfad()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _j.dump({"gesehen": gesehen[-2000:], "aktualisiert": _t.strftime("%Y-%m-%dT%H:%M:%S")}, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception as e:
        logger.warning("Quiz-Fortschritt speichern fehlgeschlagen: %s", e)


def markiere_uebersprungen(bild_pfad: str) -> dict:
    """Markiert ein Quiz-Bild als 'gesehen/uebersprungen' OHNE eine Person zu
    speichern. Wird genutzt, wenn auf dem Bild keine (relevante) Person ist.
    Haengt den Pfad an den persistenten Fortschritt, damit es nicht endlos
    erneut erscheint.
    """
    from app.services.datei_suche import lese_datei_info
    if not bild_pfad or not os.path.exists(bild_pfad):
        return {"ok": False, "fehler": "Bild nicht gefunden"}
    gesehen = _fortschritt_laden()
    if bild_pfad not in gesehen:
        gesehen = gesehen + [bild_pfad]
        _fortschritt_speichern(gesehen)
    info = lese_datei_info(bild_pfad)
    return {"ok": True, "uebersprungen": True, "name": info.get("name")}


def start_runde(ausgeschlossen=None):
    from app.services.datei_suche import lese_datei_info
    bilder = _alle_bilder()
    if not bilder:
        return {"keine": True, "hinweis": "Kein Lieblingsbilder-Ordner gefunden."}
    # Persistierter Fortschritt: bereits durchgespielte Bilder (ueber Neustart hinweg).
    gesehen_persist = _fortschritt_laden()
    aus = list(ausgeschlossen or [])
    kombiniert = []
    for g in (aus + gesehen_persist):
        if g and g not in kombiniert:
            kombiniert.append(g)
    # Nur Bilder mit >=1 erkanntem Gesicht sind zum Anlernen tauglich.
    # Gesichtslose Bilder werden uebersprungen (und als gesehen gemerkt, damit
    # sie nicht bei jedem start erneut per SFace geprueft werden).
    kandidat = None
    for b in bilder:
        if b in kombiniert:
            continue
        try:
            from app.services import face_service
            gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(b))
        except Exception:
            gesichter = []
        if gesichter:
            kandidat = b
            break
        else:
            kombiniert.append(b)  # gesichtslos -> nicht anlernbar, merken
    if not kandidat:
        return {
            "fertig": True,
            "gesamt": len(bilder),
            "verarbeitet": len(kombiniert),
            "hinweis": "Du hast alle Lieblingsbilder durchgespielt.",
        }
    # Bild NICHT beim Anzeigen als verbraucht markieren: Es wird erst nach
    # erfolgreicher Beantwortung persistent als 'gesehen' gespeichert
    # (in beantworte_runde). So bleibt eine pausierte/unbeantwortete Frage offen
    # und kommt beim 'fortsetzen' wieder - keine doppelten Bilder, aber auch
    # kein Verlust der aktuellen Frage.
    kombiniert.append(kandidat)  # nur fuer diesen Durchlauf (Auswahl), nicht persistiert
    # _fortschritt_speichern(kombiniert)  -> verschoben nach Beantwortung
    info = lese_datei_info(kandidat)
    runde = {
        "bild_pfad": kandidat,
        "name": info.get("name"),
        "data_url": info.get("data_url", ""),
        "ist_bild": bool(info.get("ist_bild")),
    }
    runde["vermutung"] = _hypothese(kandidat)
    # Gruppenbild-Erkennung: Anzahl Gesichter + welche Personen (von den
    # Bekannten) sicher/unsicher auf dem Bild sind -> Frontend fragt gezielt.
    _erk = _erkannte_personen_bildes(kandidat)
    runde["anzahl_gesichter"] = _erk.get("anzahl_gesichter", 0)
    runde["erkannte_personen"] = _erk.get("erkannte", [])
    runde["unsichere_personen"] = _erk.get("unsicher", [])
    runde["gesichter"] = _erk.get("gesichter", [])
    # Die offene Quiz-Frage dauerhaft in den Chat-Verlauf (conv_main) schreiben
    # (mit bild_pfad + Vermutung). So ist der Quiz-Zustand nach einem
    # Server-Neustart/Reload ZU 100% aus dem Chat rekonstruierbar: der Chat zeigt
    # die letzte gestellte Frage mit Bild, und der Fortschritt (quiz_fortschritt)
    # sagt, wo weiterzumachen ist. Append-only, mutiert nichts Bestehendes.
    try:
        from app.services.chat_verlauf import verlauf_nachricht_anhaengen
        v = runde.get("vermutung") or {}
        v_txt = ""
        if v.get("person"):
            v_txt = f" (Vermutung: {v.get('person')}, Sicherheit {v.get('sicherheit')})"
        frage_text = f"🗒 QUIZ-ANTWORTEN [QUIZ-OFFEN] — Wen siehst du auf diesem Bild?{v_txt}"
        # UI-Block serialisieren: ermoeglicht die verlustfreie Rekonstruktion
        # der interaktiven Quiz-Karte (Bild + Antwort-Optionen) nach Reload/
        # Server-Neustart. Generalisiertes Muster fuer interaktive Chat-Elemente.
        ui_block = {
            "typ": "quiz",
            "bild_pfad": runde.get("bild_pfad"),
            "name": runde.get("name"),
            "optionen": None,  # optionen setzt der Router (bekannte Personen)
            "vermutung": v if v.get("person") else None,
            "gesichter": runde.get("gesichter") or [],  # bbox je Gesicht fuer den Rahmen
            "offen": True,
        }
        verlauf_nachricht_anhaengen("conv_main", "assistant", frage_text,
                                    bild_pfad=runde.get("bild_pfad"), ui=ui_block)
    except Exception:
        pass
    return runde


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

    # Aufnahmejahr des Bildes fuer die Zeitstufen-Referenz (EXIF, Fallback mtime).
    try:
        from app.services.datei_suche import _datei_jahr
        jahr = _datei_jahr(bild_pfad)
    except Exception:
        jahr = None

    neue_ref = {"embedding": dom["embedding"], "jahr": jahr}
    if vorhanden is None:
        gesichter_service.person_speichern(name=name, rolle=rolle, referenzen=[neue_ref])
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
        # Bestehende zeitgestempelte Referenzen (neues Schema) ODER legacy
        # embedding-Feld zu {embedding, jahr}-Dicts normalisieren.
        bestehende = vorhanden.get("referenzen")
        if not bestehende:
            bestehende = [{"embedding": r, "jahr": None}
                          for r in _refs_als_liste(vorhanden.get("embedding"))]
        bestehende = [r for r in bestehende if isinstance(r, dict) and r.get("embedding")]
        refs_emb = [r["embedding"] for r in bestehende]
        zu_alt = min((face_service._cosinus_distanz(dom["embedding"], r) for r in refs_emb if r),
                     default=None)
        if zu_alt is None or zu_alt > 0.05:
            bestehende = bestehende + [neue_ref]
            gesichter_service.person_speichern(**basis, referenzen=bestehende)
        referenzen = len(bestehende)

    # Persistente Quiz-Notiz in den Chat-Verlauf (conv_main), mit Bild-Pfad,
    # damit das Quiz dauerhaft im Chat steht und spaeter wieder angesehen werden
    # kann (Append-only; fehlendes Original wird beim Anzeigen graceful gemeldet).
    try:
        from app.services.chat_verlauf import verlauf_nachricht_anhaengen
        rolle_txt = f" ({rolle})" if rolle else ""
        text = (f"[Gesichter-Quiz] '{name}'{rolle_txt} gelernt — "
                f"{referenzen} Referenz(en), Aufnahmejahr {jahr or '?'}. "
                f"[Bild gespeichert zum erneuten Ansehen]")
        verlauf_nachricht_anhaengen("conv_main", "assistant", text, bild_pfad=bild_pfad)
    except Exception:
        pass

    # Nach erfolgreicher Beantwortung das Bild als persistent 'gesehen' markieren
    # (erst jetzt verbraucht, nicht schon beim Anzeigen -> echtes Pausieren).
    try:
        gesehen = _fortschritt_laden()
        if bild_pfad not in gesehen:
            _fortschritt_speichern(gesehen + [bild_pfad])
    except Exception:
        pass

    return {"ok": True, "person": name, "ist_neu": neu, "referenzen": referenzen, "jahr": jahr}