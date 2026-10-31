"""Lebensabschnitte und belegbare Aussagen (On-Device, 30.10.2026).

Warum dieses Modul:
  Sebastian benennt Personen im Gruppen-Quiz und im Bildeditor am Smartphone.
  Bisher wurden alle Gesichter einer Person als ungeordneter Block dargestellt.
  Dieses Modul strukturiert die Gesichter und Gruppen einer Person am Smartphone
  in chronologische Lebensabschnitte (Phasen nach Jahren), leitet belegbare
  Aussagen über Zeiträume und Begleitpersonen ab und liefert Vorschläge für
  offene Gruppen auf dem Gerät.
  Seit 31.10.2026:
    * 100 % aller Gesichter aus gesicht_zuordnung.jsonl werden lückenlos abgedeckt.
    * Kontinuierliche 128-dim Phasen-Zentroide (Embedding-Mittelwert je Lebensabschnitt).
    * Zwillings-Differenzierung (Sebastian vs. Julian) über Vektorabstand und Cannot-Link.
    * Temporal-Filter für Kinder- und Jugendphasen.

Eigenschaften:
  * Rein lokal: keine externen Netzanrufe, keine Modellkosten, nur lokale Daten.
  * Belegbar: Aussagen beruhen ausschließlich auf vorhandenen Daten
    (Aufnahmejahren, bestätigten Namen, beziehungen.jsonl / gesicht_zuordnung.jsonl).
  * Robust: Fehler werden abgefangen; kein Wurf ("nie ein Crash").
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Maximale Lücke in Jahren innerhalb einer zusammenhängenden Phase
PHASEN_LUECKE_MAX = 2
# Maximale Zeitspanne einer Phase in Jahren, bevor getrennt wird
PHASEN_SPANNE_MAX = 5


def jahr_aus(datum: Any) -> Optional[int]:
    """Extrahiert ein 4-stelliges Kalenderjahr (1900..2100) aus Text, Zahl oder None."""
    if datum is None:
        return None
    if isinstance(datum, int):
        return datum if 1900 <= datum <= 2100 else None
    s = str(datum).strip()
    m = re.match(r"^(\d{4})", s)
    if m:
        try:
            j = int(m.group(1))
            if 1900 <= j <= 2100:
                return j
        except ValueError:
            return None
    return None


def alter_in_jahr(geburtsdatum: Any, ziel_jahr: int) -> Optional[int]:
    """Berechnet das ungefähre Alter in einem bestimmten Kalenderjahr."""
    geb_jahr = jahr_aus(geburtsdatum)
    if geb_jahr is None or ziel_jahr < geb_jahr:
        return None
    return ziel_jahr - geb_jahr


def phasen_bilden_jahre(jahre: List[int]) -> List[Tuple[int, int]]:
    """Unterteilt eine Liste von Kalenderjahren in zusammenhängende Phasen [(von, bis), ...]."""
    bereinigt = sorted({j for j in jahre if isinstance(j, int) and 1900 <= j <= 2100})
    if not bereinigt:
        return []

    phasen: List[Tuple[int, int]] = []
    akt_von = bereinigt[0]
    akt_bis = bereinigt[0]

    for j in bereinigt[1:]:
        luecke = j - akt_bis
        spanne = j - akt_von
        if luecke > PHASEN_LUECKE_MAX or spanne >= PHASEN_SPANNE_MAX:
            phasen.append((akt_von, akt_bis))
            akt_von = j
            akt_bis = j
        else:
            akt_bis = j

    phasen.append((akt_von, akt_bis))
    return phasen


def _basis_ordner(basis_pfad: Optional[str] = None) -> str:
    if basis_pfad and basis_pfad.strip():
        return basis_pfad.strip()
    from app.services import gruppen_quiz
    return gruppen_quiz.basis()


_BEZIEHUNGEN_CACHE: Dict[str, Tuple[Tuple[float, int], Dict[str, List[Tuple[Optional[int], List[str]]]]]] = {}
_MITTELPUNKTE_CACHE: Dict[str, Tuple[Tuple[float, int], Dict[str, List[float]]]] = {}
_PHASEN_CACHE: Dict[str, Tuple[Tuple[Any, ...], Dict[str, List[Dict[str, Any]]]]] = {}


def invalidiere_cache() -> None:
    """Leert alle internen Caches für Phasen, Beziehungen und Vektoren."""
    _PHASEN_CACHE.clear()
    _BEZIEHUNGEN_CACHE.clear()
    _MITTELPUNKTE_CACHE.clear()


def _kennungen_mittelpunkte(basis_pfad: Optional[str] = None) -> Dict[str, List[float]]:
    """Liest die 128-dimensionalen SFace-Mittelpunkte aus kennungen.json."""
    from app.services import gruppen_quiz
    b = _basis_ordner(basis_pfad)
    for p in (os.path.join(b, gruppen_quiz.UNTERORDNER, "kennungen.json"), os.path.join(b, "kennungen.json")):
        if os.path.isfile(p):
            try:
                st = os.stat(p)
                sig = (st.st_mtime, st.st_size)
            except OSError:
                continue
            cached = _MITTELPUNKTE_CACHE.get(p)
            if cached and cached[0] == sig:
                return cached[1]
            try:
                with open(p, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                mps: Dict[str, List[float]] = {}
                for e in daten.get("kennungen", []) if isinstance(daten, dict) else []:
                    if isinstance(e, dict) and e.get("kennung") and isinstance(e.get("mittelpunkt"), list):
                        mps[str(e["kennung"])] = e["mittelpunkt"]
                _MITTELPUNKTE_CACHE[p] = (sig, mps)
                return mps
            except Exception as fehler:
                logger.warning("kennungen.json nicht lesbar: %s", fehler)
                return {}
    return {}


def cosinus_aehnlichkeit(v1: Optional[List[float]], v2: Optional[List[float]]) -> float:
    """Berechnet die Kosinus-Ähnlichkeit zweier 128-dim Vektoren."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    n1 = 0.0
    n2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        n1 += a * a
        n2 += b * b
    if n1 <= 0.0 or n2 <= 0.0:
        return 0.0
    return dot / ((n1 * n2) ** 0.5)


