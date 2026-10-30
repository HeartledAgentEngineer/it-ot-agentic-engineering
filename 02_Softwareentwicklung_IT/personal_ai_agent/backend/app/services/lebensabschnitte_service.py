"""Lebensabschnitte und belegbare Aussagen (On-Device, 30.10.2026).

Warum dieses Modul:
  Sebastian benennt Personen im Gruppen-Quiz und im Bildeditor am Smartphone.
  Bisher wurden alle Gesichter einer Person als ungeordneter Block dargestellt.
  Dieses Modul strukturiert die Gesichter und Gruppen einer Person am Smartphone
  in chronologische Lebensabschnitte (Phasen nach Jahren), leitet belegbare
  Aussagen über Zeiträume und Begleitpersonen ab und liefert Vorschläge für
  offene Gruppen auf dem Gerät.

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
# Maximale Zeitspanne einer Phase in Jahren, bevor bei vorhandener Lücke getrennt wird
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
        if luecke > PHASEN_LUECKE_MAX or (spanne > PHASEN_SPANNE_MAX and luecke > 1):
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


def begleiter_aus_beziehungen(name: str, von_jahr: Optional[int], bis_jahr: Optional[int],
                              basis_pfad: Optional[str] = None) -> List[str]:
    """Findet häufige Begleitpersonen aus beziehungen.jsonl im Zeitraum."""
    pfad = os.path.join(_basis_ordner(basis_pfad), "beziehungen.jsonl")
    if not os.path.isfile(pfad):
        return []

    treffer: Counter = Counter()
    sauber_name = name.casefold()

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

                d_jahr = jahr_aus(e.get("datum"))
                if von_jahr is not None and d_jahr is not None and d_jahr < von_jahr:
                    continue
                if bis_jahr is not None and d_jahr is not None and d_jahr > bis_jahr:
                    continue

                personen = e.get("personen")
                if not isinstance(personen, list):
                    continue

                namen_in_zeile = [
                    str(p.get("name") or "").strip()
                    for p in personen
                    if isinstance(p, dict) and p.get("name")
                ]

                ist_dabei = any(n.casefold() == sauber_name for n in namen_in_zeile)
                if ist_dabei:
                    for n in namen_in_zeile:
                        if n.casefold() != sauber_name:
                            treffer[n] += 1
    except Exception as fehler:
        logger.warning("Begleiter-Suche für %s fehlgeschlagen: %s", name, fehler)
        return []

    return [p for p, _c in treffer.most_common(3)]


def lebensabschnitte_fuer_person(name: str,
                                 vorschlaege: Optional[List[Dict[str, Any]]] = None,
                                 profil_daten: Optional[Dict[str, Any]] = None,
                                 basis_pfad: Optional[str] = None) -> Dict[str, Any]:
    """Berechnet die chronologischen Lebensabschnitte und Aussagen für eine Person."""
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
            })

    gesamt_gesichter = sum(max(0, int(v.get("groesse") or 0)) for v in vorschlaege if isinstance(v, dict))

    if not alle_jahre:
        # Keine Jahresangaben bekannt: 1 unbestimmte Phase
        phase = {
            "phase_id": "phase-unbekannt",
            "von_jahr": None,
            "bis_jahr": None,
            "von": None,
            "bis": None,
            "titel": "Aufnahmen ohne Datum",
            "alters_hinweis": None,
            "gesichter_anzahl": gesamt_gesichter,
            "beispiele": [b["beispiel"] for b in belege if b["beispiel"]][:6],
            "begleiter": begleiter_aus_beziehungen(echter_name, None, None, basis_pfad),
            "aussage": f"{gesamt_gesichter} Bild(er) ohne bekanntes Aufnahmedatum.",
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

    gefundene_phasen_spannen = phasen_bilden_jahre(alle_jahre)
    phasen_liste: List[Dict[str, Any]] = []

    for von_j, bis_j in gefundene_phasen_spannen:
        passende_belege = [b for b in belege if b["jahr"] and von_j <= b["jahr"] <= bis_j]
        # Beispiele für diese Phase
        phasen_beispiele = [b["beispiel"] for b in passende_belege if b["beispiel"]][:6]

        # Wenn keine konkreten Beispiele vorhanden, Gesichterzahl aus Belegen summieren
        anzahl = sum(
            (b.get("groesse", 1) if b["beispiel"] is None else 1)
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

        satz = f"{zeit_teil} auf {anzahl} Foto(s) festgehalten"
        if begleiter:
            satz += f", am häufigsten zusammen mit {', '.join(begleiter[:2])}"
        satz += "."
        saetze.append(satz)

        phasen_liste.append({
            "phase_id": f"phase-{von_j}-{bis_j}",
            "von_jahr": von_j,
            "bis_jahr": bis_j,
            "von": f"{von_j}-01-01",
            "bis": f"{bis_j}-12-31",
            "titel": titel,
            "alters_hinweis": alter_text,
            "gesichter_anzahl": anzahl,
            "beispiele": phasen_beispiele,
            "begleiter": begleiter,
            "aussage": " ".join(saetze),
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


def vorschlag_fuer_offene_gruppe(gruppe: Dict[str, Any],
                                 katalog: Optional[Dict[str, Any]] = None,
                                 personen_phasen: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                                 basis_pfad: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Prüft, ob eine unbenannte Gruppe zeitlich in den Lebensabschnitt einer bekannten Person passt."""
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
        personen_phasen = {}
        if katalog is None:
            from app.services import gruppen_quiz
            bestaetigt = gruppen_quiz.bestaetigt_lesen()
            namen_kandidaten = sorted(set(bestaetigt.values()))
            for n in namen_kandidaten:
                abschnitte = lebensabschnitte_fuer_person(n, basis_pfad=basis_pfad)
                if abschnitte.get("ok"):
                    personen_phasen[n] = abschnitte.get("phasen") or []
        else:
            for n, v_liste in katalog.items():
                abschnitte = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
                if abschnitte.get("ok"):
                    personen_phasen[n] = abschnitte.get("phasen") or []

    # Nach passendem Lebensabschnitt in vorbereiteten Phasen suchen
    treffer: List[Tuple[str, Dict[str, Any], bool]] = []
    for n, phasen in personen_phasen.items():
        for p in phasen:
            von_j = p.get("von_jahr")
            bis_j = p.get("bis_jahr")
            if von_j is not None and bis_j is not None:
                exakt = von_j <= g_jahr <= bis_j
                if exakt or (von_j - 1) <= g_jahr <= (bis_j + 1):
                    treffer.append((n, p, exakt))
                    break

    if not treffer:
        return None

    if len(treffer) == 1:
        n, p, exakt = treffer[0]
        sicherheit = 0.90 if exakt else 0.80
        return {
            "name": n,
            "phase_id": p.get("phase_id"),
            "phase": p.get("jahre") or f"{p.get('von_jahr')}–{p.get('bis_jahr')}",
            "titel": p.get("titel"),
            "aussage": p.get("aussage"),
            "sicherheit": sicherheit,
            "grund": f"Aufnahmejahr {g_jahr} passt eindeutig zum Lebensabschnitt {p.get('titel')} von {n}.",
        }

    # Mehrere Personen kommen für dieses Jahr in Frage (bei Unsicherheit lieber offenlassen)
    namen_liste = [t[0] for t in treffer]
    erste_person, erste_phase, exakt = treffer[0]
    return {
        "name": erste_person,
        "phase_id": erste_phase.get("phase_id"),
        "phase": erste_phase.get("jahre") or f"{erste_phase.get('von_jahr')}–{erste_phase.get('bis_jahr')}",
        "titel": erste_phase.get("titel"),
        "aussage": erste_phase.get("aussage"),
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

    # Phasen aller relevanten Personen VORAB EINMAL berechnen:
    personen_phasen: Dict[str, List[Dict[str, Any]]] = {}
    if katalog is not None:
        for n, v_liste in katalog.items():
            if ziel_name_sauber and n.strip().casefold() != ziel_name_sauber:
                continue
            abschnitte = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
            if abschnitte.get("ok"):
                personen_phasen[n] = abschnitte.get("phasen") or []
    else:
        namen_kandidaten = sorted(set(bestaetigt.values()))
        for n in namen_kandidaten:
            if ziel_name_sauber and n.strip().casefold() != ziel_name_sauber:
                continue
            abschnitte = lebensabschnitte_fuer_person(n, basis_pfad=basis_pfad)
            if abschnitte.get("ok"):
                personen_phasen[n] = abschnitte.get("phasen") or []

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
            "grund": vorschlag.get("grund"),
            "groesse": max(0, int(g.get("groesse") or 0)),
            "bilder": max(0, int(g.get("bilder") or 0)),
            "von": g.get("von"),
            "bis": g.get("bis"),
        })

    return kandidaten
