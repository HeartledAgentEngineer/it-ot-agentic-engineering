"""Phasen und Vorbilder fuer die Gruppierung v2 (Gruppierung v2, G2, 15.10.2026).

Dieses Modul ist **rein** (nur numpy, kein Lesen, kein Schreiben, kein Netz) und
wird von ``personen_gruppieren.py`` (``--verfahren v2``) und
``gruppierung_bewerten.py`` benutzt. Hier steht, was eine Gruppe ueber die Zeit
beschreibt:

* ``sauber(gesicht)`` - ist ein Fund sicher UND nicht grob aufgeloest? Nur
  saubere Gesichter duerfen eine Gruppe **gruenden**. Die Grenzen (score 0,90 und
  Ausschnittbreite 64 Pixel) stehen NUR in ``mittelpunkt_rauschen_messen.py``
  (``MIN_SCORE``, ``MIN_BREITE``) und werden von dort importiert, nicht doppelt
  geschrieben.
* ``phasen_bilden(vektoren, jahre)`` - eine Gruppe wird nicht mehr durch EINEN
  Mittelpunkt beschrieben, sondern durch mehrere **Phasen-Mittelpunkte**
  (``(von_jahr, bis_jahr, mittelpunkt, anzahl)``). Benachbarte Aufnahmejahre
  bleiben in einer Phase, solange der Mittelpunkt des naechsten Jahres sich
  vom laufenden Phasen-Mittelpunkt um weniger als ``PHASE_BRUCH`` (Cosinus-
  Distanz) entfernt; Phasen mit weniger als ``PHASE_MIN`` Gesichtern werden dem
  aehnlicheren Nachbarn zugeschlagen; es gibt hoechstens ``PHASE_MAX`` Phasen.
  Gesichter ohne Datum zaehlen zur **Gesamtphase** (``von = bis = None``).
* ``vergleichen(vektor, jahr, phasen)`` - Aehnlichkeit eines Gesichts zu einer
  Gruppe: Cosinus zum besten **passenden** Phasen-Mittelpunkt, "passend" heisst:
  das Aufnahmejahr liegt in der Phase oder hoechstens ``PHASE_TOLERANZ`` Jahre
  daneben. Ohne Datum zaehlt der beste aller Phasen.
* Blockweise Hilfen (``phasen_satz``, ``beste_gruppen``, ``verschmelz_paare``,
  ``andocken``): rechnen immer nur ``BLOCK`` Gesichter gegen alle Phasen - nie
  eine n x n-Matrix ueber alle Gesichter.

Die Konstanten sind **Startwerte**. Sie sind aus dem Bestehenden abgeleitet
(Cosinus-Schwellen 0,45 / 0,55 / 0,60 des Gruppierens, die gemessene Verschiebung
von Phasen-Mittelpunkten durch Rauschen in
``docs/changelog-2026-10-14-mittelpunkte-rauschen.md``), NICHT aus einer
Messung auf den echten Daten dieser Gruppierung. Erst der Messlauf G4
(``gruppierung_bewerten.py``) zeigt, ob sie taugen; keine Schwelle wird ohne
Zahl daraus geaendert.
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))


def _nachbar(name: str):
    """Ein Nachbarmodul importieren; im Test-Ladeweg ueber den Dateipfad."""
    try:
        return __import__(name)
    except ImportError:                          # pragma: no cover
        spez = importlib.util.spec_from_file_location(
            name, os.path.join(HIER, name + ".py"))
        if spez is None or spez.loader is None:  # pragma: no cover
            raise
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        return modul


_messer = _nachbar("mittelpunkt_rauschen_messen")

# ── "sauber": die Grenzen stehen im Messwerkzeug, hier nur importiert ──────
SAUBER_SCORE = _messer.MIN_SCORE         # 0,90 - ab hier gilt ein Fund als sicher
SAUBER_BREITE = _messer.MIN_BREITE       # 64 px - darunter ist der Ausschnitt grob

# ── Startwerte (von G4 zu pruefen, siehe Moduldoku) ────────────────────────
#
# PHASE_BRUCH (Cosinus-DISTANZ, 1 - Cosinus): so weit darf der Mittelpunkt eines
#   weiteren Jahres vom laufenden Phasen-Mittelpunkt abweichen, ohne eine neue
#   Phase zu beginnen. 0,10 liegt knapp 4x ueber der groessten gemessenen
#   Verschiebung eines Phasen-Mittelpunkts durch Rauschen (0,026, Median 0,003;
#   das ist reines Stichproben-Rauschen, keine Alterung) und gut ein Fuenftel
#   unter der Gruppierungsgrenze (Distanz 0,45): echtes Aelterwerden wird als
#   neue Phase sichtbar, Rauschen nicht.
PHASE_BRUCH = 0.10
# PHASE_MIN: Gesichter, damit ein Phasen-Mittelpunkt als stabil gilt. Ueberschlag
#   (nicht gemessen) bei Cosinus ~0,8 der Gesichter zum Personen-Mittelpunkt:
#   der Mittelwert aus 10 Gesichtern liegt ~0,03 (Distanz) neben dem wahren
#   Mittelpunkt - klar unter PHASE_BRUCH. Das Messwerkzeug nutzt fuer seine
#   Statistik strenger 20; fuer die Bildung genuegen 10.
PHASE_MIN = 10
# PHASE_TOLERANZ (Jahre): so weit darf das Aufnahmejahr eines Gesichts ausserhalb
#   einer Phase liegen und die Phase zaehlt noch als "passend". Grosse Luecken
#   (Kindheit/Erwachsene) schliesst das Verschmelzen ueber die Jahre dazwischen,
#   nicht eine grosse Toleranz.
PHASE_TOLERANZ = 2
# PHASE_MAX: Deckel der Phasen je Gruppe. Der Bestand umfasst rund ein
#   Jahrzehnt; mehr als 8 Phasen waeren feiner als ein Jahr je Phase und treiben
#   nur die Rechenzeit (k x P Vergleiche).
PHASE_MAX = 8
# ANDOCK_SCHWELLE: Mindest-Cosinus eines unsicheren Gesichts zum besten Phasen-
#   Mittelpunkt. Strenger als die Zuordnung sauberer Gesichter (0,55): unsichere
#   Funde sind verrauschter. Aufschlag +0,10.
ANDOCK_SCHWELLE = 0.65
# ANDOCK_ABSTAND: Vorsprung des Besten vor dem besten ANDEREN Namen. Ein Drittel
#   der Spanne zwischen Verschmelzgrenze (0,60) und Zwillingsgrenze (0,45).
ANDOCK_ABSTAND = 0.05

BLOCK = 1024                  # Gesichter je Rechenblock (Speicher)
_NICHT_VERGLEICHBAR = -2.0    # Cosinus liegt in [-1, 1]; darunter = "keine passende Phase"


# ── sauber ────────────────────────────────────────────────────────────────

def sauber(gesicht, min_score: float = SAUBER_SCORE,
           min_breite: float = SAUBER_BREITE) -> bool:
    """Ist das Gesicht sicher UND nicht grob aufgeloest?

    ``gesicht`` ist ein Woerterbuch mit ``score`` und entweder ``breite_px``
    oder ``bbox`` (``[x, y, breite, hoehe]`` - die Breite ist der dritte Wert,
    wie in ``mittelpunkt_rauschen_messen.zuordnung_lesen``). Entscheidung wie
    ``mittelpunkt_rauschen_messen.sauber``; fehlende Werte gelten als NICHT
    sauber.
    """
    breite = gesicht.get("breite_px")
    if breite is None:
        bbox = gesicht.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) > 2:
            breite = bbox[2]
    return _messer.sauber({"score": gesicht.get("score"), "breite_px": breite},
                          min_score, min_breite)


# ── Kleine Helfer ─────────────────────────────────────────────────────────

def jahr_aus(aufnahme):
    """Das Aufnahmejahr aus ``"2019-06-18T11:21:00"`` - sonst ``None``."""
    if isinstance(aufnahme, str) and len(aufnahme) >= 4 and aufnahme[:4].isdigit():
        jahr = int(aufnahme[:4])
        if 1900 <= jahr <= 2100:
            return jahr
    return None


def _einheit(zeilen) -> np.ndarray:
    """Zeilen auf Laenge 1 (float64); Nullzeilen bleiben Null."""
    m = np.asarray(zeilen, dtype=np.float64)
    if m.ndim == 1:
        m = m.reshape(1, -1)
    laenge = np.linalg.norm(m, axis=1, keepdims=True)
    laenge[laenge == 0] = 1.0
    return m / laenge


def _mitte(summe) -> np.ndarray:
    """Normierter Mittelpunkt aus einer Summe von Einheitsvektoren."""
    summe = np.asarray(summe, dtype=np.float64)
    laenge = float(np.linalg.norm(summe))
    return summe / laenge if laenge else summe


def _jahres_abstand(jahr, von, bis) -> int:
    """Wie viele Jahre liegt ``jahr`` ausserhalb von ``[von, bis]`` (0 = innerhalb)."""
    return max(von - jahr, jahr - bis, 0)


# ── Phasen bilden ─────────────────────────────────────────────────────────

def phasen_bilden(vektoren, jahre, bruch: float = PHASE_BRUCH,
                  minimum: int = PHASE_MIN, maximum: int = PHASE_MAX) -> list:
    """Die Phasen einer Gruppe: ``[(von_jahr, bis_jahr, mittelpunkt, anzahl), ...]``.

    ``vektoren`` sind die Gesichtsvektoren der Gruppe, ``jahre`` die Aufnahmejahre
    (``int`` oder ``None``) in gleicher Reihenfolge.

    1. **Jahre durchlaufen** (aufsteigend): Der Mittelpunkt des naechsten Jahres
       bleibt in der laufenden Phase, solange seine Cosinus-Distanz zum LAUFENDEN
       PHASEN-Mittelpunkt hoechstens ``bruch`` betraegt - nicht zum Vorjahr, sonst
       wuerde ein langsam aufwachsendes Kind nie eine neue Phase beginnen. Sonst
       beginnt eine neue Phase.
    2. **Zu kleine Phasen** (weniger als ``minimum`` Gesichter) werden dem
       aehnlicheren Nachbarn zugeschlagen, bis alle gross genug sind oder nur
       noch eine uebrig ist (eine kleine Gruppe hat eine kleine Phase).
    3. **Deckel:** mehr als ``maximum`` Phasen -> das aehnlichste Nachbarpaar
       wird vereint.
    4. **Ohne Datum:** Gesichter ohne Jahr zaehlen zur **Gesamtphase** - ein
       Eintrag ``(None, None, Mittelpunkt aller Gesichter der Gruppe, Anzahl)``,
       der nur angehaengt wird, wenn es undatierte Gesichter gibt. Hat die Gruppe
       gar kein Datum, ist die Gesamtphase die einzige.

    Ein Mittelpunkt ist ein ``float32``-Vektor der Laenge 1. Leere Eingabe -> ``[]``.
    """
    n = len(jahre)
    if n == 0:
        return []
    v = _einheit(vektoren)
    if v.shape[0] != n:
        raise ValueError("Vektoren und Jahre muessen gleich viele Eintraege haben.")
    je_jahr: dict = {}
    undatiert = 0
    for i, jahr in enumerate(jahre):
        if jahr is None:
            undatiert += 1
        else:
            je_jahr.setdefault(int(jahr), []).append(i)
    gesamt_summe = v.sum(axis=0)
    if not je_jahr:
        return [(None, None, _mitte(gesamt_summe).astype(np.float32), n)]

    phasen: list = []                       # [von, bis, summe, anzahl]
    for jahr in sorted(je_jahr):
        stellen = je_jahr[jahr]
        summe = v[stellen].sum(axis=0)
        if phasen:
            lauf = phasen[-1]
            distanz = 1.0 - float(np.dot(_mitte(summe), _mitte(lauf[2])))
            if distanz <= bruch:
                lauf[1], lauf[2], lauf[3] = jahr, lauf[2] + summe, lauf[3] + len(stellen)
                continue
        phasen.append([jahr, jahr, summe, len(stellen)])

    def zuschlagen(i, j):
        """Phase ``i`` in den Nachbarn ``j`` einschmelzen."""
        phasen[j][0] = min(phasen[j][0], phasen[i][0])
        phasen[j][1] = max(phasen[j][1], phasen[i][1])
        phasen[j][2] = phasen[j][2] + phasen[i][2]
        phasen[j][3] = phasen[j][3] + phasen[i][3]
        del phasen[i]

    while len(phasen) > 1:
        kleine = [i for i, p in enumerate(phasen) if p[3] < minimum]
        if not kleine:
            break
        i = min(kleine, key=lambda x: (phasen[x][3], x))
        nachbarn = [j for j in (i - 1, i + 1) if 0 <= j < len(phasen)]
        mitte_i = _mitte(phasen[i][2])
        j = max(nachbarn, key=lambda x: (float(np.dot(mitte_i, _mitte(phasen[x][2]))), -x))
        zuschlagen(i, j)

    while len(phasen) > max(1, int(maximum)):
        beste = min(range(len(phasen) - 1),
                    key=lambda x: (1.0 - float(np.dot(_mitte(phasen[x][2]),
                                                      _mitte(phasen[x + 1][2]))), x))
        zuschlagen(beste + 1, beste)

    ergebnis = [(p[0], p[1], _mitte(p[2]).astype(np.float32), int(p[3])) for p in phasen]
    if undatiert:
        ergebnis.append((None, None, _mitte(gesamt_summe).astype(np.float32), n))
    return ergebnis


def vergleichen(vektor, jahr, phasen, toleranz: int = PHASE_TOLERANZ):
    """Aehnlichkeit eines Gesichts zu einer Gruppe (Cosinus zur passenden Phase).

    ``phasen`` ist das Ergebnis von ``phasen_bilden``. Mit Aufnahmejahr zaehlen
    nur Phasen, die das Jahr enthalten oder hoechstens ``toleranz`` Jahre daneben
    liegen; die Gesamtphase zaehlt fuer datierte Gesichter nur, wenn die Gruppe
    KEINE datierten Phasen hat. Ohne Jahr zaehlt der beste aller Phasen. Rueckgabe:
    der beste Cosinus oder ``None``, wenn keine Phase passt.
    """
    hat_datierte = any(p[0] is not None for p in phasen)
    v = _einheit(vektor)[0]
    beste = None
    for von, bis, mitte, _anzahl in phasen:
        if jahr is None:
            passend = True
        elif von is None:
            passend = not hat_datierte
        else:
            passend = _jahres_abstand(int(jahr), von, bis) <= toleranz
        if passend:
            wert = float(np.dot(v, np.asarray(mitte, dtype=np.float64)))
            beste = wert if beste is None else max(beste, wert)
    return beste


# ── Alle Gruppen auf einmal (blockweise) ───────────────────────────────────

def phasen_satz(phasen_je_gruppe) -> dict:
    """Die Phasen aller Gruppen als Matrix, fuer blockweises Vergleichen.

    ``phasen_je_gruppe[g]`` ist das Ergebnis von ``phasen_bilden`` fuer Gruppe
    ``g`` (mindestens eine Phase). Rueckgabe: ``mitte`` (P x 128, float32),
    ``von``/``bis`` (P, float32, ``nan`` = Gesamtphase), ``gruppe`` (P,),
    ``nur_undatiert`` (P, bool - Gesamtphase einer Gruppe MIT datierten Phasen),
    ``starts`` (k,) Anfang der Phasen je Gruppe, ``k``.
    """
    mitten, von, bis, gruppe, nur_undatiert, starts = [], [], [], [], [], []
    for g, phasen in enumerate(phasen_je_gruppe):
        if not phasen:
            raise ValueError("Eine Gruppe braucht mindestens eine Phase.")
        hat_datierte = any(p[0] is not None for p in phasen)
        starts.append(len(mitten))
        for vo, bi, m, _anzahl in phasen:
            mitten.append(np.asarray(m, dtype=np.float32))
            von.append(np.nan if vo is None else float(vo))
            bis.append(np.nan if bi is None else float(bi))
            gruppe.append(g)
            nur_undatiert.append(vo is None and hat_datierte)
    d = len(mitten[0]) if mitten else 0
    return {
        "mitte": np.asarray(mitten, dtype=np.float32).reshape(len(mitten), d),
        "von": np.asarray(von, dtype=np.float32),
        "bis": np.asarray(bis, dtype=np.float32),
        "gruppe": np.asarray(gruppe, dtype=np.int64),
        "nur_undatiert": np.asarray(nur_undatiert, dtype=bool),
        "starts": np.asarray(starts, dtype=np.int64),
        "k": len(phasen_je_gruppe),
    }


def gruppen_vergleich(v_block, jahre_block, satz, toleranz: int = PHASE_TOLERANZ):
    """Beste Phasen-Aehnlichkeit jedes Gesichts des Blocks zu jeder Gruppe.

    ``v_block`` (b x 128, Einheitsvektoren), ``jahre_block`` (b, ``nan`` = ohne
    Datum). Rueckgabe (b x k, float32); ``_NICHT_VERGLEICHBAR`` (-2) = keine
    Phase der Gruppe passt zum Aufnahmejahr. Rechnet nur b x P - nie n x n.
    """
    if satz["k"] == 0:
        return np.zeros((len(jahre_block), 0), dtype=np.float32)
    s = np.asarray(v_block, dtype=np.float32) @ satz["mitte"].T            # (b, P)
    y = np.asarray(jahre_block, dtype=np.float32)[:, None]
    with np.errstate(invalid="ignore"):
        abstand = np.maximum(np.maximum(satz["von"][None, :] - y,
                                        y - satz["bis"][None, :]), 0.0)
        passend_datiert = np.where(np.isnan(satz["von"])[None, :],
                                   ~satz["nur_undatiert"][None, :], abstand <= toleranz)
    passend = np.where(np.isnan(y), True, passend_datiert)
    s = np.where(passend, s, np.float32(_NICHT_VERGLEICHBAR))
    return np.maximum.reduceat(s, satz["starts"], axis=1)


def beste_gruppen(v, jahre, satz, top: int = 5, toleranz: int = PHASE_TOLERANZ):
    """Die ``top`` aehnlichsten Gruppen je Gesicht, blockweise.

    Rueckgabe ``(gruppen, werte)`` je (n x top), absteigend sortiert. Ein Wert von
    ``_NICHT_VERGLEICHBAR`` heisst: diese Gruppe ist nicht vergleichbar.
    """
    n = v.shape[0]
    k = satz["k"]
    top = max(1, min(int(top), k)) if k else 0
    beste = np.zeros((n, top), dtype=np.int64)
    werte = np.zeros((n, top), dtype=np.float32)
    jahre = np.asarray(jahre, dtype=np.float32)
    for start in range(0, n, BLOCK):
        s = gruppen_vergleich(v[start:start + BLOCK], jahre[start:start + BLOCK],
                              satz, toleranz)                               # (b, k)
        if top < k:
            idx = np.argpartition(-s, top - 1, axis=1)[:, :top]
        else:
            idx = np.tile(np.arange(k), (s.shape[0], 1))
        w = np.take_along_axis(s, idx, axis=1)
        ordnung = np.argsort(-w, axis=1, kind="stable")
        beste[start:start + BLOCK] = np.take_along_axis(idx, ordnung, axis=1)
        werte[start:start + BLOCK] = np.take_along_axis(w, ordnung, axis=1)
    return beste, werte


def jahre_als_zahlen(jahre) -> np.ndarray:
    """``[2019, None, ...]`` -> float32-Feld mit ``nan`` fuer "ohne Datum"."""
    return np.asarray([np.nan if j is None else float(j) for j in jahre], dtype=np.float32)


def verschmelz_paare(satz, schwelle: float, toleranz: int = PHASE_TOLERANZ) -> list:
    """Gruppenpaare ``(aehnlich, a, b)`` (a < b), die sich Phase gegen Phase treffen.

    Verglichen werden nur Phasenpaare, deren Jahre hoechstens ``toleranz`` Jahre
    auseinanderliegen (die Luecke zwischen den Jahresbereichen; ueberlappende
    Bereiche = 0). Eine Gesamtphase wird gegen jede Phase verglichen. Die Gesamtphase
    einer Gruppe MIT datierten Phasen nimmt nicht teil. Absteigend nach
    Aehnlichkeit, bei Gleichstand nach (a, b). Blockweise - nie P x P auf einmal.
    """
    P = satz["mitte"].shape[0]
    zaehlt = ~satz["nur_undatiert"]
    bester: dict = {}
    for start in range(0, P, BLOCK):
        ende = min(P, start + BLOCK)
        s = satz["mitte"][start:ende] @ satz["mitte"].T                   # (b, P)
        von_a, bis_a = satz["von"][start:ende, None], satz["bis"][start:ende, None]
        with np.errstate(invalid="ignore"):
            luecke = np.maximum(np.maximum(satz["von"][None, :] - bis_a,
                                           von_a - satz["bis"][None, :]), 0.0)
            gesamt = np.isnan(von_a) | np.isnan(satz["von"])[None, :]
            nah = np.where(gesamt, True, luecke <= toleranz)
        ga = satz["gruppe"][start:ende, None]
        gb = satz["gruppe"][None, :]
        ok = (nah & (s >= schwelle) & (ga < gb)
              & zaehlt[start:ende, None] & zaehlt[None, :])
        zeilen, spalten = np.nonzero(ok)
        for z, sp in zip(zeilen.tolist(), spalten.tolist()):
            schluessel = (int(ga[z, 0]), int(satz["gruppe"][sp]))
            wert = float(s[z, sp])
            if wert > bester.get(schluessel, -2.0):
                bester[schluessel] = wert
    paare = [(w, a, b) for (a, b), w in bester.items()]
    paare.sort(key=lambda t: (-t[0], t[1], t[2]))
    return paare


# ── Andocken unsicherer Gesichter ──────────────────────────────────────────

def andocken(v, jahre, bild, satz, gruppen_bilder, namensschluessel, verboten=None,
             schwelle: float = ANDOCK_SCHWELLE, abstand: float = ANDOCK_ABSTAND,
             toleranz: int = PHASE_TOLERANZ) -> dict:
    """Unsichere oder bisher kennungslose Gesichter an fertige Gruppen haengen.

    Ein Gesicht dockt an die Gruppe mit dem besten Phasenvergleich, wenn

    * die Aehnlichkeit mindestens ``schwelle`` betraegt UND
    * der Vorsprung vor dem besten **anderen Namen** mindestens ``abstand``
      betraegt - gemessen ZWISCHEN Namen: Gruppen mit gleichem
      ``namensschluessel`` (zwei Kennungen desselben Namens) konkurrieren nicht
      gegeneinander; das Gesicht geht an die beste davon, UND
    * die Gruppe kein Gesicht desselben Bildes enthaelt (zwei Gesichter eines
      Fotos sind zwei Menschen), UND
    * die Gruppe nicht in ``verboten[i]`` steht (ausgeschlossene Kennung).

    Sonst bleibt das Gesicht ohne Kennung - nie geloescht. Gesichter allein gruenden
    keine Gruppe. Die Zuweisung laeuft in absteigender Aehnlichkeit, damit der Platz
    in einer Gruppe an das aehnlichste Gesicht geht; ``gruppen_bilder`` wird dabei
    NICHT veraendert (Kopie). Rueckgabe::

        {"gruppe": ndarray (m,), -1 = ohne Kennung, "aehnlich": ndarray (m,),
         "zaehler": {"angedockt", "keine_passende_phase", "unter_schwelle",
                     "zu_knapp", "gleiches_bild"}}
    """
    m = v.shape[0]
    zaehler = {"angedockt": 0, "keine_passende_phase": 0, "unter_schwelle": 0,
               "zu_knapp": 0, "gleiches_bild": 0}
    ergebnis = np.full(m, -1, dtype=np.int64)
    aehnlich = np.zeros(m, dtype=np.float32)
    if m == 0 or satz["k"] == 0:
        return {"gruppe": ergebnis, "aehnlich": aehnlich, "zaehler": zaehler}
    ids: dict = {}
    nid = np.asarray([ids.setdefault(s, len(ids)) for s in namensschluessel], dtype=np.int64)
    jahre = np.asarray(jahre, dtype=np.float32)
    kandidaten = []
    for start in range(0, m, BLOCK):
        s = gruppen_vergleich(v[start:start + BLOCK], jahre[start:start + BLOCK],
                              satz, toleranz)                               # (b, k)
        if verboten is not None:
            for r in range(s.shape[0]):
                for g in verboten[start + r] or ():
                    s[r, g] = _NICHT_VERGLEICHBAR
        zeilen = np.arange(s.shape[0])
        g1 = np.argmax(s, axis=1)
        erster = s[zeilen, g1]
        andere = np.where(nid[None, :] != nid[g1][:, None], s, np.float32(_NICHT_VERGLEICHBAR))
        zweiter = andere.max(axis=1)
        for r in range(s.shape[0]):
            i = start + r
            wert = float(erster[r])
            if wert <= _NICHT_VERGLEICHBAR + 1e-6:
                zaehler["keine_passende_phase"] += 1
                continue
            if wert < schwelle:
                zaehler["unter_schwelle"] += 1
                continue
            vorsprung = wert - max(float(zweiter[r]), -1.0)
            if vorsprung < abstand:
                zaehler["zu_knapp"] += 1
                continue
            kandidaten.append((wert, i, int(g1[r])))
    kandidaten.sort(key=lambda t: (-t[0], t[1]))
    belegt = [set(b) for b in gruppen_bilder]
    for wert, i, g in kandidaten:
        if bild[i] in belegt[g]:
            zaehler["gleiches_bild"] += 1
            continue
        belegt[g].add(bild[i])
        ergebnis[i] = g
        aehnlich[i] = wert
        zaehler["angedockt"] += 1
    return {"gruppe": ergebnis, "aehnlich": aehnlich, "zaehler": zaehler}
