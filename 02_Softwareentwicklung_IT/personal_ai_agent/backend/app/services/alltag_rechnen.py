"""Alltagsprotokoll S2: Rechenteil (rein, ohne Modell, 03.11.2026).

Eine Nacht zählt zu dem Tag, an dem man aufwacht („Nacht zum 03.11."). Uhrzeiten
bleiben in der Ortszeit, die die Uhr mitgeliefert hat. Eine Sitzung, die tagsüber
(9–19 Uhr) beginnt und kürzer als 3 Stunden ist, gilt als Nickerchen.

Dazu (S2-Rest): Stundenbereiche auf Stunden verteilen, Nächte aus den Schlaf-Knöpfen,
letzter Stand und offene Stunden fürs Pop-up, fehlende Felder je Stunden-Eintrag.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional

from app.services.alltag_speicher import MAX_NACHT, zeit_lesen

WACH_STUFEN = ("wach", "aus_dem_bett")
NICKERCHEN_MAX_MIN = 180
NICKERCHEN_STUNDEN = range(9, 20)


def _minuten(beginn: Any, ende: Any) -> int:
    a, b = zeit_lesen(beginn), zeit_lesen(ende)
    if not a or not b or b <= a:
        return 0
    return int(round((b - a).total_seconds() / 60))


def nacht_auswerten(nacht: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Kennzahlen einer Schlafsitzung — ``None`` bei unlesbaren Zeiten."""
    beginn, ende = zeit_lesen(nacht.get("beginn")), zeit_lesen(nacht.get("ende"))
    if not beginn or not ende or ende <= beginn:
        return None
    dauer = _minuten(nacht["beginn"], nacht["ende"])
    phasen = [p for p in nacht.get("phasen") or [] if isinstance(p, dict)]
    summe = {"wach": 0, "leicht": 0, "tief": 0, "rem": 0}
    wach_phasen = 0
    for i, p in enumerate(phasen):
        minuten = _minuten(p.get("beginn"), p.get("ende"))
        stufe = p.get("stufe")
        if stufe in WACH_STUFEN:
            summe["wach"] += minuten
            # Wach am Anfang (Einschlafen) oder am Ende (Aufstehen) ist keine Wachphase.
            if 0 < i < len(phasen) - 1:
                wach_phasen += 1
        elif stufe in summe:
            summe[stufe] += minuten
    return {
        "quelle_kennung": nacht.get("quelle_kennung"),
        "nacht_zum": ende.date().isoformat(),
        "einschlafen": beginn.strftime("%H:%M"),
        "aufwachen": ende.strftime("%H:%M"),
        "dauer_min": dauer,
        "schlaf_min": dauer - summe["wach"],
        "wach_min": summe["wach"],
        "leicht_min": summe["leicht"],
        "tief_min": summe["tief"],
        "rem_min": summe["rem"],
        "wach_phasen": wach_phasen,
        "phasen_bekannt": bool(phasen),
        "nickerchen": beginn.hour in NICKERCHEN_STUNDEN and dauer < NICKERCHEN_MAX_MIN,
    }


