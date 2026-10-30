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

    # Wenn kein Katalog übergeben wurde: benannte Personen aus dem Quiz prüfen
    if katalog is None:
        from app.services import gruppen_quiz
        bestaetigt = gruppen_quiz.bestaetigt_lesen()
        namen_kandidaten = sorted(set(bestaetigt.values()))
    else:
        namen_kandidaten = list(katalog.keys())

    # Nach passendem Lebensabschnitt suchen
    for n in namen_kandidaten:
        v_liste = katalog.get(n) if katalog else None
        abschnitte = lebensabschnitte_fuer_person(n, vorschlaege=v_liste, basis_pfad=basis_pfad)
        if not abschnitte.get("ok"):
            continue
        for p in abschnitte.get("phasen") or []:
            von_j = p.get("von_jahr")
            bis_j = p.get("bis_jahr")
            if von_j is not None and bis_j is not None:
                # Toleranz von 1 Jahr für nahtlose Übergänge
                if (von_j - 1) <= g_jahr <= (bis_j + 1):
                    return {
                        "name": n,
                        "phase_id": p.get("phase_id"),
                        "titel": p.get("titel"),
                        "grund": f"Aufnahmejahr {g_jahr} passt zum Lebensabschnitt {p.get('titel')} von {n}.",
                    }

    return None
