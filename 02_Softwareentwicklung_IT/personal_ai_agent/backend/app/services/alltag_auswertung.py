"""Alltagsprotokoll S8: Auswertung fürs Chat-Werkzeug ``alltag_abfragen`` (rein, ohne Modell, 03.11.2026).

Das Ergebnis eines Werkzeugs geht als Text an das Sprachmodell (OpenRouter ZDR). Deshalb:

* ``originalworte`` (der eigene Satz) geht **nie** hinaus.
* Freitexte (Tätigkeit, eigene Gefühlsworte) nur geschwärzt: jeder bekannte Name wird zu
  „[Name]“ und nicht zurückübersetzt. Ohne lesbare Namensliste fallen die Freitexte ganz weg
  (fail-closed, wie die Glättung).
* Gefühle aus der festen Liste (``GRUNDGEFUEHLE``), Stimmung, Anspannung und Zeiten sind keine
  Namen und gehen unverändert hinaus.

Dazu die Verknüpfung mit dem Schlaf der Uhr: Stimmung und Anspannung nach den kürzeren und
nach den längeren Nächten (Teilung am Median). Nur ein Zusammenhang, keine Bewertung.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from app.services.alltag_rechnen import auswerten, dauer_text, nacht_zeile
from app.services.alltag_speicher import zeit_lesen
from app.services.alltag_struktur import GRUNDGEFUEHLE, STIMMUNG

Schwaerzer = Callable[[str], str]

STIMMUNG_WORT = dict(STIMMUNG)
MIN_TAGE_VERGLEICH = 4
_KUERZEL_NAME = re.compile(r"\[PERSON_\d+\]")
_KUERZEL_KONTAKT = re.compile(r"\[(EMAIL|PHONE)_\d+\]")


def schwaerzer(namen: Optional[Iterable[str]]) -> Optional[Schwaerzer]:
    """Text → Text mit „[Name]“ statt jedes bekannten Namens; ``None`` ohne Namensliste."""
    liste = [n for n in (namen or []) if isinstance(n, str) and n.strip()]
    if not liste:
        return None
    from app.services.pii_shield import schild_aus_namen

    schild = schild_aus_namen(liste)
    return lambda text: _KUERZEL_KONTAKT.sub("[Kontakt]", _KUERZEL_NAME.sub("[Name]", schild.encode(text or "")))


def _zahl(wert: Any, unten: float, oben: float) -> Optional[float]:
    if isinstance(wert, (int, float)) and not isinstance(wert, bool) and unten <= wert <= oben:
        return float(wert)
    return None


def _komma(wert: float) -> str:
    return f"{wert:.1f}".replace(".", ",")


def _datum_de(iso: str) -> str:
    j, m, t = iso.split("-")
    return f"{t}.{m}.{j}"


def _gefuehl_liste(e: Dict[str, Any]) -> List[Any]:
    """Gefühle nur als Liste — ein Text würde sonst in Buchstaben zerfallen."""
    roh = e.get("gefuehle")
    return roh if isinstance(roh, list) else []


def _gefuehle(e: Dict[str, Any], schwaerzen: Optional[Schwaerzer]) -> List[str]:
    erg = []
    for g in _gefuehl_liste(e):
        if not isinstance(g, str) or not g.strip():
            continue
        if g in GRUNDGEFUEHLE:
            erg.append(g)
        elif schwaerzen is not None:
            erg.append(schwaerzen(g.strip()))
    return erg


def stunden_zeile(e: Dict[str, Any], schwaerzen: Optional[Schwaerzer]) -> str:
    """„03.11. 14:40–15:40 · Tätigkeit · Stimmung gut (4) · Anspannung 30 · Gefühle“."""
    von, bis = zeit_lesen(e.get("von")), zeit_lesen(e.get("bis"))
    kopf = von.strftime("%d.%m. %H:%M") if von else "?"
    if bis:
        kopf += "–" + bis.strftime("%H:%M")
    teile = [kopf]
    taetigkeit = str(e.get("aktivitaet") or "").strip()
    if taetigkeit and schwaerzen is not None:
        teile.append(schwaerzen(taetigkeit))
    stimmung = _zahl(e.get("stimmung"), 1, 5)
    if stimmung is not None:
        teile.append(f"Stimmung {STIMMUNG_WORT.get(int(stimmung), '')} ({int(stimmung)})")
    anspannung = _zahl(e.get("anspannung"), 0, 100)
    if anspannung is not None:
        teile.append(f"Anspannung {int(anspannung)}")
    gefuehle = _gefuehle(e, schwaerzen)
    if gefuehle:
        teile.append(", ".join(gefuehle))
    return " · ".join(teile)


def _tag(e: Dict[str, Any]) -> Optional[str]:
    zeit = zeit_lesen(e.get("von") or e.get("bis"))
    return zeit.date().isoformat() if zeit else None


def _schnitt(werte: List[float]) -> Optional[float]:
    return round(sum(werte) / len(werte), 1) if werte else None


def tag_kennzahlen(stunden: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Je Tag: Anzahl Einträge, Schnitt von Stimmung/Anspannung, häufigste Grundgefühle."""
    roh: Dict[str, Dict[str, Any]] = {}
    for e in stunden or []:
        tag = _tag(e) if isinstance(e, dict) else None
        if not tag:
            continue
        t = roh.setdefault(tag, {"eintraege": 0, "stimmung": [], "anspannung": [], "gefuehle": Counter()})
        t["eintraege"] += 1
        for feld, unten, oben in (("stimmung", 1, 5), ("anspannung", 0, 100)):
            wert = _zahl(e.get(feld), unten, oben)
            if wert is not None:
                t[feld].append(wert)
        t["gefuehle"].update(g for g in _gefuehl_liste(e) if isinstance(g, str) and g in GRUNDGEFUEHLE)
    return {tag: {"eintraege": t["eintraege"], "stimmung": _schnitt(t["stimmung"]),
                  "anspannung": _schnitt(t["anspannung"]), "gefuehle": t["gefuehle"].most_common(3)}
            for tag, t in sorted(roh.items())}


