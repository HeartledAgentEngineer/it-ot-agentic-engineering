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


def _gesichter_robust(bild_pfad: str) -> list:
    """Gesichts-Erkennung mit einem Wiederholungsversuch (Fix 2026-09-15).

    Die YuNet-Detektion ist auf Termux/proot bewusst wechselhaft: Ein Lauf kann
    0 Gesichter liefern, obwohl das Bild garantiert eins hat. Genau das machte
    das Quiz "mal so, mal so": eine Antwort ("Ja, das ist X") schlug sporadisch
    mit 'kein Gesicht im Bild erkannt' fehl, das Bild wurde NICHT als gesehen
    markiert und die Zuordnung startete beim naechsten Durchlauf von vorne.
    Deshalb: bei leerem Ergebnis EINEN zweiten Lauf versuchen.
    """
    from app.services import face_service
    gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
    if not gesichter:
        gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
    return gesichter


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


def _ueberlappung(a, b):
    """Intersection-over-Union zweier [x,y,w,h]-Boxen (float)."""
    try:
        ax, ay, aw, ah = float(a[0]), float(a[1]), float(a[2]), float(a[3])
        bx, by, bw, bh = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    except (TypeError, ValueError, IndexError):
        return 0.0
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _gesicht_zu_bbox(gesichter, bbox):
    """Waehlt das Gesicht, dessen bbox am staerksten mit der korrigierten
    ueberlappt (IoU). Fallback: dominantes Gesicht. Robust gegen instabile
    Gesichts-Reihenfolge zwischen zwei Erkennungslaeufen."""
    if not bbox or len(bbox) < 4:
        return _dominantes_gesicht(gesichter)
    best, best_iou = None, 0.0
    for g in gesichter:
        iou = _ueberlappung(g.get("bbox") or [], bbox)
        if iou > best_iou:
            best_iou, best = iou, g
    return best if best else _dominantes_gesicht(gesichter)


def _refs_als_liste(embedding):
    """Normalisiert das Embedding-Feld einer Person zu einer Liste von Vektoren."""
    if not embedding:
        return []
    if isinstance(embedding[0], (int, float)):
        return [embedding]
    return embedding


def _optionen_sortiert(bild_pfad):
    """Liefert alle Katalog-Namen sortiert nach Wahrscheinlichkeit (distanz:
    beste SFace-Cosinus-Distanz des dominanten Gesichts, + Alters-Bonus), der
    wahrscheinlichste zuerst. Wird genutzt, damit die Namens-Chips im Quiz nach
    der Vermutung sortiert erscheinen (Wunsch Sebastian: nach 'Nein' die
    wahrscheinlichste Reihenfolge).

    Returns Liste[str]. Fallback: Katalog-Reihenfolge, wenn kein Gesicht/keine
    Distanz berechenbar (dann ist jede Reihenfolge gleich).
    """
    try:
        from app.services import face_service, gesichter_service
        katalog = gesichter_service.liste_personen()
        if not katalog:
            return []
        if not face_service.verfuegbar():
            return [p.get("name") for p in katalog if p.get("name")]
        gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
        if not gesichter:
            return [p.get("name") for p in katalog if p.get("name")]
        dom = _dominantes_gesicht(gesichter)
        if not dom or not dom.get("embedding"):
            return [p.get("name") for p in katalog if p.get("name")]
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
                bonus = -0.02 if naechstes_jahr_dist <= 10 else (0.0 if naechstes_jahr_dist <= 25 else 0.03)
            kandidaten.append({"person": p.get("name"), "distanz": beste_d + bonus})
        kandidaten.sort(key=lambda k: k["distanz"])
        return [k["person"] for k in kandidaten if k.get("person")]
    except Exception:
        try:
            from app.services import gesichter_service
            return [p.get("name") for p in gesichter_service.liste_personen() if p.get("name")]
        except Exception:
            return []


