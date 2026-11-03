"""Alltagsprotokoll S2: Rechenteil für Schlafnächte (rein, ohne Modell, 03.11.2026).

Eine Nacht zählt zu dem Tag, an dem man aufwacht („Nacht zum 03.11."). Uhrzeiten
bleiben in der Ortszeit, die die Uhr mitgeliefert hat. Eine Sitzung, die tagsüber
(9–19 Uhr) beginnt und kürzer als 3 Stunden ist, gilt als Nickerchen.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.alltag_speicher import zeit_lesen

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