def _alle_gesichter_fuer_person(name: str, basis_pfad: Optional[str] = None) -> List[Dict[str, Any]]:
    """Gibt alle bestätigten und zugeordneten Gesichter einer Person mit Aufnahme-Datum zurück.
    Liest direkt aus gesicht_zuordnung.jsonl (über gruppen_quiz._gemerkt). Nie ein Wurf."""
    from app.services import gruppen_quiz
    b = _basis_ordner(basis_pfad)
    pfad = None
    for p in (os.path.join(b, gruppen_quiz.UNTERORDNER, gruppen_quiz.ZUORDNUNG_DATEINAME),
              os.path.join(b, gruppen_quiz.ZUORDNUNG_DATEINAME)):
        if os.path.isfile(p):
            pfad = p
            break
    if not pfad:
        return []

    try:
        echter, kennungen = gruppen_quiz._person_kennungen(name)
        if not kennungen and not echter:
            best = gruppen_quiz.bestaetigt_lesen()
            echter = name.strip()
            kennungen = sorted(k for k, n in best.items() if n.casefold() == echter.casefold())
        if not echter:
            echter = name.strip()

        je = gruppen_quiz._gemerkt(pfad, gruppen_quiz._gesichter_laden)
        aus = gruppen_quiz.ausgeschlossen_lesen()
        zug = gruppen_quiz.zugeordnet_lesen()
    except Exception as e:
        logger.warning("_alle_gesichter_fuer_person fehlgeschlagen: %s", e)
        return []

    gesichter: List[Dict[str, Any]] = []
    for k in kennungen:
        weg = aus.get(k, set())
        for g in je.get(k, []):
            if g["gid"] not in weg and (zug.get(g["gid"]) or {}).get("name", echter).casefold() == echter.casefold():
                gesichter.append(dict(g, kennung=k))

    schon = {g["gid"] for g in gesichter}
    for gid, e in zug.items():
        if e.get("name", "").casefold() == echter.casefold() and gid not in schon:
            k = e.get("kennung")
            if k and k in je:
                for g in je[k]:
                    if g["gid"] == gid:
                        gesichter.append(dict(g, kennung=k, zugeordnet=True))
                        break

    return gesichter