def _hypothese(bild_pfad, gesichter=None):
    """Stellt eine ML-Vermutung auf: welcher Katalog-Person das dominanteste
    Gesicht des Bildes am naechsten liegt (SFace-Cosinus) und wie sicher.

    Returns dict {person, sicherheit(hoch/mittel/niedrig|None), distanz} oder
    {person: None} wenn kein Gesicht/kein Katalog/kein plausibler Treffer.

    `gesichter` kann VON AUSSEN uebergeben werden (die bereits berechnete
    Detektion). Dann entfaellt der zweite, unabhaengige Detektionslauf — der auf
    Termux sporadisch 0 Gesichter liefert und damit dieselbe Frage "mal mit
    Vermutung, mal ohne" beantwortete (Fix 2026-09-15).
    """
    try:
        from app.services import face_service, gesichter_service
        if not face_service.verfuegbar():
            return {"person": None}
        katalog = gesichter_service.liste_personen()
        if not katalog:
            return {"person": None}
        if gesichter is None:
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


def _erkannte_personen_bildes(bild_pfad, gesichter=None):
    """Erkennt ALLE Personen auf einem Bild (Gruppenbild-faehig).

    Liefert dict {anzahl_gesichter: int, erkannte: [names], unsicher: [names]}.
    Fuer jedes erkannte Gesicht wird erkenne_personen aufgerufen; sichere und
    unsichere Treffer werden getrennt gesammelt (Ehrlichkeit: keine erfundene
    Zuordnung bei unsicheren/kleinen Gesichtern).

    `gesichter` kann VON AUSSEN übergeben werden (die bei der Bild-Auswahl in
    start_runde bereits berechnete Gesichtsliste). Dann wird KEIN zweiter,
    unabhängiger Detektionslauf gemacht — auf Termux/proot ist die Detektion
    bewusst wechselhaft und ein zweiter Lauf kann 0 Gesichter liefern, obwohl
    das Bild (Lauf A) garantiert eins hat. Ohne Übergabe wird intern erkannt.
    """
    try:
        from app.services import face_service, gesichter_service
        if gesichter is None:
            gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
        anzahl = len(gesichter)
        sicher, unsicher = [], []
        # bbox je Gesicht (relativ zur Bildgroesse) fuer das Markieren im Quiz.
        gesicht_boxen = []
        for i, g in enumerate(gesichter):
            emb = g.get("embedding")
            bbox = g.get("bbox") or []
            # Pro Gesicht eine Vermutung ableiten: erst ein sicherer Treffer,
            # sonst der beste unsichere (Name + Sicherheitsstufe). So kann das
            # Frontend bei JEDEM Gesicht eine "Ist das X?"-Ja/Nein-Frage stellen,
            # statt nur die Namens-Chips zu zeigen.
            vermut = None
            if emb:
                try:
                    treffer = face_service.erkenne_personen(emb)
                except Exception:
                    treffer = []
                bester_unsicher = None
                for t in treffer:
                    name = t.get("name")
                    if not name:
                        continue
                    if t.get("sicher"):
                        vermut = {"person": name, "sicherheit": "hoch"}
                        break
                    if bester_unsicher is None:
                        bester_unsicher = {"person": name, "sicherheit": "mittel"}
                if vermut is None and bester_unsicher:
                    vermut = bester_unsicher
            gesicht_boxen.append({"index": i, "bbox": bbox, "vermutung": vermut})
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
    """Pfad der Fortschritts-Datei.

    `_FORTSCHRITT_OVERRIDE` erlaubt Tests, auf ein tmp_path umzubiegen — der
    ECHTE Stand (quiz_fortschritt.json, enthaelt Sebastians Quiz-Reihenfolge)
    wird von Tests nie angefasst.
    """
    if _FORTSCHRITT_OVERRIDE:
        return str(_FORTSCHRITT_OVERRIDE)
    from app.config import BASE_DIR
    return str(BASE_DIR / "quiz_fortschritt.json")


# Nie in Produktion gesetzt; nur Tests biegen den Fortschritt damit um.
_FORTSCHRITT_OVERRIDE = None


def _region_schluessel(bbox_norm) -> str:
    """Stabile Kennung einer GESICHTS-REGION aus der normalisierten bbox.

    Auf 1 % gerundet, damit minimale Zitter-Beträge derselben Region nicht als
    zwei verschiedene Regionen gelten. Grundlage der Regel "dieselbe Region
    fuer dieselbe Person ist bereits bestaetigt -> nicht erneut fragen"
    (Fix 2026-09-15).
    """
    try:
        if not bbox_norm or len(bbox_norm) < 4:
            return ""
        return ",".join(f"{round(float(v), 2):.2f}" for v in bbox_norm[:4])
    except (TypeError, ValueError):
        return ""