def auswerten(naechte: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Alle lesbaren Sitzungen ausgewertet, nach Aufwachzeit sortiert."""
    erg = [a for a in (nacht_auswerten(n) for n in naechte or []) if a]
    return sorted(erg, key=lambda a: (a["nacht_zum"], a["aufwachen"]))


def zusammenfassung(naechte: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Durchschnitt und Extreme über die Nächte (Nickerchen getrennt gezählt)."""
    alle = auswerten(naechte)
    nur_naechte = [a for a in alle if not a["nickerchen"]]
    if not nur_naechte:
        return {"naechte": 0, "nickerchen": len(alle)}
    schlaf = [a["schlaf_min"] for a in nur_naechte]
    return {
        "naechte": len(nur_naechte),
        "nickerchen": len(alle) - len(nur_naechte),
        "schnitt_schlaf_min": round(sum(schlaf) / len(schlaf)),
        "schnitt_tief_min": round(sum(a["tief_min"] for a in nur_naechte) / len(nur_naechte)),
        "kuerzeste": min(nur_naechte, key=lambda a: a["schlaf_min"]),
        "laengste": max(nur_naechte, key=lambda a: a["schlaf_min"]),
    }


def dauer_text(minuten: int) -> str:
    std, rest = divmod(max(0, int(minuten)), 60)
    if std and rest:
        return f"{std} Std. {rest} Min."
    return f"{std} Std." if std else f"{rest} Min."


def _datum_de(iso: str) -> str:
    j, m, t = iso.split("-")
    return f"{t}.{m}.{j}"


def nacht_zeile(a: Dict[str, Any]) -> str:
    art = "Nickerchen am" if a["nickerchen"] else "Nacht zum"
    teile = [f"{art} {_datum_de(a['nacht_zum'])}: {a['einschlafen']}–{a['aufwachen']}, "
             f"Schlaf {dauer_text(a['schlaf_min'])}"]
    if a["phasen_bekannt"]:
        teile.append(f" (Tiefschlaf {dauer_text(a['tief_min'])}, REM {dauer_text(a['rem_min'])}, "
                     f"leicht {dauer_text(a['leicht_min'])})")
        teile.append(f", {a['wach_phasen']}× wach, {dauer_text(a['wach_min'])} wach gesamt")
    return "".join(teile)


def schlaf_text(naechte: List[Dict[str, Any]]) -> str:
    """Klartext für Chat und Oberfläche."""
    alle = auswerten(naechte)
    if not alle:
        return ("Keine Schlafdaten im Zeitraum. Die Uhr liefert sie über Health Connect an Hey Agent; "
                "die App überträgt sie beim Öffnen.")
    zeilen = [nacht_zeile(a) for a in alle]
    z = zusammenfassung(naechte)
    if z["naechte"] > 1:
        zeilen.append(f"Schnitt über {z['naechte']} Nächte: {dauer_text(z['schnitt_schlaf_min'])} Schlaf, "
                      f"davon {dauer_text(z['schnitt_tief_min'])} Tiefschlaf; kürzeste Nacht zum "
                      f"{_datum_de(z['kuerzeste']['nacht_zum'])} ({dauer_text(z['kuerzeste']['schlaf_min'])}), "
                      f"längste zum {_datum_de(z['laengste']['nacht_zum'])} "
                      f"({dauer_text(z['laengste']['schlaf_min'])}).")
    return "\n".join(zeilen)


# ── Stunden verteilen ──────────────────────────────────────────────────────

def _lokal(zeit: datetime, zone: Optional[tzinfo]) -> datetime:
    """In ``zone`` umrechnen; ohne Zone gilt die Systemzeit (kennt die Zeitumstellung)."""
    return zeit.astimezone(zone) if zone is not None else zeit.astimezone()


def stunden_verteilen(von: Any, bis: Any, zone: Optional[tzinfo] = None) -> List[str]:
    """Jede angebrochene Stunde in ``[von, bis)`` als Ortszeit ``JJJJ-MM-TTTHH:00±HH:MM``.

    Gezählt wird in echten Stunden: Bei der Rückstellung erscheint 02:00 zweimal
    (einmal mit +02:00, einmal mit +01:00) — beide Stunden wurden erlebt.
    """
    a, b = zeit_lesen(von), zeit_lesen(bis)
    if not a or not b or b <= a:
        return []
    schritt = _lokal(a, zone).replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    ende = b.astimezone(timezone.utc)
    stunden: List[str] = []
    while schritt < ende:
        stunden.append(_lokal(schritt, zone).isoformat(timespec="minutes"))
        schritt += timedelta(hours=1)
    return stunden


# ── Schlaf aus den Knöpfen ─────────────────────────────────────────────────

def _nacht_abschliessen(beginn: datetime, ende: Optional[datetime], wach_min: int,
                        wach_phasen: int) -> Dict[str, Any]:
    dauer = int(round((ende - beginn).total_seconds() / 60)) if ende else 0
    return {
        "beginn": beginn.isoformat(timespec="seconds"),
        "ende": ende.isoformat(timespec="seconds") if ende else None,
        "nacht_zum": ende.date().isoformat() if ende else None,
        "dauer_min": dauer,
        "wach_min": wach_min if ende else 0,
        "schlaf_min": max(0, dauer - wach_min) if ende else 0,
        "wach_phasen": wach_phasen if ende else 0,
        "offen": ende is None,
    }


def schlaf_aus_ereignissen(ereignisse: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nächte aus „Ich gehe schlafen / Kann nicht schlafen / Gehe wieder schlafen / Ich wache auf".

    Reihenfolge der Eingabe egal (nach Zeit sortiert). Verirrte Knöpfe (aufwachen ohne
    Schlaf, wieder_schlafen ohne Wachliegen, doppeltes schlafen) werden ignoriert. Liegt ein
    neues „schlafen" mehr als 24 Stunden nach dem Beginn, bleibt die alte Nacht offen
    (Aufwachen vergessen) und eine neue beginnt. Wachliegen bis zum Aufstehen zählt als wach.
    """
    zeitlich = []
    for e in ereignisse or []:
        if not isinstance(e, dict):
            continue
        zeit = zeit_lesen(e.get("zeit"))
        if zeit:
            zeitlich.append((zeit, e.get("ereignis")))
    zeitlich.sort(key=lambda z: z[0])

    naechte: List[Dict[str, Any]] = []
    beginn: Optional[datetime] = None
    wach_seit: Optional[datetime] = None
    wach_min = wach_phasen = 0

    def wach_beenden(bis: datetime) -> None:
        nonlocal wach_seit, wach_min
        if wach_seit is not None:
            wach_min += int(round((bis - wach_seit).total_seconds() / 60))
            wach_seit = None

    for zeit, ereignis in zeitlich:
        if ereignis == "schlafen":
            if beginn is None:
                beginn, wach_min, wach_phasen = zeit, 0, 0
            elif zeit - beginn > MAX_NACHT:
                naechte.append(_nacht_abschliessen(beginn, None, 0, 0))
                beginn, wach_seit, wach_min, wach_phasen = zeit, None, 0, 0
            elif wach_seit is not None:
                wach_beenden(zeit)
        elif beginn is None:
            continue
        elif ereignis == "wach_liegen" and wach_seit is None:
            wach_seit = zeit
            wach_phasen += 1
        elif ereignis == "wieder_schlafen":
            wach_beenden(zeit)
        elif ereignis == "aufwachen":
            wach_beenden(zeit)
            naechte.append(_nacht_abschliessen(beginn, zeit, wach_min, wach_phasen))
            beginn = None
    if beginn is not None:
        naechte.append(_nacht_abschliessen(beginn, None, 0, 0))
    return naechte


# ── Letzter Stand und offene Stunden (für das Pop-up) ──────────────────────

SCHLAEFT_EREIGNISSE = ("schlafen", "wach_liegen", "wieder_schlafen")


def letzter_stand(eintraege: List[Dict[str, Any]], jetzt: Optional[datetime] = None) -> Dict[str, Any]:
    """``{"letzter_eintrag": ISO | None, "schlaeft": bool}`` aus Stunden-, Schlaf- und Uhr-Einträgen.

    Zeitpunkt eines Stunden-Eintrags ist ``bis`` (sonst ``von``), eines Schlaf-Ereignisses ``zeit``,
    einer Uhr-Nacht ``ende`` (S9: die Nacht deckt ihre Stunden; ein künftiges Ende zählt nicht).
    ``schlaeft`` gilt, wenn das letzte Ereignis ein Schlaf-Knopf der Nacht ist und höchstens
    24 Stunden zurückliegt — ein späterer Stunden-Eintrag beendet den Schlaf.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    letzter: Optional[tuple] = None
    for e in eintraege or []:
        if not isinstance(e, dict):
            continue
        if e.get("art") == "stunde":
            roh = e.get("bis") or e.get("von")
        elif e.get("art") == "schlaf":
            roh = e.get("zeit")
        elif e.get("art") == "schlafnacht":
            roh = e.get("ende")
        else:
            continue
        zeit = zeit_lesen(roh)
        if e.get("art") == "schlafnacht" and zeit and zeit > jetzt:
            continue
        # Gleiche Zeit (Schnellknöpfe in derselben Sekunde): der später erfasste gewinnt,
        # bei gleicher Erfassungssekunde der spätere in der Liste (Reihenfolge der Datei).
        rang = (zeit, str(e.get("erfasst_um") or ""))
        if zeit and (letzter is None or rang >= letzter[0]):
            letzter = (rang, roh, e)
    if letzter is None:
        return {"letzter_eintrag": None, "schlaeft": False}
    (zeit, _), roh, e = letzter
    schlaeft = (e.get("art") == "schlaf" and e.get("ereignis") in SCHLAEFT_EREIGNISSE
                and jetzt - zeit <= MAX_NACHT)
    return {"letzter_eintrag": roh, "schlaeft": bool(schlaeft)}


def offene_stunden(letzter_eintrag: Any, jetzt: datetime, schlaeft: bool) -> int:
    """Volle Stunden seit dem letzten Eintrag; im Schlaf 0; ohne jeden Eintrag 1."""
    if schlaeft:
        return 0
    zeit = zeit_lesen(letzter_eintrag)
    if zeit is None:
        return 1
    rest = jetzt - zeit
    if rest <= timedelta(0):
        return 0
    return int(rest // timedelta(hours=1))


# ── Fehlende Felder je Stunden-Eintrag ─────────────────────────────────────

def _zahl_im_bereich(wert: Any, unten: float, oben: float) -> bool:
    return (isinstance(wert, (int, float)) and not isinstance(wert, bool)
            and unten <= wert <= oben)


def fehlende_felder(eintrag: Dict[str, Any]) -> List[str]:
    """Felder, nach denen die Rückfrage-Einblendung fragt (Stimmung 1–5, Anspannung 0–100).

    Ungültige Werte zählen als fehlend. Schlaf-Ereignisse haben keine Rückfragen. Essen
    fehlt bewusst: im Plan noch offen (Hermes, Runde 1, Punkt D).
    """
    if not isinstance(eintrag, dict) or eintrag.get("art") != "stunde":
        return []
    fehlt: List[str] = []
    if not _zahl_im_bereich(eintrag.get("stimmung"), 1, 5):
        fehlt.append("stimmung")
    if not _zahl_im_bereich(eintrag.get("anspannung"), 0, 100):
        fehlt.append("anspannung")
    gefuehle = eintrag.get("gefuehle")
    if not (isinstance(gefuehle, list)
            and any(isinstance(g, str) and g.strip() for g in gefuehle)):
        fehlt.append("gefuehle")
    aktivitaet = eintrag.get("aktivitaet")
    if not (isinstance(aktivitaet, str) and aktivitaet.strip()):
        fehlt.append("aktivitaet")
    return fehlt