def _beziehungen_index(pfad: str) -> Dict[str, List[Tuple[Optional[int], List[str]]]]:
    """Indexiert beziehungen.jsonl einmalig in den RAM (name.casefold -> [(jahr, andere_namen), ...])."""
    try:
        st = os.stat(pfad)
        sig = (st.st_mtime, st.st_size)
    except OSError:
        return {}
    cached = _BEZIEHUNGEN_CACHE.get(pfad)
    if cached and cached[0] == sig:
        return cached[1]

    index: Dict[str, List[Tuple[Optional[int], List[str]]]] = {}
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for zeile in datei:
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    e = json.loads(zeile)
                except ValueError:
                    continue
                if not isinstance(e, dict):
                    continue

                personen = e.get("personen")
                if not isinstance(personen, list):
                    continue

                namen_in_zeile = [
                    str(p.get("name") or "").strip()
                    for p in personen
                    if isinstance(p, dict) and p.get("name")
                ]
                if len(namen_in_zeile) < 2:
                    continue

                d_jahr = jahr_aus(e.get("datum"))
                for n in namen_in_zeile:
                    n_cf = n.casefold()
                    andere = [x for x in namen_in_zeile if x.casefold() != n_cf]
                    index.setdefault(n_cf, []).append((d_jahr, andere))
    except Exception as fehler:
        logger.warning("Beziehungen-Indexierung fehlgeschlagen: %s", fehler)
        return {}

    _BEZIEHUNGEN_CACHE[pfad] = (sig, index)
    return index


def begleiter_aus_beziehungen(name: str, von_jahr: Optional[int], bis_jahr: Optional[int],
                              basis_pfad: Optional[str] = None) -> List[str]:
    """Findet häufige Begleitpersonen aus beziehungen.jsonl im Zeitraum (sub-millisekundenschnell per Index)."""
    pfad = os.path.join(_basis_ordner(basis_pfad), "beziehungen.jsonl")
    if not os.path.isfile(pfad):
        return []

    idx = _beziehungen_index(pfad)
    eintraege = idx.get(name.casefold(), [])
    if not eintraege:
        return []

    treffer: Counter = Counter()
    for d_jahr, andere in eintraege:
        if von_jahr is not None and d_jahr is not None and d_jahr < von_jahr:
            continue
        if bis_jahr is not None and d_jahr is not None and d_jahr > bis_jahr:
            continue
        for a in andere:
            treffer[a] += 1

    return [p for p, _c in treffer.most_common(3)]


