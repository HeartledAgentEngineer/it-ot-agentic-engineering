"""Messwerkzeug: Verrauschen unsichere oder verpixelte Gesichter die Gruppenmittelpunkte?
(14.10.2026)

Anlass: Sebastians Frage vom 14.10.2026 (Wunschliste, Wisch-Sortierer Stufe 1):
"Verrauschen verpixelte Ausschnitte die Mittelwerte, also die Gruppenmittelpunkte und die
Lebensphasen?" Antwort und Messung gehoeren in den Plan - **dies ist die Messung**.

Dieses Werkzeug **misst nur**. Es rechnet keine Gruppen neu, aendert keine Schwelle, oeffnet
kein Bild, ruft kein Netz und **schreibt nichts** (Bericht nur auf der Konsole).

Was gemessen wird (auf den echten Vektoren, je Gruppe):

1. **Verschiebung des Mittelpunkts**, wenn die unsicheren (``score`` unter ``--min-score``,
   Standard 0,90) und die grob aufgeloesten Ausschnitte (Breite in Pixeln unter
   ``--min-breite``, Standard 64) weggelassen werden. Mass ist die **Cosinus-Distanz**
   (``1 - Kosinus``).
2. **Neuordnung:** wie viele der sauberen Gesichter unter den sauberen Mittelpunkten eine
   **andere** Gruppe als unter allen Mittelpunkten bekaemen (naechster Mittelpunkt).
3. **Dasselbe je Aufnahmejahr** (Lebensphase) - nur fuer Gruppen, die in einem Jahr genug
   Gesichter haben.
4. **Reihenfolge fuer den Wisch-Sortierer (Stufe 1):** wie viele **saubere** Gesichter jede
   Gruppe hat, in Stufen (kein sauberes, 1 bis 2, 3 bis 9, 10 oder mehr) und die Gruppen
   **schlechteste zuerst** - der Vorschlag, wonach sich der Sortierer richten soll (die Zahl
   der brauchbaren Gesichter, nicht die Gruppengroesse).

Ein **Mittelpunkt** ist der normierte Mittelwert der normierten Gesichtsvektoren (Richtung,
nicht Laenge) - dieselbe Cosinus-Welt wie ``personen_cluster``.

Eingabe (nur lesend):

* Vektorzeilen im Format von ``gesicht_erkennen.py`` / ``video_gesichter.py`` (JSONL je Bild:
  ``bild_id``, ``gesichter[].bbox/score/embedding``).
* Die Zuordnung ``personen_gruppen/gesicht_zuordnung.jsonl`` (Gesicht -> Kennung).

Verbunden wird ueber ``(bild_id, index)``; bei doppelter Kennung gewinnt die **erste** Datei
(wie ``personen_gruppieren``). Video-Zeilen tragen dieselbe Form (``<fileid>#t=4.0``) und
werden mitgezaehlt.

Ausgabe: **nur Zahlen und Kennungen** (``Person_0123``) - keine Namen, keine Bild-IDs, keine
Koordinaten.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\mittelpunkt_rauschen_messen.py

Fuer einen Lauf genuegen Zahlen; nichts davon geht an ein fremdes Modell.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "personen_gruppen", "gesicht_zuordnung.jsonl")
STANDARD_VEKTOREN = tuple(os.path.join(STANDARD_BASIS, name) for name in (
    "personen_vektoren_n0929_voll.jsonl",
    "personen_vektoren_n0929_bildervideos.jsonl",
    "personen_vektoren_fotobuch.jsonl",
    "personen_vektoren_gedreht_neu.jsonl",
    "personen_vektoren_papa.jsonl",
    "video_vektoren_bildervideos.jsonl",
    "video_vektoren_upload.jsonl",
))
MIN_SCORE = 0.90      # ab hier gilt ein Fund als sicher
MIN_BREITE = 64       # Ausschnittbreite in Pixeln; darunter ist die Nahansicht grob aufgeloest
GRUPPE_MIN = 30       # kleinere Gruppen werden nicht einzeln bewertet
PHASE_MIN = 20        # Gesichter je Gruppe UND Jahr, damit eine Lebensphase zaehlt
STUECK = 8192         # Zeilen je Rechenblock (Speicher)
# Stufen fuer die Wisch-Sortierer-Reihenfolge: (untere Grenze, obere Grenze ohne, Name)
SAUBER_STUFEN = ((0, 1, "kein sauberes Gesicht"), (1, 3, "1 bis 2 saubere"),
                 (3, 10, "3 bis 9 saubere"), (10, None, "10 oder mehr saubere"))


# ── 1. Lesen (lokal, nur lesend, kein Netz, kein Bild) ───────────────────────

def jsonl_lesen(pfad: str):
    """Zeilen einer JSONL-Datei als Dicts; kaputte Zeilen fallen weg."""
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                daten = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(daten, dict):
                yield daten


def zuordnung_lesen(pfad: str) -> tuple:
    """``(gesichter, ohne_kennung)`` aus der Zuordnungsdatei.

    ``gesichter`` ist ``{(bild_id, index): {...}}`` - nur Zeilen MIT Kennung (die Gesichter
    also, die in einer Gruppe stehen). Fehlt die Datei, gibt es eine Klartextmeldung (Exit 2
    in ``main``), es wird nichts geraten.
    """
    gesichter: dict = {}
    ohne = 0
    for zeile in jsonl_lesen(pfad):
        kennung = zeile.get("kennung")
        if not kennung:
            ohne += 1
            continue
        bild_id = zeile.get("bild_id")
        index = zeile.get("index")
        if bild_id is None or not isinstance(index, int):
            ohne += 1
            continue
        bbox = zeile.get("bbox") or []
        breite_px = bbox[2] if len(bbox) > 2 else None
        gesichter[(str(bild_id), int(index))] = {
            "kennung": str(kennung),
            "score": zeile.get("score") if isinstance(zeile.get("score"), (int, float)) else None,
            "breite_px": breite_px if isinstance(breite_px, (int, float)) else None,
            "anteil": zeile.get("anteil") if isinstance(zeile.get("anteil"), (int, float)) else None,
            "aufnahme": zeile.get("aufnahme"),
            "video": bool(zeile.get("video_id")),
        }
    return gesichter, ohne


def vektoren_sammeln(pfade, schluessel=None) -> tuple:
    """Vektoren aus Vektorzeilen einsammeln - **nur** die Schluessel aus ``schluessel``.

    ``schluessel`` ist eine Menge ``(bild_id, index)`` (``None`` = alles behalten). Ein
    doppelter Schluessel wird nicht ueberschrieben (die erste Datei gewinnt, wie
    ``personen_gruppieren``). Zeilen ohne erkennbares Gesicht, ohne Liste ``embedding``, mit
    falscher Laenge oder mit defektem JSON zaehlen in den Zaehlern und brechen nichts ab.

    Rueckgabe ``(vektoren, statistik)`` mit ``vektoren[(bild_id, index)] = np.ndarray`` in
    ``float32``.
    """
    vektoren: dict = {}
    masse: int | None = None
    statistik = {"dateien": 0, "fehlend": 0, "zeilen": 0, "defekt": 0, "gesichter": 0,
                 "behalten": 0, "fremde_laenge": 0, "gelesen": 0}
    for pfad in pfade:
        if not os.path.isfile(pfad):
            statistik["fehlend"] += 1
            continue
        statistik["dateien"] += 1
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                statistik["zeilen"] += 1
                try:
                    daten = json.loads(zeile)
                except ValueError:
                    statistik["defekt"] += 1
                    continue
                if not isinstance(daten, dict):
                    statistik["defekt"] += 1
                    continue
                bild_id = daten.get("bild_id")
                gesichter = daten.get("gesichter")
                if bild_id is None or not isinstance(gesichter, list):
                    continue
                for index, gesicht in enumerate(gesichter):
                    if not isinstance(gesicht, dict):
                        continue
                    statistik["gesichter"] += 1
                    schluessel_paar = (str(bild_id), index)
                    if schluessel is not None and schluessel_paar not in schluessel:
                        continue
                    if schluessel_paar in vektoren:
                        continue
                    werte = gesicht.get("embedding")
                    if not isinstance(werte, list) or not werte:
                        continue
                    if masse is None:
                        masse = len(werte)
                    if len(werte) != masse:
                        statistik["fremde_laenge"] += 1
                        continue
                    try:
                        vektoren[schluessel_paar] = np.asarray(werte, dtype=np.float32)
                    except (TypeError, ValueError):
                        statistik["defekt"] += 1
                        continue
                    statistik["behalten"] += 1
    statistik["gelesen"] = len(vektoren)
    statistik["masse"] = masse
    return vektoren, statistik


# ── 2. Rechnen (normierte Richtung, Cosinus) ─────────────────────────────────

def einheitsvektor(vektor):
    """Vektor auf Laenge 1 bringen; ein Nullvektor bleibt ``None``."""
    laenge = float(np.linalg.norm(vektor))
    if laenge == 0.0:
        return None
    return vektor / laenge


def mittelpunkt(vektoren):
    """Normierter Mittelwert normierter Vektoren (Richtung); leer -> ``None``."""
    if len(vektoren) == 0:
        return None
    stapel = np.asarray(vektoren, dtype=np.float32)
    normen = np.linalg.norm(stapel, axis=1)
    brauchbar = stapel[normen > 0]
    if brauchbar.shape[0] == 0:
        return None
    return einheitsvektor(brauchbar.mean(axis=0))


def winkel(a, b) -> float:
    """Cosinus-Distanz zweier Richtungen (``1 - Kosinus``), gekappt auf [0, 2]."""
    if a is None or b is None:
        return 0.0
    wert = 1.0 - float(np.dot(a, b))
    return max(0.0, min(2.0, wert))


def sauber(gesicht, min_score: float = MIN_SCORE, min_breite: float = MIN_BREITE) -> bool:
    """Ist das Gesicht sicher UND nicht grob aufgeloest?

    Unsicher = ``score`` fehlt oder liegt unter ``min_score``. Grob = die Ausschnittbreite
    fehlt oder liegt unter ``min_breite`` Pixeln (die Nahansicht waere dort verpixelt).
    """
    score = gesicht.get("score")
    if not isinstance(score, (int, float)) or score < min_score:
        return False
    breite = gesicht.get("breite_px")
    if not isinstance(breite, (int, float)) or breite < min_breite:
        return False
    return True


def gesichter_einer_gruppe(zuordnung, kennung):
    """Alle Gesichter einer Kennung als ``[(schluessel, gesicht), …]``."""
    return [(schluessel, gesicht) for schluessel, gesicht in zuordnung.items()
            if gesicht["kennung"] == kennung]


def mittelpunkt_verschiebung(vektoren, gesichter, *, min_score: float = MIN_SCORE,
                             min_breite: float = MIN_BREITE, art: str = "beide") -> dict:
    """Vergleicht den Mittelpunkt ALLER Vektoren mit dem der sauberen.

    ``art`` waehlt, was weggelassen wird: ``unsicher`` (nur ``score``), ``grob`` (nur die
    Ausschnittbreite) oder ``beide``. Rueckgabe ``{"alle": n, "sauber": n, "winkel": d}``.
    """
    alle = []
    rein = []
    for schluessel, gesicht in gesichter:
        vektor = vektoren.get(schluessel)
        if vektor is None:
            continue
        alle.append(vektor)
        if art == "unsicher":
            weiter = _sicher(gesicht, min_score)
        elif art == "grob":
            weiter = _nicht_grob(gesicht, min_breite)
        else:
            weiter = sauber(gesicht, min_score, min_breite)
        if weiter:
            rein.append(vektor)
    if not rein:
        return {"alle": len(alle), "sauber": 0, "winkel": None}
    return {"alle": len(alle), "sauber": len(rein),
            "winkel": winkel(mittelpunkt(alle), mittelpunkt(rein))}


def _sicher(gesicht, min_score: float) -> bool:
    score = gesicht.get("score")
    return isinstance(score, (int, float)) and score >= min_score


def _nicht_grob(gesicht, min_breite: float) -> bool:
    breite = gesicht.get("breite_px")
    return isinstance(breite, (int, float)) and breite >= min_breite


def zentren_matrix(gruppen, vektoren, *, nur_sauber: bool, min_score: float = MIN_SCORE,
                   min_breite: float = MIN_BREITE):
    """``(kennungen, matrix)``: normierte Mittelpunkte je Gruppe (Reihenfolge wie ``gruppen``).

    Gruppen ohne brauchbare Vektoren fallen weg (sie stehen dann in keiner Zeile).
    """
    kennungen = []
    reihen = []
    for kennung in gruppen:
        menge = []
        for schluessel, gesicht in gruppen[kennung]:
            vektor = vektoren.get(schluessel)
            if vektor is None:
                continue
            if nur_sauber and not sauber(gesicht, min_score, min_breite):
                continue
            menge.append(vektor)
        punkt = mittelpunkt(menge)
        if punkt is None:
            continue
        kennungen.append(kennung)
        reihen.append(punkt)
    if not reihen:
        return [], np.zeros((0, 0), dtype=np.float32)
    return kennungen, np.asarray(reihen, dtype=np.float32)


def neuordnung(vektoren, gesichter_sauber, kennungen_alle, zentren_alle,
               kennungen_rein, zentren_rein, *, stueck: int = STUECK) -> dict:
    """Wie viele saubere Gesichter wechseln unter den sauberen Mittelpunkten die Gruppe?

    Verglichen wird der naechste Mittelpunkt ALLER Gruppen mit dem naechsten Mittelpunkt der
    sauberen Gruppen. Rueckgabe ``{"geprueft": n, "gewechselt": n}``.
    """
    ergebnis = {"geprueft": 0, "gewechselt": 0}
    if len(zentren_alle) == 0 or len(zentren_rein) == 0:
        return ergebnis
    stapel = []
    for schluessel, gesicht in gesichter_sauber:
        vektor = vektoren.get(schluessel)
        if vektor is None:
            continue
        einheit = einheitsvektor(vektor)
        if einheit is not None:
            stapel.append(einheit)
    if not stapel:
        return ergebnis
    daten = np.asarray(stapel, dtype=np.float32)
    ergebnis["geprueft"] = int(daten.shape[0])
    gewechselt = 0
    for anfang in range(0, daten.shape[0], stueck):
        block = daten[anfang:anfang + stueck]
        nah_alle = np.argmax(block @ zentren_alle.T, axis=1)
        nah_rein = np.argmax(block @ zentren_rein.T, axis=1)
        for i in range(block.shape[0]):
            if kennungen_alle[int(nah_alle[i])] != kennungen_rein[int(nah_rein[i])]:
                gewechselt += 1
    ergebnis["gewechselt"] = gewechselt
    return ergebnis


def sauber_je_gruppe(gruppen, vektoren, *, min_score: float = MIN_SCORE,
                     min_breite: float = MIN_BREITE) -> list:
    """``[(kennung, saubere, gesamt), …]`` je Gruppe - nur Gesichter **mit** Vektor.

    ``saubere`` = Gesichter mit ``score >= min_score`` UND Ausschnittbreite ``>= min_breite``;
    ``gesamt`` = Gesichter der Gruppe, zu denen es einen Vektor gibt. Das ist die Zahl, die
    fuer die Reihenfolge des Wisch-Sortierers zaehlt (nicht die Gruppengroesse).
    """
    ergebnis = []
    for kennung, menge in gruppen.items():
        gesamt = 0
        rein = 0
        for schluessel, gesicht in menge:
            if schluessel not in vektoren:
                continue
            gesamt += 1
            if sauber(gesicht, min_score, min_breite):
                rein += 1
        ergebnis.append((kennung, rein, gesamt))
    return ergebnis


def sauber_stufen(werte) -> list:
    """``[(stufe, anzahl), …]`` - wie viele Gruppen in jede Stufe saubere Gesichter fallen."""
    return [(name, sum(1 for wert in werte if wert >= unten
                       and (oben is None or wert < oben)))
            for unten, oben, name in SAUBER_STUFEN]


def wisch_reihenfolge(gruppen, vektoren, *, min_score: float = MIN_SCORE,
                      min_breite: float = MIN_BREITE) -> list:
    """Die Gruppen fuer den Wisch-Sortierer: **schlechteste zuerst**.

    Sortiert nach der Zahl der sauberen Gesichter (wenige zuerst), bei Gleichstand die groessere
    Gruppe zuerst, dann die Kennung - damit die unsichersten Gruppen (und die ganz ohne sauberen
    Fund) oben stehen. Reine Reihenfolge: es wird nichts geloescht, nichts verschoben.
    """
    return sorted(sauber_je_gruppe(gruppen, vektoren, min_score=min_score, min_breite=min_breite),
                  key=lambda eintrag: (eintrag[1], -eintrag[2], eintrag[0]))


def jahresphasen(zuordnung, vektoren, kennung, *, min_score: float = MIN_SCORE,
                 min_breite: float = MIN_BREITE, phasen_min: int = PHASE_MIN) -> list:
    """``[(jahr, n_alle, n_sauber, winkel)]`` je Aufnahmejahr einer Gruppe (nur ausreichende)."""
    je: dict = {}
    for schluessel, gesicht in gesichter_einer_gruppe(zuordnung, kennung):
        aufnahme = gesicht.get("aufnahme")
        if not isinstance(aufnahme, str) or len(aufnahme) < 4 or not aufnahme[:4].isdigit():
            continue
        vektor = vektoren.get(schluessel)
        if vektor is None:
            continue
        je.setdefault(aufnahme[:4], []).append((vektor, gesicht))
    ergebnis = []
    for jahr in sorted(je):
        menge = je[jahr]
        if len(menge) < phasen_min:
            continue
        rein = [v for v, g in menge if sauber(g, min_score, min_breite)]
        if len(rein) < phasen_min:
            continue
        ergebnis.append((jahr, len(menge), len(rein),
                         winkel(mittelpunkt([v for v, _ in menge]), mittelpunkt(rein))))
    return ergebnis


# ── 3. Bericht (nur Zahlen, nur Kennungen) ───────────────────────────────────

def _zahl(wert, stellen: int = 3) -> str:
    return " - " if wert is None else f"{wert:.{stellen}f}"


def _prozent(teil: int, ganzes: int) -> str:
    return " - " if not ganzes else f"{100.0 * teil / ganzes:4.0f} %"


def _verteilung(werte) -> str:
    """Median · 90 % · groesster Wert einer Zahlenliste (nur Zahlen)."""
    brauchbar = sorted(w for w in werte if w is not None)
    if not brauchbar:
        return "keine"
    n = len(brauchbar)
    median = brauchbar[n // 2] if n % 2 else 0.5 * (brauchbar[n // 2 - 1] + brauchbar[n // 2])
    neunzig = brauchbar[min(n - 1, int(round(0.9 * (n - 1))))]
    return f"Median {median:.3f} · 90 % {neunzig:.3f} · groesste {brauchbar[-1]:.3f}"


def bericht(zuordnung, ohne_kennung, vektoren, statistik, *,
            min_score: float = MIN_SCORE, min_breite: float = MIN_BREITE,
            gruppe_min: int = GRUPPE_MIN, phasen_min: int = PHASE_MIN,
            zeigen: int = 5, stueck: int = STUECK) -> list:
    """Alle Messzeilen als Liste von Texten (nur Zahlen und Kennungen)."""
    zeilen = []
    gruppen: dict = {}
    for schluessel, gesicht in zuordnung.items():
        gruppen.setdefault(gesicht["kennung"], []).append((schluessel, gesicht))
    mit_vektor = sum(1 for s in zuordnung if s in vektoren)
    zeilen.append(f"Gesichter in Gruppen: {len(zuordnung)} · mit Vektor: {mit_vektor} "
                  f"({_prozent(mit_vektor, len(zuordnung)).strip()}) · ohne Vektor: "
                  f"{len(zuordnung) - mit_vektor} · ohne Kennung (nicht gezaehlt): {ohne_kennung}")
    zeilen.append(f"Vektoren: {statistik['dateien']} Dateien gelesen "
                  f"({statistik['fehlend']} fehlten) · {statistik['zeilen']} Zeilen · "
                  f"{statistik['defekt']} defekt · {statistik['gesichter']} Gesichter · "
                  f"uebernommen {statistik['gelesen']} · andere Laenge verworfen "
                  f"{statistik['fremde_laenge']} · Masse {statistik['masse']}")
    sicher = sum(1 for s in zuordnung if _sicher(zuordnung[s], min_score))
    grob = sum(1 for s in zuordnung if not _nicht_grob(zuordnung[s], min_breite))
    rein = sum(1 for s in zuordnung if sauber(zuordnung[s], min_score, min_breite))
    zeilen.append(f"Nicht sicher (score < {min_score}): {sicher} "
                  f"({_prozent(sicher, len(zuordnung)).strip()}) · grob aufgeloest "
                  f"(Breite < {min_breite} px): {grob} "
                  f"({_prozent(grob, len(zuordnung)).strip()}) · unsicher ODER grob: "
                  f"{len(zuordnung) - rein} ({_prozent(len(zuordnung) - rein, len(zuordnung)).strip()})")
    zeilen.append("")

    bewertbar = [k for k, m in gruppen.items()
                 if sum(1 for s, _ in m if s in vektoren) >= gruppe_min]
    zeilen.append(f"Gruppen: {len(gruppen)} · mit mindestens {gruppe_min} Gesichtern mit Vektor: "
                  f"{len(bewertbar)}")
    versch = {"unsicher": [], "grob": [], "beide": []}
    spur = {"unsicher": [], "grob": [], "beide": []}
    for kennung in bewertbar:
        for art in versch:
            m = mittelpunkt_verschiebung(vektoren, gruppen[kennung], min_score=min_score,
                                         min_breite=min_breite, art=art)
            if m["winkel"] is not None:
                versch[art].append(m["winkel"])
                spur[art].append((m["winkel"], kennung, m["sauber"]))
    namen = {"unsicher": f"ohne unsichere (score < {min_score})",
             "grob": f"ohne grobe (Breite < {min_breite} px)",
             "beide": "ohne unsichere und grobe"}
    zeilen.append("Verschiebung des Gruppenmittelpunkts (Cosinus-Distanz):")
    for art in ("unsicher", "grob", "beide"):
        zeilen.append(f"  {namen[art]:<34} {_verteilung(versch[art])}")
        for wert, kennung, sauber_n in sorted(spur[art], reverse=True)[:zeigen]:
            zeilen.append(f"      {kennung:<13} {wert:.3f}  ({sauber_n} saubere Gesichter)")
    zeilen.append("")

    kennungen_alle, zentren_alle = zentren_matrix(gruppen, vektoren, nur_sauber=False)
    kennungen_rein, zentren_rein = zentren_matrix(gruppen, vektoren, nur_sauber=True,
                                                 min_score=min_score, min_breite=min_breite)
    saubere_gesichter = [(s, g) for s, g in zuordnung.items()
                         if sauber(g, min_score, min_breite)]
    n = neuordnung(vektoren, saubere_gesichter, kennungen_alle, zentren_alle,
                   kennungen_rein, zentren_rein, stueck=stueck)
    zeilen.append(f"Neuordnung: von {n['geprueft']} sauberen Gesichtern bekaemen "
                  f"{n['gewechselt']} ({_prozent(n['gewechselt'], n['geprueft']).strip()}) unter "
                  f"den sauberen Mittelpunkten eine andere Gruppe ({len(kennungen_alle)} gegen "
                  f"{len(kennungen_rein)} Mittelpunkte)")
    zeilen.append("")

    phasen = []
    for kennung in bewertbar:
        phasen += jahresphasen(zuordnung, vektoren, kennung, min_score=min_score,
                               min_breite=min_breite, phasen_min=phasen_min)
    zeilen.append(f"Lebensphasen (Gruppe und Aufnahmejahr mit mindestens {phasen_min} Gesichtern): "
                  f"{len(phasen)} Phasen")
    if phasen:
        phasen.sort(key=lambda p: -p[3])
        zeilen.append(f"  Verschiebung je Phase            {_verteilung([p[3] for p in phasen])}")
        for jahr, alle_n, rein_n, wert in phasen[:zeigen]:
            zeilen.append(f"      Jahr {jahr}  {wert:.3f}  ({alle_n} Gesichter, {rein_n} saubere)")
    zeilen.append("")
    je_gruppe = sauber_je_gruppe(gruppen, vektoren, min_score=min_score, min_breite=min_breite)
    bewertet = [eintrag for eintrag in je_gruppe if eintrag[2] > 0]
    ohne_vektor = len(je_gruppe) - len(bewertet)
    zeilen.append("Wisch-Sortierer, Stufe 1 (Vorschlag: nach Zahl der sauberen Gesichter, "
                  "schlechteste zuerst):")
    for stufe, anzahl in sauber_stufen([eintrag[1] for eintrag in bewertet]):
        zeilen.append(f"  {stufe:<24} {anzahl} Gruppen")
    if ohne_vektor:
        zeilen.append(f"  {'ohne Vektor (nicht bewertet)':<24} {ohne_vektor} Gruppen")
    for kennung, rein_n, gesamt in wisch_reihenfolge(gruppen, vektoren, min_score=min_score,
                                                     min_breite=min_breite)[:zeigen]:
        zeilen.append(f"      {kennung:<13} {rein_n} saubere von {gesamt} Gesichtern")
    return zeilen


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Mittelpunkt-Verschiebung durch unsichere/grobe Gesichter messen "
                    "(nur lesen, nur Zahlen, nichts schreiben).")
    zerleger.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG)
    zerleger.add_argument("--vektoren", nargs="*", default=list(STANDARD_VEKTOREN))
    zerleger.add_argument("--min-score", type=float, default=MIN_SCORE)
    zerleger.add_argument("--min-breite", type=float, default=MIN_BREITE)
    zerleger.add_argument("--gruppe-min", type=int, default=GRUPPE_MIN)
    zerleger.add_argument("--phasen-min", type=int, default=PHASE_MIN)
    zerleger.add_argument("--zeigen", type=int, default=5)
    args = zerleger.parse_args(argv)
    if not os.path.isfile(args.zuordnung):
        print(f"Abbruch: Zuordnungsdatei nicht gefunden: {args.zuordnung}")
        return 2
    if not any(os.path.isfile(p) for p in args.vektoren):
        print("Abbruch: keine der Vektordateien gefunden.")
        return 2
    zuordnung, ohne = zuordnung_lesen(args.zuordnung)
    if not zuordnung:
        print("Abbruch: die Zuordnung enthaelt keine Gesichter mit Kennung.")
        return 2
    vektoren, statistik = vektoren_sammeln(args.vektoren, schluessel=set(zuordnung))
    if not vektoren:
        print("Abbruch: zu keinem Gesicht der Zuordnung gibt es einen Vektor.")
        return 2
    for zeile in bericht(zuordnung, ohne, vektoren, statistik, min_score=args.min_score,
                         min_breite=args.min_breite, gruppe_min=max(1, args.gruppe_min),
                         phasen_min=max(1, args.phasen_min), zeigen=max(0, args.zeigen)):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