def _bestaetigte_eintraege(bild_pfad: str) -> list:
    """Roh-Eintraege {person, region} der Bestaetigungs-Markierung eines Bildes.

    Kompatibel zu beiden Schemata der Datei: aeltere Eintraege sind reine
    Namens-Strings, neuere {person, region}-Dicts.
    """
    if not bild_pfad:
        return []
    roh = (_fortschritt_daten().get("bestaetigt") or {}).get(bild_pfad) or []
    out = []
    for e in roh:
        if isinstance(e, str) and e:
            out.append({"person": e, "region": ""})
        elif isinstance(e, dict) and e.get("person"):
            out.append({"person": str(e.get("person")),
                        "region": str(e.get("region") or "")})
    return out


def _fortschritt_laden():
    """Liste der bereits durchgespielten Bildpfade (persistent)."""
    g = _fortschritt_daten().get("gesehen", [])
    return [x for x in g if isinstance(x, str)] if isinstance(g, list) else []


def _fortschritt_roh_speichern(daten: dict) -> None:
    """Schreibt den Fortschritt atomar (gesehen + bestaetigt)."""
    try:
        import json as _j, time as _t
        p = _fortschritt_pfad()
        tmp = p + ".tmp"
        gesehen = [x for x in (daten.get("gesehen") or []) if isinstance(x, str)]
        best = daten.get("bestaetigt") if isinstance(daten.get("bestaetigt"), dict) else {}
        # Nur die letzten 500 Bilder behalten, damit die Datei kompakt bleibt.
        kurz = {k: v for k, v in list(best.items())[-500:]}
        with open(tmp, "w", encoding="utf-8") as f:
            _j.dump({"gesehen": gesehen[-2000:], "bestaetigt": kurz,
                     "aktualisiert": _t.strftime("%Y-%m-%dT%H:%M:%S")}, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception as e:
        logger.warning("Quiz-Fortschritt speichern fehlgeschlagen: %s", e)


def _fortschritt_speichern(gesehen):
    d = _fortschritt_daten()
    d["gesehen"] = [x for x in (gesehen or []) if isinstance(x, str)]
    _fortschritt_roh_speichern(d)


def _bbox_zu_norm(bbox, bild_pfad):
    """bbox [x,y,w,h] in nativen Pixeln -> normalisiert [0..1] relativ zum Bild.

    Wird je Referenz mitgespeichert, damit der Rahmen im Frontend unabhaengig von
    Anzeigegroesse/Zoom/Drehung exakt am Gesicht sitzt (Befund Sebastian
    2026-09-15). None, wenn die Bildgroesse nicht ermittelbar ist.
    """
    try:
        if not bbox or len(bbox) < 4:
            return None
        from PIL import Image, ImageOps
        with Image.open(bild_pfad) as img:
            gedreht = ImageOps.exif_transpose(img)   # wie das angezeigte Bild
            iw, ih = gedreht.size
        if not iw or not ih:
            return None
        return [round(float(bbox[0]) / iw, 6), round(float(bbox[1]) / ih, 6),
                round(float(bbox[2]) / iw, 6), round(float(bbox[3]) / ih, 6)]
    except Exception:
        return None


def _fortschritt_daten() -> dict:
    """Vollstaendiger Fortschritt {gesehen: [...], bestaetigt: {pfad: [namen]}}."""
    try:
        import json as _j
        p = _fortschritt_pfad()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = _j.load(f)
            if isinstance(d, dict):
                d.setdefault("gesehen", [])
                d.setdefault("bestaetigt", {})
                return d
    except Exception as e:
        logger.warning("Quiz-Fortschritt laden fehlgeschlagen: %s", e)
    return {"gesehen": [], "bestaetigt": {}}


def _bestaetigte_gesichter(bild_pfad: str) -> list:
    """Namen, die fuer DIESES Bild bereits bestaetigt wurden (dedupliziert).

    Deterministische Fortschritts-Regel (Fix 2026-09-15, Repro Sebastian):
    Beim Speichern/Abschluss darf NICHT von vorne durch alle Gesichter gelaufen
    werden. Was hier steht, wird nicht erneut abgefragt.
    """
    out = []
    for e in _bestaetigte_eintraege(bild_pfad):
        n = e.get("person")
        if isinstance(n, str) and n and n not in out:
            out.append(n)
    return out


def _bestaetigte_regionen(bild_pfad: str) -> list:
    """Bereits bestaetigte GESICHTS-REGIONEN eines Bildes.

    Zwei Quellen, deterministisch zusammengefuehrt:
      1) die ausdrueckliche Markierung in `quiz_fortschritt.json`
         (`bestaetigt`: {bild_pfad: [{person, region}]}), gesetzt durch
         _bestaetigung_merken bei jeder bestaetigten Zuordnung.
      2) der KATALOG: jede Referenz, die aus DIESEM Ursprungsbild stammt,
         traegt Person + Bild + Region (bbox_norm) — also eine real
         gespeicherte Bestaetigung. Damit ueberlebt die Regel auch einen
         geloeschten Fortschritt (Bild bleibt trotzdem nicht offen).

    Liefert [{person, region, bbox, bbox_norm, ref_id}].
    """
    if not bild_pfad:
        return []
    out, gesehen = [], set()
    for e in _bestaetigte_eintraege(bild_pfad):
        schluessel = ((e.get("person") or "").strip().lower(), e.get("region") or "")
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        out.append({"person": e.get("person"), "region": e.get("region") or "",
                    "bbox": [], "bbox_norm": [], "ref_id": ""})
    try:
        from app.services import gesichter_service
        for r in gesichter_service.referenzen_zu_bild(bild_pfad):
            norm = r.get("bbox_norm") or []
            region = _region_schluessel(norm)
            schluessel = ((r.get("person") or "").strip().lower(), region)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            out.append({"person": r.get("person"), "region": region,
                        "bbox": r.get("bbox") or [], "bbox_norm": norm,
                        "ref_id": r.get("ref_id") or ""})
    except Exception:
        pass
    return out


def _ist_bestaetigt(bild_pfad: str, person: str, region: str = "") -> bool:
    """True, wenn (Person[, Region]) fuer dieses Bild schon bestaetigt ist.

    Ohne Region zaehlt die Person insgesamt (aeltere Markierungen ohne Region).
    """
    ziel = (person or "").strip().lower()
    if not bild_pfad or not ziel:
        return False
    for e in _bestaetigte_regionen(bild_pfad):
        if (e.get("person") or "").strip().lower() != ziel:
            continue
        if not region or e.get("region") == region:
            return True
    return False


def _bestaetigung_merken(bild_pfad: str, person: str, region: str = "") -> None:
    """Merkt (bild_pfad, person[, region]) dauerhaft als bestaetigt."""
    name = (person or "").strip()
    if not bild_pfad or not name:
        return
    try:
        d = _fortschritt_daten()
        best = d.get("bestaetigt")
        if not isinstance(best, dict):
            best = {}
        liste = best.get(bild_pfad)
        if not isinstance(liste, list):
            liste = []
        neu = {"person": name, "region": region or ""} if region else name
        if neu not in liste:
            liste.append(neu)
        best[bild_pfad] = liste
        d["bestaetigt"] = best
        _fortschritt_roh_speichern(d)
    except Exception as e:
        logger.warning("Quiz-Bestaetigung merken fehlgeschlagen: %s", e)


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


# Flüchtige Merkliste "Bild gerade angezeigt, aber noch nicht beantwortet" (in-memory).
# Verhindert, dass mehrere schnelle naechsteQuizRunde-/analysiere-Aufrufe DASSELBE
# Bild doppelt nacheinander waehlen, bevor es beantwortet/uebersprungen wurde
# (Wunsch Sebastian 2026-09-10: keine doppelten Bilder).
_geleert_nach = []  # [{pfad, zeit}] kappt nach kurzer Zeit / wenn alles verbraucht


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
    # NUR schnell: erstes nicht-durchgespieltes Bild waehlen (OHNE SFace-Sync),
    # damit es SOFORT angezeigt wird (Wunsch Sebastian). Die Gesichts-Analyse
    # erfolgt danach asynchron ueber /quiz/analysiere (oder beim Antworten).
    kandidat = None
    # "gerade angezeigt, noch nicht beantwortet" – beim schnellen Mehrfach-Ruf
    # ueberspringen, damit nicht dasselbe Bild doppelt nacheinander kommt.
    gerade = [p for p, t in _geleert_nach]
    for b in bilder:
        if b in kombiniert:
            continue
        if b in gerade:
            continue
        kandidat = b
        break
    # Falls alle Kandidaten "gerade angezeigt" sind (z. B. 1 Bild), dieses nehmen,
    # damit es nicht hängt – die Doppel-Dedup gilt nur, solange Alternativen da sind.
    if not kandidat:
        for b in bilder:
            if b in kombiniert:
                continue
            kandidat = b
            break
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
    # Als "gerade angezeigt" merken (in-memory), Altlasten aehnlich kurz halten.
    try:
        import time as _tmp
        _geleert_nach.append([kandidat, _tmp.time()])
        if len(_geleert_nach) > 400:
            _geleert_nach[:] = _geleert_nach[-400:]
        # Eintraege aelter als 2 Minuten verwerfen (Bild wurde inzwischen
        # beantwortet ODER darf wieder verfuegbar sein).
        _geleert_nach[:] = [x for x in _geleert_nach if _tmp.time() - x[1] < 120]
    except Exception:
        pass
    info = lese_datei_info(kandidat)
    runde = {
        "bild_pfad": kandidat,
        "name": info.get("name"),
        "data_url": info.get("data_url", ""),
        "ist_bild": bool(info.get("ist_bild")),
        # Analyse (Gesichter/Vermutung) folgt asynchron -> Frontend zeigt erst
        # nur Bild + Lade-Animation, dann Ja/Nein.
        "analyse_ausstehend": True,
        "anzahl_gesichter": 0,
        "gesichter": [],
        "vermutung": None,
    }
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


def beantworte_runde(bild_pfad: str, person: str, ist_neu: bool, rolle: str = "",
                     beziehung: str = "", beschreibung: str = "", bbox=None):
    from app.services import face_service, gesichter_service
    name = (person or "").strip()
    rolle = (rolle or "").strip()
    beziehung = (beziehung or "").strip()
    beschreibung = (beschreibung or "").strip()
    if not name:
        return {"ok": False, "fehler": "keine Person angegeben"}
    if not bild_pfad or not os.path.exists(bild_pfad):
        return {"ok": False, "fehler": "Bild nicht gefunden"}

    # DETERMINISTISCHE BESTAETIGUNGS-REGEL (Fix 2026-09-15, Repro Sebastian
    # "beim Speichern geht er die Personen nochmal von vorne durch, auch die
    # schon zugeordneten"): Ist dieselbe Gesichts-Region fuer dieselbe Person
    # bereits bestaetigt, wird NICHTS erneut eingelernt und die Runde gilt als
    # abgeschlossen. Das VOR der (teuren) Detektion pruefen.
    bbox_norm_neu = _bbox_zu_norm(bbox, bild_pfad) if bbox else None
    region_neu = _region_schluessel(bbox_norm_neu)
    if region_neu and _ist_bestaetigt(bild_pfad, name, region_neu):
        vorhanden_jetzt = None
        for p in gesichter_service.liste_personen():
            if (p.get("name") or "").strip().lower() == name.lower():
                vorhanden_jetzt = p
                break
        return {"ok": True, "person": name, "ist_neu": False,
                "bereits_bestaetigt": True, "uebersprungen": True,
                "referenzen": len(gesichter_service._refs_of(vorhanden_jetzt)) if vorhanden_jetzt else 0,
                "hinzugefuegt": False, "jahr": None,
                "bereits_bestaetigt_namen": list(_bestaetigte_gesichter(bild_pfad))}

    # Erkennung robust (ein Wiederholungsversuch) — die Detektion ist auf
    # Termux wechselhaft; ein leerer Lauf liess die Antwort sonst sporadisch
    # fehlschlagen und das Bild NICHT als gesehen markieren (Quiz begann von vorn).
    gesichter = _gesichter_robust(bild_pfad)
    dom = _gesicht_zu_bbox(gesichter, bbox) if gesichter else None
    if dom and dom.get("embedding"):
        neue_emb = dom["embedding"]
        neue_bbox = dom.get("bbox") or []
    else:
        # Fallback: GENAU den (ggf. korrigierten) Rahmen einbetten, den der
        # Nutzer bestaetigt hat — statt die Antwort zu verwerfen.
        if not (bbox and len(bbox) >= 4):
            return {"ok": False, "fehler": "kein Gesicht im Bild erkannt"}
        if not face_service.verfuegbar():
            return {"ok": False, "fehler": "Face-Engine nicht verfuegbar"}
        emb_fallback = face_service.embedding_fuer_bbox(os.path.abspath(bild_pfad), bbox)
        if not emb_fallback:
            return {"ok": False, "fehler": "kein brauchbares Gesicht"}
        neue_emb = emb_fallback
        neue_bbox = [float(v) for v in bbox]

    neu = False
    hinzugefuegt = True
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

    # Gesichts-Ausschnitt als NORMALISIERTE Koordinaten (0..1) mitspeichern,
    # damit der Rahmen im Frontend unabhaengig von Anzeigegroesse/Zoom/Drehung
    # exakt am Gesicht sitzt (Befund Sebastian 2026-09-15).
    neue_ref = {"embedding": neue_emb, "jahr": jahr, "bild_pfad": bild_pfad,
                "bbox": neue_bbox,
                "bbox_norm": _bbox_zu_norm(neue_bbox, bild_pfad)}
    if vorhanden is None:
        gesichter_service.person_speichern(name=name, rolle=rolle,
                                           beziehung=beziehung, beschreibung=beschreibung,
                                           referenzen=[neue_ref])
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
        zu_alt = min((face_service._cosinus_distanz(neue_emb, r) for r in refs_emb if r),
                     default=None)
        hinzugefuegt = zu_alt is None or zu_alt > 0.05
        if hinzugefuegt:
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
        # ui-Feld: erlaubt dem Frontend nach Reload die SCHÖNE Bildunterschrift-
        # Karte zu rekonstruieren (Bild + "… das ist X") statt nur den Text
        # (Wunsch Sebastian 2026-09-10: nach F5 den Quiz-Verlauf mit Bild sehen).
        ui_block = {
            "typ": "quiz_ergebnis",
            "person": name,
            "referenzen": referenzen,
            "jahr": jahr,
            "bild_pfad": bild_pfad,
        } if name else None
        verlauf_nachricht_anhaengen("conv_main", "assistant", text, bild_pfad=bild_pfad, ui=ui_block)
    except Exception:
        pass

    # Nach erfolgreicher Beantwortung das Bild als persistent 'gesehen' markieren
    # (erst jetzt verbraucht, nicht schon beim Anzeigen -> echtes Pausieren).
    try:
        # Mit REGION: damit ist dieselbe Gesichts-Region fuer dieselbe Person
        # als bestaetigt markiert und wird nicht erneut abgefragt.
        region_final = _region_schluessel(_bbox_zu_norm(neue_bbox, bild_pfad))
        _bestaetigung_merken(bild_pfad, name, region_final)   # deterministische Fortschritts-Regel
        gesehen = _fortschritt_laden()
        if bild_pfad not in gesehen:
            _fortschritt_speichern(gesehen + [bild_pfad])
    except Exception:
        pass

    return {"ok": True, "person": name, "ist_neu": neu, "referenzen": referenzen,
            "jahr": jahr, "hinzugefuegt": hinzugefuegt,
            "bereits_bestaetigt": list(_bestaetigte_gesichter(bild_pfad))}


def ergaenze_person_mit_bbox(bild_pfad: str, person: str, ist_neu: bool,
                             rolle: str = "", beziehung: str = "",
                             beschreibung: str = "", bbox=None) -> dict:
    """Ergänzt eine Person über einen SELBST gezeichneten Rahmen (bbox in
    ABSOLUTEN Pixeln). Anders als beantworte_runde (das nur unter den von YuNet
    gefundenen Gesichtern wählt) wird hier der vom Nutzer markierte Ausschnitt
    direkt eingebettet — so lässt sich auch eine Person anlernen, die YuNet
    gar nicht (richtig) erkannt hat (Wunsch Sebastian 2026-09-11).

    `bbox` MUSS gesetzt sein. Liefert {ok, person, ist_neu, referenzen, jahr}.
    """
    from app.services import face_service, gesichter_service
    name = (person or "").strip()
    rolle = (rolle or "").strip()
    beziehung = (beziehung or "").strip()
    beschreibung = (beschreibung or "").strip()
    if not name:
        return {"ok": False, "fehler": "keine Person angegeben"}
    if not bild_pfad or not os.path.exists(bild_pfad):
        return {"ok": False, "fehler": "Bild nicht gefunden"}
    if not bbox or len(bbox) < 4:
        return {"ok": False, "fehler": "kein Rahmen (bbox) angegeben"}
    if not face_service.verfuegbar():
        return {"ok": False, "fehler": "Face-Engine nicht verfügbar"}

    # Dieselbe Region fuer dieselbe Person schon bestaetigt -> nicht erneut
    # einlernen (idempotent, Fix 2026-09-15).
    region_neu = _region_schluessel(_bbox_zu_norm(bbox, bild_pfad))
    if region_neu and _ist_bestaetigt(bild_pfad, name, region_neu):
        vorhanden_jetzt = None
        for p in gesichter_service.liste_personen():
            if (p.get("name") or "").strip().lower() == name.lower():
                vorhanden_jetzt = p
                break
        return {"ok": True, "person": name, "ist_neu": False,
                "bereits_bestaetigt": True, "uebersprungen": True,
                "referenzen": len(gesichter_service._refs_of(vorhanden_jetzt)) if vorhanden_jetzt else 0,
                "jahr": None}

    emb = face_service.embedding_fuer_bbox(os.path.abspath(bild_pfad), bbox)
    if not emb:
        return {"ok": False,
                "fehler": "im markierten Ausschnitt wurde kein Gesicht erkannt"}

    neu = False
    vorhanden = None
    for p in gesichter_service.liste_personen():
        if (p.get("name") or "").strip().lower() == name.lower():
            vorhanden = p
            break

    try:
        from app.services.datei_suche import _datei_jahr
        jahr = _datei_jahr(bild_pfad)
    except Exception:
        jahr = None

    neue_ref = {"embedding": emb, "jahr": jahr, "bild_pfad": bild_pfad,
                "bbox": [float(v) for v in bbox],
                "bbox_norm": _bbox_zu_norm(bbox, bild_pfad)}
    if vorhanden is None:
        gesichter_service.person_speichern(name=name, rolle=rolle,
                                           beziehung=beziehung, beschreibung=beschreibung,
                                           referenzen=[neue_ref])
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
        bestehende = vorhanden.get("referenzen")
        if not bestehende:
            bestehende = [{"embedding": r, "jahr": None}
                          for r in _refs_als_liste(vorhanden.get("embedding"))]
        bestehende = [r for r in bestehende if isinstance(r, dict) and r.get("embedding")]
        refs_emb = [r["embedding"] for r in bestehende]
        zu_alt = min((face_service._cosinus_distanz(emb, r) for r in refs_emb if r),
                     default=None)
        if zu_alt is None or zu_alt > 0.05:
            bestehende = bestehende + [neue_ref]
            gesichter_service.person_speichern(**basis, referenzen=bestehende)
        referenzen = len(bestehende)

    try:
        from app.services.chat_verlauf import verlauf_nachricht_anhaengen
        rolle_txt = f" ({rolle})" if rolle else ""
        text = (f"[Gesichter-Quiz] '{name}'{rolle_txt} per Rahmen ergänzt — "
                f"{referenzen} Referenz(en), Aufnahmejahr {jahr or '?'}. "
                f"[Bild gespeichert zum erneuten Ansehen]")
        ui_block = {
            "typ": "quiz_ergebnis",
            "person": name,
            "referenzen": referenzen,
            "jahr": jahr,
            "bild_pfad": bild_pfad,
        } if name else None
        verlauf_nachricht_anhaengen("conv_main", "assistant", text,
                                    bild_pfad=bild_pfad, ui=ui_block)
    except Exception:
        pass

    try:
        region_final = _region_schluessel(_bbox_zu_norm(bbox, bild_pfad))
        _bestaetigung_merken(bild_pfad, name, region_final)   # deterministische Fortschritts-Regel
        gesehen = _fortschritt_laden()
        if bild_pfad not in gesehen:
            _fortschritt_speichern(gesehen + [bild_pfad])
    except Exception:
        pass

    return {"ok": True, "person": name, "ist_neu": neu, "referenzen": referenzen,
            "jahr": jahr, "bereits_bestaetigt": list(_bestaetigte_gesichter(bild_pfad)),
            "bereits_bestaetigt_regionen": _bestaetigte_regionen(bild_pfad)}


def analysiere_bild(bild_pfad: str) -> dict:
    """Fuehrt die (langsame) Gesichts-Analyse fuer ein bereits angezeigtes Bild
    nach: erkennt Gesichter, stellt ggf. eine Vermutung. Wird vom Frontend NACH
    der Sofort-Anzeige des Bildes aufgerufen (Wunsch Sebastian: Bild sofort,
    Lade-Animation darunter, dann Ja/Nein ersetzt die Animation).

    Returns dict {anzahl_gesichter, gesichter, vermutung, erkannte_personen,
    unsichere_personen, engine_verfuegbar}.

    `engine_verfuegbar` (Fix 2026-09-15): Das Frontend darf ein Bild NUR dann
    automatisch als "gesehen" abhaken, wenn die Engine wirklich gelaufen ist.
    Ist sie nicht verfuegbar, waeren 0 Gesichter ein Messfehler — und das Bild
    wuerde dauerhaft (quiz_fortschritt) verbraucht. Deshalb wird der Zustand
    ehrlich mitgeliefert.
    """
    leer = {"anzahl_gesichter": 0, "gesichter": [], "vermutung": None,
            "erkannte_personen": [], "unsichere_personen": []}
    try:
        from app.services import face_service
        if not bild_pfad or not os.path.exists(bild_pfad):
            # Bild fehlt/verschoben -> keine Aussage moeglich; als "Engine nicht
            # gelaufen" melden, damit das Frontend es nicht verbraucht.
            return dict(leer, engine_verfuegbar=False)
        if not face_service.verfuegbar():
            return dict(leer, engine_verfuegbar=False)
        gesichter = face_service.embeddings_fuer_pfad(os.path.abspath(bild_pfad))
        if not gesichter:
            return dict(leer, engine_verfuegbar=True)
        _erk = _erkannte_personen_bildes(bild_pfad, gesichter)
        # Bereits bestaetigte Regionen + Bestaetigungs-Flag JE GESICHT (Fix
        # 2026-09-15): Das Frontend ueberspringt damit Gesichter, deren Region
        # schon zugeordnet ist, statt nach "Speichern" alles neu aufzurollen.
        regionen = _bestaetigte_regionen(bild_pfad)
        boxen = []
        for g in _erk.get("gesichter", []):
            eintrag = dict(g)
            try:
                norm = _bbox_zu_norm(g.get("bbox") or [], bild_pfad)
                reg = _region_schluessel(norm)
                eintrag["bbox_norm"] = norm or []
                eintrag["region"] = reg
                eintrag["bestaetigt"] = sorted({
                    e.get("person") for e in regionen
                    if e.get("person") and (not reg or e.get("region") == reg)
                })
            except Exception:
                eintrag["bestaetigt"] = []
            boxen.append(eintrag)
        return {
            "anzahl_gesichter": _erk.get("anzahl_gesichter", 0),
            "gesichter": boxen,
            # Dieselbe Detektion wiederverwenden -> kein zweiter, unabhaengiger
            # Lauf, der die Vermutung sporadisch wegfallen liess.
            "vermutung": _hypothese(bild_pfad, gesichter),
            "erkannte_personen": _erk.get("erkannte", []),
            "unsichere_personen": _erk.get("unsicher", []),
            "engine_verfuegbar": True,
            "bestaetigte_personen": list(_bestaetigte_gesichter(bild_pfad)),
            "bestaetigte_regionen": regionen,
        }
    except Exception:
        return dict(leer, engine_verfuegbar=False)