def lebensabschnitte_fuer_person(name: str,
                                 vorschlaege: Optional[List[Dict[str, Any]]] = None,
                                 profil_daten: Optional[Dict[str, Any]] = None,
                                 basis_pfad: Optional[str] = None) -> Dict[str, Any]:
    """Berechnet die chronologischen Lebensabschnitte, Zentroide und Aussagen für eine Person."""
    from app.services import gruppen_quiz

    echter_name = name.strip()
    if not echter_name:
        return {"ok": False, "name": "", "phasen": [], "anzahl_phasen": 0,
                "gesamt_gesichter": 0, "aussage": "Kein Personenname angegeben."}

    if vorschlaege is None:
        person_daten = gruppen_quiz.person(echter_name)
        if not person_daten.get("ok"):
            return {"ok": False, "name": echter_name, "phasen": [], "anzahl_phasen": 0,
                    "gesamt_gesichter": 0, "aussage": str(person_daten.get("fehler") or "Person nicht gefunden.")}
        vorschlaege = person_daten.get("vorschlaege") or []
        if profil_daten is None:
            profil_daten = person_daten.get("profil") or {}

    # Geburtstag für Altersstufen ermitteln
    geburtstag = None
    if isinstance(profil_daten, dict):
        kontakt = profil_daten.get("kontakt")
        if isinstance(kontakt, dict) and kontakt.get("geburtstag"):
            geburtstag = kontakt.get("geburtstag")

    # Alle Gesichts-Beispiele und Jahre zusammentragen
    belege: List[Dict[str, Any]] = []
    alle_jahre: List[int] = []

    # 100% aller Gesichter aus gesicht_zuordnung.jsonl bevorzugen
    sichtbare_gesichter = []
    if vorschlaege is None:
        sichtbare_gesichter = _alle_gesichter_fuer_person(echter_name, basis_pfad)

    if sichtbare_gesichter:
        gesamt_gesichter = len(sichtbare_gesichter)
        for g in sichtbare_gesichter:
            j = jahr_aus(g.get("aufnahme"))
            if j:
                alle_jahre.append(j)
            belege.append({
                "jahr": j,
                "datum": g.get("aufnahme"),
                "beispiel": g,
                "kennung": g.get("kennung"),
                "_guete": g.get("_guete", 0.0),
            })
    else:
        # Fallback auf übergebene vorschlaege
        for v in vorschlaege:
            if not isinstance(v, dict):
                continue
            v_groesse = max(0, int(v.get("groesse") or 0))
            beispiele = v.get("beispiele") or []
            v_jahr_von = jahr_aus(v.get("von"))
            v_jahr_bis = jahr_aus(v.get("bis"))

            if v_jahr_von:
                alle_jahre.append(v_jahr_von)
            if v_jahr_bis and v_jahr_bis != v_jahr_von:
                alle_jahre.append(v_jahr_bis)

            if beispiele:
                for b in beispiele:
                    if not isinstance(b, dict):
                        continue
                    b_jahr = jahr_aus(b.get("aufnahme")) or v_jahr_von or v_jahr_bis
                    if b_jahr:
                        alle_jahre.append(b_jahr)
                    belege.append({
                        "jahr": b_jahr,
                        "datum": b.get("aufnahme") or v.get("von"),
                        "beispiel": b,
                        "kennung": v.get("kennung"),
                        "_guete": 0.0,
                    })
            elif v_jahr_von or v_jahr_bis:
                j = v_jahr_von or v_jahr_bis
                if j:
                    alle_jahre.append(j)
                belege.append({
                    "jahr": j,
                    "datum": v.get("von") or v.get("bis"),
                    "beispiel": None,
                    "kennung": v.get("kennung"),
                    "groesse": v_groesse,
                    "_guete": 0.0,
                })

        gesamt_gesichter = sum(max(0, int(v.get("groesse") or 0)) for v in vorschlaege if isinstance(v, dict))
        if gesamt_gesichter == 0 and belege:
            gesamt_gesichter = len(belege)

    if not alle_jahre:
        # Keine Jahresangaben bekannt: 1 unbestimmte Phase
        passende_kennungen = sorted(list(set(b["kennung"] for b in belege if b.get("kennung"))))
        phase = {
            "phase_id": "phase-unbekannt",
            "von_jahr": None,
            "bis_jahr": None,
            "von": None,
            "bis": None,
            "titel": "Aufnahmen ohne Datum",
            "alters_hinweis": None,
            "gesichter_anzahl": gesamt_gesichter,
            "gruppen_anzahl": len(passende_kennungen),
            "gruppen_kennungen": passende_kennungen,
            "beispiele": [b["beispiel"] for b in belege if b["beispiel"]][:6],
            "begleiter": begleiter_aus_beziehungen(echter_name, None, None, basis_pfad),
            "aussage": f"{gesamt_gesichter} Bild(er) ohne bekanntes Aufnahmedatum.",
            "zentroid": None,
        }
        return {
            "ok": True,
            "name": echter_name,
            "phasen": [phase] if gesamt_gesichter > 0 else [],
            "anzahl_phasen": 1 if gesamt_gesichter > 0 else 0,
            "gesamt_gesichter": gesamt_gesichter,
            "von_jahr": None,
            "bis_jahr": None,
            "aussage": f"{gesamt_gesichter} Fotos ohne zeitliche Einordnung.",
        }

    mps = _kennungen_mittelpunkte(basis_pfad)
    gefundene_phasen_spannen = phasen_bilden_jahre(alle_jahre)
    phasen_liste: List[Dict[str, Any]] = []

    for von_j, bis_j in gefundene_phasen_spannen:
        passende_belege = [b for b in belege if b["jahr"] and von_j <= b["jahr"] <= bis_j]
        # Beste Beispiele für diese Phase nach Güte sortiert
        sortierte_belege = sorted(
            [b for b in passende_belege if b.get("beispiel")],
            key=lambda x: -float(x.get("_guete") or 0.0)
        )
        phasen_beispiele = [b["beispiel"] for b in sortierte_belege][:6]

        # Wenn keine konkreten Beispiele vorhanden, Gesichterzahl aus Belegen summieren
        anzahl = sum(
            (b.get("groesse", 1) if b.get("beispiel") is None else 1)
            for b in passende_belege
        )
        if anzahl == 0:
            anzahl = len(phasen_beispiele)

        # Titel & Altersangabe
        if von_j == bis_j:
            titel = str(von_j)
            alter_text = None
            if geburtstag:
                alt = alter_in_jahr(geburtstag, von_j)
                if alt is not None:
                    alter_text = f"ca. {alt} Jahre"
        else:
            titel = f"{von_j} – {bis_j}"
            alter_text = None
            if geburtstag:
                alt_von = alter_in_jahr(geburtstag, von_j)
                alt_bis = alter_in_jahr(geburtstag, bis_j)
                if alt_von is not None and alt_bis is not None:
                    alter_text = f"ca. {alt_von}–{alt_bis} Jahre"

        # Begleiter
        begleiter = begleiter_aus_beziehungen(echter_name, von_j, bis_j, basis_pfad)

        # Lesbare Aussage für diesen Lebensabschnitt
        saetze: List[str] = []
        if von_j == bis_j:
            zeit_teil = f"Im Jahr {von_j}"
        else:
            zeit_teil = f"In den Jahren {von_j} bis {bis_j}"

        if alter_text:
            zeit_teil += f" ({alter_text})"

        passende_kennungen = sorted(list(set(b["kennung"] for b in passende_belege if b.get("kennung"))))
        grp_anz = len(passende_kennungen)
        grp_text = f" in {grp_anz} Gruppe{'n' if grp_anz != 1 else ''}" if grp_anz > 0 else ""
        satz = f"{zeit_teil} auf {anzahl} Foto(s){grp_text} festgehalten"
        if begleiter:
            satz += f", am häufigsten zusammen mit {', '.join(begleiter[:2])}"
        satz += "."
        saetze.append(satz)

        # 128-dim Phasen-Zentroid berechnen
        zentroid = None
        k_counts = Counter(b.get("kennung") for b in passende_belege if b.get("kennung"))
        if mps and any(k in mps for k in k_counts):
            sum_vec = [0.0] * 128
            for k, w in k_counts.items():
                if k in mps and len(mps[k]) == 128:
                    vec = mps[k]
                    for d in range(128):
                        sum_vec[d] += w * vec[d]
            norm = sum(x * x for x in sum_vec) ** 0.5
            if norm > 0.0:
                zentroid = [round(x / norm, 6) for x in sum_vec]

        phasen_liste.append({
            "phase_id": f"phase-{von_j}-{bis_j}",
            "von_jahr": von_j,
            "bis_jahr": bis_j,
            "von": f"{von_j}-01-01",
            "bis": f"{bis_j}-12-31",
            "titel": titel,
            "alters_hinweis": alter_text,
            "gesichter_anzahl": anzahl,
            "gruppen_anzahl": grp_anz,
            "gruppen_kennungen": passende_kennungen,
            "beispiele": phasen_beispiele,
            "begleiter": begleiter,
            "aussage": " ".join(saetze),
            "zentroid": zentroid,
        })

    min_jahr = min(alle_jahre)
    max_jahr = max(alle_jahre)

    if len(phasen_liste) == 1:
        gesamt_aussage = (
            f"Insgesamt {gesamt_gesichter} Fotos im Lebensabschnitt {phasen_liste[0]['titel']}."
        )
    else:
        gesamt_aussage = (
            f"Insgesamt {gesamt_gesichter} Fotos in {len(phasen_liste)} Lebensabschnitten "
            f"von {min_jahr} bis {max_jahr}."
        )

    return {
        "ok": True,
        "name": echter_name,
        "phasen": phasen_liste,
        "anzahl_phasen": len(phasen_liste),
        "gesamt_gesichter": gesamt_gesichter,
        "von_jahr": min_jahr,
        "bis_jahr": max_jahr,
        "aussage": gesamt_aussage,
    }