def _tageszeile(tag: str, k: Dict[str, Any]) -> str:
    teile = [f"{_datum_de(tag)}: {k['eintraege']} Eintrag" + ("" if k["eintraege"] == 1 else "e")]
    if k["stimmung"] is not None:
        teile.append(f"Stimmung im Schnitt {_komma(k['stimmung'])}")
    if k["anspannung"] is not None:
        teile.append(f"Anspannung {round(k['anspannung'])}")
    if k["gefuehle"]:
        teile.append("oft " + ", ".join(g for g, _ in k["gefuehle"]))
    return " · ".join(teile)


_SUMMEN = ("dauer_min", "schlaf_min", "wach_min", "leicht_min", "tief_min", "rem_min", "wach_phasen")


def _nacht_zusammen(teile: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Abschnitte einer Nacht addieren; jede Lücke zwischen zwei Abschnitten ist ein Aufwachen."""
    if len(teile) == 1:
        return teile[0]
    erg = dict(teile[-1])
    for feld in _SUMMEN:
        erg[feld] = sum(t[feld] for t in teile)
    erg["wach_phasen"] += len(teile) - 1
    erg["phasen_bekannt"] = all(t["phasen_bekannt"] for t in teile)
    return erg


def _ohne_doppelte(naechte: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Überlappende Sitzungen sind dieselbe Nacht aus zwei Quellen: nur die längere zählt.

    Aufeinanderfolgende Abschnitte (unterbrochene Nacht) überlappen nie und bleiben alle erhalten.
    """
    gelesen = []
    for n in naechte or []:
        beginn = zeit_lesen(n.get("beginn")) if isinstance(n, dict) else None
        ende = zeit_lesen(n.get("ende")) if isinstance(n, dict) else None
        if beginn and ende and ende > beginn:
            gelesen.append((beginn, ende, n))
    gelesen.sort(key=lambda g: g[0])
    erg: List[Tuple[Any, Any, Dict[str, Any]]] = []
    for beginn, ende, n in gelesen:
        if erg and beginn < erg[-1][1]:
            if ende - beginn > erg[-1][1] - erg[-1][0]:
                erg[-1] = (beginn, ende, n)
            continue
        erg.append((beginn, ende, n))
    return [n for _, _, n in erg]


def _nacht_und_tag(naechte: List[Dict[str, Any]], stunden: List[Dict[str, Any]],
                   nur_mit_phasen: bool = False) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """(Nacht, Tageskennzahlen) für jeden Tag mit Stimmung; die Nacht zählt zum Tag des Aufwachens.

    Mehrere Abschnitte zum selben Tag (unterbrochene Nacht) werden zu einer Nacht zusammengezählt;
    doppelt gemeldete (überlappende) Sitzungen zählen nur einmal.
    """
    teile: Dict[str, List[Dict[str, Any]]] = {}
    for a in auswerten(_ohne_doppelte(naechte)):
        if not a["nickerchen"]:
            teile.setdefault(a["nacht_zum"], []).append(a)
    nacht = {tag: n for tag, n in ((t, _nacht_zusammen(ts)) for t, ts in teile.items())
             if n["phasen_bekannt"] or not nur_mit_phasen}
    return [(nacht[tag], k) for tag, k in tag_kennzahlen(stunden).items()
            if tag in nacht and k["stimmung"] is not None]


def verknuepfung_text(naechte: List[Dict[str, Any]], stunden: List[Dict[str, Any]]) -> str:
    """Stimmung/Anspannung nach kürzeren und längeren Nächten (Nacht zählt zum Tag des Aufwachens)."""
    paare: List[Tuple[int, Dict[str, Any]]] = sorted(
        ((n["schlaf_min"], k) for n, k in _nacht_und_tag(naechte, stunden)), key=lambda p: p[0])
    if len(paare) < MIN_TAGE_VERGLEICH:
        return (f"Schlaf und Stimmung: Zu wenige Tage mit beidem für einen Vergleich "
                f"({len(paare)} von mindestens {MIN_TAGE_VERGLEICH}).")
    haelfte = len(paare) // 2
    kurz, lang = paare[:haelfte], paare[-haelfte:]

    def schnitt(gruppe: List[Tuple[int, Dict[str, Any]]], feld: str) -> Optional[float]:
        return _schnitt([k[feld] for _, k in gruppe if k[feld] is not None])

    text = (f"Schlaf und Stimmung ({len(paare)} Tage): Nach den kürzeren Nächten "
            f"(bis {dauer_text(kurz[-1][0])}) lag die Stimmung im Schnitt bei "
            f"{_komma(schnitt(kurz, 'stimmung'))}, nach den längeren bei {_komma(schnitt(lang, 'stimmung'))}.")
    a_kurz, a_lang = schnitt(kurz, "anspannung"), schnitt(lang, "anspannung")
    if a_kurz is not None and a_lang is not None:
        text += f" Anspannung im Schnitt {round(a_kurz)} gegenüber {round(a_lang)}."
    return text + " Nur ein Zusammenhang über wenige Tage, kein Beweis."


# ── S10: Tageszeiten und Schlafqualität (nur Zahlen, kein Freitext) ─────────

TAGESZEITEN = (("morgens", range(5, 12)), ("nachmittags", range(12, 17)),
               ("abends", range(17, 22)), ("nachts", (22, 23, 0, 1, 2, 3, 4)))
MIN_EINTRAEGE_TAGESZEIT = 4


def _mittel(werte: List[float]) -> float:
    """Schnitt einer nicht leeren Liste, eine Nachkommastelle."""
    return round(sum(werte) / len(werte), 1)


def tageszeit_text(stunden: List[Dict[str, Any]]) -> Optional[str]:
    """Stimmung und Anspannung je Tageszeit (Beginn des Eintrags, Ortszeit) — ``None`` bei zu wenig."""
    werte: Dict[str, Dict[str, List[float]]] = {name: {"stimmung": [], "anspannung": []} for name, _ in TAGESZEITEN}
    for e in stunden or []:
        von = zeit_lesen(e.get("von")) if isinstance(e, dict) else None
        if von is None:
            continue
        stimmung = _zahl(e.get("stimmung"), 1, 5)
        if stimmung is None:
            continue
        name = next(n for n, stunden_ in TAGESZEITEN if von.hour in stunden_)
        werte[name]["stimmung"].append(stimmung)
        anspannung = _zahl(e.get("anspannung"), 0, 100)
        if anspannung is not None:
            werte[name]["anspannung"].append(anspannung)
    belegt = [(n, w) for n, w in werte.items() if w["stimmung"]]
    if sum(len(w["stimmung"]) for _, w in belegt) < MIN_EINTRAEGE_TAGESZEIT or len(belegt) < 2:
        return None
    text = "Tageszeiten, Stimmung im Schnitt (Einträge): " + " · ".join(
        f"{n} {_komma(_mittel(w['stimmung']))} ({len(w['stimmung'])})" for n, w in belegt) + "."
    spannung = [f"{n} {round(_mittel(w['anspannung']))}" for n, w in belegt if w["anspannung"]]
    if spannung:
        text += " Anspannung: " + " · ".join(spannung) + "."
    return text


def schlafqualitaet_text(naechte: List[Dict[str, Any]], stunden: List[Dict[str, Any]]) -> Optional[str]:
    """Stimmung nach Tiefschlaf (Teilung am Median) und nach Nächten mit/ohne Aufwachen.

    Nur Nächte, für die die Uhr Schlafphasen geliefert hat. ``None``, wenn nichts zu vergleichen ist.
    """
    paare = sorted(_nacht_und_tag(naechte, stunden, nur_mit_phasen=True), key=lambda p: p[0]["tief_min"])
    saetze: List[str] = []
    if len(paare) >= MIN_TAGE_VERGLEICH:
        haelfte = len(paare) // 2
        wenig, viel = paare[:haelfte], paare[-haelfte:]
        saetze.append(
            f"Tiefschlaf und Stimmung ({len(paare)} Tage): Nach den Nächten mit weniger Tiefschlaf "
            f"(bis {dauer_text(wenig[-1][0]['tief_min'])}) lag die Stimmung im Schnitt bei "
            f"{_komma(_mittel([k['stimmung'] for _, k in wenig]))}, nach denen mit mehr bei "
            f"{_komma(_mittel([k['stimmung'] for _, k in viel]))}.")
    ruhig = [k["stimmung"] for n, k in paare if n["wach_phasen"] == 0]
    unruhig = [k["stimmung"] for n, k in paare if n["wach_phasen"] > 0]
    if len(ruhig) >= 2 and len(unruhig) >= 2:
        saetze.append(f"Ohne nächtliches Aufwachen ({len(ruhig)} Nächte) Stimmung im Schnitt "
                      f"{_komma(_mittel(ruhig))}, mit Aufwachen ({len(unruhig)} Nächte) "
                      f"{_komma(_mittel(unruhig))}.")
    if not saetze:
        return None
    return " ".join(saetze) + " Nur ein Zusammenhang, kein Beweis."


def protokoll_text(stunden: List[Dict[str, Any]], naechte: List[Dict[str, Any]],
                   schwaerzen: Optional[Schwaerzer], einzeln: bool) -> str:
    """Klartext fürs Chat-Werkzeug: einzelne Einträge (ein Tag) oder Tageszeilen (Zeitraum)."""
    stunden = [e for e in stunden or [] if isinstance(e, dict) and e.get("art") == "stunde"]
    if not stunden:
        return "Keine Einträge im Alltagsprotokoll für diesen Zeitraum."
    zeilen: List[str] = []
    if einzeln:
        zeilen += [nacht_zeile(a) for a in auswerten(naechte)]
        zeilen += [stunden_zeile(e, schwaerzen) for e in stunden]
    else:
        zeilen += [_tageszeile(tag, k) for tag, k in tag_kennzahlen(stunden).items()]
        zeilen.append(verknuepfung_text(naechte, stunden))
        zeilen += [t for t in (schlafqualitaet_text(naechte, stunden), tageszeit_text(stunden)) if t]
    if schwaerzen is None:
        zeilen.append("(Tätigkeiten und eigene Worte ausgeblendet: Namensliste nicht lesbar.)")
    return "\n".join(zeilen)
