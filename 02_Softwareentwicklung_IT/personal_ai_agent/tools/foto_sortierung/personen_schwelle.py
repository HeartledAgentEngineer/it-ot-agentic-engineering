"""Schwellen-Messwerkzeug der Personen-Stufe (Nachtlauf-Schritt N9e, 27.09.2026).

Wozu dieses Werkzeug:
  Der echte Lauf (N9b/N9d) hat am Bestand gezeigt, dass ``vektoren_clustern``
  aus N9a die **189 nutzbaren Gesichter** der ``gruppe``-Bilder zu **einer**
  Gruppe gebuendelt hat — obwohl die Aufnahmen aus **neun verschiedenen
  Anlaessen** stammen. Ein Dichte-Verfahren (DBSCAN-artig, Expansion vom
  Kernpunkt = transitives Verketten) ist dafuer bekannt; am echten Bestand war
  die Schwelle ``CLUSTER_SCHWELLE = 0.45`` aber **nie mit Bodenwahrheit
  geprueft**.

  Dieses Werkzeug **misst**. Es rechnet fuer einen Bestand von Vektorzeilen
  (genau das Format, das ``gesicht_erkennen.py`` schreibt) aus, wie sich die
  Gruppen bei **verschiedenen Schwellen** verhalten, **beziffert** die
  Verschmelzung der Bild-Paare der Bodenwahrheit (``verschmelzungsquote``,
  ``kettenmass``), zusaetzlich den **Anlass-Mix** je Cluster
  (``falsche_cluster`` — ein **Strukturmass**, ausdruecklich **keine**
  Identitaetsaussage) und liefert die **Trennschaerfe** der Cosinus-Distanz
  (innerhalb vs. zwischen den Beschriftungen). Daraus entsteht eine
  **begruendete Empfehlung**.

  Als **Strukturmass** dient, was am Bestand als Struktur bekannt ist: der
  **Anlass** eines Bildes (``thema_quelle`` aus dem Sortierplan) oder die
  **Burst-Familie** eines Dateinamens (Dateiname ohne ``_BURST<nnn>…`` bzw.
  ``_Burst<nn>``-Zusatz). Das ist **keine Identitaetswahrheit**: ein Anlass
  enthaelt legitim viele verschiedene Personen, und dieselbe Person kann in
  mehreren Anlaessen vorkommen. Das Werkzeug nennt dieses Mass daher
  **Strukturmass** ("Anlass-Mix je Cluster") und leitet daraus keine
  Identitaetsaussage ab.

  Die **echte Bodenwahrheit** ist eine Bildaussage: **zwei erkennbare Gesichter
  im selben Bild sind verschiedene Personen** (Flaechenanteil >=
  ``ANTEIL_ERKENNBAR`` = 0,005; eine Person ist einmal im Bild). Daraus bildet
  das Werkzeug Paare, beziffert je Schwelle die **Verschmelzungsquote** ("x von
  y Paaren in derselben Gruppe" — jedes solche Paar ist falsch zusammengelegt)
  und das **Kettenmass** (Anteil der Paare innerhalb einer Gruppe, die weiter
  auseinander liegen als die Schwelle selbst = Beleg fuer transitives
  Verketten, plus Gruppendurchmesser). Bekannte Ausnahmen der Bildaussage
  (Spiegelung, Plakat/Monitor, Zwillinge) stehen im Docstring von
  ``bild_paare`` — die Quote ist daher eine Naeherung, keine absolute Wahrheit.

Was dieses Werkzeug bewusst NICHT tut:
  * **Es aendert keine Schwelle.** ``CLUSTER_SCHWELLE``, ``CLUSTER_MIN_NACHBAR``
    und alle anderen Werte in ``personen_cluster.py`` werden **nur gelesen**
    (ueber ``_personen_cluster().CLUSTER_SCHWELLE``) und beim Namen genannt. Es
    gibt hier keine Zuweisung an eine dieser Schwellen; ein Test prueft das.
    Kandidaten kommen ausschliesslich als Argument herein.
  * **Kein Schreiben ins Repo.** Der Bericht geht nur in einen Ordner
    **ausserhalb** des Repos; ein Repo-Pfad ergibt eine deutsche Klartextmeldung
    und ``SystemExit(2)``, geschrieben wird dann nichts.
  * **Kein Loeschen, kein Netz, kein Bild.** Es oeffnet kein Bild, laedt nichts
    herunter und ruft keine pCloud an. Eingabe sind Vektorzeilen als Text.
  * **Keine Namen.** Beschriftungen sind Anlass-/Familien-Kennungen aus dem
    Sortierplan, nie Personennamen.

Eingabe (genau das Format aus ``gesicht_erkennen.py``):: JSONL, eine Zeile je
Bild mit ``bild_id``, ``breite``, ``hoehe`` und ``gesichter`` (``bbox``,
``score``, ``embedding`` 128 Werte). Der Sortierplan (JSON) liefert nur die
Zuordnung ``zuege[].fileid`` -> ``thema_quelle``/``von_name``.

Aufruf (Kommandozeile):: Standard ist der Trockenlauf (nichts geschrieben).

    .venv/Scripts/python.exe tools/foto_sortierung/personen_schwelle.py \
        --vektoren ~/foto_sortierung/personen_vektoren_n9d.jsonl \
        --plan     ~/foto_sortierung/sortierplan.json

    # Bericht wirklich ablegen (PFLICHT ausserhalb des Repos)
    ... --ausgabe ~/foto_sortierung/n9e_bericht.json --schreiben

Als Modul (Tests, Skripte): ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import math
import os
import re

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen Biometrie und Vektoren.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = os.path.join(STANDARD_BASIS, "personen_vektoren_n9d.jsonl")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "n9e_schwellen_bericht.json")

# ── Messparameter (nur hier, nichts davon wird in personen_cluster gesetzt) ─

# Die Mess-Schwellen. 0.45 ist der **heutige** Wert (``CLUSTER_SCHWELLE`` aus
# N9a) und steht bewusst **mit** in der Liste — so ist der Ist-Zustand im
# Bericht sichtbar. Die uebrigen Werte sind ein grobes Gitter darunter, damit
# sichtbar wird, ob ein Absenken ueberhaupt etwas trennt.
SCHWELLEN_STANDARD = (0.60, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20,
                      0.15, 0.10, 0.05)

# Ein Cluster gilt als **falsch zusammengelegt**, sobald er Gesichter aus
# mindestens so vielen verschiedenen Beschriftungen enthaelt. 2 ist die
# strengste sinnvolle Grenze: aus zwei verschiedenen Anlaessen stammende
# Gesichter in einer Gruppe sind ein Widerspruch zur Beschriftung.
UNREIN_AB = 2

# Burst-Familie: Dateiname ohne den ``_BURST<nnn>…``- bzw. ``_Burst<nn>``-Zusatz.
# Der Zusatz steht am Ende bzw. vor einer Endung; ``_BURST000_COVER.jpg``
# gehoert damit zur selben Familie wie ``_BURST001.jpg``.
BURST_MUSTER = re.compile(r"(_BURST\d+.*|_Burst\d+.*)$")

# Standardfeld des Sortierplans, das als Beschriftung dient.
BESCHRIFTUNG_STANDARD = "thema_quelle"

# Prozentpunkte fuer die Verteilungsangaben der Trennschaerfe.
QUANTILE = (5.0, 50.0, 90.0)


class SchwelleFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── N9a laden (nichts nachbauen, was es schon gibt) ───────────────────────

_CACHE: dict = {}


def _personen_cluster():
    """``personen_cluster.py`` (N9a) laden — Cluster-Verfahren und Schwellen."""
    if "personen_cluster" not in _CACHE:
        pfad = os.path.join(HIER, "personen_cluster.py")
        spez = importlib.util.spec_from_file_location("schwelle_personen_cluster",
                                                      pfad)
        if spez is None or spez.loader is None:
            raise SchwelleFehler(f"personen_cluster.py nicht gefunden: {pfad}")
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        _CACHE["personen_cluster"] = modul
    return _CACHE["personen_cluster"]


def _ist_zahl(wert) -> bool:
    """Eine endliche Zahl (kein ``bool``) — sonst ``False``."""
    return _personen_cluster()._ist_zahl(wert)


def _liste(wert) -> list:
    """``wert`` als Liste — alles andere wird zur leeren Liste."""
    return _personen_cluster()._liste(wert)


def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return _personen_cluster()._text(wert)


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    return _personen_cluster()._zahl(n)


# ── 1. Beschriftungen (Bodenwahrheit aus Anlass bzw. Burst-Familie) ───────

def burst_familie(name):
    """Die Burst-Familie eines Dateinamens — Basename ohne ``_BURST<nnn>…``.

    ``IMG_20250609_015239666_BURST008.jpg`` -> ``IMG_20250609_015239666``.
    Ein Name **ohne** Zusatz ist seine eigene Familie (``IMG_1.jpg`` ->
    ``IMG_1.jpg``). ``None``/kein Text ergeben ``None`` — es wird nicht geraten.
    """
    if not isinstance(name, str):
        return None
    rest = os.path.basename(name.strip())
    if not rest:
        return None
    return BURST_MUSTER.sub("", rest)


def plan_beschriftungen_lesen(pfad: str, feld: str = BESCHRIFTUNG_STANDARD) -> dict:
    """Aus dem Sortierplan ``{fileid: beschriftung}`` lesen — nur lesend.

    Gelesen werden ausschliesslich ``zuege[].fileid`` und das Feld ``feld``
    (Vorgabe ``thema_quelle`` = Anlass) bzw. — bei ``feld == "von_name"`` —
    dessen **Burst-Familie**. Eine fehlende, unlesbare oder strukturlose Datei
    ergibt eine ``SchwelleFehler``-Meldung (hier wird nichts geraten: eine
    falsche Zuordnung wuerde die ganze Messung verfaelschen). Eintraege ohne
    ``fileid`` oder ohne lesbare Beschriftung fallen weg und werden gezaehlt.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise SchwelleFehler("Kein Plan-Pfad angegeben.")
    if not os.path.isfile(pfad):
        raise SchwelleFehler(f"Sortierplan nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise SchwelleFehler(
            f"Sortierplan nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None
    if isinstance(daten, dict):
        zuege = daten.get("zuege")
    elif isinstance(daten, list):
        zuege = daten
    else:
        zuege = None
    if not isinstance(zuege, list):
        raise SchwelleFehler(f"Sortierplan ohne Feld 'zuege': {pfad}")

    roh = feld if isinstance(feld, str) and feld.strip() else BESCHRIFTUNG_STANDARD
    aus_name = roh == "von_name"
    zuordnung: dict = {}
    for zug in zuege:
        if not isinstance(zug, dict):
            continue
        fileid = zug.get("fileid")
        if isinstance(fileid, bool) or fileid is None:
            continue
        kennung = str(fileid).strip()
        if not kennung:
            continue
        wert = zug.get(roh)
        if aus_name:
            wert = burst_familie(wert)
        beschriftung = _text(wert)
        if not beschriftung:
            continue
        zuordnung[kennung] = beschriftung
    return zuordnung


def beschriftung_je_eintrag(eintraege, zuordnung, feld: str = "bild_id") -> list:
    """Die Beschriftung je Eintrag in Eingabereihenfolge — ``None``, wenn keine.

    ``zuordnung`` ist ``{kennung: beschriftung}`` (siehe
    ``plan_beschriftungen_lesen``). Ein Eintrag ohne brauchbare Kennung oder
    ohne Treffer bekommt ``None`` — solche Eintraege zaehlen in der Messung als
    **ohne Beschriftung** und werden nie als Widerspruch gewertet.
    """
    karte = zuordnung if isinstance(zuordnung, dict) else {}
    ergebnis: list = []
    for eintrag in _liste(eintraege):
        schluessel = None
        if isinstance(eintrag, dict):
            wert = eintrag.get(feld)
            if isinstance(wert, (str, int)) and not isinstance(wert, bool):
                schluessel = str(wert).strip()
        ergebnis.append(karte.get(schluessel) if schluessel else None)
    return ergebnis


# ── 2. Einen Cluster beschreiben (Groesse, Beschriftungen, Purheit) ───────

def cluster_beschriften(gruppen, eintraege, beschriftungen) -> list[dict]:
    """Je Cluster ein Beschreibungs-Dict — rein, ohne I/O.

    ``gruppen`` sind Index-Listen in ``eintraege`` (so, wie
    ``personen_cluster.vektoren_clustern`` sie liefert); ``beschriftungen`` ist
    die zu ``eintraege`` **gleich lange** Liste aus ``beschriftung_je_eintrag``.

    Rueckgabe je Cluster (Reihenfolge = Reihenfolge der Gruppen)::

        {"nummer", "groesse", "beschriftungen", "anzahl_beschriftungen",
         "rein", "ohne_beschriftung", "indizes"}

    ``rein`` heisst: hoechstens **eine** Beschriftung (Eintraege ohne
    Beschriftung zaehlen nicht mit). ``nummer`` faengt bei 1 an — damit lassen
    sich falsch zusammengelegte Cluster im Bericht **beziffern**.
    """
    liste_eintraege = _liste(eintraege)
    labels = _liste(beschriftungen)
    ergebnis: list[dict] = []
    for nummer, gruppe in enumerate(_liste(gruppen), start=1):
        indizes = [int(index) for index in _liste(gruppe)
                   if _ist_zahl(index) and 0 <= int(index) < len(liste_eintraege)]
        haeufig: dict = {}
        ohne = 0
        for index in indizes:
            label = labels[index] if index < len(labels) else None
            if label is None:
                ohne += 1
                continue
            haeufig[label] = haeufig.get(label, 0) + 1
        ergebnis.append({
            "nummer": nummer,
            "groesse": len(indizes),
            "beschriftungen": {name: haeufig[name] for name in sorted(haeufig)},
            "anzahl_beschriftungen": len(haeufig),
            "rein": len(haeufig) < UNREIN_AB,
            "ohne_beschriftung": ohne,
            "indizes": indizes,
        })
    return ergebnis


def falsche_cluster(beschriebene) -> list[dict]:
    """Die **falsch zusammengelegten** Cluster — beziffert, groesster zuerst.

    Ein Cluster ist falsch zusammengelegt, wenn er Gesichter aus mindestens
    ``UNREIN_AB`` verschiedenen Beschriftungen enthaelt (``rein`` ist ``False``).
    Sortiert wird nach ``(-groesse, nummer)`` — der groesste Widerspruch steht
    oben. Jeder Eintrag traegt ``nummer``, ``groesse``, ``beschriftungen``,
    ``anzahl_beschriftungen`` und ``anteil`` (Anteil an allen Gesichtern).
    """
    alle = [eintrag for eintrag in _liste(beschriebene)
            if isinstance(eintrag, dict) and not eintrag.get("rein", True)]
    gesamt = sum(int(eintrag.get("groesse") or 0)
                 for eintrag in _liste(beschriebene)
                 if isinstance(eintrag, dict))
    treffer: list[dict] = []
    for eintrag in alle:
        treffer.append({
            "nummer": int(eintrag.get("nummer") or 0),
            "groesse": int(eintrag.get("groesse") or 0),
            "beschriftungen": dict(eintrag.get("beschriftungen") or {}),
            "anzahl_beschriftungen": int(eintrag.get("anzahl_beschriftungen") or 0),
            "anteil": (int(eintrag.get("groesse") or 0) / gesamt) if gesamt else 0.0,
        })
    treffer.sort(key=lambda eintrag: (-eintrag["groesse"], eintrag["nummer"]))
    return treffer


# ── 3. Echte Bodenwahrheit: zwei erkennbare Gesichter im selben Bild ─────
#
# Das Anlass-Mass aus Abschnitt 2 ist **keine** Identitaetswahrheit: ein Anlass
# enthaelt legitim viele verschiedene Personen, und **dieselbe** Person kann in
# mehreren Anlaessen vorkommen. Es ist ein **Strukturmass** ("Anlass-Mix je
# Cluster").
#
# Die belastbare Identitaetsaussage, die am Bestand wirklich gilt, ist eine
# **Bildaussage**: zwei **erkennbare** Gesichter im **selben** Bild sind
# **verschiedene** Personen. Erkennbar heisst: Flaechenanteil >=
# ``ANTEIL_ERKENNBAR`` (0,005 = 0,5 % der Bildflaeche, bei 12 MP rund 70x70 px)
# — erst dort traegt ein SFace-Merkmal, und erst dort ist es ein
# Vordergrund-Gesicht. Weil eine Person in einem Bild nur **einmal** auftritt,
# ist jedes solche Paar ein **fester** Beleg fuer "zwei verschiedene Personen".
#
# Ausnahmen, die im Bestand denkbar sind (und den Beleg im Einzelfall
# entkraeften): **Spiegelung** (eine Person und ihr Spiegelbild), ein
# **Plakat/Monitor** mit demselben Gesicht im Bild und **Zwillinge** (sehen
# gleich aus, sind aber zwei Personen). Diese Faelle sind selten; die Quote
# wird daher als **Naeherung** genannt, nie als absolute Wahrheit.

def _cosinus_distanz(vektor_a, vektor_b):
    """Cosinus-Distanz (``1 - cosinus``) zweier Vektoren — ``None``, wenn nicht.

    Nullvektoren ergeben ``None`` (ihre Aehnlichkeit ist nicht definiert) —
    es wird nichts geraten.
    """
    a = np.asarray(vektor_a, dtype=float)
    b = np.asarray(vektor_b, dtype=float)
    if a.size == 0 or a.size != b.size:
        return None
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return None
    aehnlich = max(-1.0, min(1.0, float(np.dot(a, b) / (na * nb))))
    return 1.0 - aehnlich


def _ist_erkennbar(eintrag) -> bool:
    """Ist dieses Gesicht **erkennbar** (Flaechenanteil >= ANTEIL_ERKENNBAR)?"""
    if not isinstance(eintrag, dict):
        return False
    anteil = eintrag.get("anteil")
    if not _ist_zahl(anteil):
        return False
    return float(anteil) >= float(_personen_cluster().ANTEIL_ERKENNBAR)


def bild_paare(eintraege) -> list[dict]:
    """**Bodenwahrheit**: Paare erkennbarer Gesichter im **selben** Bild.

    Reine Funktion (kein I/O). Eingabe sind die geclusterten N9a-Eintraege
    (``bild_id``, ``bbox``, ``score``, ``anteil``, ``embedding``). Ein Paar
    entsteht fuer **zwei** Gesichter desselben Bildes, die beide
    ``anteil >= ANTEIL_ERKENNBAR`` haben. Nach der Annahme oben sind das
    **zwei verschiedene Personen** — also gilt: sie muessen in **zwei
    verschiedenen** Gruppen landen.

    Rueckgabe je Paar: ``{"bild_id", "a", "b", "distanz"}``. ``a``/``b`` sind
    die **Indizes** in ``eintraege`` (so, wie ``vektoren_clustern`` sie
    liefert); ``distanz`` ist die Cosinus-Distanz der beiden Vektoren (oder
    ``None``, wenn sie nicht rechnen laesst). Paare entstehen nur, wenn beide
    Vektoren brauchbar sind. Ein Bild mit ``n`` erkennbaren Gesichtern liefert
    ``n*(n-1)/2`` Paare.
    """
    pc = _personen_cluster()
    liste = _liste(eintraege)
    nach_bild: dict = {}
    for index, eintrag in enumerate(liste):
        if not _ist_erkennbar(eintrag):
            continue
        if pc._vektor_von(eintrag) is None:
            continue
        schluessel = _text(eintrag.get("bild_id"))
        nach_bild.setdefault(schluessel, []).append(index)
    paare: list[dict] = []
    for bild_id in sorted(nach_bild):
        indizes = nach_bild[bild_id]
        for a_pos in range(len(indizes)):
            for b_pos in range(a_pos + 1, len(indizes)):
                ia, ib = indizes[a_pos], indizes[b_pos]
                distanz = _cosinus_distanz(pc._vektor_von(liste[ia]),
                                           pc._vektor_von(liste[ib]))
                if distanz is None:
                    continue
                paare.append({"bild_id": bild_id, "a": ia, "b": ib,
                              "distanz": distanz})
    paare.sort(key=lambda paar: (paar["bild_id"], paar["a"], paar["b"]))
    return paare


def _gruppen_zuordnung(gruppen) -> dict:
    """``{index: gruppen_nummer}`` aus den Index-Listen der Gruppen."""
    zuordnung: dict = {}
    for nummer, gruppe in enumerate(_liste(gruppen), start=1):
        for index in _liste(gruppe):
            if _ist_zahl(index):
                zuordnung[int(index)] = nummer
    return zuordnung


def _paar_index(paar, name: str):
    """Den Index ``a``/``b`` eines Paares lesen — ``None``, wenn es keinen gibt.

    Wichtig: ``0`` ist ein gueltiger Index und darf **nicht** als "fehlt"
    gelten (ein ``wert or -1`` wuerde das tun).
    """
    wert = paar.get(name)
    if not _ist_zahl(wert):
        return None
    return int(wert)


def verschmelzungsquote(paare, gruppen) -> dict:
    """Wie viele Bild-Paare legt diese Schwelle in **dieselbe** Gruppe? — rein.

    Das ist die **Verschmelzungsquote je Schwelle**: "x von y Paaren in
    derselben Gruppe". Nach der Bodenwahrheit sind alle diese Paare **falsch**
    zusammengelegt (zwei verschiedene Personen im selben Bild, in einer
    Gruppe). Rueckgabe ``{"paare", "verschmolzen", "getrennt", "quote",
    "distanzen"}`` — ``distanzen`` sind die Cosinus-Distanzen der
    verschmolzenen Paare (Beleg, wie weit sie auseinander lagen).
    """
    zuordnung = _gruppen_zuordnung(gruppen)
    gesamt = 0
    zusammen = 0
    distanzen: list = []
    for paar in _liste(paare):
        if not isinstance(paar, dict):
            continue
        gesamt += 1
        ia = _paar_index(paar, "a")
        ib = _paar_index(paar, "b")
        ga = zuordnung.get(ia) if ia is not None else None
        gb = zuordnung.get(ib) if ib is not None else None
        if ga is not None and gb is not None and ga == gb:
            zusammen += 1
            if _ist_zahl(paar.get("distanz")):
                distanzen.append(float(paar["distanz"]))
    return {"paare": gesamt, "verschmolzen": zusammen,
            "getrennt": gesamt - zusammen,
            "quote": (zusammen / gesamt) if gesamt else 0.0,
            "distanzen": distanzen}


def gruppendurchmesser(gruppen, eintraege) -> dict:
    """Groesster Cosinus-Abstand **innerhalb** je einer Gruppe — der Durchmesser.

    Ein Durchmesser **ueber** der Schwelle ist der direkte Beleg fuer
    **transitives Verketten**: die Gruppe haelt Punkte zusammen, die selbst
    weiter auseinander liegen als die Schwelle erlaubt (A-B und B-C sind nah,
    A-C ist fern). Rueckgabe ``{"je_gruppe", "groesste", "max"}`` — ``je_gruppe``
    ist die Liste der Durchmesser in Gruppen-Reihenfolge, ``groesste`` der
    Durchmesser der **groessten** Gruppe, ``max`` der groesste ueberhaupt.
    """
    pc = _personen_cluster()
    liste = _liste(eintraege)
    durchmesser: list = []
    groessen: list = []
    for gruppe in _liste(gruppen):
        indizes = [int(index) for index in _liste(gruppe) if _ist_zahl(index)]
        groessen.append(len(indizes))
        vektoren = [pc._vektor_von(liste[index]) for index in indizes
                    if 0 <= index < len(liste)]
        vektoren = [vektor for vektor in vektoren if vektor is not None]
        groesster = None
        for a_pos in range(len(vektoren)):
            for b_pos in range(a_pos + 1, len(vektoren)):
                wert = _cosinus_distanz(vektoren[a_pos], vektoren[b_pos])
                if wert is None:
                    continue
                if groesster is None or wert > groesster:
                    groesster = wert
        durchmesser.append(groesster if groesster is not None else 0.0)
    if not durchmesser:
        return {"je_gruppe": [], "groesste": None, "max": None}
    ziel = max(range(len(durchmesser)), key=lambda i: (groessen[i], -i))
    return {"je_gruppe": durchmesser,
            "groesste": durchmesser[ziel],
            "max": max(durchmesser)}


def kettenmass(paare, gruppen, eintraege, schwelle) -> dict:
    """Das **Kettenmass** einer Schwelle — wie weit die Gruppen auseinandergezogen sind.

    Gemessen an den Bild-Paaren der Bodenwahrheit: wie viele Paare liegen
    **innerhalb** einer Gruppe (verschmolzen) und davon wie viele **weiter
    auseinander als die Schwelle selbst**. Ein solches Paar kann nur durch
    **transitives Verketten** in einer Gruppe sein — es ist der direkte Beleg
    fuer die Ursache (Expansion vom Kernpunkt), nicht nur ihr Symptom.

    Rueckgabe ``{"paare_innerhalb", "paare_weit", "anteil_weit",
    "distanz_median_weit", "durchmesser"}`` — ``durchmesser`` kommt aus
    ``gruppendurchmesser`` (auch ueber die nicht-paarigen Punkte der Gruppe).
    """
    zuordnung = _gruppen_zuordnung(gruppen)
    innerhalb = 0
    weit = 0
    distanzen: list = []
    for paar in _liste(paare):
        if not isinstance(paar, dict):
            continue
        ia = _paar_index(paar, "a")
        ib = _paar_index(paar, "b")
        ga = zuordnung.get(ia) if ia is not None else None
        gb = zuordnung.get(ib) if ib is not None else None
        if ga is None or gb is None or ga != gb:
            continue
        innerhalb += 1
        wert = paar.get("distanz")
        if not _ist_zahl(wert):
            continue
        if float(wert) > float(schwelle):
            weit += 1
            distanzen.append(float(wert))
    median = None
    if distanzen:
        median = float(np.median(np.asarray(distanzen, dtype=float)))
    return {"paare_innerhalb": innerhalb,
            "paare_weit": weit,
            "anteil_weit": (weit / innerhalb) if innerhalb else 0.0,
            "distanz_median_weit": median,
            "durchmesser": gruppendurchmesser(gruppen, eintraege)}


# ── 4. Eine Schwelle messen (rein) ────────────────────────────────────────

def _staerke(werte):
    """``{min, p05, median, p90, max, anzahl}`` einer Zahlenliste — oder ``None``."""
    zahlen = [float(wert) for wert in _liste(werte)]
    if not zahlen:
        return None
    reihe = np.asarray(zahlen, dtype=float)
    q05, q50, q90 = np.percentile(reihe, QUANTILE)
    return {"anzahl": len(zahlen),
            "min": float(np.min(reihe)),
            "p05": float(q05),
            "median": float(q50),
            "p90": float(q90),
            "max": float(np.max(reihe))}


def distanzpaare(eintraege, beschriftungen) -> dict:
    """Cosinus-Distanzen aller Paare, getrennt nach gleicher/fremder Beschriftung.

    **Reine Messung an den Vektoren** — keine Schwelle, kein Cluster. Zurueck
    kommt ``{"gleich", "fremd", "naechster_fremd", "gleich_werte",
    "fremd_werte"}``: ``gleich``/``fremd``/``naechster_fremd`` sind
    ``_staerke``-Kennzahlen (oder ``None``), ``*_werte`` die rohen Listen.
    Paare ohne brauchbare Beschriftung zaehlen nicht (sie sind kein Beleg);
    Vektoren unbrauchbarer Eintraege ergeben keine Paare.
    """
    pc = _personen_cluster()
    liste_eintraege = _liste(eintraege)
    labels = _liste(beschriftungen)
    vektoren = [pc._vektor_von(eintrag) for eintrag in liste_eintraege]
    brauchbar = [nummer for nummer, vektor in enumerate(vektoren)
                 if vektor is not None]
    gleich: list = []
    fremd: list = []
    naechster_fremd: list = []
    if len(brauchbar) < 2:
        return {"gleich": None, "fremd": None, "naechster_fremd": None,
                "gleich_werte": gleich, "fremd_werte": fremd}
    matrix = pc._einheit([vektoren[nummer] for nummer in brauchbar])
    aehnlich = np.clip(matrix @ matrix.T, -1.0, 1.0)
    abstand = 1.0 - aehnlich
    for a, ia in enumerate(brauchbar):
        bestes = None
        la = labels[ia] if ia < len(labels) else None
        for b, ib in enumerate(brauchbar):
            if b <= a:
                continue
            lb = labels[ib] if ib < len(labels) else None
            if la is None or lb is None:
                continue
            wert = float(abstand[a, b])
            if la == lb:
                gleich.append(wert)
            else:
                fremd.append(wert)
                if bestes is None or wert < bestes:
                    bestes = wert
        if bestes is not None:
            naechster_fremd.append(bestes)
    return {"gleich": _staerke(gleich), "fremd": _staerke(fremd),
            "naechster_fremd": _staerke(naechster_fremd),
            "gleich_werte": gleich, "fremd_werte": fremd}


def schwelle_messen(eintraege, beschriftungen, schwelle, min_nachbarn=None,
                    paare=None) -> dict:
    """Eine Schwelle vollstaendig messen — rein (kein I/O, keine Schwellenaenderung).

    Cluster mit ``personen_cluster.vektoren_clustern`` und beschreibt das
    Ergebnis. Zwei Masse stehen nebeneinander, **deutlich getrennt**:

      * **Bodenwahrheit (Identitaet)** — ``verschmelzungsquote`` und
        ``kettenmass`` (Abschnitt 3): zwei **erkennbare** Gesichter im
        **selben** Bild sind **verschiedene** Personen. "x von y Paaren in
        derselben Gruppe" ist damit eine echte Falschaussage des Verfahrens.
      * **Strukturmass (Anlass-Mix je Cluster)** — ``falsche_cluster``: wie
        viele Cluster Gesichter aus mehr als einer Beschriftung (Anlass)
        zusammenlegen. Das ist **keine** Identitaetswahrheit: ein Anlass
        enthaelt legitim viele Personen.

    ``min_nachbarn`` faellt auf ``CLUSTER_MIN_NACHBAR`` zurueck, wenn es keine
    Zahl ist. ``paare`` (aus ``bild_paare``) darf hereingereicht werden, damit
    ein Lauf es nicht je Schwelle neu rechnet.
    """
    pc = _personen_cluster()
    if not _ist_zahl(schwelle):
        raise SchwelleFehler("Mess-Schwelle ist keine Zahl.")
    if not _ist_zahl(min_nachbarn):
        min_nachbarn = pc.CLUSTER_MIN_NACHBAR
    schwelle = float(schwelle)
    min_nachbarn = max(1, int(min_nachbarn))

    gruppen = pc.vektoren_clustern(eintraege, schwelle, min_nachbarn)
    beschrieben = cluster_beschriften(gruppen, eintraege, beschriftungen)
    falsche = falsche_cluster(beschrieben)
    groessen = [eintrag["groesse"] for eintrag in beschrieben]
    gesichter = sum(groessen)
    in_falschen = sum(eintrag["groesse"] for eintrag in falsche)
    if paare is None:
        paare = bild_paare(eintraege)
    verschmelzung = verschmelzungsquote(paare, gruppen)
    ketten = kettenmass(paare, gruppen, eintraege, schwelle)
    return {
        "schwelle": schwelle,
        "min_nachbarn": min_nachbarn,
        "gruppen": len(beschrieben),
        "groessen": groessen,
        "groesste": max(groessen) if groessen else 0,
        "gesichter": gesichter,
        # ── Bodenwahrheit (Bild-Paare erkennbarer Gesichter) ──
        "personen_paare": verschmelzung["paare"],
        "verschmolzene_paare": verschmelzung["verschmolzen"],
        "verschmelzungsquote": verschmelzung["quote"],
        "kettenmass": ketten,
        # ── Strukturmass (Anlass-Mix je Cluster), KEINE Identitaetswahrheit ──
        "strukturmass": {
            "falsche_cluster": len(falsche),
            "gesichter_in_falschen": in_falschen,
            "anteil_in_falschen": (in_falschen / gesichter) if gesichter else 0.0,
            "hinweis": ("Anlass-Mix je Cluster ist ein STRUKTURMASS, keine "
                        "Identitaetswahrheit: ein Anlass enthaelt legitim viele "
                        "verschiedene Personen, und dieselbe Person kann in "
                        "mehreren Anlaessen vorkommen."),
        },
        "falsche_cluster": len(falsche),
        "gesichter_in_falschen": in_falschen,
        "anteil_in_falschen": (in_falschen / gesichter) if gesichter else 0.0,
        "cluster": beschrieben,
        "falsche": falsche,
    }


def verlauf_messen(eintraege, beschriftungen, schwellen, min_nachbarn=None,
                   paare=None) -> list:
    """Mehrere Schwellen nacheinander messen — Liste aus ``schwelle_messen``.

    Die Reihenfolge der Schwellen bleibt erhalten; unbrauchbare Werte (keine
    Zahl) fallen weg. Bereits gemessene Schwellen kommen nicht doppelt vor.
    ``paare`` (aus ``bild_paare``) wird durchgereicht, damit die
    Bild-Paare der Bodenwahrheit nicht je Schwelle neu gerechnet werden.
    """
    ergebnis: list[dict] = []
    gesehen: set = set()
    for schwelle in _liste(schwellen):
        if not _ist_zahl(schwelle):
            continue
        wert = float(schwelle)
        if wert in gesehen:
            continue
        gesehen.add(wert)
        ergebnis.append(schwelle_messen(eintraege, beschriftungen, wert,
                                        min_nachbarn, paare=paare))
    return ergebnis


# ── 4. Empfehlung (aus der Messung, nicht aus dem Bauch) ──────────────────

def empfehlung_bauen(verlauf, trenn, schwelle_heute=None) -> dict:
    """Aus Messung + Trennschaerfe eine begruendete Empfehlung bauen — rein.

    Die Empfehlung leitet sich aus **zwei getrennten** Dingen ab und nennt
    beide ausdruecklich:

      * **Bodenwahrheit (Identitaet, hart)** — ``verschmelzungsquote`` aus
        ``verlauf``: zwei **erkennbare** Gesichter im **selben** Bild sind
        **verschiedene** Personen. Jedes solche Paar, das in **einer** Gruppe
        landet, ist eine **belegte Falschaussage** des Verfahrens. Zusammen mit
        ``kettenmass`` (Paare, die innerhalb einer Gruppe **weiter auseinander
        liegen als die Schwelle**) belegt das die Ursache: **transitives
        Verketten** des Dichte-Verfahrens (Expansion vom Kernpunkt).
      * **Strukturmass (Anlass-Mix je Cluster, weich)** — ``falsche_cluster``
        und ``trenn``: ein Anlass enthaelt legitim viele Personen, dieselbe
        Person kann in mehreren Anlaessen vorkommen. Das ist **keine**
        Identitaetswahrheit, sondern die einzige belastbare **Struktur** am
        Bestand. Es taugt als Hinweis, nicht als Beweis.

    Rueckgabe ``{"dringend", "trennbar", "heute_schwelle", "heute_falsche",
    "heute_groesste", "heute_paare", "heute_verschmolzen",
    "heute_verschmelzungsquote", "feinste_schwelle", "feinste_falsche",
    "feinste_verschmelzungsquote", "kernaussage", "vorschlag", "beleg",
    "struktur_hinweis"}``.
    """
    pc = _personen_cluster()
    reihe = [eintrag for eintrag in _liste(verlauf) if isinstance(eintrag, dict)]
    if schwelle_heute is None:
        schwelle_heute = pc.CLUSTER_SCHWELLE
    heute = None
    for eintrag in reihe:
        if eintrag.get("schwelle") == float(schwelle_heute):
            heute = eintrag
            break
    feinste = None
    for eintrag in reihe:
        if feinste is None or eintrag.get("schwelle", 1.0) < feinste.get(
                "schwelle", 1.0):
            feinste = eintrag

    trennbar = None
    beleg = ""
    gleich = (trenn or {}).get("gleich") if isinstance(trenn, dict) else None
    fremd = (trenn or {}).get("fremd") if isinstance(trenn, dict) else None
    if isinstance(gleich, dict) and isinstance(fremd, dict):
        trennbar = float(fremd["min"]) > float(gleich["median"])
        beleg = (f"Strukturmass Trennschaerfe: innerhalb median "
                 f"{gleich['median']:.4f}; zwischen min {fremd['min']:.4f}, "
                 f"median {fremd['median']:.4f}")

    def _quote(eintrag):
        wert = eintrag.get("verschmelzungsquote") if isinstance(eintrag, dict) else None
        return float(wert) if _ist_zahl(wert) else None

    heute_quote = _quote(heute)
    feinste_quote = _quote(feinste)
    heute_paare = heute.get("personen_paare") if heute else None
    heute_verschmolzen = heute.get("verschmolzene_paare") if heute else None

    # ── Kernaussage: zuerst die harte Bodenwahrheit, dann die Struktur ──
    if not heute_paare:
        boden = ("Bodenwahrheit: ohne Bild-Paare erkennbarer Gesichter ist am "
                 "heutigen Wert keine Identitaetsaussage moeglich.")
    elif (heute_quote or 0) > 0:
        boden = (f"Bodenwahrheit (hart): {heute_verschmolzen} von "
                 f"{heute_paare} Bild-Paaren erkennbarer Gesichter liegen beim "
                 f"heutigen Wert {float(schwelle_heute)} in DERSELBEN Gruppe - "
                 "zwei verschiedene Personen sind damit belegt zusammengelegt.")
    else:
        boden = (f"Bodenwahrheit (hart): 0 von {heute_paare} Bild-Paaren "
                 f"erkennbarer Gesichter liegen beim heutigen Wert "
                 f"{float(schwelle_heute)} in derselben Gruppe.")

    if trennbar is False:
        struktur = ("Das Anlass-Mass sortiert sich NICHT (es ist nur ein "
                    "Strukturmass): die kleinste Distanz zwischen zwei "
                    "Anlaessen liegt unter dem Median innerhalb eines "
                    "Anlasses - keine Schwelle kann die Anlaesse sauber "
                    "trennen.")
    elif trennbar is True:
        struktur = ("Das Anlass-Strukturmass trennt sich: die kleinste Distanz "
                    "zwischen zwei Anlaessen liegt ueber dem Median innerhalb - "
                    "als Hinweis brauchbar, als Identitaetsbeweis nicht.")
    else:
        struktur = ("Ohne Beschriftungspaare in beiden Klassen ist keine "
                    "Aussage zum Anlass-Strukturmass moeglich.")
    kernaussage = boden + " " + struktur

    # ── Vorschlag: der Hebel ist die Verkettung, nicht die Schwelle allein ──
    if (feinste_quote or 0) > 0:
        weit = (feinste.get("kettenmass") or {}).get("paare_weit")
        vorschlag = (
            f"Auch bei der feinsten gemessenen Schwelle "
            f"({feinste.get('schwelle')}) liegen noch "
            f"{feinste.get('verschmolzene_paare')} von "
            f"{feinste.get('personen_paare')} Bild-Paaren in derselben Gruppe"
            + (f" ({weit} davon weiter auseinander als die Schwelle selbst)"
               if isinstance(weit, int) else "")
            + ". Das ist transitives Verketten des Dichte-Verfahrens "
              "(Expansion vom Kernpunkt) - der Hebel ist die Verkettung "
              "(z. B. Vollstaendigkeits- oder Mittelpunkt-Verknuepfung bzw. "
              "eine Groessen-Grenze), nicht die Schwelle allein. "
              "Empfehlung: zuerst die Verkettung messen/ersetzen, dann die "
              "Schwelle neu messen. Eine Schwellenabsenkung ist nur nach "
              "dieser Messung zu begruenden.")
    elif trennbar is False:
        vorschlag = ("Die Anlass-Beschriftungen (Strukturmass) trennen sich bei "
                     "keiner Schwelle. Der Hebel ist daher nicht die Schwelle, "
                     "sondern die Verkettung: das Dichte-Verfahren haelt die "
                     "Punkte ueber Kernpunkt-Expansion zusammen. Empfehlung: "
                     "die Verkettung ersetzen (Vollstaendigkeits- oder "
                     "Mittelpunkt-Verknuepfung bzw. eine Groessen-Grenze), dann "
                     "die Schwelle neu messen.")
    elif feinste is not None and not feinste.get("falsche_cluster"):
        vorschlag = (f"Bei der feinsten gemessenen Schwelle "
                     f"({feinste.get('schwelle')}) gibt es keinen "
                     "Anlass-Mix im Cluster und kein verschmolzenes Bild-Paar - "
                     "dann ist die Schwellenwahl der Hebel und mit dieser "
                     "Messung begruendbar.")
    else:
        vorschlag = "Keine Messwerte - kein Vorschlag moeglich."

    return {
        "dringend": bool((heute_quote or 0) > 0 or trennbar is False
                         or (heute and heute.get("falsche_cluster"))),
        "trennbar": trennbar,
        "heute_schwelle": float(schwelle_heute),
        "heute_falsche": heute.get("falsche_cluster") if heute else None,
        "heute_groesste": heute.get("groesste") if heute else None,
        "heute_paare": heute_paare,
        "heute_verschmolzen": heute_verschmolzen,
        "heute_verschmelzungsquote": heute_quote,
        "feinste_schwelle": feinste.get("schwelle") if feinste else None,
        "feinste_falsche": feinste.get("falsche_cluster") if feinste else None,
        "feinste_verschmelzungsquote": feinste_quote,
        "kernaussage": kernaussage,
        "vorschlag": vorschlag,
        "beleg": beleg,
        "struktur_hinweis": ("'falsche_cluster' ist ein STRUKTURMASS "
                             "(Anlass-Mix je Cluster), KEINE "
                             "Identitaetswahrheit: ein Anlass enthaelt legitim "
                             "viele Personen, dieselbe Person kann in mehreren "
                             "Anlaessen vorkommen."),
    }


# ── 5. Der Bericht ────────────────────────────────────────────────────────

def bericht_bauen(verlauf, trenn=None, empfehlung=None, *, beschriftung="",
                  zeilen_gesamt=0, ungueltige_zeilen=0, gesichter=0,
                  eintraege=0, bekannte_beschriftungen=None,
                  personen_paare=0, stand="") -> dict:
    """Die Messung als Dict — **rein**, ohne Dateizugriff.

    Felder: ``beschriftung``, ``zeilen_gesamt``, ``ungueltige_zeilen``,
    ``eintraege`` (geclusterte Gesichter), ``gesichter`` (Eintraege mit
    Beschriftung), ``beschriftungen`` (Anzahl bekannter Anlass-Kennungen),
    ``personen_paare`` (Bodenwahrheit: Bild-Paare erkennbarer Gesichter),
    ``bodenwahrheit`` (der Satz, warum das die Wahrheit ist),
    ``strukturmass_hinweis`` (der Satz, warum der Anlass-Mix keine Wahrheit
    ist), ``verlauf``, ``trennschaerfe``, ``empfehlung`` und ``stand``.
    """
    reihe = [eintrag for eintrag in _liste(verlauf) if isinstance(eintrag, dict)]
    bekannt = bekannte_beschriftungen
    if not _ist_zahl(bekannt):
        namen = set()
        for eintrag in reihe:
            for cluster in _liste(eintrag.get("cluster")):
                if isinstance(cluster, dict):
                    for name in cluster.get("beschriftungen") or {}:
                        namen.add(name)
        bekannt = len(namen)
    return {
        "beschriftung": _text(beschriftung),
        "zeilen_gesamt": int(zeilen_gesamt) if _ist_zahl(zeilen_gesamt) else 0,
        "ungueltige_zeilen": int(ungueltige_zeilen)
        if _ist_zahl(ungueltige_zeilen) else 0,
        "eintraege": int(eintraege) if _ist_zahl(eintraege) else 0,
        "gesichter": int(gesichter) if _ist_zahl(gesichter) else 0,
        "beschriftungen": int(bekannt),
        "personen_paare": int(personen_paare) if _ist_zahl(personen_paare) else 0,
        "bodenwahrheit": (
            "Bodenwahrheit: zwei ERKENNBARE Gesichter im SELBEN Bild sind "
            "verschiedene Personen (Flaechenanteil >= ANTEIL_ERKENNBAR = "
            "0,005; eine Person ist einmal im Bild). Ausnahmen: Spiegelung, "
            "Plakat/Monitor, Zwillinge - daher Naeherung, keine absolute "
            "Wahrheit."),
        "strukturmass_hinweis": (
            "Der Anlass-Mix je Cluster ('falsche_cluster') ist ein "
            "STRUKTURMASS, KEINE Identitaetswahrheit: ein Anlass enthaelt "
            "legitim viele verschiedene Personen, und dieselbe Person kann in "
            "mehreren Anlaessen vorkommen."),
        "verlauf": reihe,
        "trennschaerfe": trenn if isinstance(trenn, dict) else {},
        "empfehlung": empfehlung if isinstance(empfehlung, dict) else {},
        "stand": stand or datetime.datetime.now().isoformat(timespec="seconds"),
    }


def bericht_text(bericht) -> str:
    """Den Bericht als Klartext-Deutsch aufbereiten (feste Reihenfolge).

    Zwei Bloecke: zuerst die **Bodenwahrheit** (Bild-Paare, Verschmelzung,
    Kettenmass je Schwelle), dann das **Strukturmass** (Anlass-Mix je Cluster).
    """
    b = bericht if isinstance(bericht, dict) else {}
    reihe = [eintrag for eintrag in _liste(b.get("verlauf"))
             if isinstance(eintrag, dict)]
    zeilen = [
        f"Beschriftung: {b.get('beschriftung') or '-'}   "
        f"Zeilen: {_zahl(b.get('zeilen_gesamt'))}   "
        f"ungueltig: {_zahl(b.get('ungueltige_zeilen'))}   "
        f"geclusterte Gesichter: {_zahl(b.get('eintraege'))}   "
        f"mit Beschriftung: {_zahl(b.get('gesichter'))}   "
        f"Anlass-Kennungen: {_zahl(b.get('beschriftungen'))}",
        f"BODENWAHRHEIT (Identitaet): {b.get('bodenwahrheit') or ''}",
        f"Bild-Paare erkennbarer Gesichter: {_zahl(b.get('personen_paare'))}",
        "",
        "Schwelle   Gruppen   groesste   Bild-Paare   verschmolzen   Quote   "
        "weit(>Schwelle)   Ketten-Durchmesser",
    ]
    for eintrag in reihe:
        ketten = eintrag.get("kettenmass") or {}
        durchmesser = (ketten.get("durchmesser") or {}).get("groesste")
        zeilen.append(
            f"{eintrag.get('schwelle'):>7.5f}   {_zahl(eintrag.get('gruppen')):>7}   "
            f"{_zahl(eintrag.get('groesste')):>8}   "
            f"{_zahl(eintrag.get('personen_paare')):>10}   "
            f"{_zahl(eintrag.get('verschmolzene_paare')):>11}   "
            f"{100.0 * float(eintrag.get('verschmelzungsquote') or 0.0):>6.1f} %   "
            f"{_zahl(ketten.get('paare_weit')):>15}   "
            + (f"{float(durchmesser):.4f}" if _ist_zahl(durchmesser) else "-"))
    zeilen.extend([
        "",
        f"STRUKTURMASS (Anlass-Mix je Cluster, KEINE Wahrheit): "
        f"{b.get('strukturmass_hinweis') or ''}",
        "Schwelle   Anlass-Mix-Cluster   Gesichter_in_Mix   Anteil",
    ])
    for eintrag in reihe:
        zeilen.append(
            f"{eintrag.get('schwelle'):>7.5f}   {_zahl(eintrag.get('falsche_cluster')):>17}   "
            f"{_zahl(eintrag.get('gesichter_in_falschen')):>16}   "
            f"{100.0 * float(eintrag.get('anteil_in_falschen') or 0.0):>6.1f} %")
    trenn = b.get("trennschaerfe") if isinstance(b.get("trennschaerfe"), dict) else {}
    for name in ("gleich", "fremd", "naechster_fremd"):
        staerke = trenn.get(name)
        if not isinstance(staerke, dict):
            continue
        zeilen.append(
            f"Distanz {name}: n={_zahl(staerke.get('anzahl'))}   "
            f"min={staerke.get('min'):.4f}   p05={staerke.get('p05'):.4f}   "
            f"median={staerke.get('median'):.4f}   p90={staerke.get('p90'):.4f}   "
            f"max={staerke.get('max'):.4f}")
    empfehlung = b.get("empfehlung") if isinstance(b.get("empfehlung"), dict) else {}
    if empfehlung:
        zeilen.append("Empfehlung: " + str(empfehlung.get("kernaussage", "")))
        if empfehlung.get("beleg"):
            zeilen.append("Beleg: " + str(empfehlung.get("beleg")))
        zeilen.append("Vorschlag: " + str(empfehlung.get("vorschlag", "")))
    return "\n".join(zeilen)


# ── 6. Schutz: nur ausserhalb des Repos schreiben ─────────────────────────

def pruefe_ausserhalb_repo(pfad: str) -> str:
    """Sicherstellen, dass ein Ausgabeziel AUSSERHALB des Repos liegt.

    Reicht an ``personen_cluster.pruefe_ausserhalb_repo`` durch — dieselbe
    Regel, dieselbe Meldung (kein zweites Verfahren).
    """
    return _personen_cluster().pruefe_ausserhalb_repo(pfad)


def bericht_schreiben(pfad: str, bericht) -> str:
    """Den Messbericht als JSON schreiben — atomar, nur ausserhalb des Repos."""
    pruefe_ausserhalb_repo(pfad)
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8") as datei:
        json.dump(bericht, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    os.replace(temp, pfad)
    return pfad


# ── 7. Einen ganzen Messlauf rechnen (rein) ───────────────────────────────

def messlauf(bilder, zuordnung, schwellen=None, min_nachbarn=None,
             beschriftung="", ungueltige_zeilen=0) -> dict:
    """Den ganzen Messlauf rechnen — **ohne** Schreiben, ohne Netz, ohne Bild.

    Ablauf: je Bild die N9a-Entscheidung -> die freigegebenen Gesichter
    einsammeln -> Schwellen messen -> Trennschaerfe -> Empfehlung -> Bericht.
    Rueckgabe ``{"entscheidungen", "eintraege", "beschriftungen", "verlauf",
    "trennschaerfe", "empfehlung", "bericht"}`` — alles reine Daten.
    """
    pc = _personen_cluster()
    liste = _liste(bilder)
    entscheidungen = [pc.bild_entscheidung(bild) for bild in liste]
    eintraege = pc.geclusterte_eintraege(liste, entscheidungen)
    labels = beschriftung_je_eintrag(eintraege, zuordnung)
    bekannt = [label for label in labels if label is not None]
    # Bodenwahrheit: Paare erkennbarer Gesichter im SELBEN Bild (einmal rechnen).
    paare = bild_paare(eintraege)
    reihenfolge = list(schwellen) if schwellen else list(SCHWELLEN_STANDARD)
    if pc.CLUSTER_SCHWELLE not in reihenfolge:
        reihenfolge = [pc.CLUSTER_SCHWELLE] + reihenfolge
    verlauf = verlauf_messen(eintraege, labels, reihenfolge, min_nachbarn,
                             paare=paare)
    trenn = distanzpaare(eintraege, labels)
    empfehlung = empfehlung_bauen(verlauf, trenn, pc.CLUSTER_SCHWELLE)
    bericht = bericht_bauen(verlauf, trenn, empfehlung,
                            beschriftung=beschriftung,
                            zeilen_gesamt=len(liste) + int(ungueltige_zeilen or 0),
                            ungueltige_zeilen=int(ungueltige_zeilen or 0),
                            gesichter=len(bekannt), eintraege=len(eintraege),
                            bekannte_beschriftungen=len(set(bekannt)),
                            personen_paare=len(paare))
    return {"entscheidungen": entscheidungen, "eintraege": eintraege,
            "beschriftungen": labels, "paare": paare, "verlauf": verlauf,
            "trennschaerfe": trenn,
            "empfehlung": empfehlung, "bericht": bericht}


# ── 8. Kommandozeile ──────────────────────────────────────────────────────

def _schwellen_aus_text(text):
    """``"0.45,0.3,0.1"`` -> ``[0.45, 0.3, 0.1]``; unbrauchbare Teile fallen weg."""
    if not isinstance(text, str):
        return []
    werte: list = []
    for teil in text.replace(";", ",").split(","):
        teil = teil.strip()
        if not teil:
            continue
        try:
            werte.append(float(teil))
        except ValueError:
            continue
    return werte


def main(argv=None) -> int:
    """Kommandozeilen-Teil: Schwellen messen, Bericht zeigen (Standard: trocken).

    Standard ist der **Trockenlauf**: die Messung wird nur gezeigt, nichts
    geschrieben. Geschrieben wird nur mit ``--schreiben`` (und ``--trocken``
    hat Vorrang). Ein Ausgabeziel **innerhalb** des Repos ist ein Fehler.
    Es wird **keine** Schwelle geaendert — nur gemessen.
    """
    zerleger = argparse.ArgumentParser(
        description="Schwellen-Messwerkzeug N9e: misst am echten Bestand, ob "
                    "CLUSTER_SCHWELLE die Beschriftungen trennt, beziffert "
                    "falsch zusammengelegte Cluster und gibt eine begruendete "
                    "Empfehlung. Es aendert KEINE Schwelle.")
    zerleger.add_argument("--vektoren", dest="vektoren", default=STANDARD_VEKTOREN,
                          help="Vektordatei (JSONL, ausserhalb des Repos)")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Sortierplan (JSON, nur lesend) fuer die "
                               "Beschriftung")
    zerleger.add_argument("--beschriftung", dest="beschriftung",
                          default=BESCHRIFTUNG_STANDARD,
                          help="Feld im Sortierplan als Bodenwahrheit "
                               "(Vorgabe thema_quelle; 'von_name' = "
                               "Burst-Familie)")
    zerleger.add_argument("--schwellen", dest="schwellen", default=None,
                          help="Komma-Liste der Mess-Schwellen "
                               "(Vorgabe: Gitter um den heutigen Wert)")
    zerleger.add_argument("--min-nachbarn", dest="min_nachbarn", type=int,
                          default=None,
                          help="Nachbarn je Kernpunkt (Vorgabe: N9a-Wert)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei des Berichts (PFLICHT ausserhalb "
                               "des Repos)")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nichts schreiben (hat Vorrang vor --schreiben)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="den Bericht wirklich schreiben")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.trocken)
    if schreiben:
        pruefe_ausserhalb_repo(args.ausgabe)

    try:
        pc = _personen_cluster()
        eingelesen = pc.zeilen_lesen(args.vektoren)
        zuordnung = plan_beschriftungen_lesen(args.plan, args.beschriftung)
        schwellen = _schwellen_aus_text(args.schwellen) or list(SCHWELLEN_STANDARD)

        print("Schwellen-Messwerkzeug N9e — "
              + ("Trockenlauf (es wird NICHTS geschrieben)" if not schreiben
                 else "Schreiben ist eingeschaltet"))
        print(f"Vektordatei: {args.vektoren}")
        print(f"Sortierplan: {args.plan}   Beschriftung: {args.beschriftung} "
              f"({len(zuordnung)} Zuordnungen)")
        print(f"CLUSTER_SCHWELLE (N9a, unveraendert): {pc.CLUSTER_SCHWELLE}   "
              f"CLUSTER_MIN_NACHBAR: {pc.CLUSTER_MIN_NACHBAR}")

        lauf = messlauf(eingelesen["bilder"], zuordnung, schwellen,
                        args.min_nachbarn, beschriftung=args.beschriftung,
                        ungueltige_zeilen=eingelesen["ungueltige_zeilen"])
        print(bericht_text(lauf["bericht"]))

        if schreiben:
            bericht_schreiben(args.ausgabe, lauf["bericht"])
            print(f"Bericht geschrieben: {args.ausgabe}")
        else:
            print(f"Geplant (nicht geschrieben): {args.ausgabe}")
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except SchwelleFehler as problem:
        print(f"Fehler: {problem}")
        return 2
    except _personen_cluster().PersonenFehler as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