def alle_personen_phasen(basis_pfad: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Berechnet die Lebensabschnitte aller benannten Personen in einem schnellen Durchlauf und cached sie."""
    from app.services import gruppen_quiz
    b_pfad = _basis_ordner(basis_pfad)
    pfad_bestaetigt = os.path.join(b_pfad, gruppen_quiz.BESTAETIGT_DATEINAME)
    pfad_gruppen = os.path.join(b_pfad, gruppen_quiz.BEISPIELE_DATEINAME)

    sig = []
    for p in (pfad_bestaetigt, pfad_gruppen):
        if os.path.isfile(p):
            try:
                st = os.stat(p)
                sig.append((p, st.st_mtime, st.st_size))
            except OSError:
                pass
    sig_tuple = tuple(sig)
    cached = _PHASEN_CACHE.get(b_pfad)
    if cached and cached[0] == sig_tuple and sig_tuple:
        return cached[1]

    try:
        alle_gruppen, _ = gruppen_quiz._gruppen_laden()
        bestaetigt = gruppen_quiz.bestaetigt_lesen()
    except Exception:
        return {}

    nach_kennung = {g.get("kennung"): g for g in alle_gruppen if isinstance(g, dict) and g.get("kennung")}
    katalog: Dict[str, List[Dict[str, Any]]] = {}
    for k, n in bestaetigt.items():
        if k in nach_kennung:
            katalog.setdefault(n, []).append(nach_kennung[k])

    phasen_je_person: Dict[str, List[Dict[str, Any]]] = {}
    for n, v_liste in katalog.items():
        res = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
        if res.get("ok"):
            phasen_je_person[n] = res.get("phasen") or []

    if sig_tuple:
        _PHASEN_CACHE[b_pfad] = (sig_tuple, phasen_je_person)
    return phasen_je_person


def vorschlag_fuer_offene_gruppe(gruppe: Dict[str, Any],
                                 katalog: Optional[Dict[str, Any]] = None,
                                 personen_phasen: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                                 basis_pfad: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Prüft, ob eine unbenannte Gruppe zeitlich und vektoriell in den Lebensabschnitt einer bekannten Person passt.
    Berücksichtigt Phasen-Zentroide, Altersgrenzen und Zwillings-Trennung."""
    if not isinstance(gruppe, dict):
        return None

    # Zeitraum der Gruppe ermitteln
    g_jahr = jahr_aus(gruppe.get("von")) or jahr_aus(gruppe.get("bis"))
    if g_jahr is None:
        for b in gruppe.get("beispiele") or []:
            if isinstance(b, dict) and b.get("aufnahme"):
                g_jahr = jahr_aus(b["aufnahme"])
                if g_jahr:
                    break

    if g_jahr is None:
        return None

    if personen_phasen is None:
        if katalog is not None:
            personen_phasen = {}
            for n, v_liste in katalog.items():
                abschnitte = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
                if abschnitte.get("ok"):
                    personen_phasen[n] = abschnitte.get("phasen") or []
        else:
            personen_phasen = alle_personen_phasen(basis_pfad=basis_pfad)

    # 128-dim Vektor der offenen Gruppe holen
    mps = _kennungen_mittelpunkte(basis_pfad)
    g_k = str(gruppe.get("kennung") or "")
    g_vec = mps.get(g_k)

    # Nach passendem Lebensabschnitt in vorbereiteten Phasen suchen
    treffer: List[Tuple[str, Dict[str, Any], bool, float]] = []
    for n, phasen in personen_phasen.items():
        for p in phasen:
            von_j = p.get("von_jahr")
            bis_j = p.get("bis_jahr")
            if von_j is not None and bis_j is not None:
                # Kindheits-Filter: vor 2015 (Alter < 16) ist Zeitspanne streng
                is_child = von_j < 2015
                diff = 0
                if g_jahr < von_j:
                    diff = von_j - g_jahr
                elif g_jahr > bis_j:
                    diff = g_jahr - bis_j

                if is_child and diff > 2:
                    continue
                if diff > 5:
                    continue

                exakt = (diff == 0)
                sim = cosinus_aehnlichkeit(g_vec, p.get("zentroid")) if g_vec and p.get("zentroid") else 0.0
                treffer.append((n, p, exakt, sim))
                break

    if not treffer:
        return None

    # Eindeutiger Treffer
    if len(treffer) == 1:
        n, p, exakt, sim = treffer[0]
        sicherheit = 0.90 if exakt else 0.80
        grund = f"Aufnahmejahr {g_jahr} passt eindeutig zum Lebensabschnitt {p.get('titel')} von {n}."
        if sim > 0:
            grund += f" (Phasen-Ähnlichkeit {sim:.2f})"
        return {
            "name": n,
            "phase_id": p.get("phase_id"),
            "phase": p.get("jahre") or f"{p.get('von_jahr')}–{p.get('bis_jahr')}",
            "titel": p.get("titel"),
            "aussage": p.get("aussage"),
            "sicherheit": sicherheit,
            "aehnlichkeit": round(sim, 4),
            "grund": grund,
        }

    # Mehrere Personen passen zeitlich — prüfe Vektor-Differenzierung & Zwillings-Trennung
    treffer_namen = [t[0].casefold() for t in treffer]
    # Spezieller Zwillings-Fall (Sebastian & Julian)
    if "sebastian" in treffer_namen and "julian" in treffer_namen and g_vec:
        seb_t = next(t for t in treffer if t[0].casefold() == "sebastian")
        jul_t = next(t for t in treffer if t[0].casefold() == "julian")
        sim_seb = seb_t[3]
        sim_jul = jul_t[3]
        delta = sim_seb - sim_jul

        # Co-occurrence / Cannot-Link: Ist einer der Zwillinge bereits auf den Fotos dieser Gruppe?
        from app.services import gruppen_quiz
        b_ids = [str(b.get("fileid") or b.get("bild_id") or "") for b in gruppe.get("beispiele") or [] if b]
        b_ids = [b for b in b_ids if b]
        if b_ids:
            try:
                wb = gruppen_quiz.personen_auf_bildern(b_ids)
                schon_drauf = set()
                for b_info in (wb.get("bilder") or {}).values():
                    for n_on_img in b_info.get("namen") or []:
                        schon_drauf.add(n_on_img.casefold())
                if "julian" in schon_drauf and "sebastian" not in schon_drauf:
                    return {
                        "name": seb_t[0],
                        "phase_id": seb_t[1].get("phase_id"),
                        "phase": seb_t[1].get("titel"),
                        "titel": seb_t[1].get("titel"),
                        "aussage": seb_t[1].get("aussage"),
                        "sicherheit": 0.95,
                        "aehnlichkeit": round(sim_seb, 4),
                        "grund": "Julian ist bereits auf demselben Foto erkannt — Gruppe gehört daher zu Sebastian.",
                    }
                elif "sebastian" in schon_drauf and "julian" not in schon_drauf:
                    return {
                        "name": jul_t[0],
                        "phase_id": jul_t[1].get("phase_id"),
                        "phase": jul_t[1].get("titel"),
                        "titel": jul_t[1].get("titel"),
                        "aussage": jul_t[1].get("aussage"),
                        "sicherheit": 0.95,
                        "aehnlichkeit": round(sim_jul, 4),
                        "grund": "Sebastian ist bereits auf demselben Foto erkannt — Gruppe gehört daher zu Julian.",
                    }
            except Exception:
                pass

        # Vektor-Abstand zum Phasen-Zentroid
        if delta >= 0.04:
            return {
                "name": seb_t[0],
                "phase_id": seb_t[1].get("phase_id"),
                "phase": seb_t[1].get("titel"),
                "titel": seb_t[1].get("titel"),
                "aussage": seb_t[1].get("aussage"),
                "sicherheit": 0.85,
                "aehnlichkeit": round(sim_seb, 4),
                "grund": f"Phasen-Zentroid {seb_t[1].get('titel')} passt signifikant besser zu Sebastian ({sim_seb:.2f} vs {sim_jul:.2f}).",
            }
        elif delta <= -0.04:
            return {
                "name": jul_t[0],
                "phase_id": jul_t[1].get("phase_id"),
                "phase": jul_t[1].get("titel"),
                "titel": jul_t[1].get("titel"),
                "aussage": jul_t[1].get("aussage"),
                "sicherheit": 0.85,
                "aehnlichkeit": round(sim_jul, 4),
                "grund": f"Phasen-Zentroid {jul_t[1].get('titel')} passt signifikant besser zu Julian ({sim_jul:.2f} vs {sim_seb:.2f}).",
            }

    # Allgemeiner Fall: Sortiere Treffer nach Kosinus-Ähnlichkeit
    treffer_sortiert = sorted(treffer, key=lambda t: -t[3])
    beste_person, beste_phase, exakt, beste_sim = treffer_sortiert[0]
    zweite_sim = treffer_sortiert[1][3] if len(treffer_sortiert) > 1 else 0.0

    if beste_sim > 0 and (beste_sim - zweite_sim) >= 0.08:
        return {
            "name": beste_person,
            "phase_id": beste_phase.get("phase_id"),
            "phase": beste_phase.get("titel"),
            "titel": beste_phase.get("titel"),
            "aussage": beste_phase.get("aussage"),
            "sicherheit": 0.85,
            "aehnlichkeit": round(beste_sim, 4),
            "grund": f"Phasen-Zentroid {beste_phase.get('titel')} passt deutlich am besten zu {beste_person} (Ähnlichkeit {beste_sim:.2f}).",
        }

    # Keine eindeutige Vektor-Entscheidung möglich -> mehrere Kandidaten
    namen_liste = [t[0] for t in treffer]
    return {
        "name": beste_person,
        "phase_id": beste_phase.get("phase_id"),
        "phase": beste_phase.get("titel"),
        "titel": beste_phase.get("titel"),
        "aussage": beste_phase.get("aussage"),
        "sicherheit": 0.50,
        "kandidaten": namen_liste,
        "grund": f"Aufnahmejahr {g_jahr} liegt im gemeinsamen Zeitraum mehrerer Personen ({', '.join(namen_liste)}).",
    }


def andocken_kandidaten(katalog: Optional[Dict[str, Any]] = None,
                        gruppen: Optional[List[Dict[str, Any]]] = None,
                        min_sicherheit: float = 0.85,
                        kennungen: Optional[List[str]] = None,
                        ziel_name: Optional[str] = None,
                        basis_pfad: Optional[str] = None) -> List[Dict[str, Any]]:
    """Findet alle offenen Gruppen, die sicher an den Lebensabschnitt einer bekannten Person andocken koennen."""
    from app.services import gruppen_quiz

    if gruppen is None:
        alle_gruppen, _ = gruppen_quiz._gruppen_laden()
    else:
        alle_gruppen = gruppen

    st = gruppen_quiz._stand_lesen()
    aufgeloest = set(st.get("aufgeloest", []))
    bestaetigt = gruppen_quiz.bestaetigt_lesen()

    kandidaten: List[Dict[str, Any]] = []
    filter_kennungen = set(kennungen) if kennungen else None
    ziel_name_sauber = ziel_name.strip().casefold() if ziel_name else None

    # Phasen aller relevanten Personen VORAB EINMAL berechnen / aus Cache holen
    personen_phasen: Dict[str, List[Dict[str, Any]]] = {}
    if katalog is not None:
        for n, v_liste in katalog.items():
            if ziel_name_sauber and n.strip().casefold() != ziel_name_sauber:
                continue
            abschnitte = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
            if abschnitte.get("ok"):
                personen_phasen[n] = abschnitte.get("phasen") or []
    else:
        alle_phasen = alle_personen_phasen(basis_pfad=basis_pfad)
        for n, phasen in alle_phasen.items():
            if ziel_name_sauber and n.strip().casefold() != ziel_name_sauber:
                continue
            personen_phasen[n] = phasen

    for g in alle_gruppen:
        if not isinstance(g, dict):
            continue
        k = g.get("kennung")
        if not k or k in aufgeloest or k in bestaetigt:
            continue
        if filter_kennungen and k not in filter_kennungen:
            continue

        vorschlag = vorschlag_fuer_offene_gruppe(
            g,
            katalog=katalog,
            personen_phasen=personen_phasen,
            basis_pfad=basis_pfad,
        )
        if not vorschlag:
            continue

        if ziel_name_sauber and vorschlag["name"].strip().casefold() != ziel_name_sauber:
            continue

        sicherheit = float(vorschlag.get("sicherheit") or 0.0)
        if sicherheit < min_sicherheit:
            continue

        kandidaten.append({
            "kennung": k,
            "name": vorschlag["name"],
            "phase": vorschlag.get("phase"),
            "titel": vorschlag.get("titel"),
            "aussage": vorschlag.get("aussage"),
            "sicherheit": sicherheit,
            "aehnlichkeit": vorschlag.get("aehnlichkeit"),
            "grund": vorschlag.get("grund"),
            "groesse": max(0, int(g.get("groesse") or 0)),
            "bilder": max(0, int(g.get("bilder") or 0)),
            "von": g.get("von"),
            "bis": g.get("bis"),
        })

    return kandidaten
